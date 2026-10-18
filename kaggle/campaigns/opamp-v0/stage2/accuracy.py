"""Measurement-accuracy check of the verifier's DC gain for high-gain designs (README D-O20).

For every sized Stage-2 result (stage2/results/{golden,max}-*.json) of a cascode / multi-stage
circuit whose verifier gain is >= GAIN_MIN dB, re-read the low-frequency gain independently:

  ver      the verifier's reading: |A(0.01 Hz)|, AC injected at VINN (default ngspice options)
  ac_n_t   same fixture, tight tolerances (reltol 1e-6, abstol 1e-15, vntol 1e-12)
  ac_p_t   AC injected at VINP instead (VINN held by the 1 TH DC loop), tight tolerances
  ac_p_g   as ac_p_t with gmin 1e-15 (ngspice default 1e-12): sensitivity to the gmin shunts
  fd_t     DC finite difference in the open-loop-equivalent sweep: Vsw over +-2 mV in 0.25 mV
           steps around the operating point, least-squares slope dVOUT / dVid with
           Vid = v(vinp) - v(vinn) computed inside ngspice (full relative precision), tight tol
Discrepancy = max |reading - ver| over the tight-tolerance readings; FLAG if > 1 dB.
Usage: accuracy.py [gain_min_db=75]
"""
import glob
import json
import math
import os
import sys

import s2common as C
from opamp_v0 import testbench as TB, dialect as DL

GAIN_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 75.0
CHECK = ("telescopic", "folded_cascode", "three_stage_nmc", "W-R1", "W-R23", "W-R4")
TIGHT = ".options reltol=1e-6 abstol=1e-15 vntol=1e-12"


def deck(devs, params, tb, wd, inj, gmin=None):
    vdd, vcm, cl = tb["vdd"], tb["vcm"], tb["cl_pf"] * 1e-12
    L = ["* opamp-v0 accuracy deck", '.include "%s"' % TB.MODEL_PATH, ".temp %s" % TB.fmt(tb["temp_c"]),
         TIGHT + ("" if gmin is None else " gmin=%g" % gmin),
         "Vdd vdd 0 dc %s" % TB.fmt(vdd), "Iref vdd iref dc %s" % TB.fmt(params["IREF"]),
         "Vp vinp 0 dc %s ac %d" % (TB.fmt(vcm), 1 if inj == "p" else 0),
         "Vsw tb_fb vout dc 0", "Lfb tb_fb vinn 1T", "Cin vinn tb_sig 1T",
         "Vsig tb_sig 0 dc 0 ac %d" % (1 if inj == "n" else 0), "CL vout 0 %s" % TB.fmt(cl)]
    L += TB.dut_lines(devs, params)
    L += [".control", "set wr_singlescale", "op", "print v(vout) i(vdd)",
          "ac dec 10 0.01 1", "wrdata %s/acc_ac.txt v(vout)" % wd,
          "dc vsw -0.002 0.002 0.00025", "let vid = v(vinp) - v(vinn)",
          "let dvo = v(vout) - %s" % TB.fmt(vcm),
          "wrdata %s/acc_dc.txt dvo vid" % wd, ".endc", ".end", ""]
    return "\n".join(L)


def read(devs, params, tb, wd, inj, gmin=None):
    text, err = TB.run_ngspice(deck(devs, params, tb, wd, inj, gmin), wd, ["acc_ac.txt", "acc_dc.txt"])
    ac = TB.read_rows(os.path.join(wd, "acc_ac.txt"))
    dc = TB.read_rows(os.path.join(wd, "acc_dc.txt"))
    out = {}
    if ac:
        h = complex(ac[0][1], ac[0][2])
        out["ac_db"] = 20 * math.log10(max(abs(h), 1e-30))
        out["ac_db_1hz"] = 20 * math.log10(max(abs(complex(ac[-1][1], ac[-1][2])), 1e-30))
    if len(dc) >= 5:
        xs = [r[2] for r in dc]      # rows (wr_singlescale): vsw, dvo, vid
        ys = [r[1] for r in dc]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        a = sxy / sxx if sxx > 0 else float("nan")
        out["fd_db"] = 20 * math.log10(abs(a)) if a == a and a != 0 else None
        res = [y - my - a * (x - mx) for x, y in zip(xs, ys)]
        out["fd_rel_resid"] = (max(abs(r) for r in res) / max(abs(y - my) for y in ys)) if ys else None
        out["fd_sign"] = 1 if a > 0 else -1
    return out


def main():
    os.environ.setdefault("OPAMP_V0_TMP", "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp")
    wd = TB.work_dir()
    rows = []
    for p in sorted(glob.glob(os.path.join(C.RESULTS, "*.json"))):
        b = os.path.basename(p)
        if not (b.startswith("golden-") or b.startswith("max-")):
            continue
        r = json.load(open(p))
        circ = r["job"]["circuit"]
        g = r["summary"].get("gain_db")
        if circ not in CHECK or g is None or g < GAIN_MIN or not r.get("params"):
            continue
        devs = DL.parse(r["netlist"])
        from opamp_v0.sizer import tb_from_spec
        tb = tb_from_spec(r["job"]["spec"])
        n_t = read(devs, r["params"], tb, wd, "n")
        p_t = read(devs, r["params"], tb, wd, "p")
        p_g = read(devs, r["params"], tb, wd, "p", gmin=1e-15)
        rec = {"tag": r["job"]["tag"], "circuit": circ, "ver_db": g,
               "ac_n_t": n_t.get("ac_db"), "ac_p_t": p_t.get("ac_db"), "ac_p_g": p_g.get("ac_db"),
               "fd_t": n_t.get("fd_db"), "fd_t_gmin15": p_g.get("fd_db"),
               "fd_rel_resid": n_t.get("fd_rel_resid"), "fd_sign": n_t.get("fd_sign"),
               "ac_n_t_1hz": n_t.get("ac_db_1hz")}
        reads = [rec[k] for k in ("ac_n_t", "ac_p_t", "fd_t") if rec[k] is not None]
        rec["max_abs_diff_db"] = max(abs(x - g) for x in reads) if reads else None
        rec["gmin_effect_db"] = (rec["ac_p_g"] - rec["ac_p_t"]) if None not in (rec["ac_p_g"], rec["ac_p_t"]) else None
        rec["flag_gt_1db"] = bool(rec["max_abs_diff_db"] is None or rec["max_abs_diff_db"] > 1.0)
        rows.append(rec)
        print(json.dumps(rec, sort_keys=True), flush=True)
    out = {"gain_min_db": GAIN_MIN, "rows": rows,
           "n_flagged": sum(1 for r in rows if r["flag_gt_1db"]),
           "max_abs_diff_db": max((r["max_abs_diff_db"] or 0) for r in rows) if rows else None}
    with open(os.path.join(C.RESULTS, "accuracy.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("n", len(rows), "flagged", out["n_flagged"], "max diff", out["max_abs_diff_db"])


if __name__ == "__main__":
    main()
