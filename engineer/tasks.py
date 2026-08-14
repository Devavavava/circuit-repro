"""engineer/tasks.py -- the benchmark registry v0 of the `engineer` line.

The charter's E-2 item ("benchmark curation + scoring protocol") starts here: a
frozen list of (spec, topology, tier, budget, reference) tuples that any search,
agent or loop can be scored on, with the numbers a claim has to be stated
against attached to each one.

WHAT A TASK IS PINNED TO, AND WHY EACH PIN EXISTS
-------------------------------------------------
    spec        one of `lna/specs/*.yaml`, unchanged. No spec is invented here:
                a benchmark that ships its own specs benchmarks its own specs.
    wl_hash     a stored topology, rebuildable from its L2 row's token graph.
    ref_ts      the EXACT stored L2 row the budget and reference numbers come
                from. `(wl_hash, spec)` alone is not a pin -- five of the eight
                tasks below have two or more stored rows, and
                `null_sizer.build_task` takes `rows[-1]`, so one append to the
                store would silently move a "frozen" budget. `env._pinned_row`
                fails loudly if the pinned row is gone.
    budget      ngspice EVALS, matched to that row's `n_evals` (the S11/AnalogGym
                rule: baselines are compute-matched or they are decoration). One
                eval is two ngspice calls wherever the spec gates NF, for every
                arm alike.
    tier        which gate the task is judged at. See the tier-3 note below.
    era         `current` iff the reference row was produced after the
                2026-08-10 multi-finger cutover (`zoaf_cfg.w_finger == 2e-6`).
                FINDINGS §43.1 measured 1,109 of 1,215 stored designs era-stale
                on at least one metric (median dNF -2.1 dB), so an era stamp is
                not bookkeeping -- it is the difference between a reference
                number and a number from a simulator that no longer exists.

SELECTION RULE (one rule, applied to the store, so the table is auditable)
-------------------------------------------------------------------------
Among the L2 rows for a (spec, wl_hash) that carry both a token graph and an
eval count: prefer the rows that carry a `best_obj` (a reference without a
comparable objective is a weaker reference), then take the most recent. Where a
current-era row exists it is preferred over a pre-cutover one; where none does,
the task ships with `era: "pre-cutover"` stamped rather than being quietly
dropped or quietly compared. `--check` re-runs this rule against the live store
and reports any drift from the pins below.

THERE IS NO TIER-3 TASK, AND THIS IS NOT AN OVERSIGHT
-----------------------------------------------------
Tier 3 is linearity. Every spec in `lna/specs/` carries `iip3_dbm` with
`status: unsupported`, which `spec.feasible` skips and `spec.report` prints as
UNMEASURED -- so a "tier-3 task" today would be a tier-2 task with a label on
it. WP-LIN's two-tone harness is what binds `iip3_dbm`; the tier-3 rungs of this
registry get written the day it does, not before. (`--check` asserts the
condition, so the day it changes, this file's claim fails rather than rots.)

    python engineer/tasks.py --list
    python engineer/tasks.py --list --long
    python engineer/tasks.py --check
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from env import Task, _bind_runtime_deps        # noqa: E402

_bind_runtime_deps()
import datastore as ds                          # noqa: E402
from spec import Spec                           # noqa: E402


# --------------------------------------------------------------- the registry
# Frozen 2026-08-14 against `lna/data/topo_labels.jsonl` at 4,074 L2 rows.
# `ref_evals` is the pinned row's own `n_evals`; `budget` equals it except (a)
# where a task exists to be cheap (the smoke) or (b) where the pinned row is an
# era-relabeled row (n_evals=0 by construction) and the budget is inherited from
# the original campaign -- see wideband-sdr-t2-a and R-2 in 00-CHARTER.md §7.
_ROWS = [
    # id                    spec            wl_hash             dev  budget  ref_evals  ref_ts                       feas   ref_obj              era
    ("wifi24-smoke",        "wifi24",       "4b351a49fa6e4f23",  10,   150,     336, "2026-08-11T07:31:52+00:00", True,  -0.7324616666666666, "current",
     "The cheap end-to-end check, NOT a scoring task: 150 evals is ~40% of the "
     "matched budget and is expected to land infeasible. At the full 336, "
     "FINDINGS 43.2 measured CMA-ES 4/5 seeds feasible; quote that, not this."),
    ("wifi24-t2-a",         "wifi24",       "4b351a49fa6e4f23",  10,   336,     336, "2026-08-11T07:31:52+00:00", True,  -0.7324616666666666, "current",
     "The reference task: the only plain-ZOAF feasible wifi24 row in the modern "
     "label domain, and the one FINDINGS 43.2's 5-seed null table was run on."),
    ("gps-l1-t2-a",         "gps-l1",       "82e8ca6a4cc02a43",   6,   136,     136, "2026-08-11T04:27:58+00:00", False,  7.921651344444444,  "current",
     "Small (d is the smallest in the registry) and the reference is INFEASIBLE "
     "at obj +7.92 -- a task where the incumbent did not solve it, which is the "
     "kind a benchmark needs and a leaderboard usually lacks."),
    ("wideband-sdr-t2-a",   "wideband-sdr", "e56f5b775362195d",   6,   136,       0, "2026-08-14T10:47:16+00:00", False,  None,               "current",
     "R-2 executed 2026-08-14: re-labeled under era 2026-08-14-relabel (w_finger=2e-6, "
     "series_rs NF, stab harness). ref_ts is the relabeled row (n_evals=0 by "
     "construction -- a re-label is one measurement of one stored point, not a "
     "campaign); budget=136 is inherited from the original 136-eval campaign "
     "(ingest-v1, ts=2026-08-09T11:45:22). Old ref NF 8.27 dB; new ref NF 6.28 dB "
     "(d=-1.99 dB, era-attributable, fence PASS). ref_obj dropped to None: the "
     "relabeled row carries no best_obj (it is not a search result)."),
    ("dhruva-l1-t2-a",      "dhruva-l1",    "439032fd40e7e504",  18,   392,     392, "2026-08-10T10:45:44+00:00", True,   None,               "current",
     "The flagship case study's L1 band. 18 devices, the largest deck here."),
    ("dhruva-l2-t2-a",      "dhruva-l2",    "439032fd40e7e504",  18,   266,     266, "2026-08-10T07:55:06+00:00", True,   None,               "current",
     "Same topology as dhruva-l1-t2-a at a different band -- the registry's one "
     "controlled pair for asking whether a method transfers across a spec move "
     "with the structure held fixed."),
    ("dhruva-l5-t2-a",      "dhruva-l5",    "46d1edb3be115fc5",   9,  1050,    1050, "2026-08-10T13:02:24+00:00", True,   None,               "current",
     "The most expensive reference in the registry (1,050 evals). Stage 22 ruled "
     "the l5 input stage a topology problem, not a sizing one -- so a sizer that "
     "matches the reference here is doing well, and one that beats it is "
     "evidence about the ruling."),
    ("dhruva-s-t2-a",       "dhruva-s",     "f578743ae13296d0",  18,  1030,    1030, "2026-08-10T10:57:01+00:00", True,   None,               "current",
     "The S-band rung of the designated dhruva-simul point; 7 stored rows for "
     "this (wl_hash, spec), which is exactly why ref_ts is pinned."),
]

REGISTRY = {}
for (_id, _spec, _wl, _dev, _bud, _ref_ev, _ts, _feas, _obj, _era, _note) in _ROWS:
    REGISTRY[_id] = Task(_id, _spec, _wl, budget=_bud, seed=1, tier=2,
                         ref_ts=_ts, ref_evals=_ref_ev, ref_feasible=_feas,
                         ref_obj=_obj, era=_era, n_devices=_dev, notes=_note)

SMOKE = "wifi24-smoke"
SCORING = [t for t in REGISTRY if t != SMOKE]   # the smoke is not a scoring task


def get(task_id, **overrides):
    """One task by id. `overrides` (budget=, seed=, ...) return a COPY -- the
    registry's pins are never mutated by a caller that wants a different seed."""
    if task_id not in REGISTRY:
        raise KeyError(f"unknown task {task_id!r}; know {sorted(REGISTRY)}")
    t = REGISTRY[task_id]
    return t.with_(**overrides) if overrides else t


