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

# ---- capability-v1 arm variants (see CAMPAIGN-CAPABILITY-V1.md) -------------
#   v0        ARM1 "v0-repeat"     -- byte-identical v0 arm-B (run-to-run noise)
#   arch      ARM2 "architecture"  -- v0 + CONCENTRATION (triage) + SELF-DIVERSITY
#   selflearn ARM3 "self-learning" -- arch + REFLECT-FIRST overlay consult
VARIANTS = ("v0", "arch", "selflearn")

# CONCENTRATION split (pre-registered). The per-spec TOTAL eval budget is
# UNCHANGED from v0: (k + edit_rounds) * seeds * budget eval-equivalents. arch
# re-allocates it as a cheap triage over the k proposals, then ALL remaining
# budget + full seeds on the single triage winner:
#   triage:      each of the k proposals sized at TRIAGE_SEEDS=1 seed and
#                TRIAGE_FRAC * budget evals (base budget=300 -> 60 evals).
#   concentrate: the triage winner re-sized at full `seeds` and driven through
#                the edit rounds, spending the remaining eval-equivalents.
TRIAGE_FRAC = 5            # triage_budget = budget // TRIAGE_FRAC  (300//5 = 60)
TRIAGE_SEEDS = 1


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
    variant = next((r.get("variant") for r in rows if r.get("variant")), None)
    title = ("# capability results (EXPERIMENTAL -- not frozen)"
             + (" -- variant=%s" % variant if variant else ""))
    pdk = next((r.get("pdk") for r in rows if r.get("pdk")), None)
    L = [title + (" -- pdk=%s" % pdk if pdk and pdk != "bptm45" else ""),
         "",
         "Advisory columns (iip3_dbm, stability) NEVER gate the verdict.",
         "0-feasible rows are results, not failures suppressed.",
         "stages = bias/sized/feasible counts over the candidates a spec walked "
         "(the cross-PDK funnel-rate signal).",
         "",
         "| spec | tier | arm | variant | pdk | feasible | first-feasible | iters | evals | "
         "escalated | best_obj | margins (worst) | stages(b/s/f of n) | iip3_dbm | stability | notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        worst = r.get("worst_margin")
        worst_s = ("%s=%.3g" % (worst[0], worst[1])
                   if worst and isinstance(worst[1], (int, float)) else "-")
        sr = r.get("stage_rates") or {}
        stage_s = ("%s/%s/%s of %s" % (sr.get("n_bias", "-"), sr.get("n_sized", "-"),
                                       sr.get("n_feasible", "-"),
                                       sr.get("n_candidates", "-"))
                   if sr else "-")
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                 % (r.get("spec"), r.get("tier"), r.get("arm"),
                    r.get("variant") or "-", r.get("pdk") or "-",
                    "YES" if r.get("feasible") else "no",
                    r.get("first_feasible_phase") or "-",
                    _fmt(r.get("iters_to_first_feasible"), "%d")
                    if r.get("iters_to_first_feasible") is not None else "-",
                    _fmt(r.get("evals_to_first_feasible"), "%d")
                    if r.get("evals_to_first_feasible") is not None else
                    _fmt(r.get("total_evals"), "%d"),
                    "yes" if r.get("escalated") else "no",
                    _fmt(r.get("best_obj")), worst_s, stage_s,
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


# ---- cross-PDK stage-rate instrumentation (deliverable 3) -------------------
# Every candidate driver.run_candidate produces carries a `stages` dict
# {parsed, l0, bias, sized, feasible}; arm A synthesizes the same dict per corpus
# topology. This folds a spec's candidate stages into uniform per-stage counts so
# the cross-PDK funnel-rate table (the overfit-to-bptm45 signal = differential
# stage attrition across processes) falls out of results.jsonl MECHANICALLY.
_STAGE_KEYS = ("parsed", "l0", "bias", "sized", "feasible")


def _stage_rates(cand_stages):
    """Fold a list of per-candidate `stages` dicts into {n, parsed, l0, bias,
    sized, feasible} counts. Missing keys count False, so a pre-instrumentation
    candidate (no stages) contributes only to `n`."""
    counts = {k: 0 for k in _STAGE_KEYS}
    n = 0
    for st in cand_stages or []:
        n += 1
        for k in _STAGE_KEYS:
            if (st or {}).get(k):
                counts[k] += 1
    return {"n_candidates": n, **{("n_%s" % k): counts[k] for k in _STAGE_KEYS}}


def _overlay_consult(spec, extra_consult_dir=None):
    """driver.consult_playbook, optionally ALSO searching a system overlay dir.

    Without extra_consult_dir this is driver.consult_playbook verbatim (the
    governed lna/playbook only). With it (ARM3), the exact same query is re-run
    with `--extra-dir <overlay>` so retrieval spans BOTH the governed playbook
    and the system-authored overlay. Returns (hits, argv, error_or_None); never
    fatal. Uses playbook.py's own additive --extra-dir flag (default unchanged).
    """
    if not extra_consult_dir:
        return D.consult_playbook(spec)
    import subprocess
    band = spec.band_type
    kws = [band]
    kws.append("inductorless" if spec.allow_inductorless else "inductor")
    for m in spec.constraints:
        kws.append(m.replace("_db", "").replace("_dbm", "").replace("_ma", ""))
    argv = [sys.executable, os.path.join(LNA, "playbook.py"), "--consult",
            "--json", "--family", "lna", "--keywords", ",".join(sorted(set(kws))),
            "--extra-dir", extra_consult_dir, "--top", "5"]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT,
                             timeout=120)
    except Exception as e:                                        # noqa: BLE001
        return [], argv, "overlay consult subprocess failed: %r" % (e,)
    if out.returncode != 0:
        return [], argv, (out.stderr or out.stdout or "").strip()
    try:
        return json.loads(out.stdout or "[]"), argv, None
    except Exception as e:                                        # noqa: BLE001
        return [], argv, "overlay consult JSON parse failed: %s" % e


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
                   temperature=0.7, pdk=None):
    """One spec through the full loop, reusing driver.py machinery verbatim.

    Mirrors driver.main's control flow (consult -> K propose -> rank -> diagnose
    -> edit_rounds) but parameterized and instrumented so first-feasibility can
    be attributed to a proposal N vs an edit round M. Returns a partial-row dict
    the caller finishes and appends. Never raises past the outer campaign guard.

    `pdk` (cross-PDK v0): threaded into every run_candidate so the whole funnel
    (bias/emission/extract/size) runs on the selected process."""
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
                               cfg["seeds"], cfg["budget"], raw_completion=content,
                               pdk=pdk)
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
                "stage_rates": _stage_rates([c.get("stages") for c in candidates]),
                "notes": "no candidate survived the funnel"}
    ok.sort(key=lambda c: D.rank_key(c, spec))
    best = ok[0]

    # ---- diagnose + edit rounds -------------------------------------------
    edit_stages = []          # stage record for edits (incl. ones that fail ok)
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
                                    raw_completion=content, pdk=pdk)
            ecand["rationale"] = rationale
            total_evals[0] += _size_evals(ecand)
            _note_feasible(ecand, "edit#%d" % er, it)
            edit_stages.append(ecand.get("stages"))    # stage record, all edits
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
        "stage_rates": _stage_rates([c.get("stages") for c in candidates]
                                    + edit_stages),
        "notes": "" if feasible else "infeasible (closest attempt saved)",
    }


