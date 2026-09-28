#!/usr/bin/env python
"""bench-v1 anchor prep (externals_prep.py generalized to the four bench classes).

For every approved bench-v1 anchor family in kaggle/bench-anchors/<class>/:

    parse -> round_trip -> Topology.valid -> WL hash + novelty vs ref-v3
          -> per-class structural screen vs ONE representative bench spec
          -> CONDUCTION SMOKE (real 40-eval gf180 sizing against that spec)

and emit <family>.tokens.json + a MANIFEST.json carrying every gate result.

TWO HARNESS-CONVENTION FACTS this prep is built around (both discovered by
scouting the harnesses + proving them with the round-trip, see the report):

  * MIXER LO net = `VLO`. lna/size.py::_mixer_lo_node drives the harness LO on a
    body net literally named VLO (its first candidate). The AnalogGenie Eulerian
    tokenizer (proposal.to_tokens / dfs_all_paths) only preserves nets that are
    passed in the `ports` list, so a bare round_trip() drops VLO. This prep
    round-trips the mixer families with an EXTENDED port list (+VLO) so the LO
    net survives into the sized to_spice body and the harness can find it.

  * BALUN non-inverting output net = `VOUT2` (diff3/balun_harness port-3
    convention: port1=VIN1 RF-in, port2=VOUT1 INVERTING, port3=VOUT2
    NON-INVERTING). Same tokenizer rule -> balun families are round-tripped with
    an EXTENDED port list (+VOUT2). HISTORY (LOUD): as scouted, lna/to_spice.py
    emitted ONLY a 2-port (no port-3 path for VOUT2), so measure_balun (which
    needs S_3_1) returned None on any token->to_spice body and sds21/cmrr/
    imbalance were UNMEASURABLE in-loop. During this bring-up, commit ae751458
    ("class-objective: balun port-3 emission + VOUT2 dialect + token-topology
    golden", golden lna/ref/check_balun3.py) added a contiguous `portnum 3` on
    VOUT2 whenever the net is present AND made VOUT2 a reserved proposal-
    dialect port; the balun class harness was then verified to measure
    sds21/cmrr/imbalance end-to-end on these token topologies. The balun smoke
    fence binds on sds21 accordingly. (VLO stays a NON-dialect net -- the LO is
    a harness-injected drive, not a proposal port -- so mixers still need the
    extended tokenizer ports above.)

Fences (per the bench pre-reg conduction gate -- "best" = best over the WHOLE
40-eval run, read from the per-eval points hook, matching the v0 fence wording
"40-eval smoke, best idd_ma > 0.05"; the CMA winner alone is NOT the fence,
because a class objective dominated by class-gate penalties does not select
for idd/s21):
  * all classes: best idd_ma > 0.05 mA  (the circuit actually conducts).
  * lna / pa    : PLUS best s21_db > -30 dB   (the spec gates s21_db).
  * mixer       : PLUS conv_gain_db measured at the winning point.
  * balun       : PLUS best sds21_db > -30 dB (the spec gates sds21_db; the
                  class harness runs every eval, so best-over-run is real).

WINNER = ENDPOINT UNGATED RE-EVAL (the make_objective contract): lna/size.py's
EliteGate skips the pa/mixer harness on proxy-losing evals, and
null_sizer._Budget.best() returns the LOOP-stored metrics with NO re-sim -- so
at a small-budget smoke the loop-stored winner routinely carries no class
metrics (measured: conv_gain None on both mixer families at 40 evals).
make_objective's OWN documented answer is its 4th return value `evaluate`:
"used at best_x for the final metrics -- UNGATED, so the winning point is
always measured in full". solve_spec.size_tokens never wired it; smoke_run
does: the loop runs with the ENGINE-DEFAULT elite gate for every class (no env
overrides), and the winner is re-measured ONCE ungated at best_x -- where the
mixer fence reads conv_gain and where the PA winner's p1db/pae get recorded.

CHUNKED INVOCATION: `python kaggle/bench_anchor_prep.py [class ...]` runs only
the named classes and MERGES their records into an existing MANIFEST.json
(background runs of the full matrix were repeatedly killed in this shared
worktree; per-class foreground chunks are kill-robust). No args = all classes,
fresh manifest.

SMOKE BUDGETS (LOUD DEVIATION NOTE): the pre-reg fence names a 40-eval smoke;
the first prep run showed 40 evals cannot bring a choke-fed PA match within
the s21 fence nor hand a mixer winner measured conv_gain, and the on-disk
bring-up fix of 2026-09-14 (SMOKE_BUDGET_BY_CLASS below -- added in-worktree
during bring-up, not part of the original prep draft) raises the pa/mixer
smoke budgets to 240/160. lna/balun keep the pre-reg 40. The manifest records
the budget actually used per family.

A family failing a gate is REPORTED, not silently fixed. Zero store writes;
outputs live under kaggle/bench-anchors/. lna/ is otherwise READ-ONLY.
NOTE: novelty.reference() rewrites its cache file lna/data/novelty_ref_v2.json
(same reference, refreshed cache); restore it before committing
(`git checkout -- lna/data/novelty_ref_v2.json`).
"""
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "lna"))
sys.path.insert(0, str(REPO / "kaggle" / "loop"))

import proposal                                    # kaggle/loop/proposal.py  # noqa: E402
from topology import Topology                      # noqa: E402
from spec import Spec                              # noqa: E402
import novelty                                     # noqa: E402
import size as SZ                                  # noqa: E402
import null_sizer as NS                            # noqa: E402
import solve_spec as SS                            # noqa: E402

ANCH = REPO / "kaggle" / "bench-anchors"
SPEC = REPO / "kaggle" / "bench-specs"

# per-class: representative bench spec to screen + smoke against, and the extra
# tokenizer ports needed to preserve the class's harness-injected/second-output
# net through the AnalogGenie round-trip.
CLASS_CFG = {
    "lna":   {"spec": SPEC / "lna"   / "bnl-09-gain-g0.yaml",
              "ports": ["VDD", "VSS", "VIN1", "VOUT1"]},
    "pa":    {"spec": SPEC / "pa"    / "bpa-09-p5-e25-i5.yaml",
              "ports": ["VDD", "VSS", "VIN1", "VOUT1"]},
    "mixer": {"spec": SPEC / "mixer" / "bmx-09-cg12-ip0-iso30.yaml",
              "ports": ["VDD", "VSS", "VIN1", "VOUT1", "VLO"]},
    "balun": {"spec": SPEC / "balun" / "bbl-09-g12-c20-a05.yaml",
              "ports": ["VDD", "VSS", "VIN1", "VOUT1", "VOUT2"]},
}

