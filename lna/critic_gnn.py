"""WP-CRITIC Stage-1 GNN (plans2/02-CRITIC §3) — plain-torch MPNN, no PyG.

The feature baselines (critic.py) clear Gate C1 on the family-holdout split but
not on the source-shift split (corpus+templates -> generated arms, ~rho 0.28),
which is the number that matters for ranking generated candidates. This is the
brief's preferred model and the crux experiment: does a graph inductive bias
close that gap? If a GNN can't either, the problem is the generated distribution,
not the surrogate.

Graphs are tiny (<=~16 devices / ~25 nets), so dense per-role adjacency matmuls
beat any sparse library and add no deps (00-OVERVIEW rule 2). Runs on CPU under
the analoggenie env (torch 2.0.1); the 3050 is unnecessary at this size:

    "C:/Users/Devavrat/radioconda/envs/analoggenie/python.exe" lna/critic_gnn.py --eval

Bipartite device<->net message passing with pin-role-specific maps, sum+max
device pooling -> margin head (S11/S21/Idd). Loss = Huber(margins) + rank-hinge
on S21 (hinge margin from the repeat-probe sigma -- do not fit below label
noise). Deep ensemble (5 seeds) -> mean prediction + std (uncertainty for
03-SEARCH). Reported against the critic.py baselines on the same frozen splits.
"""
import argparse
import os
import sys

import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import critic  # noqa: E402  (dataset, splits, metrics, baselines)
from topology import base_of  # noqa: E402

DEV_TYPES = ["NM", "PM", "R", "C", "L"]
ROLES = ["D", "G", "S", "B", "P", "N"]
MOS_PINS, PASSIVE_PINS = ["D", "G", "S", "B"], ["P", "N"]


# --------------------------------------------------------------- graph -> tensors
def _net_class(members):
    s = list(members)
    if "VDD" in s:
        return 0
    if any(m in ("0", "VSS") for m in s):
        return 1
    if any(m.startswith(("VIN", "VOUT")) for m in s):
        return 2
    if any(m.startswith(("VB", "VCM", "VREF", "IB")) for m in s):
        return 3
    return 4                                      # internal node


def graph_tensors(topo):
    devs = sorted(d for d in topo.devices if base_of(d) in DEV_TYPES)
    roots = list(topo.nodes.keys())
    ri = {r: i for i, r in enumerate(roots)}
    pin2root = {m: r for r, members in topo.nodes.items() for m in members}
    nD, nN = len(devs), len(roots)
    dev_feat = np.zeros((nD, len(DEV_TYPES)), np.float32)
    role_adj = np.zeros((len(ROLES), nD, nN), np.float32)
    for i, d in enumerate(devs):
        b = base_of(d)
        dev_feat[i, DEV_TYPES.index(b)] = 1.0
        for role in (MOS_PINS if b in ("NM", "PM") else PASSIVE_PINS):
            root = pin2root.get(f"{d}_{role}")
            if root is not None:
                role_adj[ROLES.index(role), i, ri[root]] = 1.0
    net_feat = np.zeros((nN, 5), np.float32)
    for r, members in topo.nodes.items():
        net_feat[ri[r], _net_class(members)] = 1.0
    return dev_feat, net_feat, role_adj


def build_batch(data):
    """Pad graphs to batch-max device/net counts; return tensors + device mask."""
    tens = [graph_tensors(d["topo"]) for d in data]
    maxD = max(t[0].shape[0] for t in tens)
    maxN = max(t[1].shape[0] for t in tens)
    B = len(tens)
    dev = np.zeros((B, maxD, len(DEV_TYPES)), np.float32)
    net = np.zeros((B, maxN, 5), np.float32)
    adj = np.zeros((B, len(ROLES), maxD, maxN), np.float32)
    dmask = np.zeros((B, maxD), np.float32)
    for k, (df, nf, ra) in enumerate(tens):
        nD, nN = df.shape[0], nf.shape[0]
        dev[k, :nD] = df
        net[k, :nN] = nf
        adj[k, :, :nD, :nN] = ra
        dmask[k, :nD] = 1.0
    Y = np.array([d["y"] for d in data], np.float32)
    return (torch.tensor(dev), torch.tensor(net), torch.tensor(adj),
            torch.tensor(dmask), torch.tensor(Y))


# --------------------------------------------------------------- model
class MPNN(nn.Module):
    def __init__(self, h=64, rounds=3):
        super().__init__()
        self.rounds = rounds
        self.dev_in = nn.Linear(len(DEV_TYPES), h)
        self.net_in = nn.Linear(5, h)
        self.dev_msg = nn.ModuleList([nn.Linear(h, h) for _ in ROLES])   # net<-dev
        self.net_msg = nn.ModuleList([nn.Linear(h, h) for _ in ROLES])   # dev<-net
        self.dev_upd = nn.Linear(h, h)
        self.net_upd = nn.Linear(h, h)
        self.head = nn.Sequential(nn.Linear(2 * h, h), nn.ReLU(),
                                  nn.Linear(h, 3))

    def forward(self, dev, net, adj, dmask):
        hd = torch.relu(self.dev_in(dev))          # [B,nD,H]
        hn = torch.relu(self.net_in(net))          # [B,nN,H]
        for _ in range(self.rounds):
            net_in = sum(adj[:, r].transpose(1, 2) @ self.dev_msg[r](hd)
                         for r in range(len(ROLES)))
            hn = torch.relu(hn + self.net_upd(net_in))
            dev_in = sum(adj[:, r] @ self.net_msg[r](hn)
                         for r in range(len(ROLES)))
            hd = torch.relu(hd + self.dev_upd(dev_in))
        m = dmask.unsqueeze(-1)                     # [B,nD,1]
        s = (hd * m).sum(1)                         # masked sum pool
        mx = (hd + (1 - m) * -1e9).max(1).values    # masked max pool
        return self.head(torch.cat([s, mx], -1))    # [B,3]


