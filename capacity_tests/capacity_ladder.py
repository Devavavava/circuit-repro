"""Capacity test: can the LNA branch solve a variety of tasks across difficulty,
or is it clustered around the specs it was tuned on?

Two arms per spec, both using the same deterministic sizer (CMA-ES) at a fixed
budget so the only difference is where the topology comes from:

  ARM A (generator)  -- the v7 model generates a pool of topologies; each spec
                        screens it (L0) and sizes the L0-passers. Tests the
                        TRAINED generator's reach on untuned specs.
  ARM B (corpus)     -- a fixed pool of varied stored topologies is sized to
                        each spec. Tests the sizer's reach given known topologies.

Arm A vs Arm B separates generator overtraining from raw sizer capability; the
easy->hard gradient over the ladder specs shows whether capacity is universal.

Specs: the 6 capacity-ladder rungs (easy1g..xband8) + 3 tuned references
(wifi24, dhruva-l5, gps-l1). "Solved" = any (topology, seed) reaches feasible.

Read-only (no label-store writes). Imports the MAIN checkout's lna/ via
$LNA_DEPS_ROOT so data + the model checkpoint + the ZOAF clone resolve from a
worktree.

    source env.sh
    python capacity_tests/capacity_ladder.py --pool 96 --seeds 3 --workers 24
    python capacity_tests/capacity_ladder.py --aggregate-only --out <file.json>
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "lna"))
sys.path.insert(0, os.path.join(ROOT, "misc", "ZOAF"))

import null_sizer as N          # noqa: E402
import size as S                # noqa: E402
from spec import Spec           # noqa: E402
from topology import Topology   # noqa: E402

# The 6 new ladder specs live in THIS worktree, not the main checkout whose lna/
# code we import. Spec.load accepts a path, and the worktree's specs dir holds
# every spec (tracked + new), so we load them all by worktree path.
WT_SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "lna", "specs")


def spec_id(name):
    p = os.path.join(WT_SPECS, name + ".yaml")
    return p if os.path.exists(p) else name


LADDER = ["easy1g", "n78-35", "sub900", "wb05-2", "unii55", "xband8"]
REFERENCE = ["wifi24", "dhruva-l5", "gps-l1"]
CAP_SPECS = LADDER + REFERENCE

BUDGET = 300
INDUCTOR_Q = 12
ARM_A_MAX = 8            # size at most this many L0-passers per spec (arm A)
CORPUS_HASHES = [        # varied stored topologies for arm B (8..20 devices)
    "d6c0e6fc6dc1adaa", "5fa89b4737cdf8cc", "1403690fcd12173e",
    "baea72246df87313", "182aa0c736e801a4", "ace8383c2fa68d03",
]

_POOL = []               # arm-A generated token lists
_CORPUS = {}             # wl_hash -> token list


# ------------------------------------------------------------------- the sizer
def size_tokens(tokens, spec_name, seed, budget=BUDGET):
    """Size one topology (given as a token list) to a spec with CMA-ES. Returns
    (feasible, best_obj, evals_to_best, n_evals) or None if not sizable."""
    spec = S._spec_for_sizing(spec_id(spec_name), nf_gate=None)
    topo = Topology(list(tokens))
    prep = S.prepared_body(topo, inductor_q=INDUCTOR_Q)
    if prep is None:
        return None
    body, sizable, fixed = prep
    if not sizable:
        return None
    points = []
    obj, names, decode, _ = S.make_objective(body, spec, sizable, fixed,
                                              points=points)
    bud = N._Budget(obj, budget, points)
    try:
        N.run_cmaes(bud, len(names), seed)
    except N._BudgetOut:
        pass
    bx, bm = bud.best()
    feas = bool(spec.feasible(bm)[0]) if bm else False
    return {"feasible": feas, "best_obj": round(bud.best_f, 5),
            "evals_to_best": bud.best_i, "n_evals": bud.n}


# ------------------------------------------------------------------------ arms
def screen_pool_for(spec_name):
    """L0-passing topologies from the generated pool, best LNA score first."""
    spec = Spec.load(spec_id(spec_name))
    passers = []
    for i, toks in enumerate(_POOL):
        try:
            topo = Topology(list(toks))
        except Exception:
            continue
        ok = spec.structural_screen(topo)
        passed = ok[0] if isinstance(ok, tuple) else bool(ok)
        if passed:
            passers.append((topo.lna_score()[0], i))
    passers.sort(reverse=True)
    return [i for _, i in passers[:ARM_A_MAX]]


def run_spec_cell(args):
    """One (arm, spec, item, seed) sizing. `item` is a pool index (A) or a
    wl_hash (B)."""
    arm, spec_name, item, seed = args
    try:
        toks = _POOL[item] if arm == "A" else _CORPUS[item]
        r = size_tokens(toks, spec_name, seed)
        if r is None:
            return {"arm": arm, "spec": spec_name, "item": item, "seed": seed,
                    "skip": "not sizable"}
        r.update(arm=arm, spec=spec_name, item=item, seed=seed)
        return r
    except BaseException as e:
        return {"arm": arm, "spec": spec_name, "item": item, "seed": seed,
                "skip": f"{type(e).__name__}: {str(e)[:80]}"}


# ------------------------------------------------------------------ generation
def generate_pool(n, seed, workdir):
    # generate.py runs with cwd=ROOT, so --out must be absolute or it lands under
    # the main checkout while we look for it in the worktree.
    out = os.path.abspath(os.path.join(workdir, "poolgen"))
    cmd = [sys.executable, os.path.join(ROOT, "lna", "generate.py"),
           "--n", str(n), "--batch", "32", "--prefix", "lna",
           "--prefix-len", "12", "--seed", str(seed), "--device", "cpu",
           "--out", out]
    print(f"generating arm-A pool: {n} topologies ...", flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    pool = []
    for fn in sorted(os.listdir(out)):
        if fn.startswith("seq") and fn.endswith(".txt"):
            txt = open(os.path.join(out, fn)).read().strip()
            toks = [t for t in txt.replace("\n", "").split("->") if t]
            if toks:
                pool.append(toks)
    print(f"  pool: {len(pool)} topologies", flush=True)
    return pool


def load_corpus():
    store = os.path.join(ROOT, "lna", "data", "topo_labels.jsonl")
    want = set(CORPUS_HASHES)
    for line in open(store):
        r = json.loads(line)
        wl = r.get("wl_hash")
        if wl in want and wl not in _CORPUS:
            g = r.get("graph") or {}
            if g.get("tokens"):
                _CORPUS[wl] = list(g["tokens"])


def aggregate(res):
    cells = res["cells"]
    print(f"\n=== capacity ladder — arm A (generator) vs arm B (corpus) ===")
    print(f"pool: {res['pool_size']} generated topologies; "
          f"corpus: {len(CORPUS_HASHES)} topologies; budget {BUDGET} evals/size\n")
    print(f"{'spec':<12}{'A solved':>10}{'A best_obj':>12}"
          f"{'B solved':>10}{'B best_obj':>12}")
    for sp in CAP_SPECS:
        a = [c for c in cells if c["arm"] == "A" and c["spec"] == sp and "skip" not in c]
        b = [c for c in cells if c["arm"] == "B" and c["spec"] == sp and "skip" not in c]
        a_solved = any(c["feasible"] for c in a)
        b_solved = any(c["feasible"] for c in b)
        a_best = min((c["best_obj"] for c in a), default=None)
        b_best = min((c["best_obj"] for c in b), default=None)
        tag = "  <-- LADDER" if sp in LADDER else "  (reference)"
        print(f"{sp:<12}{('YES' if a_solved else 'no'):>10}"
              f"{(f'{a_best:.3f}' if a_best is not None else '-'):>12}"
              f"{('YES' if b_solved else 'no'):>10}"
              f"{(f'{b_best:.3f}' if b_best is not None else '-'):>12}{tag}")
    na = sum(sp for sp in [any(c['feasible'] for c in cells
             if c['arm'] == 'A' and c['spec'] == s and 'skip' not in c)
             for s in CAP_SPECS])
    nb = sum(sp for sp in [any(c['feasible'] for c in cells
             if c['arm'] == 'B' and c['spec'] == s and 'skip' not in c)
             for s in CAP_SPECS])
    print(f"\nspecs solved: arm A {na}/{len(CAP_SPECS)}   arm B {nb}/{len(CAP_SPECS)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=int, default=96)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--genseed", type=int, default=1337)
    ap.add_argument("--out", default="capacity_tests/results/capacity_ladder.json")
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()

    if args.aggregate_only:
        aggregate(json.load(open(args.out)))
        return 0

    global _POOL
    workdir = os.path.join(os.path.dirname(args.out), "_work")
    os.makedirs(workdir, exist_ok=True)
    _POOL = generate_pool(args.pool, args.genseed, workdir)
    load_corpus()

    # build the cell list: arm A over each spec's L0-passers, arm B over corpus
    cells_args = []
    for sp in CAP_SPECS:
        for idx in screen_pool_for(sp):
            for seed in range(1, args.seeds + 1):
                cells_args.append(("A", sp, idx, seed))
        for wl in CORPUS_HASHES:
            for seed in range(1, args.seeds + 1):
                cells_args.append(("B", sp, wl, seed))
    print(f"sizing cells: {len(cells_args)}  (workers={args.workers})", flush=True)

    cells, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(run_spec_cell, cells_args), 1):
            cells.append(r)
            if i % 40 == 0 or i == len(cells_args):
                print(f"  {i}/{len(cells_args)} ({time.time()-t0:.0f}s)", flush=True)
    res = {"pool_size": len(_POOL), "budget": BUDGET, "seeds": args.seeds,
           "cap_specs": CAP_SPECS, "ladder": LADDER, "cells": cells}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(res, open(args.out, "w"))
    print(f"done in {time.time()-t0:.0f}s -> {args.out}")
    aggregate(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
