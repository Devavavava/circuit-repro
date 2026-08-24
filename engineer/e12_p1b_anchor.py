"""E-12 P1b anchor resolver -- near-miss store anchors for the easy tier.

Binding pre-reg: engineer/E12-TRAINEDIT.md §P1b (user ruling 2026-08-24).

Per easy goal, the P1b anchor is the base-feasible SAME-SPEC topo_labels store
row with the best delta-metric value that still FAILS the goal's delta (nearest
non-passing). Base-feasibility is recomputed from RAW metrics via Spec.feasible
(no stored feasible flag trusted). The anchor's exact recorded sizing is
reconstructed from best_params (the e10_s22_measure.py pattern) and RE-EVALUATED
through ngspice to (a) confirm base-feasibility on recomputed metrics and (b)
confirm it does NOT already pass the extended goal spec (a pre-solved anchor
banks a worthless empty-edit positive). If the nearest candidate passes on
re-eval, the next-nearest non-passing row is taken. If NO base-feasible
non-passing row exists (E2 has no store s22; E3 all base-feasible rows already
pass nf<=1.9), fall back to the standard E-9 reached *-t2-a anchor (recorded).

    python e12_p1b_anchor.py            # resolve + verify all six, write JSON
"""
import sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from env import _bind_runtime_deps, Env, Task
_bind_runtime_deps()
import datastore as ds
from spec import Spec
import tasks

# easy goals: base task + delta metric/cmp/target (calibration.json final).
GOALS = {
    "E1": {"task": "dhruva-s-t2-a", "spec": "dhruva-s",
           "metric": "s21_db", "cmp": "min", "target": 30.5},
    "E2": {"task": "dhruva-s-t2-a", "spec": "dhruva-s",
           "metric": "s22_max_db", "cmp": "max", "target": -3.5},
    "E3": {"task": "dhruva-l2-t2-a", "spec": "dhruva-l2",
           "metric": "nf_db", "cmp": "max", "target": 1.9},
    "E4": {"task": "dhruva-l2-t2-a", "spec": "dhruva-l2",
           "metric": "s21_db", "cmp": "min", "target": 26.0},
    "E5": {"task": "dhruva-l5-t2-a", "spec": "dhruva-l5",
           "metric": "s11_max_db", "cmp": "max", "target": -11.0},
    "E6": {"task": "dhruva-l5-t2-a", "spec": "dhruva-l5",
           "metric": "idd_ma", "cmp": "max", "target": 12.0},
}

OUT = os.path.join(HERE, "data", "e12", "p1b_anchors.json")


def passes_delta(cmp, val, target):
    if val is None:
        return None
    return (val >= target) if cmp == "min" else (val <= target)


def delta_gap(cmp, val, target):
    """Residual gap for a FAILING row (positive natural-unit shortfall)."""
    return (target - val) if cmp == "min" else (val - target)


def near_miss_candidates(g):
    """Base-feasible SAME-SPEC store rows that FAIL the delta, nearest first.
    Base-feasibility recomputed from RAW metrics (no flag trust)."""
    spec = Spec.load(g["spec"])
    rows = [r for r in ds.load("topo_labels")
            if r.get("spec") == g["spec"]
            and (r.get("graph") or {}).get("tokens")
            and r.get("best_params") is not None]
    out = []
    for r in rows:
        m = r.get("metrics")
        if not m:
            continue
        ok, _ = spec.feasible(m)
        if not ok:
            continue
        v = m.get(g["metric"])
        if v is None:
            continue
        if passes_delta(g["cmp"], v, g["target"]):
            continue      # stored value passes -> not a near-miss
        out.append((r, v))
    # nearest non-passing = best delta value that still fails
    if g["cmp"] == "min":
        out.sort(key=lambda t: -t[1])      # highest s21 (closest to min from below)
    else:
        out.sort(key=lambda t: t[1])       # smallest val (closest to max from above)
    return out


def reeval_anchor(task_id, spec, wl, ts):
    """Rebuild the pinned row, reconstruct recorded best_params sizing, and
    re-evaluate through ngspice (e10_s22_measure pattern). Returns
    (metrics, ngspice_calls)."""
    row = None
    for r in ds.load("topo_labels"):
        if r.get("wl_hash") == wl and r.get("ts") == ts and r.get("spec") == spec:
            row = r
            break
    if row is None:
        raise RuntimeError(f"row not found {wl}@{ts}")
    t = Task(f"p1b-anchor-{wl[:8]}", spec, wl, budget=3, seed=1, tier=2,
             ref_ts=ts, ref_evals=row.get("n_evals"), era="current")
    env = Env(t, logger=None)
    out = env.evaluate(params=row.get("best_params"))
    return out["metrics"], env.ngspice_calls


def resolve():
    results = {}
    total_ng = 0
    for gid, g in GOALS.items():
        spec = Spec.load(g["spec"])
        cands = near_miss_candidates(g)
        chosen = None
        tried = []
        for (r, stored_v) in cands:
            m, ng = reeval_anchor(g["task"], g["spec"], r["wl_hash"], r["ts"])
            total_ng += ng
            base_ok, _ = spec.feasible(m)
            reval = m.get(g["metric"])
            passes = passes_delta(g["cmp"], reval, g["target"])
            rec = {"wl": r["wl_hash"], "ts": r["ts"],
                   "stored_delta": round(stored_v, 4),
                   "reeval_delta": (round(reval, 4) if reval is not None else None),
                   "reeval_base_feasible": bool(base_ok),
                   "reeval_passes_delta": bool(passes) if passes is not None else None,
                   "ngspice": ng, "n_evals_recorded": r.get("n_evals")}
            tried.append(rec)
            # accept: base-feasible on re-eval AND does NOT pass the delta
            if base_ok and (passes is False):
                chosen = {"kind": "near_miss", "wl": r["wl_hash"], "ts": r["ts"],
                          "reeval_delta": round(reval, 4),
                          "residual_gap": round(delta_gap(g["cmp"], reval, g["target"]), 4),
                          "stored_delta": round(stored_v, 4),
                          "n_evals_recorded": r.get("n_evals")}
                break
        if chosen is None:
            # fallback: standard E-9 reached *-t2-a anchor
            t = tasks.get(g["task"])
            chosen = {"kind": "fallback_standard", "wl": t.wl_hash,
                      "ts": t.ref_ts, "reeval_delta": None, "residual_gap": None,
                      "stored_delta": None, "n_evals_recorded": None,
                      "fallback_reason": ("no base-feasible same-spec store row "
                                          "that fails the delta on re-eval")}
        results[gid] = {"goal": g, "chosen_anchor": chosen,
                        "candidates_tried": tried,
                        "n_near_miss_candidates": len(cands)}
        print(f"{gid}: anchor={chosen['kind']} wl={chosen['wl']} "
              f"reeval_delta={chosen.get('reeval_delta')} "
              f"gap={chosen.get('residual_gap')}  "
              f"(cands={len(cands)}, tried={len(tried)})")

    doc = {"campaign": "e12-p1b", "phase": "P1b anchor resolution",
           "ngspice_calls": total_ng, "anchors": results,
           "note": ("near-miss = base-feasible same-spec store row with best "
                    "delta value that still fails; base-feasibility recomputed "
                    "from raw metrics; anchor re-evaluated to verify base-feasible "
                    "AND not-passing before use; fallback = standard reached "
                    "*-t2-a anchor.")}
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(doc, fh, indent=2, default=str)
    os.replace(tmp, OUT)
    print(f"\nwrote {OUT}; total ngspice (anchor verify) = {total_ng}")
    return doc


if __name__ == "__main__":
    resolve()