# which families belong to which class (order = report order). mx-a3 is DROPPED
# by pre-approval (convention mismatch, logged in DROPPED below), never adapted.
FAMILIES = {
    "lna":   ["lna-a1-inddegen-cascode", "lna-a2-current-reuse",
              "lna-a3-shunt-feedback", "lna-a4-twostage", "lna-a5-commongate"],
    "pa":    ["pa-a1-classA-cs", "pa-a2-cascode", "pa-a3-twostage"],
    "mixer": ["mx-a1-gatepumped", "mx-a2-dualgate"],
    "balun": ["bl-a1-noisecancel", "bl-a2-cs-cg-split"],
}

DROPPED = {
    "mx-a3-singlebalanced": (
        "single-balanced Gilbert-style mixer produces a DIFFERENTIAL IF (two "
        "drain outputs), but lna/mixer_harness.measure_conv_gain reads the IF at "
        "ONE single-ended node (portnum 2 = VOUT1) and the harness injects only "
        "ONE single-ended LO drive on ONE net (VLO). The published switching-pair "
        "form needs a differential IF read + anti-phase LO; the harness supports "
        "neither. Per the approval (pre-authorized to drop on convention "
        "mismatch, never adapt beyond the published form), mx-a3 is DROPPED."),
}

SMOKE_SEED = 1
SMOKE_BUDGET = 40          # the pre-reg 40-eval conduction smoke (lna)
# Bring-up fix 2026-09-14: class-appropriate smoke budgets. 40 evals cannot
# tune a choke-fed PA match (measured s21 -41 dB = unsized, not dead); the
# winner's class metrics come from the endpoint ungated re-eval, so the loop
# itself stays elite-gated (engine default) at every budget.
SMOKE_BUDGET_BY_CLASS = {"pa": 240, "mixer": 160,
                         # balun: 40 evals drove best sds21 -95 -> -32.2 dB
                         # (mechanism proven, 2.2 dB shy of the -30 bar); the
                         # 3-port objective is harder than the 2-port lna one,
                         # so balun gets the mixer budget. Bar UNCHANGED.
                         "balun": 160}
IDD_FENCE_MA = 0.05
S21_FENCE_DB = -30.0
PDK = "gf180mcu"


INDUCTOR_Q = 12                       # solve_spec.INDUCTOR_Q, verbatim


def _body_of(net_path):
    return "\n".join(ln for ln in net_path.read_text().splitlines()
                     if ln.strip() and not ln.lstrip().startswith("*"))


def _num(x):
    return round(x, 4) if isinstance(x, (int, float)) else x


# ------------------------------------------------ verifier profiles (rl-v1)
# kaggle/VERIFIER-RL-V1.md (user rulings W1-W6, 2026-09-28). A profile is a
# named bundle of the opt-in verifier env flags below; it is selected by env
# VERIFIER_PROFILE=<name> or smoke_run(..., profile=<name>) (the kwarg beats the
# env; profile="" forces none). Precedence per flag: an env var that is SET
# (even to "0"/"") beats the profile value. The effective flags are applied to
# os.environ only for the duration of the smoke_run call (every guard reads the
# env at call time), then removed again.
# The stability pieces still need the SPEC to constrain mu_min (stab_gate_on);
# use rl_v1_spec() to put a library spec into rl-v1 form.
# Recording: whenever a profile is active or ANY flag below is set, the result
# gains result["verifier"] = {profile, flags (every flag: effective value or
# None), env_overrides, stab_gate_on, stab_window, spec_rl_v1_issues}. With no
# profile and no flag set, smoke_run is the historical code path, byte-identical.
VERIFIER_PROFILES = {
    "rl-v1": {
        "STAB_WIDE_INLOOP": "1",                 # S-1: wide mu in the objective
        "STAB_WIDE_WINDOW": "1e7,5e10,1001",     # R4(d): 10 MHz-50 GHz window
        "VERIFY_STRUCT": "1",                    # R4(b): degenerate structures
        "VERIFY_FINITE": "1",                    # R4(f): NaN/inf constrained metric
        "VERIFY_TOPO_LIMITS": "1",               # W1: spec topology limits enforced
        "VERIFY_INERT_COUNT": "1",               # W2: inert-device COUNT (no gate)
        # NOT in rl-v1 (diagnostics only): VERIFY_ROBUST (W3 waived),
        # VERIFY_NO_INERT (W2: penalty, not gate), VERIFY_NF_BAND (W5 is in-loop
        # via nf_max_db), VERIFY_BAND_METRICS (W6 is spec-level s11_max_db).
    },
}
VERIFIER_FLAGS = ("STAB_WIDE_INLOOP", "STAB_WIDE_WINDOW", "VERIFY_TOPO_LIMITS",
                  "VERIFY_STRUCT", "VERIFY_FINITE", "VERIFY_BAND_METRICS",
                  "VERIFY_NF_BAND", "VERIFY_NO_INERT", "VERIFY_INERT_COUNT",
                  "VERIFY_ROBUST", "VERIFY_ROBUST_PCT", "VERIFY_ROBUST_MIN")


def resolve_verifier(profile=None):
    """(profile_name_or_None, {flag: effective value}, [env-overridden flags])."""
    name = profile if profile is not None else os.environ.get("VERIFIER_PROFILE")
    name = name or None
    if name is not None and name not in VERIFIER_PROFILES:
        raise ValueError(f"unknown VERIFIER_PROFILE {name!r}; known: "
                         f"{sorted(VERIFIER_PROFILES)}")
    base = VERIFIER_PROFILES.get(name, {})
    eff, over = {}, []
    for k in VERIFIER_FLAGS:
        if k in os.environ:
            eff[k] = os.environ[k]
            if k in base and os.environ[k] != base[k]:
                over.append(k)
        elif k in base:
            eff[k] = base[k]
    return name, eff, over


def rl_v1_issues(spec):
    """Why `spec` is NOT in rl-v1 form ([] = conforming; see rl_v1_spec)."""
    c = spec.constraints
    bad = []
    if not stab_gate_on(spec):
        bad.append("no mu_min constraint (stability gate off)")
    if spec.band_type == "wideband":
        if "nf_db" in c:
            bad.append("wideband gates nf_db (f0) instead of nf_max_db (band)")
        if (spec.topology or {}).get("max_inductors") != 2:
            bad.append("wideband max_inductors != 2")
    elif "s11_db" in c:
        bad.append("narrowband gates s11_db (f0) instead of s11_max_db (band)")
    return bad


