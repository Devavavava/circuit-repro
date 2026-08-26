"""Export the feasible designs found by the capacity + ZOAF-vs-CMA-ES tests as
renderable design files, deterministically re-derived (CMA-ES is seeded, so a
feasible cell reproduces its exact winning sizing).

For each solved spec it writes the best design from the corpus/grid, and -- where
the generator (arm A) also solved it -- the best generated design, so you can see
both. Each design lands in its own dir with tokens.json + design.params.json +
design.meta.json, which lna/render_design.py --design reads.

    source env.sh
    python capacity_tests/export_winners.py
    # then, e.g.:
    python lna/render_design.py --design capacity_tests/designs/n78-35__corpus/design
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import capacity_ladder as C          # noqa: E402
import zoaf_vs_cmaes as Z            # noqa: E402

RESULTS = os.path.join(HERE, "results")
OUTDIR = os.path.join(HERE, "designs")


def best_per(key_fn, cells, feas_fn, obj_fn, tok_fn):
    best = {}
    for c in cells:
        if not feas_fn(c):
            continue
        k = key_fn(c)
        if k not in best or obj_fn(c) < best[k]["best_obj"]:
            best[k] = {"best_obj": obj_fn(c), "seed": c["seed"],
                       "tokens": tok_fn(c), "source": k[1]}
    return best


def write_design(name, tokens, spec, seed):
    r = C.size_tokens(list(tokens), spec, seed, with_design=True)
    if r is None or not r.get("feasible") or "best_params" not in r:
        return None
    ddir = os.path.join(OUTDIR, name)
    os.makedirs(ddir, exist_ok=True)
    json.dump(list(tokens), open(os.path.join(ddir, "tokens.json"), "w"))
    json.dump(r["best_params"], open(os.path.join(ddir, "design.params.json"), "w"))
    json.dump({"source": name, "spec": spec, "seed": seed,
               "feasible": r["feasible"], "best_obj": r["best_obj"],
               "metrics": r["metrics"], "margins": r["margins"]},
              open(os.path.join(ddir, "design.meta.json"), "w"))
    return r["best_obj"]


def main():
    # arm-A pool: regenerate deterministically (same genseed/size as the run)
    print("regenerating arm-A pool (for generated winners) ...", flush=True)
    C._POOL = C.generate_pool(96, 1337, os.path.join(RESULTS, "_work"))
    C.load_corpus()
    Z.load_token_rows()

    cap = json.load(open(os.path.join(RESULTS, "capacity_ladder.json")))["cells"]
    zoaf = [json.loads(l) for l in open(os.path.join(RESULTS, "zoaf_vs_cmaes.jsonl"))]

    # best corpus/grid design per spec (arm B + the zoaf grid's cmaes arm)
    corpus_cells = ([{"spec": c["spec"], "seed": c["seed"], "feasible": c["feasible"],
                      "best_obj": c["best_obj"], "wl": c["item"]}
                     for c in cap if c["arm"] == "B" and "skip" not in c]
                    + [{"spec": r["spec"], "seed": r["seed"],
                        "feasible": r["cmaes"]["feasible"],
                        "best_obj": r["cmaes"]["best_obj"], "wl": r["wl"]}
                       for r in zoaf if "skip" not in r])
    corpus_best = best_per(lambda c: (c["spec"], "corpus"), corpus_cells,
                           lambda c: c["feasible"], lambda c: c["best_obj"],
                           lambda c: Z._TOKEN_ROWS[c["wl"]]["graph"]["tokens"])

    # best generated design per spec (arm A)
    gen_best = best_per(lambda c: (c["spec"], "generated"),
                        [c for c in cap if c["arm"] == "A" and "skip" not in c],
                        lambda c: c["feasible"], lambda c: c["best_obj"],
                        lambda c: C._POOL[c["item"]])

    manifest = []
    for (spec, src), d in sorted({**corpus_best, **gen_best}.items()):
        name = f"{spec}__{src}"
        obj = write_design(name, d["tokens"], spec, d["seed"])
        if obj is not None:
            manifest.append((name, spec, src, obj))
            print(f"  wrote {name}  (best_obj {obj})", flush=True)

    print(f"\n{len(manifest)} designs -> {OUTDIR}")
    print("\n# render each one:")
    for name, spec, src, obj in manifest:
        print(f"python lna/render_design.py --design capacity_tests/designs/{name}/design")
    print("\n# or all at once:")
    print("for d in capacity_tests/designs/*/; do "
          "python lna/render_design.py --design \"$d/design\"; echo; done")
    json.dump({"designs": [{"name": n, "spec": s, "source": src, "best_obj": o}
                           for n, s, src, o in manifest]},
              open(os.path.join(OUTDIR, "manifest.json"), "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
