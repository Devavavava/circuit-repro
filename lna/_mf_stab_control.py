"""Did multi-finger emission expose a stability problem, or create one?

`check_stab` now reports the Gate-D1/D2 4-band archetype `rfbcs3_tank_cc21_bf0`
as only CONDITIONALLY stable on dhruva-l2 (K_min -17), where it read
unconditional before the cutover. The two candidate explanations are opposite in
meaning:

  (a) the cutover DESTABILISED the design  -> the new emission is suspect;
  (b) single-finger gate resistance was DAMPING it, and the honest harness
      exposes marginal stability that was always there in the design.

Only a control answers it: same archetype, same stored sizing, both emissions.
Gate resistance is a real series loss at the gate, so if (b) holds we should see
K fall as fingers rise -- monotonically, and driven by |S12*S21| rising as the
loss that was swamping the feedback path is removed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bias                       # noqa: E402
import datastore as ds            # noqa: E402
import extract as E               # noqa: E402
import size as S                  # noqa: E402
import templates as T             # noqa: E402
from topology import Topology     # noqa: E402

ARCH = "rfbcs3_tank_cc21_bf0"


def main():
    arch = next(a for a in T.archetypes() if a["name"] == ARCH)
    topo = Topology(arch["seq"])
    # the stored 4-band sizing for this archetype
    row = None
    for r in ds.load("topo_labels"):
        if r.get("spec") != "dhruva-l2" or not r.get("best_params"):
            continue
        g = r.get("graph") or {}
        if g.get("tokens") and Topology(g["tokens"]).n_devices == topo.n_devices:
            if (r.get("provenance") or {}).get("archetype") == ARCH:
                row = r
    if row is None:
        for r in ds.load("topo_labels"):
            if (r.get("provenance") or {}).get("archetype") == ARCH and r.get("best_params"):
                row = r
    if row is None:
        print("no stored sizing found for", ARCH)
        return
    params = row["best_params"]
    spec = S._spec_for_sizing("dhruva-l2")
    b = spec.band
    f0, flo, fhi = float(b["f0"]), float(b["f_lo"]), float(b["f_hi"])
    print(f"{ARCH}  vs dhruva-l2  (sizing from a {row.get('spec')} row)\n")
    print(f"{'w_finger':>10}{'K_f0':>12}{'K_min':>10}{'mu_min':>9}"
          f"{'|S12S21|dB':>12}{'S21':>8}{'NF':>8}  verdict")
    for wf in (None, 8e-6, 4e-6, 2e-6, 1e-6):
        nl, _, rep, _ = bias.insert_bias(topo, sweep=True, inductor_q=12, w_finger=wf)
        if rep.get("skipped") or not nl.two_port:
            continue
        body = E.body_of(nl.emit())
        m = S.eval_metrics(body, params, spec, nf_gated=True)
        st = E.measure_stability(body, params, f0, flo, fhi, npts=201)
        if m is None or st is None:
            print(f"{str(wf):>10}   (failed)")
            continue
        s12s21 = (m.get("s12_db") or 0) + (m.get("s21_db") or 0)
        print(f"{str(wf):>10}{st['k_f0']:>12.4g}{st['k_min']:>10.4g}"
              f"{st['mu_min']:>9.3f}{s12s21:>12.2f}{m['s21_db']:>8.2f}"
              f"{(m.get('nf_db') or float('nan')):>8.3f}  "
              f"{E.stability_verdict(st)[0]}", flush=True)
    print("\nIf K falls monotonically as fingers rise while |S12*S21| rises, the "
          "gate resistance was damping a feedback path the design always had.")


if __name__ == "__main__":
    main()