# ================================================= ARM2/ARM3 (arch, selflearn)
# CONTENT-NEUTRAL self-diversity prompt. It asks the model to enumerate k
# structurally distinct approaches IN ITS OWN WORDS -- it names no circuit
# family, archetype, metric, or design move (the binding no-injected-content
# clause). {k} is filled from the config; nothing else is domain content.
DIVERSITY_SYSTEM = (
    "You are enumerating distinct engineering approaches to one problem. You "
    "output a numbered list of short, structurally different approach "
    "descriptions in your own words -- not full designs, just the distinguishing "
    "idea of each. You invent no facts; each item is a genuinely different "
    "structural direction from the others."
)

DIVERSITY_USER = (
    "For the design problem specified below, enumerate exactly {k} STRUCTURALLY "
    "DISTINCT approaches you could take. Each approach must differ from the "
    "others in its core structure, not merely in numeric values. Give each as "
    "one short sentence describing its distinguishing structural idea. Output a "
    "plain numbered list (1., 2., ...) and nothing else.\n\n"
    "=== PROBLEM SPECIFICATION ({name}) ===\n{spec_yaml}\n"
)


def _parse_approaches(content, k):
    """Extract up to k numbered approach descriptions from a diversity completion.

    Content-neutral: splits on leading '1.'/'2.'/'-'/'*' markers and keeps the
    text verbatim. Falls back to non-empty lines. Returns a list of strings
    (possibly shorter than k); the caller cycles if it needs more anchors.
    """
    import re
    items = []
    for line in (content or "").splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(?:\(?\d+[.)]|[-*•])\s*(.+)$", s)
        if m:
            items.append(m.group(1).strip())
    if not items:                                   # fallback: any prose lines
        items = [ln.strip() for ln in (content or "").splitlines() if ln.strip()]
    return items[:k] if items else []


