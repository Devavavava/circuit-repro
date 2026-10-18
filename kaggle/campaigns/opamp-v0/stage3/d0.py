"""Stage 3 — D0 depth test driver (PREREG-OPAMP-V0-D0.md Stage 3 + Amendment 1).

Phases (each resumable on exact job keys; results appended to results/jobs.jsonl):
  frontier [procs]        witness x seeds 1-3 at the regime hard constraints (calibration ladder
                          if infeasible at all 3 seeds), then F1 x seeds 1-3 (max:M, 2,500 evals);
                          shared by the two anchors of a regime (D-O23)
  screen <R|all> [procs]  F2'(anchor) and the 500 two-edit designs, seed 1, 300 evals, max:M
  top [procs]             top-20 F2' per task x seeds 1-3 at 2,500; top-20 two-edit x seed 1 at 2,500
  confirm [procs]         gap per task; for tasks passing the minimum gap: witness + top-5
                          references, margin objective at hard + M >= ref + G/2, seeds 1-3
  analyse                 print the per-task analysis (no runs)
  status                  counts and CPU
Usage: ~/.claude/jobs/7cd7ffc3/tmp/run_cr.sh kaggle/campaigns/opamp-v0/stage3/d0.py <phase> ...
"""
import json
import math
import os
import sys

import d0common as C

INF = math.inf


# ------------------------------------------------------------------ job builders
def w_job(reg, step, seed):
    n = C.WITNESS[reg]
    sp = C.calib_spec(reg, step)
    return C.make_job("frontier", "W:" + n, C.S2.circuit_text(n), sp, "max:" + C.regime_M(reg),
                      seed, C.EVALS_FULL, regime=reg, calib=step)


def f1_job(reg, step, name, seed):
    sp = C.calib_spec(reg, step)
    return C.make_job("frontier", "F1:" + name, C.S2.circuit_text(name), sp,
                      "max:" + C.regime_M(reg), seed, C.EVALS_FULL, regime=reg, calib=step)


def calib_state(reg, res):
    """-> (step, status) with status 'ok' | 'pending' | 'dropped'."""
    for step in range(C.MAX_CALIB + 1):
        recs = [res.get(w_job(reg, step, s)["key"]) for s in C.SEEDS]
        if any(r is None for r in recs):
            return step, "pending"
        if any(r["feasible"] for r in recs):
            return step, "ok"
    return C.MAX_CALIB, "dropped"


def regime_step(reg, res):
    st, status = calib_state(reg, res)
    if status != "ok":
        raise RuntimeError("regime %s calibration %s at step %d" % (reg, status, st))
    return st


def screen_jobs(reg, step, anchor):
    sp = C.calib_spec(reg, step)
    obj = "max:" + C.regime_M(reg)
    jobs = []
    for d in C.f2_designs(anchor):
        jobs.append(C.make_job("screen-f2", "F2:%s:%d" % (anchor, d["i"]), d["netlist"], sp, obj, 1,
                               C.EVALS_SCREEN, regime=reg, anchor=anchor, calib=step))
    for d in C.te_designs(anchor):
        jobs.append(C.make_job("screen-te", "TE:%s:%d" % (anchor, d["j"]), d["netlist"], sp, obj, 1,
                               C.EVALS_SCREEN, regime=reg, anchor=anchor, calib=step))
    return jobs


def rank_key(rec, idx):
    """Screen ranking (D-O24): feasible first by M desc; then infeasible by the sizer's best
    loop objective (closest to feasibility); ties by enumeration index."""
    if rec["feasible"]:
        return (0, -float(rec["target"]), idx)
    bo = rec.get("best_obj")
    return (1, float(bo) if bo is not None else 1e9, idx)