def all_tasks(tier=None, era=None, scoring_only=False):
    out = [REGISTRY[k] for k in sorted(REGISTRY)]
    if scoring_only:
        out = [t for t in out if t.id in SCORING]
    if tier is not None:
        out = [t for t in out if t.tier == int(tier)]
    if era is not None:
        out = [t for t in out if t.era == era]
    return out


# -------------------------------------------------------------------- the CLI
def cmd_list(long=False):
    print(f"{'task id':<20} {'spec':<14} {'wl_hash':<18} {'dev':>3} {'tier':>4} "
          f"{'budget':>6} {'ref':>6} {'ref feas':>8} {'ref obj':>10} era")
    for t in all_tasks():
        obj = ("%.4f" % t.ref_obj) if isinstance(t.ref_obj, (int, float)) else "-"
        print(f"{t.id:<20} {t.spec:<14} {t.wl_hash:<18} {t.n_devices or 0:>3} "
              f"{t.tier:>4} {t.budget:>6} {t.ref_evals:>6} "
              f"{str(bool(t.ref_feasible)):>8} {obj:>10} {t.era}")
        if long:
            print(f"{'':<20} ref_ts {t.ref_ts}")
            for line in _wrap(t.notes, 92):
                print(f"{'':<20} {line}")
    print(f"\n{len(REGISTRY)} tasks, {len(SCORING)} of them scoring "
          f"({SMOKE} is the end-to-end check, not a score).")
    print("tier 3 (linearity): 0 tasks -- iip3_dbm is `unsupported` in every "
          "spec until WP-LIN binds the two-tone harness. See the module docstring.")
    return 0


