"""campaign.py -- capability-v0 ladder runner (arms A and B).

Iterates kaggle/specs-ladder/ladder.json in order and, per spec, produces one
result row + a saved best design + an advisory verify verdict. ONE file runs
both arms so the two share the table/selection/save/verify code paths; only the
candidate source differs:

  --arm B  (full loop, Kaggle GPU session)  proposals from the LLM via driver.py
           machinery (import driver: its ChatClient, prompts, run_candidate,
           rank_key, save_best, Trajectory). REUSE, not reimplementation --
           this file owns only the per-spec control flow, escalation, the
           results table, checkpointing, and time management.

  --arm A  (sizing-only null, the box)       candidates from solve_spec's stored
           CORPUS topologies + CMA-ES at a MATCHED total eval budget, NO LLM
           anywhere. The comparison the campaign attributes topology credit off.

Budgets (per spec):
  base       k=3  edit_rounds=2  seeds=2  budget=300  max_tokens=3072
  escalate   k=5  edit_rounds=4  seeds=3  budget=600   (ONE retry on infeasible)
Arm A matches arm B's TOTAL eval budget, not its per-candidate budget:
  base total   = (k_B + edit_rounds_B) * seeds_B * budget_B   evals of headroom
  escalate     = (k_esc + er_esc) * seeds_esc * budget_esc
distributed over the corpus topologies (see _arm_a_plan).

Outputs (checkpointed after EVERY spec -- a session timeout loses nothing):
  <out>/results.jsonl     one JSON row per spec (append; the machine record)
  <out>/results.md        the human table, rewritten each spec
  <out>/designs/<spec>/   the best design in solve_spec designs/ layout PLUS
                          proposal.json (netlist + rationale + trajectory ptr)
  <out>/PARTIAL           written if wall-budget stops the run early
  <out>/trajectory/       arm-B per-spec trajectory jsonl (driver.Trajectory)

Time management: WALL_BUDGET_MIN env (default 500). After each spec the mean
per-spec wall time is updated; if the next spec would not fit, stop cleanly and
drop a PARTIAL marker.

    # local dry-run (no server, no ngspice) -- CI smoke:
    python kaggle/loop/campaign.py --arm B --dry-run --no-sim \
        --ladder kaggle/specs-ladder/ladder.json --max-specs 2

    # arm A on the box (real ngspice), one easy spec, tiny:
    source env.sh && export LNA_DEPS_ROOT=$PWD
    python kaggle/loop/campaign.py --arm A \
        --ladder kaggle/specs-ladder/ladder.json --max-specs 1 \
        --budget 80 --seeds 1 --out /tmp/arma
"""
import argparse
import json
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(
    os.path.join(HERE, "..", ".."))