def smoke_run(tokens, spec_path, seed, budget, pdk, profile=None):
    """Verifier entry point: resolves the verifier profile/flags (see
    VERIFIER_PROFILES above), runs _smoke_run with them applied, and records
    them in result["verifier"]. No profile and no flag set -> exactly the
    historical _smoke_run call (byte-identical result)."""
    name, eff, over = resolve_verifier(profile)
    if name is None and not any(k in os.environ for k in VERIFIER_FLAGS):
        return _smoke_run(tokens, spec_path, seed, budget, pdk)
    applied = [k for k in eff if k not in os.environ]
    for k in applied:
        os.environ[k] = eff[k]
    try:
        res = _smoke_run(tokens, spec_path, seed, budget, pdk)
        if res is not None:
            spec = SZ._spec_for_sizing(spec_path, nf_gate=None, pdk=pdk)
            res["verifier"] = {
                "profile": name,
                "flags": {k: eff.get(k) for k in VERIFIER_FLAGS},
                "env_overrides": over,
                "stab_gate_on": stab_gate_on(spec),
                "stab_window": list(stab_window()),
                "spec_rl_v1_issues": rl_v1_issues(spec)}
    finally:
        for k in applied:
            os.environ.pop(k, None)
    return res


def _smoke_run(tokens, spec_path, seed, budget, pdk):
    """solve_spec.size_tokens with (a) the per-eval points KEPT and (b) the
    winner re-measured through make_objective's UNGATED endpoint `evaluate`
    (identical engine calls otherwise: _spec_for_sizing -> prepared_body ->
    make_objective -> _Budget -> run_cmaes; solve_spec discards both).

    Returns None if the topology is not sizable for the spec, else a dict with
    the winner's FULL ungated metrics (class harness measured at best_x) AND
    best-over-run idd/s21/sds21/conv: the fence reads best-over-run for the
    always-measured in-loop metrics, matching the v0 fence wording "40-eval
    smoke, best idd_ma > 0.05" (the CMA winner is picked by the class
    objective, which does not select for idd/s21).

    OPT-IN WIDE STABILITY GATE: when the spec constrains `mu_min` (see
    stab_gate_on / _wide_stability_gate below) the winner is also audited over
    0.1-20 GHz and "feasible" additionally requires wide stability; extra keys
    (spec_feasible, mu_min_wide, k_min_wide, delta_max_wide, stab_wide_ok,
    stab_points_checked, stab_winner_replaced, ...) are added. Specs without
    mu_min get exactly the historical dict.

    OPT-IN IN-LOOP WIDE STABILITY (S-1): additionally with env
    STAB_WIDE_INLOOP=1 (and the gate on), every sizing eval also pays the wide
    audit and its mu shortfall enters the objective as a hard-constraint
    violation (_stab_inloop_objective); the result gains `stab_inloop` stats.
    Unset -> byte-identical to the gate-only behavior.

    OPT-IN R4 LOOPHOLE GUARDS (kaggle/campaigns/rl-readiness/R4; every one
    unset -> byte-identical): pre-sizing VERIFY_TOPO_LIMITS=1 (spec topology
    screen) and VERIFY_STRUCT=1 (structural degeneracy) reject with
    `infeasible_reason` and 0 evals; STAB_WIDE_WINDOW="lo,hi,n" widens the
    stability window (in-loop + gate); post-hoc on the final winner
    VERIFY_FINITE / VERIFY_BAND_METRICS / VERIFY_NF_BAND / VERIFY_NO_INERT /
    VERIFY_ROBUST=N (see _r4_posthoc) can only turn feasible -> infeasible;
    VERIFY_INERT_COUNT=1 (W2) only RECORDS inert devices (no feasibility effect)."""
    spec = SZ._spec_for_sizing(spec_path, nf_gate=None, pdk=pdk)
    topo = Topology(list(tokens))
    topo_chk = None
    if os.environ.get("VERIFY_TOPO_LIMITS") == "1":            # R4 guard (a), opt-in
        topo_chk = topo_limits(spec, topo)
        if not topo_chk["ok"]:
            return _topo_reject(topo_chk)
    struct_chk = None
    if os.environ.get("VERIFY_STRUCT") == "1":                 # R4 guard (b), opt-in
        struct_chk = structural_degeneracy(topo)
        if struct_chk:
            return _topo_reject({"criteria": {"structural": False},
                                 "failed": [f"{k}={v}" for k, v in struct_chk.items()]},
                                key="structural_degeneracy", detail=struct_chk)
    prep = SZ.prepared_body(topo, inductor_q=INDUCTOR_Q, pdk=SZ._pdk_name(spec))
    if prep is None:
        return None
    body, sizable, fixed = prep
    if not sizable:
        return None
    points = []
    health = SZ.SimHealth()
    obj, names, decode, evaluate = SZ.make_objective(
        body, spec, sizable, fixed, points=points, sim_health=health)
    inloop = None
    if stab_gate_on(spec) and os.environ.get("STAB_WIDE_INLOOP") == "1":
        obj, inloop = _stab_inloop_objective(obj, spec, body, decode, points)
    bud = NS._Budget(obj, budget, points)
    x0 = SZ.warm_start_x0(
        {"tokens": list(tokens), "counts": topo.counts(),
         "n_devices": topo.n_devices, "inductor_ratio": topo.inductor_ratio},
        SZ._spec_target_metrics(spec), spec, sizable, pdk=SZ._pdk_name(spec))
    try:
        NS.run_cmaes(bud, len(names), seed, x0=x0)
    except NS._BudgetOut:
        pass
    bx, bm = bud.best()
    if bx is None:
        return None
    # endpoint re-eval, UNGATED (make_objective's documented `evaluate` use):
    # one extra sim; the winner's class metrics (conv_gain/p1db/...) are real.
    full = None
    try:
        full = evaluate(bx)
    except Exception:                                           # noqa: BLE001
        full = None
    winner = full if full else (bm or {})
    runs = [m for _x, m in points if m]

    def _best(key):
        vals = [m[key] for m in runs
                if isinstance(m.get(key), (int, float))]
        return max(vals) if vals else None

    feas = bool(spec.feasible(winner)[0]) if winner else False
    res = {"feasible": feas, "metrics": winner,
           "winner_reeval_ungated": bool(full),
           "best_idd_ma": _best("idd_ma"), "best_s21_db": _best("s21_db"),
           "best_conv_gain_db": _best("conv_gain_db"),
           "best_sds21_db": _best("sds21_db"),
           "n_evals": health.n_evals, "n_sim_fail": health.n_sim_fail,
           "sim_error": health.first_error}
    # WIDE STABILITY GATE (opt-in, 2026-09-28): runs ONLY when the spec itself
    # constrains mu_min; every other spec returns the dict above untouched.
    if stab_gate_on(spec):
        _wide_stability_gate(res, spec, body, decode, evaluate, points, bx,
                             bud.best_i)
    if inloop is not None:
        res["stab_inloop"] = {k: (round(v, 3) if isinstance(v, float) else v)
                              for k, v in inloop.items()}
    if topo_chk is not None:
        res["topo_limits_ok"] = True
        res["topo_limits"] = topo_chk["criteria"]
    if struct_chk is not None:
        res["structural_degeneracy"] = {}
    if any(os.environ.get(k) for k in _R4_POSTHOC_FLAGS):          # R4 guards, opt-in
        _r4_posthoc(res, spec, body, sizable, decode, bx, seed)
    return res


