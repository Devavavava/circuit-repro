"""E-9 aggregator — reconstructs the whole campaign from per-cell JSONs alone
(crash-safe). Prints the headline, per-goal tables, spend breakdown, coverage,
edit sequences. Reads tmp/e9_results/cell_*.json only; never simulates."""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "e9_results")

GOAL_ORDER = ["G2p", "G4p", "G9", "G1pp", "G7pp", "G11pp"]
GOAL_LABEL = {"G2p": "G2'", "G4p": "G4'", "G9": "G9", "G1pp": "G1''",
              "G7pp": "G7''", "G11pp": "G11''"}
ARMS = ["a", "b", "c"]
ARM_LABEL = {"a": "sizing-only", "b": "random-2stage", "c": "guided-2stage"}


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


def main():
    cells = load()
    goals = [g for g in GOAL_ORDER if any(k[0] == g for k in cells)]
    print(f"# E-9 aggregate — {len(cells)} cells on disk\n")

    # expected cell count
    exp = 0
    seeds_of = {}
    for (g, a, s), d in cells.items():
        seeds_of.setdefault(g, set()).add(s)
    for g in goals:
        exp += len(seeds_of.get(g, set())) * len(ARMS)
    print(f"cells: {len(cells)} (seeds x 3 arms per goal)\n")

    # headline: goals solved per arm
    solved_by_arm = {a: 0 for a in ARMS}
    solved_goals = {a: [] for a in ARMS}
    for g in goals:
        for a in ARMS:
            seeds = sorted(seeds_of.get(g, set()))
            any_solved = any(cells.get((g, a, s), {}).get("solved")
                             for s in seeds)
            if any_solved:
                solved_by_arm[a] += 1
                solved_goals[a].append(GOAL_LABEL[g])
    ng = len(goals)
    print("## HEADLINE")
    for a in ARMS:
        gg = ", ".join(solved_goals[a]) or "none"
        print(f"  arm {a} ({ARM_LABEL[a]:15s}): {solved_by_arm[a]}/{ng}  [{gg}]")
    print()

    # per-goal table
    print("## Per-goal (solved seeds / arm; evals+spice-min to solve)")
    hdr = f"{'goal':7s} {'type':11s} {'B':>5s} {'seeds':>5s} | " + \
          " | ".join(f"arm {a}" for a in ARMS)
    print(hdr)
    for g in goals:
        seeds = sorted(seeds_of.get(g, set()))
        any_d = next(cells[(g, a, s)] for a in ARMS for s in seeds
                     if (g, a, s) in cells)
        row = f"{GOAL_LABEL[g]:7s} {any_d.get('gtype',''):11s} " \
              f"{any_d.get('B',''):>5} {len(seeds):>5} | "
        parts = []
        for a in ARMS:
            ns = sum(1 for s in seeds if cells.get((g, a, s), {}).get("solved"))
            first = None
            for s in seeds:
                d = cells.get((g, a, s), {})
                if d.get("solved"):
                    first = f"@{d.get('evals_to_solve')}ev/" \
                            f"{d.get('spice_min_to_solve')}sm"
                    break
            parts.append(f"{ns}/{len(seeds)} {first or ''}".strip())
        print(row + " | ".join(f"{p:14s}" for p in parts))
    print()

    # spend breakdown (matched-budget parity check + stage split)
    print("## Spend breakdown (mean per cell: total evals / stage1 / stage2 / spice-min)")
    print(f"{'goal':7s} {'arm':14s} {'Σev':>6s} {'s1ev':>6s} {'s2ev':>6s} "
          f"{'spice-min':>10s} {'blame_x':>8s}")
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
            bx = sum(d.get("blame_extra_sims", 0) for d in ds)
            print(f"{GOAL_LABEL[g]:7s} {ARM_LABEL[a]:14s} {ev:6.0f} {s1:6.0f} "
                  f"{s2:6.0f} {sm:10.3f} {bx:8d}")
    print()

    # coverage-correlation (guided arm diagnosis)
    print("## Coverage (guided arm c diagnosis, per goal)")
    print(f"{'goal':7s} {'binding':14s} {'coverage':12s} {'blame_devs':20s} "
          f"{'g_solved':>9s} {'r_solved':>9s}")
    for g in goals:
        seeds = sorted(seeds_of.get(g, set()))
        dc = next((cells[(g, "c", s)] for s in seeds
                   if (g, "c", s) in cells and cells[(g, "c", s)].get("diagnosis")),
                  None)
        diag = dc.get("diagnosis") if dc else {}
        bm = diag.get("binding_metric", "?")
        cov = diag.get("blame_coverage", "?")
        bd = ",".join(diag.get("blame_devices", []) or []) or "-"
        gs = sum(1 for s in seeds if cells.get((g, "c", s), {}).get("solved"))
        rs = sum(1 for s in seeds if cells.get((g, "b", s), {}).get("solved"))
        print(f"{GOAL_LABEL[g]:7s} {bm:14s} {cov:12s} {bd:20s} "
              f"{gs:>9} {rs:>9}")
    print()

    # winning edit sequences
    print("## Winning edit sequences (solved cells only)")
    any_win = False
    for (g, a, s), d in sorted(cells.items()):
        if d.get("solved"):
            any_win = True
            print(f"  {GOAL_LABEL.get(g,g)} arm {a} s{s}: "
                  f"stage={d.get('solved_stage')} edits={d.get('edit_seq')} "
                  f"@ {d.get('evals_to_solve')} evals / "
                  f"{d.get('spice_min_to_solve')} spice-min "
                  f"metrics={d.get('solve_metrics')}")
    if not any_win:
        print("  none (no arm solved any goal)")
    print()

    # falsifier verdict
    print("## Falsifier (E9-TWOSTAGE §5)")
    a_g = set(solved_goals["a"])
    b_g = set(solved_goals["b"])
    c_g = set(solved_goals["c"])
    c_beats = c_g - a_g - b_g
    if c_beats:
        print(f"  arm C solves {sorted(c_beats)} where BOTH A and B do not "
              f"=> two-stage split + guidance LIFTS the E-8 v2 ceiling.")
    elif b_g and not (c_g - b_g):
        print(f"  arm B (random 2-stage) solves {sorted(b_g)} but C adds nothing "
              f"=> the SPLIT helps, GUIDANCE does not (null for guidance).")
    elif not b_g and not c_g:
        print("  BOTH B and C solve ~zero => two-stage does NOT lift this "
              "ceiling; ceiling = move repertoire / editor intelligence "
              "(=> ROADMAP §7). E-8 v2 secondary-negative replicated under split.")
    else:
        print(f"  mixed: A={sorted(a_g)} B={sorted(b_g)} C={sorted(c_g)}")


if __name__ == "__main__":
    main()