def top_designs(reg, step, anchor, res, kind, n):
    jobs = [j for j in screen_jobs(reg, step, anchor) if j["phase"] == "screen-" + kind]
    recs = []
    for j in jobs:
        r = res.get(j["key"])
        if r is None:
            raise RuntimeError("screen incomplete: %s %s %s" % (reg, anchor, j["design"]))
        recs.append((rank_key(r, int(j["design"].split(":")[2])), j, r))
    recs.sort(key=lambda t: t[0])
    return [(j, r) for _k, j, r in recs[:n]], recs


def full_job(phase, j, seed):
    sp = j["spec"]
    return C.make_job(phase, j["design"], j["netlist"], sp, j["objective"], seed, C.EVALS_FULL,
                      regime=j["regime"], anchor=j["anchor"], calib=j["calib"])


# ------------------------------------------------------------------ analysis
def seed_vals(jobs, res):
    out = []
    for j in jobs:
        r = res.get(j["key"])
        if r is None:
            return None
        out.append(float(r["target"]) if r["feasible"] else None)
    return out


def analyse_task(anchor, reg, res, need_confirm=True):
    step = regime_step(reg, res)
    a = {"anchor": anchor, "regime": reg, "M": C.regime_M(reg), "calib_step": step}
    wv = seed_vals([w_job(reg, step, s) for s in C.SEEDS], res)
    a["witness"] = {"design": "W:" + C.WITNESS[reg], "seeds": wv, "Mstar": C.median_inf(wv)}
    refs = []
    for name in C.F1:
        v = seed_vals([f1_job(reg, step, name, s) for s in C.SEEDS], res)
        refs.append({"design": "F1:" + name, "seeds": v, "Mstar": C.median_inf(v)})
    top, allf2 = top_designs(reg, step, anchor, res, "f2", C.TOP_F2)
    for j, r in top:
        v = seed_vals([full_job("top-f2", j, s) for s in C.SEEDS], res)
        if v is None:
            raise RuntimeError("top-f2 incomplete for %s %s" % (reg, anchor))
        refs.append({"design": j["design"], "seeds": v, "Mstar": C.median_inf(v),
                     "screen": r["target"] if r["feasible"] else None})
    a["f2_screen"] = {"n": len(allf2), "n_feasible": sum(1 for _k, _j, r in allf2 if r["feasible"]),
                      "best": max([r["target"] for _k, _j, r in allf2 if r["feasible"]] or [None],
                                  key=lambda x: -INF if x is None else x)}

    def mean_fin(v):
        f = [x for x in v if x is not None]
        return sum(f) / len(f) if f else -INF
    refs.sort(key=lambda d: (-d["Mstar"], -mean_fin(d["seeds"]), d["design"]))
    a["refs"] = refs
    best = refs[0]
    a["best_ref"] = best["design"]
    refmax = best["Mstar"]
    wst = a["witness"]["Mstar"]
    a["ref_Mstar"] = refmax
    if wst == -INF:
        G = -INF
    elif refmax == -INF:
        G = INF
    else:
        G = wst - refmax
    a["G"] = G
    kind, mn = C.MIN_GAP[reg]
    gmin = mn if kind == "abs" else mn * refmax
    a["G_min"] = gmin
    a["G_rel"] = (G / refmax) if (kind == "rel" and refmax not in (INF, -INF) and refmax > 0) else None
    a["gap_pass"] = bool(G >= gmin and G not in (INF, -INF))
    if refmax == -INF and wst != -INF:
        a["note_gap"] = "all references infeasible (G = +inf); not covered by the pre-reg rule"
    a["thr"] = refmax + G / 2.0 if a["gap_pass"] else None
    a["top5"] = [d["design"] for d in refs[:C.TOP_CONF]]
    # two-edit (step 4): screen + top-20 at 2,500 seed 1
    tetop, allte = top_designs(reg, step, anchor, res, "te", C.TOP_TE)
    te_rows = []
    for j, r in tetop:
        rr = res.get(full_job("top-te", j, 1)["key"])
        te_rows.append({"design": j["design"], "screen": r["target"] if r["feasible"] else None,
                        "full": (None if rr is None else (rr["target"] if rr["feasible"] else None)),
                        "done": rr is not None})
    a["te"] = {"n": len(allte), "n_feasible": sum(1 for _k, _j, r in allte if r["feasible"]),
               "top": te_rows}
    if a["thr"] is not None:
        a["te"]["hits_full"] = [t["design"] for t in te_rows
                                if t["full"] is not None and t["full"] >= a["thr"]]
        a["te"]["hits_screen"] = sum(1 for _k, _j, r in allte
                                     if r["feasible"] and r["target"] >= a["thr"])
        a["two_edit_label"] = "<= 2 edits" if a["te"]["hits_full"] else "not <= 2 edits"
    # confirmation (step 3)
    if a["gap_pass"] and need_confirm:
        sp = C.confirm_spec(reg, step, a["thr"])
        lim = -(G / 4.0) / C.m_scale(a["thr"])
        a["confirm_margin_limit"] = lim
        conf = {}
        for did in ["W:" + C.WITNESS[reg]] + a["top5"]:
            rows = []
            for s in C.SEEDS:
                r = res.get(confirm_job(did, sp, reg, step, s, anchor)["key"])
                rows.append(None if r is None else {
                    "seed": s, "feasible": r["feasible"], "worst_margin": r["worst_margin"],
                    "M": (r["metrics"] or {}).get(C.regime_M(reg)), "valid": r["valid"]})
            conf[did] = rows
        a["confirm"] = conf
        if all(x is not None for v in conf.values() for x in v):
            wrows = conf["W:" + C.WITNESS[reg]]
            w_ok = sum(1 for x in wrows if x["feasible"]) >= 2
            ref_ok = {}
            for did in a["top5"]:
                rows = conf[did]
                ref_ok[did] = all((not x["feasible"]) and (x["worst_margin"] is None
                                                           or x["worst_margin"] <= lim)
                                  for x in rows)
            a["confirm_w_ok"] = w_ok
            a["confirm_refs_ok"] = ref_ok
            a["accepted"] = bool(w_ok and all(ref_ok.values()))
        else:
            a["accepted"] = None            # pending
    else:
        a["accepted"] = False if not a["gap_pass"] else None
    return a


