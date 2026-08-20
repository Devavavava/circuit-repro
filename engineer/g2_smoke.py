"""engineer/g2_smoke.py -- the E-7 (G2) SMOKE tier (mechanics check only).

Pre-reg §4.2-4.3 (engineer/E7-MOVES.md): three arms on the pinned dhruva
flagship (ace8383c2fa68d03, dhruva-s), each spending 150 counted env evals,
seeds 1-3, DETERMINISTIC:

  (G) guided  -- primitive edits AIMED at the output stage (the ruled diagnosis
                 "output-stage current-swing limit, Iq x |Z_ac|" names the output
                 device NM6 and its output node; the guided arm proposes edits
                 there, preferring the complementary-add that changes output class).
  (R) random  -- the SAME ruled repertoire (P1-P5,P7 + add_and_connect), moves
                 chosen uniformly at random, no aim. The null that isolates aim.
  (N) no-move -- NO structural edits: sizing-only on the pinned class-A flagship.
                 Establishes the wall is not reachable by sizing (never non-class-A).

WHAT AN "EVAL" IS: one call of the env objective (== one null-sizer eval == 1-2
ngspice calls; nf-gated dhruva-s => 2). Structural proposal + realize() (the L0
token round-trip) is FREE and un-counted; the counted spend is the L1 sizing
probe (env.evaluate -> DC-convergent operating point). A candidate "reaches" iff:
L0 survives (realize ok) AND it is NON-class-A AND L1 survives (sim_ok on its
first sizing eval). Auto-proceed to L2 (up to 500 evals, the OQ-2 ruled cap) on
any reached candidate, using the standard constrained-descent sizing recipe.

SMOKE REFUTES THE HARNESS, NEVER CONFIRMS THE HYPOTHESIS (pre-reg §4.3 / E-6 §7).
The falsifier is read at the FULL tier, not here.

INTERPRETATION LOGGED (pre-reg ambiguity, recorded not guessed): the pre-reg
states "150 evals/arm ... Seeds 1-3". Read as 3 seeds sharing the 150-eval arm
budget => 50 evals/seed, so every arm spends exactly 150 and the seed spread is
covered. (OQ-SMOKE-1 in the results doc.)

    python engineer/g2_smoke.py --evals 150 --seeds 1,2,3
"""
import argparse
import os
import random
import sys
import time

# DETERMINISM ACROSS PROCESSES: topo_to_netlist's internal node labels iterate
# Python sets (topo.pins/nets), whose order depends on string-hash randomization
# (PYTHONHASHSEED). That label order feeds the random arm's node sampling, so
# without a fixed hash seed two PROCESSES disagree on what the random arm reaches
# (the guided arm, which aims at the structurally-derived output node, is immune).
# Pin PYTHONHASHSEED=0 (re-exec once if unset) so every run is byte-reproducible
# -- the pre-reg's "deterministic seeds" requirement, honoured across processes.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import env as _env                       # noqa: E402  (binds deps)
from env import Env, Task, NotSizable, BudgetExhausted  # noqa: E402
import g2_moves as G                     # noqa: E402
import moves as M                        # noqa: E402
from moves import fet_pins, dname, dtype  # noqa: E402

FLAGSHIP_WL = "ace8383c2fa68d03"
FLAGSHIP_SPEC = "dhruva-s"
FLAGSHIP_REF_TS = "2026-08-10T06:00:59+00:00"    # a stored dhruva-s L2 row (n_evals=1264, feasible)

# The ruled diagnosis string the guided arm is GIVEN (and nothing more).
DIAGNOSIS = "output-stage current-swing limit, Iq x |Z_ac|"


# --------------------------------------------------------------- guided aiming
def _output_targets(nl):
    """From the diagnosis (which names the OUTPUT stage), the nodes/devices a
    guided edit should aim at: the output FET, its drain (output) node, and its
    gate node. This is the ONLY thing the guided arm reads beyond the repertoire
    -- it is the experimental variable, disclosed (ledger §6)."""
    outf = G.output_fet(nl)
    if outf is None:
        return None
    _, out_node = M.output_coupler(nl)
    return {"fet": dname(outf), "out_node": out_node,
            "gate": fet_pins(outf)["G"], "src": fet_pins(outf)["S"]}