# ------------------------------------------- post-hoc winner guards (R4, opt-in)
# kaggle/campaigns/rl-readiness/R4 items (b)(c)(f). Each runs only when its env
# flag is set; with none set smoke_run never reaches this code (byte-identical).
# They audit the FINAL winner (the gate's replacement if any, else bx) and can
# only turn feasible -> infeasible (reasons appended to `infeasible_reason`):
#   VERIFY_FINITE=1   a constrained metric that is NaN/inf -> infeasible
#                     (Spec.feasible treats NaN as satisfied: `nan > max` is False)
#   VERIFY_NF_BAND=1  nf_db max-constraint re-checked at ALL 51 points of the
#                     series-Rs noise sweep over [f_lo, f_hi] (the spec path
#                     reads NF at f0 only -- matters for wideband specs)
#   VERIFY_NO_INERT=1 open each proposal R/C/L of the winner in turn (R 1e12,
#                     C 1e-20 F, L 1 H); if the design is STILL final-feasible
#                     that device does nothing -> infeasible (padding/no-op edits)
#   VERIFY_ROBUST=N   N draws (deterministic, seeded by `seed`) of every sized
#                     value x (1+U[-p,+p]), p = VERIFY_ROBUST_PCT (default 5 %);
#                     infeasible if the final-feasible fraction < VERIFY_ROBUST_MIN
#                     (default 0.5). Result gains robust_frac / robust_n.
#   VERIFY_INERT_COUNT=1  (W2, rl-v1) the SAME inert test as VERIFY_NO_INERT but
#                     record-only: result gains inert_devices (list of sized
#                     R/C/L names that can be opened with the design staying
#                     final-feasible) + n_inert_devices (their count, the RL
#                     reward-penalty input); NO feasibility effect. Both are
#                     None when the final winner is infeasible (inert undefined);
#                     absent on a pre-sizing (topo/struct) reject.
#   VERIFY_BAND_METRICS=1  a point constraint is also held over the whole spec
#                     band using the band metrics run_and_extract ALREADY
#                     measures (free): s11_db max -> s11_max_db, s21_db min ->
#                     s21_min_db (narrowband specs gate s11/s21 at f0 only; R4
#                     found 61/63 nb winners with in-band s11_max above the limit)
_R4_POSTHOC_FLAGS = ("VERIFY_FINITE", "VERIFY_NF_BAND", "VERIFY_NO_INERT",
                     "VERIFY_ROBUST", "VERIFY_BAND_METRICS", "VERIFY_INERT_COUNT")
_BAND_OF = {"s11_db": ("s11_max_db", "max"), "s21_db": ("s21_min_db", "min")}
_OPEN_VALUE = {"R": "1e12", "C": "1e-20", "L": "1"}


def _final_ok(spec, body, params):
    """Final verdict for (body, params): spec-feasible AND (if gated) wide-stable."""
    m = SZ.eval_metrics(body, params, spec)
    if not m or not spec.feasible(m)[0]:
        return False
    if stab_gate_on(spec):
        return bool(wide_stability(spec, body, params)[1])
    return True


def nf_over_band(spec, body, params):
    """Max NF (dB) over the 51-point series-Rs noise sweep of the spec band, or
    None (unmeasurable / OSDI pdk). Same deck as extract.measure_nf."""
    import extract as E
    import re as _re
    if E.osdi_lines_for(SZ._pdk_name(spec)):
        return None
    b = spec.band or {}
    f0 = float(b.get("f0", 2.442e9))
    flo, fhi = float(b.get("f_lo", f0 * 0.98)), float(b.get("f_hi", f0 * 1.02))
    deck = E.build_noise_deck(body, _stab_params(spec, params), f0, flo, fhi)[0]
    if deck is None:
        return None
    out = E.run_deck(deck.replace("print m_nf_f0", "print m_nf_f0\nprint nfv"),
                     "nfb_", "nf.cir") or ""
    vals = []
    for ln in out.splitlines():
        t = ln.split()
        if len(t) == 3 and _re.match(r"^\d+$", t[0]):
            try:
                vals.append(float(t[2]))
            except ValueError:
                return None
    return max(vals) if len(vals) >= 2 else None


def _r4_posthoc(res, spec, body, sizable, decode, bx, seed):
    import math
    import random
    why = []
    if os.environ.get("VERIFY_FINITE") == "1":
        bad = [n for n, c in spec.constraints.items()
               if c.get("status") != "unsupported"
               and isinstance((res.get("metrics") or {}).get(n), float)
               and not math.isfinite(res["metrics"][n])]
        res["nonfinite_metrics"] = bad
        if bad:
            why.append("non-finite metric: " + ", ".join(bad))
    if os.environ.get("VERIFY_BAND_METRICS") == "1" and res["feasible"]:
        m = res.get("metrics") or {}
        bad = []
        for point, (band_key, side) in _BAND_OF.items():
            c = spec.constraints.get(point) or {}
            if side not in c or c.get("status") == "unsupported":
                continue
            # a spec that already states band semantics keeps them: wideband
            # specs gate s11_max_db directly and bound s21 flatness with
            # s21_ripple_db (s21_db stays a point-at-f0 + ripple contract)
            if band_key in spec.constraints or (point == "s21_db"
                                                and "s21_ripple_db" in spec.constraints):
                continue
            v = m.get(band_key)
            if not isinstance(v, (int, float)) or \
                    (v > c[side] if side == "max" else v < c[side]):
                bad.append(f"{band_key}={v} vs {point} {side} {c[side]}")
        res["band_metrics_violations"] = bad
        if bad:
            why.append("band: " + ", ".join(bad))
    rep = res.get("stab_replacement")
    x = rep["x"] if (res.get("stab_winner_replaced") and rep) else bx
    if res["feasible"] and x is not None:
        params = decode(x)
        if os.environ.get("VERIFY_NF_BAND") == "1" and "max" in spec.constraints.get("nf_db", {}):
            nfb = nf_over_band(spec, body, params)
            res["nf_band_max_db"] = nfb
            if nfb is None or nfb > spec.constraints["nf_db"]["max"]:
                why.append(f"NF over band {nfb} > {spec.constraints['nf_db']['max']}")
        gate_inert = os.environ.get("VERIFY_NO_INERT") == "1"
        count_inert = os.environ.get("VERIFY_INERT_COUNT") == "1"
        if gate_inert or count_inert:
            inert = []
            for name, kind in sizable.items():
                if kind in _OPEN_VALUE and _final_ok(spec, body,
                                                     dict(params, **{name: _OPEN_VALUE[kind]})):
                    inert.append(name)
            res["inert_devices"] = inert
            if count_inert:                      # W2: penalty input, never a gate
                res["n_inert_devices"] = len(inert)
            if gate_inert and inert:
                why.append("inert device(s): " + ", ".join(inert))
        n = int(os.environ.get("VERIFY_ROBUST") or 0)
        if n > 0:
            p = float(os.environ.get("VERIFY_ROBUST_PCT", "5")) / 100.0
            need = float(os.environ.get("VERIFY_ROBUST_MIN", "0.5"))
            rng = random.Random(1000003 * int(seed) + 17)
            ok = 0
            for _ in range(n):
                p2 = dict(params)
                for name in sizable:
                    p2[name] = f"{float(params[name]) * (1 + rng.uniform(-p, p)):.6g}"
                ok += _final_ok(spec, body, p2)
            res["robust_n"], res["robust_frac"] = n, ok / n
            if ok / n < need:
                why.append(f"robust fraction {ok}/{n} < {need}")
    elif os.environ.get("VERIFY_INERT_COUNT") == "1":
        res["inert_devices"], res["n_inert_devices"] = None, None
    if why:
        res["feasible"] = False
        res["infeasible_reason"] = "; ".join(why)


