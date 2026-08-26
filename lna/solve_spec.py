"""solve_spec.py -- turn a spec into a sized, verified LNA design.

Give it a spec; it searches for a topology and sizes it (CMA-ES driving ngspice)
until it meets the spec, then saves the design so you can render it.

    python lna/solve_spec.py <spec>                 # generate topologies + size (default)
    python lna/solve_spec.py <spec> --corpus        # size a few known-good topologies instead
    python lna/solve_spec.py <spec> --topology WL   # size one specific stored topology

<spec> is a name in lna/specs/ (e.g. wifi24) or a path to a .yaml file.

Output: capacity_tests/../designs/<spec>/design.{tokens,params,meta}.json, then

    python lna/render_design.py --design designs/<spec>/design

Read-only: never writes the label store. Deterministic per seed.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# prefer this checkout; fall back to $LNA_DEPS_ROOT so it also runs from a worktree
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.dirname(HERE)
for _p in (os.path.join(ROOT, "lna"), os.path.join(ROOT, "misc", "ZOAF"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import size as S              # noqa: E402
import null_sizer as N        # noqa: E402
import datastore as ds        # noqa: E402
from spec import Spec         # noqa: E402
from topology import Topology  # noqa: E402

# a few varied known-good topologies (8..20 devices) for --corpus / fallback
CORPUS = ["d6c0e6fc6dc1adaa", "5fa89b4737cdf8cc", "1403690fcd12173e",
          "baea72246df87313", "182aa0c736e801a4", "ace8383c2fa68d03"]
INDUCTOR_Q = 12


def size_tokens(tokens, spec_ref, seed, budget):
    """Size one topology to a spec with CMA-ES. Returns a result dict (feasible,
    best_obj, best_params, metrics, margins) or None if the topology isn't sizable."""
    spec = S._spec_for_sizing(spec_ref, nf_gate=None)
    topo = Topology(list(tokens))
    prep = S.prepared_body(topo, inductor_q=INDUCTOR_Q)
    if prep is None:
        return None
    body, sizable, fixed = prep
    if not sizable:
        return None
    points = []
    obj, names, decode, _ = S.make_objective(body, spec, sizable, fixed, points=points)
    bud = N._Budget(obj, budget, points)
    try:
        N.run_cmaes(bud, len(names), seed)
    except N._BudgetOut:
        pass
    bx, bm = bud.best()
    if bx is None:
        return None
    feas = bool(spec.feasible(bm)[0]) if bm else False
    return {"feasible": feas, "best_obj": round(bud.best_f, 5),
            "best_params": decode(bx), "metrics": bm,
            "margins": ds.margins_for(spec, bm) if bm else {}, "seed": seed}


def tokens_for(wl_hash):
    store = os.path.join(ROOT, "lna", "data", "topo_labels.jsonl")
    for line in open(store):
        r = json.loads(line)
        if r.get("wl_hash") == wl_hash and (r.get("graph") or {}).get("tokens"):
            return list(r["graph"]["tokens"])
    sys.exit(f"no stored topology with tokens for wl_hash={wl_hash}")


