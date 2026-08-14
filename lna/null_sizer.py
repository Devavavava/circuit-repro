"""The SIZER's null hypothesis -- untuned search at ZOAF's own budget (N3).

plans2/15-ENGINEER-PROPOSAL §1.5 item 2 and §4.1-N3, which say it plainly:

    "The sizer needs its own null hypothesis. Stage 27 built the generator's
     null (`grammar_gen.py`); nothing plays that role for ZOAF. Run untuned
     CMA-ES + TuRBO-style BO at matched sim budgets on 2-3 of our own sizing
     tasks. If ZOAF doesn't beat the nulls, the program should know now."

`grammar_gen.py` is the same move one level up: a candidate stream with no
learned content, run through the identical downstream harness. This file is that
stream for the *optimizer*: a search with no ZOAF in it, run through the
identical objective, box, deck and eval accounting.

WHAT IS SHARED WITH ZOAF (i.e. what is NOT re-implemented here)
--------------------------------------------------------------
Everything that measures anything. This module never touches ngspice, never
builds a netlist, never decides feasibility:

    bias.insert_bias + classify_params  ->  size.prepared_body(topo, inductor_q)
    the [0,1]^d box and its log/linear
      per-kind decode                   ->  size.make_objective(...) -> decode
    ONE ngspice evaluation              ->  size.make_objective(...) -> the
                                            returned `objective_func`, i.e.
                                            extract.run_and_extract (+
                                            extract.measure_nf when the spec
                                            gates NF) -> spec.objective
    feasibility / margins               ->  spec.feasible, datastore.margins_for

`objective_func` is the exact callable `size.run_zoaf` is handed by
`size.size_topology`, taken unmodified. The nulls differ from ZOAF in one thing
only: which x it is called on next.

BUDGET ACCOUNTING (the whole point -- SURVEY S2/S11: untuned baselines must be
run at matched budgets). ZOAF counts one eval per `objective(x)` call
(`zoaf_core.ZOAF._eval` increments `_n_evals` once per user-objective call, and
that count is what lands in the L2 row's `n_evals`). `_Budget` below counts the
same event, for every arm, and hard-stops the search on the budget-th call --
so "300 evals" means the same number of ngspice invocations for random search,
for CMA-ES and for ZOAF. When the spec gates NF one eval is TWO ngspice calls
(op/sp + series-Rs NF) for every arm alike; both numbers are reported.
`--budget 0` (default) takes the budget from the stored ZOAF row for the same
(topology, spec), which is the tightest match available.

Like ZOAF's own driver, the final best point's metric vector costs no extra
simulation: it is kept from the eval that produced it via `make_objective`'s
free `points` hook, so the reported margins are the ones the sizer actually saw.

THE ARMS
--------
  --algo random   uniform i.i.d. draws from [0,1]^d. The floor under everything;
                  if a null this dumb ties ZOAF, the task is not a search
                  problem and the budget is being spent on nothing.
  --algo cmaes    self-contained CMA-ES, Hansen's standard formulation
                  (purecmaes.m): rank-mu + rank-one covariance update,
                  cumulative step-size adaptation, lambda = 4 + floor(3 ln n),
                  mu = lambda/2 with log-decreasing weights, sigma0 = 0.3 and
                  x0 ~ U[0,1]^n (which is exactly purecmaes' own default, and
                  happens to be this program's box). No tuning, no surrogate,
                  no problem knowledge.
  --algo zoaf     NOT a null -- the incumbent, re-run in-process through the
                  identical counting wrapper, so a budget-matched comparison
                  never rests on the assumption that two eval counters agree.

BOX CONSTRAINTS IN CMA-ES: handled by CLIPPING (projection), not penalty, and
the clipped point is what enters the recombination -- because `make_objective`'s
`decode` already clamps x into [0,1] before mapping it to device values. An
unclipped CMA-ES would therefore be told the value of a point it was never at,
and would build its covariance from fiction. Clipping is also exactly what ZOAF
does (`zoaf_core._clip`), so both arms meet the box the same way. The known cost
is the standard one -- projection can shrink sigma prematurely when the optimum
sits on a face -- and it is why the only deviation from purecmaes below exists:
on stagnation the run RESTARTS from a fresh random mean rather than burning the
remaining budget at sigma ~ 0, since an unspent budget would flatter ZOAF.

NOT A BENCHMARK BY ITSELF. One (topology, spec) is a pilot: it validates the
mechanism and produces one honest row. Claims about "the sizer" need the 2-3
in-house tasks plus the AnalogGym externals of §1.1.

    python lna/null_sizer.py --list-tasks 12
    python lna/null_sizer.py --time-eval --wl-hash 4b351a49fa6e4f23
    python lna/null_sizer.py --algo random --wl-hash 4b351a49fa6e4f23 --seed 1
    python lna/null_sizer.py --algo cmaes  --wl-hash 4b351a49fa6e4f23 --seed 1
    python lna/null_sizer.py --table            # every null_sizer_*.json + ZOAF

Writes ONE new JSON per run under lna/data/null_sizer_*.json. It never appends
to the label store: these are not L2 labels (no ZOAF recipe produced them) and
the append-only tables are not the place to find out what happens if they were.
"""
import argparse
import glob
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds  # noqa: E402
import size as S  # noqa: E402
from topology import Topology  # noqa: E402

