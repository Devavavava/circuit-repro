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
dropped, so the critic set is the corpus + templates + generated topologies.

The store is **multi-spec** as of v4-train (wifi24 / gps-l1 / wideband-sdr /
dhruva-{l5,l2,l1,s}), which changes three things: the S11 target is whichever S11
constraint the spec gates (`s11_max_db` for broadband specs -- reading `s11_db`
alone silently dropped every dhruva row); every arm is spec-conditioned; and the
pooled Spearman is an upper bound, so `_per_spec` reports the within-spec rho that
search actually consumes.

    python lna/critic.py --eval          # full baseline report on the store
    python lna/critic.py --eval --snapshot v4-train --sigma-recipe candidate-v1+bo3
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
# The S11 constraint has two names: broadband specs (dhruva-*, wideband-sdr) gate
# `s11_max_db` (worst point over the band), narrowband specs gate `s11_db` at f0.
# Reading only `s11_db` silently DROPPED every dhruva row from the critic set --
# ~240 of tonight's rows, including the whole Track-B corpus. The target is "the
# spec's S11 margin", whichever name that spec uses.
S11_SLOTS = ("s11_max_db", "s11_db")
MARGIN_CLIP = (-4.0, 2.0)     # scale units; degenerate S21=-600 rows clip to floor
NEAR_FEASIBLE = -1.0          # a margin > -1 scale unit is "near-feasible" (§4)
_SPEC_CACHE = {}


# --------------------------------------------------------------- dataset
def _spec(name):
    from spec import Spec
    if name not in _SPEC_CACHE:
        _SPEC_CACHE[name] = Spec.load(name)
    return _SPEC_CACHE[name]


def _margins(row):
    """(s11, s21, idd) clipped margins, or None if any is missing."""
    mg = row.get("margins") or {}
    out = []
    for m in METRICS:
        if m == "s11_db":
            v = next((mg[s]["margin"] for s in S11_SLOTS
                      if (mg.get(s) or {}).get("supported")
                      and mg[s].get("margin") is not None), None)
        else:
            v = (mg.get(m) or {}).get("margin")
        if v is None:
            return None
        out.append(min(max(v, MARGIN_CLIP[0]), MARGIN_CLIP[1]))
    return out


def nf_margin(row):
    """Normalized NF margin (limit - measured)/scale, or None.

    Computed from the spec YAML *live* rather than from the row's stored
    `margins.nf_db.supported`: every row written before WP-D1 was logged with NF
    forced `unsupported`, yet its `metrics.nf_db` is a perfectly good series-Rs
    measurement of that sized point. Only `nf_method == "series_rs"` rows count --
    the retired port-referred NF (finding #7) flattered every design by +0.55…
    +12.58 dB and must never be a training target."""
    m = row.get("metrics") or {}
    if m.get("nf_method") != "series_rs" or m.get("nf_db") is None:
        return None
    c = _spec(row["spec"]).constraints.get("nf_db") or {}
    lim = c.get("max")
    if lim is None:
        return None
    v = (lim - m["nf_db"]) / max(abs(lim), 1.0)
    return min(max(v, MARGIN_CLIP[0]), MARGIN_CLIP[1])


def is_generated(row):
    """Did a *generator* produce this topology (vs corpus / hand ref / template)?

    The source-shift split (§4) is "corpus + ref + templates -> generated", and
    tonight that is no longer just `campaign-G`: g4-generated, p5v3-gen and the
    ~200 Track-B rows are generator output too, while dhruva-label / broaden-label
    / d3-lownoise are `templates.py` archetypes. The discriminator is the
    provenance: a generated row points at a sampled token file outside the
    templates dir; an archetype row names an `archetype`."""
    p = row.get("provenance") or {}
    tf = (p.get("token_file") or p.get("gen_file") or "").replace("\\", "/")
    return bool(tf) and "out/templates/" not in tf and not p.get("archetype")


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
                     "y_nf": nf_margin(r), "gen": is_generated(r),
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


SPEC_FEATS = ["s21_min", "idd_max", "nf_max", "s11_max", "f0_ghz", "band_frac"]


