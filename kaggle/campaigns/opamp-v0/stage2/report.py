"""Print the Stage-2 README tables (markdown) from stage2/results/. Usage: report.py"""
import glob
import json
import os

import s2common as C

R = C.RESULTS


def load(tag):
    p = os.path.join(R, tag + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def f(v, fmt="%.2f"):
    return (fmt % v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v is not None else "—"


def spec_str(sp):
    out = []
    for k, c in sp["constraints"].items():
        if "min" in c:
            out.append("%s ≥ %g" % (k, c["min"]))
        if "max" in c:
            out.append("%s ≤ %g" % (k, c["max"]))
    return "CL %g pF; " % sp["cl_pf"] + ", ".join(out)


def golden():
    print("| circuit | devices / params | demo spec (margin mode, + stability gate) | feasible | worst margin | gain dB | UGF MHz | PM ° | Idd µA | swing Vpp | ICMR V | FOM MHz·pF/mA | CPU s |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for n in C.CIRCUITS:
        r = load("golden-" + n)
        s = r["summary"]
        print("| %s | %d / %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            n, s["n_devices"], s["n_params"], spec_str(r["job"]["spec"]), "yes" if s["feasible"] else "**no**",
            f(s["worst_margin"], "%.3f"), f(s["gain_db"]), f(s["ugf_mhz"]), f(s["pm_deg"], "%.1f"),
            f(s["idd_ua"], "%.1f"), f(s["swing_vpp"], "%.3f"), f(s["icmr_v"], "%.3f"),
            f(s["fom_mhzpf_ma"], "%.0f"), f(s["cpu_s"], "%.0f")))


def med3(vals):
    v = sorted(x if x is not None else float("-inf") for x in vals)
    return v[1] if len(v) == 3 else None


def preview():
    for reg in ("R1", "R23", "R4"):
        M = C.REGIMES[reg]["M"]
        w = [k for k, v in C.WITNESS_REGIME.items() if v == reg][0]
        print("\n**%s** (max:%s; %s)\n" % (reg, M, spec_str(C.REGIMES[reg]["spec"])))
        print("| design | seed 1 | seed 2 | seed 3 | median (infeasible = −∞) | seed-1 gain / UGF / PM / Idd |")
        print("|---|---|---|---|---|---|")
        for n in [w] + list(C.LIB):
            vals, cells = [], []
            for sd in (1, 2, 3):
                r = load("max-%s-%s" % (reg, n) + ("" if sd == 1 else "-s%d" % sd))
                if r is None:
                    cells.append("")
                    continue
                s = r["summary"]
                v = s["target"] if s["feasible"] else None
                vals.append(v)
                cells.append(f(v, "%.3f" if M == "icmr_v" else ("%.0f" if M.startswith("fom") else "%.2f"))
                             if s["feasible"] else "infeasible" + (" (ss_unstable)" if "ss_unstable" in (s["flags"] or []) else ""))
            s1 = load("max-%s-%s" % (reg, n))["summary"]
            md = med3(vals) if len(vals) == 3 else None
            print("| %s | %s | %s | %s | %s | %s / %s / %s / %s |" % (
                n, cells[0], cells[1], cells[2],
                (f(md, "%.3f" if M == "icmr_v" else "%.2f") if md not in (None, float("-inf")) else ("−∞" if md is not None else "")),
                f(s1["gain_db"]), f(s1["ugf_mhz"]), f(s1["pm_deg"], "%.1f"), f(s1["idd_ua"], "%.1f")))


def f2():
    print("| anchor | nets / devices | raw edits | unique (canonical) | after pre-filter | addRC | addMOS | del | rewire | pre-filter rejects (first rule) | two-edit kept / tries |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for a in C.ANCHORS:
        c = json.load(open(os.path.join(R, "f2_%s_counts.json" % a)))
        k = c["counts"]
        kinds = ["%d/%d/%d" % (k["by_kind_raw"].get(x, 0), k["by_kind_unique"].get(x, 0), k["by_kind_ok"].get(x, 0))
                 for x in ("addRC", "addMOS", "del", "rewire")]
        print("| %s | %d / %d | %d | %d | **%d** | %s | %s | %s | %s | %s | %d / %d |" % (
            a, k["n_nets"], k["n_devices"], k["raw"], k["unique"], k["prefilter_ok"], *kinds,
            ", ".join("%s %d" % kv for kv in sorted(k["prefilter_reject_first_reason"].items())),
            c["two_edit"]["stats"]["kept"], c["two_edit"]["stats"]["tries"]))


def accuracy():
    a = json.load(open(os.path.join(R, "accuracy.json")))
    print("| design | verifier | AC@VINN tight | AC@VINP tight | AC@VINP gmin 1e-15 | DC FD tight | max diff | flag |")
    print("|---|---|---|---|---|---|---|---|")
    for r in a["rows"]:
        print("| %s | %.3f | %.3f | %.3f | %.3f | %.3f | %.3f | %s |" % (
            r["tag"], r["ver_db"], r["ac_n_t"], r["ac_p_t"], r["ac_p_g"], r["fd_t"], r["max_abs_diff_db"],
            "**>1 dB**" if r["flag_gt_1db"] else "ok"))


def cpu():
    tot = 0.0
    for p in glob.glob(os.path.join(R, "*.json")):
        try:
            tot += json.load(open(p))["summary"]["cpu_s"]
        except (KeyError, TypeError):
            pass
    pre = 0.0
    for p in glob.glob(os.path.join(R, "pre_stability", "*.json")):
        try:
            pre += json.load(open(p))["summary"]["cpu_s"]
        except (KeyError, TypeError):
            pass
    print("\nCPU: gated sizing runs %.0f s; pre-gate runs %.0f s" % (tot, pre))


if __name__ == "__main__":
    print("### Goldens\n")
    golden()
    print("\n### Preview\n")
    preview()
    print("\n### F2'\n")
    f2()
    print("\n### Accuracy\n")
    accuracy()
    cpu()
