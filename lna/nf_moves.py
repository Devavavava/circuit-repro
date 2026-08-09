"""1-edit structural search around the low-noise elites, NF in the objective.

Pure sizing measured a hard floor (FINDINGS §17): on `19f723034c0a` the noise
bottoms at 3.73 dB with the broadband match held, and the gain tops out at
~27.6 dB at NF 4.0 -- and the graph already sits at the 16-device budget, so it
has no room for the extra gain stage Friis says would be almost free in noise.
`7b0b485b629cecd2` (nccgcs_s1_R, NF 3.86) carries **14** devices and 6.4 mA of
current headroom, i.e. two free slots. This mutates the elites one edit at a
time (`moves.py` stratum M), realizes each mutant through the full token
round-trip, and sizes the survivors match-first + NF-descent.

Every mutant is SPICE-verified; nothing is claimed off a critic score.

    python lna/nf_moves.py --spec dhruva-s --parents 7b0b485b,19f72303 \
        --n 24 --budget 500 --out lna/out/_nf/m1.json
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import moves as M                 # noqa: E402
import size as S                  # noqa: E402
import templates as T             # noqa: E402
from novelty import wl_features   # noqa: E402
from topology import Topology     # noqa: E402

RECIPE = "nf-v1+move"

# Growth moves, by what they cost against `device_budget`. With the dhruva budget
# at [3,18] a 16-device frontier design can still only afford +1 (cascode) or +2
# (aux path); a full AC-coupled CS stage costs **3** (coupling cap + FET + load),
# so it can only be proposed off a <=15-device parent -- which is why
# `7b0b485b629cecd2` (14 devices, nccgcs_s1_R) is the parent that matters for the
# Friis experiment.
GROWTH = {"stage_add": 3, "aux_path_add": 2, "cascode_add": 1, "buffer_add": 2,
          "match_elem_add": 1, "feedback_add": 1, "degen_add": 1, "load_swap": 0,
          "passive_type_swap": 0, "input_class_swap": 0, "rewire": 0}


def mutate_filtered(nl, rng, ctx, names, tries=16):
    """`moves.mutate` restricted to a named subset, same weights and sanity gate."""
    fns = {n: f for n, f, _ in M.MOVES}
    ws = {n: w for n, _, w in M.MOVES}
    pick = [n for n in names if n in fns]
    if not pick:
        raise SystemExit(f"no known moves in {names!r}")
    for _ in range(tries):
        name = rng.choices(pick, weights=[ws[n] for n in pick], k=1)[0]
        try:
            out = fns[name](M.copy_nl(nl), rng, ctx)
        except Exception:
            out = None
        if out and M.sane(out, ctx["max_dev"], ctx["min_dev"]):
            return out, name
    return None, None


def parent_rows(prefixes, spec_name):
    best = {}
    for r in ds.load("topo_labels"):
        g = r.get("graph") or {}
        h = r.get("wl_hash") or ""
        if not g.get("tokens") or not any(h.startswith(p) for p in prefixes):
            continue
        nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
        rank = (0 if r.get("spec") == spec_name else 1, nf if nf is not None else 1e9)
        if h not in best or rank < best[h][0]:
            best[h] = (rank, r)
    return [v[1] for v in best.values()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="dhruva-s")
    ap.add_argument("--parents", required=True, help="comma-separated wl_hash prefixes")
    ap.add_argument("--n", type=int, default=24, help="distinct mutants to size")
    ap.add_argument("--budget", type=int, default=500, help="NF-descent budget")
    ap.add_argument("--pre-budget", type=int, default=8)
    ap.add_argument("--keep", default="s11", choices=("s11", "s11idd", "tier1"))
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--moves", default=None,
                    help="comma-separated move subset (default: the full set)")
    ap.add_argument("--recipe", default=RECIPE)
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    import nf_campaign as C
    spec = S._spec_for_sizing(a.spec)
    t1 = C.tier1_names(spec)
    keepmap = {"s11": C.MATCH, "s11idd": C.MATCH + ("idd_ma",), "tier1": t1}
    keep = {n: {k: c[k] for k in ("min", "max") if k in c}
            for n, c in spec.constraints.items() if n in keepmap[a.keep]}
    ctx = {"max_dev": spec.topology.get("device_budget", [3, 16])[1],
           "min_dev": spec.topology.get("device_budget", [3, 16])[0],
           "max_inductors": spec.topology.get("max_inductors", 99)}
    rng = random.Random(a.seed)
    movenames = [m for m in (a.moves or '').split(',') if m] or None
    parents = parent_rows([p for p in a.parents.split(",") if p], a.spec)
    if not parents:
        raise SystemExit("no parent rows found")

    # --- propose mutants ------------------------------------------------------
    seen = set()
    for r in ds.load("topo_labels"):
        if r.get("wl_hash"):
            seen.add(r["wl_hash"])
    cand, tries = [], 0
    print(f"parents: {[ (r['wl_hash'][:10], len(Topology(r['graph']['tokens']).devices)) for r in parents ]}")
    while len(cand) < a.n and tries < a.n * 40:
        tries += 1
        r = rng.choice(parents)
        topo = Topology(r["graph"]["tokens"])
        nl, _ = T.topo_to_netlist(topo)
        if nl is None:
            continue
        out, move = (mutate_filtered(nl, rng, ctx, movenames)
                     if movenames else M.mutate(M.copy_nl(nl), rng, ctx))
        if out is None:
            continue
        real = M.realize(out, spec)
        if real is None:
            continue
        mtopo, _seq, wl, _canon = real
        if wl in seen:
            continue
        seen.add(wl)
        cand.append({"topo": mtopo, "wl": wl, "move": move,
                     "parent": r["wl_hash"], "n_dev": len(mtopo.devices)})
    print(f"{len(cand)} distinct novel mutants from {tries} proposals\n")
    print(C.HDR)

    results = []
    for c in cand:
        t0 = time.time()
        prep = S.prepared_body(c["topo"], inductor_q=12)
        name = f"{c['move'][:14]}/{c['wl'][:6]}"
        if prep is None:
            print(f"{name:<22}    -     -   (bias insert skipped)")
            continue
        pre = S.size_match_first(c["topo"], spec, seed=1, inductor_q=12,
                                 budget=a.pre_budget, polish_budget=0)
        if pre is None or pre.get("metrics") is None:
            print(f"{name:<22}    -     -   (match-first sizing failed)")
            continue
        res = S.constrained_descent(c["topo"], spec, pre["best_params"],
                                    target=("nf_db", "min"), keep=keep,
                                    budget=a.budget, seed=0, prepared=prep)
        if res is None or res.get("metrics") is None:
            print(f"{name:<22}    -     -   (descent failed)")
            continue
        m, bp = res["metrics"], res["best_params"]
        feas, viol = spec.feasible(m)
        tot = sum(viol.values()) if viol else 0.0
        ne = pre["n_evals"] + res["n_evals"]
        print(f"{name:<22} {c['n_dev']:>4} {ne:>5} {C._row(m)} {tot:>7.3f}  "
              f"{'** TIER-2 FEASIBLE **' if feas else ''}  [{time.time()-t0:.0f}s]",
              flush=True)
        results.append({"wl_hash": c["wl"], "move": c["move"], "parent": c["parent"],
                        "n_dev": c["n_dev"], "metrics": m, "feasible": feas,
                        "violation": tot, "best_params": bp, "n_evals": ne})
        if not a.no_log:
            S.log_l2_result(spec, c["topo"], m, feas, bp,
                            {"source_arm": "nf-moves", "move": c["move"],
                             "parent_wl_hash": c["parent"], "keep": a.keep,
                             "inductor_q": 12,
                             "device_budget": ctx["max_dev"]}, a.recipe, ne,
                            inductor_q=12,
                            repeat_probe=False)
    results.sort(key=lambda r: r["metrics"].get("nf_db") or 1e9)
    print("\nbest by NF:")
    for r in results[:8]:
        print(f"  {r['move']:<18} {r['wl_hash'][:10]} dev={r['n_dev']:>2} "
              f"NF {r['metrics'].get('nf_db'):.2f}  S21 {r['metrics'].get('s21_db'):.2f} "
              f" viol {r['violation']:.3f}")
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(results, open(a.out, "w"), indent=1, default=str)
        print(f"wrote {len(results)} -> {a.out}")


if __name__ == "__main__":
    main()
