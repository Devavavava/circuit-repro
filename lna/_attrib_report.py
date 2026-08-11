"""WP-ATTRIB step 4 -- the one funnel table (plans2/10 section 1.3 step 7).

Reads the three artefacts the earlier steps wrote (gen_stats.json,
bias_stats.json, sized.json + rank.json) and prints ONE table per arm, ending in
the program's currency: near-feasible and feasible-novel per SPICE-minute,
accounted exactly the way loop.spice_curve does (n_evals * SEC_PER_SIM / 60).

    python lna/_attrib_report.py [--md]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "out", "_at")

from loop import SEC_PER_SIM                                      # noqa: E402

ARMS = ["GR", "GR+RAG", "G2", "G3"]
LABEL = {"GR": "GR grammar-only", "GR+RAG": "GR+RAG grammar+retrieval",
         "G2": "G2 pretrained prefix-12", "G3": "G3 P5-v7 (adopted)"}


def _load(name):
    p = os.path.join(OUT, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def build(spec="wifi24"):
    gen = _load("gen_stats.json") or {}
    bias = _load("bias_stats.json") or {}
    pool = _load("pool.json") or {}
    rank = _load("rank.json") or {}
    import glob as _g
    sized = {"results": []}
    for _p in sorted(_g.glob(os.path.join(OUT, "sized*.json"))):
        with open(_p, encoding="utf-8") as fh:
            sized["results"].extend(json.load(fh).get("results", []))
    per_arm_pool = pool.get("per_arm", {})
    rows = {}
    for arm in ARMS:
        g = gen.get(f"{spec}|{arm}") or {}
        b = bias.get(arm) or {}
        p = per_arm_pool.get(arm) or {}
        rs = [r for r in sized["results"] if r.get("arm") == arm]
        ok = [r for r in rs if r.get("ok")]
        sims = sum((r.get("n_evals") or 0) for r in rs)
        smin = sims * SEC_PER_SIM / 60.0
        near = sum(1 for r in ok if r.get("near"))
        feas = sum(1 for r in ok if r.get("feasible"))
        rows[arm] = {
            "n": g.get("n"), "valid_pct": g.get("valid_pct"),
            "term_pct": g.get("term_pct"),
            "l0": g.get("spec_pass"), "l0_pct": g.get("spec_pass_pct"),
            "ndl": g.get("ndl"), "copies_pct": g.get("copies_pct"),
            "median_nn": g.get("median_nn"), "ind_ratio": g.get("ind_ratio"),
            "conduct": b.get("all_conduct"),
            "conduct_pct": b.get("all_conduct_pct"),
            "wl_distinct_novel": p.get("wl_distinct_novel"),
            "qualifying": p.get("qualifying"),
            "sized": len(rs), "sized_ok": len(ok),
            "near": near, "feasible": feas,
            "sims": sims, "spice_min": round(smin, 1),
            "near_per_min": (near / smin) if smin else None,
            "feasnovel_per_min": (feas / smin) if smin else None,
            "best_viol": min([r["viol"] for r in ok], default=None),
            "med_viol": (sorted(r["viol"] for r in ok)[len(ok) // 2]
                         if ok else None),
        }
    return rows, rank, pool


HDR = (f"{'arm':<26} {'n':>4} {'valid':>6} {'L0':>5} {'L0%':>6} {'NDL':>4} "
       f"{'copy%':>6} {'medNN':>6} {'indR':>5} {'cond':>5} {'cond%':>6} "
       f"{'novWL':>6} {'qual':>5} {'sized':>6} {'near':>5} {'feas':>5} "
       f"{'SPICEmin':>9} {'near/min':>9} {'featnov/min':>11}")


def _f(v, fmt="{:.1f}"):
    return "-" if v is None else fmt.format(v)


def show(spec="wifi24", md=False):
    rows, rank, pool = build(spec)
    print(f"\n=== WP-ATTRIB funnel, spec={spec}, ref-v3, 256 samples/arm "
          f"(128 @ 1337 + 128 @ 2338) ===")
    if rank.get("critic"):
        ci = rank["critic"]
        print(f"rung-0 selector (FIXED across arms): {pool.get('selector')}\n"
              f"critic v2 GNN ens-{ci.get('n_models')} on snapshot "
              f"{ci.get('snapshot')} ({ci.get('n_store_rows')} rows, "
              f"{ci.get('n_dropped_pool_hashes')} pool-hash rows dropped), "
              f"holdout rho_S21={ci.get('holdout_rho_s21'):.3f}")
    print(HDR)
    for arm in ARMS:
        r = rows[arm]
        print(f"{LABEL[arm]:<26} {r['n'] or 0:>4} {_f(r['valid_pct']):>6} "
              f"{r['l0'] or 0:>5} {_f(r['l0_pct']):>6} {r['ndl'] or 0:>4} "
              f"{_f(r['copies_pct']):>6} {_f(r['median_nn'], '{:.3f}'):>6} "
              f"{_f(r['ind_ratio'], '{:.3f}'):>5} {r['conduct'] or 0:>5} "
              f"{_f(r['conduct_pct']):>6} {r['wl_distinct_novel'] or 0:>6} "
              f"{r['qualifying'] or 0:>5} {r['sized']:>6} {r['near']:>5} "
              f"{r['feasible']:>5} {_f(r['spice_min']):>9} "
              f"{_f(r['near_per_min'], '{:.3f}'):>9} "
              f"{_f(r['feasnovel_per_min'], '{:.3f}'):>11}")
    print("\nbest / median violation among sized-ok candidates:")
    for arm in ARMS:
        r = rows[arm]
        print(f"  {LABEL[arm]:<26} best {_f(r['best_viol'], '{:.3f}'):>8}   "
              f"median {_f(r['med_viol'], '{:.3f}'):>8}   "
              f"sized-ok {r['sized_ok']}/{r['sized']}")

    g3 = rows["G3"]
    rag = rows["GR+RAG"]
    print("\n--- registered decision rule (plans2/10 section 3) ---")
    if (g3["feasible"] or 0) == 0 and (rag["feasible"] or 0) == 0:
        a, b = rag["near_per_min"], g3["near_per_min"]
        print("  feasible count is 0 in both arms -> the declared tie-breaker "
              "(near-feasible per SPICE-minute) governs.")
        if a and b:
            print(f"  R(GR+RAG)={a:.3f}  R(G3)={b:.3f}  ratio G3/GR+RAG = "
                  f"{b / a:.2f}x" if a else "  GR+RAG scored 0")
        else:
            print(f"  R(GR+RAG)={_f(a, '{:.3f}')}  R(G3)={_f(b, '{:.3f}')}")
    else:
        a, b = rag["feasnovel_per_min"], g3["feasnovel_per_min"]
        print(f"  R(GR+RAG)={_f(a, '{:.3f}')}  R(G3)={_f(b, '{:.3f}')}")
    if md:
        with open(os.path.join(OUT, "funnel.json"), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=2)
        print(f"\nwrote {os.path.join(OUT, 'funnel.json')}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    show(a.spec, a.md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