DATA_DIR = os.path.join(HERE, "data")
TRACE_EVERY = 10          # best-so-far sample rate, in evals


class _BudgetOut(Exception):
    """Raised by `_Budget` on the call after the budget is spent."""


class _Budget:
    """The single eval counter every arm goes through.

    Counts exactly what ZOAF counts: one tick per call of the objective
    `size.make_objective` returned. Records the best-so-far point, the eval
    index at which it was first reached, and a best-so-far trace every
    `trace_every` evals. Raises `_BudgetOut` instead of running eval
    `budget + 1`, so an arm that plans in generations (CMA-ES) or in phases
    (ZOAF) stops on the eval, not on the iteration."""

    def __init__(self, objective, budget, points, trace_every=TRACE_EVERY):
        self.objective, self.budget = objective, budget
        self.points = points            # the (x, metrics) rows the hook fills
        self.trace_every = trace_every
        self.n = 0                      # evals spent
        self.best_f = float("inf")
        self.best_i = None              # 1-based eval index of the best
        self.trace = []
        self.n_fail = 0                 # simulations that returned no metrics

    def __call__(self, x):
        if self.n >= self.budget:
            raise _BudgetOut()
        f = float(self.objective(np.asarray(x, dtype=float)))
        self.n += 1
        if f >= S.SIM_FAIL_PENALTY:
            self.n_fail += 1
        if f < self.best_f:
            self.best_f, self.best_i = f, self.n
        if self.n % self.trace_every == 0:
            self.trace.append({"n": self.n, "best_obj": self.best_f,
                               "feasible": bool(self.best_f < 0)})
        return f

    def best(self):
        """(x, metrics) of the best eval -- from the points hook, no re-sim."""
        if self.best_i is None:
            return None, None
        x, m = self.points[self.best_i - 1]
        return list(x), m


# ------------------------------------------------------------------- the arms
# Every arm is an infinite loop: the budget is not a parameter of the search,
# it is enforced by `_Budget` raising `_BudgetOut` on the eval after the last
# one. That is deliberate -- an arm that could stop itself could stop early and
# quietly un-match the budget.
def run_random(f, n, seed):
    """Uniform random search over the box. numpy PCG64, seeded."""
    rng = np.random.default_rng(seed)
    while True:
        f(rng.random(n))            # _BudgetOut ends it


