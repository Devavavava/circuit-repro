"""ZOAF sizing loop (WP-SIZE, plans/05-SIZING.md).

Per candidate topology (post-bias, L1-conducting), turn the .param surface into a
vector x in [0,1]^d, and let ZOAF drive ngspice toward the spec's objective:

    x  --(log/linear map per param kind)-->  device values
       --> extract.run_and_extract --> metrics --> spec.objective (feasibility-first)

ZOAF MAXIMISES, so the driver maximises `-spec.objective`: every feasible point
(objective < 0) beats every infeasible one (objective >= 1), and among feasible
points more objective improvement wins. Params are normalised to [0,1]^d and
mapped log-scale for W/R/C/L, linear for bias voltages.

The headline test (§3.1) is the anchor re-derivation: strip the stage-B reference
to defaults, hand the sizer its topology + wifi24, and check ZOAF reaches
feasibility near the hand-tuned numbers -- it validates extract.py, the objective
encoding, and ZOAF's budget at once on a circuit whose answer is known.

    python lna/size.py --anchor            # re-derive the stage-B reference vs wifi24

NF: as of WP-D1 the sizer GATES nf_db whenever the spec asks it to (see
`_spec_for_sizing` / `nf_is_gated`). The measurement is the golden-validated
series-Rs one (`extract.measure_nf`), taken inside the loop -- one extra ~0.07 s
ngspice call per evaluation -- because a supported-but-missing metric counts as
fully violated and would flatten the objective. Everything logged BEFORE that is
a tier-1 (S11/S21/Idd) claim; `zoaf_cfg.nf_gated` separates the two label
domains. Enable finite inductor Q in the deck for physical inductors.
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "misc", "ZOAF")))
import extract as E  # noqa: E402
import datastore as ds  # noqa: E402  (append-only label store, 01-DATA)
from spec import Spec  # noqa: E402
from zoaf.zoaf_core import ZOAF  # noqa: E402  (generic core; the *param variants pull PySpice)

# spec.objective is minimised feasibility-first (>=1 infeasible, <0 feasible), so a
# failed simulation must score worse than any infeasible point.
SIM_FAIL_PENALTY = 1e3


def kind_ranges(spec):
    # PyYAML parses exponentials without a decimal point (20e3, 10e-12) as
    # strings, so coerce every bound to float.
    sz, topo = spec.sizing, spec.topology
    f = float
    return {   # kind: (lo, hi, log?)
        "W":  (f(sz["w_um"][0]) * 1e-6, f(sz["w_um"][1]) * 1e-6, True),
        "L":  (f(topo.get("l_min", 0.3e-9)), f(topo.get("l_max", 12e-9)), True),
        "R":  (f(sz["r_ohm"][0]), f(sz["r_ohm"][1]), True),
        "C":  (f(sz["c_f"][0]), f(sz["c_f"][1]), True),
        "VB": (f(sz["vb_v"][0]), f(sz["vb_v"][1]), False),
    }


def nf_is_gated(spec):
    """Does this spec gate nf_db as a hard constraint? (WP-D1 step 4.)

    When it does, NF must be measured INSIDE the sizing loop, not enriched once at
    the end: spec.feasible() counts a missing supported metric as fully violated,
    so an unmeasured NF would make every point infeasible and flatten the
    objective. Costs one extra ngspice call per evaluation (~0.07 s, same order as
    the op/sp call)."""
    c = spec.constraints.get("nf_db")
    return bool(c) and c.get("status") != "unsupported"


def eval_metrics(body, params, spec, nf_gated=None):
    """One full L2 evaluation: op/sp/stability, plus the series-Rs NF when gated."""
    m = E.run_and_extract(body, params, spec)
    if m is None:
        return None
    if nf_is_gated(spec) if nf_gated is None else nf_gated:
        nf = E.measure_nf(body, params, spec)
        m = dict(m, nf_db=nf, nf_method="series_rs" if nf is not None else None)
    return m


def make_objective(body, spec, sizable, fixed, points=None):
    """sizable: {param_name: kind}; fixed: {param_name: literal}. Returns
    (objective_func for ZOAF, names, decode(x)->metrics helper).

    If `points` (a list) is given, every ngspice eval appends `(x, metrics)` to
    it -- the free point-row byproduct (01-DATA §1). This only *reads* x and the
    metrics the objective already computed, so the returned objective value is
    byte-for-byte unchanged (the additive-hook invariant)."""
    names = list(sizable)
    ranges = kind_ranges(spec)
    nf_gated = nf_is_gated(spec)

    def decode(x):
        params = dict(fixed)
        for xi, name in zip(x, names):
            lo, hi, islog = ranges[sizable[name]]
            xi = float(min(max(xi, 0.0), 1.0))
            v = (10 ** (math.log10(lo) + xi * (math.log10(hi) - math.log10(lo)))
                 if islog else lo + xi * (hi - lo))
            params[name] = f"{v:.6g}"
        return params

    def evaluate(x):
        return eval_metrics(body, decode(x), spec, nf_gated=nf_gated)

    def objective_func(x):
        m = evaluate(x)
        if points is not None:
            points.append(([float(v) for v in x], m))
        return SIM_FAIL_PENALTY if m is None else spec.objective(m)

    return objective_func, names, decode, evaluate


def run_zoaf(objective_func, names, seed=1, n_candidates=8, sgd_iters=8, cgd_iters=2):
    bounds = np.array([[0.0, 1.0]] * len(names))   # x normalised; decode maps to values
    opt = ZOAF(objective_func, bounds, maximize=False, n_candidates=n_candidates,
               n_starts=4, sampling="hybrid", sgd_iterations=sgd_iters,
               sgd_K=2, sgd_lr=0.3, sgd_mu=0.1, cgd_iterations=cgd_iters,
               cgd_lr=0.5, cgd_mu=0.3, seed=seed)
    res = opt.optimize()
    return res.x_best, res.f_best, res.n_evals


def classify_params(nl):
    """From a bias-inserted Netlist, split .param names into sizable (kind) and
    fixed (literal). Widths/R/C/L values and inserted bias voltages are sized;
    channel length, bias-feed R, supplies stay fixed."""
    from topology import base_of
    sizable, fixed = {}, {}
    for d in sorted(nl.t.devices):
        b = base_of(d)
        if b in ("NM", "PM"):
            sizable[f"p{d}W"] = "W"
            fixed[f"p{d}L"] = "45n"
        elif b == "R":
            sizable[f"p{d}V"] = "R"
        elif b == "C":
            sizable[f"p{d}V"] = "C"
        elif b == "L":
            sizable[f"p{d}V"] = "L"
    for p, v in nl.extra_params.items():
        (sizable.__setitem__(p, "VB") if p.startswith("pVBG")
         else fixed.__setitem__(p, v))
    fixed["pVDD"] = "1.1"
    fixed["pVB"] = "0.5"
    # Finite-Q constants (pINDQ/pINDW0) are emitted into the netlist's own .param
    # block by to_spice, but E.body_of() strips every .param line, so they must be
    # re-declared here as fixed or the RQ series-R expression evaluates undefined
    # ("Undefined parameter [pindw0]"). Recompute w0 exactly as to_spice.emit does.
    if nl.inductor_q:
        lo, hi = nl.freq[0], nl.freq[1]
        f0 = (lo * hi) ** 0.5
        fixed["pINDQ"] = str(nl.inductor_q)
        fixed["pINDW0"] = f"{2 * math.pi * f0:g}"
    return sizable, fixed


def _zoaf_cfg(seed, n_candidates, sgd_iters, cgd_iters, recipe="anchor-v1",
             inductor_q=None, spec=None):
    """The fixed label budget (01-DATA §5): labels are only comparable at equal
    ZOAF budget, so the knobs that define it are stamped on every row. inductor_q
    is a deck/harness setting that changes the metrics, so it is stamped too --
    and so is `nf_gated` (WP-D1 step 4), which changes what the optimizer is even
    solving. Rows with nf_gated true/false are DIFFERENT label domains; every row
    written before WP-D1 is implicitly nf_gated:false (tier-1)."""
    cfg = {"recipe": recipe, "seed": seed, "n_candidates": n_candidates,
           "n_starts": 4, "sgd_iters": sgd_iters, "cgd_iters": cgd_iters,
           "inductor_q": inductor_q}
    if spec is not None:
        cfg["nf_gated"] = nf_is_gated(spec)
    return cfg


def _enrich_nf(body, params, spec, m):
    """Replace the port-based (unphysical, finding #7) nf_db with the series-Rs NF
    measured at the sized point. Additive: NF is `unsupported` in the sizing spec,
    so this changes only the logged metric, never sizing/feasibility/objective.
    One extra ~1 s ngspice call per label; defensive (keeps the old value on
    failure)."""
    if m is None:
        return m
    try:
        nf = E.measure_nf(body, params, spec)
        if nf is not None:
            return dict(m, nf_db=nf, nf_method="series_rs")
    except Exception:
        pass
    return m


def _log_l2(spec, metrics, feasible, n_evals, points, best_x, best_params,
            best_obj, topo, wl_hash, provenance, zoaf_cfg, repeat_probe=False):
    """Append an L2 row (+ its point rows) to the label store. Logging must never
    break a sizing run, so any failure is warned and swallowed."""
    try:
        row = ds.row_l2(spec, metrics, feasible, n_evals, best_x=best_x,
                        best_params=best_params, best_obj=best_obj, topo=topo,
                        wl_hash=wl_hash, provenance=provenance, zoaf_cfg=zoaf_cfg)
        status, _ = ds.append_l2(row, repeat_probe=repeat_probe)
        if status == "appended" and points:
            ds.append_all("sim_points",
                          [ds.row_point(wl_hash, spec.name, x, m) for x, m in points])
        extra = f" +{len(points)} points" if status == "appended" and points else ""
        print(f"  [log] L2 {status}: ({wl_hash}, {spec.name}){extra}")
        return status
    except Exception as e:                       # logging is additive, never fatal
        print(f"  [log] WARN: L2 logging failed: {e}")
        return "error"


def match_devices(topo):
    """Input-match passives (06-LAST-MILE §1): 2-terminal R/C/L on the path from the
    input port to the first MOS gate, plus the input device's source (degeneration)
    and gate-source passives. Fixing these -- not sizing them free -- is what let the
    tapped reference reach feasibility (all-free ZOAF lands gain OR match, not both).
    Returns (set of match device tokens, input device token or None)."""
    from collections import defaultdict, deque
    from topology import base_of, PIN_RE
    pin2root = {m: r for r, members in topo.nodes.items() for m in members}
    net2root = {m: r for r, members in topo.nodes.items()
                for m in members if m in topo.nets}
    devpin = defaultdict(dict)
    for p in topo.pins:
        mm = PIN_RE.match(p)
        if mm and p in pin2root:
            devpin[mm.group("dev")][mm.group("pin")] = pin2root[p]
    adj = defaultdict(list)                       # passive adjacency over nodes
    for d in topo.devices:
        if base_of(d) in ("R", "C", "L"):
            pp = devpin.get(d, {})
            if "P" in pp and "N" in pp:
                adj[pp["P"]].append((d, pp["N"]))
                adj[pp["N"]].append((d, pp["P"]))
    gate_node = {devpin[d].get("G"): d for d in topo.devices
                 if base_of(d) in ("NM", "PM")}
    vin = next((n for n in sorted(topo.nets) if n.startswith("VIN")), None)
    start, match, input_dev = net2root.get(vin), set(), None
    if start is not None:
        seen, dq = {start}, deque([start])
        while dq:
            u = dq.popleft()
            for dev, v in adj[u]:
                match.add(dev)                    # passive on the input path
                if v in gate_node and input_dev is None:
                    input_dev = gate_node[v]
                if v not in seen and v not in gate_node:
                    seen.add(v)
                    dq.append(v)
    if input_dev:                                 # + source-degen / gate-source
        snode = devpin[input_dev].get("S")
        for d in topo.devices:
            if base_of(d) in ("R", "C", "L") and snode in devpin.get(d, {}).values():
                match.add(d)
    return match, input_dev


def _curate(topo, sizable, fixed, prior_params):
    """Move the input-match passives from sizable to fixed at their prior best
    values (06-LAST-MILE §1). Returns the match device set actually fixed."""
    mdevs, _ = match_devices(topo)
    fixed_now = set()
    for d in mdevs:
        p = f"p{d}V"                              # passive value param (R/C/L)
        if p in sizable and prior_params and p in prior_params:
            fixed[p] = prior_params[p]
            del sizable[p]
            fixed_now.add(d)
    return fixed_now


def replay_ok(topo, best_params, spec, stored_metrics, sigma=1.0, inductor_q=12):
    """Replay invariant (07-EXIT §1a): re-evaluating a stored `best_params` on the
    topology reconstructed from the *same* row's tokens must reproduce the stored
    metrics within label noise. It fails when a (topo, params) pair is inconsistent
    -- e.g. a token_file re-parsed from a different arm's same-named seq (the bug
    that stalled polish). Such rows are quarantined, not sized. Returns bool."""
    import bias
    if not (best_params and stored_metrics):
        return False
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return False
    m = E.run_and_extract(E.body_of(nl.emit()), best_params, spec)
    if m is None:
        return False
    s = max(sigma, 0.5)
    return (abs((m.get("s21_db") or -1e9) - (stored_metrics.get("s21_db") or 1e9)) <= s
            and abs((m.get("s11_db") or -1e9) - (stored_metrics.get("s11_db") or 1e9)) <= 2.0)


def polish(topo, spec, prior_params, budget=80, inductor_q=12):
    """Boundary polish (06-LAST-MILE §2): coordinate pattern search from the stored
    best point that maximizes the **minimum normalized margin** -- which, unlike the
    feasibility-first scalar, has a gradient right at the boundary (it trades a
    near-miss's slack on a passing constraint for the one it violates). Perturbs
    only the sizable device/bias params (match held via prior values); ~budget sims.
    Returns {metrics, feasible, best_params, n_evals, min_margin} or None."""
    import bias
    from datastore import margins_for
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return None
    body = E.body_of(nl.emit())
    sizable, _ = classify_params(nl)
    nf_gated = nf_is_gated(spec)
    # ascend the minimum margin over every SUPPORTED hard constraint -- so when a
    # spec gates NF, polish trades gain slack for noise instead of ignoring it.
    keys = [n for n, c in spec.constraints.items() if c.get("status") != "unsupported"]

    def min_margin(p):
        m = eval_metrics(body, p, spec, nf_gated=nf_gated)
        if m is None:
            return -1e9, None
        mg = margins_for(spec, m)
        vals = [(mg.get(k) or {}).get("margin") for k in keys]
        vals = [v for v in vals if v is not None]
        if len(vals) < len(keys):        # a supported constraint went unmeasured
            return -1e9, m
        return (min(vals) if vals else -1e9), m

    params = {k: v for k, v in (prior_params or {}).items()}
    best_mm, best_m = min_margin(params)
    n, step = 1, 0.15
    while n < budget and step > 0.02:
        improved = False
        for name in list(sizable):
            if name not in params:
                continue
            try:
                base = float(params[name])
            except (TypeError, ValueError):
                continue
            for factor in (1 - step, 1 + step):
                trial = dict(params)
                trial[name] = f"{base * factor:.6g}"
                mm, m = min_margin(trial)
                n += 1
                if mm > best_mm:
                    best_mm, best_m, params, improved = mm, m, trial, True
                if n >= budget:
                    break
            if n >= budget:
                break
        if not improved:
            step *= 0.6
    feas = best_m is not None and spec.feasible(best_m)[0]
    return {"metrics": best_m, "feasible": feas, "best_params": params,
            "n_evals": n, "min_margin": best_mm}


def size_topology(topo, spec, seed=1, n_candidates=6, sgd_iters=6, cgd_iters=1,
                  provenance=None, log=True, repeat_probe=False, inductor_q=None,
                  curate=False, prior_params=None):
    """Bias-insert, then ZOAF-size a generated topology against `spec`.

    With `log=True` (default for CLI paths) the completed sizing run is appended
    to the label store as one L2 row; pass `log=False` for throwaway experiments
    (`size.py --no-log`) and from callers that only want the score. `inductor_q`
    (default None = ideal, unchanged) gives inductors finite Q so real
    inductor-bearing topologies do not hit the ideal-branch singularity that
    finding #10 / R1 flagged -- HANDOVER-EXEC §6.1's "size with inductor_q=12"."""
    import bias
    from novelty import wl_features
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, inserter, rep, swept = bias.insert_bias(topo, sweep=True, **kw)
    if rep.get("skipped") or not nl.two_port:
        return None
    body = E.body_of(nl.emit())
    sizable, fixed = classify_params(nl)
    recipe = "candidate-v1"
    if curate:
        _curate(topo, sizable, fixed, prior_params)   # fix input match at prior best
        recipe = "curated-v1"
    if not sizable:
        return None
    points = [] if log else None
    obj, names, decode, evaluate = make_objective(body, spec, sizable, fixed,
                                                  points=points)
    best_x, best_obj, n_evals = run_zoaf(obj, names, seed=seed,
                                         n_candidates=n_candidates,
                                         sgd_iters=sgd_iters, cgd_iters=cgd_iters)
    m = evaluate(best_x)
    if log:
        m = _enrich_nf(body, decode(best_x), spec, m)   # physical NF for the row
    feas, viol = (spec.feasible(m) if m is not None else (False, None))
    if log:
        _log_l2(spec, m, feas, n_evals, points, best_x, decode(best_x), best_obj,
                topo, wl_features(topo)[0], provenance,
                _zoaf_cfg(seed, n_candidates, sgd_iters, cgd_iters, recipe,
                          inductor_q=inductor_q, spec=spec),
                repeat_probe=repeat_probe)
    if m is None:
        return {"metrics": None, "feasible": False, "n_evals": n_evals}
    return {"metrics": m, "feasible": feas, "viol": viol, "n_evals": n_evals,
            "best_obj": best_obj, "n_params": len(names),
            "best_params": decode(best_x)}   # so callers can polish/curate from here


def _nf_gate_default():
    """Global default for NF gating. True since WP-D1; set LNA_NF_GATE=0 in the
    environment to run a whole session under the old tier-1 gating (an escape
    hatch for reproducing/continuing a tier-1 campaign without editing code)."""
    return os.environ.get("LNA_NF_GATE", "1").strip().lower() not in ("0", "false", "no")


def _spec_for_sizing(name, nf_gate=None):
    """Load a spec for the sizing loop.

    HISTORY / LABEL DOMAIN (important when comparing rows): until WP-D1 this
    function *forced* nf_db to `unsupported`, because the only NF the harness had
    was the port-referred one that finding #7 retired. Every feasibility claim
    logged before then -- the wifi24 six, the two gps-l1 generated feasibles, the
    dhruva 4-band family -- is therefore a **tier-1** claim (S11/S21/Idd only)
    and stays valid on its own terms.

    Now that `extract.measure_nf` is golden-validated, nf_gate=True (the default)
    honours whatever the YAML says, so NF is a real hard constraint. Pass
    nf_gate=False to reproduce a tier-1 result exactly under the old gating --
    that is history, not a fallback to be used for new labels."""
    if nf_gate is None:
        nf_gate = _nf_gate_default()
    spec = Spec.load(name)
    if not nf_gate and "nf_db" in spec.constraints:
        spec.constraints["nf_db"]["status"] = "unsupported"
    return spec


def scoreboard(directory, spec_name="wifi24", seed=1, max_candidates=4, log=True):
    """Size the top spec-passing candidates in a generation dir end-to-end.

    The program's headline: spec in, novel generated topology -> bias -> ZOAF
    sized -> scored. (NF gated off pending the harness fix.) Every candidate's
    sizing run is logged as an L2 row unless `log=False` (--no-log)."""
    import glob
    from topology import Topology, parse_arrow_file
    from novelty import corpus_reference, wl_features
    spec = _spec_for_sizing(spec_name)
    corpus_hashes, _ = corpus_reference()

    cands = []
    for f in sorted(glob.glob(os.path.join(directory, "seq*.txt"))):
        topo = Topology(parse_arrow_file(f))
        if not spec.structural_screen(topo)[0]:
            continue
        novel = wl_features(topo)[0] not in corpus_hashes
        cands.append((f, topo, novel))
        if len(cands) >= max_candidates:
            break

    arm = os.path.basename(os.path.normpath(directory))
    print(f"sizing {len(cands)} spec-passing candidates from {directory} vs "
          f"{spec_name} (nf gated off)\n")
    print(f"{'candidate':<12} {'novel':>5} {'dev':>3} {'sims':>5} "
          f"{'S11':>7} {'S21':>7} {'Idd':>6} {'feasible':>9}")
    n_feas = 0
    for f, topo, novel in cands:
        name = os.path.basename(f)
        prov = {"source_arm": arm, "seed": seed,
                "token_file": os.path.relpath(f, HERE).replace("\\", "/")}
        res = size_topology(topo, spec, seed=seed, provenance=prov, log=log)
        if res is None or res["metrics"] is None:
            print(f"{name:<12} {str(novel):>5} {topo.n_devices:>3}   "
                  f"{'-':>5}  (bias/sim failed)")
            continue
        m = res["metrics"]
        n_feas += int(res["feasible"])
        print(f"{name:<12} {str(novel):>5} {topo.n_devices:>3} {res['n_evals']:>5} "
              f"{m['s11_db']:>7.1f} {m['s21_db']:>7.1f} {m.get('idd_ma') or 0:>6.2f} "
              f"{'FEASIBLE' if res['feasible'] else 'no':>9}")
    print(f"\n{n_feas}/{len(cands)} feasible (Gate G4 needs >=1 novel + feasible; "
          "S21 ceiling is the topology, finding #10)")
    return n_feas


def log_l2_result(spec, topo, metrics, feasible, best_params, provenance, recipe,
                  n_evals, inductor_q=12, repeat_probe=True):
    """Append an already-computed sizing result (curated ZOAF or polish) as one L2
    row without re-sizing -- so a boundary/polish win is recorded exactly as found.
    Reconstructs the body only to enrich the physical NF."""
    import bias
    from novelty import wl_features
    kw = {"inductor_q": inductor_q} if inductor_q else {}
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, **kw)
    m = metrics
    if not rep.get("skipped") and nl.two_port:
        m = _enrich_nf(E.body_of(nl.emit()), best_params, spec, metrics)
    _log_l2(spec, m, feasible, n_evals, None, None, best_params, None, topo,
            wl_features(topo)[0], provenance,
            _zoaf_cfg(0, 0, 0, 0, recipe, inductor_q=inductor_q, spec=spec),
            repeat_probe=repeat_probe)
    return m


