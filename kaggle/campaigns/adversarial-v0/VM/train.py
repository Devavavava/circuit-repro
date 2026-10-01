#!/usr/bin/env python
"""VM step 2: splits, models (LR / MLP / GNN), out-of-fold predictions, metrics.

usage (via envrun.sh):  train.py [--models lr,mlp,gnn] [--variants bv2,aux] [--splits SF,PA,CELL,TIME]
writes results/oof_<variant>_<split>_<model>.npz, results/metrics.json, results/folds.json,
checkpoints/full_<model>.pt (models trained on all non-fenced bench-v2 rows; used for the
transfer check and as the shipped pruner).
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.set_num_threads(4)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import features as FT  # noqa: E402

RES = f"{HERE}/results"
CKPT = f"{HERE}/checkpoints"
BANDS = ["wb0530", "wb0824", "wb1020", "nb090", "nb158", "nb240", "nb350"]
FLAVORS = ["noise", "gain", "power"]
ANCHORS = ["a1", "a2", "a3", "a4", "a5"]
SEARCH_KINDS = {"search", "confirm"}
WM_CLIP = 2.0
N_SEEDS = {"lr": 1, "mlp": 3, "gnn": 3}


def h(s):
    return int(hashlib.sha1(s.encode()).hexdigest(), 16)


# ------------------------------------------------------------------ data
def load():
    rows = [json.loads(l) for l in gzip.open(f"{HERE}/data/rows.jsonl.gz", "rt")]
    rows = [r for r in rows if r.get("incl")]
    tokmap = json.load(gzip.open(f"{HERE}/data/tokmap.json.gz", "rt"))
    specs = json.load(gzip.open(f"{HERE}/data/specs.json.gz", "rt"))
    return rows, tokmap, specs


def subpop(r):
    if r["src"] != "bench-v2":
        return "aux"
    if r["kind"] in SEARCH_KINDS:
        return "search"
    if r["kind"] == "F2":
        return "F2"
    return "stages"


def make_splits(rows):
    """-> {split: [(fold, train_idx, test_idx, n_dropped_leak)]}; aux rows are never test,
    fenced rows never train."""
    bv = [i for i, r in enumerate(rows) if r["src"] == "bench-v2"]
    aux = [i for i, r in enumerate(rows) if r["src"] != "bench-v2"]
    ts_sorted = sorted(rows[i]["ts"] for i in bv)
    t70 = ts_sorted[int(0.7 * len(ts_sorted))]

    def fold_of(split, r):
        if split == "SF":
            b, f = r["g"].split("-")
            return (BANDS.index(b) + FLAVORS.index(f)) % 3
        if split == "PA":
            return ANCHORS.index(r["lineage"]) if r["lineage"] in ANCHORS else None
        if split == "CELL":
            return h(r["grp"]) % 5
        if split == "TIME":
            return 0 if r["ts"] >= t70 else None
    nf = {"SF": 3, "PA": 5, "CELL": 5, "TIME": 1}
    out = {}
    for split in ("SF", "PA", "CELL", "TIME"):
        fo = {i: fold_of(split, rows[i]) for i in bv}
        lst = []
        for k in range(nf[split]):
            tr = [i for i in bv if fo[i] != k and not rows[i]["fenced"]]
            if split == "TIME":
                tr = [i for i in bv if fo[i] is None and not rows[i]["fenced"]]
            te = [i for i in bv if fo[i] == k]
            keys = {(rows[i]["tok"], rows[i]["spec_sha"]) for i in tr}
            te2 = [i for i in te if (rows[i]["tok"], rows[i]["spec_sha"]) not in keys]
            lst.append((k, tr, te2, len(te) - len(te2)))
        out[split] = lst
    return out, aux, t70


def val_mask(rows, idx):
    return np.array([h(rows[i]["grp"] + "|val") % 10 == 0 for i in idx])


# ------------------------------------------------------------------ models
class Tab(nn.Module):
    def __init__(self, d, hidden):
        super().__init__()
        if hidden:
            self.net = nn.Sequential(nn.Linear(d, hidden), nn.ReLU(), nn.Dropout(0.1),
                                     nn.Linear(hidden, hidden), nn.ReLU(), nn.Dropout(0.1),
                                     nn.Linear(hidden, 2))
        else:
            self.net = nn.Linear(d, 2)

    def forward(self, x, _g=None):
        return self.net(x)


class GNN(nn.Module):
    """Bipartite device<->node MPNN, edge maps per (device type, pin role)."""
    def __init__(self, ds, H=64, L=3):
        super().__init__()
        E = len(FT.EDGE_TYPES)
        self.H, self.E = H, E
        self.dev_emb = nn.Embedding(len(FT.DEV_TYPES), H)
        self.node_emb = nn.Embedding(len(FT.SPECIAL) + 1, H)
        self.d2n = nn.ModuleList([nn.Linear(H, E * H, bias=False) for _ in range(L)])
        self.n2d = nn.ModuleList([nn.Linear(H, E * H, bias=False) for _ in range(L)])
        self.un = nn.ModuleList([nn.Sequential(nn.Linear(2 * H, H), nn.ReLU()) for _ in range(L)])
        self.ud = nn.ModuleList([nn.Sequential(nn.Linear(2 * H, H), nn.ReLU()) for _ in range(L)])
        self.lnn = nn.ModuleList([nn.LayerNorm(H) for _ in range(L)])
        self.lnd = nn.ModuleList([nn.LayerNorm(H) for _ in range(L)])
        self.spec = nn.Sequential(nn.Linear(ds, H), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(7 * H, 128), nn.ReLU(), nn.Dropout(0.1), nn.Linear(128, 2))

    def forward(self, s, g):
        dt, nk, es, ed, et, dgi, ngi, B = g
        hd, hn = self.dev_emb(dt), self.node_emb(nk)
        for l in range(len(self.d2n)):
            md = self.d2n[l](hd).view(-1, self.E, self.H)[es, et]          # [Ne, H]
            agg_n = torch.zeros_like(hn).index_add_(0, ed, md)
            hn = self.lnn[l](hn + self.un[l](torch.cat([hn, agg_n], 1)))
            mn = self.n2d[l](hn).view(-1, self.E, self.H)[ed, et]
            agg_d = torch.zeros_like(hd).index_add_(0, es, mn)
            hd = self.lnd[l](hd + self.ud[l](torch.cat([hd, agg_d], 1)))
        H = self.H
        sd = torch.zeros(B, H).index_add_(0, dgi, hd)
        sn = torch.zeros(B, H).index_add_(0, ngi, hn)
        xd = torch.full((B, H), -1e4).index_reduce_(0, dgi, hd, "amax", include_self=True)
        xn = torch.full((B, H), -1e4).index_reduce_(0, ngi, hn, "amax", include_self=True)
        vin = torch.zeros(B, H).index_add_(0, ngi, hn * (nk == 0).float().unsqueeze(1))
        vout = torch.zeros(B, H).index_add_(0, ngi, hn * (nk == 1).float().unsqueeze(1))
        z = torch.cat([sd, xd, sn, xn, vin, vout, self.spec(s)], 1)
        return self.head(z)


def collate(gl, toks):
    dts, nks, ess, eds, ets, dg, ng = [], [], [], [], [], [], []
    od = on = 0
    for b, t in enumerate(toks):
        dt, nk, es, ed, et = gl[t]
        dts.append(dt); nks.append(nk); ess.append(es + od); eds.append(ed + on); ets.append(et)
        dg.append(np.full(len(dt), b)); ng.append(np.full(len(nk), b))
        od += len(dt); on += len(nk)
    c = lambda a: torch.from_numpy(np.concatenate(a))                   # noqa: E731
    return (c(dts), c(nks), c(ess), c(eds), c(ets), c(dg), c(ng), len(toks))


# ------------------------------------------------------------------ training
def fit_predict(kind, X, Y, WM, toks, gl, tr, va, te_sets, seed):
    """Train on tr (early stop on va BCE); return {name: (p, wm_hat)} for te_sets."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
    Xs = torch.from_numpy((X - mu) / sd).float()
    y = torch.from_numpy(Y).float()
    wm = torch.from_numpy(np.nan_to_num(np.clip(WM, -WM_CLIP, WM_CLIP), nan=0.0)).float()
    wmm = torch.from_numpy(~np.isnan(WM)).float()
    if kind == "gnn":
        model = GNN(X.shape[1])
        lr, bs, maxep, pat = 2e-3, 256, 60, 8
    else:
        model = Tab(X.shape[1], 128 if kind == "mlp" else 0)
        lr, bs, maxep, pat = (3e-3 if kind == "lr" else 1e-3), 512, (200 if kind == "lr" else 100), 10
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4 if kind != "lr" else 1e-3)

    def fwd(idx):
        g = collate(gl, [toks[i] for i in idx]) if kind == "gnn" else None
        return model(Xs[idx], g)

    def loss_of(out, idx):
        bce = F.binary_cross_entropy_with_logits(out[:, 0], y[idx])
        m = wmm[idx]
        hub = (F.smooth_l1_loss(out[:, 1], wm[idx], reduction="none") * m).sum() / m.sum().clamp(min=1)
        return bce + 0.5 * hub, bce

    def predict(idx):
        model.eval()
        ps, ms = [], []
        with torch.no_grad():
            for k in range(0, len(idx), 2048):
                o = fwd(idx[k:k + 2048])
                ps.append(torch.sigmoid(o[:, 0]).numpy()); ms.append(o[:, 1].numpy())
        model.train()
        return (np.concatenate(ps), np.concatenate(ms)) if ps else (np.zeros(0), np.zeros(0))

    best, best_state, bad = 1e9, None, 0
    tr = np.array(tr)
    va = np.array(va)
    for ep in range(maxep):
        perm = np.random.permutation(tr)
        for k in range(0, len(perm), bs):
            idx = perm[k:k + bs]
            out = fwd(idx)
            loss, _ = loss_of(out, idx)
            opt.zero_grad(); loss.backward(); opt.step()
        p, _ = predict(va)
        vb = float(F.binary_cross_entropy(torch.from_numpy(np.clip(p, 1e-6, 1 - 1e-6)), y[va]))
        if vb < best - 1e-4:
            best, bad = vb, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= pat:
                break
    model.load_state_dict(best_state)
    out = {name: predict(np.array(ix)) for name, ix in te_sets.items()}
    return out, model, (mu, sd), ep + 1


