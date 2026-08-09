"""Track-B sidecar: spec-parameterized pool scan + boosted refinement.

Why this exists: `g4_search.py` hardcodes `wifi24` and pulls candidates from the
store by the substring "ft_p5"; Track B needs the same flow against `dhruva-l1`
over a *specific* v6 pool, and the concurrency contract for this session forbids
editing shared .py files. This is a strict superset of g4_search's logic with
`--spec`, `--glob`, `--nf-gate/--no-nf-gate`, `--recipe` and `--shard` added.

Two phases:
  --scan DIR    structural-screen a generation dir, dedupe by wl_hash, size each
                candidate once (light budget), log one L2 row each.
  --refine      take the closest stored rows (by total violation) whose
                token_file matches --glob, and spend polish-first + curated
                multi-seed ZOAF on them (the P5-v3 / Gate-G4 recipe).

Tier-1 note: `--no-nf-gate` reproduces the tier-1 gating (S11/S21/Idd) that Gates
D1/D2 were claimed under, while NF is still measured and reported as advisory.
"""
import argparse
import glob as globmod
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds
import size
from topology import Topology, parse_arrow_file

BUDGET = dict(n_candidates=8, sgd_iters=8, cgd_iters=2)      # anchor-strength
SCAN_BUDGET = dict(n_candidates=6, sgd_iters=6, cgd_iters=1)  # light scan


def total_viol(spec, m):
    feas, viol = spec.feasible(m)
    return (0 if feas else 1, sum(viol.values()) if viol else 0.0)


def fmt(m):
    s11 = m.get("s11_max_db")
    s11 = s11 if s11 is not None else m.get("s11_db")
    return (f"S11max={s11 if s11 is None else round(s11, 1)} "
            f"S21={m.get('s21_db') and round(m['s21_db'], 1)} "
            f"Idd={m.get('idd_ma') and round(m['idd_ma'], 2)} "
            f"NF={m.get('nf_db') and round(m['nf_db'], 2)}")


def tokfile(r):
    return (r.get("provenance") or {}).get("token_file", "")


def scan(args, spec):
    # Novelty vs the VERSIONED reference (ref-v2 = 41 corpus + every templates.py
    # archetype), not the corpus alone -- a regenerated archetype is a copy of
    # training data, which is exactly the hole `_ref_hashes()` below was hand-built
    # to plug for --novel-only refinement (FINDINGS §14.5).
    from novelty import ref_tag, reference, wl_features
    ref_hashes, _, ref_meta = reference()
    novelty_ref = ref_tag(ref_meta)
    files = sorted(globmod.glob(os.path.join(args.scan, "seq*.txt")))
    seen, cands = set(), []
    for f in files:
        try:
            topo = Topology(parse_arrow_file(f))
        except Exception:
            continue
        if not spec.structural_screen(topo)[0]:
            continue
        h = wl_features(topo)[0]
        if h in seen:
            continue
        seen.add(h)
        cands.append((f, topo, h, h not in ref_hashes))
    print(f"[scan] {len(files)} seqs -> {len(cands)} screen-passing distinct "
          f"(spec {spec.name}; novelty vs {novelty_ref})", flush=True)
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        cands = [c for k, c in enumerate(cands) if k % n == i]
        print(f"[scan] shard {args.shard}: {len(cands)} candidates", flush=True)
    cands = cands[:args.limit] if args.limit else cands
    out = []
    for f, topo, h, novel in cands:
        name = os.path.basename(f)
        try:
            res = size.size_topology(topo, spec, seed=args.seed, inductor_q=12,
                                     log=False, **SCAN_BUDGET)
        except Exception as e:
            print(f"  {name:<14} ERROR {e}", flush=True)
            continue
        if not res or not res.get("metrics"):
            print(f"  {name:<14} no metrics", flush=True)
            continue
        m, tv = res["metrics"], total_viol(spec, res["metrics"])
        prov = {"source_arm": args.source_arm, "token_file": f.replace("\\", "/"),
                "novel": bool(novel), "novelty_ref": novelty_ref,
                "wl_hash": h, "trackb": True}
        if not args.no_log:
            size.log_l2_result(spec, topo, m, res["feasible"], res["best_params"],
                               prov, args.recipe, res.get("n_evals") or 0)
        print(f"  {name:<14} viol={tv[1]:7.3f} {fmt(m)} novel={novel} "
              f"feas={res['feasible']}", flush=True)
        out.append((tv, name, m))
    out.sort()
    print("\n[scan] closest:", flush=True)
    for tv, name, m in out[:12]:
        print(f"  {name:<14} viol={tv[1]:7.3f} {fmt(m)}", flush=True)
    return 0


def _ref_hashes():
    """(archetype wl -> name, corpus wl set) from the Track-B snapshot. A claimed
    win must match NEITHER: the P5 pools regenerate templates.py archetypes
    verbatim (~50% of screen-passing samples).

    Kept as a pinned snapshot: it names the archetype a candidate collides with,
    which `novelty.reference()` (now ref-v2, the same union) does not, and it
    freezes the 148-archetype set the Track-B claims were checked against."""
    p = "lna/out/_trackb_ref_hashes.json"
    d = json.load(open(p, encoding="utf-8"))
    return {a["wl"]: a["name"] for a in d["archetypes"]}, set(d["corpus_hashes"])