def run_cmaes(f, n, seed, sigma0=0.3, lam=None, diag=None):
    """CMA-ES, Hansen's standard formulation (purecmaes.m), self-contained.

    Defaults are the published ones -- nothing here is tuned to this problem:
    lambda = 4 + floor(3 ln n), mu = lambda/2 with log-decreasing weights,
    sigma0 = 0.3 on a unit box, x0 ~ U[0,1]^n. Box handled by clipping (see the
    module docstring). Restarts from a fresh random mean when the search
    stagnates, so the whole matched budget is spent. `diag` is a caller-owned
    dict filled in place with run diagnostics -- it must survive the `_BudgetOut`
    that ends the search, so it is never a return value. The results themselves
    live in the `_Budget`."""
    diag = {} if diag is None else diag
    rng = np.random.default_rng(seed)
    if lam is None:
        lam = 4 + int(math.floor(3 * math.log(n)))
    mu = lam // 2
    w = math.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
    w /= w.sum()
    mueff = 1.0 / float(np.sum(w ** 2))
    # strategy parameters: adaptation rates (Hansen, table of defaults)
    cc = (4 + mueff / n) / (n + 4 + 2 * mueff / n)          # cumulation for C
    cs = (mueff + 2) / (n + mueff + 5)                      # cumulation for sigma
    c1 = 2 / ((n + 1.3) ** 2 + mueff)                       # rank-one rate
    cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
    damps = 1 + 2 * max(0.0, math.sqrt((mueff - 1) / (n + 1)) - 1) + cs
    chiN = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))

    diag.update(lam=lam, mu=mu, mueff=round(mueff, 4), sigma0=sigma0,
                box="clip", restarts=0, gens=0, sigma_final=None)
    while True:                                   # restart loop
        xmean = rng.random(n)
        sigma = sigma0
        pc, ps = np.zeros(n), np.zeros(n)
        B, D = np.eye(n), np.ones(n)
        C, invsqrtC = np.eye(n), np.eye(n)
        counteval, eigeneval = 0, 0
        while True:                               # generation loop
            arx = np.empty((lam, n))
            arf = np.empty(lam)
            for k in range(lam):
                y = B @ (D * rng.standard_normal(n))
                # clip: the evaluated point IS the point the update sees
                arx[k] = np.clip(xmean + sigma * y, 0.0, 1.0)
                arf[k] = f(arx[k])                # may raise _BudgetOut
            counteval += lam
            diag["gens"] += 1
            idx = np.argsort(arf)
            xold = xmean
            xmean = w @ arx[idx[:mu]]

            # cumulative step-size adaptation
            ps = ((1 - cs) * ps
                  + math.sqrt(cs * (2 - cs) * mueff) * (invsqrtC @ (xmean - xold)) / sigma)
            hsig = (float(np.linalg.norm(ps))
                    / math.sqrt(1 - (1 - cs) ** (2 * counteval / lam))
                    / chiN) < (1.4 + 2 / (n + 1))
            pc = ((1 - cc) * pc
                  + (1.0 if hsig else 0.0) * math.sqrt(cc * (2 - cc) * mueff)
                  * (xmean - xold) / sigma)

            # rank-one + rank-mu covariance update
            artmp = (arx[idx[:mu]] - xold) / sigma
            C = ((1 - c1 - cmu) * C
                 + c1 * (np.outer(pc, pc)
                         + (0.0 if hsig else cc * (2 - cc)) * C)
                 + cmu * (artmp.T @ (w[:, None] * artmp)))
            sigma *= math.exp((cs / damps) * (float(np.linalg.norm(ps)) / chiN - 1))

            # lazy eigendecomposition (Hansen's O(n^2)-amortised condition)
            if counteval - eigeneval > lam / (c1 + cmu) / n / 10:
                eigeneval = counteval
                C = np.triu(C) + np.triu(C, 1).T          # enforce symmetry
                dd, B = np.linalg.eigh(C)
                dd = np.maximum(dd, 1e-20)
                D = np.sqrt(dd)
                invsqrtC = B @ np.diag(1.0 / D) @ B.T

            # stagnation -> restart (the only deviation from purecmaes; see the
            # module docstring: an unspent matched budget would flatter ZOAF)
            cond = float(np.max(D) / np.min(D)) if np.min(D) > 0 else np.inf
            diag["sigma_final"] = float(sigma) if np.isfinite(sigma) else None
            flat = float(arf[idx[-1]] - arf[idx[0]]) == 0.0
            if (not np.isfinite(sigma) or sigma * float(np.max(D)) < 1e-11
                    or cond > 1e14 or flat):
                diag["restarts"] += 1
                break