def spec_vector(name):
    """Spec conditioning (02-CRITIC §1): the constraint thresholds + band, so one
    model serves all seven specs. Mandatory now that the store spans wifi24 /
    gps-l1 / wideband-sdr / dhruva-{l5,l2,l1,s}: the SAME topology carries
    different margins against different specs, and a graph-only feature vector
    cannot tell those rows apart -- it just averages them."""
    sp = _spec(name)
    c = sp.constraints
    g = lambda k, b, d: (c.get(k) or {}).get(b, d)          # noqa: E731
    b = sp.band or {}
    f0 = float(b.get("f0") or 2.4e9)
    lo, hi = b.get("f_lo"), b.get("f_hi")
    frac = (float(hi) - float(lo)) / f0 if (lo and hi) else 0.0
    return [float(g("s21_db", "min", 0.0)), float(g("idd_ma", "max", 10.0)),
            float(g("nf_db", "max", 10.0)),
            float(g("s11_max_db", "max", g("s11_db", "max", -10.0))),
            f0 / 1e9, frac]


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
    rows = [np.concatenate([graph_stats(d["topo"]), spec_vector(d["spec"]),
                            wl_vector(d["wl"], vocab)]) for d in data]
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


def pred_knn(train, test, key="y"):
    """Nearest train neighbor by WL-cosine; predict its margin vector.

    Spec-conditioned: the neighbor is searched *within the same spec* first,
    because a margin is only meaningful against the spec it was measured for --
    an unconditioned neighbor would happily hand a dhruva-s row a wifi24 label.
    Falls back to the global nearest neighbor when the test row's spec is absent
    from train (the honest degradation, and it is reported as such)."""
    out = []
    for d in test:
        who = _nn(d, [t for t in train if t["spec"] == d["spec"]], key) \
            or _nn(d, train, key)
        out.append(who[key] if who is not None else 0.0)
    return np.array(out)


def _nn(d, pool, key="y"):
    best, who = -1.0, None
    for t in pool:
        if t.get(key) is None:
            continue
        s = wl_cosine(d["wl"], t["wl"])
        if s > best:
            best, who = s, t
    return who


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
    y_true_margins: (n,3) array; near-feasible = all margins > NEAR_FEASIBLE.

    Returns (enrichment, n_near, precision@20%, ceiling). ⚠ **The ceiling matters
    for reading Gate C1.** Enrichment is precision@20% / base-rate, and precision
    cannot exceed 1, so the metric is capped at 1/base-rate: once ~50% of the test
    pool is near-feasible, a *perfect* ranker scores only 2.0x. C1's "enrichment
    >= 2x" was set when the pool was mostly far-from-feasible; as the pool
    improves the same bar silently becomes "perfect precision@20%". Always read
    enrichment against its ceiling, and precision@20% as the model's real skill."""
    near = (y_true_margins > NEAR_FEASIBLE).all(1)
    base = near.mean()
    if base == 0:
        return float("nan"), 0, float("nan"), float("nan")
    ceil = 1.0 / base
    if np.std(score) < 1e-9:          # no ranking signal (e.g. trivial) -> random
        return 1.0, int(near.sum()), float(base), ceil
    k = max(1, int(round(0.2 * len(score))))
    top = np.argsort(-score)[:k]
    prec = float(near[top].mean())
    return prec / base, int(near.sum()), prec, ceil


# --------------------------------------------------------------- evaluation
def _sigma_s21(recipe=None, snapshot=None):
    """Repeat-probe sigma(S21), conditioned on the full label domain (recipe + nf
    gating) -- see campaign.sigma_key for why pooling recipes was wrong -- and on
    the snapshot being evaluated, so a run stays reproducible as the store grows.
    `recipe='candidate-v1+bo3'` gives the best-of-3 label noise."""
    import campaign
    s, n = campaign._sigma_from_repeats(recipe=recipe, snapshot=snapshot)
    return s if s is not None else 0.5


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
    nf = _nf_arm(train, test, vocab, Xtr, Xte)
    s21 = METRICS.index("s21_db")
    print(f"\n=== {label}: train {len(train)} / test {len(test)} "
          f"(sigma_S21={sigma:.3f} dB) ===")
    print(f"{'model':<9} {'rho_S11':>8} {'rho_S21':>8} {'rho_Idd':>8} "
          f"{'rho_NF':>8} {'rankacc':>8} {'prec@20':>8} {'enrich':>7} {'C1?':>5}")
    n_near, ceil = 0, float("nan")
    for name, P in preds.items():
        rhos = [spearman(Yte[:, k], P[:, k]) for k in range(3)]
        racc = pairwise_rank_acc(Yte[:, s21], P[:, s21], sigma / 12.0)
        enr, n_near, prec, ceil = enrichment_top20(Yte, _feasibility_score(P))
        c1 = (not math.isnan(rhos[s21]) and rhos[s21] >= 0.5
              and not math.isnan(enr) and enr >= 2.0)
        print(f"{name:<9} {rhos[0]:>8.3f} {rhos[1]:>8.3f} {rhos[2]:>8.3f} "
              f"{nf.get(name, float('nan')):>8.3f} "
              f"{racc:>8.3f} {prec:>8.3f} {enr:>7.2f} {'YES' if c1 else 'no':>5}")
    print(f"  near-feasible test rows (all margins > {NEAR_FEASIBLE} scale unit): "
          f"{n_near}/{len(test)} = base rate {n_near / max(len(test), 1):.3f} "
          f"-> **enrichment ceiling {ceil:.2f}x** (a perfect ranker scores this). "
          f"NF-labeled test rows: {nf.get('_n', 0)}/{len(test)} "
          "(series-Rs only; C1 gates S21+enrichment, NF is the added head).")
    _per_spec(test, Yte, preds, s21)


