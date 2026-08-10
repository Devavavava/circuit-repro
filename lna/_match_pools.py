"""Score the WP-MATCH sampling arms on the frozen pool protocol PLUS the motif
rate that the arms were built to move (FINDINGS 29).

`novelty.evaluate` is the §16 protocol every P5 arm has been judged on (NDL@256,
copy fractions, median NN-sim, termination, validity, inductor ratio, spec-L0);
it is called unchanged so these arms are comparable with §24/§28's tables. The
one column added is `port_src` -- the fraction of screen-valid samples whose
input port reaches a transistor source, i.e. the thing the arm intervened on.

    python lna/_match_pools.py --out lna/out/_m/pools.json
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _match_struct as MS                              # noqa: E402
import novelty                                          # noqa: E402
from spec import Spec                                   # noqa: E402
from topology import Topology, parse_arrow_file         # noqa: E402

OUT = os.path.join(HERE, "out")

ARMS = [
    ("P5-v7 nb (adopted baseline)", ["ft_p5v7_nb_s1337"], "wifi24"),
    ("P5-v8 nb", ["ft_p5v8_nb_s1337"], "wifi24"),
    ("pfx uncond (repro)", ["_m/pfx_uncond"], "wifi24"),
    ("pfx all len12", ["_m/pfx_all12"], "wifi24"),
    ("pfx SRC len12", ["_m/pfx_src12"], "wifi24"),
    ("pfx gate len12", ["_m/pfx_gate12"], "wifi24"),
    ("pfx SRC len24", ["_m/pfx_src24"], "wifi24"),
    ("P5-v9m nb (reweight)", ["_m/ft_p5v9m_nb_s1337"], "wifi24"),
    ("P5-v7 wb (adopted baseline)", ["ft_p5v7_wb_s1337"], "wideband-sdr"),
    ("P5-v8 wb", ["ft_p5v8_wb_s1337"], "wideband-sdr"),
    ("P5-v9m wb (reweight)", ["_m/ft_p5v9m_wb_s1337"], "wideband-sdr"),
]


def motif_rate(paths):
    n = src = 0
    for d in paths:
        for p in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
            try:
                t = Topology(parse_arrow_file(p))
            except Exception:                             # noqa: BLE001
                continue
            if not t.valid:
                continue
            n += 1
            src += bool(MS.analyze(t).get("port_src"))
    return n, (src / n if n else 0.0), src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "_m", "pools.json"))
    ap.add_argument("--ref", default="ref-v3")
    a = ap.parse_args()
    _, _, meta = novelty.reference(a.ref)
    print(f"reference {novelty.ref_tag(meta)}\n")
    specs = {}
    print(f"{'arm':<30}{'n':>5}{'NDL':>5}{'PORT_SRC':>10}{'specL0':>8}"
          f"{'copies':>8}{'arch':>7}{'corpus':>8}{'medNN':>7}{'term':>7}"
          f"{'valid':>7}{'indR':>7}")
    rows = []
    for label, dirs, spec_name in ARMS:
        paths = [os.path.join(OUT, d) for d in dirs]
        paths = [p for p in paths if os.path.isdir(p)]
        if not paths:
            print(f"{label:<30}  (pool not on disk)")
            continue
        if spec_name not in specs:
            specs[spec_name] = Spec.load(spec_name)
        m = novelty.evaluate(paths, specs[spec_name], ref=a.ref)
        if not m:
            print(f"{label:<30}  (pool empty / still being written)")
            continue
        n_ok, rate, n_src = motif_rate(paths)
        print(f"{label:<30}{m['n']:>5}{m['ndl']:>5}{rate:>10.4f}"
              f"{m.get('spec_pass_pct', float('nan')):>8.1f}{m['copies_pct']:>8.1f}"
              f"{m['arch_copies_pct']:>7.1f}{m['corpus_copies_pct']:>8.1f}"
              f"{m['median_nn']:>7.3f}{m.get('term_pct', float('nan')):>7.1f}"
              f"{m.get('valid_pct', float('nan')):>7.1f}{m['ind_ratio']:>7.3f}")
        rows.append({"arm": label, "dirs": dirs, "spec": spec_name,
                     "port_src": rate, "n_port_src": n_src, "n_valid": n_ok,
                     "metrics": m})
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump({"ref": novelty.ref_tag(meta), "rows": rows},
              open(a.out, "w"), indent=1, default=str)
    print(f"\nwrote -> {a.out}")


if __name__ == "__main__":
    main()