def backfill_corpus(spec_name="wifi24", indices=None, seed=1, inductor_q=12,
                    limit=None, log=True):
    """Backfill L2 rows for the in-scope corpus LNAs (01-DATA §4 item 1).

    Sizes every screen-passing corpus LNA vs `spec` and logs one L2 row each.
    Idempotent: a (wl_hash, spec) key already in the store is skipped, so an
    interrupted run resumes cleanly on relaunch. Inductors get finite Q by
    default (real corpus LNAs need it -- HANDOVER-EXEC §6.1)."""
    from bias import topo_from_index, REPO
    from novelty import wl_features
    spec = _spec_for_sizing(spec_name)
    if indices is None:
        indices = list(range(461, 493)) + list(range(1081, 1091))
    done = ds.existing_l2_keys()
    print(f"corpus L2 backfill vs {spec_name} (inductor_q={inductor_q}, nf gated "
          f"off): {len(indices)} candidate indices\n")
    print(f"{'idx':>5} {'scr':>4} {'dev':>3} {'sims':>5} {'S11':>7} {'S21':>7} "
          f"{'Idd':>6} {'feasible':>9}")
    n_sized = n_feas = n_skip = 0
    for i in indices:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        topo = topo_from_index(i)
        if not spec.structural_screen(topo)[0]:
            print(f"{i:>5} {'no':>4} {topo.n_devices:>3}   (screen reject)")
            continue
        if (wl_features(topo)[0], spec.name) in done:
            n_skip += 1
            print(f"{i:>5} {'yes':>4} {topo.n_devices:>3}   (already labeled, skip)")
            continue
        res = size_topology(topo, spec, seed=seed, inductor_q=inductor_q, log=log,
                            provenance={"source_arm": "corpus", "index": i,
                                        "inductor_q": inductor_q})
        n_sized += 1
        if res is None or res["metrics"] is None:
            print(f"{i:>5} {'yes':>4} {topo.n_devices:>3}   {'-':>5}  (bias/sim failed)")
        else:
            m = res["metrics"]
            n_feas += int(res["feasible"])
            print(f"{i:>5} {'yes':>4} {topo.n_devices:>3} {res['n_evals']:>5} "
                  f"{m['s11_db']:>7.1f} {m['s21_db']:>7.1f} {m.get('idd_ma') or 0:>6.2f} "
                  f"{'FEASIBLE' if res['feasible'] else 'no':>9}")
        if limit and n_sized >= limit:
            print(f"  (limit {limit} reached)")
            break
    print(f"\nsized {n_sized} new, {n_feas} feasible, {n_skip} already-present")
    return n_sized


