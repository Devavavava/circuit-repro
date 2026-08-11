"""WP-SURROGATE v0 -- a POINT-level ngspice surrogate (plans2/12-WP-SURROGATE.md).

The critic (Block 7) predicts one margin vector per *(topology, spec)* -- "is this
topology worth a sizing run?". This module answers the strictly inner question:

    f(topology graph, parameter vector x) -> metric vector

i.e. "what would ngspice say about THIS point of THIS device box?" -- one
prediction per ngspice call. It is trained on `data/sim_points.jsonl`, the free
byproduct of every ZOAF sizing run (`size._log_l2` -> `ds.row_point`), which had
never been used for learning.

The point of it is not a better ranker; it is a **pre-gate inside the sizing
loop**: ZOAF spends 150-250 ngspice calls per topology, and a call it can be
talked out of is a SPICE-minute saved. `--gate` measures exactly that, offline,
against runs that already happened, with zero new simulation.

    python  lna/surrogate.py --build-cache          # py3.14 default env (needs size.py)
    python  lna/surrogate.py --validate-join -n 8   # + ngspice replay fence
    <torch>  lna/surrogate.py --train --arm node    # analoggenie CPU or WSL GPU
    <torch>  lna/surrogate.py --eval --arm node
    <torch>  lna/surrogate.py --gate --arm node

ERA CAVEAT -- READ BEFORE USING ANY NUMBER FROM THIS MODEL. `sim_points.jsonl`
was last appended 2026-08-07, so every row predates three harness cutovers:
multi-finger emission (`mf2-v1`, 2026-08-10, FINDINGS 27), the series-Rs noise
figure (`nfrs-v1`, 2026-08-08, FINDINGS 13) and the stability harness. The
`nf_db` column is therefore the RETIRED port-referred NF (finding #7), not the
golden-validated one -- it is learned here as a fourth response surface and must
never be pooled with, or substituted for, a `series_rs` NF. All 66,664 rows are
`wifi24`, recipe `candidate-v1`/`curated-v1`, `nf_gated=false`, single-finger.
v0 is a proof of mechanism; a production surrogate needs post-cutover points.
"""
import argparse
import io
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds          # noqa: E402
from topology import Topology, base_of   # noqa: E402
from spec import Spec           # noqa: E402

SPEC_NAME = "wifi24"
INDUCTOR_Q = 12
W_FINGER = None                 # historical single-finger emission (the era)

# device classes the graph encoder knows (must match critic_gnn.DEV_TYPES)
DEV_TYPES = ["NM", "PM", "R", "C", "L"]

METRICS = ("s11_db", "s11_max_db", "s21_db", "s21_min_db",
           "s21_ripple_db", "idd_ma", "nf_db")
# robust clips, pre-registered in plans2/12 section 2.2 (chosen from the training
# histogram, never from a result). idd is log10'd first.
CLIP = {"s11_db": (-45.0, 25.0), "s11_max_db": (-45.0, 25.0),
        "s21_db": (-60.0, 40.0), "s21_min_db": (-60.0, 40.0),
        "s21_ripple_db": (0.0, 15.0), "idd_ma": (-6.0, 3.5),
        "nf_db": (-25.0, 60.0)}
LOG10_METRICS = ("idd_ma",)

# --- the era pin -------------------------------------------------------------
# sim_points.jsonl is append-only and LIVE: a concurrent work package is writing
# post-cutover points into it right now. v0 is defined on the pre-cutover prefix
# ONLY, pinned the way datastore.snapshot pins a training set -- by line count +
# sha256 -- and cross-checked against the recipe/date of each block's L2 row, so
# a multi-finger or series-Rs row cannot leak in even if the line count is raised.
ERA_LINES = 66664                # rows present at 2026-08-07T21:42, the last
                                 # append before the nfrs-v1 / mf2-v1 cutovers
ERA_RECIPES = ("candidate-v1", "curated-v1", "tapped-v1", "cg-v1")
ERA_BEFORE_TS = "2026-08-08"     # nfrs-v1 (series-Rs NF) landed on this date

# Derived artefacts live under lna/out/_surrogate/ -- `lna/out/_*` is gitignored,
# and a cache built from a gitignored table (sim_points.jsonl) must not be
# committed as if it were data. The era pin (sha256 + line count) is what makes
# it reproducible; that goes in FINDINGS, not in git-lfs.
CACHE_DIR = os.path.join(HERE, "out", "_surrogate")
CACHE_NPZ = os.path.join(CACHE_DIR, "cache_v0.npz")
CACHE_META = os.path.join(CACHE_DIR, "cache_v0.meta.json")
CKPT_DIR = os.path.join(CACHE_DIR, "ckpt")


def era_spec(name=SPEC_NAME):
    """The spec exactly as the sizing runs in this table saw it: NF ungated.

    Reproduces `size._spec_for_sizing(name, nf_gate=False)` without importing
    size.py (which pulls ZOAF/ngspice), so the training and gate paths stay
    torch-env-portable."""
    s = Spec.load(name)
    if "nf_db" in s.constraints:
        s.constraints["nf_db"]["status"] = "unsupported"
    return s


def to_model(name, v):
    """Stored metric -> model target space (log10 for currents, then clip)."""
    if v is None:
        return None
    v = float(v)
    if name in LOG10_METRICS:
        v = math.log10(max(v, 1e-6))
    lo, hi = CLIP[name]
    return min(max(v, lo), hi)


def from_model(name, v):
    """Model target space -> stored metric units."""
    return 10.0 ** float(v) if name in LOG10_METRICS else float(v)