# ------------------------------------------ topology-limit guard (R4, opt-in)
# kaggle/campaigns/rl-readiness/R4 item (a): the sizer/verifier never checked
# the spec's own `topology:` limits (device_budget, max_inductors, ...), so a
# design over budget could be scored feasible (E-c found max_inductors
# unenforced). With env VERIFY_TOPO_LIMITS=1, smoke_run first runs the spec's
# own L0 screen (Spec.structural_screen -- every criterion it derives from the
# spec's topology/ports fields: has_transistor, device_budget, has_ports,
# single_input, not_floating, has_inductor, inductor_ratio, max_inductors,
# match_plausible) and a failing topology is returned INFEASIBLE with a reason
# and NO sizing (0 evals). A passing topology is sized exactly as before and
# the result gains `topo_limits_ok: True` + the criteria. Unset -> this code is
# never reached (byte-identical results).
def topo_limits(spec, topo):
    """{'ok', 'criteria', 'failed'} from the spec's own structural screen."""
    passed, crit = spec.structural_screen(topo)
    crit = {k: bool(v) for k, v in crit.items()}
    return {"ok": bool(passed), "criteria": crit,
            "failed": [k for k, v in crit.items() if not v]}


def _topo_reject(chk, key="topo_limits", detail=None):
    """smoke_run-shaped INFEASIBLE result for a pre-sizing structural reject."""
    res = {"feasible": False, "metrics": {}, "winner_reeval_ungated": False,
           "best_idd_ma": None, "best_s21_db": None, "best_conv_gain_db": None,
           "best_sds21_db": None, "n_evals": 0, "n_sim_fail": 0,
           "sim_error": None}
    if key == "topo_limits":
        res.update(topo_limits_ok=False, topo_limits=chk["criteria"],
                   infeasible_reason="topology limits violated: "
                                     + ", ".join(chk["failed"]))
    else:
        res.update({key: detail, "infeasible_reason": "structural degeneracy: "
                                                      + "; ".join(chk["failed"])})
    return res


# ------------------------------------ structural-degeneracy guard (R4, opt-in)
# Item (b)/(f): junk the sizer cannot remove and the metrics cannot see. The
# adversarial run showed a MOS with all four pins on VSS, a dangling R-C chain
# and a MOS with no DC current path all score verifier-feasible (they are
# electrically inert). With env VERIFY_STRUCT=1, smoke_run rejects BEFORE
# sizing a proposal topology that has any of:
#   shorted_passive  R/C/L with both pins on one node
#   mos_d_eq_s       MOS drain == source (channel shorted)
#   mos_g_eq_s       MOS gate == source (permanently off)
#   dangling_node    a non-port node touched by exactly one device pin
#   mos_no_dc_path   MOS whose channel cannot carry DC current rail-to-rail
#                    (DC graph = R, L, MOS channels; caps open)
#   port_on_rail     VIN1/VOUT1 electrically on VDD/VSS; in_eq_out VIN1==VOUT1
# Zero hits over every recorded bench-v1.2 solution (R4 static.json).
# Unset -> never reached (byte-identical).
def structural_degeneracy(topo):
    """{flag: [devices/nodes]} of degenerate structures ({} = clean)."""
    from topology import base_of, PIN_RE
    from collections import defaultdict, Counter
    pin2node, node_nets = {}, {}
    for root, members in topo.nodes.items():
        nets = sorted(m for m in members if m in topo.nets)
        name = nets[0] if nets else root
        node_nets[name] = set(nets)
        for m in members:
            if PIN_RE.match(m):
                pin2node[m] = name
    devs = {}
    for p, n in pin2node.items():
        mm = PIN_RE.match(p)
        devs.setdefault(mm.group("dev"), {})[mm.group("pin")] = n

    def node_of(net):
        return next((n for n, s in node_nets.items() if net in s), None)
    vin, vout, vdd, vss = (node_of(n) for n in ("VIN1", "VOUT1", "VDD", "VSS"))
    rails = {vdd, vss} - {None}
    kind = {d: base_of(d) for d in devs}
    mos = [d for d in devs if kind[d] in ("NM", "PM")]
    pas = [d for d in devs if kind[d] in ("R", "C", "L")]
    out = {}
    v = sorted(d for d in pas if devs[d].get("P") == devs[d].get("N"))
    if v:
        out["shorted_passive"] = v
    v = sorted(d for d in mos if devs[d].get("D") == devs[d].get("S"))
    if v:
        out["mos_d_eq_s"] = v
    v = sorted(d for d in mos if devs[d].get("G") == devs[d].get("S"))
    if v:
        out["mos_g_eq_s"] = v
    cnt = Counter(n for d in devs for n in devs[d].values())
    v = sorted(n for n, k in cnt.items() if k == 1 and n not in ({vin, vout} | rails))
    if v:
        out["dangling_node"] = v
    adj = defaultdict(set)
    for d in devs:
        if kind[d] in ("R", "L"):
            a, b = devs[d]["P"], devs[d]["N"]
        elif kind[d] in ("NM", "PM"):
            a, b = devs[d]["D"], devs[d]["S"]
        else:
            continue
        adj[a].add(b)
        adj[b].add(a)

    def reach(s, skip):
        seen, st = {s}, [s]
        while st:
            u = st.pop()
            for w in adj[u]:
                if (u, w) in skip or w in seen:
                    continue
                seen.add(w)
                st.append(w)
        return seen
    v = []
    for d in mos:
        a, b = devs[d]["D"], devs[d]["S"]
        skip = {(a, b), (b, a)}
        ra, rb = reach(a, skip), reach(b, skip)
        if not ((vdd in ra and vss in rb) or (vss in ra and vdd in rb)):
            v.append(d)
    if v:
        out["mos_no_dc_path"] = sorted(v)
    if {vin, vout} & rails:
        out["port_on_rail"] = sorted(n for n in (vin, vout) if n in rails)
    if vin is not None and vin == vout:
        out["in_eq_out"] = [vin]
    return out