def _diversity_call(spec, client, cfg, temperature):
    """One preliminary LLM call: the model enumerates k of ITS OWN structurally
    distinct approaches. Returns (approaches_list, error_or_None). Never fatal --
    an empty list just means arch anchors fall back to plain propose."""
    msgs = [{"role": "system", "content": DIVERSITY_SYSTEM},
            {"role": "user", "content": DIVERSITY_USER.format(
                k=cfg["k"], name=spec.name, spec_yaml=D._spec_yaml(spec))}]
    try:
        resp = client.complete(msgs, temperature=temperature,
                               max_tokens=cfg["max_tokens"], n=1)
    except D.LLMError as e:
        return [], str(e)
    content = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    return _parse_approaches(content, cfg["k"]), None


def _anchor_prompt(spec, hits, approach):
    """A propose prompt that anchors on ONE of the model's own approach strings.

    Reuses driver.build_propose_prompt verbatim and appends a content-neutral
    anchor line quoting the model's OWN approach text -- no domain content added.
    """
    msgs = D.build_propose_prompt(spec, hits)
    anchor = ("\n\n=== YOUR CHOSEN APPROACH FOR THIS PROPOSAL (anchor on it) ===\n"
              "%s\n\nProduce the netlist that realizes THIS approach." % approach)
    msgs[-1] = {"role": msgs[-1]["role"],
                "content": msgs[-1]["content"] + anchor}
    return msgs


