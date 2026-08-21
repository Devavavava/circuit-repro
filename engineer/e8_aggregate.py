"""Aggregate the E-8 scored ladder per-cell result files into the headline table,
per-goal detail, and the falsifier verdict. Reads .claude/jobs/a8f610e5/tmp/
e8_results/cell_*.json; prints a Markdown block for E8-LADDER.md ## Scored results.
"""
import glob
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "e8_results")
GOALS = ["G1", "G8", "G9", "G10"]
ARMS = ["a", "b", "c"]
ARM_NAME = {"a": "sizing-null", "b": "random-edit", "c": "blame-guided"}
GOAL_DESC = {
    "G1": "dhruva-l1  S21>=30 dB (gain wall, reached 26.32)",
    "G8": "dhruva-l5  Idd<=10.5 mA @ S21>=22.3 (reached Idd 12.92)",
    "G9": "dhruva-l5  s21_ripple_db<=3 (reached 15.18)",
    "G10": "dhruva-s   s21_ripple_db<=3 (reached 12.99)",
}


def load():
    cells = {}
    for f in sorted(glob.glob(os.path.join(RES, "cell_*.json"))):
        d = json.load(open(f))
        cells[(d["goal"], d["arm"], d["seed"])] = d
    return cells


def main():
    cells = load()
    n = len(cells)
    print(f"<!-- aggregated from {n} cells -->\n")

    # goals-solved per arm: a goal counts as solved by an arm if solved in >=1 seed
    solved_any = {a: 0 for a in ARMS}
    solved_seed_counts = {(g, a): 0 for g in GOALS for a in ARMS}
    for g in GOALS:
        for a in ARMS:
            k = sum(1 for s in range(1, 6)
                    if cells.get((g, a, s), {}).get("solved"))
            solved_seed_counts[(g, a)] = k
            if k > 0:
                solved_any[a] += 1

    print("### Headline: goals solved per arm at matched budget (600 evals/cell, N=5)\n")
    print("| arm | goals solved (>=1 seed) / 4 | goal-seeds solved / 20 |")
    print("|---|:--:|:--:|")
    for a in ARMS:
        gs = sum(solved_seed_counts[(g, a)] for g in GOALS)
        print(f"| ({a}) {ARM_NAME[a]} | **{solved_any[a]}/4** | {gs}/20 |")

    # time distribution per arm over solved (goal,seed) cells
    print("\n### Time-to-solve distribution per arm (SPICE-minutes, over solved cells)\n")
    print("| arm | n solved cells | median spice-min | min | max | median evals |")
    print("|---|:--:|--:|--:|--:|--:|")
    for a in ARMS:
        sm = [c["spice_min_to_solve"] for c in cells.values()
              if c["arm"] == a and c["solved"] and c["spice_min_to_solve"] is not None]
        ev = [c["evals_to_solve"] for c in cells.values()
              if c["arm"] == a and c["solved"] and c["evals_to_solve"] is not None]
        if sm:
            print(f"| ({a}) {ARM_NAME[a]} | {len(sm)} | {statistics.median(sm):.4f} "
                  f"| {min(sm):.4f} | {max(sm):.4f} | {statistics.median(ev):.0f} |")
        else:
            print(f"| ({a}) {ARM_NAME[a]} | 0 | -- | -- | -- | -- |")

    # per-goal detail
    print("\n### Per-goal detail (solved y/n per seed, evals & spice-min to solve, winning edits)\n")
    for g in GOALS:
        print(f"\n**{g}** — {GOAL_DESC[g]}\n")
        print("| arm | solved seeds | evals-to-solve (per solved seed) | spice-min-to-solve | winning edit sequences |")
        print("|---|:--:|---|---|---|")
        for a in ARMS:
            rows = [cells.get((g, a, s)) for s in range(1, 6)]
            rows = [r for r in rows if r]
            k = sum(1 for r in rows if r["solved"])
            ev = [f"s{r['seed']}:{r['evals_to_solve']}" for r in rows if r["solved"]]
            sm = [f"s{r['seed']}:{r['spice_min_to_solve']}" for r in rows if r["solved"]]
            edits = sorted({tuple(r["edit_seq"]) for r in rows
                            if r["solved"] and r["edit_seq"]})
            edstr = "; ".join(" -> ".join(e) for e in edits) if edits else (
                "(none)" if a != "a" else "0 edits (sizing-only)")
            print(f"| ({a}) {ARM_NAME[a]} | {k}/5 | {', '.join(ev) or '--'} "
                  f"| {', '.join(sm) or '--'} | {edstr} |")
        # diagnosis recorded for arm c
        dc = next((cells.get((g, "c", s)) for s in range(1, 6)
                   if cells.get((g, "c", s))), None)
        if dc and dc.get("diagnosis"):
            di = dc["diagnosis"]
            print(f"\n  arm (c) auto-diagnosis @ warm anchor: binding_metric="
                  f"`{di['binding_metric']}` (probe verdict `{di['verdict']}`), "
                  f"blame devices `{di['blame_devices']}` (coverage "
                  f"`{di['blame_coverage']}`).")

    # falsifier
    print("\n### Falsifier (pre-stated §6, applied verbatim)\n")
    b, c = solved_any["b"], solved_any["c"]
    print(f"> If blame-guided (c) solves no more goals than random-edit (b) at the "
          f"matched budget — and is no faster in SPICE-minutes on the goals both "
          f"solve — then the Q3 diagnosis->intervention integration "
          f"(blame.py+binding_probe.py -> move prior) is REFUTED for this ladder.\n")
    print(f"Measured at matched budget: blame-guided (c) solved **{c}/4**, "
          f"random-edit (b) solved **{b}/4**.")
    # speed comparison on goals both solve
    both = [g for g in GOALS if solved_seed_counts[(g, "b")] > 0
            and solved_seed_counts[(g, "c")] > 0]
    if c > b:
        print(f"\n**VERDICT: NOT refuted** — blame-guided solves MORE goals than "
              f"random-edit ({c} > {b}).")
    elif c == b:
        # tie on count: compare speed on shared goals
        faster = None
        if both:
            cmed = statistics.median(
                [cells[(g, "c", s)]["spice_min_to_solve"] for g in both
                 for s in range(1, 6)
                 if cells.get((g, "c", s), {}).get("solved")])
            bmed = statistics.median(
                [cells[(g, "b", s)]["spice_min_to_solve"] for g in both
                 for s in range(1, 6)
                 if cells.get((g, "b", s), {}).get("solved")])
            faster = cmed < bmed
            print(f"\nGoals both solve: {both}. Median spice-min-to-solve: "
                  f"c={cmed:.4f} vs b={bmed:.4f}.")
        if faster:
            print(f"\n**VERDICT: NOT refuted on speed** — equal goal count but "
                  f"blame-guided is faster in SPICE-minutes on shared goals.")
        else:
            print(f"\n**VERDICT: REFUTED for this ladder** — blame-guided solves "
                  f"no more goals than random-edit ({c} = {b}) and is not faster "
                  f"on the goals both solve. Per OQ-5 this refutes the blame "
                  f"integration FOR THIS LADDER and returns the instruments to "
                  f"validation; no broader claim.")
    else:
        print(f"\n**VERDICT: REFUTED for this ladder** — blame-guided solves FEWER "
              f"goals than random-edit ({c} < {b}). Per OQ-5, refuted for this "
              f"ladder only.")

    # secondary negative: both ~zero -> repertoire finding
    if b == 0 and c == 0:
        a_solved = solved_any["a"]
        print(f"\n**Secondary negative (pre-stated §6):** both edit arms solve "
              f"~zero structural goals — the finding points at the ruled primitive "
              f"repertoire (E-7 P1-P5/P7/add_and_connect), not at the diagnosis. "
              f"(sizing-null solved {a_solved}/4: any sizing-null solve flags a "
              f"goal as sizing-reachable, see below.)")

    # sizing-reachable flag (arm a)
    sr = [g for g in GOALS if solved_seed_counts[(g, "a")] > 0]
    print(f"\n**Sizing-null (arm a) at 600 evals:** solved {solved_any['a']}/4"
          + (f" — goals {sr} cleared by sizing alone at the scored budget "
             f"(flagged sizing-reachable; the §8 smoke had marked them RESISTED at "
             f"150 evals, so this is a budget-scaled re-read, recorded not smoothed)."
             if sr else " — all four resist sizing-only at the scored budget too, "
             "consistent with the §8 null-filter."))


if __name__ == "__main__":
    main()
