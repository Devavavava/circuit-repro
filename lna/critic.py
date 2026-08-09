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

# ----------------------------------------------------- Gate C1, as restated
# 02-CRITIC §4 froze C1 as "enrichment@top-20% >= 2x AND rho(S21) >= 0.5". The
# Spearman half is untouched. The enrichment half was NOT base-rate-robust and
# had become unreachable; it is restated below (user decision, 2026-08-09).
#
# Why the old bar broke. With k = k_frac*n selected and n_near = base*n truly
# near-feasible, at most min(n_near, k) of the selection can be near-feasible, so
#     ceiling precision  = min(n_near, k)/k = min(base/k_frac, 1)
#     ceiling enrichment = ceiling precision / base = min(1/k_frac, 1/base)
# At k_frac = 0.2 that ceiling is 5x for base <= 0.2 but collapses to 1/base
# above it: the pool improved from base 0.27 to 0.46 and the ceiling fell
# 3.74x -> 2.20x, so "enrichment >= 2x" silently became "precision@20% >= 0.91",
# and at base >= 0.5 it becomes literally unsatisfiable. The gate got harder
# because the *candidates* got better -- backwards.
#
# Why not gate on raw precision@20%, or on the raw fraction of ceiling. Random
# selection scores precision = base and fraction-of-ceiling = base/ceiling_prec,
# both of which move with the base rate; a fixed threshold on either is passed or
# failed by a coin flip depending only on how good the pool is.
#
# The restatement: score the ranker on the fraction of the *attainable* range it
# actually captures, measured from random rather than from zero --
#
#     C1_skill = (precision@20% - base) / (ceiling_precision - base)
#
# which is 0 for random selection and 1 for a perfect ranker AT ANY BASE RATE,
# and is undefined (reported, never silently passed) when ceiling == base, i.e.
# when the split admits no discrimination at all.
#
# Calibrating theta. In the regime where the frozen bar was well-posed
# (base <= k_frac, so ceiling_precision = base/k_frac), "enrichment >= 2x" means
# precision >= 2*base, and
#     skill = (2b - b) / (b/0.2 - b) = 1/4   exactly, for every such b.
# So theta = 0.25 is the unique constant that reproduces the frozen gate's
# meaning wherever the frozen gate had one, and removes the silent tightening
# above it. (For 0.2 < base < 0.5 the old bar's implied skill climbs 0.25 -> 1.0;
# that climb is the defect, not the intent.) Historical check: the v2-train
# family-split pass -- WL-kNN precision@20% = 1.000 at base 0.485, i.e. a
# *perfect* top-20% -- scores skill 1.000 and still passes, as required.
C1_RHO = 0.5                  # Spearman half of C1 -- UNCHANGED
C1_THETA = 0.25               # restated enrichment half: skill >= 0.25
C1_KFRAC = 0.20               # selected fraction ("top-20%")
C1_ENRICH_LEGACY = 2.0        # the retired bar, still reported for continuity


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


def c1_stats(y_true_margins, score, k_frac=C1_KFRAC):
    """Everything Gate C1 needs, old bar and new, from one selection.

    y_true_margins: (n,3) array; near-feasible = all margins > NEAR_FEASIBLE.

    Returns a dict:
      base          base rate of near-feasible rows (what random selection scores)
      k             rows actually selected (the top k_frac by `score`)
      prec          precision@k -- the model's raw hit rate
      ceil_prec     min(n_near, k)/k -- the best precision ANY ranker can reach
      enrich        prec/base, the retired C1 metric (reported for continuity)
      ceil_enrich   ceil_prec/base = min(1/k_frac, 1/base), its ceiling
      frac_ceiling  prec/ceil_prec -- "fraction of ceiling", NOT base-rate-robust
                    (random scores base/ceil_prec, which moves with the pool)
      skill         (prec - base)/(ceil_prec - base) -- the restated criterion:
                    0 for random, 1 for perfect, at any base rate. NaN when
                    ceil_prec == base (no discrimination possible on this split).
    `ceil_prec` uses the ACTUAL k rather than k_frac*n, so it stays exact when
    rounding makes the selected fraction differ from the nominal 20%."""
    near = (y_true_margins > NEAR_FEASIBLE).all(1)
    n, n_near = len(near), int(near.sum())
    base = float(near.mean()) if n else float("nan")
    k = max(1, int(round(k_frac * n)))
    out = {"n": n, "n_near": n_near, "base": base, "k": k,
           "prec": float("nan"), "ceil_prec": float("nan"),
           "enrich": float("nan"), "ceil_enrich": float("nan"),
           "frac_ceiling": float("nan"), "skill": float("nan")}
    if n == 0 or n_near == 0:
        return out
    ceil_prec = min(n_near, k) / k
    # No ranking signal (e.g. the trivial arm predicts a constant) == random.
    prec = base if np.std(score) < 1e-9 else float(near[np.argsort(-score)[:k]].mean())
    out.update(prec=prec, ceil_prec=ceil_prec, enrich=prec / base,
               ceil_enrich=ceil_prec / base,
               frac_ceiling=prec / ceil_prec if ceil_prec > 0 else float("nan"))
    denom = ceil_prec - base
    # denom == 0 means every ranker ties: the split cannot separate anything.
    out["skill"] = (prec - base) / denom if denom > 1e-12 else float("nan")
    return out


