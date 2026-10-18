"""Stability cross-check of sized Stage-2 designs (README D-O21).

The verifier's stability criterion is the small-signal PM at the true unity crossing of the
open-loop A(f) (D-O10); the follower transient (+-0.1 V step) is reported but not gated. For
multi-stage designs a good PM reading with an oscillating transient means either (a) a
large-signal (slew-induced) oscillation of a small-signal-stable loop, or (b) a loop whose
open-loop phase crosses -180 deg while |A| > 1 below the UGF (conditionally stable), or (c) a
PM misreading. This script separates them, per design:

  ol_*        open-loop A(f) from the verifier's own AC (min relative phase while |A| >= 1,
              number of -180 crossings above unity gain, PM)
  cl_peak_db  closed-loop follower (VINN tied to VOUT) AC peaking max|H| over 0.01 Hz-10 GHz
  ss_ripple   small-step (1 mV) follower transient: peak-to-peak ripple in the last 30 % of the
              high pulse relative to the step (> 5 % = small-signal oscillation)
  ls_ripple   the verifier's own +-0.1 V transient ripple (tran_ripple_v / 0.2 V)
Usage: stability_check.py [tag-glob=*]
"""
import fnmatch
import glob
import json
import math
import os
import sys

import s2common as C
from opamp_v0 import testbench as TB, dialect as DL
from opamp_v0.sizer import tb_from_spec


def cl_ac(devs, params, tb, wd):
    L = ["* follower AC", '.include "%s"' % TB.MODEL_PATH, ".temp %s" % TB.fmt(tb["temp_c"]),
         "Vdd vdd 0 dc %s" % TB.fmt(tb["vdd"]), "Iref vdd iref dc %s" % TB.fmt(params["IREF"]),
         "Vp vinp 0 dc %s ac 1" % TB.fmt(tb["vcm"]), "Vfb vinn vout dc 0",
         "CL vout 0 %s" % TB.fmt(tb["cl_pf"] * 1e-12)]
    L += TB.dut_lines(devs, params)
    L += [".control", "set wr_singlescale", "op", "ac dec 40 0.01 10G",
          "wrdata %s/clac.txt v(vout)" % wd, ".endc", ".end", ""]
    TB.run_ngspice("\n".join(L), wd, ["clac.txt"])
    rows = TB.read_rows(os.path.join(wd, "clac.txt"))
    if not rows:
        return None
    pk = max(abs(complex(r[1], r[2])) for r in rows)
    return 20 * math.log10(max(pk, 1e-30))


def small_step(devs, params, tb, wd, ugf_hz, a=0.0005):
    vcm = tb["vcm"]
    tau = 1.0 / (2 * math.pi * max(ugf_hz or 1e6, 1e4))
    pw = min(max(100e-9, 100 * tau), 200e-6)
    td, tr = pw / 10, pw / 1000
    L = ["* small-step follower", '.include "%s"' % TB.MODEL_PATH, ".temp %s" % TB.fmt(tb["temp_c"]),
         "Vdd vdd 0 dc %s" % TB.fmt(tb["vdd"]), "Iref vdd iref dc %s" % TB.fmt(params["IREF"]),
         "Vp vinp 0 dc %s pulse(%s %s %s %s %s %s %s)" % (
             TB.fmt(vcm - a), TB.fmt(vcm - a), TB.fmt(vcm + a), TB.fmt(td), TB.fmt(tr), TB.fmt(tr),
             TB.fmt(pw), TB.fmt(2 * pw + td)),
         "Vfb vinn vout dc 0", "CL vout 0 %s" % TB.fmt(tb["cl_pf"] * 1e-12)]
    L += TB.dut_lines(devs, params)
    L += [".control", "set wr_singlescale", "tran %s %s 0 %s" % (TB.fmt(pw / 500), TB.fmt(td + 2 * pw),
                                                            TB.fmt(pw / 500)),
          "wrdata %s/sst.txt v(vout)" % wd, ".endc", ".end", ""]
    TB.run_ngspice("\n".join(L), wd, ["sst.txt"])
    rows = TB.read_rows(os.path.join(wd, "sst.txt"))
    seg = [r[1] for r in rows if td + 0.7 * pw <= r[0] <= td + 0.99 * pw]
    if not seg:
        return None
    return (max(seg) - min(seg)) / (2 * a)


def ol(devs, params, tb, wd):
    deck, _, _ = TB.main_deck(devs, params, tb, wd, icmr=False, full=False)
    TB.run_ngspice(deck, wd, ["ac.txt", "sw.txt"])
    rows = TB.read_rows(os.path.join(wd, "ac.txt"))
    H = [complex(-r[1], -r[2]) for r in rows]
    ph = TB._unwrap_deg([math.degrees(math.atan2(h.imag, h.real)) for h in H])
    rel = [p - ph[0] for p in ph]
    above = [(r, abs(h)) for r, h in zip(rel, H) if abs(h) >= 1.0]
    minph = min(r for r, _ in above) if above else None
    n180 = sum(1 for i in range(1, len(rel)) if abs(H[i]) >= 1 and abs(H[i - 1]) >= 1 and
               ((rel[i - 1] > -180) != (rel[i] > -180)))
    a = TB.ac_metrics(rows)
    return {"ol_min_rel_phase_above_unity": minph, "ol_n_180_crossings_above_unity": n180,
            "ol_pm": a.get("pm_deg"), "ol_ugf_mhz": a.get("ugf_mhz"),
            "ol_n_unity_crossings": a.get("n_unity_crossings")}


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else "*"
    os.environ.setdefault("OPAMP_V0_TMP", "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp")
    wd = TB.work_dir()
    rows = []
    for p in sorted(glob.glob(os.path.join(C.RESULTS, "*.json"))):
        tag = os.path.basename(p)[:-5]
        if not (tag.startswith("golden-") or tag.startswith("max-")) or not fnmatch.fnmatch(tag, pat):
            continue
        r = json.load(open(p))
        if not r.get("params"):
            continue
        devs = DL.parse(r["netlist"])
        tb = tb_from_spec(r["job"]["spec"])
        s = r["summary"]
        rec = {"tag": tag, "feasible": s["feasible"], "pm_deg": s["pm_deg"],
               "tran_osc_flag": "tran_oscillation" in (s.get("flags") or [])}
        rec.update(ol(devs, r["params"], tb, wd))
        rec["cl_peak_db"] = cl_ac(devs, r["params"], tb, wd)
        rec["ss_ripple_rel"] = small_step(devs, r["params"], tb, wd, (s.get("ugf_mhz") or 1) * 1e6)
        rec["small_signal_oscillates"] = bool(rec["ss_ripple_rel"] is not None and rec["ss_ripple_rel"] > 0.05)
        rows.append(rec)
        print(json.dumps(rec, sort_keys=True), flush=True)
    name = "stability.json" if pat == "*" else "stability_%s.json" % pat.replace("*", "x")
    with open(os.path.join(C.RESULTS, name), "w") as fh:
        json.dump(rows, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
