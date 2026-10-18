"""V4 loophole checks.
 (a) a netlist with a floating gate or an undriven bias node is rejected (pre-filter, 0 evals)
     or infeasible after sizing;
 (b) PM is computed at the true unity crossing: a deliberately unstable design (the V3 max-gain
     AutoCkt two-stage with Cc cut to 0.05 pF) reads PM < 0, its follower transient oscillates,
     and for stable and unstable designs the PM/UGF agree with a 10x denser AC sweep
     (|dPM| <= 1 deg, |dUGF|/UGF <= 1 %);
 (c) a design whose output CM sits outside the swing window is flagged (and so infeasible):
     the V3 max-gain 5T OTA at Vcm = 0.90 V (control: same design at Vcm = 0.55 V not flagged).
Needs gates/results/v3.json (sized params). Pass: every sub-check passes."""
import sys

from common import SPEC_BASE, circuit, dump, slim
import json
import os
import opamp_v0 as O
from opamp_v0 import testbench as TB
from common import RESULTS

OTA = circuit("ota5t.net")
BAD = {
    "floating_gate": OTA.replace("NMOS M5 tail IREF VSS VSS", "NMOS M5 tail nb VSS VSS"),
    "undriven_bias_cap_only": circuit("two_stage_autockt.net").replace(
        "NMOS M6 VOUT IREF VSS VSS", "NMOS M6 VOUT nb VSS VSS\nC Cb nb VSS"),
    "bias_from_input_source": OTA.replace("NMOS M5 tail IREF VSS VSS",
                                          "NMOS M5 tail nb VSS VSS\nR Rb VINP nb"),
    "shorted_device": OTA + "R Rx tail tail\n",
    "no_iref": OTA.replace("NMOS M5 tail IREF VSS VSS", "NMOS M5 tail d1 VSS VSS").replace(
        "NMOS M6 IREF IREF VSS VSS\n", ""),
    "vout_undriven": OTA.replace("NMOS M1b VOUT VINN tail VSS", "NMOS M1b d2 VINN tail VSS").replace(
        "PMOS M3b VOUT d1 VDD VDD", "PMOS M3b d2 d1 VDD VDD") + "C Co d2 VOUT\n",
}
# INFORMATIONAL (not gated): passes the pre-filter (the bias net is resistively tied to VSS,
# so it is DC-driven, not undriven) and the tail runs on subthreshold current only. This is
# legitimate (if poor) circuit physics, not a testbench loophole, so it is reported only.
TAIL_OFF = OTA.replace("NMOS M5 tail IREF VSS VSS", "NMOS M5 tail nb VSS VSS\nR Rb nb VSS")


def pm_check(net, params, spec):
    m20 = O.evaluate(net, params, spec, full=True)
    old = TB.PTS_DEC
    TB.PTS_DEC = 200
    try:
        m200 = O.evaluate(net, params, spec, full=False)
    finally:
        TB.PTS_DEC = old
    d_pm = abs(m20["pm_deg"] - m200["pm_deg"])
    d_f = abs(m20["ugf_hz"] - m200["ugf_hz"]) / m200["ugf_hz"]
    return m20, m200, d_pm, d_f