def propose_guided(nl, rng, ctx):
    """A guided primitive proposal aimed at the output stage. The aim's strongest
    lever for an OUTPUT-CLASS change (what the diagnosis implies is needed) is the
    complementary-device add at the output node -- so the guided arm weights the
    atomic add_and_connect(pmos4, S=VDD, D=out_node) highly, and otherwise applies
    ruled primitives targeting the output FET / node. Returns (nl', move) or
    (None, None). L0 (sane) is re-checked by the caller."""
    tgt = _output_targets(nl)
    if tgt is None:
        return None, None
    r = rng.random()
    # 60%: the class-changing complementary add (aimed); 40%: an aimed generic edit.
    if r < 0.60:
        gate_choices = [tgt["gate"]] + [n for n in M.internal_nodes(nl)
                                        if M.degree(nl, n) >= 4]
        g = rng.choice(sorted(set(gate_choices)))
        pmap = {"D": tgt["out_node"], "G": g, "S": "VDD", "B": "VSS"}
        out = G.add_and_connect_device(M.copy_nl(nl), rng, ctx, t="pmos4",
                                       pinmap=pmap)
        if out is not None:
            return out, "add_and_connect_device(pmos4@out)"
    # aimed generic edits: reconnect the output FET's own terminals, split a
    # splittable node, flip a polarity, add a device onto the output node.
    kind = rng.choice(["p7_reconnect_terminal", "p2_fet_polarity_swap",
                       "p3_split_net", "add_and_connect_device"])
    if kind == "p7_reconnect_terminal":
        pin = rng.choice([M.FET_PINS.index("G"), M.FET_PINS.index("D")])
        out = G.apply_named(nl, kind, rng, ctx, dev=tgt["fet"], pin=pin)
    elif kind == "p2_fet_polarity_swap":
        out = G.apply_named(nl, kind, rng, ctx, target=tgt["fet"])
    elif kind == "p3_split_net":
        cand = [n for n in M.internal_nodes(nl) if M.degree(nl, n) >= 4]
        out = (G.apply_named(nl, kind, rng, ctx, node=rng.choice(sorted(cand)))
               if cand else None)
    else:
        out = G.add_and_connect_device(M.copy_nl(nl), rng, ctx, t="pmos4",
                                       pinmap={"D": tgt["out_node"],
                                               "G": tgt["gate"], "S": "VDD",
                                               "B": "VSS"})
    return (out, kind) if out is not None else (None, None)


def propose_random(nl, rng, ctx):
    """Uniform-random over the SAME ruled repertoire, no aim (the null)."""
    return G.mutate(nl, rng, ctx)


# ------------------------------------------------------------------ arm runner
def _l1_probe(env, mtopo, seed):
    """One L1 sizing probe of a mutant topology: a single env eval at a fixed
    mid-box point. Returns (spent_evals, sim_ok, out) or (spent, None, None) if
    the sizer declines the topology (NotSizable -> costs no eval, contract)."""
    try:
        arena = env._arena_for(mtopo)
    except NotSizable:
        return 0, None, None            # not sizable: no eval charged
    x = np.full(arena.dim, 0.5)
    out = env.evaluate(topology=mtopo, params=x, action="g2-l1-probe")
    return 1, bool(out["sim_ok"]), out


