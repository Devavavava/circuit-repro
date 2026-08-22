"""E-11 mandated mechanics smoke of channel C (UNCOUNTED, no scoring).

From the standard start topology of 3 of the six tasks, generate ~50 regrow
proposals each; report distinct-child-wl rate, decode-failure rate, L0 pass rate.

HARD GATE: if any parent yields < 10 distinct valid children, the channel is dead
as configured -- try generic knobs (cut range, temperature); if still dead, STOP.
"""
import os
import sys
import time

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import random

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(HERE)
LNA = os.path.join(WT, "lna")
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from tasks import get                      # noqa: E402
from env import Env                        # noqa: E402
import e11_regrow as RG                    # noqa: E402


def smoke_parent(tid, n_prop=50, temperature=1.0, min_frac=0.15, max_frac=0.85,
                 seed=1, model=None, stoi=None):
    task = get(tid)
    env = Env(task, budget=task.budget, seed=seed, logger=None)
    spec = env.spec
    parent_toks = list(env.topo.tokens)
    n_ind = env.topo.n_inductors
    cls = "nb" if n_ind >= 1 else "wb"
    rng = random.Random(seed)
    cuts = RG._cut_points(len(parent_toks), rng, n_prop,
                          min_frac=min_frac, max_frac=max_frac)
    t0 = time.time()
    props = RG.regrow_batch(parent_toks, cls, cuts, temperature, model, stoi,
                            max_new_tokens=256, device="cpu")
    gen_s = time.time() - t0
    n = len(props)
    n_decode_fail = sum(1 for p in props if not p["decode_ok"])
    distinct_wl = set()
    n_topo_valid = 0
    n_l0_pass = 0
    parent_wl = env.task.wl_hash
    n_same_as_parent = 0
    for p in props:
        if not p["decode_ok"] or not p["completed_toks"]:
            continue
        topo = RG.decode_to_topo(p["completed_toks"])
        if topo is None:
            continue
        n_topo_valid += 1
        r = RG.realize_topo(topo, spec)
        if r is None:
            continue
        n_l0_pass += 1
        wl = r[2]
        if wl[:8] == parent_wl[:8] or wl == parent_wl:
            n_same_as_parent += 1
        distinct_wl.add(wl)
    return {
        "task": tid, "cls": cls, "n_inductors": n_ind,
        "parent_tok_len": len(parent_toks), "parent_wl": parent_wl[:8],
        "n_proposals": n, "temperature": temperature,
        "cut_range": [min_frac, max_frac],
        "decode_fail": n_decode_fail,
        "decode_fail_rate": round(n_decode_fail / n, 3) if n else None,
        "topo_valid": n_topo_valid,
        "l0_pass": n_l0_pass,
        "l0_pass_rate": round(n_l0_pass / n, 3) if n else None,
        "distinct_child_wl": len(distinct_wl),
        "distinct_excl_parent": len(distinct_wl - {parent_wl}),
        "same_as_parent_hits": n_same_as_parent,
        "gen_seconds": round(gen_s, 1),
        "_wl_set": sorted(distinct_wl - {parent_wl}),
    }


def main():
    model, stoi = RG.load_model("cpu")
    # 3 of the six tasks, band/size-diverse: l1 (18dev NB), l5 (9dev NB), s (18dev)
    tasks = ["dhruva-l1-t2-a", "dhruva-l5-t2-a", "dhruva-s-t2-a"]
    # Generic-knob sweep (the gate's permitted escape): more proposals, a wider
    # cut range, and two temperatures. Aggregate distinct children per parent
    # across the sweep -- distinct children is what the channel supplies stage-1.
    import os as _os
    npr = int(_os.environ.get("E11_NPROP", "100"))
    configs = [
        {"temperature": 1.0, "min_frac": 0.10, "max_frac": 0.90},
        {"temperature": 1.2, "min_frac": 0.10, "max_frac": 0.90},
    ]
    results = []
    for tid in tasks:
        for ci, cfg in enumerate(configs):
            r = smoke_parent(tid, n_prop=npr, model=model, stoi=stoi,
                             seed=1 + ci, **cfg)
            results.append(r)
            print(f"[{tid}] T={r['temperature']} cut={r['cut_range']} "
                  f"| decode_fail {r['decode_fail']}/{r['n_proposals']} "
                  f"({r['decode_fail_rate']}) | L0 {r['l0_pass']}/{r['n_proposals']} "
                  f"({r['l0_pass_rate']}) | distinct_wl {r['distinct_child_wl']} "
                  f"(excl parent {r['distinct_excl_parent']}) "
                  f"| gen {r['gen_seconds']}s", flush=True)
    import json
    # aggregate distinct children per parent across the knob sweep
    per_parent = {}
    for r in results:
        d = per_parent.setdefault(r["task"], {"wl": set(), "l0": 0,
                                              "n": 0, "decode_fail": 0})
        d["wl"].update(r.pop("_wl_set"))
        d["l0"] += r["l0_pass"]
        d["n"] += r["n_proposals"]
        d["decode_fail"] += r["decode_fail"]
    for t, d in per_parent.items():
        d["distinct"] = len(d["wl"])
        d.pop("wl")
    out = os.path.join("/home/dpatni/.claude/jobs/a8f610e5/tmp", "e11_smoke.json")
    json.dump({"per_config": results, "per_parent": per_parent},
              open(out, "w"), indent=2)
    print("\n=== per-parent aggregate across knob sweep ===")
    for t, d in per_parent.items():
        print(f"  {t}: distinct(excl parent)>= {d['distinct']}  "
              f"L0 {d['l0']}/{d['n']}  decode_fail {d['decode_fail']}/{d['n']}")
    print("wrote", out)
    dead = [t for t, d in per_parent.items() if d["distinct"] < 10]
    if dead:
        print("GATE: DEAD parents (<10 distinct valid children):", dead)
    else:
        print("GATE: PASS -- all parents >= 10 distinct valid children")
    return 0


if __name__ == "__main__":
    sys.exit(main())