def main():
    v3 = json.load(open(os.path.join(RESULTS, "v3.json")))
    P = {(r["circuit"], r["objective"]): r["params"] for r in v3["rows"]}
    res, ok_all = {"a": [], "b": [], "c": []}, True

    # (a)
    for name, net in BAD.items():
        r = O.size(net, SPEC_BASE, seed=1, evals=300)
        ok = (not r["feasible"]) and r["evals"] == 0
        ok_all &= ok
        res["a"].append({"case": name, "rejected": r["evals"] == 0, "why": r["prefilter"]["why"],
                         "feasible": r["feasible"], "pass": ok})
        print("(a) %-24s rejected=%s why=%s -> %s" % (name, r["evals"] == 0, r["prefilter"]["why"],
                                                     "PASS" if ok else "FAIL"))
    r = O.size(TAIL_OFF, SPEC_BASE, seed=1, evals=300)
    m = r["metrics"] or {}
    ok = not r["feasible"]
    res["a"].append({"case": "tail_off_resistor_bias", "gated": False, "rejected": r["evals"] == 0,
                     "feasible": r["feasible"], "evals": r["evals"], "flags": m.get("flags"),
                     "gain_db": m.get("gain_db"), "idd_ua": m.get("idd_ua"), "pass": ok})
    print("(a) %-24s evals=%d feasible=%s gain=%s flags=%s -> %s" % (
        "tail_off_resistor_bias", r["evals"], r["feasible"], m.get("gain_db"), m.get("flags"),
        "(informational)"))

    # (b)
    p2 = dict(P[("two_stage_autockt.net", "max:gain_db")])
    unst = dict(p2)
    unst["Cc.C"] = 0.05e-12
    cases = [("two_stage_v3_stable", "two_stage_autockt.net", p2, False),
             ("two_stage_cc_0p05pF_UNSTABLE", "two_stage_autockt.net", unst, True),
             ("ota5t_v3", "ota5t.net", P[("ota5t.net", "max:gain_db")], False),
             ("two_stage_rz_v3", "two_stage_rz.net", P[("two_stage_rz.net", "max:gain_db")], False)]
    for name, cnet, params, unstable in cases:
        m20, m200, d_pm, d_f = pm_check(circuit(cnet), params, {"cl_pf": 2.0, "constraints": {}})
        ok = d_pm <= 1.0 and d_f <= 0.01
        if unstable:
            ok = ok and m20["pm_deg"] < 0 and not m20.get("tran_settled") and \
                not O.feasible(SPEC_BASE, m20)
        ok_all &= ok
        res["b"].append({"case": name, "pm_deg": m20["pm_deg"], "pm_deg_dense": m200["pm_deg"],
                         "ugf_mhz": m20["ugf_mhz"], "ugf_mhz_dense": m200["ugf_mhz"],
                         "d_pm": d_pm, "d_ugf_rel": d_f, "n_unity_crossings": m20["n_unity_crossings"],
                         "tran_settled": m20.get("tran_settled"), "tran_ripple_v": m20.get("tran_ripple_v"),
                         "feasible_under_base_spec": O.feasible(SPEC_BASE, m20), "pass": ok})
        print("(b) %-30s PM=%.2f (dense %.2f) UGF=%.3f MHz (dense %.3f) crossings=%d settled=%s "
              "ripple=%.3g -> %s" % (name, m20["pm_deg"], m200["pm_deg"], m20["ugf_mhz"],
                                     m200["ugf_mhz"], m20["n_unity_crossings"], m20.get("tran_settled"),
                                     m20.get("tran_ripple_v") or 0, "PASS" if ok else "FAIL"))

    # (c)
    p5 = P[("ota5t.net", "max:gain_db")]
    spec_sw = {"constraints": {"swing_vpp": {"min": 0.1}}, "cl_pf": 2.0}
    for vcm, expect in ((0.55, False), (0.90, True)):
        sp = dict(spec_sw, vcm=vcm)
        m = O.evaluate(OTA, p5, sp, full=True)
        flagged = "outcm_outside_swing_window" in m["flags"]
        ok = flagged == expect and (O.feasible(sp, m) != expect)
        ok_all &= ok
        res["c"].append({"vcm": vcm, "vout_dc": m["vout_dc"], "gain_vv": m["gain_vv"],
                         "swing_gain_peak_vv": m["swing_gain_peak_vv"],
                         "swing_vpp": m["swing_vpp"], "outcm_window": m["outcm_window"],
                         "flags": m["flags"], "valid": m["valid"], "feasible": O.feasible(sp, m),
                         "expect_flag": expect, "pass": ok, "metrics": slim(m)})
        print("(c) vcm=%.2f vout=%.4f gain=%.2f peak=%.2f swing=%.3f window=%s flags=%s feasible=%s -> %s"
              % (vcm, m["vout_dc"], m["gain_vv"], m["swing_gain_peak_vv"], m["swing_vpp"],
                 m["outcm_window"], m["flags"], O.feasible(sp, m), "PASS" if ok else "FAIL"))
    dump("v4.json", {"gate": "V4", "pass": ok_all, **res})
    print("V4", "PASS" if ok_all else "FAIL")


if __name__ == "__main__":
    main()
