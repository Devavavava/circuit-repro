"""x0v1_run.py -- the COMMISSIONED x0-v1 eval driver (pre-registration
`kaggle/CAMPAIGN-X0-V1.md`).

Runs ONE leg (one arm) of the x0-v1 campaign over all 14 frozen cells
(`kaggle/x0v1-cells.json`). x0-v1 asks whether the warm starts help on UNSEEN
topologies -- the shapes the reasoning loop invents. Each cell fixes a topology
(k=1, NO candidate screening, no corpus, no LLM anywhere) and sizes it against
its ladder spec, mirroring arm B's per-candidate protocol EXACTLY.

The arm is selected ONLY by the `LNA_X0_PRIOR` env var (off / retrieval /
learned), which the existing `size.warm_start_x0` hook (invoked inside
`solve_spec.size_tokens`) reads. This driver NEVER sets or overrides that flag;
it records `os.environ.get("LNA_X0_PRIOR")` into every row so the leg is
self-describing. Run one leg per arm:

    LNA_X0_PRIOR=off        python kaggle/x0v1_run.py --cells kaggle/x0v1-cells.json --out <dir>   # A0
    LNA_X0_PRIOR=retrieval  python kaggle/x0v1_run.py --cells kaggle/x0v1-cells.json --out <dir>   # A1
    LNA_X0_PRIOR=learned    python kaggle/x0v1_run.py --cells kaggle/x0v1-cells.json --out <dir>   # A2

Per cell, per arm: base `seeds=2 x budget=300`; if infeasible, ONE escalation
`seeds=3 x budget=600` -- with `evals_to_first_feasible`, `total_evals`,
`first_feasible_phase`, `escalated` accounted EXACTLY as `campaign.py` accounts
them for an arm-B candidate. The reuse is deliberate and total: the sizing entry
is campaign's own `driver.size_candidate` (which loops `solve_spec.size_tokens`
across seeds, the same call arm B makes); the per-candidate eval accounting is
`campaign.run_spec_arm_b`'s own `_size_evals` rule (seeds*budget per sized
candidate); the escalation control flow mirrors `campaign.main` (a FRESH
accounting per escalation, base discarded -- NOT additive); and the row / table
/ design artifacts are written with campaign's own `_finish_row`-shaped schema
and helpers so rows are schema-compatible where meaningful. campaign.py is NOT
modified.

Outputs (checkpointed after EVERY cell -- a crash loses nothing):
  <out>/results.jsonl     one JSON row per cell (rewritten each cell)
  <out>/results.md        the human table
  <out>/designs/<spec>/   the best design (solve_spec layout) + proposal.json
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# The pre-registration and DAY-2 both bind this: prefer $LNA_DEPS_ROOT on
# sys.path so the driver runs the WORKTREE's modules, not the main checkout's.
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(os.path.join(HERE, ".."))
LNA = os.path.join(ROOT, "lna")
LOOP = os.path.join(ROOT, "kaggle", "loop")
for _p in (LOOP, LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse campaign + driver verbatim. campaign owns the accounting rule
# (_size_evals), the row schema (_finish_row), the table (_render_md), the
# checkpoint (_checkpoint), and the folding helpers; driver owns the sizing
# entry (size_candidate) arm B itself calls. Nothing here is reimplemented.
#
# NOTE: `lna/campaign.py` (the nightly data-labeling module) shadows
# `kaggle/loop/campaign.py` by name on sys.path, so we load THE LATTER by
# explicit file path and register it as `campaign` before driver.py's own
# `import driver` runs. This is the arm-B campaign runner, unambiguously.
import importlib.util as _ilu                                       # noqa: E402
_camp_path = os.path.join(LOOP, "campaign.py")
_spec = _ilu.spec_from_file_location("campaign", _camp_path)
C = _ilu.module_from_spec(_spec)
sys.modules["campaign"] = C
_spec.loader.exec_module(C)
import driver as D                                                  # noqa: E402
import solve_spec as SS                                             # noqa: E402
from spec import Spec                                               # noqa: E402

assert hasattr(C, "BASE") and C.__file__ == _camp_path, \
    "wrong campaign module loaded: %r" % getattr(C, "__file__", None)

# The x0-v1 pre-registration fixes the budgets to arm B's per-candidate grid.
# We read them straight from campaign so a future edit there tracks here too.
BASE = dict(C.BASE)             # seeds=2 budget=300
ESCALATE = dict(C.ESCALATE)     # seeds=3 budget=600

# The 14 cells all run the bptm45 ladder (kaggle/specs-ladder/) -- the same
# specs campaign resolves. Default pdk is bptm45 (each spec's own field).
LADDER_DIR = os.path.join(ROOT, "kaggle", "specs-ladder")


def _size_cell(spec, spec_ref, tokens, cfg, pdk):
    """Size ONE fixed cell topology at cfg (seeds x budget), reusing arm B's own
    sizing entry `driver.size_candidate` (which loops `solve_spec.size_tokens`
    across seeds 1..N -- the SAME house seed derivation and the SAME call arm B
    makes). Returns a `partial`-shaped dict identical in the fields campaign's
    `run_spec_arm_b` returns, with e2f accounted by campaign's OWN `_size_evals`
    rule for the k=1, fixed-topology, no-LLM case.

    Determinism: `size_candidate` derives the per-seed CMA-ES seed as the seed
    INDEX (range(1, seeds+1)) -- byte-identical to how arm B / arm A seed
    `size_tokens`, so (cell, seed-index) is fixed and reproducible.

    The warm start is chosen ENTIRELY by LNA_X0_PRIOR inside size_tokens ->
    size.warm_start_x0; this function never touches that flag."""
    seeds, budget = cfg["seeds"], cfg["budget"]
    best, secs, _ = D.size_candidate(tokens, spec_ref, seeds, budget, pdk=pdk)

    # ---- campaign's accounting, verbatim (run_spec_arm_b) ------------------
    # `_size_evals`: a candidate that reached the sized stage (or produced the
    # "sizing produced no result" error) consumed seeds*budget; else 0. Here the
    # cell either sized (best is not None) or was not sizable (best is None).
    if best is not None:
        total_evals = seeds * budget            # == campaign._size_evals(cand)
        feasible = bool(best["feasible"])
        margins = best.get("margins") or {}
        # first-feasible is snapshotted AFTER adding this candidate's evals
        # (campaign notes feasibility once total_evals is incremented), so e2f
        # == total_evals when the single fixed candidate is feasible.
        first_feasible = {
            "phase": "propose#0" if feasible else None,
            "iter": 0 if feasible else None,
            "evals": total_evals if feasible else None,
        }
        # build the campaign-shaped candidate dict so _finish_row can save it.
        sized = {
            "feasible": best["feasible"],
            "margins": best["margins"],
            "metrics": best["metrics"],
            "best_objective": best["best_obj"],
            "seed": best["seed"],
            "seconds": secs,
            # SIM-HEALTH lands FREE from the size path: size_candidate sums
            # sh_* over every seed; fold it onto sized.sim_health exactly as
            # driver.run_candidate does, so campaign._sim_health picks it up.
            "sim_health": {"n_evals": best.get("sh_n_evals"),
                           "n_sim_fail": best.get("sh_n_sim_fail"),
                           "sim_error": best.get("sh_sim_error")},
            "best_params": best["best_params"],
        }
        stages = {"parsed": True, "l0": True, "bias": True, "sized": True,
                  "feasible": feasible}
        cand = {"ok": True, "tokens": list(tokens),
                "wl_hash": None, "netlist": None, "sized": sized,
                "errors": [], "objective": best["best_obj"], "stages": stages,
                "rationale": None}
        notes = "" if feasible else "infeasible (closest attempt saved)"
    else:
        # size_candidate returned None == arm B's "sizing produced no result
        # (topology not sizable for this spec)" error path. campaign's
        # `_size_evals` CHARGES seeds*budget in that case (the error string is
        # in cand["errors"]), NOT 0 -- so we mirror it exactly and record the
        # same error, keeping e2f/total_evals parity with run_spec_arm_b.
        total_evals = seeds * budget            # == campaign._size_evals(cand)
        feasible = False
        margins = {}
        first_feasible = {"phase": None, "iter": None, "evals": None}
        stages = {"parsed": True, "l0": True, "bias": True, "sized": False,
                  "feasible": False}
        cand = {"ok": False, "tokens": list(tokens), "wl_hash": None,
                "netlist": None, "sized": None,
                "errors": ["sizing produced no result (topology not sizable "
                           "for this spec)"], "objective": None,
                "stages": stages, "rationale": None}
        notes = "sizing produced no result (topology not sizable for this spec)"

    return {
        "feasible": feasible,
        "first_feasible_phase": first_feasible["phase"],
        "iters_to_first_feasible": first_feasible["iter"],
        "evals_to_first_feasible": first_feasible["evals"],
        "total_evals": total_evals,
        "best_obj": (best or {}).get("best_obj") if best else None,
        "margins": margins,
        "worst_margin": C._worst_margin(margins),
        "run_id": "x0v1",
        "best_cand": cand,
        # single-candidate stage-rates + sim-health folded by campaign's helper
        "stage_rates": C._stage_rates([stages], [cand]),
        "notes": notes,
    }


def _finish_row(spec_row, spec, cell, partial, out_dir, cfg, escalated,
                arm_flag, pdk):
    """Complete + return one results row. Saves the best design in solve_spec's
    layout (via campaign's own SS.save_design) + a proposal.json, then folds the
    campaign-compatible fields plus the x0-v1-specific ones (arm/flag, novel,
    wl_hash, source). No verify pass (x0-v1 is sizing-only, no LLM)."""
    cand = partial.get("best_cand")
    sized = (cand or {}).get("sized") or {}
    metrics = sized.get("metrics")
    design_dir = os.path.join(out_dir, "designs", spec.name)
    saved = None
    if cand and sized.get("best_params"):
        try:
            res = {"feasible": sized["feasible"], "best_obj": cand["objective"],
                   "best_params": sized["best_params"], "metrics": sized["metrics"],
                   "margins": sized["margins"], "seed": sized.get("seed"),
                   "_label": cell.get("wl_hash") or spec.name}
            saved = SS.save_design(os.path.join(out_dir, "designs"), spec.name,
                                   cand["tokens"], res)
        except Exception as e:                                       # noqa: BLE001
            saved = "save_failed: %r" % e
        C._save_proposal(design_dir, cand,
                         {"arm": "x0v1", "flag": arm_flag,
                          "wl_hash": cell.get("wl_hash"),
                          "source_record": cell.get("source_record"),
                          "novel": cell.get("novel"),
                          "tokens_file": cell.get("tokens_file")})

    sh = ((partial.get("stage_rates") or {}).get("sim_health"))
    row = {
        "spec": spec.name,
        "spec_file": spec_row["file"],
        "tier": spec_row.get("tier"),
        "band": spec_row.get("band"),
        "band_type": spec_row.get("band_type"),
        # x0-v1 identity: the arm is the LNA_X0_PRIOR value, recorded VERBATIM
        # from the environment (never set by this driver). None -> the null.
        "arm": "x0v1",
        "flag": arm_flag,
        "LNA_X0_PRIOR": arm_flag,
        "wl_hash": cell.get("wl_hash"),
        "wl_hash12": (cell.get("wl_hash") or "")[:12] or None,
        "source_record": cell.get("source_record"),
        "novel": cell.get("novel"),
        "tokens_file": cell.get("tokens_file"),
        "pdk": pdk or getattr(spec, "pdk", "bptm45"),
        "stage_rates": partial.get("stage_rates"),
        "sim_health": sh,
        "feasible": partial["feasible"],
        "first_feasible_phase": partial["first_feasible_phase"],
        "iters_to_first_feasible": partial["iters_to_first_feasible"],
        "iters": partial["iters_to_first_feasible"],
        "evals_to_first_feasible": partial["evals_to_first_feasible"],
        "total_evals": partial["total_evals"],
        "escalated": escalated,
        "best_obj": partial["best_obj"],
        "worst_margin": partial["worst_margin"],
        "margins": {k: {kk: m.get(kk) for kk in ("achieved", "margin", "supported")}
                    for k, m in (partial["margins"] or {}).items()},
        "metrics": metrics,
        "design_dir": saved,
        "budgets": cfg,
        "notes": partial.get("notes", ""),
        "ts": time.time(),
    }
    return row


def _load_cells(path):
    with open(path, encoding="utf-8") as fh:
        cells = json.load(fh)
    # tokens_file paths in the cells file are repo-relative; resolve vs ROOT.
    for name, c in cells.items():
        tf = c["tokens_file"]
        c["_tokens_path"] = tf if os.path.isabs(tf) else os.path.join(ROOT, tf)
    return cells


def _ladder_row_for(spec_name):
    """The ladder manifest row (tier/band/band_type/file) for a spec, resolved
    the SAME way campaign resolves ladder specs (from specs-ladder/ladder.json).
    Falls back to a minimal row derived from the YAML file if the spec is not in
    the manifest (it always is, for the 14 cells)."""
    man = C._load_ladder(os.path.join(LADDER_DIR, "ladder.json"))
    for r in man["specs"]:
        if r["name"] == spec_name:
            return r
    return {"name": spec_name, "file": spec_name + ".yaml", "tier": None,
            "band": None, "band_type": None,
            "_path": os.path.join(LADDER_DIR, spec_name + ".yaml")}


def _render_md(rows, arm_flag):
    """x0-v1 table: reuse the columns campaign renders where they overlap, plus
    the novel/flag columns x0-v1 attribution needs."""
    L = ["# x0-v1 results (EXPERIMENTAL -- pre-registered, not frozen)",
         "",
         "arm = LNA_X0_PRIOR = %s   (off=A0 null / retrieval=A1 / learned=A2)"
         % (arm_flag if arm_flag is not None else "(unset -> off/A0)"),
         "Fixed topology per cell, k=1, NO screening, no LLM. 0-feasible rows "
         "are results, not suppressed failures.",
         "NOVEL-10 = wl not in the store (primary set); SEEN-4 = control strip.",
         "sim-health = fraction of ngspice evals that produced metrics "
         "(1.00 = healthy; <<1 = environment wall).",
         "",
         "| spec | tier | split | flag | pdk | feasible | first-feasible | "
         "evals | escalated | best_obj | margins (worst) | sim-health | "
         "wl_hash | notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        worst = r.get("worst_margin")
        worst_s = ("%s=%.3g" % (worst[0], worst[1])
                   if worst and isinstance(worst[1], (int, float)) else "-")
        sh = r.get("sim_health") or {}
        rate = sh.get("sim_success_rate")
        sim_s = ("%.2f (%s/%s)" % (rate, sh.get("n_sim_fail", "-"),
                                   sh.get("n_evals", "-"))
                 if isinstance(rate, (int, float)) else "-")
        e2f = r.get("evals_to_first_feasible")
        evals_s = (C._fmt(e2f, "%d") if e2f is not None
                   else C._fmt(r.get("total_evals"), "%d"))
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                 % (r.get("spec"), r.get("tier") or "-",
                    "NOVEL" if r.get("novel") else "seen",
                    r.get("flag") if r.get("flag") is not None else "off",
                    r.get("pdk") or "-",
                    "YES" if r.get("feasible") else "no",
                    r.get("first_feasible_phase") or "-",
                    evals_s, "yes" if r.get("escalated") else "no",
                    C._fmt(r.get("best_obj")), worst_s, sim_s,
                    (r.get("wl_hash12") or "-"),
                    (r.get("notes") or "").replace("|", "/")[:50]))
    return "\n".join(L) + "\n"


def _checkpoint(out_dir, rows, arm_flag):
    """Rewrite results.jsonl + results.md after EVERY cell (append semantics:
    each cell's row is durable before the next cell starts). Mirrors
    campaign._checkpoint (fsync) but with the x0-v1 table."""
    os.makedirs(out_dir, exist_ok=True)
    jl = os.path.join(out_dir, "results.jsonl")
    with open(jl, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    with open(os.path.join(out_dir, "results.md"), "w", encoding="utf-8") as fh:
        fh.write(_render_md(rows, arm_flag))
        fh.flush()
        os.fsync(fh.fileno())


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cells", default=os.path.join(ROOT, "kaggle",
                                                    "x0v1-cells.json"),
                    help="the 14 frozen cells (kaggle/x0v1-cells.json)")
    ap.add_argument("--out", required=True, help="output dir for this leg")
    ap.add_argument("--pdk", default=None,
                    help="OVERRIDE the spec pdk (default: each spec's own = "
                         "bptm45). x0-v1 runs bptm45.")
    ap.add_argument("--no-escalate", action="store_true",
                    help="skip the ONE escalation retry on infeasible (smoke)")
    ap.add_argument("--only", action="append",
                    help="restrict to these cell/spec names (smoke; repeatable)")
    ap.add_argument("--seeds", type=int,
                    help="override base seeds (smoke only)")
    ap.add_argument("--budget", type=int,
                    help="override base budget (smoke only)")
    ap.add_argument("--esc-seeds", type=int,
                    help="override escalation seeds (smoke only)")
    ap.add_argument("--esc-budget", type=int,
                    help="override escalation budget (smoke only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse cells + resolve specs + print the row SHAPE per "
                         "cell without any ngspice sizing (shape check only)")
    args = ap.parse_args(argv)

    # The arm is read from the environment ONLY -- never set/overridden here.
    arm_flag = os.environ.get("LNA_X0_PRIOR")

    base_cfg = dict(BASE)
    esc_cfg = dict(ESCALATE)
    if args.seeds is not None:
        base_cfg["seeds"] = args.seeds
    if args.budget is not None:
        base_cfg["budget"] = args.budget
    if args.esc_seeds is not None:
        esc_cfg["seeds"] = args.esc_seeds
    if args.esc_budget is not None:
        esc_cfg["budget"] = args.esc_budget

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    cells = _load_cells(args.cells)
    names = list(cells.keys())
    if args.only:
        want = set(args.only)
        names = [n for n in names if n in want]

    print("x0-v1 leg: LNA_X0_PRIOR=%s  pdk=%s  cells=%d  out=%s"
          % (arm_flag if arm_flag is not None else "(unset->off/A0)",
             args.pdk or "(spec default=bptm45)", len(names), out_dir),
          flush=True)
    print("   base=%s  escalate=%s%s" % (base_cfg, esc_cfg,
          "  [NO ESCALATE]" if args.no_escalate else ""), flush=True)

    rows = []
    for i, name in enumerate(names):
        cell = cells[name]
        spec_row = _ladder_row_for(name)
        spec = Spec.load(spec_row["_path"])
        if args.pdk is not None:
            spec.pdk = args.pdk
        split = "NOVEL" if cell.get("novel") else "seen"
        print("\n[%d/%d] %s (%s, %s) split=%s wl=%s pdk=%s"
              % (i + 1, len(names), name, spec_row.get("tier"),
                 spec_row.get("band"), split, (cell.get("wl_hash") or "")[:12],
                 getattr(spec, "pdk", "bptm45")), flush=True)

        tokens = json.load(open(cell["_tokens_path"], encoding="utf-8"))
        # spec_ref: solve_spec.size_tokens takes the spec NAME/path (Spec.load'd
        # again inside via _spec_for_sizing), exactly as campaign passes it.
        spec_ref = spec_row["_path"]

        if args.dry_run:
            # shape-only: no ngspice. Emit a row skeleton with the fields set,
            # metrics/feasible None, so the schema can be inspected pre-run.
            partial = {"feasible": None, "first_feasible_phase": None,
                       "iters_to_first_feasible": None,
                       "evals_to_first_feasible": None, "total_evals": 0,
                       "best_obj": None, "margins": {}, "worst_margin": None,
                       "run_id": "dryrun",
                       "best_cand": {"tokens": list(tokens), "sized": None,
                                     "stages": {}, "objective": None},
                       "stage_rates": None,
                       "notes": "dry-run (no sizing)"}
            row = _finish_row(spec_row, spec, cell, partial, out_dir, base_cfg,
                              False, arm_flag, args.pdk)
            rows.append(row)
            _checkpoint(out_dir, rows, arm_flag)
            print("    -> dry-run row: keys=%d  n_tokens=%d"
                  % (len(row), len(tokens)), flush=True)
            continue

        t0 = time.time()
        # ---- BASE (seeds=2 x budget=300) --------------------------------------
        partial = _size_cell(spec, spec_ref, tokens, base_cfg, args.pdk)
        escalated = False
        cfg_used = base_cfg

        # ---- ONE escalation on infeasible (seeds=3 x budget=600) --------------
        # mirrors campaign.main: on infeasible the base partial is DISCARDED and
        # replaced by a FRESH escalation accounting (e2f/total_evals reset).
        if (not partial["feasible"]) and (not args.no_escalate):
            print("    infeasible at base -> ESCALATE", flush=True)
            escalated = True
            cfg_used = esc_cfg
            partial = _size_cell(spec, spec_ref, tokens, esc_cfg, args.pdk)
            if not partial["feasible"]:
                partial["notes"] = ("HARD FAILURE after escalation; "
                                    + partial.get("notes", ""))

        row = _finish_row(spec_row, spec, cell, partial, out_dir, cfg_used,
                          escalated, arm_flag, args.pdk)
        rows.append(row)
        _checkpoint(out_dir, rows, arm_flag)      # durable after EVERY cell
        dt = time.time() - t0
        print("    -> feasible=%s  first=%s  e2f=%s  total_evals=%s  "
              "escalated=%s  (%.1f min)"
              % (row["feasible"], row["first_feasible_phase"],
                 row["evals_to_first_feasible"], row["total_evals"],
                 escalated, dt / 60), flush=True)

    n_feas = sum(1 for r in rows if r.get("feasible"))
    n_novel = sum(1 for r in rows if r.get("novel"))
    n_novel_feas = sum(1 for r in rows if r.get("novel") and r.get("feasible"))
    print("\nx0-v1 leg done: flag=%s  %d cells, %d feasible "
          "(NOVEL %d/%d); results -> %s"
          % (arm_flag, len(rows), n_feas, n_novel_feas, n_novel, out_dir),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
