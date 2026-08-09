"""Curriculum-arm novel front (FINDINGS §18) — `_ctrl_front.py`'s protocol, byte
for byte, with the store recipe/experiment tag switched to `cur-v1`.

§16's front measurement is the comparison this experiment has to join, so the
protocol must not be re-implemented: this is a thin wrapper that imports
`_ctrl_front` and rebinds two labels. Nothing about the scan budget, the
box-clamped polish, the novelty filter or the gating changes.

    python lna/_cur_front.py --pool lna/out/ft_cur_nb_s1337 --spec wifi24 \
        --arm cur-v1 --scan-limit 14 --top 5 --no-nf-gate \
        --out lna/out/_cur_front_curv1_wifi24.json
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _ctrl_front as cf  # noqa: E402
import size  # noqa: E402

RECIPE = "cur-v1"


def _patch(experiment):
    cf.RECIPE = RECIPE
    orig = size.log_l2_result

    def logged(spec, topo, metrics, feasible, params, prov, recipe, n_evals):
        return orig(spec, topo, metrics, feasible, params,
                    dict(prov, experiment=experiment), recipe, n_evals)
    size.log_l2_result = logged


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--arm", default="cur-v1")
    ap.add_argument("--experiment", default="cur-v1")
    ap.add_argument("--scan-limit", type=int, default=14)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--polish-budget", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-nf-gate", action="store_true")
    ap.add_argument("--allow-store", action="store_true")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    _patch(args.experiment)
    return cf.run(args)


if __name__ == "__main__":
    sys.exit(main())