def _size_ref(deck, sizable, fixed, spec_name, recipe, label, seed=1, log=True):
    """Size a hand-written reference deck vs a spec with ZOAF and (optionally) log
    the L2 row. Shared by the stage-B anchor re-derivation and the tapped-C
    gain-capable reference; returns (feasible, metrics)."""
    spec = _spec_for_sizing(spec_name)
    print("note: nf_db treated as unsupported (port-noise harness gap); "
          "gating on S11/S21/Idd.")
    body = E.body_of(os.path.join(HERE, "ref", deck))
    points = [] if log else None
    obj, names, decode, evaluate = make_objective(body, spec, sizable, fixed,
                                                  points=points)
    print(f"{label} vs {spec_name}: {len(names)} params, ZOAF (feasibility-first).")
    best_x, best_obj, n_evals = run_zoaf(obj, names, seed=seed)
    m = evaluate(best_x)
    prov = {"source_arm": recipe.split("-")[0], "ref_deck": deck, "seed": seed}
    # reference decks have no token topology, so key them by deck name -- otherwise
    # every ref row hashes to (None, spec) and they collide.
    if m is None:
        print(f"\nZOAF: {n_evals} sims -- sizing FAILED (no metrics; deck params?)")
        if log:
            _log_l2(spec, None, False, n_evals, points, best_x, decode(best_x),
                    best_obj, None, f"ref:{deck}", prov,
                    _zoaf_cfg(seed, 8, 8, 2, recipe, spec=spec))
        return False, None
    if log:
        m = _enrich_nf(body, decode(best_x), spec, m)   # physical NF for the row
    feas, viol = spec.feasible(m)
    if log:
        _log_l2(spec, m, feas, n_evals, points, best_x, decode(best_x), best_obj,
                None, f"ref:{deck}", prov, _zoaf_cfg(seed, 8, 8, 2, recipe,
                                                    spec=spec))
    print(f"\nZOAF: {n_evals} sims, best objective {best_obj:.4f}")
    print(spec.report(m))
    print("\nsized values:")
    for k, v in decode(best_x).items():
        if k in sizable:
            print(f"    {k:<7} {v}")
    print(f"\n=> {'FEASIBLE' if feas else 'infeasible: ' + str({k: round(v,3) for k,v in viol.items()})}"
          f"  [{label}]")
    return feas, m


