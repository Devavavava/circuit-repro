"""Re-run the frozen NDL@256 protocol under every novelty reference (ref-v3).

§14.5 re-froze the adopt-only-if-better baselines when the reference gained the
`templates.py` archetypes (ref-v1 -> ref-v2). Ingesting nine external real/cited
LNAs grows the corpus half 41 -> 50, so the same governance step is due again:
re-measure every checkpoint that faced an adopt/reject decision, re-freeze the
baselines, and flip-check the history.

Nothing here samples a model. It reads the pools already on disk -- which is why
`--ref all` on the *same* files is a controlled comparison: only the measuring
stick moves.

    python lna/_ndl_refv3.py                 # nb + wb table, all three refs
    python lna/_ndl_refv3.py --json out.json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import novelty                                          # noqa: E402
from spec import Spec                                   # noqa: E402

OUT = os.path.join(HERE, "out")

# (label, [pool dirs], spec) -- the pools §14.5 identified, plus the Session-5
# control arms so the newest comparison is re-scored on the same stick.
POOLS = [
    ("P0 prefix-12", ["sweep12repro", "sweep12repro_s2338"], "wifi24"),
    ("P5-v1", ["ft_p5_nb_s1337"], "wifi24"),
    ("P5-v2", ["ft_p5v2_nb_s1337.v2repro"], "wifi24"),
    ("P5-v3 (adopted)", ["ft_p5v2_nb_s1337.v3"], "wifi24"),
    ("P5-v4", ["ft_p5v2_nb_s1337.v4"], "wifi24"),
    ("P5-v5", ["ft_p5v2_nb_s1337"], "wifi24"),
    ("P5-v6", ["ft_p5v6_nb_s1337"], "wifi24"),
    ("ctrl-v1 (nb)", ["ft_ctrl_nb_s1337"], "wifi24"),
    ("ctrl-v1s (nb)", ["ft_ctrls_nb_s1337"], "wifi24"),
    ("P5-v3 wb (adopted)", ["ft_p5v2_wb_s1337"], "wideband-sdr"),
    ("ctrl-v1 wb", ["ft_ctrl_wb_s1337"], "wideband-sdr"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(OUT, "_ingest",
                                                   "ndl_refv3.json"))
    ap.add_argument("--refs", default="all")
    args = ap.parse_args()
    refs = novelty._refs_for(args.refs)

    for v in refs:
        _, _, m = novelty.reference(v)
        print(f"{novelty.ref_tag(m):<28} corpus={m['n_corpus']} "
              f"external={m.get('n_external', 0)} archetypes={m['n_archetypes']}")
    print()

    specs = {n: Spec.load(n) for n in {s for _, _, s in POOLS}}
    rows = []
    for label, dirs, spec_name in POOLS:
        paths = [os.path.join(OUT, d) for d in dirs]
        paths = [p for p in paths if os.path.isdir(p)]
        if not paths:
            print(f"  {label:<20} (pool missing on disk)")
            continue
        per = {}
        for v in refs:
            m = novelty.evaluate(paths, specs[spec_name], ref=v)
            per[v] = m
        first = per[refs[0]]
        cols = "  ".join(f"{v.split('-')[1]}={per[v]['ndl']:>3}" for v in refs)
        last = per[refs[-1]]
        print(f"  {label:<20} n={first['n']:<4} spec={spec_name:<13} "
              f"NDL {cols}   copies(last ref)="
              f"{last['copies_pct']:4.1f}% "
              f"(arch {last['arch_copies_pct']:4.1f}% / corpus "
              f"{last['corpus_copies_pct']:4.1f}% / ext "
              f"{last.get('ext_copies_pct', 0.0):4.1f}%)  "
              f"med_nn={last['median_nn']:.3f} indR={last['ind_ratio']:.3f}",
              flush=True)
        rows.append({"label": label, "dirs": dirs, "spec": spec_name,
                     "by_ref": {v: per[v] for v in refs}})

    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"refs": refs, "rows": rows}, fh, indent=1)
    print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
