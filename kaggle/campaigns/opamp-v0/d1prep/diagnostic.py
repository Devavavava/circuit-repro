"""Pre-D1 diagnostic (no verdict): does the robustness gate (README D-O33) separate the D0 witnesses
from D0's single-transistor bias-feedback designs?  D0's results are only READ (stage3/results/
jobs.jsonl); nothing of D0 is re-run or changed.

Phases (from the worktree root via the env wrapper):
  assized [procs]  every selected D0 design AS SIZED (D0's stored parameters, no re-sizing):
                   nominal full re-measure (checks M reproduces D0's value) + the robustness gate
                   at the regime's hard constraints (+ stability gate) -> results/assized.jsonl
  resize [procs]   top-3 single-edit (F2') designs by D0 M* + the witness per regime, re-sized with
                   the gate ON, max:M, seed 1, 2,500 evals -> results/resize.jsonl
  report           -> results/diagnostic.json and the markdown tables (stdout)

Selection (per regime R1, R23, R4; all from D0's 2,500-eval runs):
  (a) witness   the witness frontier runs, seeds 1-3
  (b) edits     every top-f2 / top-te run (single-edit F2' / two-edit) with M >= the witness M*
                (median of its 3 seeds; "beat or matched"), plus every seed of the top-3 F2'
                designs by D0 M* and the best two-edit run, so each regime has >= 3 single-edit
                designs and one two-edit design even where fewer beat the witness
  (c) F1        every feasible F1 library frontier run (seeds 1-3)
"""
import json
import math
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(CAMPAIGN, "stage3"))
import d0common as C          # noqa: E402  (read-only: D0 store, specs, design texts)

O = C.O
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)
TMP = C.TMP
ROBUST = "pvt_mm"
PROCS_MAX = 8
EVALS = 2500


def regime_spec(reg, robust=True):
    sp = C.calib_spec(reg, 0)                       # D0 used calibration step 0 for every regime
    if robust:
        sp = dict(sp, robust=ROBUST, name=sp["name"] + "+robust")
    return sp


def _w_mstar(res, reg):
    v = []
    for r in res.values():
        if r["phase"] == "frontier" and r["design"] == "W:" + C.WITNESS[reg] and r["calib"] == 0:
            v.append(r["target"] if r["feasible"] else None)
    assert len(v) == 3
    return C.median_inf(v)


def selection():
    res = C.load_results()
    out = []
    for reg in C.REGIME_ORDER:
        wst = _w_mstar(res, reg)
        rows = [r for r in res.values() if r.get("regime") == reg and r["evals"] == EVALS
                and r["phase"] in ("frontier", "top-f2", "top-te") and r["calib"] == 0]
        by = {}
        for r in rows:
            if r["phase"] in ("top-f2", "top-te"):
                by.setdefault(r["design"], []).append(r)
        f2rank = []
        for d, rs in by.items():
            if d.startswith("F2:"):
                v = [x["target"] if x["feasible"] else None for x in rs]
                f2rank.append((-C.median_inf(v), d))
        f2rank.sort()
        top3 = [d for _m, d in f2rank[:3]]
        te = [r for r in rows if r["phase"] == "top-te" and r["feasible"]]
        best_te = max(te, key=lambda r: r["target"]) if te else None
        sel = {}
        for r in rows:
            if r["phase"] == "frontier":
                if r["design"].startswith("W:"):
                    cat = "witness"
                elif r["feasible"]:
                    cat = "F1"
                else:
                    continue
            else:
                keep = (r["feasible"] and r["target"] >= wst) or r["design"] in top3 \
                    or (best_te is not None and r["key"] == best_te["key"])
                if not keep:
                    continue
                cat = "single-edit" if r["phase"] == "top-f2" else "two-edit"
            sel[r["key"]] = dict(regime=reg, category=cat, design=r["design"], seed=r["seed"],
                                 d0_feasible=r["feasible"], d0_M=r["target"],
                                 d0_M_raw=r.get("target_raw"), params=r["params"],
                                 beats_witness=bool(r["feasible"] and r["target"] >= wst),
                                 top3_single_edit=r["design"] in top3, witness_Mstar=wst,
                                 d0_key=r["key"])
        out += sorted(sel.values(), key=lambda s: (["witness", "single-edit", "two-edit", "F1"]
                                                  .index(s["category"]), s["design"], s["seed"]))
    return out