def c1_pass(rho_s21, skill, theta=C1_THETA, rho_bar=C1_RHO):
    """Gate C1 as restated (2026-08-09): Spearman half unchanged, enrichment half
    replaced by the base-rate-robust selection skill. Returns 'YES' / 'no' /
    'n/a' -- 'n/a' when the split admits no discrimination, which is a
    measurement problem to fix, not a pass and not a failure."""
    if math.isnan(skill):
        return "n/a"
    if math.isnan(rho_s21):
        return "no"
    return "YES" if (rho_s21 >= rho_bar and skill >= theta) else "no"


def enrichment_top20(y_true_margins, score):
    """Backward-compatible view of `c1_stats` -- (enrichment, n_near,
    precision@20%, enrichment ceiling). Kept so `critic_gnn.py`'s existing
    unpacking keeps working; new code should call `c1_stats`.

    ⚠ Enrichment is the RETIRED half of Gate C1. It is precision@20%/base-rate
    and is capped at min(1/k_frac, 1/base-rate), so it gets harder to score as
    the candidate pool improves -- see the C1 block at the top of this module."""
    s = c1_stats(y_true_margins, score)
    if s["n_near"] == 0:
        return float("nan"), 0, float("nan"), float("nan")
    return s["enrich"], s["n_near"], s["prec"], s["ceil_enrich"]


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
          f"{'rho_NF':>8} {'rankacc':>8} {'prec@20':>8} "
          f"{'enrich':>7} {'ofceil':>7} {'skill':>7} {'C1?':>5}")
    st = None
    for name, P in preds.items():
        rhos = [spearman(Yte[:, k], P[:, k]) for k in range(3)]
        racc = pairwise_rank_acc(Yte[:, s21], P[:, s21], sigma / 12.0)
        st = c1_stats(Yte, _feasibility_score(P))
        print(f"{name:<9} {rhos[0]:>8.3f} {rhos[1]:>8.3f} {rhos[2]:>8.3f} "
              f"{nf.get(name, float('nan')):>8.3f} "
              f"{racc:>8.3f} {st['prec']:>8.3f} {st['enrich']:>7.2f} "
              f"{st['frac_ceiling']:>7.3f} {st['skill']:>7.3f} "
              f"{c1_pass(rhos[s21], st['skill']):>5}")
    if st:
        print(f"  near-feasible test rows (all margins > {NEAR_FEASIBLE} scale "
              f"unit): {st['n_near']}/{st['n']} = base rate {st['base']:.3f}; "
              f"top-20% selects k={st['k']} -> ceiling precision "
              f"{st['ceil_prec']:.3f} (= retired enrichment ceiling "
              f"{st['ceil_enrich']:.2f}x). A perfect ranker scores skill 1.000, "
              f"random scores 0.000.")
        print(f"  Gate C1 (restated 2026-08-09) = rho(S21) >= {C1_RHO} AND "
              f"skill >= {C1_THETA}, skill = (prec@20% - base)/(ceiling prec - "
              f"base). At this base rate that is prec@20% >= "
              f"{st['base'] + C1_THETA * (st['ceil_prec'] - st['base']):.3f}; "
              f"the retired bar (enrichment >= {C1_ENRICH_LEGACY:.0f}x) would "
              f"have demanded prec@20% >= "
              f"{min(C1_ENRICH_LEGACY * st['base'], 1.0):.3f}"
              f"{' -- UNREACHABLE' if C1_ENRICH_LEGACY * st['base'] > st['ceil_prec'] + 1e-12 else ''}."
              f" NF-labeled test rows: {nf.get('_n', 0)}/{len(test)} "
              "(NF is an added head, not gated by C1).")
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