def size_anchor(spec_name="wifi24", seed=1, log=True):
    sizable = {"pW": "W", "pLs": "L", "pLg": "L", "pLd": "L",
               "pCex": "C", "pCtnk": "C", "pVB": "VB", "pVB2": "VB"}
    fixed = {"pL": "45n", "pRB": "10k", "pQ": "10", "pF0": "2.442e9",
             "pRq": "{2*3.14159265*pF0*pLd/pQ}"}
    feas, _ = _size_ref("ref24_csdeg.cir", sizable, fixed, spec_name,
                        "anchor-v1", "anchor re-derivation", seed=seed, log=log)
    return feas


def size_tapped(spec_name="wifi24", seed=1, log=True):
    """Size the tapped-C gain-capable reference (Stage-0 day 3). The tapped
    transformer decouples gain from the 50 ohm load, so this is the deck expected
    to reach S21 >= 12 -- the first *feasible* label (Gate G4 by hand).

    The input match (Ls/Lg/Cex) and the series tap cap Ct1 are FIXED at the
    reference's known-good values -- the cascode isolates the input from the
    output tank, so the match does not need re-tuning per output-gain point, and
    freezing them keeps ZOAF out of the degenerate 'collapse the transformer'
    basin (Ct1->max, gain->0) it fell into when everything was free. ZOAF sizes
    the gain/bias/transform knobs {W, Ld, Ct2, VB, VB2}."""
    sizable = {"pW": "W", "pLd": "L", "pCt2": "C", "pVB": "VB", "pVB2": "VB"}
    fixed = {"pL": "45n", "pRB": "10k", "pQ": "10", "pF0": "2.442e9",
             "pRq": "{2*3.14159265*pF0*pLd/pQ}",
             "pLs": "1.35n", "pLg": "8n", "pCex": "440f", "pCt1": "0.3p"}
    feas, _ = _size_ref("ref24_tapped.cir", sizable, fixed, spec_name,
                        "tapped-v1", "tapped-C gain reference", seed=seed, log=log)
    return feas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", action="store_true",
                    help="run the stage-B anchor re-derivation test")
    ap.add_argument("--tapped", action="store_true",
                    help="size the tapped-C gain-capable reference (Gate G4 by hand)")
    ap.add_argument("--scoreboard", metavar="DIR",
                    help="size the top spec-passing candidates in a generation dir")
    ap.add_argument("--corpus-l2", action="store_true",
                    help="backfill L2 rows for the in-scope corpus LNAs (01-DATA §4)")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--n", type=int, default=0,
                    help="max candidates (--scoreboard, default 4) / max new "
                         "labels (--corpus-l2, default all)")
    ap.add_argument("--inductor-q", type=int, default=12,
                    help="finite inductor Q for --corpus-l2 sizing (0 = ideal)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-log", action="store_true",
                    help="do not append L2/point rows to the label store")
    args = ap.parse_args()
    log = not args.no_log
    if args.anchor:
        return 0 if size_anchor(args.spec, seed=args.seed, log=log) else 1
    if args.tapped:
        return 0 if size_tapped(args.spec, seed=args.seed, log=log) else 1
    if args.scoreboard:
        scoreboard(args.scoreboard, args.spec, seed=args.seed,
                   max_candidates=(args.n or 4), log=log)
        return 0
    if args.corpus_l2:
        backfill_corpus(args.spec, seed=args.seed, log=log,
                        inductor_q=(args.inductor_q or None),
                        limit=(args.n or None))
        return 0
    ap.error("give --anchor, --scoreboard DIR, or --corpus-l2")


if __name__ == "__main__":
    sys.exit(main())