# ============================================================== STEP 1: the join
def _point_blocks(path=None, max_lines=None):
    """Segment `sim_points.jsonl` into ZOAF runs.

    `size._log_l2` appends a run's point rows in one contiguous `ds.append_all`
    burst, so a maximal run of equal `wl_hash` in file order IS one sizing run.
    Returns [(start_line, wl_hash, n_rows)] and the parsed rows."""
    import hashlib
    path = path or os.path.join(HERE, "data", "sim_points.jsonl")
    with io.open(path, "r", encoding="utf-8") as fh:
        raw = fh.readlines()
    n_file = len(raw)
    if max_lines is not None:
        raw = raw[:max_lines]
    digest = hashlib.sha256("".join(raw).encode("utf-8")).hexdigest()
    rows = [json.loads(ln) for ln in raw if ln.strip()]
    blocks, cur, n, start = [], "\0", 0, 0
    for i, r in enumerate(rows):
        h = r.get("wl_hash")
        if h != cur:
            if n:
                blocks.append((start, cur, n))
            cur, n, start = h, 0, i
        n += 1
    if n:
        blocks.append((start, cur, n))
    return blocks, rows, {"lines_used": len(raw), "lines_in_file": n_file,
                          "sha256": digest}


def _l2_by_hash():
    by = {}
    for r in ds.load("topo_labels"):
        by.setdefault(r.get("wl_hash"), []).append(r)
    return by


def _param_map(topo, best_x, best_params, S):
    """(sizable, fixed, bias_nets, deck_body) for one run, via size.py's machinery.

    `size.classify_params` gives the free-parameter ORDER (sorted devices, then
    the inserted `pVBG*`), which is exactly the order `make_objective` zipped x
    against. A `curated-v1` run had its input-match passives moved to *fixed* by
    `size._curate`; `size.match_devices` names them and their frozen values come
    back out of the row's own `best_params`. Returns None if the topology cannot
    be biased."""
    import bias
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, inductor_q=INDUCTOR_Q,
                                     w_finger=W_FINGER)
    if rep.get("skipped") or not nl.two_port:
        return None
    sizable, fixed = S.classify_params(nl)
    if len(sizable) != len(best_x):          # curated-v1: match passives frozen
        mdevs, _dev = S.match_devices(topo)
        drop = set("p%sV" % d for d in mdevs) & set(sizable)
        for k in drop:
            fixed[k] = (best_params or {}).get(k)
        sizable = dict((k, v) for k, v in sizable.items() if k not in drop)
    import extract as E
    return sizable, fixed, (rep.get("bias_nets") or {}), E.body_of(nl.emit())


def _decode(x, sizable, fixed, ranges):
    """size.make_objective's `decode`, re-expressed (size.py owns the ranges)."""
    params = dict(fixed)
    for xi, name in zip(x, list(sizable)):
        lo, hi, islog = ranges[sizable[name]]
        xi = float(min(max(xi, 0.0), 1.0))
        v = (10 ** (math.log10(lo) + xi * (math.log10(hi) - math.log10(lo)))
             if islog else lo + xi * (hi - lo))
        params[name] = "%.6g" % v
    return params