def confirm_job(did, sp, reg, step, seed, anchor):
    return C.make_job("confirm", did, C.design_text(did), sp, "margin", seed, C.EVALS_FULL,
                      regime=reg, anchor=anchor, calib=step)


def verdict(tasks):
    acc = [t for t in tasks if t["accepted"]]
    deep = [t for t in acc if t.get("two_edit_label") == "not <= 2 edits"]
    if len(acc) >= 4 and len(deep) >= 2:
        v = "GO"
    elif len(acc) <= 1:
        v = "STOP"
    else:
        v = "DISCUSS"
    return {"verdict": v, "n_accepted": len(acc), "n_accepted_not_le2": len(deep),
            "accepted": ["%s/%s" % (t["anchor"], t["regime"]) for t in acc]}


# ------------------------------------------------------------------ phases
def ph_frontier(procs):
    while True:
        res = C.load_results()
        jobs, pend = [], False
        for reg in C.REGIME_ORDER:
            st, status = calib_state(reg, res)
            if status == "pending":
                pend = True
                jobs += [w_job(reg, st, s) for s in C.SEEDS]
                if st == 0:                         # speculative: F1 at step 0
                    jobs += [f1_job(reg, 0, n, s) for n in C.F1 for s in C.SEEDS]
        if not pend:
            break
        if not C.run_jobs(jobs, procs, "frontier-W"):
            return False
    res = C.load_results()
    jobs = []
    for reg in C.REGIME_ORDER:
        st, status = calib_state(reg, res)
        print("calibration %s: step %d (%s)" % (reg, st, status), flush=True)
        if status == "ok":
            jobs += [f1_job(reg, st, n, s) for n in C.F1 for s in C.SEEDS]
    return C.run_jobs(jobs, procs, "frontier-F1")


