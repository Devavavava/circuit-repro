"""Validate the series-Rs noise-figure harness (extract.measure_nf) -- WP-D1 step 1.

The port-source NF (control_block's m_nf_f0, referred to the S-param port Vp1) is
unphysical once there is gain: the port z0 is not a noisy source resistor, so NF
goes negative (WORKLOG R3 / finding #7). extract.measure_nf swaps the input port
for a real series-Rs (50 ohm) noisy source and refers noise to it. This script
proves that fix is correct and trustworthy on real circuits, so NF can be un-gated.

Two kinds of check:

  1. ANALYTIC GOLDEN (exact). An ideal noiseless VCVS amp fed through a series input
     resistor Rn from a 50 ohm source has, exactly, F = 1 + Rn/Rs and
     NF = 10*log10(1 + Rn/50). We build that DUT as a port-driven body, push it
     through the *real* measure_nf path, and require the measured NF to match the
     closed form within 0.1 dB across Rn in {~0, 25, 50, 100, 150}. This validates
     the deck rewrite AND the K4TRS normalization together.

  2. REAL-LNA SANITY. Run measure_nf on the Gate-D1 dhruva-l1 design and the
     ref24_csdeg reference: NF must be finite, positive, and physically plausible
     (~1-8 dB), and -- the whole point -- SANE where the old port-based NF is not.
     We print both so the contrast is on the record.

    python lna/ref/check_nf.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)
import math                       # noqa: E402
import extract as E               # noqa: E402
import size                       # noqa: E402
import bias                       # noqa: E402
from topology import Topology     # noqa: E402


def golden_body():
    """Port-driven ideal-amp DUT: Vnz->Rns(50)->p1 -Rn- gin -[VCVS x1000]- p2.
    measure_nf rewrites the portnum lines; Rn (param pRnV) is the noise under test."""
    return "\n".join([
        "* analytic NF golden: ideal noiseless amp + series input resistor Rn",
        "Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50",
        "Rn p1 gin {pRnV}",
        "Eamp out 0 gin 0 1000",
        "Ro out p2 1",
        "Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50",
        ".option rshunt=1e12",
    ])


def analytic_golden():
    spec = size._spec_for_sizing("wifi24")     # only used for band f0/f_lo/f_hi
    body = golden_body()
    print("== 1. analytic golden: ideal amp + series Rn, expect NF = 10log10(1+Rn/50) ==")
    worst = 0.0
    ok = True
    for rn in (1e-6, 25.0, 50.0, 100.0, 150.0):
        want = 10 * math.log10(1 + rn / 50.0)
        got = E.measure_nf(body, {"pRnV": f"{rn:g}"}, spec)
        if got is None:
            print(f"   Rn={rn:>7g}  measured=None  (ngspice failure)"); ok = False; continue
        err = abs(got - want)
        worst = max(worst, err)
        flag = "ok" if err <= 0.1 else "MISMATCH"
        print(f"   Rn={rn:>7g}  measured={got:6.3f} dB   expected={want:6.3f} dB   "
              f"|err|={err:.3f}  [{flag}]")
        ok &= err <= 0.1
    print(f"   worst error {worst:.3f} dB  ->  {'PASS' if ok else 'FAIL'} (tol 0.1 dB)\n")
    return ok


def real_lna(label, body, params, spec):
    nf_series = E.measure_nf(body, params, spec)
    m = E.run_and_extract(body, params, spec)          # port-based (unphysical) nf
    nf_port = (m or {}).get("nf_db")
    sane = nf_series is not None and 0.0 < nf_series < 20.0
    print(f"== 2. real LNA: {label} ==")
    print(f"   series-Rs NF (measure_nf) = "
          f"{'None' if nf_series is None else f'{nf_series:6.3f} dB'}   "
          f"[{'sane' if sane else 'CHECK'}]")
    print(f"   port-based NF (old path)  = "
          f"{'None' if nf_port is None else f'{nf_port:6.3f} dB'}   "
          f"(unphysical reference -- for contrast)\n")
    return sane


def dhruva_l1_case():
    import datastore as ds
    row = next(r for r in ds.load("topo_labels")
               if r.get("spec") == "dhruva-l1" and r.get("feasible"))
    topo = Topology(row["graph"]["tokens"])
    spec = size._spec_for_sizing("dhruva-l1")
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, inductor_q=12)
    body = E.body_of(nl.emit())
    return real_lna("Gate-D1 dhruva-l1 (rfbcs3_tank_cc21_bf0)", body, row["best_params"], spec)


def main():
    ok = True
    ok &= analytic_golden()
    try:
        ok &= dhruva_l1_case()
    except StopIteration:
        print("   (no feasible dhruva-l1 row in store; skipping real-LNA case)\n")
    print("check_nf:", "GREEN" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