def _coord(value, kind, ranges):
    """Inverse of the decode map: device value -> normalized [0,1] coordinate.

    Needed for parameters a run held FIXED (a curated run's Lg/Ls/Cin/Cex), so the
    model sees the circuit as it was simulated, not as the optimizer varied it."""
    lo, hi, islog = ranges[kind]
    v = float(value)
    if islog:
        return (math.log10(max(v, 1e-30)) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
    return (v - lo) / (hi - lo)


def _dev_param(d):
    """(param name, kind_range_key) for a device's one sizable value."""
    b = base_of(d)
    if b in ("NM", "PM"):
        return "p%sW" % d, "W"
    return "p%sV" % d, b


def build_cache(verbose=True):
    """Join sim_points -> (topology, named params, metrics) and cache it.

    Every block is accepted ONLY if the reconstructed parameter map decodes the
    L2 row's stored `best_x` into its stored `best_params` string for string.
    That is the fence: a silently mis-ordered map cannot survive it."""
    import size as S                       # py3.14 analysis env only
    spec = era_spec()
    ranges = S.kind_ranges(spec)
    blocks, rows, pin = _point_blocks(max_lines=ERA_LINES)
    byh = _l2_by_hash()
    print("[join] era pin: %d of %d lines, sha256 %s"
          % (pin["lines_used"], pin["lines_in_file"], pin["sha256"][:16]))

    topos, topo_ix, runs, prep_cache = [], {}, [], {}
    row_run, row_topo, row_ord, xs, devcoord, vbgcoord = [], [], [], [], [], []
    Y, skipped = [], {}
    for (start, h, n) in blocks:
        cands = [r for r in byh.get(h, [])
                 if r.get("spec") == SPEC_NAME and r.get("n_evals") == n]
        if not cands:
            skipped["no_l2_row"] = skipped.get("no_l2_row", 0) + n
            continue
        l2 = cands[0]
        cfg = l2.get("zoaf_cfg") or {}
        if (cfg.get("recipe") not in ERA_RECIPES or cfg.get("nf_gated")
                or (l2.get("ts") or "") >= ERA_BEFORE_TS):
            skipped["out_of_era"] = skipped.get("out_of_era", 0) + n
            continue
        toks = (l2.get("graph") or {}).get("tokens")
        bx, bp = l2.get("best_x"), l2.get("best_params")
        if not toks or not bx or not bp:
            skipped["no_tokens_or_bestx"] = skipped.get("no_tokens_or_bestx", 0) + n
            continue
        key = (h, len(bx))
        if key not in prep_cache:
            topo = Topology(toks)
            pm = _param_map(topo, bx, bp, S)
            prep_cache[key] = (topo, pm)
        topo, pm = prep_cache[key]
        if pm is None:
            skipped["bias_skipped"] = skipped.get("bias_skipped", 0) + n
            continue
        sizable, fixed, bias_nets, _body = pm
        if len(sizable) != len(bx) or _decode(bx, sizable, fixed, ranges) != bp:
            skipped["param_map_unproven"] = skipped.get("param_map_unproven", 0) + n
            continue
        # --- topology record (device order == critic_gnn.graph_tensors order)
        if h not in topo_ix:
            devs = sorted(d for d in topo.devices if base_of(d) in DEV_TYPES)
            topo_ix[h] = len(topos)
            topos.append({"wl_hash": h, "tokens": toks, "devs": devs,
                          "n_devices": len(devs)})
        ti = topo_ix[h]
        devs = topos[ti]["devs"]
        dpos = dict((d, i) for i, d in enumerate(devs))
        # which x slot / fixed value feeds each device, and each device's bias net
        dev_src = []                       # (dev_index, x_slot | None, kind, fixed_val)
        names = list(sizable)
        for d in devs:
            pname, kind = _dev_param(d)
            if pname in names:
                dev_src.append((dpos[d], names.index(pname), kind, None))
            elif pname in fixed and fixed[pname] is not None:
                dev_src.append((dpos[d], None, kind, _coord(fixed[pname], kind, ranges)))
        vbg_src = []                       # (dev_index, x_slot)
        for _vbnet, info in bias_nets.items():
            p = info.get("param")
            if p not in names:
                continue
            for d in info.get("devices", ()):
                if d in dpos:
                    vbg_src.append((dpos[d], names.index(p)))
        ri = len(runs)
        runs.append({"topo": ti, "wl_hash": h, "start_line": start, "n": n,
                     "recipe": (l2.get("zoaf_cfg") or {}).get("recipe"),
                     "n_params": len(names), "param_names": names,
                     "source_arm": (l2.get("provenance") or {}).get("source_arm")})
        for j in range(n):
            r = rows[start + j]
            x = [float(v) for v in r["x"]]
            dc = [0.0] * len(devs)
            dm = [0.0] * len(devs)
            vb = [0.0] * len(devs)
            vm = [0.0] * len(devs)
            for (di, slot, kind, fv) in dev_src:
                dc[di] = min(max(x[slot] if slot is not None else fv, 0.0), 1.0)
                dm[di] = 1.0
            for (di, slot) in vbg_src:
                vb[di] = min(max(x[slot], 0.0), 1.0)
                vm[di] = 1.0
            row_run.append(ri)
            row_topo.append(ti)
            row_ord.append(j)
            xs.append(x)
            devcoord.append((dc, dm))
            vbgcoord.append((vb, vm))
            m = r.get("metrics") or {}
            Y.append([to_model(k, m.get(k)) for k in METRICS])
    return _pack_cache(topos, runs, row_run, row_topo, row_ord, xs, devcoord,
                       vbgcoord, Y, skipped, len(rows), verbose, pin)


def _pack_cache(topos, runs, row_run, row_topo, row_ord, xs, devcoord, vbgcoord,
                Y, skipped, n_total, verbose, pin):
    """Pad, split by FAMILY (never by row), write the npz + meta sidecar."""
    maxD = max(t["n_devices"] for t in topos)
    maxP = max(len(x) for x in xs)
    N = len(xs)
    A = np.zeros
    dc, dm = A((N, maxD), np.float32), A((N, maxD), np.float32)
    vb, vm = A((N, maxD), np.float32), A((N, maxD), np.float32)
    px, pm = A((N, maxP), np.float32), A((N, maxP), np.float32)
    for i in range(N):
        d, mask = devcoord[i]
        v, vmask = vbgcoord[i]
        k = len(d)
        dc[i, :k], dm[i, :k], vb[i, :k], vm[i, :k] = d, mask, v, vmask
        px[i, :len(xs[i])] = xs[i]
        pm[i, :len(xs[i])] = 1.0
    Ya = np.array([[np.nan if v is None else v for v in row] for row in Y], np.float32)

    # family split: whole WL-similarity families to train/val/test (Block 6).
    pseudo = [{"wl_hash": t["wl_hash"], "graph": {"tokens": t["tokens"]}} for t in topos]
    sp = ds.family_split(k_holdout=0.3, rows=pseudo)
    where = {}
    for name in ("train", "val", "test"):
        for r in sp[name]:
            where[r["wl_hash"]] = name
    split_of_topo = np.array([{"train": 0, "val": 1, "test": 2}[where[t["wl_hash"]]]
                              for t in topos], np.int8)
    n_fams = len(sp.get("families") or [])

    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    np.savez_compressed(CACHE_NPZ, dev_c=dc, dev_m=dm, vbg_c=vb, vbg_m=vm,
                        pad_x=px, pad_m=pm, Y=Ya,
                        row_run=np.array(row_run, np.int32),
                        row_topo=np.array(row_topo, np.int32),
                        row_ord=np.array(row_ord, np.int32),
                        split_of_topo=split_of_topo)
    meta = {"spec": SPEC_NAME, "metrics": list(METRICS), "clip": CLIP,
            "log10_metrics": list(LOG10_METRICS), "max_devices": int(maxD),
            "max_params": int(maxP), "n_rows": N, "n_runs": len(runs),
            "n_topologies": len(topos), "n_families": n_fams,
            "n_rows_in_file": n_total, "skipped_rows": skipped, "era_pin": pin,
            "inductor_q": INDUCTOR_Q, "w_finger": W_FINGER,
            "era": "pre-mf2-v1 (single finger), pre-nfrs-v1 (nf_db = RETIRED port NF), "
                   "pre-stability; recipes candidate-v1/curated-v1, nf_gated=false",
            "topos": topos, "runs": runs}
    with io.open(CACHE_META, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, indent=1, sort_keys=True)
    if verbose:
        cov = 100.0 * N / max(n_total, 1)
        print("[join] sim_points rows            : %d" % n_total)
        print("[join] joined (topology resolved) : %d  (%.2f%% coverage)" % (N, cov))
        for k in sorted(skipped):
            print("[join]   dropped %-22s: %d rows" % (k, skipped[k]))
        print("[join] runs %d   topologies %d   families %d   maxD %d   maxP %d"
              % (len(runs), len(topos), n_fams, maxD, maxP))
        tr = int((split_of_topo == 0).sum())
        va = int((split_of_topo == 1).sum())
        te = int((split_of_topo == 2).sum())
        print("[join] family split topologies: train %d / val %d / test %d" % (tr, va, te))
        print("[join] wrote %s + %s" % (os.path.basename(CACHE_NPZ),
                                        os.path.basename(CACHE_META)))
    return meta


def load_cache():
    if not os.path.exists(CACHE_NPZ):
        raise SystemExit("no cache -- run:  python lna/surrogate.py --build-cache")
    with io.open(CACHE_META, "r", encoding="utf-8") as fh:
        meta = json.load(fh)
    return dict(np.load(CACHE_NPZ)), meta


# ------------------------------------------------ the replay fence (needs ngspice)
def validate_join(n=8, seed=7, w_finger_both=True):
    """Replay joined rows through ngspice and compare to the STORED metrics.

    This is the fence the whole WP stands on. A point row is (x, metrics) with no
    provenance of its own; if the block segmentation, the L2 attachment or the
    parameter ordering were wrong, the replay would disagree. Rows are drawn from
    the INTERIOR of their runs (not the argmin, which the L2 row already pins).

    Also replays each row through today's DEFAULT multi-finger deck, to show the
    size of the era gap the cache is deliberately not crossing."""
    import random
    import size as S
    import extract as E
    spec = era_spec()
    ranges = S.kind_ranges(spec)
    blocks, rows, pin = _point_blocks(max_lines=ERA_LINES)
    byh = _l2_by_hash()
    pool = []
    for (start, h, k) in blocks:
        c = [r for r in byh.get(h, [])
             if r.get("spec") == SPEC_NAME and r.get("n_evals") == k]
        if c and (c[0].get("graph") or {}).get("tokens") and c[0].get("best_x"):
            pool.append((start, h, k, c[0]))
    rnd = random.Random(seed)
    sample = rnd.sample(pool, min(n, len(pool)))
    keys = ("s11_db", "s11_max_db", "s21_db", "s21_min_db", "s21_ripple_db", "idd_ma")
    worst_hist, worst_mf, fails = 0.0, 0.0, 0
    print("[fence] replaying %d joined rows (interior points, not the argmin)" % len(sample))
    for (start, h, k, l2) in sample:
        topo = Topology(l2["graph"]["tokens"])
        j = start + rnd.randrange(k)
        pr = rows[j]
        for era, tag in ((True, "single-finger (the era)"),
                         (False, "multi-finger (today)")):
            import bias
            kw = {"inductor_q": INDUCTOR_Q}
            if era:                       # else: to_spice's own default (mf2-v1)
                kw["w_finger"] = W_FINGER
            nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
            if rep.get("skipped") or not nl.two_port:
                print("  %s  %-26s BIAS SKIPPED" % (h[:8], tag))
                continue
            sizable, fixed = S.classify_params(nl)
            if len(sizable) != len(l2["best_x"]):
                mdevs, _d = S.match_devices(topo)
                drop = set("p%sV" % d for d in mdevs) & set(sizable)
                for kk in drop:
                    fixed[kk] = l2["best_params"].get(kk)
                sizable = dict((a, b) for a, b in sizable.items() if a not in drop)
            m = E.run_and_extract(E.body_of(nl.emit()),
                                  _decode(pr["x"], sizable, fixed, ranges), spec)
            if m is None:
                print("  %s  %-26s SIM FAILED" % (h[:8], tag))
                fails += 1
                continue
            d = {}
            for kk in keys:
                a, b = m.get(kk), (pr["metrics"] or {}).get(kk)
                d[kk] = abs(a - b) if (a is not None and b is not None) else float("nan")
            worst = max(v for v in d.values() if v == v)
            if tag.startswith("single"):
                worst_hist = max(worst_hist, worst)
            else:
                worst_mf = max(worst_mf, worst)
            print("  %s pt%4d/%-4d %-26s max|delta| %8.4f   (S21 %+.4f  S11 %+.4f  Idd %+.4f)"
                  % (h[:8], j - start, k, tag, worst,
                     d["s21_db"], d["s11_db"], d["idd_ma"]))
    print("[fence] worst |delta| over ALL metrics, single-finger replay: %.6f" % worst_hist)
    print("[fence] worst |delta| over ALL metrics, multi-finger replay : %.6f" % worst_mf)
    print("[fence] VERDICT: %s" % ("PASS -- the join is bit-exact"
                                   if (worst_hist < 1e-6 and not fails)
                                   else "FAIL -- do not train on this join"))
    return worst_hist


# ============================================================ STEP 2: the model
def _graph_bank(meta):
    """Per-topology graph tensors, built ONCE (only ~310 distinct graphs exist).

    Uses `critic_gnn.graph_tensors` unchanged, so the encoder sees exactly the
    representation the critic sees. The device ORDER it produces is asserted
    against the cache's, because the parameter injection is positional."""
    import critic_gnn as CG
    assert CG.DEV_TYPES == DEV_TYPES, "critic_gnn device vocabulary changed"
    tens = []
    for t in meta["topos"]:
        topo = Topology(t["tokens"])
        df, nf, ra = CG.graph_tensors(topo)
        devs = sorted(d for d in topo.devices if base_of(d) in DEV_TYPES)
        assert devs == t["devs"], "device order drift for %s" % t["wl_hash"]
        tens.append((df, nf, ra))
    T = len(tens)
    maxD = max(x[0].shape[0] for x in tens)
    maxN = max(x[1].shape[0] for x in tens)
    dev = np.zeros((T, maxD, len(DEV_TYPES)), np.float32)
    net = np.zeros((T, maxN, 5), np.float32)
    adj = np.zeros((T, len(CG.ROLES), maxD, maxN), np.float32)
    dmask = np.zeros((T, maxD), np.float32)
    for k, (df, nf, ra) in enumerate(tens):
        nD, nN = df.shape[0], nf.shape[0]
        dev[k, :nD] = df
        net[k, :nN] = nf
        adj[k, :, :nD, :nN] = ra
        dmask[k, :nD] = 1.0
    return dev, net, adj, dmask


def make_model(arm, h, max_params, n_out):
    """The surrogate head on the critic's trunk.

    `critic_gnn.MPNN` supplies the bipartite device<->net trunk verbatim
    (`net_in`, `dev_msg`, `net_msg`, `dev_upd`, `net_upd`); only the INPUT
    embedding and the READOUT differ, which is exactly the difference between
    "score a topology" and "score a point in a topology's device box"."""
    import torch
    import torch.nn as nn
    import critic_gnn as CG

    class PointSurrogate(CG.MPNN):
        def __init__(self):
            n_glob = 2 * max_params if arm == "concat" else 0
            CG.MPNN.__init__(self, h=h, rounds=3, n_spec=n_glob, n_out=n_out)
            self.arm = arm
            din = len(DEV_TYPES) + (0 if arm == "concat" else 4)
            self.dev_in = nn.Linear(din, h)
            if arm == "film":
                # FiLM: a pooled parameter summary modulates every message round
                self.film = nn.ModuleList([nn.Linear(13, 2 * h) for _ in range(3)])

        def forward(self, dev, net, adj, dmask, pfeat, pglob, psum):
            din = dev if self.arm == "concat" else torch.cat([dev, pfeat], -1)
            hd = torch.relu(self.dev_in(din))
            hn = torch.relu(self.net_in(net))
            R = adj.shape[1]
            for r_i in range(self.rounds):
                net_in = sum(adj[:, r].transpose(1, 2) @ self.dev_msg[r](hd)
                             for r in range(R))
                hn = torch.relu(hn + self.net_upd(net_in))
                dev_in = sum(adj[:, r] @ self.net_msg[r](hn) for r in range(R))
                hd = torch.relu(hd + self.dev_upd(dev_in))
                if self.arm == "film":
                    g = self.film[r_i](psum)
                    scale, shift = g[:, :h].unsqueeze(1), g[:, h:].unsqueeze(1)
                    hd = hd * (1.0 + scale) + shift
            m = dmask.unsqueeze(-1)
            s = (hd * m).sum(1)
            mx = (hd + (1 - m) * -1e9).max(1).values
            parts = [s, mx] + ([pglob] if self.arm == "concat" else [])
            return self.head(torch.cat(parts, -1))

    return PointSurrogate()


def _psum(c):
    """13-d pooled parameter summary (the FiLM / global conditioning input)."""
    dc, dm, vb, vm = c["dev_c"], c["dev_m"], c["vbg_c"], c["vbg_m"]
    nd = dm.sum(1, keepdims=True) + 1e-6
    nv = vm.sum(1, keepdims=True) + 1e-6
    mean_d = (dc * dm).sum(1, keepdims=True) / nd
    var_d = ((dc - mean_d) ** 2 * dm).sum(1, keepdims=True) / nd
    out = np.concatenate([
        mean_d, np.sqrt(var_d),
        (dc + (1 - dm) * -1e9).max(1, keepdims=True),
        (dc + (1 - dm) * 1e9).min(1, keepdims=True),
        (dc * dm).sum(1, keepdims=True) / dm.shape[1],
        (vb * vm).sum(1, keepdims=True) / nv,
        (vb + (1 - vm) * -1e9).max(1, keepdims=True),
        nd / dm.shape[1], nv / dm.shape[1],
        dm.mean(1, keepdims=True), vm.mean(1, keepdims=True),
        (dc * dm).std(1, keepdims=True), np.ones((dc.shape[0], 1), np.float32)],
        axis=1).astype(np.float32)
    return np.clip(np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0), -5, 5)


