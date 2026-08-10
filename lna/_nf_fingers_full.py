"""Does the finger count move anything EXCEPT noise? (WP-L5 phase 1 control.)

If NF= changed the operating point or the RF response, the NF-vs-fingers sweep
would be comparing different circuits and would prove nothing. This re-measures
the full metric vector at each finger count. W_total, L and every sized value are
identical throughout -- only the gate-electrode geometry changes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import size as S                  # noqa: E402
from topology import Topology     # noqa: E402
from _nf_fingers import best_row, with_fingers   # noqa: E402


def main():
    hp = sys.argv[1] if len(sys.argv) > 1 else "439032"
    spec_name = sys.argv[2] if len(sys.argv) > 2 else "dhruva-l5"
    fingers = [1, 2, 4, 8, 16, 32]
    r = best_row(hp, spec_name)
    spec = S._spec_for_sizing(spec_name)
    base = S.prepared_body(Topology(r["graph"]["tokens"]), inductor_q=12)[0]
    print(f"{r['wl_hash'][:14]} vs {spec_name} -- full metric vector vs fingers\n")
    print(f"{'fingers':>8}{'S11_max':>10}{'S21':>9}{'Idd':>8}{'NF':>8}{'K_min':>10}"
          f"{'feasible':>10}")
    for n in fingers:
        body = base if n == 1 else with_fingers(base, n)
        m = S.eval_metrics(body, r["best_params"], spec, nf_gated=True)
        if m is None:
            print(f"{n:>8}   sim failed")
            continue
        feas = spec.feasible(m)[0]
        print(f"{n:>8}{m['s11_max_db']:>10.3f}{m['s21_db']:>9.3f}"
              f"{m['idd_ma']:>8.3f}{m['nf_db']:>8.3f}{m['k_min']:>10.4g}"
              f"{str(feas):>10}", flush=True)


if __name__ == "__main__":
    main()