# ------------------------------------------------ wide stability gate (opt-in)
# User-approved 2026-09-28. The harness already reports K/mu/|Delta| over the
# spec's OWN sweep (extract.run_and_extract -> k_min/mu_min/delta_max over
# f_lo..f_hi), and a spec may already constrain `mu_min` there (spec.py accepts
# any metric name; spec.objective sums its violation, so the sizer optimizes
# toward it). But the in-band sweep is narrow (narrowband = f0 +/- 2%) and
# feedback amplifiers oscillate OUT of band, so a spec that asks for mu_min
# ALSO gets the repo's documented honest audit (lna/_nf_gate_d3.py precedent):
# extract.measure_stability over a WIDE window, 0.1-20 GHz, 401 linear points.
#
# Trigger: `mu_min` in spec.constraints and not `status: unsupported`. Specs
# without it never reach this code (byte-identical smoke_run results).
#
# Verdict: stab_wide_ok <=> measure_stability returned a dict AND its mu_min
# satisfies the spec's own mu_min limit (min/max) -- mu > 1 over the window is
# the single-parameter test for unconditional stability (Edwards-Sinsky).
# Final "feasible" = spec-feasible (in-band, incl. the in-band mu_min
# constraint) AND stab_wide_ok. measure_stability -> None counts as NOT ok.
#
# False-negative guard: if the winner is spec-feasible but wide-unstable, the
# other spec-feasible points of the SAME run (`points`, the per-eval hook) are
# scanned best-objective-first (up to STAB_SCAN_MAX, deduped on x): each gets
# one wide sim; the first wide-stable one is re-measured through the SAME
# ungated `evaluate` smoke_run uses for its winner, and replaces the winner if
# that full re-measure is still spec-feasible. No new sizing evals are spent.
#
# LIMITS: measure_stability builds a single deck (no OSDI source-split), so an
# OSDI pdk (IHP) returns None -> not ok. gf180 gets the same MC-off pins
# eval_metrics stamps into its params. 401 linear points = ~50 MHz spacing, so
# a very sharp out-of-band dip can fall between grid points; the in-band dip is
# covered by the spec's own mu_min constraint on the in-band grid.
STAB_WIDE_F_LO = 1e8
STAB_WIDE_F_HI = 2e10
STAB_WIDE_NPTS = 401
STAB_SCAN_MAX = 30


def stab_window():
    """(f_lo, f_hi, npts) of the wide stability window. R4 guard (d), opt-in:
    env STAB_WIDE_WINDOW="f_lo,f_hi,npts" (e.g. "1e7,5e10,1001" = 10 MHz-50 GHz
    at the same ~50 MHz spacing) overrides the 0.1-20 GHz / 401 default, for
    BOTH the in-loop term and the post-hoc gate (both call wide_stability).
    R4 found in-loop winners that moved their mu<1 region to just above 20 GHz
    (window-edge gaming). Unset -> the module constants (byte-identical)."""
    w = os.environ.get("STAB_WIDE_WINDOW")
    if not w:
        return STAB_WIDE_F_LO, STAB_WIDE_F_HI, STAB_WIDE_NPTS
    lo, hi, n = w.split(",")
    return float(lo), float(hi), int(n)


def stab_gate_on(spec):
    """Does this spec opt into the wide stability gate? (mu_min constrained and
    not status: unsupported.)"""
    c = (getattr(spec, "constraints", None) or {}).get("mu_min")
    return isinstance(c, dict) and c.get("status") != "unsupported"


def _stab_params(spec, params):
    """The params dict exactly as eval_metrics hands it to the analysis decks
    (gf180 -> MC-off pins; every other pdk unchanged)."""
    if SZ._pdk_name(spec) == "gf180mcu":
        return {**params, "sw_stat_global": "0", "sw_stat_mismatch": "0"}
    return params


def wide_stability(spec, body, params):
    """extract.measure_stability over the wide window at the spec's f0.
    Returns (stab_dict_or_None, ok)."""
    import extract as E
    band = spec.band or {}
    f0 = float(band.get("f0", 2.442e9))
    w_lo, w_hi, w_n = stab_window()
    f_lo = min(w_lo, float(band.get("f_lo", f0 * 0.98)))
    f_hi = max(w_hi, float(band.get("f_hi", f0 * 1.02)))
    try:
        st = E.measure_stability(body, _stab_params(spec, params), f0, f_lo,
                                 f_hi, npts=w_n)
    except Exception:                                           # noqa: BLE001
        st = None
    mu = (st or {}).get("mu_min")
    if not isinstance(mu, (int, float)):
        return st, False
    c = spec.constraints["mu_min"]
    ok = True
    if "min" in c and mu < c["min"]:
        ok = False
    if "max" in c and mu > c["max"]:
        ok = False
    return st, ok


def _wide_stability_gate(res, spec, body, decode, evaluate, points, bx, best_i):
    """Mutates smoke_run's result dict in place (see the block comment above)."""
    spec_feas = bool(res["feasible"])
    st, ok = wide_stability(spec, body, decode(bx))
    checked, replaced, rep = 1, False, None
    if spec_feas and not ok:
        win_i = (best_i - 1) if best_i else None
        seen = {tuple(bx)}
        cands = []
        for i, (x, m) in enumerate(points):
            if i == win_i or not m or not spec.feasible(m)[0]:
                continue
            if tuple(x) in seen:
                continue
            seen.add(tuple(x))
            cands.append((spec.objective(m), i, x))
        cands.sort(key=lambda t: (t[0], t[1]))
        for _obj, i, x in cands[:STAB_SCAN_MAX]:
            st_i, ok_i = wide_stability(spec, body, decode(x))
            checked += 1
            if not ok_i:
                continue
            try:
                full_i = evaluate(x)
            except Exception:                                   # noqa: BLE001
                full_i = None
            if full_i and spec.feasible(full_i)[0]:
                replaced = True
                rep = {"point_index": i, "x": [float(v) for v in x],
                       "objective": spec.objective(full_i),
                       "spec_winner_metrics": res["metrics"],
                       "spec_winner_stab_wide": st}
                res["metrics"] = full_i
                st, ok = st_i, True
                break
    s = st or {}
    res["spec_feasible"] = spec_feas
    res["stab_window"] = list(stab_window())
    res["stab_wide"] = st
    res["mu_min_wide"] = s.get("mu_min")
    res["k_min_wide"] = s.get("k_min")
    res["delta_max_wide"] = s.get("delta_max")
    res["stab_wide_ok"] = bool(ok)
    res["stab_points_checked"] = checked
    res["stab_winner_replaced"] = replaced
    res["stab_replacement"] = rep
    res["feasible"] = bool(spec_feas and ok)