def splits(cache, meta, seed=0, holdout_frac=0.15, val_frac=0.05):
    """Row index sets for the three pre-registered strata (plans2/12 section 2.3).

    NEVER a row-level split of the whole store: the family split fixes which
    TOPOLOGIES a model may see, and only then are points of *seen* topologies
    subdivided. `point` = interpolation inside a box the model has explored;
    `run` = a whole unseen sizing run of a topology it has seen; `cross` = a
    family it has never seen."""
    rng = np.random.RandomState(seed)
    st = cache["split_of_topo"][cache["row_topo"]]
    runs_of_topo = {}
    for ri, r in enumerate(meta["runs"]):
        runs_of_topo.setdefault(r["topo"], []).append(ri)
    held_runs = set()
    for ti, rs in runs_of_topo.items():
        if cache["split_of_topo"][ti] == 0 and len(rs) > 1:
            held_runs.add(max(rs))              # the LAST run of a repeat-sized topo
    in_held = np.isin(cache["row_run"], sorted(held_runs))
    train_pool = (st == 0) & (~in_held)
    u = rng.rand(len(st))
    pt = u < holdout_frac                       # REPORTED interpolation stratum
    pv = (u >= holdout_frac) & (u < holdout_frac + val_frac)   # model selection only
    idx = {"train": np.where(train_pool & (~pt) & (~pv))[0],
           "point": np.where(train_pool & pt)[0],
           "point_val": np.where(train_pool & pv)[0],
           "run":   np.where((st == 0) & in_held)[0],
           "val":   np.where(st == 1)[0],
           "cross": np.where(st == 2)[0]}
    return idx, sorted(held_runs)