# ------------------------------------------------------------------ metrics
def auc(y, p):
    y = np.asarray(y).astype(bool)
    if y.all() or (~y).all():
        return None
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p))
    sp = p[order]
    i = 0
    while i < len(sp):                               # average ranks over ties
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    npos = y.sum()
    return float((ranks[y].sum() - npos * (npos + 1) / 2) / (npos * (len(y) - npos)))


def thr_at_recall(y, p, rec=0.95):
    pos = np.sort(p[np.asarray(y).astype(bool)])
    if len(pos) == 0:
        return None
    k = int(np.floor((1 - rec) * len(pos) + 1e-9))   # may lose k positives
    return float(pos[k])


def prune_at(y, p, thr):
    y = np.asarray(y).astype(bool)
    keep = p >= thr
    return float(1 - keep.mean()), (float(keep[y].mean()) if y.any() else None)


def ece(y, p, nb=10):
    b = np.minimum((p * nb).astype(int), nb - 1)
    e = 0.0
    for k in range(nb):
        m = b == k
        if m.any():
            e += m.mean() * abs(p[m].mean() - np.asarray(y)[m].mean())
    return float(e)


def metric_block(y, p, wmh, wm, thr_dep=None):
    y = np.asarray(y)
    out = {"n": int(len(y)), "pos": int(y.sum()), "auc": auc(y, p)}
    t = thr_at_recall(y, p)
    if t is not None:
        out["prune95_oracle"], out["recall_oracle"] = prune_at(y, p, t)
    if thr_dep is not None and len(y):
        out["prune95_dep"], out["recall_dep"] = prune_at(y, p, thr_dep)
    out["ece"] = ece(y, p) if len(y) else None
    m = ~np.isnan(wm)
    if m.any():
        out["wm_mae"] = float(np.mean(np.abs(np.clip(wm[m], -WM_CLIP, WM_CLIP) - wmh[m])))
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="lr,mlp,gnn")
    ap.add_argument("--variants", default="bv2,aux")
    ap.add_argument("--splits", default="SF,PA,CELL,TIME")
    ap.add_argument("--full", action="store_true", help="also train full-data models")
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    os.makedirs(CKPT, exist_ok=True)
    rows, tokmap, specs = load()
    Hm, Sm, hn, sn, gc = FT.build_arrays(rows, tokmap, specs)
    X = np.concatenate([Hm, Sm], 1)
    Xs_only = Sm
    Y = np.array([r["y"] for r in rows], dtype=np.float32)
    WM = np.array([np.nan if r.get("wm") is None else r["wm"] for r in rows], dtype=np.float64)
    toks = [r["tok"] for r in rows]
    gl = FT.graph_lists(sorted(set(toks)), gc)
    splits, aux, t70 = make_splits(rows)
    json.dump({"t70": t70, "hand_features": hn, "spec_features": sn,
               "folds": {s: [{"fold": k, "n_train": len(tr), "n_test": len(te), "dropped_leak": d,
                              "n_test_fenced": sum(rows[i]["fenced"] for i in te)}
                             for k, tr, te, d in v] for s, v in splits.items()}},
              open(f"{RES}/folds.json", "w"), indent=1)
    mpath = f"{RES}/metrics.json"
    metrics = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for variant in a.variants.split(","):
        for split in a.splits.split(","):
            for model in a.models.split(","):
                key = f"{variant}|{split}|{model}"
                t0 = time.time()
                P = np.full(len(rows), np.nan)
                M = np.full(len(rows), np.nan)
                DEP = {}
                eps = []
                for k, tr, te, _d in splits[split]:
                    tr = tr + (aux if variant == "aux" else [])
                    vm = val_mask(rows, tr)
                    tr_, va_ = [i for i, v in zip(tr, vm) if not v], [i for i, v in zip(tr, vm) if v]
                    acc_p = np.zeros(len(te)); acc_m = np.zeros(len(te))
                    acc_vp = np.zeros(len(va_))
                    for s in range(N_SEEDS[model]):
                        Xin = Sm if model == "gnn" else X
                        o, _mdl, _n, ne = fit_predict(model, Xin, Y, WM, toks, gl, tr_, va_,
                                                      {"te": te, "va": va_}, seed=1000 * k + s)
                        acc_p += o["te"][0]; acc_m += o["te"][1]; acc_vp += o["va"][0]
                        eps.append(ne)
                    ns = N_SEEDS[model]
                    P[te] = acc_p / ns
                    M[te] = acc_m / ns
                    vy = Y[va_]
                    vbv = np.array([rows[i]["src"] == "bench-v2" for i in va_])
                    DEP[k] = thr_at_recall(vy[vbv], (acc_vp / ns)[vbv])
                    for i in te:
                        rows[i].setdefault("_fold", {})[split] = k
                np.savez_compressed(f"{RES}/oof_{variant}_{split}_{model}.npz", p=P, m=M)
                # metrics on pooled OOF
                te_all = [i for i in range(len(rows)) if not np.isnan(P[i])]
                res = {"secs": round(time.time() - t0, 1), "epochs": eps,
                       "thr_dep": {str(k): v for k, v in DEP.items()}}
                for pop in ("all", "search", "F2", "stages", "fenced"):
                    if pop == "fenced":
                        ix = [i for i in te_all if rows[i]["fenced"]]
                    elif pop == "all":
                        ix = [i for i in te_all if not rows[i]["fenced"]]
                    else:
                        ix = [i for i in te_all if not rows[i]["fenced"] and subpop(rows[i]) == pop]
                    if not ix:
                        continue
                    ix = np.array(ix)
                    blk = metric_block(Y[ix], P[ix], M[ix], WM[ix])
                    # deployable: per-fold val threshold applied to that fold's rows
                    keep, n_pos_keep, n_pos = 0, 0, 0
                    for i in ix:
                        t = DEP[rows[i]["_fold"][split]]
                        kk = P[i] >= t
                        keep += kk
                        if Y[i]:
                            n_pos += 1
                            n_pos_keep += kk
                    blk["prune95_dep"] = float(1 - keep / len(ix))
                    blk["recall_dep"] = float(n_pos_keep / n_pos) if n_pos else None
                    # per-fold oracle prune (min over folds) for 'all'
                    if pop == "all":
                        pf = []
                        for k, _tr, te, _d in splits[split]:
                            fi = np.array([i for i in te if not rows[i]["fenced"]])
                            if len(fi) and Y[fi].sum() > 0:
                                t = thr_at_recall(Y[fi], P[fi])
                                pf.append(round(prune_at(Y[fi], P[fi], t)[0], 4))
                        blk["prune95_oracle_per_fold"] = pf
                    res[pop] = blk
                metrics[key] = res
                json.dump(metrics, open(mpath, "w"), indent=1)
                a_ = res["all"]
                print(f"{key}: n={a_['n']} pos={a_['pos']} auc={a_['auc']:.3f} prune95={a_.get('prune95_oracle', 0):.3f} "
                      f"dep={a_['prune95_dep']:.3f}/rec{a_['recall_dep']:.3f} ece={a_['ece']:.3f} "
                      f"mae={a_.get('wm_mae', float('nan')):.3f} | search auc={res.get('search', {}).get('auc')} "
                      f"prune={res.get('search', {}).get('prune95_oracle')} ({res['secs']}s)", flush=True)
    if a.full:
        train_full(rows, X, Sm, Y, WM, toks, gl, a.models.split(","), hn, sn)