def _per_spec(test, Yte, preds, s21, min_n=10):
    """rho(S21) WITHIN each spec.

    Mandatory now that the test pool is multi-spec: a model that only learned
    "dhruva rows have worse gain margins than wifi24 rows" scores a high pooled
    Spearman with zero ability to rank two candidates *for the same spec* -- which
    is the only thing search ever asks it. The pooled number is an upper bound;
    these are the numbers 03-SEARCH can actually spend."""
    specs = sorted({d["spec"] for d in test})
    groups = [(sp, [i for i, d in enumerate(test) if d["spec"] == sp])
              for sp in specs]
    groups = [(sp, ix) for sp, ix in groups if len(ix) >= min_n]
    if len(groups) < 1:
        return
    print("  within-spec rho(S21) (pooled rho is an upper bound -- it can be "
          "earned by telling the specs apart):")
    for sp, ix in groups:
        cells = "  ".join(f"{n}={spearman(Yte[ix, s21], P[ix, s21]):.3f}"
                          for n, P in preds.items() if n != "trivial")
        print(f"    {sp:<14} n={len(ix):>4}  {cells}")


def _nf_arm(train, test, vocab, Xtr, Xte):
    """NF-margin head (02-CRITIC 'NF when the harness fix lands'). Same features,
    same arms; scored only on rows that carry a series-Rs NF."""
    tr = [(i, d) for i, d in enumerate(train) if d.get("y_nf") is not None]
    te = [(i, d) for i, d in enumerate(test) if d.get("y_nf") is not None]
    out = {"_n": len(te)}
    if len(tr) < 10 or len(te) < 3:
        return out
    itr = [i for i, _ in tr]
    ytr = np.array([[d["y_nf"]] for _, d in tr])
    yte = np.array([d["y_nf"] for _, d in te])
    out["trivial"] = spearman(yte, np.full(len(te), ytr.mean()))
    out["wl_knn"] = spearman(yte, pred_knn([d for _, d in tr],
                                           [d for _, d in te], key="y_nf"))
    out["ridge"] = spearman(yte, pred_ridge(fit_ridge(Xtr[itr], ytr),
                                            Xte[[i for i, _ in te]])[:, 0])
    return out


def _source_shift(data):
    """Train on corpus + references + templates, test on generated topologies
    (03-SEARCH's shift). See `is_generated` -- the generated side is every arm a
    sampler produced, not just `campaign-G`."""
    return ([d for d in data if not d["gen"]], [d for d in data if d["gen"]])


def run_eval(snapshot=None, sigma_recipe=None):
    data = load_dataset(snapshot=snapshot)
    sigma = _sigma_s21(recipe=sigma_recipe, snapshot=snapshot)
    from collections import Counter
    print(f"critic baselines -- {len(data)} token-bearing L2 rows "
          f"(feasible in set: {sum((d['y'] > 0).all() for d in data)}; "
          f"generated {sum(d['gen'] for d in data)}; "
          f"NF-labeled {sum(d.get('y_nf') is not None for d in data)})")
    print("  specs: " + ", ".join(f"{k}={v}" for k, v in
                                  sorted(Counter(d["spec"] for d in data).items())))
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
        evaluate(tr2, te2, "source-shift (corpus+ref+templates -> generated)", sigma)
    else:
        print(f"\n  source-shift split too small (train {len(tr2)}/test {len(te2)})")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eval", action="store_true", help="run the baseline report")
    ap.add_argument("--snapshot", help="pin the training/eval set to a snapshot")
    ap.add_argument("--sigma-recipe", help="label domain for the sigma ceiling "
                                           "(e.g. candidate-v1+bo3)")
    args = ap.parse_args()
    if args.eval:
        return run_eval(snapshot=args.snapshot, sigma_recipe=args.sigma_recipe)
    ap.error("give --eval")


if __name__ == "__main__":
    sys.exit(main())
