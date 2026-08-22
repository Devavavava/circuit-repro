"""E-11 aggregator -- reconstructs the whole campaign from per-cell JSONs alone
(crash-safe). Prints headline, per-goal table (solved + SPICE-min-to-first-
feasible), spend breakdown (incl. generation minutes), edit-log row counts, and
the E-11 falsifier verdict. Reads tmp/e11_results/cell_*.json + the edit log;
never simulates."""
import glob
import json
import os

RESULTS = os.path.join("/home/dpatni/.claude/jobs/a8f610e5/tmp", "e11_results")
EDIT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "edit_log", "e11_edits.jsonl")

GOAL_ORDER = ["G1pp", "G9", "G7pp", "GA", "GB", "GC"]
GOAL_LABEL = {"G1pp": "G1''", "G9": "G9", "G7pp": "G7''",
              "GA": "GA", "GB": "GB", "GC": "GC"}
ARMS = ["a", "b", "c"]
ARM_LABEL = {"a": "sizing-only", "b": "primitive-2stg", "c": "genedit-2stg"}


def load():
    cells = {}
    for p in sorted(glob.glob(os.path.join(RESULTS, "cell_*.json"))):
        try:
            with open(p) as fh:
                d = json.load(fh)
            cells[(d["goal"], d["arm"], d["seed"])] = d
        except Exception as e:
            print("  WARN unreadable", p, e)
    return cells


def edit_log_stats():
    if not os.path.exists(EDIT_LOG):
        return {"total": 0}
    n = 0
    by = {}
    dec_ok = l0_ok = 0
    with open(EDIT_LOG) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            n += 1
            by[r.get("arm")] = by.get(r.get("arm"), 0) + 1
            dec_ok += int(bool(r.get("decode_ok")))
            l0_ok += int(bool(r.get("l0_pass")))
    return {"total": n, "by_arm": by, "decode_ok": dec_ok, "l0_pass": l0_ok}