def train_full(rows, X, Sm, Y, WM, toks, gl, models, hn, sn):
    """Train on every non-fenced bench-v2 row; evaluate the transfer set (verifier-rl-v1
    rl-v1 rows on v1.2 cells) and save checkpoints."""
    bv = [i for i, r in enumerate(rows) if r["src"] == "bench-v2" and not r["fenced"]]
    tf = [i for i, r in enumerate(rows) if r["src"] == "verifier-rl-v1"]
    fen = [i for i, r in enumerate(rows) if r["fenced"]]
    vm = val_mask(rows, bv)
    tr_, va_ = [i for i, v in zip(bv, vm) if not v], [i for i, v in zip(bv, vm) if v]
    mpath = f"{RES}/metrics.json"
    metrics = json.load(open(mpath))
    for model in models:
        acc = {"tf": np.zeros(len(tf)), "va": np.zeros(len(va_))}
        accm = np.zeros(len(tf))
        states = []
        for s in range(N_SEEDS[model]):
            o, mdl, norm, _ = fit_predict(model, Sm if model == "gnn" else X, Y, WM, toks, gl, tr_, va_,
                                          {"tf": tf, "va": va_}, seed=77 + s)
            acc["tf"] += o["tf"][0]; accm += o["tf"][1]; acc["va"] += o["va"][0]
            states.append({"state": mdl.state_dict(), "mu": norm[0].tolist(), "sd": norm[1].tolist()})
        ns = N_SEEDS[model]
        thr = thr_at_recall(Y[va_], acc["va"] / ns)
        ck = f"{CKPT}/full_{model}.pt"
        torch.save({"model": model, "seeds": states, "thr_val_recall95": thr, "hand_features": hn,
                    "spec_features": sn}, ck)
        p = acc["tf"] / ns
        blk = metric_block(Y[tf], p, accm / ns, WM[tf])
        blk["prune_at_val_thr"], blk["recall_at_val_thr"] = prune_at(Y[tf], p, thr)
        metrics[f"full|transfer-verifier-rl-v1|{model}"] = blk
        metrics[f"full|ckpt|{model}"] = {"bytes": os.path.getsize(ck),
                                         "sha256": hashlib.sha256(open(ck, "rb").read()).hexdigest(),
                                         "thr_val_recall95": thr, "n_train": len(tr_), "n_val": len(va_)}
        print(model, "transfer", blk, flush=True)
    json.dump(metrics, open(mpath, "w"), indent=1)


if __name__ == "__main__":
    main()