def _clean(x):
    return json.loads(json.dumps(x, default=str))


def assized_one(s):
    os.environ["OPAMP_V0_TMP"] = TMP
    reg = s["regime"]
    M = C.regime_M(reg)
    text = C.design_text(s["design"])
    sp = regime_spec(reg, robust=False)
    m = O.evaluate(text, s["params"], sp, full=True)          # nominal, as D0's final re-measure
    nom_feas = O.feasible(sp, m)
    rb = O.robust_evaluate(text, s["params"], regime_spec(reg), objective="max:" + M)
    # M at the worst corner: None if any corner is invalid (M is then meaningless there)
    Mc = [r["metrics"].get(M) if r["valid"] else None for r in rb["corners"]]
    rec = dict(s)
    rec.pop("params")
    rec.update(nominal_feasible=nom_feas, nominal_M=m.get(M),
               nominal_M_matches_d0=(s["d0_M_raw"] is not None and m.get(M) is not None
                                     and abs(m[M] - s["d0_M_raw"]) <= 1e-5 * max(1.0, abs(m[M]))),
               nominal_flags=[f for f in m.get("flags", []) if f in O.testbench.INVALID_FLAGS],
               robust_pass=bool(nom_feas and rb["pass"]), robust=rb,
               M_corners={r["corner"]: r["metrics"].get(M) for r in rb["corners"]},
               M_worst_corner=(min([x for x in Mc if x is not None]) if all(x is not None for x in Mc)
                               else None))
    return _clean(rec)


def ph_assized(procs):
    sel = selection()
    path = os.path.join(RESULTS, "assized.jsonl")
    done = set()
    if os.path.exists(path):
        done = {json.loads(ln)["d0_key"] for ln in open(path) if ln.strip()}
    todo = [s for s in sel if s["d0_key"] not in done]
    print("assized: %d selected, %d to run" % (len(sel), len(todo)), flush=True)
    with mp.Pool(min(procs, PROCS_MAX)) as pool, open(path, "a") as fh:
        for rec in pool.imap_unordered(assized_one, todo, chunksize=1):
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            print("%-4s %-11s %-22s s%d nomM=%s robust=%s worst=%s %s" % (
                rec["regime"], rec["category"], rec["design"], rec["seed"], rec["nominal_M"],
                rec["robust_pass"], rec["robust"]["worst_corner"], rec["robust"]["worst_margin"]),
                flush=True)


def resize_jobs():
    sel = selection()
    jobs = []
    for reg in C.REGIME_ORDER:
        top3 = []
        for s in sel:
            if s["regime"] == reg and s["top3_single_edit"] and s["design"] not in top3:
                top3.append(s["design"])
        for d in ["W:" + C.WITNESS[reg]] + top3:
            jobs.append(dict(regime=reg, design=d, seed=1, evals=EVALS,
                             objective="max:" + C.regime_M(reg),
                             category="witness" if d.startswith("W:") else "single-edit"))
    return jobs


def resize_one(j):
    os.environ["OPAMP_V0_TMP"] = TMP
    sp = regime_spec(j["regime"])
    r = O.size(C.design_text(j["design"]), sp, seed=j["seed"], evals=j["evals"],
               objective=j["objective"])
    m = r.get("metrics") or {}
    rec = dict(j)
    rec.update(feasible=r["feasible"], feasible_nominal=r.get("feasible_nominal"),
               target=r["target"], target_raw=r.get("target_raw"), worst_margin=r["worst_margin"],
               worst_margin_robust=r.get("worst_margin_robust"), robust=r.get("robust"),
               params=r["params"], n_fail=r["n_fail"], best_eval=r["best_eval"],
               best_obj=r.get("best_obj"), cpu_s=r["cpu_s"], secs=r["secs"],
               metrics={k: m.get(k) for k in C.SUM_KEYS})
    return _clean(rec)