def run_spec_arch(spec, client, model_id, cfg, out_dir, traj_dir, no_sim,
                  temperature=0.7, extra_consult_dir=None, pdk=None):
    """ARM2/ARM3 per-spec run: self-diversity + concentration, same TOTAL budget.

    Flow:
      0. consult (ARM3: consult overlay via extra_consult_dir); diversity call.
      1. propose k candidates, each anchored on one of the model's own approaches.
      2. TRIAGE: size every proposal at TRIAGE_SEEDS x triage_budget (cheap).
      3. CONCENTRATE: re-size the triage winner at full `seeds` x budget, then
         run edit_rounds on it -- spending the remaining eval-equivalents.
    Returns the same partial-row shape as run_spec_arm_b (+ triage details), so
    the table/verify code paths are shared.

    `pdk` (cross-PDK v0): threaded into every run_candidate."""
    spec_ref = spec.source
    run_id = uuid.uuid4().hex[:16]
    traj = D.Trajectory(os.path.join(traj_dir, run_id + ".jsonl"), run_id, spec.name)
    total_evals = [0]
    first_feasible = {"phase": None, "iter": None, "evals": None}

    def _note_feasible(cand, phase_label, iteration):
        if first_feasible["phase"] is not None:
            return
        if cand.get("sized") and cand["sized"].get("feasible"):
            first_feasible.update(phase=phase_label, iter=iteration,
                                  evals=total_evals[0])

    triage_budget = max(1, cfg["budget"] // TRIAGE_FRAC)

    hits, _argv, cerr = _overlay_consult(spec, extra_consult_dir)
    n_hits = len(hits or [])
    # overlay attribution: a retrieved id is a system-overlay hit iff a file of
    # that name exists in the overlay dir (overlay entries carry author:system).
    overlay_ids = set()
    if extra_consult_dir and os.path.isdir(extra_consult_dir):
        overlay_ids = {f[:-5] for f in os.listdir(extra_consult_dir)
                       if f.endswith(".json")}
    n_overlay = sum(1 for h in (hits or []) if h.get("id") in overlay_ids)
    traj.row(0, "consult", consult_hits=hits, error_verbatim=cerr,
             next_action="diversity")

    approaches, derr = _diversity_call(spec, client, cfg, temperature)
    traj.row(0, "propose", diagnosis="self-diversity: %d approach(es)"
             % len(approaches), completion_verbatim="\n".join(
                 "%d. %s" % (i + 1, a) for i, a in enumerate(approaches)),
             error_verbatim=derr, next_action="anchor-propose")

    # ---- propose k, anchored on the model's own approaches -----------------
    candidates = []
    for k in range(cfg["k"]):
        if approaches:
            msgs = _anchor_prompt(spec, hits, approaches[k % len(approaches)])
        else:
            msgs = D.build_propose_prompt(spec, hits)     # graceful fallback
        try:
            resp = client.complete(msgs, temperature=temperature,
                                   max_tokens=cfg["max_tokens"], n=1)
        except D.LLMError as e:
            traj.row(k, "propose", error_verbatim=str(e), next_action="skip")
            continue
        ch = (resp.get("choices") or [{}])[0]
        content = (ch.get("message") or {}).get("content", "")
        netlist, rationale, deltas = D.parse_completion(content)
        # TRIAGE sizing: 1 seed, small budget
        cand = D.run_candidate(traj, spec, spec_ref, k, netlist, rationale,
                               deltas, resp.get("model", model_id),
                               resp.get("usage"), "propose", no_sim,
                               TRIAGE_SEEDS, triage_budget, raw_completion=content,
                               pdk=pdk)
        cand["rationale"] = rationale
        cand["approach"] = approaches[k % len(approaches)] if approaches else None
        if not no_sim and (cand.get("sized") is not None
                           or (cand.get("errors") and any(
                               "sizing produced no result" in e for e in cand["errors"]))):
            total_evals[0] += TRIAGE_SEEDS * triage_budget
        _note_feasible(cand, "triage#%d" % k, k)
        candidates.append(cand)

    ok = [c for c in candidates if c["ok"]]
    if not ok:
        traj.row(len(candidates), "diagnose",
                 diagnosis="all triage proposals failed before sizing",
                 next_action="give_up")
        traj.close()
        return {"feasible": False, "first_feasible_phase": first_feasible["phase"],
                "iters_to_first_feasible": first_feasible["iter"],
                "evals_to_first_feasible": first_feasible["evals"],
                "total_evals": total_evals[0], "best_obj": None, "margins": {},
                "worst_margin": None, "run_id": run_id, "best_cand": None,
                "notes": "no candidate survived triage",
                "consult_hits": n_hits, "overlay_hits": n_overlay,
                "stage_rates": _stage_rates([c.get("stages") for c in candidates]),
                "triage": {"n_proposals": len(candidates), "triage_budget": triage_budget,
                           "n_approaches": len(approaches), "winner": None}}

    ok.sort(key=lambda c: D.rank_key(c, spec))
    winner = ok[0]
    conc_stages = []          # concentrate + edit stage records (incl. non-ok)
    traj.row(len(candidates), "diagnose",
             diagnosis="triage winner wl=%s obj=%s (concentrating full budget)"
             % ((winner.get("wl_hash") or "?"), winner.get("objective")),
             wl_hash=winner.get("wl_hash"), next_action="concentrate")

    best = winner
    # ---- CONCENTRATE: full-seed re-size of the winner ----------------------
    if not no_sim:
        it = len(candidates)
        rc = D.run_candidate(traj, spec, spec_ref, it, winner["netlist"],
                             winner.get("rationale"), {}, model_id, None,
                             "propose", no_sim, cfg["seeds"], cfg["budget"],
                             raw_completion=None, pdk=pdk)
        total_evals[0] += cfg["seeds"] * cfg["budget"]
        _note_feasible(rc, "concentrate", it)
        conc_stages.append(rc.get("stages"))
        if rc["ok"]:
            candidates.append(rc)
            ok.append(rc)
            ok.sort(key=lambda c: D.rank_key(c, spec))
            best = ok[0]

        # ---- edit rounds on the concentrated winner -----------------------
        for er in range(cfg["edit_rounds"]):
            if best.get("sized") and best["sized"].get("feasible"):
                break
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
                                    raw_completion=content, pdk=pdk)
            ecand["rationale"] = rationale
            if not no_sim and ecand.get("sized") is not None:
                total_evals[0] += cfg["seeds"] * cfg["budget"]
            _note_feasible(ecand, "edit#%d" % er, it)
            conc_stages.append(ecand.get("stages"))
            if ecand["ok"]:
                candidates.append(ecand)
                ok.append(ecand)
                ok.sort(key=lambda c: D.rank_key(c, spec))
                best = ok[0]

    traj.close()
    sized = best.get("sized") or {}
    margins = sized.get("margins") or {}
    feasible = bool(sized.get("feasible"))
    # stage rates fold triage proposals + concentrate + edits (the whole funnel
    # this variant walked), so the cross-PDK table is uniform with arm B / arm A.
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
        "stage_rates": _stage_rates([c.get("stages") for c in candidates]
                                    + conc_stages),
        "notes": "" if feasible else "infeasible (closest attempt saved)",
        "consult_hits": n_hits, "overlay_hits": n_overlay,
        "triage": {"n_proposals": len(candidates), "triage_budget": triage_budget,
                   "n_approaches": len(approaches),
                   "winner": winner.get("wl_hash")},
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


