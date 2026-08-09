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
device pooling, the spec-conditioning vector concatenated at the readout
(02-CRITIC §1) -> margin head (S11/S21/Idd/**NF**, the NF term masked on the rows
that predate the series-Rs harness). Loss = Huber(margins) + rank-hinge on S21
(hinge margin from the repeat-probe sigma -- do not fit below label noise). Deep
ensemble (5 seeds) -> mean prediction + std (uncertainty for 03-SEARCH). Reported
against the critic.py baselines on the same frozen splits.

**Result on v4-train (FINDINGS §14.2): this arm ships as critic v1** -- it takes
the headline rho(S21) on both splits (family **0.851** vs 0.790 ridge / 0.687 kNN;
source-shift **0.609** vs 0.585 / 0.370) and, uniquely, its ensemble std ranks
|error| (rho 0.54 / 0.53), which is what 03-SEARCH's `mean - beta*std` needs. Not a
sweep: ridge ties its source-shift precision@20% and beats its rho(S11) there.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import critic  # noqa: E402  (dataset, splits, metrics, baselines)
import datastore as ds  # noqa: E402
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


_SPEC_MU = None      # (mean, std) of the spec-conditioning vector, fit on train


def build_batch(data):
    """Pad graphs to batch-max device/net counts; return tensors + device mask.

    Y is the 4-vector (S11, S21, Idd, NF margins) with a companion mask: NF is
    NaN on the pre-harness rows, so its loss term is masked rather than imputed."""
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
    Y = np.zeros((B, 4), np.float32)
    M = np.ones((B, 4), np.float32)
    for k, d in enumerate(data):
        Y[k, :3] = d["y"]
        if d.get("y_nf") is None:
            M[k, 3] = 0.0
        else:
            Y[k, 3] = d["y_nf"]
    # spec conditioning (02-CRITIC §1): one model, seven specs
    S = np.array([critic.spec_vector(d["spec"]) for d in data], np.float32)
    mu, sd = _SPEC_MU if _SPEC_MU is not None else (S.mean(0), S.std(0) + 1e-6)
    S = (S - mu) / sd
    return (torch.tensor(dev), torch.tensor(net), torch.tensor(adj),
            torch.tensor(dmask), torch.tensor(S), torch.tensor(Y), torch.tensor(M))


# --------------------------------------------------------------- model
class MPNN(nn.Module):
    def __init__(self, h=64, rounds=3, n_spec=len(critic.SPEC_FEATS), n_out=4):
        super().__init__()
        self.rounds = rounds
        self.dev_in = nn.Linear(len(DEV_TYPES), h)
        self.net_in = nn.Linear(5, h)
        self.dev_msg = nn.ModuleList([nn.Linear(h, h) for _ in ROLES])   # net<-dev
        self.net_msg = nn.ModuleList([nn.Linear(h, h) for _ in ROLES])   # dev<-net
        self.dev_upd = nn.Linear(h, h)
        self.net_upd = nn.Linear(h, h)
        self.head = nn.Sequential(nn.Linear(2 * h + n_spec, h), nn.ReLU(),
                                  nn.Linear(h, n_out))

    def forward(self, dev, net, adj, dmask, spec):
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
        return self.head(torch.cat([s, mx, spec], -1))    # [B,4]


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


def _masked_huber(pred, true, mask, delta=1.0):
    d = (pred - true).abs()
    l = torch.where(d < delta, 0.5 * d * d, delta * (d - 0.5 * delta)) * mask
    return l.sum() / mask.sum().clamp(min=1.0)


def train_one(train, val, sigma_norm, seed=0, epochs=400, h=64, lr=3e-3):
    torch.manual_seed(seed)
    model = MPNN(h=h)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    Xtr = build_batch(train)
    Xva = build_batch(val) if val else None
    best, best_state, patience = 1e9, None, 0
    for ep in range(epochs):
        model.train()
        opt.zero_grad()
        pred = model(*Xtr[:5])
        loss = (_masked_huber(pred, Xtr[5], Xtr[6])
                + 0.5 * _rank_hinge(pred, Xtr[5], sigma_norm))
        loss.backward()
        opt.step()
        if Xva is not None:
            model.eval()
            with torch.no_grad():
                vloss = _masked_huber(model(*Xva[:5]), Xva[5], Xva[6]).item()
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
        return model(*X[:5]).numpy()


def ensemble_predict(train, val, test, sigma_norm, n=5):
    preds = [predict(train_one(train, val, sigma_norm, seed=s), test)
             for s in range(n)]
    P = np.stack(preds)
    return P.mean(0), P.std(0)


# --------------------------------------------------------------- eval
def evaluate_gnn(train, val, test, label, sigma):
    global _SPEC_MU
    sigma_norm = sigma / 12.0
    S = np.array([critic.spec_vector(d["spec"]) for d in train], np.float32)
    _SPEC_MU = (S.mean(0), S.std(0) + 1e-6)      # spec scaler fit on TRAIN only
    Yte = np.array([d["y"] for d in test])
    mean, std = ensemble_predict(train, val, test, sigma_norm, n=5)
    s21 = 1
    rhos = [critic.spearman(Yte[:, k], mean[:, k]) for k in range(3)]
    nf_i = [i for i, d in enumerate(test) if d.get("y_nf") is not None]
    rho_nf = (critic.spearman(np.array([test[i]["y_nf"] for i in nf_i]),
                              mean[nf_i, 3]) if len(nf_i) >= 3 else float("nan"))
    racc = critic.pairwise_rank_acc(Yte[:, s21], mean[:, s21], sigma_norm)
    # Gate C1 as RESTATED 2026-08-09 (FINDINGS §14.6): the enrichment half is
    # retired -- its ceiling is min(1/k_frac, 1/base), so it got *harder* as the
    # candidate pool improved and became unsatisfiable by a perfect ranker above
    # base 0.5. `skill` = (prec@20% - base)/(ceiling prec - base) is 0 for random
    # and 1 for perfect at any base rate; the bar is skill >= critic.C1_THETA.
    # `enrich` is still printed for continuity with the historical rows.
    st = critic.c1_stats(Yte, critic._feasibility_score(mean[:, :3]))
    # uncertainty calibration: does ensemble std rank the |error|?
    err = np.abs(mean[:, s21] - Yte[:, s21])
    cal = critic.spearman(std[:, s21], err)
    c1 = critic.c1_pass(rhos[s21], st["skill"])
    print(f"\n=== {label}: train {len(train)} / val {len(val)} / test {len(test)} "
          f"(sigma_S21={sigma:.3f}) ===")
    print(f"{'model':<10} {'rho_S11':>8} {'rho_S21':>8} {'rho_Idd':>8} "
          f"{'rho_NF':>8} {'rankacc':>8} {'prec@20':>8} {'enrich':>7} "
          f"{'ofceil':>7} {'skill':>7} {'unc_cal':>8} {'C1?':>5}")
    print(f"{'gnn(ens5)':<10} {rhos[0]:>8.3f} {rhos[1]:>8.3f} {rhos[2]:>8.3f} "
          f"{rho_nf:>8.3f} {racc:>8.3f} {st['prec']:>8.3f} {st['enrich']:>7.2f} "
          f"{st['frac_ceiling']:>7.3f} {st['skill']:>7.3f} {cal:>8.3f} {c1:>5}")
    print(f"  near-feasible {st['n_near']}/{len(test)} = base {st['base']:.3f}; "
          f"top-20% selects k={st['k']} -> ceiling precision {st['ceil_prec']:.3f} "
          f"(= retired enrichment ceiling {st['ceil_enrich']:.2f}x); "
          f"NF-labeled {len(nf_i)}/{len(test)}")
    print(f"  Gate C1 (restated 2026-08-09) = rho(S21) >= {critic.C1_RHO} AND "
          f"skill >= {critic.C1_THETA} (0 = random, 1 = perfect at any base rate); "
          f"here that is prec@20% >= "
          f"{st['base'] + critic.C1_THETA * (st['ceil_prec'] - st['base']):.3f}, "
          f"where the retired {critic.C1_ENRICH_LEGACY:.0f}x bar demanded "
          f"{min(critic.C1_ENRICH_LEGACY * st['base'], 1.0):.3f}"
          f"{' -- UNREACHABLE' if critic.C1_ENRICH_LEGACY * st['base'] > st['ceil_prec'] + 1e-12 else ''}.")
    critic._per_spec(test, Yte, {"trivial": mean, "gnn": mean}, s21)


# ============================================ off-distribution (mutant) eval
# FINDINGS §15.4 measured critic v1 collapsing from rho ~0.83 on its own family
# holdout to rho ~0.17-0.20 on the mutant distribution `evolve.py` generates, and
# blamed coverage: v4-train had 16 wideband-sdr and 24 dhruva-s rows. The evolve
# run then appended 213 rows on exactly those two specs. This mode answers "did
# the coverage fix it?" without letting the answer be leakage -- ALL of the new
# coverage on those specs came from the very rows we score against, so a model
# trained on everything would be marking its own homework.
#
# Three regimes, same protocol, same test rows:
#   v1-equiv  train on every NON-evolve row  -> reproduces v1's coverage exactly
#   v2-cv     k-fold over evolve WL-FAMILIES -> the coverage benefit, out-of-fold
#   v2-leaky  train on everything            -> upper bound, quoted as leakage
EVOLVE_PREFIX = "evolve-"


def _fit_ensemble(pool, sigma_norm, n_models, k_holdout=0.25, seed0=0):
    """Train an ensemble on `pool` exactly the way the deployed scorer does
    (`evolve_score.Scorer`): family split, train on the train families, early-stop
    on val, keep the untouched test families for the uncertainty-gate p90 and the
    in-distribution reference numbers."""
    sp = ds.family_split(k_holdout=k_holdout, rows=[d["row"] for d in pool])
    id2d = {id(d["row"]): d for d in pool}
    tr = [id2d[id(r)] for r in sp["train"] if id(r) in id2d]
    va = [id2d[id(r)] for r in sp["val"] if id(r) in id2d]
    te = [id2d[id(r)] for r in sp["test"] if id(r) in id2d]
    global _SPEC_MU
    S = np.array([critic.spec_vector(d["spec"]) for d in tr], np.float32)
    _SPEC_MU = (S.mean(0), S.std(0) + 1e-6)
    models = [train_one(tr, va, sigma_norm, seed=seed0 + s) for s in range(n_models)]

    def ens(items):
        P = np.stack([predict(m, items) for m in models])
        return P.mean(0), P.std(0)

    hmean, hstd = ens(te)
    Yte = np.array([d["y"] for d in te])
    herr = np.abs(hmean[:, 1] - Yte[:, 1])
    info = {"n_train": len(tr), "n_val": len(va), "n_holdout": len(te),
            "rho_s21_holdout": critic.spearman(Yte[:, 1], hmean[:, 1]),
            "unc_cal_holdout": critic.spearman(hstd[:, 1], herr),
            "sigma_gate_p90": float(np.percentile(hstd[:, :3].mean(1), 90)),
            "sigma_med_holdout": float(np.median(hstd[:, :3].mean(1)))}
    return ens, info


def _margin_cols(spec):
    """Which of the 4 heads this spec gates (== evolve.margin_cols; inlined so
    this module does not import the sizer stack under the py-3.8 torch env)."""
    cols = [0, 1, 2]
    c = spec.constraints.get("nf_db") or {}
    if c.get("status") != "unsupported" and c.get("max") is not None:
        cols.append(3)
    return cols


def _feas_scalar(vec):
    """05-SIZING feasibility-first scalar (== evolve.feasibility_score)."""
    short = sum(min(v, 0.0) for v in vec)
    return short if short < 0 else sum(max(v, 0.0) for v in vec)


def _mutant_metrics(items, mean, std, gate):
    """Everything §15.4 reported, per group, plus the calibration diagnostics."""
    from spec import Spec
    sp = Spec.load(items[0]["spec"])
    cols = _margin_cols(sp)
    real = [[d["y"][0], d["y"][1], d["y"][2], d.get("y_nf")] for d in items]
    out = {"n": len(items)}
    for k, nm in enumerate(("S11", "S21", "Idd", "NF")):
        ix = [i for i, r in enumerate(real) if r[k] is not None]
        out["rho_" + nm] = (critic.spearman(np.array([real[i][k] for i in ix]),
                                            mean[ix, k]) if len(ix) >= 3
                            else float("nan"))
    fs = _feas_scalar
    fp = np.array([fs([mean[i][c] for c in cols]) for i in range(len(items))])
    fr = np.array([fs([-4.0 if real[i][c] is None else real[i][c] for c in cols])
                   for i in range(len(items))])
    cons = np.array([fs([mean[i][c] - std[i][c] for c in cols])
                     for i in range(len(items))])
    unc = std[:, :3].mean(1)
    err = np.abs(fp - fr)
    out["rho_fs"] = critic.spearman(fp, fr)
    out["rho_cons"] = critic.spearman(cons, fr)
    out["unc_cal"] = critic.spearman(unc, err)
    out["sigma_med"] = float(np.median(unc))
    out["n_above_gate"] = int((unc > gate).sum())
    near = np.array([all(r[c] is None or r[c] > critic.NEAR_FEASIBLE
                         for c in cols) for r in real])
    n, n_near = len(near), int(near.sum())
    base = float(near.mean())
    k = max(1, int(round(0.2 * n)))
    out.update(base=base, k=k, n_near=n_near)
    if n_near:
        ceil_prec = min(n_near, k) / float(k)
        prec = float(near[np.argsort(-fp)[:k]].mean())
        out.update(prec=prec, ceil_prec=ceil_prec, enrich=prec / base,
                   skill=((prec - base) / (ceil_prec - base)
                          if ceil_prec - base > 1e-12 else float("nan")))
    else:
        out.update(prec=float("nan"), ceil_prec=float("nan"),
                   enrich=float("nan"), skill=float("nan"))
    return out


def _fold_families(rows, n_folds, seed=0):
    """Assign whole WL families of the mutant rows to CV folds (never a row-level
    split -- the mutants are dense with near-duplicates by construction)."""
    import hashlib
    fams = ds._families(rows)
    keyed = sorted(fams, key=lambda mem: min(str(rows[i].get("wl_hash") or i)
                                             for i in mem))
    fold = [0] * len(rows)
    for fi, mem in enumerate(sorted(keyed, key=lambda mem: hashlib.blake2b(
            ("%d:%s" % (seed, min(str(rows[i].get("wl_hash") or i)
                                  for i in mem))).encode(),
            digest_size=8).hexdigest())):
        for i in mem:
            fold[i] = fi % n_folds
    return fold, len(keyed)


def mutant_eval(snapshot=None, sigma_recipe=None, n_models=5, folds=3,
                regimes=("v1-equiv", "v2-cv", "v2-leaky"), out=None):
    data = critic.load_dataset(snapshot=snapshot)
    sigma = critic._sigma_s21(recipe=sigma_recipe, snapshot=snapshot)
    sigma_norm = sigma / 12.0
    mut = [d for d in data if d["arm"].startswith(EVOLVE_PREFIX)]
    rest = [d for d in data if not d["arm"].startswith(EVOLVE_PREFIX)]
    mrows = [d["row"] for d in mut]
    fold, n_fam = _fold_families(mrows, folds)
    groups = sorted(set((d["spec"], d["arm"]) for d in mut))
    print("mutant post-hoc eval -- snapshot=%s, sigma_S21=%.3f, %d evolve rows "
          "in %d WL families, %d folds, ens-%d"
          % (snapshot, sigma, len(mut), n_fam, folds, n_models))
    print("  groups: " + ", ".join("%s/%s=%d" % (s, a, sum(
        1 for d in mut if d["spec"] == s and d["arm"] == a)) for s, a in groups))
    print("  non-evolve pool: %d rows (this is critic v1's coverage on the two "
          "search specs: wideband-sdr=%d, dhruva-s=%d)"
          % (len(rest), sum(1 for d in rest if d["spec"] == "wideband-sdr"),
             sum(1 for d in rest if d["spec"] == "dhruva-s")))
    results = {}
    for reg in regimes:
        t0 = time.time()
        pred_mean = [None] * len(mut)
        pred_std = [None] * len(mut)
        infos = []
        if reg == "v2-cv":
            for f in range(folds):
                pool = rest + [d for i, d in enumerate(mut) if fold[i] != f]
                test_ix = [i for i in range(len(mut)) if fold[i] == f]
                if not test_ix:
                    continue
                ens, info = _fit_ensemble(pool, sigma_norm, n_models)
                m, s = ens([mut[i] for i in test_ix])
                for j, i in enumerate(test_ix):
                    pred_mean[i], pred_std[i] = m[j], s[j]
                info["fold"] = f
                info["n_test"] = len(test_ix)
                infos.append(info)
                print("  [%s] fold %d/%d: %s" % (reg, f + 1, folds,
                                                 json.dumps(_r3(info))), flush=True)
        else:
            pool = rest if reg == "v1-equiv" else rest + mut
            ens, info = _fit_ensemble(pool, sigma_norm, n_models)
            m, s = ens(mut)
            for i in range(len(mut)):
                pred_mean[i], pred_std[i] = m[i], s[i]
            infos.append(info)
            print("  [%s] %s" % (reg, json.dumps(_r3(info))), flush=True)
        gate = float(np.mean([i["sigma_gate_p90"] for i in infos]))
        mean = np.stack(pred_mean)
        std = np.stack(pred_std)
        rows = []
        for spec_name, arm in groups:
            ix = [i for i, d in enumerate(mut)
                  if d["spec"] == spec_name and d["arm"] == arm]
            if len(ix) < 5:
                continue
            r = _mutant_metrics([mut[i] for i in ix], mean[ix], std[ix], gate)
            r.update(spec=spec_name, arm=arm, regime=reg)
            rows.append(r)
        results[reg] = {"infos": infos, "gate": gate, "groups": rows,
                        "secs": round(time.time() - t0, 1)}
        _print_mutant(reg, rows, infos, gate)
    if out:
        with open(out, "w") as fh:
            json.dump(results, fh, indent=1, default=float)
        print("\nwrote " + out)
    return 0


def _r3(d):
    return dict((k, (round(v, 3) if isinstance(v, float) else v))
                for k, v in d.items())


def _print_mutant(reg, rows, infos, gate):
    rho_h = float(np.mean([i["rho_s21_holdout"] for i in infos]))
    cal_h = float(np.mean([i["unc_cal_holdout"] for i in infos]))
    print("\n=== regime %s: in-distribution holdout rho(S21)=%.3f, holdout "
          "unc_cal=%.3f, uncertainty gate p90=%.4f ===" % (reg, rho_h, cal_h, gate))
    print("%-14s %-14s %4s %8s %8s %8s %8s %8s %6s %7s %7s %6s"
          % ("spec", "arm", "n", "rho_S21", "rho_fs", "rho_cons", "unc_cal",
             "sig_med", "base", "prec20", "skill", "gated"))
    for r in rows:
        print("%-14s %-14s %4d %8.3f %8.3f %8.3f %8.3f %8.4f %6.3f %7.3f %7.3f "
              "%3d/%d" % (r["spec"], r["arm"], r["n"], r["rho_S21"], r["rho_fs"],
                          r["rho_cons"], r["unc_cal"], r["sigma_med"], r["base"],
                          r["prec"], r["skill"], r["n_above_gate"], r["n"]))


def run_eval(snapshot=None, sigma_recipe=None):
    data = critic.load_dataset(snapshot=snapshot)
    sigma = critic._sigma_s21(recipe=sigma_recipe, snapshot=snapshot)
    print(f"GNN critic -- {len(data)} rows, sigma_S21={sigma:.3f}, "
          f"generated {sum(d['gen'] for d in data)}, "
          f"NF-labeled {sum(d.get('y_nf') is not None for d in data)}")
    print("(baselines for comparison: run `python lna/critic.py --eval`)")
    sp = ds.family_split(k_holdout=0.25, rows=[d["row"] for d in data])
    id2d = {id(d["row"]): d for d in data}
    tr = [id2d[id(r)] for r in sp["train"] if id(r) in id2d]
    va = [id2d[id(r)] for r in sp["val"] if id(r) in id2d]
    te = [id2d[id(r)] for r in sp["test"] if id(r) in id2d]
    if len(te) >= 3:
        evaluate_gnn(tr, va, te, "family-holdout split", sigma)
    tr2, te2 = critic._source_shift(data)
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
    ap.add_argument("--mutant-eval", action="store_true",
                    help="score the evolve-run rows off-distribution (FINDINGS "
                         "§15.4), leak-free by family CV")
    ap.add_argument("--snapshot")
    ap.add_argument("--sigma-recipe")
    ap.add_argument("--n-models", type=int, default=5)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--regimes", default="v1-equiv,v2-cv,v2-leaky")
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.mutant_eval:
        return mutant_eval(snapshot=args.snapshot,
                           sigma_recipe=args.sigma_recipe,
                           n_models=args.n_models, folds=args.folds,
                           regimes=tuple(args.regimes.split(",")), out=args.out)
    if args.eval:
        return run_eval(snapshot=args.snapshot, sigma_recipe=args.sigma_recipe)
    ap.error("give --eval")


if __name__ == "__main__":
    sys.exit(main())
