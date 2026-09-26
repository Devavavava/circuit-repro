"""Golden: TOKEN-topology balun port-3 plumbing (class-objective balun port-3).

Where check_classgate proves the class WIRING with a BEHAVIORAL VCVS balun, this
golden proves the harder half the behavioral deck cannot: that a *token
topology* -- a real device netlist produced by the proposal round-trip and
emitted by to_spice.py -- reaches the 3-port balun harness in-loop, yields
sds21/cmrr, and makes the class gate RESPOND. Behavioral decks hand-write their
own portnum lines; only a token topology exercises to_spice's port-3 emission
(the `Vp3 ... portnum 3` + coupling cap that this change added when net VOUT2 is
present) AND proposal.py's VOUT2 reserved-net dialect end-to-end.

The DUT is the canonical single-in / diff-out topology: the Blaakmeer-Klumperink
CG-CS noise-cancelling balun-LNA (JSSC 2008), structure-only (no component
values -- the sizer supplies them). Its non-inverting leg lands on VOUT2, its
inverting leg on VOUT1, exactly the diff3/balun_harness port convention.

WHAT IT PROVES:
  (0) PLUMBING     -- proposal.round_trip parses the token netlist (VOUT2 is a
      reserved output port, not an internal node) and to_spice emits THREE
      contiguous S-parameter ports (portnum 1/2/3). No behavioral source anywhere
      in the deck.
  (a) PRESENCE     -- one in-loop eval_metrics on the sized token body carries the
      balun class keys sds21_db/cmrr_db/imbalance_amp_db/imbalance_phase_deg. If
      port 3 were NOT emitted (2-port body), the harness returns None and these
      keys are ABSENT -- this golden asserts that counterfactual too, so PRESENCE
      is load-bearing, not incidental.
  (b) RESPONSE     -- on the SAME measured point, a loose cmrr gate is feasible
      and an absurd cmrr gate is infeasible: feasibility moves with the class
      gate, which can only happen if the class metric is measured in-loop on the
      token topology.

Runtime: one bias-insert + a handful of sub-second sp sweeps (the balun harness
is a single sp run, ~10-20 ms per eval); the whole golden is a few seconds.

BYTE-IDENTICAL lna path is fenced by check_ref/check_simhealth, NOT here.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.dirname(HERE)
REPO = os.path.dirname(LNA)
sys.path.insert(0, LNA)
sys.path.insert(0, os.path.join(REPO, "kaggle", "loop"))

import numpy as np                     # noqa: E402
import iip3 as I                       # noqa: E402
import size as S                       # noqa: E402
from spec import Spec                  # noqa: E402


# The Blaakmeer-Klumperink CG-CS noise-cancelling balun-LNA, structure-only, in
# the proposal netlist dialect. VOUT1 = inverting (CS) leg, VOUT2 = non-inverting
# (CG) leg -- the diff3/balun_harness port-2/port-3 convention. Embedded here so
# the golden is self-contained (it does NOT depend on the bench-anchor file, which
# a separate pass owns); the anchor is the same topology.
_BALUN_TOKEN_NETLIST = """
* CG-CS noise-cancelling balun-LNA (single-in / diff-out), structure-only.
C C1 VIN1 n1
L L1 n1 VSS
NMOS NM1 n2 n4 n1 VSS
L L2 VDD n2
C C3 n2 VOUT2
C Cin2 n1 n6
NMOS NM2 n3 n6 VSS VSS
L L3 VDD n3
C C4 n3 VOUT1
R R1 VDD n5
NMOS NM3 n5 n5 VSS VSS
R R2 n5 n4
R R3 n5 n6
C Cg n4 VSS
"""

_BAND = {"type": "narrowband", "f0": 2.4e9, "f_lo": 1.5e9, "f_hi": 3.0e9}
_SIZING = {"w_um": [1, 400], "l_fixed": 45e-9, "r_ohm": [100, 20000],
           "c_f": [50e-15, 20e-12], "vb_v": [0.2, 0.9]}


def _spec(name, gate):
    """A minimal balun-lna Spec gating cmrr_db at `gate` (status:measured) with a
    maximise objective on it -- the same junction the campaign uses."""
    return Spec({
        "name": name, "circuit_class": "balun-lna", "pdk": "bptm45",
        "topology": {"device_budget": [1, 24], "allow_inductorless": True,
                     "reject_floating": False},
        "band": _BAND,
        "ports": {"z0": 50, "input": "VIN1", "output": "VOUT1"},
        "constraints": {"cmrr_db": dict(gate, status="measured")},
        "sizing": _SIZING,
        "objectives": [{"metric": "cmrr_db", "direction": "max", "weight": 1.0}],
    })


def _token_body():
    """proposal.round_trip -> Topology -> to_spice, returning
    (nl, body, sizable, fixed). Proves the token round-trip AND the port-3
    emission in one path; raises on any failure so a broken plumbing is RED."""
    import proposal as P
    from topology import Topology
    from to_spice import Netlist
    info = P.round_trip(_BALUN_TOKEN_NETLIST)
    if not info["ok"] or not info["valid"]:
        raise RuntimeError(f"round-trip failed: {info.get('error')}")
    if "VOUT2" not in info["ports"]:
        raise RuntimeError(f"VOUT2 not a recognized port: ports={info['ports']}")
    topo = Topology(info["tokens"])
    nl = Netlist(topo)
    body_full = nl.emit()                      # forces two_port/three_port flags
    pb = S.prepared_body(topo)                 # bias-inserted sizing body
    if pb is None:
        raise RuntimeError("prepared_body -> None (bias skipped)")
    body, sizable, fixed = pb
    return nl, body_full, body, sizable, fixed, info["ports"]


def main():
    I.private_tmp()
    ok = True
    print("[BALUN3] token-topology balun port-3 plumbing")

    nl, emitted, body, sizable, fixed, ports = _token_body()

    # (0) PLUMBING: three contiguous portnum lines, no behavioral source.
    portnums = sorted(int(ln.split("portnum")[1].split()[0])
                      for ln in emitted.splitlines() if "portnum" in ln.lower())
    has_behavioral = any(ln.lstrip()[:1] in ("B", "E", "G")
                         for ln in emitted.splitlines())
    ok_plumb = (portnums == [1, 2, 3] and nl.three_port and not has_behavioral
                and "VOUT2" in ports)
    print(f"    (0) ports={ports} portnums={portnums} three_port={nl.three_port} "
          f"behavioral_source={has_behavioral}")
    print(f"        -> {'THREE-PORT token deck' if ok_plumb else 'PLUMBING BROKEN'}")
    ok &= ok_plumb

    # size once against the loose gate to get an in-loop measured point
    sp_loose = _spec("bl3-loose", {"min": -50.0})
    sp_absurd = _spec("bl3-absurd", {"min": 900.0})
    obj, names, decode, evaluate = S.make_objective(body, sp_loose, sizable, fixed)
    m = evaluate(np.full(len(names), 0.5))
    if m is None:
        print("    RED: in-loop eval produced no metrics (sim failed)")
        return 1

    # (a) PRESENCE on the token topology
    keys = ("sds21_db", "cmrr_db", "imbalance_amp_db", "imbalance_phase_deg")
    have = [k for k in keys if m.get(k) is not None]
    ok_present = len(have) == len(keys)
    print("    (a) token-topology class metrics: "
          + ", ".join(f"{k}={m.get(k):.3g}" for k in keys if m.get(k) is not None))
    print(f"        -> {'all present' if ok_present else 'MISSING ' + str([k for k in keys if m.get(k) is None])}")
    ok &= ok_present

    # (a') COUNTERFACTUAL: a 2-port body (port-3 lines stripped) yields NO balun
    # metrics -- so PRESENCE is caused by the port-3 emission, not by luck.
    body2 = "\n".join(ln for ln in body.splitlines()
                      if "portnum 3" not in ln.lower()
                      and not ln.lstrip().startswith("Cp3")
                      and "port 3" not in ln)
    o2, n2, d2, ev2 = S.make_objective(body2, sp_loose, sizable, fixed)
    m2 = ev2(np.full(len(n2), 0.5))
    ok_counter = (m2 is None) or (m2.get("sds21_db") is None
                                  and m2.get("cmrr_db") is None)
    print(f"    (a') 2-port-only body: sds21_db={None if m2 is None else m2.get('sds21_db')}, "
          f"cmrr_db={None if m2 is None else m2.get('cmrr_db')}")
    print(f"        -> {'balun metrics ABSENT without port 3 (port-3 is load-bearing)' if ok_counter else 'UNEXPECTED: measured without port 3'}")
    ok &= ok_counter

    # (b) RESPONSE on the SAME measured point
    feas_loose = sp_loose.feasible(m)[0]
    feas_absurd = sp_absurd.feasible(m)[0]
    ok_response = feas_loose and not feas_absurd
    print(f"    (b) cmrr_db={m['cmrr_db']:.3g}: loose(min -50) feasible={feas_loose}; "
          f"absurd(min 900) feasible={feas_absurd}")
    print(f"        -> objective {'RESPONDS' if ok_response else 'DOES NOT RESPOND'} to the class gate")
    ok &= ok_response

    print("check_balun3:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