def ph_resize(procs):
    path = os.path.join(RESULTS, "resize.jsonl")
    done = set()
    if os.path.exists(path):
        done = {(json.loads(ln)["regime"], json.loads(ln)["design"]) for ln in open(path)
                if ln.strip()}
    todo = [j for j in resize_jobs() if (j["regime"], j["design"]) not in done]
    print("resize: %d to run" % len(todo), flush=True)
    with mp.Pool(min(procs, PROCS_MAX)) as pool, open(path, "a") as fh:
        for rec in pool.imap_unordered(resize_one, todo, chunksize=1):
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()
            print("%-4s %-22s feas=%s nominal=%s M=%s worst=%s cpu=%.0f" % (
                rec["regime"], rec["design"], rec["feasible"], rec["feasible_nominal"],
                rec["target"], (rec["robust"] or {}).get("worst_corner"), rec["cpu_s"]), flush=True)


# ------------------------------------------------------------------ report
def _fmt(v, nd=3):
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return "%.0f" % v
        return ("%." + str(nd) + "g") % v if abs(v) < 1 else "%.2f" % v
    return str(v)


def _worst(rb):
    w = [c for c in rb["corners"] if not c["feasible"]]
    if not rb["corners"]:
        return "—"
    c = min(w or rb["corners"], key=lambda c: -math.inf if c["worst_margin"] is None
            else c["worst_margin"])
    if not c["valid"]:
        return "%s: invalid (%s)" % (c["corner"], ",".join(c["flags"]))
    return "%s: %s %+.3f" % (c["corner"], c["worst_constraint"], c["worst_margin"])


def _fails(rb):
    return ",".join(c["corner"] for c in rb["corners"] if not c["feasible"]) or "—"