def run_arm(arm, evals, seeds, max_proposals=None, verbose=True):
    """Run one arm to `evals` counted env evals total, split across `seeds`, with
    a MATCHED proposal cap (`max_proposals`, same for G and R -- the fair budget:
    each arm gets the same number of L0 proposals AND the same env-eval cap, and
    stops on whichever binds first). Returns reachability counts + candidates."""
    from spec import Spec
    spec = Spec.load(FLAGSHIP_SPEC)
    ctx = G.ctx_for_spec(spec)
    base_nl = G._flagship_nl()
    per_seed = max(1, evals // len(seeds))
    prop_cap_seed = (max_proposals // len(seeds)) if max_proposals else evals * 60

    reached = []          # non-class-A candidates surviving L0/L1 (dedup by wl)
    seen_wl = set()
    total_spent = 0
    n_proposed = n_l0 = n_nonA = n_l1ok = 0
    t0 = time.time()

    for si, seed in enumerate(seeds):
        # a fresh env per seed (the base topology is the flagship; the mutants get
        # their own cached arenas). Budget = this seed's slice.
        budget = per_seed if si < len(seeds) - 1 else (evals - per_seed * (len(seeds) - 1))
        task = Task("g2-flagship", FLAGSHIP_SPEC, FLAGSHIP_WL, budget=budget,
                    seed=seed, tier=2, ref_ts=FLAGSHIP_REF_TS)
        env = Env(task, budget=budget, seed=seed, logger=None)
        rng = random.Random(seed)

        if arm == "none":
            # no structural edits: size the pinned class-A flagship, seed's slice.
            xr = np.random.default_rng(seed)
            while env.n_evals < budget:
                try:
                    out = env.evaluate(params=xr.random(env.dim), action="g2-none")
                except BudgetExhausted:
                    break
            total_spent += env.n_evals
            continue

        # G / R: propose -> realize (L0, free) -> class check -> L1 probe (counted)
        propose = propose_guided if arm == "guided" else propose_random
        guard = 0
        while env.n_evals < budget and guard < prop_cap_seed:
            guard += 1
            try:
                mut, move = propose(base_nl, rng, ctx)
            except Exception:
                mut, move = None, None
            if mut is None:
                continue
            n_proposed += 1
            r = M.realize(mut, spec)                    # L0 (free)
            if r is None:
                continue
            n_l0 += 1
            mtopo, _seq, wl, canon = r
            isA, cinfo = G.output_class_is_A(canon)
            if isA:
                continue                                # class-A: not what we seek
            n_nonA += 1
            try:
                spent, sim_ok, out = _l1_probe(env, mtopo, seed)  # L1 (counted)
            except BudgetExhausted:
                break
            if sim_ok is None:
                continue                                # NotSizable: no eval spent
            if sim_ok:
                n_l1ok += 1
                if wl not in seen_wl:
                    seen_wl.add(wl)
                    reached.append({"wl": wl, "move": move, "seed": seed,
                                    "n_dev": len(canon), "class_info": cinfo,
                                    "topo": mtopo, "canon": canon,
                                    "l1_obj": out["objective"],
                                    "l1_feasible": out["feasible"]})
        total_spent += env.n_evals

    dt = time.time() - t0
    res = {"arm": arm, "evals_spent": total_spent, "seeds": seeds,
           "n_proposed": n_proposed, "n_l0_survivors": n_l0,
           "n_nonclassA": n_nonA, "n_l1_survivors": n_l1ok,
           "n_reached_distinct": len(reached), "reached": reached,
           "wall_s": round(dt, 1)}
    if verbose:
        print(f"[{arm:>6}] evals={total_spent:>4}  proposed={n_proposed:>5}  "
              f"L0={n_l0:>5}  non-classA={n_nonA:>4}  L1ok={n_l1ok:>4}  "
              f"reached(distinct)={len(reached):>3}  [{dt:.0f}s]")
    return res


# ----------------------------------------------------------------------- L2
def size_l2(cand, cap=500, seed=1, verbose=True):
    """L2 sizing on a reached candidate, driven THROUGH engineer/env.py so the
    500-eval cap (OQ-2 ruling) is a HARD, env-counted cap: env raises
    BudgetExhausted on the eval after `cap`, exactly the pre-reg's counting
    surface ("counted through env.py"). The optimizer is the line's standard CMA-ES
    (null_sizer.run_cmaes -- the same driver the null-sizer/engineer baselines use);
    NOT size.py's constrained_descent, whose internal `budget` args do NOT map 1:1
    to env evals (measured: size_match_first(budget=40) spends ~1400 evals), which
    would blow the ruled cap. Returns a summary with the env-counted eval spend."""
    import null_sizer as NS
    topo = cand["topo"]
    task = Task("g2-l2", FLAGSHIP_SPEC, FLAGSHIP_WL, budget=cap, seed=seed,
                tier=2, ref_ts=FLAGSHIP_REF_TS)
    try:
        env = Env(task, budget=cap, seed=seed, logger=None)
    except Exception as ex:                                       # noqa: BLE001
        return {"wl": cand["wl"], "l2": "env build failed: %s" % str(ex)[:60]}
    try:
        arena = env._arena_for(topo)
    except NotSizable:
        return {"wl": cand["wl"], "l2": "not sizable (prepared_body declined)"}
    f = env.objective_fn(topology=topo)
    t0 = time.time()
    try:
        # run_cmaes(f, n, seed): n is the PROBLEM DIMENSION (arena.dim); the eval
        # budget is enforced by env, which raises BudgetExhausted after `cap`.
        NS.run_cmaes(f, arena.dim, seed)
    except BudgetExhausted:
        pass
    except Exception as ex:                                       # noqa: BLE001
        return {"wl": cand["wl"], "l2": "cmaes error: %s" % str(ex)[:60],
                "n_evals": env.n_evals}
    # env.best() reads env.arena (the flagship's), but we sized a FOREIGN topology
    # in `arena`; read the best directly from THAT arena's free `points` hook
    # (the eval that produced it -- no re-sim), scoring by env's own objective.
    best_m, best_obj = None, float("inf")
    for x, m in arena.points:
        if m is None:
            continue
        o = env.spec.feasible(m)  # noqa: F841  (touch to keep m realized)
        # objective proxy: total normalized violation (lower is better); use the
        # spec's feasibility+margins the same way env does.
        feas_i, viol_i = env.spec.feasible(m)
        score = 0.0 if feas_i else sum((viol_i or {}).values())
        if score < best_obj:
            best_obj, best_m = score, m
    bm = best_m
    if bm is None:
        return {"wl": cand["wl"], "l2": "no convergent sim", "n_evals": env.n_evals}
    feas, viol = env.spec.feasible(bm)
    out = {"wl": cand["wl"], "n_evals": env.n_evals,
           "ngspice_calls": env.ngspice_calls, "l2": "sized",
           "nf_db": bm.get("nf_db"), "s21_db": bm.get("s21_db"),
           "s11_max_db": bm.get("s11_max_db"), "idd_ma": bm.get("idd_ma"),
           "feasible": bool(feas), "violation": round(sum((viol or {}).values()), 4),
           "wall_s": round(time.time() - t0, 1)}
    if verbose:
        print(f"    L2 {cand['wl'][:10]}: NF={_fmt(out['nf_db'])} "
              f"S21={_fmt(out['s21_db'])} S11={_fmt(out['s11_max_db'])} "
              f"Idd={_fmt(out['idd_ma'])} feas={out['feasible']} "
              f"[{env.n_evals} evals / {env.ngspice_calls} ngspice, {out['wall_s']}s]")
    return out


def _fmt(v):
    return "None" if v is None else format(float(v), ".3f")


def main():
    ap = argparse.ArgumentParser(description="G2 smoke tier")
    ap.add_argument("--evals", type=int, default=150, help="counted evals per arm")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--l2-cap", type=int, default=500)
    ap.add_argument("--max-proposals", type=int, default=1500,
                    help="matched L0-proposal cap per arm (G and R)")
    ap.add_argument("--no-l2", action="store_true")
    a = ap.parse_args()
    seeds = [int(s) for s in a.seeds.split(",") if s]

    print(f"G2 SMOKE -- flagship {FLAGSHIP_WL} / {FLAGSHIP_SPEC}, "
          f"{a.evals} evals/arm, seeds {seeds}, matched proposal cap "
          f"{a.max_proposals}/arm")
    print(f"guided diagnosis (given): {DIAGNOSIS!r}\n")
    results = {}
    for arm in ("guided", "random", "none"):
        results[arm] = run_arm(arm, a.evals, seeds, max_proposals=a.max_proposals)

    l2 = {}
    if not a.no_l2:
        for arm in ("guided", "random"):
            for cand in results[arm]["reached"]:
                print(f"\n  auto-L2 [{arm}] candidate {cand['wl'][:10]} "
                      f"(move {cand['move']}):")
                l2[cand["wl"]] = size_l2(cand, cap=a.l2_cap, seed=1)
                break     # smoke: L2 the FIRST reached candidate per arm only
    results["_l2"] = l2

    import json
    print("\n=== JSON ===")
    print(json.dumps({k: (v if k == "_l2" else
                          {kk: vv for kk, vv in v.items() if kk != "reached"}
                          | {"reached": [{k2: c[k2] for k2 in
                                          ("wl", "move", "seed", "n_dev",
                                           "l1_obj", "l1_feasible")}
                                         for c in v["reached"]]})
                      for k, v in results.items()}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