def ph_screen(which, procs):
    res = C.load_results()
    regs = C.REGIME_ORDER if which == "all" else which.split(",")
    jobs = []
    for reg in regs:
        st = regime_step(reg, res)
        for anchor in C.ANCHORS:
            jobs += screen_jobs(reg, st, anchor)
    return C.run_jobs(jobs, procs, "screen-" + which)


def ph_top(procs):
    res = C.load_results()
    jobs = []
    for anchor, reg in C.TASKS:
        st = regime_step(reg, res)
        top, _ = top_designs(reg, st, anchor, res, "f2", C.TOP_F2)
        jobs += [full_job("top-f2", j, s) for j, _r in top for s in C.SEEDS]
    for anchor, reg in C.TASKS:
        st = regime_step(reg, res)
        top, _ = top_designs(reg, st, anchor, res, "te", C.TOP_TE)
        jobs += [full_job("top-te", j, 1) for j, _r in top]
    return C.run_jobs(jobs, procs, "top")


def ph_confirm(procs):
    res = C.load_results()
    jobs = []
    for anchor, reg in C.TASKS:
        a = analyse_task(anchor, reg, res, need_confirm=False)
        print("%-13s %-3s W*=%s ref*=%s (%s) G=%s min=%s pass=%s" % (
            anchor, reg, a["witness"]["Mstar"], a["ref_Mstar"], a["best_ref"], a["G"], a["G_min"],
            a["gap_pass"]), flush=True)
        if a["gap_pass"]:
            sp = C.confirm_spec(reg, a["calib_step"], a["thr"])
            for did in ["W:" + C.WITNESS[reg]] + a["top5"]:
                jobs += [confirm_job(did, sp, reg, a["calib_step"], s, anchor) for s in C.SEEDS]
    return C.run_jobs(jobs, procs, "confirm")


def ph_analyse():
    res = C.load_results()
    tasks = [analyse_task(a, r, res) for a, r in C.TASKS]
    for t in tasks:
        print(json.dumps({k: t[k] for k in ("anchor", "regime", "calib_step", "ref_Mstar", "best_ref",
                                           "G", "G_min", "gap_pass", "thr", "accepted")},
                         default=str))
        print("   W", t["witness"]["seeds"], "top5", t["top5"], "TE", t.get("two_edit_label"))
    print(verdict(tasks))
    print("CPU total %.2f h" % C.cpu_total_h(res))


def ph_status():
    res = C.load_results()
    cnt = {}
    for r in res.values():
        k = (r["phase"], r.get("regime"), r.get("anchor"))
        cnt[k] = cnt.get(k, 0) + 1
    for k in sorted(cnt, key=str):
        print(k, cnt[k])
    print("records %d, CPU total %.3f h" % (len(res), C.cpu_total_h(res)))


def main():
    ph = sys.argv[1]
    if ph == "frontier":
        ok = ph_frontier(int(sys.argv[2]) if len(sys.argv) > 2 else C.PROCS_MAX)
    elif ph == "screen":
        ok = ph_screen(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else C.PROCS_MAX)
    elif ph == "top":
        ok = ph_top(int(sys.argv[2]) if len(sys.argv) > 2 else C.PROCS_MAX)
    elif ph == "confirm":
        ok = ph_confirm(int(sys.argv[2]) if len(sys.argv) > 2 else C.PROCS_MAX)
    elif ph == "analyse":
        ph_analyse()
        ok = True
    elif ph == "status":
        ph_status()
        ok = True
    else:
        raise SystemExit(__doc__)
    print("PHASE %s %s" % (ph, "DONE" if ok else "STOPPED"), flush=True)
    ph_status()


if __name__ == "__main__":
    main()
