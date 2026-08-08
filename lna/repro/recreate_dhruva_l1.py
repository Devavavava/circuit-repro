"""Recreate the Gate-D1 feasible dhruva-l1 design (WP-DHRUVA, blind protocol).

Two modes:
  --replay  (default) re-evaluate the stored sized params -> should print the exact
            logged metrics (s11_max -11.2 / S21 37.8 / Idd 12.9, feasible).
  --resize  re-derive the device values from scratch: size the archetype
            `rfbcs3_tank_cc21_bf0` vs dhruva-l1 at seed 5, heavy ZOAF + polish
            (this is the run that first found the feasible point).

IMPORTANT / honest note: the feasible *topology* is a hand-authored generic-
textbook archetype (`templates.rfb_cs3_lna`, a 3-stage resistive-feedback-input +
two tuned CS stages), NOT an output of the P5 neural generator. What the automated
pipeline did here is the device SIZING (ZOAF + polish) and evaluation; the topology
family was added by the assistant under blind-protocol rule 2 (generic textbook, no
paper). See lna/FINDINGS.md Section 12.

    python lna/repro/recreate_dhruva_l1.py            # replay stored params
    python lna/repro/recreate_dhruva_l1.py --resize   # re-derive from scratch
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
sys.path.insert(0, LNA)
import templates as T          # noqa: E402
import size                    # noqa: E402
import bias                    # noqa: E402
import extract as E            # noqa: E402
from topology import Topology  # noqa: E402

ARCH = "rfbcs3_tank_cc21_bf0"
SPEC = "dhruva-l1"


def topo_of():
    a = next(a for a in T.archetypes() if a["name"] == ARCH)
    return Topology(a["seq"])


def replay():
    params = json.load(open(os.path.join(HERE, "dhruva-l1-rfbcs3.params.json")))
    topo = topo_of()
    spec = size._spec_for_sizing(SPEC)
    nl, _, rep, _ = bias.insert_bias(topo, sweep=True, inductor_q=12)
    m = E.run_and_extract(E.body_of(nl.emit()), params, spec)
    feas, viol = spec.feasible(m)
    print(f"REPLAY {ARCH} vs {SPEC}: s11_max={m['s11_max_db']:.2f} "
          f"S21={m['s21_db']:.2f} Idd={m.get('idd_ma') or 0:.2f}  feasible={feas}")
    return feas


def resize():
    topo = topo_of()
    spec = size._spec_for_sizing(SPEC)
    print(f"re-sizing {ARCH} vs {SPEC} at seed 5 (heavy ZOAF + polish)...", flush=True)
    res = size.size_topology(topo, spec, seed=5, inductor_q=12, log=False,
                             curate=False, n_candidates=14, sgd_iters=14, cgd_iters=3)
    m, bp = res["metrics"], res["best_params"]
    pol = size.polish(topo, spec, bp, budget=400, inductor_q=12)
    if pol and pol.get("metrics"):
        m, bp = pol["metrics"], pol["best_params"]
    feas, viol = spec.feasible(m)
    print(f"RESIZE {ARCH} vs {SPEC}: s11_max={m['s11_max_db']:.2f} "
          f"S21={m['s21_db']:.2f} Idd={m.get('idd_ma') or 0:.2f}  feasible={feas}")
    return feas


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resize", action="store_true", help="re-derive from scratch")
    args = ap.parse_args()
    ok = resize() if args.resize else replay()
    sys.exit(0 if ok else 1)