def run_zoaf_ref(f, names, seed, cfg):
    """The incumbent, driven through the same counter. `cfg` carries the stored
    row's ZOAF knobs so the reference arm is the same optimizer, not a guess."""
    S.run_zoaf(f, names, seed=seed,
               n_candidates=int(cfg.get("n_candidates") or 8),
               sgd_iters=int(cfg.get("sgd_iters") or 8),
               cgd_iters=int(cfg.get("cgd_iters") or 2))


ARMS = {"random": "uniform random search over the box",
        "cmaes": "CMA-ES (Hansen purecmaes defaults, box by clipping)",
        "zoaf": "the incumbent ZOAF, same counter (reference arm, not a null)"}


# ------------------------------------------------------------------ the task
def stored_zoaf_rows(spec_name=None, wl_hash=None):
    """L2 rows that carry both a token graph (so the topology is rebuildable)
    and a ZOAF eval count (so a budget can be matched to them)."""
    out = []
    for r in ds.load("topo_labels"):
        if spec_name and r.get("spec") != spec_name:
            continue
        if wl_hash and r.get("wl_hash") != wl_hash:
            continue
        if not (r.get("graph") or {}).get("tokens") or not r.get("n_evals"):
            continue
        out.append(r)
    return out


def build_task(wl_hash, spec_name="wifi24", inductor_q=None, nf_gate=None,
               row=None):
    """Rebuild (deck, box, objective) for a stored (topology, spec) exactly as
    `size.size_topology` would, and return it with the stored ZOAF row.

    `inductor_q` / `nf_gate` default to the stored row's own `zoaf_cfg` stamps:
    a null run under a different deck or a different gating is not a comparison,
    it is a different problem (01-DATA's label-domain rule)."""
    rows = stored_zoaf_rows(spec_name, wl_hash) if row is None else [row]
    if not rows:
        raise SystemExit(f"no stored L2 row with tokens for "
                         f"({wl_hash}, {spec_name})")
    row = rows[-1]                                  # most recent label
    cfg = row.get("zoaf_cfg") or {}
    if inductor_q is None:
        inductor_q = cfg.get("inductor_q")
    if nf_gate is None:
        nf_gate = cfg.get("nf_gated")               # None for pre-WP-D1 rows
    topo = Topology(list(row["graph"]["tokens"]))
    spec = S._spec_for_sizing(spec_name, nf_gate=nf_gate)
    prep = S.prepared_body(topo, inductor_q=(inductor_q or None))
    if prep is None:
        raise SystemExit("bias insertion skipped this topology -- not sizable")
    body, sizable, fixed = prep
    return {"row": row, "cfg": cfg, "topo": topo, "spec": spec, "body": body,
            "sizable": sizable, "fixed": fixed, "inductor_q": inductor_q,
            "nf_gated": S.nf_is_gated(spec)}


def _harness_note(task):
    """What this run's deck differs by from the stored ZOAF row's, if anything.
    Stated, never silently absorbed."""
    cfg, notes = task["cfg"], []
    try:
        from to_spice import W_FINGER as wf
    except Exception:                                          # noqa: BLE001
        wf = None
    if "w_finger" in cfg and cfg["w_finger"] != wf:
        notes.append(f"w_finger stored={cfg['w_finger']} now={wf} "
                     "(pre/post 2026-08-10 finger cutover -- NF not comparable)")
    if cfg.get("nf_gated") is None and task["nf_gated"]:
        notes.append("stored row predates the nf_gated stamp (tier-1 label) "
                     "but this run gates NF -- different label domains")
    if cfg.get("stab_guard") is not None and not cfg.get("stab_guard"):
        notes.append("stored row ran with the stability guard off")
    return notes


