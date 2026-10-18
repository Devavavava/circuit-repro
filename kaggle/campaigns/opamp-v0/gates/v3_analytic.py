"""V3 analytic sanity: sized 5T OTA gain vs gm*ro/2 from its own operating point; sized
two-stage Miller gain vs its two-stage product (seed 1, 2,500 evals, objectives max:gain_db
and margin, circuits ota5t / two_stage_autockt / two_stage_rz).

Analytic form: gm_in * (ro_in || ro_load) per stage (= gm*ro/2 when ro_in = ro_load; the
literal gm_in*ro_in/2 is reported beside it). The textbook formula presumes every MOS is
saturated (|vds| >= |vdsat|); a design with a device in triode is REPORTED but not gated
(README D-O8). Pass: every premise-satisfying design within 3 dB, and at least one
premise-satisfying design for the 5T and for a two-stage."""
import math
import sys

from common import SPEC_BASE, circuit, dump, slim
import opamp_v0 as O

EVALS = int(sys.argv[1]) if len(sys.argv) > 1 else 2500


def db(x):
    return 20 * math.log10(x)


def ota5(op):
    i, l = op["M1b"], op["M3b"]                     # output branch: input device + mirror load
    a_par = i["gm"] / (i["gds"] + l["gds"])         # gm1 * (ro1 || ro3)
    a_lit = i["gm"] * (1.0 / i["gds"]) / 2.0         # gm1 * ro1 / 2 (equal-ro textbook form)
    return {"A_gm_ro_par_db": db(a_par), "A_gm_ro_over_2_db": db(a_lit),
            "parts": {"gm1": i["gm"], "gds1": i["gds"], "gds3": l["gds"]}}


def two_stage(op):
    i, l = op["M2b"], op["M1b"]                     # first-stage output branch (n5)
    s, k = op["M5"], op["M6"]                       # second stage CS + sink
    a1 = i["gm"] / (i["gds"] + l["gds"])
    a2 = s["gm"] / (s["gds"] + k["gds"])
    a1_lit = i["gm"] / i["gds"] / 2.0
    a2_lit = s["gm"] / s["gds"] / 2.0
    return {"A_gm_ro_par_db": db(a1 * a2), "A1_db": db(a1), "A2_db": db(a2),
            "A_gm_ro_over_2_db": db(a1_lit * a2_lit),
            "parts": {"gm_in": i["gm"], "gds_in": i["gds"], "gds_load": l["gds"],
                      "gm_cs": s["gm"], "gds_cs": s["gds"], "gds_sink": k["gds"]}}


def main():
    rows, ok_all, fams = [], True, set()
    for net, fn in (("ota5t.net", ota5), ("two_stage_autockt.net", two_stage),
                    ("two_stage_rz.net", two_stage)):
        for obj in ("max:gain_db", "margin"):
            r = O.size(circuit(net), SPEC_BASE, seed=1, evals=EVALS, objective=obj)
            m = r["metrics"]
            an = fn(m["op"])
            err = m["gain_db"] - an["A_gm_ro_par_db"]
            triode = sorted(k for k, o in m["op"].items() if abs(o["vds"]) < abs(o["vdsat"]))
            premise = not triode
            ok = abs(err) <= 3.0
            if premise:
                ok_all &= ok
                fams.add("5t" if net == "ota5t.net" else "2st")
            row = {"circuit": net, "objective": obj, "feasible": r["feasible"],
                   "premise_all_saturated": premise, "triode_devices": triode,
                   "gain_db_sim": m["gain_db"], "analytic": an, "err_db": err,
                   "err_literal_db": m["gain_db"] - an["A_gm_ro_over_2_db"], "pass": ok,
                   "params": r["params"], "metrics": slim(m), "op": m["op"],
                   "secs": r["secs"], "cpu_s": r["cpu_s"]}
            rows.append(row)
            print("%-22s %-12s feas=%s sim=%.2f dB analytic(par)=%.2f dB err=%.2f lit=%.2f triode=%s -> %s"
                  % (net, obj, r["feasible"], m["gain_db"], an["A_gm_ro_par_db"], err,
                     row["err_literal_db"], triode,
                     ("PASS" if ok else "FAIL") if premise else "(not gated)"), flush=True)
    ok_all = ok_all and fams == {"5t", "2st"}
    dump("v3.json", {"gate": "V3", "pass": ok_all, "evals": EVALS, "spec": SPEC_BASE, "rows": rows})
    print("V3", "PASS" if ok_all else "FAIL")


if __name__ == "__main__":
    main()