# --------------------------------------------------------------- train / predict
def _rank_hinge(pred, true, sigma_norm, idx=1):
    """Pairwise hinge on metric `idx` (S21): pairs whose true gap exceeds label
    noise must be ordered right by at least that gap (02-CRITIC §3)."""
    pt, tt = pred[:, idx], true[:, idx]
    dt = tt[:, None] - tt[None, :]
    dp = pt[:, None] - pt[None, :]
    mask = (dt.abs() > sigma_norm).float()
    loss = torch.relu(sigma_norm - torch.sign(dt) * dp) * mask
    n = mask.sum()
    return loss.sum() / n if n > 0 else pred.sum() * 0.0


def train_one(train, val, sigma_norm, seed=0, epochs=400, h=64, lr=3e-3):
    torch.manual_seed(seed)
    model = MPNN(h=h)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    huber = nn.HuberLoss(delta=1.0)
    Xtr = build_batch(train)
    Xva = build_batch(val) if val else None
    best, best_state, patience = 1e9, None, 0
    for ep in range(epochs):
        model.train()
        opt.zero_grad()
        pred = model(*Xtr[:4])
        loss = huber(pred, Xtr[4]) + 0.5 * _rank_hinge(pred, Xtr[4], sigma_norm)
        loss.backward()
        opt.step()
        if Xva is not None:
            model.eval()
            with torch.no_grad():
                vloss = huber(model(*Xva[:4]), Xva[4]).item()
            if vloss < best - 1e-4:
                best, best_state, patience = vloss, {k: v.clone() for k, v in
                                                     model.state_dict().items()}, 0
            else:
                patience += 1
                if patience >= 40:
                    break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model


def predict(model, data):
    model.eval()
    with torch.no_grad():
        X = build_batch(data)
        return model(*X[:4]).numpy()


def ensemble_predict(train, val, test, sigma_norm, n=5):
    preds = [predict(train_one(train, val, sigma_norm, seed=s), test)
             for s in range(n)]
    P = np.stack(preds)
    return P.mean(0), P.std(0)


# --------------------------------------------------------------- eval
def evaluate_gnn(train, val, test, label, sigma):
    sigma_norm = sigma / 12.0
    Yte = np.array([d["y"] for d in test])
    mean, std = ensemble_predict(train, val, test, sigma_norm, n=5)
    s21 = 1
    rhos = [critic.spearman(Yte[:, k], mean[:, k]) for k in range(3)]
    racc = critic.pairwise_rank_acc(Yte[:, s21], mean[:, s21], sigma_norm)
    enr, n_near = critic.enrichment_top20(Yte, critic._feasibility_score(mean))
    # uncertainty calibration: does ensemble std rank the |error|?
    err = np.abs(mean[:, s21] - Yte[:, s21])
    cal = critic.spearman(std[:, s21], err)
    c1 = (not np.isnan(rhos[s21]) and rhos[s21] >= 0.5
          and not np.isnan(enr) and enr >= 2.0)
    print(f"\n=== {label}: train {len(train)} / val {len(val)} / test {len(test)} "
          f"(sigma_S21={sigma:.3f}) ===")
    print(f"{'model':<10} {'rho_S11':>8} {'rho_S21':>8} {'rho_Idd':>8} "
          f"{'rankacc':>8} {'enrich':>7} {'unc_cal':>8} {'C1?':>5}")
    print(f"{'gnn(ens5)':<10} {rhos[0]:>8.3f} {rhos[1]:>8.3f} {rhos[2]:>8.3f} "
          f"{racc:>8.3f} {enr:>7.2f} {cal:>8.3f} {'YES' if c1 else 'no':>5}")


def run_eval(snapshot=None):
    data = critic.load_dataset(snapshot=snapshot)
    sigma = critic._sigma_s21()
    import datastore as ds
    print(f"GNN critic -- {len(data)} rows, sigma_S21={sigma:.3f}")
    print("(baselines for comparison: run `python lna/critic.py --eval`)")
    sp = ds.family_split(k_holdout=0.25, rows=[d["row"] for d in data])
    id2d = {id(d["row"]): d for d in data}
    tr = [id2d[id(r)] for r in sp["train"] if id(r) in id2d]
    va = [id2d[id(r)] for r in sp["val"] if id(r) in id2d]
    te = [id2d[id(r)] for r in sp["test"] if id(r) in id2d]
    if len(te) >= 3:
        evaluate_gnn(tr, va, te, "family-holdout split", sigma)
    tr2 = [d for d in data if not d["arm"].startswith("campaign-G")]
    te2 = [d for d in data if d["arm"].startswith("campaign-G")]
    if len(te2) >= 3:
        # carve a small val off train2 for early stopping (identity-based split;
        # data dicts hold numpy arrays, so never compare them by ==)
        va2_ids = {id(d) for d in tr2[::6]}
        va2 = [d for d in tr2 if id(d) in va2_ids]
        tr2b = [d for d in tr2 if id(d) not in va2_ids]
        evaluate_gnn(tr2b, va2, te2, "source-shift (corpus+ref+tmpl -> generated)",
                     sigma)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--snapshot")
    args = ap.parse_args()
    if args.eval:
        return run_eval(snapshot=args.snapshot)
    ap.error("give --eval")


if __name__ == "__main__":
    sys.exit(main())
