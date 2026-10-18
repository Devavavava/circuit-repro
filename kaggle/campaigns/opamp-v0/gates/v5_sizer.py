"""V5 sizer strength: AutoCkt's two-stage Miller (circuits/two_stage_autockt.net) with AutoCkt's
own spec, sized in the standard margin mode at seeds 1, 2, 3 with 2,500 evaluations.
Pass: feasible at 3/3 seeds.

AutoCkt's own spec = the target in AutoCkt/smoke_engine.py (the only AutoCkt spec on disk):
gain >= 300 V/V (49.54 dB), UGBW >= 10 MHz, PM >= 60 deg, ibias (supply current) <= 1 mA,
with AutoCkt's load CL = 10 pF. Process/testbench are opamp-v0's (bptm45, VDD 1.1 V,
Vcm 0.55 V, unity-feedback DC loop, free W/L, one ideal IREF).

Informational (not gated): the same at the anchor with Rz, and a stretch spec at the
upper ends of AutoCkt's target ranges as recalled from the paper's yaml (gain 400 V/V,
UGBW 25 MHz, PM 60, ibias 0.1 mA) -- the yaml is not on disk (README D-O9)."""
import math
import sys

from common import circuit, dump, slim
import opamp_v0 as O

EVALS = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
AUTOCKT = {"name": "autockt-smoke", "cl_pf": 10.0, "constraints": {
    "gain_db": {"min": 20 * math.log10(300.0)}, "ugf_mhz": {"min": 10.0},
    "pm_deg": {"min": 60.0}, "idd_ua": {"max": 1000.0}}}
STRETCH = {"name": "autockt-stretch", "cl_pf": 10.0, "constraints": {
    "gain_db": {"min": 20 * math.log10(400.0)}, "ugf_mhz": {"min": 25.0},
    "pm_deg": {"min": 60.0}, "idd_ua": {"max": 100.0}}}
RUNS = [("gate", "two_stage_autockt.net", AUTOCKT),
        ("info", "two_stage_rz.net", AUTOCKT),
        ("info", "two_stage_autockt.net", STRETCH),
        ("info", "two_stage_rz.net", STRETCH)]


def main():
    only_gate = "--gate-only" in sys.argv
    rows, n_ok = [], 0
    for kind, net, spec in RUNS:
        if only_gate and kind != "gate":
            continue
        for seed in (1, 2, 3):
            r = O.size(circuit(net), spec, seed=seed, evals=EVALS, objective="margin")
            m = r["metrics"] or {}
            first_feas = None
            for t in r["trace"]:
                if t["feasible"]:
                    first_feas = t["n"]
                    break
            row = {"kind": kind, "circuit": net, "spec": spec["name"], "seed": seed,
                   "feasible": r["feasible"], "worst_margin": r["worst_margin"],
                   "margins": r["margins"], "first_feasible_by_eval": first_feas,
                   "best_eval": r["best_eval"], "evals": r["evals"], "n_fail": r["n_fail"],
                   "params": r["params"], "metrics": slim(m), "secs": r["secs"], "cpu_s": r["cpu_s"]}
            rows.append(row)
            if kind == "gate" and r["feasible"]:
                n_ok += 1
            print("%-5s %-22s %-16s seed %d feas=%s worst=%.3f first_feas<=%s gain=%.2f ugf=%.2f "
                  "pm=%.1f idd=%.1f cpu=%.0fs" % (kind, net, spec["name"], seed, r["feasible"],
                                                  r["worst_margin"] if r["worst_margin"] is not None else math.nan,
                                                  first_feas, m.get("gain_db") or math.nan,
                                                  m.get("ugf_mhz") or math.nan, m.get("pm_deg") or math.nan,
                                                  m.get("idd_ua") or math.nan, r["cpu_s"]), flush=True)
    ok = n_ok == 3
    dump("v5.json", {"gate": "V5", "pass": ok, "feasible_seeds": n_ok, "evals": EVALS,
                     "spec": AUTOCKT, "stretch": STRETCH, "rows": rows})
    print("V5", "PASS" if ok else "FAIL", "%d/3" % n_ok)


if __name__ == "__main__":
    main()