def _tensors(cache, meta, device):
    import torch
    bank = _graph_bank(meta)
    t = lambda a: torch.tensor(a, device=device)
    pglob = np.concatenate([cache["pad_x"], cache["pad_m"]], 1).astype(np.float32)
    return {"dev": t(bank[0]), "net": t(bank[1]), "adj": t(bank[2]),
            "dmask": t(bank[3]),
            "pfeat": t(np.stack([cache["dev_c"], cache["dev_m"],
                                 cache["vbg_c"], cache["vbg_m"]], -1)),
            "pglob": t(pglob), "psum": t(_psum(cache)),
            "topo": torch.tensor(cache["row_topo"].astype(np.int64), device=device),
            "Y": t(cache["Y"])}


def _forward(model, T, ix):
    ti = T["topo"][ix]
    return model(T["dev"][ti], T["net"][ti], T["adj"][ti], T["dmask"][ti],
                 T["pfeat"][ix], T["pglob"][ix], T["psum"][ix])


def train(arm="node", seed=0, epochs=60, batch=512, h=64, lr=3e-3, device="cpu",
          verbose=True):
    """Fit one surrogate. Huber on z-scored targets; early stop on the val FAMILIES."""
    import torch
    cache, meta = load_cache()
    idx, _ = splits(cache, meta)
    T = _tensors(cache, meta, device)
    torch.manual_seed(seed)
    np.random.seed(seed)
    tr = idx["train"]
    Ytr = cache["Y"][tr]
    mu = np.nanmean(Ytr, 0).astype(np.float32)
    sd = (np.nanstd(Ytr, 0) + 1e-6).astype(np.float32)
    mu_t = torch.tensor(mu, device=device)
    sd_t = torch.tensor(sd, device=device)
    model = make_model(arm, h, meta["max_params"], len(METRICS)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    tr_t = torch.tensor(tr.astype(np.int64), device=device)
    # Model selection uses BOTH regimes -- unseen families AND unseen points of
    # seen families -- because early-stopping on the cross-family loss alone
    # would deliberately under-fit the interpolation case this surrogate is
    # mostly deployed in. Neither reported stratum is used for selection.
    va_t = torch.tensor(idx["val"].astype(np.int64), device=device)
    pv_t = torch.tensor(idx["point_val"].astype(np.int64), device=device)

    def zloss(ix):
        pred = _forward(model, T, ix)
        y = (T["Y"][ix] - mu_t) / sd_t
        m = (~torch.isnan(y)).float()
        y = torch.nan_to_num(y)
        d = (pred - y).abs()
        l = torch.where(d < 1.0, 0.5 * d * d, d - 0.5) * m
        return l.sum() / m.sum().clamp(min=1.0)

    best, best_state, bad = 1e9, None, 0
    for ep in range(epochs):
        model.train()
        perm = tr_t[torch.randperm(len(tr_t), device=device)]
        tot = 0.0
        for b in range(0, len(perm), batch):
            opt.zero_grad()
            loss = zloss(perm[b:b + batch])
            loss.backward()
            opt.step()
            tot += float(loss.detach()) * min(batch, len(perm) - b)
        sched.step()
        model.eval()
        with torch.no_grad():
            vs = [float(zloss(va_t[b:b + 4096])) for b in range(0, len(va_t), 4096)]
            ps = [float(zloss(pv_t[b:b + 4096])) for b in range(0, len(pv_t), 4096)]
        v = 0.5 * float(np.mean(vs)) + 0.5 * float(np.mean(ps))
        if v < best - 1e-4:
            best, bad = v, 0
            best_state = dict((k, x.detach().clone()) for k, x in model.state_dict().items())
        else:
            bad += 1
        if verbose and (ep % 5 == 0 or ep == epochs - 1):
            print("  [%s s%d] ep %3d  train %.4f  sel %.4f  (fam %.4f  pt %.4f)  best %.4f"
                  % (arm, seed, ep, tot / max(len(perm), 1), v,
                     float(np.mean(vs)), float(np.mean(ps)), best))
        if bad >= 12:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    if not os.path.isdir(CKPT_DIR):
        os.makedirs(CKPT_DIR)
    path = os.path.join(CKPT_DIR, "%s_s%d.pt" % (arm, seed))
    torch.save({"state": model.state_dict(), "arm": arm, "h": h,
                "mu": [float(v) for v in mu], "sd": [float(v) for v in sd],
                "max_params": meta["max_params"], "val": best, "seed": seed}, path)
    if verbose:
        print("  [%s s%d] saved %s (val %.4f)" % (arm, seed, os.path.basename(path), best))
    return path, best


def _torch_load(path, device):
    """torch 2.6+ defaults `weights_only=True`, which rejects the numpy scalars
    older checkpoints carry; torch 2.0 has no such kwarg. Handle both."""
    import torch
    try:
        return torch.load(path, map_location=device)
    except Exception:
        return torch.load(path, map_location=device, weights_only=False)


def predict(paths, device="cpu", chunk=8192):
    """Ensemble mean prediction over ALL cached rows, in model target space."""
    import torch
    cache, meta = load_cache()
    T = _tensors(cache, meta, device)
    N = cache["Y"].shape[0]
    acc = np.zeros((N, len(METRICS)), np.float64)
    for p in paths:
        ck = _torch_load(p, device)
        model = make_model(ck["arm"], ck["h"], ck["max_params"], len(METRICS)).to(device)
        model.load_state_dict(ck["state"])
        model.eval()
        mu = torch.tensor(np.asarray(ck["mu"], np.float32), device=device)
        sd = torch.tensor(np.asarray(ck["sd"], np.float32), device=device)
        out = np.zeros((N, len(METRICS)), np.float32)
        with torch.no_grad():
            for b in range(0, N, chunk):
                ix = torch.arange(b, min(b + chunk, N), device=device)
                out[b:b + chunk] = (_forward(model, T, ix) * sd + mu).cpu().numpy()
        acc += out
    return acc / float(len(paths))


# ============================================================ STEP 3: evaluation
def _ranks(a):
    """Average ranks (ties shared), O(n log n) -- the store has long flat tails
    (every dead point reads S21 = -600), so ties must not be broken by order."""
    o = np.argsort(a, kind="mergesort")
    sa = a[o]
    r = np.empty(len(a), np.float64)
    i, n = 0, len(a)
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        r[o[i:j + 1]] = 0.5 * (i + j)
        i = j + 1
    return r


def _spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return float("nan")
    ra, rb = _ranks(a[ok]), _ranks(b[ok])
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    den = math.sqrt(float((ra * ra).sum() * (rb * rb).sum()))
    return float((ra * rb).sum() / den) if den > 0 else float("nan")


def score(P, cache, idx, name):
    """Per-metric MAE / RMSE / Spearman on one stratum, in TARGET units.

    Target units are the stored units for every metric except `idd_ma`, which is
    log10(mA) -- so its MAE is a decade error, and a relative-error column is
    reported alongside."""
    out = {}
    ix = idx[name]
    for k, mname in enumerate(METRICS):
        t, p = cache["Y"][ix, k].astype(np.float64), P[ix, k]
        ok = np.isfinite(t) & np.isfinite(p)
        e = p[ok] - t[ok]
        out[mname] = {"n": int(ok.sum()), "mae": float(np.abs(e).mean()),
                      "rmse": float(np.sqrt((e * e).mean())),
                      "rho": _spearman(t[ok], p[ok]),
                      "sd_true": float(t[ok].std())}
    return out


def report_eval(P, cache, meta, idx, sigma_bo3=0.726, sigma_single=1.478):
    strata = [("point", "within-family / within-topology point holdout"),
              ("run", "held-out whole RUN of a seen topology"),
              ("val", "cross-family (val families)"),
              ("cross", "cross-family (test families) -- COLD START")]
    print("\n=== per-metric accuracy (target units; idd_ma is log10 mA) ===")
    print("sigma floor for S21 (FINDINGS 14.1): best-of-3 %.3f dB / single-seed %.3f dB"
          % (sigma_bo3, sigma_single))
    print("  (that is SIZING-RUN seed noise, not point noise -- the point label is")
    print("   deterministic, measured at 0.0000 by the replay fence.)")
    res = {}
    for key, label in strata:
        if len(idx[key]) == 0:
            print("\n-- %s: EMPTY (no rows in this stratum)" % label)
            continue
        s = score(P, cache, idx, key)
        res[key] = s
        print("\n-- %s   [n = %d rows]" % (label, len(idx[key])))
        print("   %-16s %8s %8s %8s %8s" % ("metric", "MAE", "RMSE", "rho", "sd(true)"))
        for m in METRICS:
            d = s[m]
            print("   %-16s %8.3f %8.3f %8.3f %8.3f"
                  % (m, d["mae"], d["rmse"], d["rho"], d["sd_true"]))
        v = s["s21_db"]
        print("   S21: MAE %.3f dB vs sigma_bo3 %.3f -> %s"
              % (v["mae"], sigma_bo3,
                 "UNDER the floor" if v["mae"] <= sigma_bo3 else "ABOVE the floor"))
    return res


# ------------------------------------------------- the offline ZOAF replay gate
def _metric_dict(vec):
    """Model-space vector -> the metrics dict `spec.objective` consumes."""
    return dict((m, from_model(m, vec[i])) for i, m in enumerate(METRICS))


def replay_gate(P, cache, meta, spec, which="cross", delta=0.5, warmup=8, cal=True,
                held=()):
    """Replay every stored ZOAF run with a surrogate pre-gate. ZERO new SPICE.

    A block of point rows IS a sizing run, in the order ngspice saw it. Walk it
    again; before each evaluation ask the surrogate what it expects, and skip the
    ngspice call when the prediction is clearly worse than the incumbent best
    (rule pre-registered in plans2/12 section 3.1). A skipped point cannot become
    the incumbent -- that is the whole risk, and the number that matters is how
    often the run's final argmin changes."""
    rows = []
    path = os.path.join(HERE, "data", "sim_points.jsonl")
    with io.open(path, "r", encoding="utf-8") as fh:
        raw = fh.readlines()
    split_of_topo = cache["split_of_topo"]
    row_run = cache["row_run"]
    starts = np.searchsorted(row_run, np.arange(len(meta["runs"])), "left")
    ends = np.searchsorted(row_run, np.arange(len(meta["runs"])), "right")
    # "held_run" is the WARM-START deployment, and the one this program actually
    # hits every night: size_best_of_k re-sizes the same topology with 3 seeds, so
    # runs 2 and 3 are always "a new run of a topology we have already explored".
    held = set(held)
    want = {"cross": 2, "val": 1, "train": 0, "held_run": 0}[which]
    n_sim = n_tot = n_runs = n_keep = 0
    n_tol = n_flip = 0
    degrade, kept_sim, kept_tot = [], 0, 0
    for ri, run in enumerate(meta["runs"]):
        if split_of_topo[run["topo"]] != want:
            continue
        if which == "held_run" and ri not in held:
            continue
        if which == "train" and ri in held:
            continue
        a, b = int(starts[ri]), int(ends[ri])
        if b - a != run["n"]:
            continue                       # cache/meta drift guard
        truem = [json.loads(raw[run["start_line"] + j])["metrics"]
                 for j in range(run["n"])]
        ftrue = np.array([spec.objective(m) for m in truem])
        pred = P[a:b]
        resid = np.zeros(len(METRICS))
        simmed, fstar, res_hist = [], float("inf"), []
        for j in range(run["n"]):
            if j >= warmup:
                fhat = spec.objective(_metric_dict(pred[j] + resid))
                if not np.isfinite(fhat) or fhat > fstar + delta:
                    continue               # SKIPPED -- no ngspice call
            simmed.append(j)
            fstar = min(fstar, ftrue[j])
            if cal:
                res_hist.append(cache["Y"][a + j] - pred[j])
                resid = np.nanmedian(np.array(res_hist), 0)
                resid = np.nan_to_num(resid)
        true_arg = int(np.argmin(ftrue))
        gate_arg = simmed[int(np.argmin(ftrue[simmed]))]
        n_runs += 1
        n_sim += len(simmed)
        n_tot += run["n"]
        if gate_arg == true_arg or ftrue[gate_arg] == ftrue[true_arg]:
            n_keep += 1
            kept_sim += len(simmed)
            kept_tot += run["n"]
        else:
            degrade.append(float(ftrue[gate_arg] - ftrue[true_arg]))
        # decision relevance: does the run's ANSWER move, not just its argmin?
        if ftrue[gate_arg] <= ftrue[true_arg] + 0.05:
            n_tol += 1
        if (ftrue[gate_arg] < 0) != (ftrue[true_arg] < 0):
            n_flip += 1
    if not n_runs:
        return None
    out = {"stratum": which, "delta": delta, "warmup": warmup, "cal": bool(cal),
           "runs": n_runs, "sims": n_sim, "points": n_tot,
           "skipped_pct": 100.0 * (1 - n_sim / float(n_tot)),
           "runs_argmin_preserved": n_keep,
           "runs_within_0p05": n_tol,
           "pct_runs_within_0p05": 100.0 * n_tol / float(n_runs),
           "runs_feasibility_flipped": n_flip,
           "pct_runs_preserved": 100.0 * n_keep / float(n_runs),
           "skipped_pct_on_preserved_runs":
               100.0 * (1 - kept_sim / float(kept_tot)) if kept_tot else 0.0,
           "objective_degradation_mean": float(np.mean(degrade)) if degrade else 0.0,
           "objective_degradation_max": float(max(degrade)) if degrade else 0.0}
    return out


def print_gate(g):
    print("  delta %-5s cal=%-5s | runs %3d | sims %6d/%6d  skipped %5.1f%% | "
          "argmin kept %3d/%-3d (%5.1f%%) | within .05 %5.1f%% | feas-flip %d | "
          "skipped-on-kept %5.1f%% | degrade mean %.3f max %.3f"
          % (g["delta"], g["cal"], g["runs"], g["sims"], g["points"],
             g["skipped_pct"], g["runs_argmin_preserved"], g["runs"],
             g["pct_runs_preserved"], g["pct_runs_within_0p05"],
             g["runs_feasibility_flipped"], g["skipped_pct_on_preserved_runs"],
             g["objective_degradation_mean"], g["objective_degradation_max"]))


# ==================================================================== CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build-cache", action="store_true")
    ap.add_argument("--validate-join", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--arm", default="node", choices=("node", "concat", "film"))
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("-n", type=int, default=8, help="rows for --validate-join")
    ap.add_argument("--delta", type=float, default=0.5)
    ap.add_argument("--warmup", type=int, default=8)
    ap.add_argument("--oracle", action="store_true",
                    help="run the gate on the TRUE metrics -- the ceiling of the "
                         "skip mechanism itself, independent of any model")
    ap.add_argument("--out", default=None, help="write a JSON report here")
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s.strip() != ""]
    report = {}

    if a.build_cache:
        report["join"] = build_cache()
        report["join"].pop("topos", None)
        report["join"].pop("runs", None)
    if a.validate_join:
        report["fence_worst_abs_delta"] = validate_join(n=a.n)
    if a.train:
        for s in seeds:
            p, v = train(arm=a.arm, seed=s, epochs=a.epochs, batch=a.batch,
                         device=a.device)
            report.setdefault("ckpts", []).append({"path": p, "val": v, "seed": s})
    if a.eval or a.gate:
        cache, meta = load_cache()
        idx, held = splits(cache, meta)
        paths = [os.path.join(CKPT_DIR, "%s_s%d.pt" % (a.arm, s)) for s in seeds]
        paths = [p for p in paths if os.path.exists(p)]
        if not paths:
            raise SystemExit("no checkpoints for arm %s seeds %s" % (a.arm, seeds))
        print("[eval] arm=%s ensemble of %d: %s"
              % (a.arm, len(paths), ", ".join(os.path.basename(p) for p in paths)))
        print("[eval] strata rows: " + "  ".join("%s=%d" % (k, len(v))
                                                 for k, v in sorted(idx.items())))
        P = predict(paths, device=a.device)
        if a.eval:
            report["accuracy"] = report_eval(P, cache, meta, idx)
        if a.gate:
            spec = era_spec()
            print("\n=== offline ZOAF replay gate (ZERO new SPICE) ===")
            print("rule: warm-up K=%d always simulated; skip when predicted objective"
                  % a.warmup)
            print("      exceeds the incumbent best by more than delta.")
            gates = []
            if a.oracle:
                # The control: a PERFECT surrogate. It can only skip points that
                # truly do not beat the incumbent, so preservation is 100% by
                # construction and the skip rate is the mechanism's ceiling --
                # the number every model result below should be read against.
                print(chr(10) + "[ORACLE -- true metrics as predictions; the ceiling]")
                for which in ("cross", "held_run", "train"):
                    g = replay_gate(cache["Y"].astype(np.float64), cache, meta,
                                    spec, which=which, delta=0.0,
                                    warmup=a.warmup, cal=False, held=held)
                    if g is not None:
                        g["arm"] = "oracle"
                        g["stratum"] = which + "/oracle"
                        gates.append(g)
                        print("  %-6s" % which, end="")
                        print_gate(g)
            for which in ("cross", "held_run", "train"):
                print(chr(10) + "[%s]" % which)
                for cal in (True, False):
                    for d in (0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0):
                        g = replay_gate(P, cache, meta, spec, which=which,
                                        delta=d, warmup=a.warmup, cal=cal,
                                        held=held)
                        if g is None:
                            continue
                        g["arm"] = a.arm
                        gates.append(g)
                        if d == a.delta or True:
                            print_gate(g)
            report["gate"] = gates
    if a.out:
        with io.open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, indent=1, sort_keys=True, default=float)
        print("\n[out] wrote %s" % a.out)


if __name__ == "__main__":
    main()
