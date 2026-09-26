"""Golden: in-loop class-gate wiring (class-objective-v0, the anti-vacuous fence).

Program rule (same as check_pa/mixer/balun): the wiring is not trusted until this
is GREEN. Where check_pa/mixer/balun certify the HARNESSES in isolation, this
golden certifies that `lna/size.py::eval_metrics` -> `make_objective` actually
FEEDS those harness metrics to the objective and the feasibility check, for each
of the three RF classes, so a class cell can no longer be vacuously feasible.

WHAT IT PROVES, per class (pa / mixer / balun-lna):
  (a) PRESENCE -- a real ZOAF sizing (~20-40 evals) on a minimal conducting
      behavioral topology against a class-gated spec returns metrics that carry
      the class metric keys (pa: p1db_dbm/psat_dbm/pae_pct; mixer:
      conv_gain_db/lo_rf_iso_db/lo_if_iso_db; balun: sds21_db/cmrr_db/
      imbalance_amp_db/imbalance_phase_deg). If the harness were NOT wired into
      eval_metrics these keys would be absent (the pre-wiring state).
  (b) RESPONSE -- the objective BINDS on the class metric: an ABSURDLY strict
      class gate makes the sized point INFEASIBLE, while a TRIVIALLY loose gate on
      the SAME metric (everything else identical) makes it FEASIBLE. This is the
      anti-vacuous-feasibility check: feasibility must move when the class gate
      moves, which can only happen if the class metric is measured in-loop.

The topologies are minimal BEHAVIORAL decks (B-source / VCVS, no PDK, no BSIM) --
the same style the class goldens use -- so the runtime is dominated by the harness
transient/sp, not device convergence, and the whole golden stays well under
~2 min. The DUT bodies carry a sized `.param` so ZOAF has a real knob to turn;
the point of the golden is the WIRING, not a device model, so a behavioral DUT is
the honest minimal conductor (exactly as check_pa argues for its own reference).

BYTE-IDENTICAL lna path is fenced by check_ref/check_simhealth, NOT here; this
golden only exercises the three NEW class paths.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)

import iip3 as I                       # noqa: E402
import size as S                       # noqa: E402
from spec import Spec                  # noqa: E402


# ------------------------------------------------------- minimal conducting DUTs
# Each DUT is a to_spice-style body (portnum lines present) with ONE sized
# `.param` knob so make_objective has a real coordinate. Load/source element
# names avoid the harness's own injected names (Rload/Rif/Rmxsrc/Vt1/Vlo...) so
# the deck surgery never hits a duplicate-device bail-out.

# Sizing box for the behavioral knobs. The knobs are dimensionless behavioral
# gains, not device geometries, so the sizer's `R` kind (log-mapped, positive) is
# reused as a generic positive-scalar decoder over a small numeric range chosen so
# ZOAF explores the interesting regime for each DUT; `vb_v` (linear) decodes the
# balun leg gain. The values are NOT ohms/volts -- they are the .param the
# behavioral B-source/VCVS multiplies -- but the DECODER math (log/linear over a
# box) is identical, which is all make_objective needs.
_SIZING = {"w_um": [1, 400], "l_fixed": 45e-9,
           "r_ohm": [1.0, 10.0],        # behavioral gain knob (pGAIN / pK), log
           "c_f": [50e-15, 20e-12],
           "vb_v": [0.2, 0.9]}          # balun non-inverting leg gain, linear


def _pa_body():
    """Strongly-compressive behavioral amp: y = pGAIN*x - 90*x^3, matched I/O.
    g3=90 puts P1dB_in ~ -12 dBm (for pGAIN in [1,10]), inside pa_harness
    DEFAULT_PINS, so p1db/pae are reached (psat is reached regardless). VDD/Rdc
    give a known Idd for PAE. pGAIN decoded over the r_ohm box (positive scalar)."""
    return "\n".join([
        "* classgate pa DUT: behavioral compressive amp, sized gain",
        "Vp1 x 0 dc 0 ac 1 portnum 1 z0 50",
        "Rin x 0 50",
        "Bnl y 0 V = {pGAINV}*v(x) - 90.0*v(x)*v(x)*v(x)",
        "Vp2 y 0 dc 0 ac 0 portnum 2 z0 50",
        "RLD y 0 50",
        "Vsup VDD 0 dc 1.1",
        "Rdc VDD 0 110",
        ".option reltol=1e-5",
    ]), {"pGAINV": "R"}, {}


def _mixer_body():
    """Ideal multiplier IF = pK*v(lo)*v(rf); portnum1 RF, 2 IF, 3 LO. conv_gain
    tracks pK, so the objective has a real knob; iso is at the numerical floor.
    pK decoded over the r_ohm box (positive scalar)."""
    return "\n".join([
        "* classgate mixer DUT: ideal multiplier, sized k",
        "Vp1 rf 0 dc 0 ac 1 portnum 1 z0 50",
        "Rrf rf 0 50",
        "Vp3 lo 0 dc 0 ac 0 portnum 3 z0 50",
        "Bif if 0 V = {pKV}*v(lo)*v(rf)",
        "Vp2 if 0 dc 0 ac 0 portnum 2 z0 50",
        "RLD if 0 50",
        "Vsup VDD 0 dc 1.1",
        "Rdc VDD 0 110",
        ".option reltol=1e-5",
    ]), {"pKV": "R"}, {}


def _balun_body():
    """Center-tapped behavioral balun; inverting leg fixed at -0.5, non-inverting
    leg SIZED via pGP so imbalance/cmrr move with the knob (pGP=0.5 -> ideal;
    pGP != 0.5 -> imbalance). portnum1 in, 2 inverting out, 3 non-inverting out.
    pGP decoded over the vb_v box (linear, [0.2,0.9], straddling the balanced 0.5)."""
    return "\n".join([
        "* classgate balun DUT: center-tapped, sized non-inverting leg",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        "Rt p1 0 50",
        "E2 e2 0 p1 0 -0.5",
        "R2 e2 out2 50",
        "E3 e3 0 p1 0 {pGPB}",
        "R3 e3 out3 50",
        "Vp2 out2 0 dc 0 ac 0 portnum 2 z0 50",
        "Vp3 out3 0 dc 0 ac 0 portnum 3 z0 50",
        "Vsup VDD 0 dc 1.1",
    ]), {"pGPB": "VB"}, {}


# ------------------------------------------------------------------- spec builder
def _spec(name, cls, gate_metric, gate, extra_constraints=None, band=None):
    """A minimal in-memory class Spec gating exactly `gate_metric` at `gate`
    ({'min':v}|{'max':v}) as status:measured, plus a maximise objective on it so
    the sizing has a direction. `band` defaults to a 2.4 GHz narrowband block."""
    band = band or {"type": "narrowband", "f0": 1.5e9,
                    "f_lo": 1.4e9, "f_hi": 1.6e9}
    cons = {gate_metric: dict(gate, status="measured")}
    cons.update(extra_constraints or {})
    return Spec({
        "name": name, "circuit_class": cls, "pdk": "bptm45",
        "topology": {"device_budget": [1, 24], "allow_inductorless": True,
                     "reject_floating": False},
        "band": band,
        "ports": {"z0": 50, "input": "VIN1", "output": "VOUT1"},
        "constraints": cons,
        "sizing": _SIZING,
        "objectives": [{"metric": gate_metric,
                        "direction": ("min" if "max" in gate else "max"),
                        "weight": 1.0}],
    })


def _size(body, sizable, fixed, spec):
    """A tiny ZOAF sizing through make_objective (the SAME junction the campaign
    uses), returning (best_metrics, feasible, n_evals). make_objective ->
    objective_func -> eval_metrics is exactly the path class metrics are wired
    into, and (for pa/mixer) the elite gate is created inside make_objective so
    the expensive harness only runs on proxy-competitive candidates. The endpoint
    re-eval `evaluate(best_x)` is UNGATED, so the winning point carries the full
    class metrics regardless of gating. n_candidates=2/sgd=2/cgd=1 -> ~28 evals,
    the pre-reg's ~20-40 band; elite gating keeps the pa/mixer harness count low
    so the whole golden stays well under ~2 min."""
    obj, names, decode, evaluate = S.make_objective(body, spec, sizable, fixed)
    best_x, best_obj, n_evals = S.run_zoaf(obj, names, seed=1,
                                           n_candidates=2, sgd_iters=2,
                                           cgd_iters=1)
    m = evaluate(best_x)                        # ungated: full class metrics
    return m, (m is not None and spec.feasible(m)[0]), n_evals


def _run_class(label, cls, body_fn, gate_metric, loose_gate, absurd_gate,
               present_keys, band=None, extra=None):
    """Presence + response for one class. Sizes ONCE (loose gate) to get a metrics
    dict, checks (a) the class keys are present, then re-scores that SAME point
    against a loose vs an absurd gate to check (b) feasibility responds.

    Scoring the one sized point against both gates (rather than re-sizing) makes
    the response check deterministic and cheap, and is the sharper statement: on
    ONE fixed measured point, only the gate differs, so a feasibility flip can
    ONLY come from the class metric being read by spec.feasible."""
    print(f"[{label}] class={cls}  gate={gate_metric}")
    body, sizable, fixed = body_fn()
    spec_loose = _spec(f"{label}-loose", cls, gate_metric, loose_gate,
                       extra_constraints=extra, band=band)
    spec_absurd = _spec(f"{label}-absurd", cls, gate_metric, absurd_gate,
                        extra_constraints=extra, band=band)
    t0 = time.time()
    m, feas_loose, n_evals = _size(body, sizable, fixed, spec_loose)
    dt = time.time() - t0
    if m is None:
        print(f"    RED: sizing produced no metrics (sim failed) [{n_evals} evals]")
        return False
    # (a) PRESENCE
    present = {k: m.get(k) for k in present_keys}
    have = [k for k in present_keys if m.get(k) is not None]
    ok_present = len(have) == len(present_keys)
    print(f"    (a) class metrics in dict: "
          + ", ".join(f"{k}={('%.3g' % v) if isinstance(v, (int, float)) else v}"
                      for k, v in present.items()))
    print(f"        -> {'all present' if ok_present else 'MISSING ' + str([k for k in present_keys if m.get(k) is None])}")
    # (b) RESPONSE: same measured point, loose gate feasible / absurd gate not
    feas_loose2 = spec_loose.feasible(m)[0]
    feas_absurd = spec_absurd.feasible(m)[0]
    obj_loose = spec_loose.objective(m)
    obj_absurd = spec_absurd.objective(m)
    ok_response = feas_loose2 and not feas_absurd
    gm = m.get(gate_metric)
    print(f"    (b) {gate_metric}={('%.3g' % gm) if isinstance(gm, (int, float)) else gm}: "
          f"loose {loose_gate} -> feasible={feas_loose2} (obj {obj_loose:+.3g}); "
          f"absurd {absurd_gate} -> feasible={feas_absurd} (obj {obj_absurd:+.3g})")
    print(f"        -> objective {'RESPONDS' if ok_response else 'DOES NOT RESPOND'} "
          f"to the class gate  [{n_evals} evals, {dt:.1f}s]")
    ok = ok_present and ok_response
    print(f"    [{label}] {'GREEN' if ok else 'RED'}")
    return ok


def main():
    I.private_tmp()
    ok = True

    # PA: gate p1db_dbm. A behavioral amp with P1dB_out ~ -1 dBm; loose min -50
    # (met), absurd min 200 dBm (impossible).
    ok &= _run_class(
        "PA", "pa", _pa_body, "p1db_dbm",
        loose_gate={"min": -50}, absurd_gate={"min": 200.0},
        present_keys=("p1db_dbm", "psat_dbm", "pae_pct"))

    # MIXER: gate conv_gain_db. Ideal multiplier conv_gain ~ 0..-6 dB depending on
    # k; loose min -50 (met), absurd min 200 dB (impossible). RF=2.4G, LO band f_lo
    # is a real down-converting LO (2.0 GHz).
    ok &= _run_class(
        "MIXER", "mixer", _mixer_body, "conv_gain_db",
        loose_gate={"min": -50}, absurd_gate={"min": 200.0},
        present_keys=("conv_gain_db", "lo_rf_iso_db", "lo_if_iso_db"),
        band={"type": "narrowband", "f0": 2.4e9, "f_lo": 2.0e9, "f_hi": 2.4835e9})

    # BALUN: gate cmrr_db. Center-tapped balun CMRR is large when balanced; loose
    # min -50 (met), absurd min 900 dB (above the 1e-30 numerical CMRR ceiling ~
    # 600 dB, impossible). Also asserts imbalance/sds21 presence.
    ok &= _run_class(
        "BALUN", "balun-lna", _balun_body, "cmrr_db",
        loose_gate={"min": -50}, absurd_gate={"min": 900.0},
        present_keys=("sds21_db", "cmrr_db", "imbalance_amp_db",
                      "imbalance_phase_deg"),
        band={"type": "narrowband", "f0": 1.8e9, "f_lo": 1.1e9, "f_hi": 2.5e9})

    print("check_classgate:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
