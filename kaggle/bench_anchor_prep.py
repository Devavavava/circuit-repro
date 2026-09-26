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


def smoke_run(tokens, spec_path, seed, budget, pdk):
    """solve_spec.size_tokens with (a) the per-eval points KEPT and (b) the
    winner re-measured through make_objective's UNGATED endpoint `evaluate`
    (identical engine calls otherwise: _spec_for_sizing -> prepared_body ->
    make_objective -> _Budget -> run_cmaes; solve_spec discards both).

    Returns None if the topology is not sizable for the spec, else a dict with
    the winner's FULL ungated metrics (class harness measured at best_x) AND
    best-over-run idd/s21/sds21/conv: the fence reads best-over-run for the
    always-measured in-loop metrics, matching the v0 fence wording "40-eval
    smoke, best idd_ma > 0.05" (the CMA winner is picked by the class
    objective, which does not select for idd/s21)."""
    spec = SZ._spec_for_sizing(spec_path, nf_gate=None, pdk=pdk)
    topo = Topology(list(tokens))
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
    return {"feasible": feas, "metrics": winner,
            "winner_reeval_ungated": bool(full),
            "best_idd_ma": _best("idd_ma"), "best_s21_db": _best("s21_db"),
            "best_conv_gain_db": _best("conv_gain_db"),
            "best_sds21_db": _best("sds21_db"),
            "n_evals": health.n_evals, "n_sim_fail": health.n_sim_fail,
            "sim_error": health.first_error}


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