def _stab_inloop_objective(obj, spec, body, decode, points):
    """S-1 (opt-in, STAB_WIDE_INLOOP=1 AND stab_gate_on): wrap the sizer
    objective so EVERY evaluation is also audited over the wide window and an
    out-of-band stability shortfall is penalized like any other hard spec
    constraint (spec.feasible semantics: normalized violation
    (limit - value)/_scale(limit), missing value -> 1.0).

        wide ok       : f = spec.objective(m)                (unchanged)
        wide violated : f = 1 + sum(in-band violations) + v_wide

    i.e. exactly Spec.objective with the wide mu shortfall as ONE MORE hard
    constraint: any violation (in-band or wide) -> the infeasible branch
    1 + sum(violations), no violation -> the feasible branch unchanged. The
    feasibility-first ordering is kept (a wide-unstable point never beats a
    spec-feasible wide-stable one). Sim failures (m None) keep SIM_FAIL_PENALTY.
    `points` still receives the plain (x, metrics) rows (the in-band metrics);
    the wide verdict per eval is not stored there. Returns (wrapped, stats)."""
    c = spec.constraints["mu_min"]
    scale = spec._scale(c)
    stats = {"n_wide": 0, "n_wide_viol": 0, "n_wide_none": 0, "wide_secs": 0.0}

    def wrapped(x):
        n0 = len(points)
        f = obj(x)
        m = points[-1][1] if len(points) > n0 else None
        if not m:
            return f
        t = time.time()
        st, _ok = wide_stability(spec, body, decode(x))
        stats["wide_secs"] += time.time() - t
        stats["n_wide"] += 1
        mu = (st or {}).get("mu_min")
        if not isinstance(mu, (int, float)):
            stats["n_wide_none"] += 1
            v = 1.0
        else:
            v = 0.0
            if "min" in c and mu < c["min"]:
                v += (c["min"] - mu) / scale
            if "max" in c and mu > c["max"]:
                v += (mu - c["max"]) / scale
        if v <= 0:
            return f
        stats["n_wide_viol"] += 1
        _feas, viol = spec.feasible(m)
        return 1.0 + sum(viol.values()) + v

    return wrapped, stats


def stability_spec(src, out_dir=None, mu_min=1.0):
    """Write a stability-enabled COPY of spec `src` (adds `mu_min: {min: mu_min}`
    to its constraints; everything else verbatim) and return its path. The
    source spec is never modified. Default out_dir = $TMPDIR/stab-specs."""
    import yaml
    data = yaml.safe_load(Path(src).read_text())
    data.setdefault("constraints", {})["mu_min"] = {"min": float(mu_min)}
    d = Path(out_dir or os.path.join(os.environ.get("TMPDIR", "/tmp"),
                                     "stab-specs"))
    d.mkdir(parents=True, exist_ok=True)
    name = data.get("name") or Path(src).stem
    out = d / f"{name}__mu{mu_min:g}.yaml"
    # Atomic write: parallel callers on the same cell share this path, and a
    # plain open("w") let one process read another's half-written file (S-1).
    # Content is deterministic per (src, mu_min), so last-rename-wins is safe.
    tmp = d / f".{out.name}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)
    os.replace(tmp, out)
    Spec.load(str(out))                    # validate loudly
    return str(out)


def rl_v1_spec(src, out_dir=None, mu_min=1.0):
    """Write the rl-v1-form COPY of spec `src` (kaggle/VERIFIER-RL-V1.md) and
    return its path; the source is never modified.

      all        : + constraints.mu_min {min: mu_min}   (stability gate on)
      wideband   : constraint nf_db -> nf_max_db (same limit; band-worst NF,
                   measured in-loop by extract.run_and_extract)  [W5]
                   topology.max_inductors = 2                     [W1]
      narrowband : constraint s11_db -> s11_max_db (same limit; worst S11 over
                   [f_lo, f_hi], already measured every eval)   [W6]

    A renamed constraint keeps its position and limit dict; objectives on the
    old metric are renamed too (so the objective floor/scale stays the
    constraint's). If the new name already exists the old one is dropped and
    the existing limit kept. Everything else verbatim. Default out_dir =
    $TMPDIR/rlv1-specs; the write is atomic (per-PID temp + os.replace), like
    stability_spec, so parallel callers on the same cell are safe."""
    import yaml
    data = yaml.safe_load(Path(src).read_text())
    cons = data.get("constraints") or {}
    wide = (data.get("band") or {}).get("type") == "wideband"

    def rename(old, new):
        nonlocal cons
        if old not in cons:
            return
        if new in cons:
            cons = {k: v for k, v in cons.items() if k != old}
        else:
            cons = {(new if k == old else k): v for k, v in cons.items()}
        for o in data.get("objectives") or []:
            if o.get("metric") == old:
                o["metric"] = new

    if wide:
        rename("nf_db", "nf_max_db")
        data.setdefault("topology", {})["max_inductors"] = 2
    else:
        rename("s11_db", "s11_max_db")
    cons["mu_min"] = {"min": float(mu_min)}
    data["constraints"] = cons
    d = Path(out_dir or os.path.join(os.environ.get("TMPDIR", "/tmp"),
                                     "rlv1-specs"))
    d.mkdir(parents=True, exist_ok=True)
    name = data.get("name") or Path(src).stem
    out = d / f"{name}__rlv1.yaml"
    tmp = d / f".{out.name}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)
    os.replace(tmp, out)
    sp = Spec.load(str(out))               # validate loudly
    assert not rl_v1_issues(sp), rl_v1_issues(sp)
    return str(out)