def run_spec_arm_a(spec, cfg, no_sim, pdk=None):
    """One spec sized over the stored CORPUS at a matched total eval budget.

    NO LLM. Reuses solve_spec.size_tokens + CORPUS verbatim. Feasibility-first
    selection identical to arm B (driver.rank_key semantics). Returns the same
    partial-row shape as run_spec_arm_b, so the table/verify code is shared.

    `pdk` (cross-PDK v0): None -> the spec's pdk (bptm45); a value sizes every
    corpus topology on that process. Each (topology, seed) contributes a `stages`
    dict so the funnel-rate table is uniform with arm B."""
    import solve_spec as SS
    topos, seeds, per, total = _arm_a_plan(cfg)
    spec_ref = spec.source
    best = None
    best_toks = None
    best_label = None
    total_evals = 0
    first_feasible = {"phase": None, "iter": None, "evals": None}
    cand_stages = []           # one per (topology, seed) -- the funnel walked
    idx = 0
    for wl in topos:
        try:
            toks = SS.tokens_for(wl)
        except SystemExit:
            continue
        # a stored corpus topology always parses (it is a token graph) and clears
        # L0 by construction (it is a real corpus LNA); bias/sized/feasible are
        # what the process actually decides -- exactly the arm-B stage semantics.
        for seed in range(1, seeds + 1):
            if no_sim:
                idx += 1
                continue
            st = {"parsed": True, "l0": True, "bias": False, "sized": False,
                  "feasible": False}
            r = SS.size_tokens(list(toks), spec_ref, seed, per, pdk=pdk)
            total_evals += per
            idx += 1
            if r is not None:
                # size_tokens returns non-None only past a conducting bias + a
                # sizable deck, so a result means bias+sized both cleared.
                st["bias"] = True
                st["sized"] = True
                st["feasible"] = bool(r["feasible"])
            cand_stages.append(st)
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
    stage_rates = _stage_rates(cand_stages)
    if best is None:
        return {"feasible": False, "first_feasible_phase": None,
                "iters_to_first_feasible": None, "evals_to_first_feasible": None,
                "total_evals": total_evals, "best_obj": None, "margins": {},
                "worst_margin": None, "run_id": "armA", "best_cand": None,
                "stage_rates": stage_rates,
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
        "stage_rates": stage_rates,
        "notes": "matched total eval budget=%d (%d topos x %d seeds x %d)"
                 % (total, len(topos), seeds, per),
    }