def generate_pool(n, seed, out, keep, spec):
    """Generate n topologies with the v7 model, return the L0-passers (best LNA
    score first, up to `keep`) as (label, tokens)."""
    if not (os.path.isdir(out) and
            len([f for f in os.listdir(out) if f.startswith("seq")]) >= n):
        cmd = [sys.executable, os.path.join(ROOT, "lna", "generate.py"),
               "--n", str(n), "--batch", "32", "--prefix", "lna",
               "--prefix-len", "12", "--seed", str(seed), "--device", "cpu",
               "--out", out]
        print(f"generating {n} candidate topologies (~1-2 min on CPU) ...", flush=True)
        subprocess.run(cmd, check=True, cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    passers = []
    for fn in sorted(f for f in os.listdir(out) if f.startswith("seq")):
        toks = [t for t in open(os.path.join(out, fn)).read().replace("\n", "").split("->") if t]
        if not toks:
            continue
        try:
            topo = Topology(toks)
        except Exception:
            continue
        ok = spec.structural_screen(topo)
        if (ok[0] if isinstance(ok, tuple) else bool(ok)):
            passers.append((topo.lna_score()[0], fn, toks))
    passers.sort(key=lambda t: -t[0])
    return [(fn.replace(".txt", ""), toks) for _, fn, toks in passers[:keep]]


def save_design(outdir, name, tokens, res):
    ddir = os.path.join(outdir, name)
    os.makedirs(ddir, exist_ok=True)
    json.dump(list(tokens), open(os.path.join(ddir, "design.tokens.json"), "w"))
    # render_design --design expects tokens.json in the dir + <prefix>.params/.meta
    json.dump(list(tokens), open(os.path.join(ddir, "tokens.json"), "w"))
    json.dump(res["best_params"], open(os.path.join(ddir, "design.params.json"), "w"))
    json.dump({"spec": name, "source": res.get("_label", name),
               "feasible": res["feasible"], "best_obj": res["best_obj"],
               "metrics": res["metrics"], "margins": res["margins"], "seed": res["seed"]},
              open(os.path.join(ddir, "design.meta.json"), "w"))
    return ddir


def main():
    ap = argparse.ArgumentParser(description="spec -> sized LNA design")
    ap.add_argument("spec", help="spec name in lna/specs/ or path to a .yaml")
    ap.add_argument("--corpus", action="store_true", help="size known-good topologies")
    ap.add_argument("--topology", help="size one specific stored topology (wl_hash)")
    ap.add_argument("--pool", type=int, default=64, help="topologies to generate (default 64)")
    ap.add_argument("--keep", type=int, default=12, help="L0-passers to size (default 12)")
    ap.add_argument("--seeds", type=int, default=3, help="CMA-ES seeds per topology")
    ap.add_argument("--budget", type=int, default=300, help="ngspice evals per sizing")
    ap.add_argument("--out", default=os.path.join(ROOT, "designs"),
                    help="output dir (default <repo>/designs)")
    args = ap.parse_args()

    spec = Spec.load(args.spec)                 # validates; accepts name or path
    name = spec.name
    print(f"solving spec '{name}'  (feasible = meets every gated constraint)\n")

    # gather candidate topologies
    if args.topology:
        candidates = [(args.topology[:12], tokens_for(args.topology))]
    elif args.corpus:
        candidates = [(wl[:12], tokens_for(wl)) for wl in CORPUS]
    else:
        work = os.path.join(args.out, "_gen", name)
        os.makedirs(work, exist_ok=True)
        candidates = generate_pool(args.pool, 1337, work, args.keep, spec)
        if not candidates:
            candidates = [(wl[:12], tokens_for(wl)) for wl in CORPUS]
            print("(no generated topology passed the L0 screen; falling back to corpus)")
    print(f"sizing {len(candidates)} topologies x {args.seeds} seeds "
          f"at {args.budget} evals each ...\n", flush=True)

    best = None
    for label, toks in candidates:
        for seed in range(1, args.seeds + 1):
            r = size_tokens(toks, args.spec, seed, args.budget)
            if r is None:
                continue
            r["_label"], r["_tokens"] = label, toks
            if r["feasible"] and (best is None or not best["feasible"]
                                  or r["best_obj"] < best["best_obj"]):
                best = r
            elif best is None or (not best["feasible"] and r["best_obj"] < best["best_obj"]):
                best = r                       # keep the closest miss if nothing feasible

    if best is None:
        sys.exit("no candidate topology was sizable for this spec.")

    ddir = save_design(args.out, name, best["_tokens"], best)
    rel = os.path.relpath(os.path.join(ddir, "design"))
    verdict = "FEASIBLE (meets the spec)" if best["feasible"] else \
        "infeasible -- closest attempt saved (see which metric FAILs)"
    print(f"result: {verdict}")
    print(f"  topology {best['_label']}, seed {best['seed']}, objective {best['best_obj']}")
    print(f"  design saved to {ddir}\n")
    print("view it:")
    print(f"  python lna/render_design.py --design {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