def ph_report():
    recs = [json.loads(ln) for ln in open(os.path.join(RESULTS, "assized.jsonl")) if ln.strip()]
    order = {k: i for i, k in enumerate(["witness", "single-edit", "two-edit", "F1"])}
    recs.sort(key=lambda r: (C.REGIME_ORDER.index(r["regime"]), order[r["category"]],
                             r["design"], r["seed"]))
    unit = {"R1": "dB", "R23": "MHz·pF/mA", "R4": "V"}
    lines = []
    summ = {}
    for reg in C.REGIME_ORDER:
        lines.append("\n**%s** (M = %s, %s; witness M* %s)\n" % (
            reg, C.regime_M(reg), unit[reg], _fmt(recs[0]["witness_Mstar"]) if False else
            _fmt([r for r in recs if r["regime"] == reg][0]["witness_Mstar"])))
        lines.append("| design | category | seed | nominal M (D0) | ≥ W* | robust | failing corners | "
                     "worst corner: constraint margin | M at worst-M corner |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in recs:
            if r["regime"] != reg:
                continue
            lines.append("| %s | %s | %d | %s%s | %s | **%s** | %s | %s | %s |" % (
                r["design"], r["category"], r["seed"], _fmt(r["nominal_M"]),
                "" if r["nominal_M_matches_d0"] else " (≠ D0!)",
                "yes" if r["beats_witness"] else "", "PASS" if r["robust_pass"] else "fail",
                _fails(r["robust"]), _worst(r["robust"]), _fmt(r["M_worst_corner"])))
            k = (reg, r["category"])
            s = summ.setdefault("%s/%s" % k, {"n": 0, "pass": 0, "failing_corners": 0,
                                               "invalid_corners": 0, "polarity_flip": 0,
                                               "M_keep": []})
            s["n"] += 1
            s["pass"] += int(r["robust_pass"])
            cs = r["robust"]["corners"]
            s["failing_corners"] += sum(1 for c in cs if not c["feasible"])
            s["invalid_corners"] += sum(1 for c in cs if not c["valid"])
            s["polarity_flip"] += int(any("polarity" in c["flags"] for c in cs))
            if r["M_worst_corner"] is not None and r["nominal_M"]:
                s["M_keep"].append(r["M_worst_corner"] / r["nominal_M"])
    for s in summ.values():
        n = float(s["n"])
        s["mean_failing_corners"] = s["failing_corners"] / n
        s["mean_invalid_corners"] = s["invalid_corners"] / n
        mk = sorted(s.pop("M_keep"))
        s["median_M_worst_over_nominal"] = mk[len(mk) // 2] if mk else None
        s["n_M_measured_all_corners"] = len(mk)
    lines.append("\n**Per category** (as sized; 8 corners each unless fewer matched groups)\n")
    lines.append("| regime/category | n | robust pass | mean failing corners | mean invalid corners | "
                 "designs with a polarity flip | median M(worst corner)/M(nominal) |")
    lines.append("|---|---|---|---|---|---|---|")
    for k in sorted(summ, key=lambda k: (C.REGIME_ORDER.index(k.split("/")[0]),
                                          order[k.split("/")[1]])):
        s = summ[k]
        lines.append("| %s | %d | %d | %.1f | %.1f | %d | %s%s |" % (
            k, s["n"], s["pass"], s["mean_failing_corners"], s["mean_invalid_corners"],
            s["polarity_flip"], _fmt(s["median_M_worst_over_nominal"]),
            "" if s["n_M_measured_all_corners"] == s["n"] else
            " (%d of %d valid at all corners)" % (s["n_M_measured_all_corners"], s["n"])))
    rz = []
    p = os.path.join(RESULTS, "resize.jsonl")
    if os.path.exists(p):
        rz = [json.loads(ln) for ln in open(p) if ln.strip()]
        rz.sort(key=lambda r: (C.REGIME_ORDER.index(r["regime"]), r["category"] != "witness",
                               r["design"]))
        lines.append("\n**Re-sized with the gate ON** (max:M, seed 1, 2,500 evals)\n")
        lines.append("| regime | design | robust-feasible | M (gate on) | D0 M* (gate off) | "
                     "nominal feasible | worst corner: constraint margin | CPU s |")
        lines.append("|---|---|---|---|---|---|---|---|")
        mstar = {}
        for r in recs:
            mstar.setdefault((r["regime"], r["design"]), []).append(
                r["d0_M"] if r["d0_feasible"] else None)
        for r in rz:
            v = mstar.get((r["regime"], r["design"]))
            lines.append("| %s | %s | **%s** | %s | %s | %s | %s | %.0f |" % (
                r["regime"], r["design"], "yes" if r["feasible"] else "no", _fmt(r["target"]),
                _fmt(C.median_inf(v)) if v else "—", r["feasible_nominal"],
                _worst(r["robust"]) if r["robust"] else "—", r["cpu_s"]))
    out = {"assized_summary": summ, "n_assized": len(recs),
           "nominal_reproduces_d0": sum(1 for r in recs if r["nominal_M_matches_d0"]),
           "resize": [{k: r[k] for k in ("regime", "design", "feasible", "feasible_nominal", "target",
                                         "cpu_s")} for r in rz],
           "cpu_s_resize": sum(r["cpu_s"] for r in rz)}
    with open(os.path.join(RESULTS, "diagnostic.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    with open(os.path.join(RESULTS, "diagnostic-tables.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ph = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else PROCS_MAX
    if ph == "assized":
        ph_assized(n)
    elif ph == "resize":
        ph_resize(n)
    elif ph == "report":
        ph_report()
    elif ph == "list":
        for s in selection():
            print(s["regime"], s["category"], s["design"], s["seed"], s["d0_M"], s["beats_witness"])
        for j in resize_jobs():
            print("RESIZE", j)
    else:
        raise SystemExit(__doc__)