# =================================================================== the runner
def _finish_row(spec_row, spec, arm, partial, out_dir, cfg, escalated,
                do_verify, verify_wide, variant=None, pdk=None):
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
        "variant": variant,
        # cross-PDK v0: the process this row ran on (default bptm45), and the
        # per-stage funnel counts (parse/L0/bias/sized/feasible) so the cross-PDK
        # funnel-rate table falls out of results.jsonl mechanically.
        "pdk": pdk or getattr(spec, "pdk", "bptm45"),
        "stage_rates": partial.get("stage_rates"),
        "triage": partial.get("triage"),
        "consult_hits": partial.get("consult_hits"),
        "overlay_hits": partial.get("overlay_hits"),
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
    ap.add_argument("--variant", choices=VARIANTS, default="v0",
                    help="arm-B family variant (capability-v1): v0=ARM1 byte-"
                         "identical v0 arm-B; arch=ARM2 concentration+self-"
                         "diversity; selflearn=ARM3 arch + reflect-first overlay "
                         "consult. Ignored for --arm A.")
    ap.add_argument("--v0-dir",
                    help="selflearn: dir with v0 arm-B results.jsonl+trajectory/ "
                         "for the reflect stage (default: repo committed armb)")
    ap.add_argument("--reflect-cap", type=int, default=12,
                    help="selflearn: max system overlay entries reflect may write")
    ap.add_argument("--ladder", required=True, help="path to ladder.json")
    ap.add_argument("--out", help="output dir (default depends on env)")
    ap.add_argument("--dry-run", action="store_true", help="arm B: driver DryRunClient")
    ap.add_argument("--no-sim", action="store_true", help="skip ngspice sizing")
    ap.add_argument("--pdk", default=None,
                    help="OVERRIDE the spec's pdk for the WHOLE ladder (bptm45, "
                         "sky130, gf180mcu, ihp_sg13g2). The same 24 ladder YAMLs "
                         "then run on the named process; the supply rail is the "
                         "adapter's, not the spec's. Default: each spec's own pdk "
                         "(bptm45). Applies to both arms.")
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

    # arm A ignores the variant; only arm B carries capability-v1 variants.
    variant = args.variant if args.arm == "B" else None
    extra_consult_dir = None

    # ---- ARM3 REFLECT-FIRST: build the system overlay before the ladder runs.
    # The overlay lives under <out>/system-playbook/ so it is saved in the run
    # output for audit + later commit. reflect reads the v0 arm-B corpus, writes
    # its own entries; consult then retrieves BOTH the governed playbook AND this
    # overlay via playbook.py --extra-dir.
    reflect_summary = None
    if variant == "selflearn":
        import reflect as R
        v0_dir = args.v0_dir or os.path.join(ROOT, "kaggle", "campaigns",
                                             "capability-v0", "armb")
        extra_consult_dir = os.path.join(out_dir, "system-playbook")
        reflect_traj = os.path.join(traj_dir, "reflect.jsonl")
        # reflect is a DIFFERENT phase than propose/edit: under --dry-run it must
        # read fixtures/reflect.json, not the propose fixtures the campaign
        # client serves. Live runs share the same server client.
        reflect_client = (R._ReflectDryRunClient(os.path.join(HERE, "fixtures"))
                          if args.dry_run else client)
        print("[campaign] ARM3 reflect-first: reading v0 corpus %s -> overlay %s"
              % (v0_dir, extra_consult_dir), flush=True)
        try:
            reflect_summary = R.reflect(v0_dir, extra_consult_dir, reflect_client,
                                        model_id, reflect_traj,
                                        cap=args.reflect_cap)
            print("[campaign] reflect wrote %d overlay entry(ies): %s"
                  % (reflect_summary.get("accepted", 0),
                     ", ".join(reflect_summary.get("entries_written", []))),
                  flush=True)
        except Exception as e:                                   # noqa: BLE001
            print("[campaign] reflect FAILED (running with governed playbook "
                  "only): %r" % e, flush=True)
            extra_consult_dir = None

    from spec import Spec
    rows = []
    wall_budget_s = args.wall_budget_min * 60.0
    t_campaign = time.time()
    per_spec_times = []
    do_verify = not args.no_verify and not args.no_sim

    print("campaign arm=%s  variant=%s  pdk=%s  out=%s  specs=%d  "
          "wall_budget=%.0f min  base=%s"
          % (args.arm, variant, args.pdk or "(spec default)", out_dir,
             len(specs), args.wall_budget_min, base_cfg), flush=True)

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
        if args.pdk is not None:
            spec.pdk = args.pdk            # ladder-wide override beats the field
        print("\n[%d/%d] %s (%s, %s) pdk=%s"
              % (i + 1, len(specs), spec.name, spec_row["tier"],
                 spec_row["band"], getattr(spec, "pdk", "bptm45")), flush=True)
        def _run_b(cfg):
            # variant dispatch (arm B). v0 is byte-identical to the v0 arm-B
            # code path (run_spec_arm_b); arch/selflearn use run_spec_arch --
            # selflearn only differs from arch by consulting the overlay dir.
            if variant in ("arch", "selflearn"):
                return run_spec_arch(spec, client, model_id, cfg, out_dir,
                                     traj_dir, args.no_sim,
                                     temperature=args.temperature,
                                     extra_consult_dir=extra_consult_dir,
                                     pdk=args.pdk)
            return run_spec_arm_b(spec, client, model_id, cfg, out_dir, traj_dir,
                                  args.no_sim, temperature=args.temperature,
                                  pdk=args.pdk)

        try:
            if args.arm == "B":
                partial = _run_b(base_cfg)
            else:
                partial = run_spec_arm_a(spec, base_cfg, args.no_sim, pdk=args.pdk)
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
                    partial = _run_b(esc_cfg)
                else:
                    partial = run_spec_arm_a(spec, esc_cfg, args.no_sim,
                                             pdk=args.pdk)
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
                          escalated, do_verify, args.verify_wide_stability,
                          variant=variant, pdk=args.pdk)
        rows.append(row)
        _checkpoint(out_dir, rows)          # after EVERY spec
        dt = time.time() - t0
        per_spec_times.append(dt)
        print("    -> feasible=%s  first=%s  evals=%s  iip3=%s  (%.1f min)"
              % (row["feasible"], row["first_feasible_phase"],
                 row["total_evals"], _fmt(row["iip3_dbm"], "%+.2f"), dt / 60),
              flush=True)

    # ARM3: save the reflect summary + the overlay entries for audit/commit.
    if reflect_summary is not None:
        try:
            with open(os.path.join(out_dir, "reflect-summary.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"variant": variant, "v0_dir": args.v0_dir,
                           "reflect_cap": args.reflect_cap,
                           "summary": reflect_summary}, fh, indent=2, default=str)
        except Exception:
            pass

    n_feas = sum(1 for r in rows if r["feasible"])
    print("\ncampaign done: variant=%s  %d/%d rows, %d feasible; results -> %s"
          % (variant, len(rows), len(specs), n_feas, out_dir), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
