"""Verify that `size.log_l2_result` actually stores the noise budget (WP-L5)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import size as S                  # noqa: E402
from topology import Topology     # noqa: E402
from _nf_fingers import best_row  # noqa: E402


def main():
    r = best_row("86d5ce", "dhruva-l5")
    spec = S._spec_for_sizing("dhruva-l5")
    topo = Topology(r["graph"]["tokens"])
    body = S.prepared_body(topo, inductor_q=12)[0]
    m = S.eval_metrics(body, r["best_params"], spec, nf_gated=True)
    feas = spec.feasible(m)[0]
    S.log_l2_result(spec, topo, m, feas, r["best_params"],
                    {"source_arm": "nf-budget-probe", "inductor_q": 12},
                    "l5-nf-v1", 1, inductor_q=12, repeat_probe=True)
    last = None
    for row in ds.load("topo_labels"):
        if (row.get("provenance") or {}).get("source_arm") == "nf-budget-probe":
            last = row
    nb = (last or {}).get("provenance", {}).get("noise_budget")
    print("stored noise_budget:", json.dumps(nb, indent=1)[:900] if nb else "MISSING")
    print("OK" if nb and nb.get("top") and nb.get("mos_mech_frac") else "FAILED")


if __name__ == "__main__":
    main()