# --------------------------------------------------------------------- driver
def run(algo, wl_hash, spec_name="wifi24", budget=0, seed=1, out=None,
        inductor_q=None, nf_gate=None, verbose=True):
    task = build_task(wl_hash, spec_name, inductor_q=inductor_q, nf_gate=nf_gate)
    spec, row, cfg = task["spec"], task["row"], task["cfg"]
    budget = int(budget) or int(row["n_evals"])     # 0 = match the stored ZOAF
    points = []
    objective, names, decode, _evaluate = S.make_objective(
        task["body"], spec, task["sizable"], task["fixed"], points=points,
        op_sink=None)                               # no store writes from here
    n = len(names)
    bud = _Budget(objective, budget, points)
    notes = _harness_note(task)
    if verbose:
        print(f"null_sizer: algo={algo} ({ARMS[algo]})")
        print(f"  task     ({row.get('wl_hash')}, {spec.name}) "
              f"{task['topo'].n_devices} devices, d={n} sizable params")
        print(f"  harness  inductor_q={task['inductor_q']} "
              f"nf_gated={task['nf_gated']} "
              f"({2 if task['nf_gated'] else 1} ngspice calls/eval)")
        print(f"  budget   {budget} evals (stored ZOAF row: {row['n_evals']} "
              f"evals, recipe {cfg.get('recipe')}, seed {cfg.get('seed')})")
        for note in notes:
            print(f"  [note]   {note}")
    t0 = time.time()
    diag = {}
    try:
        if algo == "random":
            run_random(bud, n, seed)
        elif algo == "cmaes":
            run_cmaes(bud, n, seed, diag=diag)
        elif algo == "zoaf":
            run_zoaf_ref(bud, names, seed, cfg)
        else:
            raise SystemExit(f"unknown algo {algo!r}; know {sorted(ARMS)}")
    except _BudgetOut:
        pass
    wall = time.time() - t0

    best_x, best_m = bud.best()
    feas, viol = (spec.feasible(best_m) if best_m else (False, None))
    margins = ds.margins_for(spec, best_m) if best_m else {}
    res = {
        "kind": "null_sizer", "algo": algo, "arm_desc": ARMS[algo],
        "is_null": algo != "zoaf",
        "spec": spec.name, "wl_hash": row.get("wl_hash"),
        "n_devices": task["topo"].n_devices, "n_params": n,
        "param_names": list(names), "seed": seed,
        "budget_evals": budget, "n_evals": bud.n,
        "ngspice_calls": bud.n * (2 if task["nf_gated"] else 1),
        "n_sim_fail": bud.n_fail,
        "evals_to_best": bud.best_i, "best_obj": bud.best_f,
        "feasible": bool(feas),
        "viol": ({k: round(v, 6) for k, v in viol.items()} if viol else {}),
        "metrics": best_m, "margins": margins,
        "best_x": best_x,
        "best_params": (decode(best_x) if best_x is not None else None),
        "trace": bud.trace, "trace_every": TRACE_EVERY,
        "algo_diag": diag,
        "harness": {"inductor_q": task["inductor_q"],
                    "nf_gated": task["nf_gated"],
                    "stab_guard": S._stab_guard_on(),
                    "eval_entry": "size.make_objective(...)[0]",
                    "notes": notes},
        "zoaf_reference": {
            "n_evals": row.get("n_evals"), "recipe": cfg.get("recipe"),
            "seed": cfg.get("seed"), "feasible": row.get("feasible"),
            "best_obj": row.get("best_obj"), "metrics": row.get("metrics"),
            "margins": row.get("margins"), "ts": row.get("ts"),
            "provenance": row.get("provenance")},
        "wall_s": round(wall, 1),
        "s_per_eval": round(wall / max(bud.n, 1), 4),
        "git_sha": ds.git_sha(), "ts": _now(),
    }
    if out is None:
        out = os.path.join(DATA_DIR, f"null_sizer_{algo}_{spec.name}_"
                                     f"{(row.get('wl_hash') or 'ref')[:8]}_"
                                     f"s{seed}_b{budget}.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(_plain(res), fh, indent=1)
    if verbose:
        print(f"\n  {bud.n} evals ({res['ngspice_calls']} ngspice calls) in "
              f"{res['wall_s']}s = {res['s_per_eval']}s/eval"
              + (f", {bud.n_fail} sim failures" if bud.n_fail else ""))
        print(f"  best objective {bud.best_f:.4f} at eval {bud.best_i} -> "
              f"{'FEASIBLE' if feas else 'infeasible ' + str(res['viol'])}")
        if best_m:
            print(spec.report(best_m))
            print("  margins: " + _margin_str(margins))
        print(f"  -> {os.path.relpath(out, HERE)}")
    return res


def _margin_str(margins):
    return "  ".join(
        f"{k}={'--' if v.get('margin') is None else format(v['margin'], '+.3f')}"
        for k, v in margins.items() if v.get("supported"))


def _now():
    """Same stamp format the store rows carry, without importing its private."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _plain(o):
    """numpy -> json-native (the store's `_jsonify` is the store's; this file
    writes its own results file and does not reach into it)."""
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return _plain(o.tolist())
    return o


# ------------------------------------------------------------------- CLI bits
def time_eval(wl_hash, spec_name="wifi24", reps=3, inductor_q=None, nf_gate=None):
    """One eval's wall clock, so a budget can be chosen before spending it."""
    task = build_task(wl_hash, spec_name, inductor_q=inductor_q, nf_gate=nf_gate)
    objective, names, _dec, _ev = S.make_objective(
        task["body"], task["spec"], task["sizable"], task["fixed"])
    rng = np.random.default_rng(0)
    ts = []
    for _ in range(reps):
        t0 = time.time()
        objective(rng.random(len(names)))
        ts.append(time.time() - t0)
    mean = sum(ts) / len(ts)
    print(f"({wl_hash}, {spec_name}) d={len(names)} nf_gated={task['nf_gated']}: "
          + " ".join(f"{t:.3f}s" for t in ts) + f" -> mean {mean:.3f}s/eval "
          f"({2 if task['nf_gated'] else 1} ngspice calls each)")
    print(f"  a {task['row']['n_evals']}-eval budget costs ~"
          f"{mean * task['row']['n_evals'] / 60:.1f} min per arm")
    return mean


def list_tasks(spec_name="wifi24", limit=12, feasible_only=False):
    """Stored (topology, spec) pairs a null can be pointed at."""
    rows = stored_zoaf_rows(spec_name)
    if feasible_only:
        rows = [r for r in rows if r.get("feasible")]
    rows = sorted(rows, key=lambda r: r.get("ts") or "")[::-1][:limit]
    print(f"{'wl_hash':<18} {'dev':>3} {'evals':>6} {'feas':>5} {'obj':>9} "
          f"{'nfg':>5} {'iq':>3} {'recipe':<24} ts")
    for r in rows:
        c = r.get("zoaf_cfg") or {}
        ob = r.get("best_obj")
        print(f"{str(r.get('wl_hash')):<18} {(r.get('graph') or {}).get('n_devices') or 0:>3} "
              f"{r.get('n_evals'):>6} {str(bool(r.get('feasible'))):>5} "
              f"{('%.3f' % ob) if isinstance(ob, (int, float)) else '-':>9} "
              f"{str(c.get('nf_gated')):>5} {str(c.get('inductor_q')):>3} "
              f"{str(c.get('recipe')):<24} {r.get('ts')}")
    return rows


def table(pattern=None):
    """The pilot table: every null_sizer_*.json, plus the stored ZOAF row each
    one was matched against."""
    files = sorted(glob.glob(pattern or os.path.join(DATA_DIR, "null_sizer_*.json")))
    if not files:
        print("no null_sizer_*.json under lna/data/")
        return []
    hdr = (f"{'algo':<8} {'seed':>4} {'budget':>7} {'evals':>6} {'to_best':>8} "
           f"{'best_obj':>9} {'feasible':>9}  margins")
    rows, seen = [], set()
    print(hdr)
    for fp in files:
        with open(fp, encoding="utf-8") as fh:
            r = json.load(fh)
        rows.append(r)
        print(f"{r['algo']:<8} {r['seed']:>4} {r['budget_evals']:>7} "
              f"{r['n_evals']:>6} {str(r['evals_to_best']):>8} "
              f"{r['best_obj']:>9.4f} {('FEASIBLE' if r['feasible'] else 'no'):>9}  "
              + _margin_str(r.get("margins") or {}))
        key = (r["wl_hash"], r["spec"])
        if key not in seen:
            seen.add(key)
            z = r.get("zoaf_reference") or {}
            zo = z.get("best_obj")
            print(f"{'ZOAF*':<8} {str(z.get('seed')):>4} {'-':>7} "
                  f"{str(z.get('n_evals')):>6} {'-':>8} "
                  f"{(('%.4f' % zo) if isinstance(zo, (int, float)) else '-'):>9} "
                  f"{('FEASIBLE' if z.get('feasible') else 'no'):>9}  "
                  + _margin_str(z.get("margins") or {})
                  + f"   [stored row, {z.get('recipe')}]")
    print("\n* ZOAF row is the STORED label for the same (topology, spec); its "
          "margins were measured by the same harness.\n"
          "  Its best_obj is the objective at the point that got logged.")
    return rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algo", choices=sorted(ARMS),
                    help="random | cmaes (the nulls) | zoaf (reference arm)")
    ap.add_argument("--wl-hash", help="stored topology to size (see --list-tasks)")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--budget", type=int, default=0,
                    help="ngspice evals; 0 = match the stored ZOAF row's n_evals")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", help="results json (default lna/data/null_sizer_*.json)")
    ap.add_argument("--inductor-q", type=int, default=None,
                    help="override the stored row's deck Q (0 = ideal)")
    ap.add_argument("--nf-gate", choices=["auto", "on", "off"], default="auto",
                    help="auto = follow the stored row's zoaf_cfg.nf_gated")
    ap.add_argument("--time-eval", action="store_true",
                    help="measure one eval's wall clock and stop")
    ap.add_argument("--list-tasks", type=int, metavar="N", default=0,
                    help="list N stored (topology, spec) tasks with tokens")
    ap.add_argument("--feasible-only", action="store_true",
                    help="--list-tasks: only rows ZOAF got to feasible")
    ap.add_argument("--table", action="store_true",
                    help="print the pilot table from lna/data/null_sizer_*.json")
    a = ap.parse_args()
    nf_gate = {"auto": None, "on": True, "off": False}[a.nf_gate]
    iq = a.inductor_q if a.inductor_q is not None else None
    if a.list_tasks:
        list_tasks(a.spec, a.list_tasks, feasible_only=a.feasible_only)
        return 0
    if a.table:
        table()
        return 0
    if a.time_eval:
        if not a.wl_hash:
            ap.error("--time-eval needs --wl-hash")
        time_eval(a.wl_hash, a.spec, inductor_q=iq, nf_gate=nf_gate)
        return 0
    if not a.algo or not a.wl_hash:
        ap.error("give --algo and --wl-hash (or --list-tasks/--time-eval/--table)")
    run(a.algo, a.wl_hash, a.spec, budget=a.budget, seed=a.seed, out=a.out,
        inductor_q=iq, nf_gate=nf_gate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