def main():
    cells = load()
    goals = [g for g in GOAL_ORDER if any(k[0] == g for k in cells)]
    print(f"# E-11 aggregate -- {len(cells)} cells on disk\n")
    seeds_of = {}
    for (g, a, s), d in cells.items():
        seeds_of.setdefault(g, set()).add(s)

    # headline
    solved_goals = {a: [] for a in ARMS}
    first_feas = {}     # (g,a) -> spice_min_to_solve (min over seeds)
    for g in goals:
        seeds = sorted(seeds_of.get(g, set()))
        for a in ARMS:
            sm = [cells[(g, a, s)].get("spice_min_to_solve")
                  for s in seeds if cells.get((g, a, s), {}).get("solved")]
            sm = [x for x in sm if x is not None]
            if any(cells.get((g, a, s), {}).get("solved") for s in seeds):
                solved_goals[a].append(g)
            if sm:
                first_feas[(g, a)] = min(sm)
    ng = len(goals)
    print("## HEADLINE (goals solved per arm)")
    for a in ARMS:
        gg = ", ".join(GOAL_LABEL[x] for x in solved_goals[a]) or "none"
        print(f"  arm {a} ({ARM_LABEL[a]:15s}): {len(solved_goals[a])}/{ng}  [{gg}]")
    print()

    # per-goal table
    print("## Per-goal (solved seeds/arm; SPICE-min to first feasible)")
    print(f"{'goal':6s} {'type':11s} {'kind':6s} {'B':>5s} {'N':>3s} | "
          + " | ".join(f"{ARM_LABEL[a]:16s}" for a in ARMS))
    for g in goals:
        seeds = sorted(seeds_of.get(g, set()))
        any_d = next(cells[(g, a, s)] for a in ARMS for s in seeds
                     if (g, a, s) in cells)
        row = (f"{GOAL_LABEL[g]:6s} {any_d.get('gtype',''):11s} "
               f"{any_d.get('kind',''):6s} {any_d.get('B',''):>5} "
               f"{len(seeds):>3} | ")
        parts = []
        for a in ARMS:
            ns = sum(1 for s in seeds if cells.get((g, a, s), {}).get("solved"))
            ff = first_feas.get((g, a))
            parts.append(f"{ns}/{len(seeds)}" + (f" @{ff}sm" if ff else ""))
        print(row + " | ".join(f"{p:16s}" for p in parts))
    print()

    # spend breakdown incl generation minutes
    print("## Spend (mean/cell: Σev / s1ev / s2ev / spice-min / gen-min)")
    print(f"{'goal':6s} {'arm':16s} {'Σev':>6s} {'s1ev':>6s} {'s2ev':>6s} "
          f"{'spice-min':>10s} {'gen-min':>9s} {'#prop':>7s}")
    for g in goals:
        seeds = sorted(seeds_of.get(g, set()))
        for a in ARMS:
            ds = [cells[(g, a, s)] for s in seeds if (g, a, s) in cells]
            if not ds:
                continue
            n = len(ds)
            ev = sum(d.get("evals_spent", 0) for d in ds) / n
            s1 = sum(d.get("stage1_evals", 0) for d in ds) / n
            s2 = sum(d.get("stage2_evals", 0) for d in ds) / n
            sm = sum(d.get("spice_min_total", 0) for d in ds) / n
            gm = sum(d.get("gen_min_total", 0) for d in ds) / n
            pr = sum(d.get("n_proposals_logged", 0) for d in ds)
            print(f"{GOAL_LABEL[g]:6s} {ARM_LABEL[a]:16s} {ev:6.0f} {s1:6.0f} "
                  f"{s2:6.0f} {sm:10.3f} {gm:9.2f} {pr:7d}")
    print()

    # winning edits
    print("## Winning edits (solved cells)")
    any_win = False
    for (g, a, s), d in sorted(cells.items()):
        if d.get("solved"):
            any_win = True
            print(f"  {GOAL_LABEL.get(g,g)} arm {a} s{s}: "
                  f"stage={d.get('solved_stage')} edit={d.get('edit_seq')} "
                  f"@ {d.get('evals_to_solve')}ev / "
                  f"{d.get('spice_min_to_solve')}sm  m={d.get('solve_metrics')}")
    if not any_win:
        print("  none (no arm solved any goal)")
    print()

    # edit log
    els = edit_log_stats()
    print("## Edit log")
    print(f"  total rows: {els.get('total')}  by_arm={els.get('by_arm')}  "
          f"decode_ok={els.get('decode_ok')}  l0_pass={els.get('l0_pass')}")
    print()

    # falsifier
    print("## Falsifier (E11-GENEDIT §7)")
    a_g = set(solved_goals["a"])
    b_g = set(solved_goals["b"])
    c_g = set(solved_goals["c"])
    c_beats = c_g - a_g - b_g
    # faster-to-first-feasible on a shared solve
    faster = []
    for g in goals:
        if (g, "c") in first_feas:
            others = [first_feas[(g, x)] for x in ("a", "b")
                      if (g, x) in first_feas]
            if others and first_feas[(g, "c")] < min(others):
                faster.append(g)
    if c_beats:
        print(f"  C solves {sorted(GOAL_LABEL[x] for x in c_beats)} where BOTH "
              f"A and B do not => generic regrow LIFTS the E-9 ceiling. "
              f"FALSIFIER NOT MET.")
    elif faster:
        print(f"  C ties on solves but is FASTER to first-feasible on "
              f"{sorted(GOAL_LABEL[x] for x in faster)} => weaker positive for "
              f"the channel. FALSIFIER NOT MET (speed sub-reading).")
    else:
        print("  C solves no goal A and B both leave unsolved, and is not faster "
              "to first-feasible on any shared solve => FALSIFIER MET: generic "
              "regrow fails for this goal set; the next lever must change the "
              "proposal mechanism itself (learned priors on THIS edit log, "
              "critic-in-the-loop), not budget or screening.")


if __name__ == "__main__":
    main()