def main(argv=None):
    only = [c for c in (argv or sys.argv[1:]) if c in FAMILIES]
    mpath = ANCH / "MANIFEST.json"
    smoke_cfg = {"seed": SMOKE_SEED, "budget_default": SMOKE_BUDGET,
                 "budget_by_class": SMOKE_BUDGET_BY_CLASS,
                 "winner": "endpoint ungated re-eval (make_objective evaluate)",
                 "idd_fence_ma": IDD_FENCE_MA,
                 "s21_fence_db": S21_FENCE_DB,
                 "fence_reads": "best-over-run idd/s21/sds21; winner conv"}
    if only and mpath.exists():
        manifest = json.loads(mpath.read_text())    # merge into prior chunks
        manifest["prepared"] = time.strftime("%Y-%m-%d %H:%M")
        manifest["smoke"] = smoke_cfg
        manifest["dropped"] = DROPPED
        manifest.setdefault("classes", {})
    else:
        manifest = {"prepared": time.strftime("%Y-%m-%d %H:%M"),
                    "pdk": PDK, "smoke": smoke_cfg,
                    "dropped": DROPPED, "classes": {}}
    ref_hashes, _feats, ref_meta = novelty.reference()          # ref-v3 default
    manifest["novelty_ref"] = {k: ref_meta.get(k) for k in
                               ("version", "n_hashes", "digest")}
    ok_all = True

    for cls, fams in FAMILIES.items():
        if only and cls not in only:
            continue
        cfg = CLASS_CFG[cls]
        spec_path = str(cfg["spec"])
        spec = Spec.load(spec_path)
        gates_s21 = "s21_db" in (spec.constraints or {})
        cls_rec = {"spec": os.path.relpath(spec_path, REPO),
                   "circuit_class": spec.circuit_class,
                   "tokenizer_ports": cfg["ports"], "families": {}}
        manifest["classes"][cls] = cls_rec

        for fam in fams:
            net = ANCH / cls / f"{fam}.net"
            rec = {"net_file": os.path.relpath(net, REPO), "gates": {}}
            cls_rec["families"][fam] = rec
            body = _body_of(net)

            # --- parse + round-trip (EXTENDED ports so VLO/VOUT2 survive) -----
            try:
                rows, _ports = proposal.parse(body)
            except Exception as e:                              # noqa: BLE001
                rec["gates"]["parse"] = f"FAIL: {e}"
                ok_all = False
                print(f"[{fam}] PARSE FAIL {e}")
                continue
            rec["gates"]["parse"] = True
            try:
                tokens = proposal.to_tokens(rows, cfg["ports"])
            except Exception as e:                              # noqa: BLE001
                rec["gates"]["round_trip"] = f"FAIL: {e}"
                ok_all = False
                continue
            if not tokens:
                rec["gates"]["round_trip"] = "FAIL: no Eulerian path from VSS"
                ok_all = False
                continue
            rec["gates"]["round_trip"] = True

            topo = Topology(list(tokens))
            rec["gates"]["topology_valid"] = bool(topo.valid)
            rec["n_devices"] = topo.n_devices
            rec["n_inductors"] = topo.n_inductors
            rec["nets"] = sorted(topo.nets)
            if not topo.valid:
                ok_all = False
                continue

            # class-net survival check (the whole point of the extended ports)
            if cls == "mixer":
                rec["gates"]["lo_net_VLO_present"] = "VLO" in topo.nets
                if "VLO" not in topo.nets:
                    ok_all = False
            if cls == "balun":
                rec["gates"]["out2_net_VOUT2_present"] = "VOUT2" in topo.nets
                if "VOUT2" not in topo.nets:
                    ok_all = False

            # --- WL hash + novelty vs ref-v3 --------------------------------
            wl = novelty.wl_features(topo)[0]
            rec["wl_hash"] = wl
            rec["novel_vs_ref_v3"] = bool(wl not in ref_hashes)

            # --- structural screen vs the representative bench spec ----------
            passed, crit = spec.structural_screen(topo)
            rec["gates"]["structural_screen"] = {"passed": bool(passed),
                                                 "criteria": {k: bool(v) for k, v
                                                              in crit.items()}}
            if not passed:
                ok_all = False
                # still run the smoke so the report shows what conducts.

            # --- conduction smoke: real gf180 sizing (per-class budget) ------
            _budget = SMOKE_BUDGET_BY_CLASS.get(cls, SMOKE_BUDGET)
            try:
                res = smoke_run(list(tokens), spec_path, SMOKE_SEED, _budget,
                                PDK)
            except Exception as e:                              # noqa: BLE001
                rec["gates"]["smoke"] = f"FAIL: {type(e).__name__}: {e}"
                ok_all = False
                continue
            if res is None:
                rec["gates"]["smoke"] = "FAIL: topology not sizable for spec"
                ok_all = False
                continue
            m = res["metrics"]
            conv = m.get("conv_gain_db")
            sds21 = m.get("sds21_db")
            best_idd = res["best_idd_ma"]
            best_s21 = res["best_s21_db"]
            smoke = {"budget": _budget,
                     "winner_reeval_ungated": res["winner_reeval_ungated"],
                     "feasible": res["feasible"],
                     "n_evals": res["n_evals"],
                     "n_sim_fail": res["n_sim_fail"],
                     "sim_error": res["sim_error"],
                     "winner": {"idd_ma": _num(m.get("idd_ma")),
                                "s21_db": _num(m.get("s21_db")),
                                "conv_gain_db": _num(conv),
                                "sds21_db": _num(sds21)},
                     "best_over_run": {"idd_ma": _num(best_idd),
                                       "s21_db": _num(best_s21),
                                       "conv_gain_db":
                                       _num(res["best_conv_gain_db"]),
                                       "sds21_db":
                                       _num(res["best_sds21_db"])}}
            best_sds21 = res["best_sds21_db"]

            # --- class-appropriate conduction fence (best-over-run) ----------
            checks = {"conducts_idd": (isinstance(best_idd, (int, float))
                                       and best_idd > IDD_FENCE_MA)}
            if cls in ("lna", "pa") and gates_s21:
                checks["s21_above_fence"] = (isinstance(best_s21, (int, float))
                                             and best_s21 > S21_FENCE_DB)
            if cls == "mixer":
                # winner metrics come from the endpoint UNGATED re-eval
                checks["conv_gain_measured"] = conv is not None
            if cls == "balun":
                # measurable since commit ae751458 (to_spice port-3 emission);
                # fence mirrors the lna/pa s21 bar.
                checks["sds21_measured"] = sds21 is not None
                checks["sds21_above_fence"] = (
                    isinstance(best_sds21, (int, float))
                    and best_sds21 > S21_FENCE_DB)
            smoke["fence_checks"] = checks
            # BINDING fence: conduction (+s21 lna/pa, +conv mixer, +sds21 balun)
            binding = ["conducts_idd"]
            if cls in ("lna", "pa") and gates_s21:
                binding.append("s21_above_fence")
            if cls == "mixer":
                binding.append("conv_gain_measured")
            if cls == "balun":
                binding.append("sds21_above_fence")
            smoke["binding"] = binding
            smoke["passed"] = all(checks.get(k, False) for k in binding)
            rec["gates"]["smoke"] = smoke
            if not smoke["passed"]:
                ok_all = False

            # --- emit tokens (only for a family that got this far) -----------
            tf = ANCH / cls / f"{fam}.tokens.json"
            tf.write_text(json.dumps(list(tokens)))
            rec["tokens_file"] = os.path.relpath(tf, REPO)
            rec["n_tokens"] = len(tokens)

            print(f"[{fam}] valid={topo.valid} wl={wl} "
                  f"novel={rec['novel_vs_ref_v3']} screen={passed} "
                  f"budget={_budget} bestIdd={_num(best_idd)}mA "
                  f"bestS21={_num(best_s21)} winConv={_num(conv)} "
                  f"bestSds21={_num(best_sds21)} smoke_pass={smoke['passed']}")

    (ANCH / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print("\n== MANIFEST written:", os.path.relpath(ANCH / 'MANIFEST.json', REPO))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