def refine(args, spec):
    arch, corp = _ref_hashes() if args.novel_only else ({}, set())
    l2 = ds.load("topo_labels")
    feasible_keys = {(r.get("wl_hash"), r.get("spec")) for r in l2 if r.get("feasible")}
    cands, seen = [], set()
    for r in l2:
        if r.get("spec") != spec.name:
            continue
        if args.glob and args.glob not in tokfile(r):
            continue
        if r.get("feasible") or (r.get("wl_hash"), r.get("spec")) in feasible_keys:
            continue
        m, toks = r.get("metrics"), (r.get("graph") or {}).get("tokens")
        if not (m and toks):
            continue
        h = r.get("wl_hash")
        if args.only and os.path.basename(tokfile(r)) not in args.only.split(","):
            continue                              # structure-targeted subset
        if args.novel_only and (h in arch or h in corp):
            continue                              # archetype/corpus copy, not a win
        key = (h, tokfile(r))
        if key in seen:
            continue
        seen.add(key)
        cands.append((total_viol(spec, m)[1], tokfile(r), m, r.get("best_params"),
                      toks, r.get("wl_hash")))
    cands.sort(key=lambda c: c[0])
    top = cands[:args.top]
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        top = [c for k, c in enumerate(top) if k % n == i]
    modes = "+".join(x for x in ("CURATED" if args.curated else "",
                                 "POLISH" if args.polish else "") if x) or "all-free"
    print(f"[refine] top {len(top)} vs {spec.name} [{modes}] "
          f"seeds={args.seed_start}..{args.seed_start + args.seeds - 1}", flush=True)
    for tv, f, m, _bp, _tk, h in top:
        print(f"  {os.path.basename(f):<14} wl={h} viol={tv:7.3f} {fmt(m)}", flush=True)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    n_feasible = 0
    for tv0, f, m0, bp, toks, h in top:
        name = os.path.basename(f)
        topo = Topology(toks)
        if not size.replay_ok(topo, bp, spec, m0):
            print(f"  {name}: replay check FAILED -- quarantined", flush=True)
            continue
        m, params, feas, how = m0, bp, False, ""
        if args.polish:
            pol = size.polish(topo, spec, bp, budget=args.polish_budget)
            if pol and pol.get("metrics") and \
                    total_viol(spec, pol["metrics"]) < total_viol(spec, m):
                m, params, feas, how = (pol["metrics"], pol["best_params"],
                                        pol["feasible"], "polish")
        if not feas:
            best = None
            for s in seeds:
                try:
                    res = size.size_topology(topo, spec, seed=s, inductor_q=12,
                                             log=False, curate=args.curated,
                                             prior_params=bp, **BUDGET)
                except Exception as e:
                    print(f"  {name} seed {s}: ERROR {e}", flush=True)
                    continue
                if res and res.get("metrics") and (
                        best is None or total_viol(spec, res["metrics"]) < best[0]):
                    best = (total_viol(spec, res["metrics"]), s, res["metrics"],
                            res["feasible"], res.get("best_params"))
            if best and best[0] < total_viol(spec, m):
                _, s, m, feas, params = best
                how = ("curated" if args.curated else "seed") + str(s)
                if args.polish and not feas:
                    pol = size.polish(topo, spec, params, budget=args.polish_budget)
                    if pol and pol.get("metrics") and \
                            total_viol(spec, pol["metrics"]) < total_viol(spec, m):
                        m, params, feas, how = (pol["metrics"], pol["best_params"],
                                                pol["feasible"], how + "+polish")
        tv = total_viol(spec, m)
        tag = "   <=== FEASIBLE (tier-1)" if feas else ""
        print(f"  {name:<14} {(how or 'orig'):<16}: {fmt(m)} viol={tv[1]:.3f} "
              f"feasible={feas}{tag}", flush=True)
        if feas and not args.no_log:
            n_feasible += 1
            prov = {"source_arm": args.source_arm, "how": how,
                    "token_file": f.replace("\\", "/"), "wl_hash": h,
                    "curated": bool(args.curated), "polished": "polish" in how,
                    "trackb": True, "nf_gated": not args.no_nf_gate}
            size.log_l2_result(spec, topo, m, feas, params, prov, args.recipe, 100)
    print(f"\n[refine] {n_feasible} feasible design(s) this pass.", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Track-B spec-parameterized G4 flow")
    ap.add_argument("--spec", default="dhruva-l1")
    ap.add_argument("--scan", help="generation dir to screen+size")
    ap.add_argument("--refine", action="store_true")
    ap.add_argument("--glob", default="", help="token_file substring filter (refine)")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--seed-start", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1, help="scan seed")
    ap.add_argument("--curated", action="store_true")
    ap.add_argument("--polish", action="store_true")
    ap.add_argument("--polish-budget", type=int, default=100)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="", help="i/n round-robin split")
    ap.add_argument("--recipe", default="p5v6-gen-v1")
    ap.add_argument("--source-arm", default="trackb-p5v6")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--only", default="",
                    help="comma list of seq basenames to refine (structure-targeted)")
    ap.add_argument("--novel-only", action="store_true",
                    help="refine only candidates whose wl_hash matches no "
                         "templates.py archetype and no corpus circuit")
    ap.add_argument("--no-nf-gate", action="store_true",
                    help="reproduce tier-1 gating (S11/S21/Idd); NF still measured")
    args = ap.parse_args()
    spec = size._spec_for_sizing(args.spec, nf_gate=not args.no_nf_gate)
    gated = [k for k, c in spec.constraints.items() if c.get("status") != "unsupported"]
    print(f"[spec {spec.name}] gated constraints: {gated}", flush=True)
    if args.scan:
        return scan(args, spec)
    if args.refine:
        return refine(args, spec)
    ap.error("need --scan DIR or --refine")


if __name__ == "__main__":
    sys.exit(main())
