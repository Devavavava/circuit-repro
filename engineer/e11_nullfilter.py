"""E-11 null-filter pre-check: does sizing-only (arm A) at scored budget B=600
solve a candidate fresh goal? A fresh goal is KEPT only if arm A leaves it
unsolved (it must be beyond sizing's demonstrated reach). Uses NO target-circuit
knowledge -- only the task's own cold-start anchor sizing.

This is the null filter the pre-reg requires (arm A at scored budget); running it
on candidate placements before fixing the three fresh goals is the E-8 lesson
applied. Placement numbers are store-derived (see e11_genedit.GOALS docstring).
"""
import os
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(HERE)
LNA = os.path.join(WT, "lna")
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from env import Env  # noqa: E402
import e11_genedit as E  # noqa: E402

# candidate fresh goals: (id, task, ext-constraint, tighten note)
CANDS = {
    "NF_l1":  ("dhruva-l1-t2-a", {"nf_db": {"max": 0.47, "status": "measured"}}),
    "NF_l5":  ("dhruva-l5-t2-a", {"nf_db": {"max": 0.445, "status": "measured"}}),
    "NF_s":   ("dhruva-s-t2-a",  {"nf_db": {"max": 0.538, "status": "measured"}}),
    "S11_l1": ("dhruva-l1-t2-a", {"s11_max_db": {"max": -13.019, "status": "measured"}}),
    "S11_l2": ("dhruva-l2-t2-a", {"s11_max_db": {"max": -13.031, "status": "measured"}}),
    "GE_l2":  ("dhruva-l2-t2-a", {"s21_min_db": {"min": 37.926, "status": "measured"}}),
    "GE_l1":  ("dhruva-l1-t2-a", {"s21_min_db": {"min": 37.935, "status": "measured"}}),
    "IDD_s":  ("dhruva-s-t2-a",  {"idd_ma": {"max": 7.08, "status": "measured"}}),
}


def probe(cid, task_id, ext, seed=1, B=600):
    task = E.get_task(task_id).with_(budget=B, seed=seed)
    env = Env(task, budget=B, seed=seed, logger=None)
    base_spec = env.spec
    ext_s = E.ext_spec_of(base_spec, ext)
    anchor_params = env.row.get("best_params")
    anchor_x = env.arena.encode(anchor_params) if anchor_params else None
    solve = {"solved": False, "evals": None, "metrics": None}

    def record(out):
        if not solve["solved"] and E.ext_feasible(base_spec, ext_s, out["metrics"]):
            solve.update(solved=True, evals=env.n_evals,
                         metrics={k: round(out["metrics"].get(k), 4) for k in
                                  ("nf_db", "s11_max_db", "s21_db", "s21_min_db",
                                   "idd_ma") if out["metrics"].get(k) is not None})

    E._size_topo(env, None, anchor_x, B, seed, record)
    # also report best achieved on the target metric
    _, bm = env.best()
    tgt = list(ext.keys())[0]
    best_tgt = round(bm.get(tgt), 4) if bm and bm.get(tgt) is not None else None
    return {"cand": cid, "task": task_id, "target": tgt,
            "solved_by_sizing": solve["solved"],
            "evals_to_solve": solve["evals"],
            "best_on_target": best_tgt, "solve_metrics": solve["metrics"]}


def main():
    import json
    which = sys.argv[1:] or list(CANDS)
    out = []
    for cid in which:
        task_id, ext = CANDS[cid]
        r = probe(cid, task_id, ext)
        out.append(r)
        verdict = "SOLVED-by-sizing (REJECT)" if r["solved_by_sizing"] \
            else "unsolved (KEEP-eligible)"
        print(f"[{cid}] {task_id} {r['target']} best={r['best_on_target']} "
              f"-> {verdict}", flush=True)
    p = "/home/dpatni/.claude/jobs/a8f610e5/tmp/e11_nullfilter.json"
    json.dump(out, open(p, "w"), indent=2)
    print("wrote", p)


if __name__ == "__main__":
    main()
