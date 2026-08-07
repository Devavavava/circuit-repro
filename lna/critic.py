"""WP-CRITIC (plans2/02-CRITIC) — the pre-SPICE surrogate, baselines first.

This is the *mandatory baseline* half of the critic (§2): trivial / WL-kNN / ridge
on hand features, on the frozen family split (§4), reporting per-metric Spearman,
pairwise rank accuracy, and near-feasibility enrichment against the repeat-probe
sigma ceiling. The GNN (§3, WSL GPU) ships as critic v1 only if it beats these;
these run in the torch-free py-3.14 stack, no new deps.

Target (00-OVERVIEW R1): the per-metric **normalized margin vector** (achieved −
required)/scale, already stored on every L2 row by datastore.margins_for. We
predict S11/S21/Idd margins; feasibility is *computed* from margins, never a
trained boolean. S21 is the binding constraint everywhere (FINDINGS §5b), so its
Spearman is the headline (Gate C1: >= 0.5 on held-out families).

Rows without tokens (hand reference decks) can't be graph-featurized and are
dropped, so the critic set is the corpus + generated topologies.

    python lna/critic.py --eval          # full baseline report on the store
    python lna/critic.py --eval --snapshot v1-train
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds  # noqa: E402
from topology import Topology, base_of  # noqa: E402
from novelty import wl_features, wl_cosine  # noqa: E402

METRICS = ["s11_db", "s21_db", "idd_ma"]
MARGIN_CLIP = (-4.0, 2.0)     # scale units; degenerate S21=-600 rows clip to floor
NEAR_FEASIBLE = -1.0          # a margin > -1 scale unit is "near-feasible" (§4)


# --------------------------------------------------------------- dataset
def _margins(row):
    """(s11, s21, idd) clipped margins, or None if any is missing."""
    mg = row.get("margins") or {}
    out = []
    for m in METRICS:
        v = (mg.get(m) or {}).get("margin")
        if v is None:
            return None
        out.append(min(max(v, MARGIN_CLIP[0]), MARGIN_CLIP[1]))
    return out


def load_dataset(snapshot=None):
    """Token-bearing L2 rows with a full margin vector. Returns a list of
    {row, tokens, topo, wl, y} dicts (wl/topo cached once)."""
    data = []
    for r in ds.load("topo_labels", snapshot=snapshot):
        toks = (r.get("graph") or {}).get("tokens")
        y = _margins(r)
        if not toks or y is None:
            continue
        topo = Topology(toks)
        data.append({"row": r, "topo": topo, "wl": wl_features(topo)[1],
                     "y": np.array(y, float), "spec": r.get("spec"),
                     "arm": (r.get("provenance") or {}).get("source_arm", "?")})
    return data


# --------------------------------------------------------------- features
def graph_stats(topo):
    c = topo.counts()
    deg = _degrees(topo)
    n = topo.n_devices or 1
    return [topo.n_devices, len(topo.nets), topo.wire_edges,
            topo.n_inductors, topo.inductor_ratio,
            c.get("NM", 0), c.get("PM", 0), c.get("R", 0), c.get("C", 0),
            c.get("L", 0), (c.get("NM", 0) + c.get("PM", 0)) / n,
            max(deg) if deg else 0, sum(deg) / len(deg) if deg else 0]


def _degrees(topo):
    """Device node degrees over the electrical-node graph (how many distinct
    nodes each device touches)."""
    from collections import defaultdict
    pin2node, degs = {}, []
    for root, members in topo.nodes.items():
        for m in members:
            pin2node[m] = root
    by_dev = defaultdict(set)
    import re
    pin_re = re.compile(r"^([A-Z_]+\d+)_[A-Z]+$")
    for p in topo.pins:
        mm = pin_re.match(p)
        if mm and p in pin2node:
            by_dev[mm.group(1)].add(pin2node[p])
    return [len(v) for v in by_dev.values()]


def build_wl_vocab(train):
    vocab = {}
    for d in train:
        for k in d["wl"]:
            vocab.setdefault(k, len(vocab))
    return vocab


def wl_vector(feat, vocab):
    v = np.zeros(len(vocab))
    for k, c in feat.items():
        j = vocab.get(k)
        if j is not None:
            v[j] = c
    return v


def feature_matrix(data, vocab):
    rows = [np.concatenate([graph_stats(d["topo"]), wl_vector(d["wl"], vocab)])
            for d in data]
    return np.array(rows)


# --------------------------------------------------------------- baselines
def fit_ridge(X, Y, lam=10.0):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    Xs = np.hstack([Xs, np.ones((len(Xs), 1))])          # bias column
    A = Xs.T @ Xs + lam * np.eye(Xs.shape[1])
    W = np.linalg.solve(A, Xs.T @ Y)
    return (mu, sd, W)


def pred_ridge(model, X):
    mu, sd, W = model
    Xs = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
    return Xs @ W


def pred_knn(train, test):
    """Nearest train neighbor by WL-cosine; predict its margin vector."""
    out = []
    for d in test:
        best, who = -1.0, None
        for t in train:
            s = wl_cosine(d["wl"], t["wl"])
            if s > best:
                best, who = s, t
        out.append(who["y"])
    return np.array(out)


# --------------------------------------------------------------- metrics
def _rankdata(x):
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), float)
    ranks[order] = np.arange(len(x))
    # average ties
    x = np.asarray(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks


def spearman(a, b):
    if len(a) < 3 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return float("nan")
    ra, rb = _rankdata(a), _rankdata(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def pairwise_rank_acc(y_true, y_pred, sigma):
    """Fraction of comparable pairs (|Δtrue| > sigma) ordered correctly."""
    n, ok, tot = len(y_true), 0, 0
    for i in range(n):
        for j in range(i + 1, n):
            if abs(y_true[i] - y_true[j]) <= sigma:
                continue
            tot += 1
            if (y_true[i] - y_true[j]) * (y_pred[i] - y_pred[j]) > 0:
                ok += 1
    return ok / tot if tot else float("nan")


def enrichment_top20(y_true_margins, score):
    """Enrichment of near-feasible rows in the top-20% by score vs base rate.
    y_true_margins: (n,3) array; near-feasible = all margins > NEAR_FEASIBLE."""
    near = (y_true_margins > NEAR_FEASIBLE).all(1)
    base = near.mean()
    if base == 0:
        return float("nan"), 0
    if np.std(score) < 1e-9:          # no ranking signal (e.g. trivial) -> random
        return 1.0, int(near.sum())
    k = max(1, int(round(0.2 * len(score))))
    top = np.argsort(-score)[:k]
    return (near[top].mean() / base), int(near.sum())


# --------------------------------------------------------------- evaluation
def _sigma_s21():
    from collections import defaultdict
    by = defaultdict(list)
    for r in ds.load("topo_labels"):
        m = r.get("metrics") or {}
        if m.get("s21_db") is not None:
            by[(r.get("wl_hash"), r.get("spec"))].append(m["s21_db"])
    import statistics
    s = [statistics.pstdev(v) for v in by.values() if len(v) >= 2]
    return (sum(s) / len(s)) if s else 0.5


def _feasibility_score(pred):
    """05-SIZING feasibility-first scalar from predicted margins: higher = better
    (search/ranking yardstick). Feasible (all>=0) -> positive by slack; else the
    negative summed shortfall."""
    short = np.minimum(pred, 0.0).sum(1)          # 0 if all feasible, else <0
    slack = np.maximum(pred, 0.0).sum(1)
    return np.where((pred >= 0).all(1), slack, short)


def evaluate(train, test, label, sigma):
    vocab = build_wl_vocab(train)
    Xtr, Xte = feature_matrix(train, vocab), feature_matrix(test, vocab)
    Ytr = np.array([d["y"] for d in train])
    Yte = np.array([d["y"] for d in test])
    preds = {
        "trivial": np.tile(Ytr.mean(0), (len(test), 1)),
        "wl_knn": pred_knn(train, test),
        "ridge": pred_ridge(fit_ridge(Xtr, Ytr), Xte),
    }
    s21 = METRICS.index("s21_db")
    print(f"\n=== {label}: train {len(train)} / test {len(test)} "
          f"(sigma_S21={sigma:.3f} dB) ===")
    print(f"{'model':<9} {'rho_S11':>8} {'rho_S21':>8} {'rho_Idd':>8} "
          f"{'rankacc':>8} {'enrich':>7} {'C1?':>5}")
    for name, P in preds.items():
        rhos = [spearman(Yte[:, k], P[:, k]) for k in range(3)]
        racc = pairwise_rank_acc(Yte[:, s21], P[:, s21], sigma / 12.0)
        enr, n_near = enrichment_top20(Yte, _feasibility_score(P))
        c1 = (not math.isnan(rhos[s21]) and rhos[s21] >= 0.5
              and not math.isnan(enr) and enr >= 2.0)
        print(f"{name:<9} {rhos[0]:>8.3f} {rhos[1]:>8.3f} {rhos[2]:>8.3f} "
              f"{racc:>8.3f} {enr:>7.2f} {'YES' if c1 else 'no':>5}")
    print(f"  near-feasible test rows (all margins > {NEAR_FEASIBLE} scale unit): "
          f"{n_near}/{len(test)} -- the enrichment base rate. Fully-feasible "
          "(all margins > 0) awaits templates / Stage-2 search.")


def _source_shift(data):
    """Train on corpus + references, test on generated arms (03-SEARCH's shift)."""
    tr = [d for d in data if not d["arm"].startswith("campaign-G")]
    te = [d for d in data if d["arm"].startswith("campaign-G")]
    return tr, te


def run_eval(snapshot=None):
    data = load_dataset(snapshot=snapshot)
    sigma = _sigma_s21()
    print(f"critic baselines -- {len(data)} token-bearing L2 rows "
          f"(feasible in set: {sum((d['y'] > 0).all() for d in data)})")
    sp = ds.family_split(k_holdout=0.25, rows=[d["row"] for d in data])
    # map split rows back to dataset dicts by identity of the row dict; baselines
    # need no val set, so val families join train (more signal, same holdout).
    id2d = {id(d["row"]): d for d in data}
    train = [id2d[id(r)] for r in (sp["train"] + sp["val"]) if id(r) in id2d]
    test = [id2d[id(r)] for r in sp["test"] if id(r) in id2d]
    if len(test) >= 3 and len(train) >= 10:
        evaluate(train, test, "family-holdout split", sigma)
    else:
        print(f"  family split too small (train {len(train)}/test {len(test)})")
    tr2, te2 = _source_shift(data)
    if len(te2) >= 3 and len(tr2) >= 10:
        evaluate(tr2, te2, "source-shift (corpus+ref -> generated)", sigma)
    else:
        print(f"\n  source-shift split too small (train {len(tr2)}/test {len(te2)})")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eval", action="store_true", help="run the baseline report")
    ap.add_argument("--snapshot", help="pin the training/eval set to a snapshot")
    args = ap.parse_args()
    if args.eval:
        return run_eval(snapshot=args.snapshot)
    ap.error("give --eval")


if __name__ == "__main__":
    sys.exit(main())