def cmd_check():
    """Re-derive the pins from the live store and report every drift.

    Three claims are checked, all of which this file makes in prose above: the
    pinned row still exists; the selection rule still selects it; and no spec has
    started supporting `iip3_dbm` behind the registry's back.

    Era-relabeled rows carry n_evals=0 by construction (a re-label measures one
    stored point once, not a new campaign). For tasks pinned to such rows the
    pinned-row lookup searches all rows (not just n_evals>0 ones), and a matching
    n_evals=0 against a registry ref_evals=0 is correct -- it means the budget is
    set independently from the era-matched reference row."""
    rows = ds.load("topo_labels")
    bad = 0
    print(f"store: {len(rows)} L2 rows")
    for t in all_tasks():
        cand = [r for r in rows if r.get("spec") == t.spec
                and r.get("wl_hash") == t.wl_hash
                and (r.get("graph") or {}).get("tokens") and r.get("n_evals")]
        # Pinned-row lookup: use all token-carrying rows so that era-relabeled
        # rows (n_evals=0) can be pinned explicitly.
        all_topo = [r for r in rows if r.get("spec") == t.spec
                    and r.get("wl_hash") == t.wl_hash
                    and (r.get("graph") or {}).get("tokens")]
        pinned = [r for r in all_topo if r.get("ts") == t.ref_ts]
        withobj = [r for r in cand if isinstance(r.get("best_obj"), (int, float))]
        rule = (withobj or cand)[-1] if cand else None
        msgs = []
        if not pinned:
            msgs.append(f"PINNED ROW MISSING (ts={t.ref_ts})")
        elif pinned[-1].get("n_evals") != t.ref_evals:
            msgs.append(f"ref_evals drift: pinned row has "
                        f"{pinned[-1].get('n_evals')}, registry says {t.ref_evals}")
        if rule is not None and pinned and rule.get("ts") != t.ref_ts:
            msgs.append(f"selection rule now picks ts={rule.get('ts')} "
                        f"({rule.get('n_evals')} evals) -- {len(cand)} candidate "
                        "rows; the pin is deliberate, this is FYI")
        bad += sum(1 for m in msgs if m.startswith(("PINNED", "ref_evals")))
        print(f"  {t.id:<20} {len(cand):>2} rows  "
              + ("OK" if not msgs else "; ".join(msgs)))
    n3 = 0
    for name in sorted({t.spec for t in all_tasks()}):
        c = (Spec.load(name).constraints.get("iip3_dbm") or {})
        supported = bool(c) and c.get("status") != "unsupported"
        n3 += int(supported)
        if supported:
            print(f"  spec {name}: iip3_dbm is NOW SUPPORTED -- the registry's "
                  "'no tier-3 task' claim is stale; add the tier-3 rungs")
    print(f"\ntier-3 capable specs: {n3} (registry claims 0)")
    print("check " + ("FAILED" if bad or n3 else "GREEN"))
    return 1 if (bad or n3) else 0


def _wrap(text, width):
    out, line = [], ""
    for w in (text or "").split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="the registry table")
    ap.add_argument("--long", action="store_true", help="--list: notes + ref_ts")
    ap.add_argument("--check", action="store_true",
                    help="re-derive the pins from the live store")
    a = ap.parse_args()
    if a.check:
        return cmd_check()
    if a.list or not (a.list or a.check):
        return cmd_list(long=a.long)
    return 0


if __name__ == "__main__":
    sys.exit(main())
