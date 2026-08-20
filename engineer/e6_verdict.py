"""engineer/e6_verdict.py -- apply the E6-BUDGET.md §6 acceptance criterion + the
ROADMAP G1 falsifier EXACTLY as pre-registered, to the full-tier boards.

Reads (does not recompute cells): e6_full_v0.json (in-house) + e6_ext_v0.json
(externals). Emits the per-track win/loss reading and the family verdict, plus the
G0 time-to-competence metrics (SPICE-minutes to first feasible, to tier-2 feasible,
wall-clock) for both arms. No thresholds are invented here -- the rule is the doc's.

    python engineer/e6_verdict.py
"""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import env as EV                                              # noqa: E402

DATA = EV.DATA_DIR


def _load(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _arm_won_cell(arms):
    """Per-cell winner by the PROTOCOL §5 metric: feasible-rate, tiebroken by
    median best-obj (lower is better). Returns 'racing'|'incumbent'|'tie'."""
    inc, rac = arms.get("incumbent"), arms.get("racing")
    if not inc or not rac:
        return "incomplete"
    if inc["n_feasible"] != rac["n_feasible"]:
        return "racing" if rac["n_feasible"] > inc["n_feasible"] else "incumbent"
    im, rm = inc.get("best_obj_median"), rac.get("best_obj_median")
    if im is None or rm is None:
        return "tie"
    if abs(im - rm) <= 1e-9:
        return "tie"
    return "racing" if rm < im else "incumbent"


def _median_rank(per_cell):
    from collections import defaultdict
    ranks = defaultdict(list)
    for _c, arms in per_cell.items():
        order = sorted([(a, d) for a, d in arms.items() if a in ("incumbent", "racing")],
                       key=lambda kv: (-kv[1]["n_feasible"],
                                       (kv[1]["best_obj_median"]
                                        if kv[1].get("best_obj_median") is not None
                                        else float("inf"))))
        for i, (arm, _) in enumerate(order, start=1):
            ranks[arm].append(i)
    return {a: round(statistics.median(rs), 3) for a, rs in ranks.items()}, \
           {a: rs for a, rs in ranks.items()}


def _track_verdict(median_rank):
    """§6 acceptance on ONE track: racing matches-or-beats iff its median-rank <=
    incumbent's. Returns 'racing_wins_or_ties' | 'racing_loses'."""
    if median_rank.get("racing") is None or median_rank.get("incumbent") is None:
        return "incomplete"
    return ("racing_wins_or_ties" if median_rank["racing"] <= median_rank["incumbent"]
            else "racing_loses")


def main():
    full = _load("e6_full_v0.json")
    ext = _load("e6_ext_v0.json")
    out = {"tracks": {}}

    # ---- in-house ----
    inhouse_pc = {t: {a: d[a] for a in ("incumbent", "racing") if a in d}
                  for t, d in full["per_task"].items()}
    mr, _ = _median_rank(inhouse_pc)
    v = _track_verdict(mr)
    per_task_win = {t: _arm_won_cell(inhouse_pc[t]) for t in inhouse_pc}
    out["tracks"]["in_house"] = {"median_rank": mr, "verdict": v,
                                 "per_task_winner": per_task_win,
                                 "racing_wins": sum(1 for x in per_task_win.values() if x == "racing"),
                                 "incumbent_wins": sum(1 for x in per_task_win.values() if x == "incumbent"),
                                 "ties": sum(1 for x in per_task_win.values() if x == "tie"),
                                 "n_tasks": len(per_task_win)}

    # ---- externals (per track: amp, ldo) ----
    if ext:
        for track, per_cell in ext["per_track"].items():
            pc = {c: {a: d[a] for a in ("incumbent", "racing") if a in d}
                  for c, d in per_cell.items()}
            mr_t, _ = _median_rank(pc)
            v_t = _track_verdict(mr_t)
            per_cell_win = {c: _arm_won_cell(pc[c]) for c in pc}
            out["tracks"][f"ext_{track}"] = {
                "median_rank": mr_t, "verdict": v_t,
                "per_cell_winner": per_cell_win,
                "racing_wins": sum(1 for x in per_cell_win.values() if x == "racing"),
                "incumbent_wins": sum(1 for x in per_cell_win.values() if x == "incumbent"),
                "ties": sum(1 for x in per_cell_win.values() if x == "tie"),
                "n_cells": len(per_cell_win)}

    # ---- the falsifier (ROADMAP G1, verbatim) ----
    # "if racing loses at matched budget on the in-house tasks AND both external
    #  tracks, budget-splitting dies as a family." -> family falsifier iff racing
    #  loses on ALL THREE tracks. Anything else is where-it-helps / mixed (OQ-3).
    tv = {k: out["tracks"][k]["verdict"] for k in out["tracks"]}
    have_ext = "ext_amp" in tv and "ext_ldo" in tv
    losses = [k for k, x in tv.items() if x == "racing_loses"]
    wins = [k for k, x in tv.items() if x == "racing_wins_or_ties"]
    if not have_ext:
        family = "INCOMPLETE -- externals not both present"
    elif len(losses) == 3:
        family = ("FAMILY FALSIFIER MET: racing loses at matched budget on the "
                  "in-house tasks AND both external tracks -- budget-splitting "
                  "dies as a family (ROADMAP G1).")
    elif len(wins) == 3:
        family = ("ACCEPTANCE MET on all three tracks: racing matches-or-beats the "
                  "full-budget incumbent at matched budget in-house AND on both "
                  "external tracks (E6-BUDGET.md §6).")
    else:
        family = (f"MIXED / where-it-helps (OQ-3 reading): racing wins-or-ties on "
                  f"{sorted(wins)} and loses on {sorted(losses)}. Not the family "
                  f"falsifier (that requires a loss on ALL THREE tracks); not full "
                  f"acceptance either. Reported as a where-it-helps result.")
    out["falsifier_tracks_lost"] = losses
    out["acceptance_tracks_won"] = wins
    out["family_verdict"] = family

    # ---- G0 time-to-competence (G0-FAIRNESS §4): SPICE-minutes to first feasible,
    #      to tier-2 feasible (== first feasible here: every in-house task is tier-2,
    #      so its feasibility gate IS the tier-2 gate), and wall-clock, per arm. All
    #      three are read from the boards' per-cell stamps -- no re-sim. Under the
    #      shared pool both arms carry the same contention, so the ARM-vs-ARM read is
    #      fair even where absolute wall is inflated (recorded deviation).
    g0 = {"note": ("SPICE-minutes and wall are per-eval wall stamps summed to first "
                   "feasible; tier-2-feasible == first-feasible (all in-house tasks "
                   "are tier-2). Both arms share pool contention -> arm-vs-arm fair."),
          "in_house": {}}
    for t, d in full["per_task"].items():
        row = {}
        for arm in ("incumbent", "racing"):
            a = d.get(arm, {})
            row[arm] = {
                "n_feasible": a.get("n_feasible"),
                "spice_min_to_first_feasible_median": a.get("spice_min_to_first_feasible_median"),
                "evals_to_first_feasible_median": a.get("evals_to_first_feasible_median"),
                "sim_s_total": a.get("sim_s_total"),
            }
        g0["in_house"][t] = row
    # aggregate SPICE-min-to-first-feasible over the tasks where BOTH arms had >=1
    # feasible seed (a fair paired read)
    paired = []
    for t, row in g0["in_house"].items():
        i = row["incumbent"]["spice_min_to_first_feasible_median"]
        r = row["racing"]["spice_min_to_first_feasible_median"]
        if i is not None and r is not None:
            paired.append((t, i, r))
    g0["paired_spice_min_first_feasible"] = {
        "tasks": [t for t, _i, _r in paired],
        "incumbent_median": (round(statistics.median([i for _t, i, _r in paired]), 4)
                             if paired else None),
        "racing_median": (round(statistics.median([r for _t, _i, r in paired]), 4)
                          if paired else None)}
    out["g0_time_to_competence"] = g0
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    sys.exit(main())