LNA = os.path.join(ROOT, "lna")
for _p in (LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import driver as D                                                # noqa: E402
import verify as V                                                # noqa: E402

# ---- budgets (brief) --------------------------------------------------------
BASE = dict(k=3, edit_rounds=2, seeds=2, budget=300, max_tokens=3072)
ESCALATE = dict(k=5, edit_rounds=4, seeds=3, budget=600, max_tokens=3072)


# ===================================================================== helpers
def _spec_metric_margins(spec, metrics):
    """{metric: {achieved, margin, status}} over the spec's gated constraints,
    from datastore.margins_for -- the same margins driver/size use."""
    if not metrics:
        return {}
    try:
        import datastore as ds
        return ds.margins_for(spec, metrics)
    except Exception:
        return {}


def _load_ladder(path):
    with open(path, encoding="utf-8") as fh:
        man = json.load(fh)
    base = os.path.dirname(os.path.abspath(path))
    for row in man["specs"]:
        row["_path"] = os.path.join(base, row["file"])
    return man


def _checkpoint(out_dir, rows):
    """Rewrite results.jsonl + results.md atomically-ish after every spec."""
    os.makedirs(out_dir, exist_ok=True)
    jl = os.path.join(out_dir, "results.jsonl")
    with open(jl, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    with open(os.path.join(out_dir, "results.md"), "w", encoding="utf-8") as fh:
        fh.write(_render_md(rows))
        fh.flush()
        os.fsync(fh.fileno())


def _fmt(x, spec="%.3g"):
    return spec % x if isinstance(x, (int, float)) else "-"


def _render_md(rows):
    L = ["# capability-v0 results (EXPERIMENTAL -- not frozen)",
         "",
         "Advisory columns (iip3_dbm, stability) NEVER gate the verdict.",
         "0-feasible rows are results, not failures suppressed.",
         "",
         "| spec | tier | arm | feasible | first-feasible | iters | evals | "
         "escalated | best_obj | margins (worst) | iip3_dbm | stability | notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        worst = r.get("worst_margin")
        worst_s = ("%s=%.3g" % (worst[0], worst[1])
                   if worst and isinstance(worst[1], (int, float)) else "-")
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                 % (r.get("spec"), r.get("tier"), r.get("arm"),
                    "YES" if r.get("feasible") else "no",
                    r.get("first_feasible_phase") or "-",
                    _fmt(r.get("iters_to_first_feasible"), "%d")
                    if r.get("iters_to_first_feasible") is not None else "-",
                    _fmt(r.get("evals_to_first_feasible"), "%d")
                    if r.get("evals_to_first_feasible") is not None else
                    _fmt(r.get("total_evals"), "%d"),
                    "yes" if r.get("escalated") else "no",
                    _fmt(r.get("best_obj")), worst_s,
                    _fmt(r.get("iip3_dbm"), "%+.2f"),
                    (r.get("stability") or "-"),
                    (r.get("notes") or "").replace("|", "/")[:60]))
    return "\n".join(L) + "\n"


def _save_proposal(design_dir, cand, extra):
    """Alongside solve_spec's design.* files, drop the proposal provenance the
    brief requires: netlist + rationale + trajectory pointer."""
    try:
        os.makedirs(design_dir, exist_ok=True)
        rec = {"netlist": cand.get("netlist"),
               "wl_hash": cand.get("wl_hash"),
               "rationale": (cand.get("rationale")
                             if isinstance(cand, dict) else None)}
        rec.update(extra or {})
        with open(os.path.join(design_dir, "proposal.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2, default=float)
    except Exception:
        pass


def _worst_margin(margins):
    worst = None
    for name, m in (margins or {}).items():
        mar = m.get("margin")
        if isinstance(mar, (int, float)) and (worst is None or mar < worst[1]):
            worst = (name, mar)
    return worst


# ======================================================================= ARM B
def _make_client(args):
    if args.dry_run:
        return D.DryRunClient(os.path.join(HERE, "fixtures")), "dryrun"
    grammar = None
    if args.grammar_file:
        with open(args.grammar_file, encoding="utf-8") as fh:
            grammar = fh.read()
    return D.ChatClient(args.base_url, model=args.model, grammar=grammar), args.model


def run_spec_arm_b(spec, client, model_id, cfg, out_dir, traj_dir, no_sim,
                   temperature=0.7):
    """One spec through the full loop, reusing driver.py machinery verbatim.

    Mirrors driver.main's control flow (consult -> K propose -> rank -> diagnose
    -> edit_rounds) but parameterized and instrumented so first-feasibility can
    be attributed to a proposal N vs an edit round M. Returns a partial-row dict
    the caller finishes and appends. Never raises past the outer campaign guard.
    """
    spec_ref = spec.source
    run_id = uuid.uuid4().hex[:16]
    traj = D.Trajectory(os.path.join(traj_dir, run_id + ".jsonl"), run_id, spec.name)

    total_evals = [0]

    def _size_evals(cand):
        # solve_spec.size_tokens does not report n_evals; each seed consumes ~budget
        # evals, so total = seeds * budget per sized candidate that reached L2.
        if cand.get("sized") is not None or (cand.get("errors") and
                                             any("sizing produced no result" in e
                                                 for e in cand["errors"])):
            return cfg["seeds"] * cfg["budget"]
        return 0

    first_feasible = {"phase": None, "iter": None, "evals": None}

    def _note_feasible(cand, phase_label, iteration):
        if first_feasible["phase"] is not None:
            return
        if cand.get("sized") and cand["sized"].get("feasible"):
            first_feasible["phase"] = phase_label
            first_feasible["iter"] = iteration
            first_feasible["evals"] = total_evals[0]

    hits, _argv, cerr = D.consult_playbook(spec)
    traj.row(0, "consult", consult_hits=hits, error_verbatim=cerr)

    candidates = []
    messages = D.build_propose_prompt(spec, hits)
    try:
        resp = client.complete(messages, temperature=temperature,
                               max_tokens=cfg["max_tokens"], n=cfg["k"])
    except D.LLMError as e:
        traj.row(0, "propose", error_verbatim=str(e), next_action="give_up")
        traj.close()
        return {"feasible": False, "first_feasible_phase": None,
                "iters_to_first_feasible": None, "evals_to_first_feasible": None,
                "total_evals": 0, "best_obj": None, "margins": {},
                "worst_margin": None, "run_id": run_id, "best_cand": None,
                "notes": "propose LLM call failed: %s" % str(e)[:120]}
    choices = resp.get("choices", [])
    usage = resp.get("usage")
    rmodel = resp.get("model", model_id)

    for k, ch in enumerate(choices[:cfg["k"]]):
        content = (ch.get("message") or {}).get("content", "")
        netlist, rationale, deltas = D.parse_completion(content)
        cand = D.run_candidate(traj, spec, spec_ref, k, netlist, rationale,
                               deltas, rmodel, usage, "propose", no_sim,
                               cfg["seeds"], cfg["budget"], raw_completion=content)
        cand["rationale"] = rationale
        total_evals[0] += _size_evals(cand)
        _note_feasible(cand, "propose#%d" % k, k)
        candidates.append(cand)

    ok = [c for c in candidates if c["ok"]]
    if not ok:
        traj.row(len(candidates), "diagnose",
                 diagnosis="all proposals failed before sizing",
                 next_action="give_up")
        traj.close()
        return {"feasible": False, "first_feasible_phase": None,
                "iters_to_first_feasible": None, "evals_to_first_feasible": None,
                "total_evals": total_evals[0], "best_obj": None, "margins": {},
                "worst_margin": None, "run_id": run_id, "best_cand": None,
                "notes": "no candidate survived the funnel"}
    ok.sort(key=lambda c: D.rank_key(c, spec))
    best = ok[0]

    # ---- diagnose + edit rounds -------------------------------------------
    if not no_sim:
        for er in range(cfg["edit_rounds"]):
            if best.get("sized") and best["sized"].get("feasible"):
                break  # already feasible; stop spending edits (feasibility-first)
            if not best.get("sized"):
                break
            it = len(candidates)
            margins = best["sized"].get("margins") or {}
            binding = D._binding_constraint(margins)
            diag = ("binding: %s (margin %s)" % (binding[0], binding[1])
                    if binding else "feasible; soft-objective edit")
            traj.row(it, "diagnose", wl_hash=best.get("wl_hash"), diagnosis=diag,
                     next_action="edit")
            emsgs = D.build_edit_prompt(spec, hits, best["netlist"],
                                        best["sized"], best["errors"])
            try:
                eresp = client.complete(emsgs, temperature=temperature,
                                        max_tokens=cfg["max_tokens"], n=1)
            except D.LLMError as e:
                traj.row(it, "edit", error_verbatim=str(e), next_action="skip_edit")
                break
            ech = eresp.get("choices", [{}])[0]
            content = (ech.get("message") or {}).get("content", "")
            netlist, rationale, deltas = D.parse_completion(content)
            ecand = D.run_candidate(traj, spec, spec_ref, it, netlist, rationale,
                                    deltas, eresp.get("model", model_id),
                                    eresp.get("usage"), "edit", no_sim,
                                    cfg["seeds"], cfg["budget"],
                                    raw_completion=content)
            ecand["rationale"] = rationale
            total_evals[0] += _size_evals(ecand)
            _note_feasible(ecand, "edit#%d" % er, it)
            if ecand["ok"]:
                candidates.append(ecand)
                ok.append(ecand)
                ok.sort(key=lambda c: D.rank_key(c, spec))
                best = ok[0]

    traj.close()
    sized = best.get("sized") or {}
    margins = sized.get("margins") or {}
    feasible = bool(sized.get("feasible"))
    return {
        "feasible": feasible,
        "first_feasible_phase": first_feasible["phase"],
        "iters_to_first_feasible": first_feasible["iter"],
        "evals_to_first_feasible": first_feasible["evals"],
        "total_evals": total_evals[0],
        "best_obj": best.get("objective"),
        "margins": margins,
        "worst_margin": _worst_margin(margins),
        "run_id": run_id,
        "best_cand": best,
        "notes": "" if feasible else "infeasible (closest attempt saved)",
    }


# ======================================================================= ARM A
def _arm_a_plan(cfg):
    """Match arm B's TOTAL eval budget with the corpus.

    Arm B base headroom = (k + edit_rounds) sized candidates * seeds * budget.
    Arm A gets the SAME total, spread over the corpus topologies: each corpus
    topology sized at `seeds` seeds and a per-topology budget so the product
    equals the arm-B total. Returns (topologies, seeds, per_topo_budget)."""
    import solve_spec as SS
    n_cand = cfg["k"] + cfg["edit_rounds"]
    total = n_cand * cfg["seeds"] * cfg["budget"]
    topos = list(SS.CORPUS)
    seeds = cfg["seeds"]
    per = max(1, total // (len(topos) * seeds))
    return topos, seeds, per, total


def run_spec_arm_a(spec, cfg, no_sim):
    """One spec sized over the stored CORPUS at a matched total eval budget.

    NO LLM. Reuses solve_spec.size_tokens + CORPUS verbatim. Feasibility-first
    selection identical to arm B (driver.rank_key semantics). Returns the same
    partial-row shape as run_spec_arm_b, so the table/verify code is shared."""
    import solve_spec as SS
    topos, seeds, per, total = _arm_a_plan(cfg)
    spec_ref = spec.source
    best = None
    best_toks = None
    best_label = None
    total_evals = 0
    first_feasible = {"phase": None, "iter": None, "evals": None}
    idx = 0
    for wl in topos:
        try:
            toks = SS.tokens_for(wl)
        except SystemExit:
            continue
        for seed in range(1, seeds + 1):
            if no_sim:
                idx += 1
                continue
            r = SS.size_tokens(list(toks), spec_ref, seed, per)
            total_evals += per
            idx += 1
            if r is None:
                continue
            if first_feasible["phase"] is None and r["feasible"]:
                first_feasible.update(phase="corpus#%s" % wl[:8], iter=idx,
                                      evals=total_evals)
            better = (best is None
                      or (r["feasible"] and not best["feasible"])
                      or (r["feasible"] == best["feasible"]
                          and r["best_obj"] < best["best_obj"]))
            if better:
                best, best_toks, best_label = r, list(toks), wl[:12]
    if best is None:
        return {"feasible": False, "first_feasible_phase": None,
                "iters_to_first_feasible": None, "evals_to_first_feasible": None,
                "total_evals": total_evals, "best_obj": None, "margins": {},
                "worst_margin": None, "run_id": "armA", "best_cand": None,
                "notes": "no corpus topology sizable for this spec"
                         if not no_sim else "no-sim (arm A structure only)"}
    margins = best.get("margins") or {}
    # shape a driver-style candidate so save/verify share code paths
    cand = {"ok": True, "tokens": best_toks, "wl_hash": best_label,
            "netlist": None, "rationale": "arm A: stored corpus topology "
            "(no LLM); sized by CMA-ES at matched total eval budget",
            "sized": {"feasible": best["feasible"], "margins": margins,
                      "metrics": best["metrics"],
                      "best_objective": best["best_obj"],
                      "seed": best["seed"], "best_params": best["best_params"]},
            "objective": best["best_obj"]}
    return {
        "feasible": bool(best["feasible"]),
        "first_feasible_phase": first_feasible["phase"],
        "iters_to_first_feasible": first_feasible["iter"],
        "evals_to_first_feasible": first_feasible["evals"],
        "total_evals": total_evals,
        "best_obj": best["best_obj"],
        "margins": margins,
        "worst_margin": _worst_margin(margins),
        "run_id": "armA", "best_cand": cand,
        "notes": "matched total eval budget=%d (%d topos x %d seeds x %d)"
                 % (total, len(topos), seeds, per),
    }


# =================================================================== the runner
def _finish_row(spec_row, spec, arm, partial, out_dir, cfg, escalated,
                do_verify, verify_wide):
    """Complete a partial row: save the best design + proposal, run verify."""
    cand = partial.get("best_cand")
    metrics = ((cand or {}).get("sized") or {}).get("metrics")
    design_dir = os.path.join(out_dir, "designs", spec.name)
    verdict = None
    saved = None
    if cand and (cand.get("sized") or {}).get("best_params"):
        try:
            import solve_spec as SS
            sized = cand["sized"]
            res = {"feasible": sized["feasible"], "best_obj": cand["objective"],
                   "best_params": sized["best_params"], "metrics": sized["metrics"],
                   "margins": sized["margins"], "seed": sized.get("seed"),
                   "_label": (cand.get("wl_hash") or spec.name)}
            saved = SS.save_design(os.path.join(out_dir, "designs"), spec.name,
                                   cand["tokens"], res)
        except Exception as e:                                   # noqa: BLE001
            saved = "save_failed: %r" % e
        _save_proposal(design_dir, cand,
                       {"arm": arm, "run_id": partial.get("run_id"),
                        "trajectory": os.path.join("trajectory",
                                                   partial.get("run_id", "") + ".jsonl")
                        if arm == "B" else None})
        if do_verify:
            verdict = V.verify_design(cand["tokens"], sized["best_params"], spec,
                                      do_wide_stability=verify_wide)
    iip3_dbm = (verdict or {}).get("iip3_dbm") if verdict else None
    stability = None
    if verdict and verdict.get("sparams"):
        stability = verdict["sparams"].get("stability")
    row = {
        "spec": spec.name, "spec_file": spec_row["file"], "tier": spec_row["tier"],
        "band": spec_row["band"], "band_type": spec_row["band_type"], "arm": arm,
        "feasible": partial["feasible"],
        "first_feasible_phase": partial["first_feasible_phase"],
        "iters_to_first_feasible": partial["iters_to_first_feasible"],
        "evals_to_first_feasible": partial["evals_to_first_feasible"],
        "total_evals": partial["total_evals"],
        "escalated": escalated,
        "best_obj": partial["best_obj"],
        "worst_margin": partial["worst_margin"],
        "margins": {k: {kk: m.get(kk) for kk in ("achieved", "margin", "supported")}
                    for k, m in (partial["margins"] or {}).items()},
        "metrics": metrics,
        "iip3_dbm": iip3_dbm,
        "stability": stability,
        "verify": verdict,
        "design_dir": saved,
        "budgets": cfg,
        "notes": partial.get("notes", ""),
        "ts": time.time(),
    }
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, choices=["A", "B"])
    ap.add_argument("--ladder", required=True, help="path to ladder.json")
    ap.add_argument("--out", help="output dir (default depends on env)")
    ap.add_argument("--dry-run", action="store_true", help="arm B: driver DryRunClient")
    ap.add_argument("--no-sim", action="store_true", help="skip ngspice sizing")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model", default="local")
    ap.add_argument("--grammar-file")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-specs", type=int, help="cap the number of specs (smoke)")
    ap.add_argument("--no-escalate", action="store_true",
                    help="skip the escalation retry on infeasible")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the advisory verify (IIP3/S-params) pass")
    ap.add_argument("--verify-wide-stability", action="store_true",
                    help="verify: also run the wide out-of-band stability audit")
    # budget overrides (mainly for the arm-A pilot / smoke)
    ap.add_argument("--k", type=int)
    ap.add_argument("--edit-rounds", type=int)
    ap.add_argument("--seeds", type=int)
    ap.add_argument("--budget", type=int)
    ap.add_argument("--wall-budget-min", type=float,
                    default=float(os.environ.get("WALL_BUDGET_MIN", "500")))
    args = ap.parse_args(argv)

    on_kaggle = os.path.isdir("/kaggle/working")
    out_dir = args.out or ("/kaggle/working/campaign" if on_kaggle
                           else os.path.join(os.getcwd(), "campaign_out"))
    traj_dir = os.path.join(out_dir, "trajectory")
    os.makedirs(traj_dir, exist_ok=True)

    def _cfg(base):
        c = dict(base)
        for kk in ("k", "edit_rounds", "seeds", "budget"):
            v = getattr(args, kk if kk != "edit_rounds" else "edit_rounds")
            if v is not None:
                c[kk] = v
        return c

    base_cfg = _cfg(BASE)
    esc_cfg = _cfg(ESCALATE)

    man = _load_ladder(args.ladder)
    specs = man["specs"][:args.max_specs] if args.max_specs else man["specs"]

    client = model_id = None
    if args.arm == "B":
        client, model_id = _make_client(args)

    from spec import Spec
    rows = []
    wall_budget_s = args.wall_budget_min * 60.0
    t_campaign = time.time()
    per_spec_times = []
    do_verify = not args.no_verify and not args.no_sim

    print("campaign arm=%s  out=%s  specs=%d  wall_budget=%.0f min  base=%s"
          % (args.arm, out_dir, len(specs), args.wall_budget_min, base_cfg),
          flush=True)

    for i, spec_row in enumerate(specs):
        # time gate: stop cleanly if the next spec would not fit the wall budget
        elapsed = time.time() - t_campaign
        if per_spec_times:
            mean = sum(per_spec_times) / len(per_spec_times)
            if elapsed + mean > wall_budget_s:
                with open(os.path.join(out_dir, "PARTIAL"), "w") as fh:
                    fh.write("stopped before spec %d/%d (%s): elapsed %.1f min + "
                             "mean %.1f min > budget %.1f min\n"
                             % (i + 1, len(specs), spec_row["name"], elapsed / 60,
                                mean / 60, args.wall_budget_min))
                print("[campaign] WALL BUDGET reached; stopping before %s"
                      % spec_row["name"], flush=True)
                break

        t0 = time.time()
        spec = Spec.load(spec_row["_path"])
        print("\n[%d/%d] %s (%s, %s)" % (i + 1, len(specs), spec.name,
                                         spec_row["tier"], spec_row["band"]),
              flush=True)
        try:
            if args.arm == "B":
                partial = run_spec_arm_b(spec, client, model_id, base_cfg,
                                         out_dir, traj_dir, args.no_sim,
                                         temperature=args.temperature)
            else:
                partial = run_spec_arm_a(spec, base_cfg, args.no_sim)
        except Exception as e:                                   # noqa: BLE001
            partial = {"feasible": False, "first_feasible_phase": None,
                       "iters_to_first_feasible": None,
                       "evals_to_first_feasible": None, "total_evals": 0,
                       "best_obj": None, "margins": {}, "worst_margin": None,
                       "run_id": "err", "best_cand": None,
                       "notes": "base run raised: %r" % e}

        escalated = False
        cfg_used = base_cfg
        if (not partial["feasible"] and not args.no_escalate and not args.no_sim):
            print("    infeasible at base -> ESCALATE", flush=True)
            escalated = True
            cfg_used = esc_cfg
            try:
                if args.arm == "B":
                    partial = run_spec_arm_b(spec, client, model_id, esc_cfg,
                                             out_dir, traj_dir, args.no_sim,
                                             temperature=args.temperature)
                else:
                    partial = run_spec_arm_a(spec, esc_cfg, args.no_sim)
            except Exception as e:                              # noqa: BLE001
                partial = {"feasible": False, "first_feasible_phase": None,
                           "iters_to_first_feasible": None,
                           "evals_to_first_feasible": None, "total_evals": 0,
                           "best_obj": None, "margins": {}, "worst_margin": None,
                           "run_id": "err", "best_cand": None,
                           "notes": "escalation raised: %r" % e}
            if not partial["feasible"]:
                partial["notes"] = ("HARD FAILURE after escalation; "
                                    + partial.get("notes", ""))

        row = _finish_row(spec_row, spec, args.arm, partial, out_dir, cfg_used,
                          escalated, do_verify, args.verify_wide_stability)
        rows.append(row)
        _checkpoint(out_dir, rows)          # after EVERY spec
        dt = time.time() - t0
        per_spec_times.append(dt)
        print("    -> feasible=%s  first=%s  evals=%s  iip3=%s  (%.1f min)"
              % (row["feasible"], row["first_feasible_phase"],
                 row["total_evals"], _fmt(row["iip3_dbm"], "%+.2f"), dt / 60),
              flush=True)

    n_feas = sum(1 for r in rows if r["feasible"])
    print("\ncampaign done: %d/%d rows, %d feasible; results -> %s"
          % (len(rows), len(specs), n_feas, out_dir), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
