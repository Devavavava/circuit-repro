"""WP-DIFF: graft an active balun output stage onto the D4-SIM design (Gate D7).

The standing benchmark's tier-3 differential requirement (imbalance <= 0.22 dB /
<= 0.9 deg, plans2/14-DHRUVA-SIMUL.md SS1.2) has never been measurable: the
designated design `ace8383c2fa68d03` is single-ended and the harness had two
ports. `lna/diff3.py` (golden `lna/ref/check_diff.py`) supplies the 3-port
measurement; this driver supplies the differential OUTPUT.

  * The stage is ASSISTANT-AUTHORED, generic textbook, authored in
    `templates.py` (`diff_pair_balun` / `cs_cg_balun`) with the engineering
    argument written down there -- same provenance class as `gmb_cg_lna` /
    `nc_cgcs_lna`. User decision 2026-08-13: the ACTIVE-BALUN route, existing
    MOS/R/C/L vocabulary, no vocabulary extension, no coupled inductors.
  * The CORE IS FROZEN. Its 30 parameters are the shipped `dhruva-l5` point
    (or `dhruva-simul`, the WP-HARDEN point, with `--core simul`), read-only.
    The only free parameters are the balun's own.
  * The graft point is `VOUT1` -- the far side of the core's own output
    AC-coupling cap `CC6` -- so the core's DC operating point is untouched by
    construction. The two port-2 lines emitted by `to_spice` are removed and
    the stage's two legs take their place as ports 2 (INVERTING) and 3.

Search shape (the `constrained_descent` idea, run over this harness rather than
`size.py`, which is another agent's file this wave and is used READ-ONLY):
    `--curve`  the headline measurement. An INDEPENDENT feasibility descent at
               each of a ladder of fixed Idd ceilings, so the answer to "what
               does the stage cost" is a property of the stage and not of one
               descent's starting basin. Use this for any Idd claim.
    default    two-phase: minimize the differential-gate violation, then walk
               an Idd ceiling down from wherever that landed. Cheaper, but
               basin-bound -- it was measured reading 20.2 mA where the ceiling
               sweep finds the stage feasible far cheaper.
The gate set is {imbalance mag, imbalance phase, differential S21 vs each
band's target, band-wide S11}; Idd is deliberately NOT inside the violation
(it is the thing being measured), and NF is verified in the audit.

    python lna/_diff_balun.py --kind cscg --curve    # the Idd cost curve
    python lna/_diff_balun.py --kind cscg            # two-phase search + audit
    python lna/_diff_balun.py --replay               # re-audit the shipped winner
    python lna/_diff_balun.py --kind dpair --core simul --curve
"""
import argparse
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPRO = os.path.join(HERE, "repro", "dhruva-best")
OUT = os.path.join(HERE, "out")

import moves                            # noqa: E402
import diff3 as D                       # noqa: E402
import size as S                        # noqa: E402
import templates as T                   # noqa: E402
from topology import Topology           # noqa: E402

F_LO, F_HI = 1.1e9, 2.5e9
BANDS = ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5")
IMB_MAG_MAX = 0.22                      # dB   tier-3 target
IMB_PH_MAX = 0.9                        # deg  tier-3 target
S11_MAX = -10.0
IDD_MAX = 13.0
W_FINGER = 2e-6                         # to_spice.W_FINGER (multi-finger cutover)
L_FIXED = "45n"

CORES = {"l5": "dhruva-l5.params.json",        # the designated D4-SIM point
         "simul": "dhruva-simul.params.json"}  # the WP-HARDEN point


# ------------------------------------------------------- netlist -> SPICE
# `templates.py` speaks netlists; `to_spice.py` turns netlists into decks but
# emits exactly two ports, so it cannot emit this stage. Rather than duplicate
# the circuit here (two sources of truth for one structure is how a graft claim
# rots), the stage is READ from templates.py and emitted by these ~40 lines,
# following to_spice's own conventions: parameterised values, multi-finger MOS,
# L pinned at the spec's l_fixed.
_KIND_OF = {"nmos4": "M", "pmos4": "M", "resistor": "R", "capacitor": "C",
            "inductor": "L"}


def _node(n, keep, prefix="b"):
    """to_spice node convention + a prefix on the stage's private nodes so they
    can never collide with the core body's n0..n11."""
    if n == "VSS":
        return "0"
    return n if n in keep else prefix + n


def stage_spice(rows, keep, prefix="b"):
    """(lines, dofs) for a templates.py netlist block.

    `dofs` is {param_name: kind} with kind in W/R/C/L -- exactly the vocabulary
    `size.kind_ranges` boxes, so "in-box" means here what it means everywhere
    else in this program."""
    lines, dofs = [], {}
    for row in rows:
        label, typ = row[0], row[-1]
        nets = [_node(n, keep, prefix) for n in row[1:-1]]
        k = _KIND_OF[typ]
        tag = label.upper()
        if k == "M":
            model = "nmos" if typ == "nmos4" else "pmos"
            pw = f"pB{tag}W"
            dofs[pw] = "W"
            lines.append(f"M{prefix.upper()}{tag} {nets[0]} {nets[1]} {nets[2]} "
                         f"{nets[3]} {model} W={{{pw}}} L={L_FIXED} "
                         f"NF={{max(1,ceil({pw}/{W_FINGER:g}))}}")
        else:
            pv = f"pB{tag}V"
            dofs[pv] = k
            lines.append(f"{k}{prefix.upper()}{tag} {nets[0]} {nets[1]} {{{pv}}}")
    return lines, dofs


# ------------------------------------------------------------ the graft body
def core_body(inductor_q=12):
    tok = json.load(open(os.path.join(REPRO, "tokens.json"), encoding="utf-8"))
    prep = S.prepared_body(Topology(tok), inductor_q=inductor_q)
    if prep is None:
        raise SystemExit("bias insert skipped the core topology")
    return prep[0]


def core_params(core="l5"):
    return json.load(open(os.path.join(REPRO, CORES[core]), encoding="utf-8"))


def graft(kind, inductor_q=12):
    """(body, dofs). Core body minus its port-2 pair, plus the balun stage,
    plus the 3-port stanza. Nothing else in the core is touched."""
    body = core_body(inductor_q)
    kept, dropped = [], []
    for ln in body.splitlines():
        flat = " ".join(ln.split())
        if flat.startswith("Cp2 VOUT1 p2") or flat.startswith("Vp2 p2 0"):
            dropped.append(flat)
            continue
        if flat.startswith("* port 2"):
            continue
        kept.append(ln)
    if len(dropped) != 2:
        raise SystemExit(f"expected to drop 2 port-2 lines, dropped {dropped}")

    # The graft node is already the far side of the core's own AC-coupling cap
    # (CC6), so the CG leg needs no further series cap -- see cs_cg_balun's
    # `couple_cg` note: a second cap there is a high-pass on ONE leg only.
    kw = {"couple_cg": False} if kind == "cscg" else {"couple_in": True}
    rows = T.balun_stage(kind, "VOUT1", outn="obn", outp="obp", **kw)
    keep = {"VDD", "VOUT1", "obn", "obp"}
    lines, dofs = stage_spice(rows, keep)

    stanza = [
        "* WP-DIFF active balun (assistant-authored, templates.balun_stage"
        f" '{kind}')",
        *lines,
        "* ports 2/3: the two output legs. Port 2 is the INVERTING leg, which",
        "* is the polarity diff3.py's imbalance ratio is written against. The",
        "* stage's own output coupling caps ARE the port blocking caps (one",
        "* high-pass per leg, not two in series).",
        "Vp2 obn 0 dc 0 ac 0 portnum 2 z0 50",
        "Vp3 obp 0 dc 0 ac 0 portnum 3 z0 50",
    ]
    return "\n".join(kept + [""] + stanza), dofs


# ----------------------------------------------------------------- objective
def specs():
    out = []
    for name in BANDS:
        sp = S._spec_for_sizing(name)
        out.append({"name": name, "f0": float(sp.band["f0"]),
                    "s21_min": float(sp.constraints["s21_db"]["min"]),
                    "nf_max": float(sp.constraints["nf_db"]["max"])})
    return out


def boxes(dofs):
    """kind_ranges of the dhruva specs (identical across all four -- asserted)."""
    rr = [S.kind_ranges(S._spec_for_sizing(n)) for n in BANDS]
    for r in rr[1:]:
        assert r == rr[0], "dhruva specs disagree on kind_ranges"
    kr = rr[0]
    return {p: kr[k][:2] for p, k in dofs.items()}


def evaluate(body, base, bp, sp, with_nf=False):
    params = dict(base)
    params.update(bp)
    return D.measure_diff3(body, params, [s["f0"] for s in sp], F_LO, F_HI,
                           with_nf=with_nf)


def violation(res, sp, with_nf=False, drop=()):
    """Feasibility-first scalar over the four-band simultaneous DIFFERENTIAL
    gate set. Idd is NOT in here -- it is phase 2's target and the finding this
    experiment exists to measure; folding it in would let the search hide the
    cost by starving the stage into uselessness.

    `drop` removes named terms ('s21' / 's11' / 'imb') from the scalar. That is
    a DIAGNOSTIC, never a claim: dropping s21 answers "what does BALANCE alone
    cost in current", which is the only way to separate the stage's intrinsic
    price from the price of driving two 50 Ohm measurement ports."""
    if res is None:
        return None
    v = 0.0
    if "s11" not in drop:
        v += max(0.0, (res["s11_max_db"] - S11_MAX) / 0.5)
    for s, b in zip(sp, res["bands"]):
        if b["sd21_db"] is None or b["imb_mag_db"] is None:
            return None
        if "s21" not in drop:
            v += max(0.0, (s["s21_min"] - b["sd21_db"]) / 3.0)
        if "imb" not in drop:
            v += max(0.0, (abs(b["imb_mag_db"]) - IMB_MAG_MAX) / IMB_MAG_MAX)
            v += max(0.0, (abs(b["imb_phase_deg"]) - IMB_PH_MAX) / IMB_PH_MAX)
        if with_nf:
            nf = b.get("nf_db")
            if nf is None:
                return None
            v += max(0.0, (nf - s["nf_max"]) / 0.5)
    return v


def in_box(bp, box):
    return [(p, bp[p], lo, hi) for p, (lo, hi) in box.items()
            if bp[p] < lo * (1 - 1e-9) or bp[p] > hi * (1 + 1e-9)]


# ---------------------------------------------------------------- the search
# SMALL-SIGNAL SEED POINTS. Derived from the stage's own hand analysis against
# the MEASURED core (op read-out of the frozen l5 point: MNM6 runs 3.32 mA with
# g_ds 2.35 mS into R_R4 = 132.7 Ohm, so the graft node's driving impedance is
# R_o = R_R4 || 1/g_ds ~ 101 Ohm, and this process gives g_m/I_d ~ 17 /V in the
# weak inversion these designs sit in). Three numbers fall out and they are what
# these seeds encode:
#   * a leg's gain through the CG branch saturates at R_e/R_o however much
#     current is spent (R_e = R_D || 50 <= 50), so gain is bought by making
#     g_m * R_o >~ 1, not by making it large: ~5-25 mS, i.e. 0.3-1.5 mA/branch;
#   * the CS branch must then MATCH that, and its own divider factor is
#     Z/(Z+R_o) with Z the CG branch's input impedance, so the two widths are
#     asymmetric by construction (measured optimum ~1:3);
#   * R_bs is the free knob: it sets the load the stage presents at the graft
#     node, and the core's match was sized against a 50 Ohm port there, so
#     R_bs ~ 50-100 Ohm restores S11 at NO current cost.
# Seeding from the analysis rather than from noise is the difference between
# finding this stage's floor and finding a random basin's: a log-uniform
# multi-start over 13 parameters landed 6-10 mA above these points (measured --
# see FINDINGS SS41).
SEEDS = {
    "cscg": {"pBMBSW": 7e-6, "pBMBGW": 20e-6, "pBRBLNV": 500.0,
             "pBRBLPV": 500.0, "pBRBSV": 60.0, "pBRBB1V": 20e3,
             "pBRBB2V": 9e3, "pBRBGSV": 20e3, "pBRBGGV": 20e3,
             "pBCBGV": 10e-12, "pBCBCGV": 10e-12,
             "pBCBONV": 10e-12, "pBCBOPV": 10e-12},
    "dpair": {"pBMBPW": 20e-6, "pBMBNW": 20e-6, "pBRBLNV": 400.0,
              "pBRBLPV": 400.0, "pBRBTV": 350.0, "pBRBB1V": 20e3,
              "pBRBB2V": 9e3, "pBRBGPV": 20e3, "pBRBGNV": 20e3,
              "pBCBIV": 10e-12, "pBCBGNV": 10e-12,
              "pBCBONV": 10e-12, "pBCBOPV": 10e-12},
}


def _descend(ev, key, bp0, box, steps=(2.0, 1.5, 1.25, 1.12, 1.05),
             max_evals=1200, budget=None):
    """Coordinate descent in log space on `key(result) -> sortable`, lower is
    better. Plain, deterministic, and entirely inside this file: `size.py` is
    another agent's this wave and is used read-only.

    BEST-of-all-coordinates per sweep, not first-improvement: on this surface
    the imbalance term is far sharper than the gain term, so a
    first-improvement rule follows whichever parameter happens to come first in
    the dict and stalls early (measured: it read this stage's Idd floor 6 mA
    too high). Taking the best single-coordinate move per sweep costs 2N
    evaluations a step and is worth it at 0.12 s an evaluation."""
    best_bp = dict(bp0)
    best_r = ev(best_bp)
    best_k = key(best_r)
    n = [1]
    for step in steps:
        while n[0] < (budget or max_evals):
            trials = []
            for p, (lo, hi) in box.items():
                for fac in (step, 1.0 / step):
                    if n[0] >= (budget or max_evals):
                        break
                    cand = dict(best_bp)
                    cand[p] = min(hi, max(lo, cand[p] * fac))
                    if abs(cand[p] - best_bp[p]) <= 1e-12 * abs(best_bp[p]):
                        continue
                    r = ev(cand)
                    n[0] += 1
                    k = key(r)
                    if k is not None and (best_k is None or k < best_k):
                        trials.append((k, cand, r))
            if not trials:
                break
            trials.sort(key=lambda t: t[0])
            best_k, best_bp, best_r = trials[0][0], trials[0][1], trials[0][2]
    return best_bp, best_r, best_k, n[0]


def search(kind, core="l5", seed=1337, n_starts=24, verbose=True, drop=()):
    body, dofs = graft(kind)
    base = core_params(core)
    sp = specs()
    box = boxes(dofs)
    rng = random.Random(seed)
    calls = [0]

    def ev(bp):
        calls[0] += 1
        return evaluate(body, base, bp, sp)

    # ---- phase 0: seeded multi-start ---------------------------------------
    pool = []
    start = {p: min(hi, max(lo, SEEDS[kind][p]))
             for p, (lo, hi) in box.items()}
    cand_list = [start]
    for _ in range(n_starts):
        cand_list.append({p: math.exp(rng.uniform(math.log(lo), math.log(hi)))
                          for p, (lo, hi) in box.items()})
    for bp in cand_list:
        r = ev(bp)
        v = violation(r, sp, drop=drop)
        if v is not None:
            pool.append((v, r["idd_ma"], bp))
    if not pool:
        raise SystemExit(f"{kind}: no start simulated")
    pool.sort(key=lambda t: (round(t[0], 6), t[1]))
    if verbose:
        print(f"[{kind}] starts {len(pool)}/{len(cand_list)} ok; "
              f"best viol {pool[0][0]:.4f} (Idd {pool[0][1]:.2f} mA), "
              f"seeded start viol {violation(ev(start), sp, drop=drop):.4f}")

    # ---- phase 1: minimize the differential-gate violation ------------------
    # Coordinate descent is a local method, so the top few starts each get a
    # short pass and only the winner is refined -- cheap insurance against
    # reading one basin's floor as the stage's capability.
    def key1(r):
        v = violation(r, sp, drop=drop)
        return None if v is None else (round(v, 9), r["idd_ma"])

    heats = []
    for v0, _i0, bp0 in pool[:3]:
        b, r, k, _n = _descend(ev, key1, bp0, box, steps=(2.0, 1.4, 1.15),
                               budget=260)
        heats.append((k, b))
        if verbose:
            print(f"[{kind}]   heat from viol {v0:.4f} -> {k[0]:.5f}")
    heats.sort(key=lambda t: t[0])
    bp, r1, k1, n1 = _descend(ev, key1, heats[0][1], box, budget=900)
    v1 = violation(r1, sp, drop=drop)
    if verbose:
        print(f"[{kind}] phase 1: viol {v1:.5f}  Idd {r1['idd_ma']:.3f} mA "
              f"({n1} steps, {calls[0]} sims)")

    # ---- phase 2: minimize Idd by CEILING CONTINUATION ----------------------
    # A plain "minimize Idd subject to violation == 0" descent stalls
    # immediately here, because phase 1 lands on the S21/imbalance boundary and
    # every single-coordinate step off it is infeasible. Walking a soft Idd
    # ceiling down instead lets the point slide ALONG that boundary, which is
    # what actually answers "what does the stage cost".
    bp2, r2, ceiling, n2 = bp, r1, r1["idd_ma"], 0
    step, budget = 1.0, 1600
    while budget > 0 and step >= 0.05:
        target = ceiling - step

        def keyc(r, _t=target):
            v = violation(r, sp, drop=drop)
            if v is None:
                return None
            return (round(v + max(0.0, (r["idd_ma"] - _t) / 1.0), 9),
                    r["idd_ma"])

        b, r, _k, n = _descend(ev, keyc, bp2, box,
                               steps=(1.4, 1.18, 1.07), budget=min(budget, 320))
        budget -= n
        n2 += n
        if violation(r, sp, drop=drop) == 0 and r["idd_ma"] < ceiling - 1e-6:
            bp2, r2, ceiling = b, r, r["idd_ma"]
        else:
            step /= 2.0
    if verbose:
        print(f"[{kind}] phase 2: Idd {r1['idd_ma']:.3f} -> {r2['idd_ma']:.3f} mA "
              f"at viol {violation(r2, sp, drop=drop):.5f} ({n2} steps, {calls[0]} sims)")
    return {"kind": kind, "core": core, "seed": seed, "body": body,
            "drop": list(drop),
            "base": base, "sp": sp, "box": box, "dofs": dofs,
            "phase1": {"params": bp, "viol": v1, "idd_ma": r1["idd_ma"]},
            "params": bp2, "sims": calls[0]}


# ------------------------------------------------------- Idd cost curve
def cost_curve(kind, core="l5", seed=1337, n_starts=28, drop=(),
               ceilings=(13.0, 13.5, 14.0, 15.0, 16.0, 18.0, 21.0, 25.0),
               verbose=True):
    """The measurement this work-package exists to produce: the SMALLEST total
    Idd at which the four-band differential gate set is simultaneously met.

    Why a ceiling sweep and not just "minimize Idd": coordinate descent on a
    violation surface this sharp is basin-bound -- the plain two-phase search
    lands in a high-current basin and cannot cross to a low-current one,
    because every single-coordinate step between them is infeasible. Running an
    INDEPENDENT feasibility descent at each fixed Idd ceiling (plus a warm start
    from the cheapest solution found so far) makes the answer a property of the
    stage rather than of the descent's starting point. Reported as a curve, so
    the shape of the trade is visible and not just its endpoint.
    """
    body, dofs = graft(kind)
    base, sp, box = core_params(core), specs(), boxes(dofs)
    rng = random.Random(seed)
    calls = [0]

    def ev(bp):
        calls[0] += 1
        return evaluate(body, base, bp, sp)

    starts = [{p: min(hi, max(lo, SEEDS[kind][p])) for p, (lo, hi) in box.items()}]
    for _ in range(n_starts):
        starts.append({p: math.exp(rng.uniform(math.log(lo), math.log(hi)))
                       for p, (lo, hi) in box.items()})
    scored = []
    for bp in starts:
        r = ev(bp)
        v = violation(r, sp, drop=drop)
        if v is not None:
            scored.append((v, r["idd_ma"], bp))
    scored.sort(key=lambda t: (round(t[0], 6), t[1]))

    rows, warm = [], None
    for c in sorted(ceilings):
        def keyc(r, _c=c):
            v = violation(r, sp, drop=drop)
            if v is None:
                return None
            return (round(v + max(0.0, (r["idd_ma"] - _c) / 1.0), 9), r["idd_ma"])

        seeds_here = [t[2] for t in scored[:3]] + ([warm] if warm else [])
        best = None
        for bp0 in seeds_here:
            b, r, k, _n = _descend(ev, keyc, bp0, box,
                                   steps=(2.0, 1.4, 1.15, 1.07), budget=420)
            if best is None or k < best[0]:
                best = (k, b, r)
        k, b, r = best
        v = violation(r, sp, drop=drop)
        ok = v == 0 and r["idd_ma"] <= c + 1e-9
        rows.append({"ceiling_ma": c, "feasible": bool(ok),
                     "idd_ma": r["idd_ma"], "violation": v,
                     "s11_max_db": r["s11_max_db"],
                     "worst_sd21_shortfall_db": max(
                         [0.0] + [s["s21_min"] - bb["sd21_db"]
                                  for s, bb in zip(sp, r["bands"])]),
                     "worst_imb_mag_db": max(abs(bb["imb_mag_db"])
                                             for bb in r["bands"]),
                     "worst_imb_phase_deg": max(abs(bb["imb_phase_deg"])
                                                for bb in r["bands"]),
                     "params": b})
        if ok:
            warm = b
        if verbose:
            print(f"[{kind}/{core}] ceiling {c:5.1f} mA -> Idd {r['idd_ma']:7.3f}  "
                  f"viol {v:8.4f}  {'FEASIBLE' if ok else 'infeasible'}  "
                  f"(sd21 short {rows[-1]['worst_sd21_shortfall_db']:5.2f} dB, "
                  f"imb {rows[-1]['worst_imb_mag_db']:.3f} dB / "
                  f"{rows[-1]['worst_imb_phase_deg']:.3f} deg, "
                  f"s11 {r['s11_max_db']:.3f})")
    feas = [r for r in rows if r["feasible"]]
    ctx = {"kind": kind, "core": core, "seed": seed, "body": body, "base": base,
           "sp": sp, "box": box, "dofs": dofs, "drop": list(drop),
           "sims": calls[0], "curve": rows,
           "params": (min(feas, key=lambda r: r["idd_ma"])["params"]
                      if feas else min(rows, key=lambda r: r["violation"])["params"]),
           "phase1": {"viol": min(r["violation"] for r in rows),
                      "idd_ma": (min(r["idd_ma"] for r in feas) if feas else None)}}
    return ctx


# ------------------------------------------------------------------- audit
def audit(ctx, bp, reps=3, label=""):
    body, base, sp, box = ctx["body"], ctx["base"], ctx["sp"], ctx["box"]
    runs = [evaluate(body, base, bp, sp, with_nf=True) for _ in range(reps)]
    runs = [r for r in runs if r is not None]
    if not runs:
        raise SystemExit("audit: simulation failed")
    r0 = runs[0]
    spread = {}
    for k in ("s11_max_db", "idd_ma"):
        spread[k] = max(r[k] for r in runs) - min(r[k] for r in runs)
    for i, s in enumerate(sp):
        for k in ("sd21_db", "s21p_db", "s21n_db", "imb_mag_db",
                  "imb_phase_deg", "nf_db"):
            vals = [r["bands"][i][k] for r in runs if r["bands"][i][k] is not None]
            if vals:
                spread[f"{s['name']}.{k}"] = max(vals) - min(vals)

    oob = in_box(bp, box)
    print(f"\n=== {label or ctx['kind']} : core {ctx['core']}, "
          f"{len(bp)} balun params ===")
    print(f"replay x{len(runs)}: max spread {max(spread.values()):.6g}   "
          f"in-box {len(bp) - len(oob)}/{len(bp)}"
          + (f"  OOB {oob}" if oob else ""))
    print(f"{'band':<11}{'f0 GHz':>8}{'sd21':>8}{'tgt':>6}{'leg2':>8}{'leg3':>8}"
          f"{'imb dB':>8}{'imb deg':>9}{'NF':>7}{'NFtgt':>6}")
    gates = {"s21": True, "imb_mag": True, "imb_ph": True, "nf": True,
             "s21_leg": True}
    worst = {"imb_mag": 0.0, "imb_ph": 0.0}
    for s, b in zip(sp, r0["bands"]):
        nf = b.get("nf_db")
        gates["s21"] &= b["sd21_db"] >= s["s21_min"]
        gates["s21_leg"] &= max(b["s21p_db"], b["s21n_db"]) >= s["s21_min"]
        gates["imb_mag"] &= abs(b["imb_mag_db"]) <= IMB_MAG_MAX
        gates["imb_ph"] &= abs(b["imb_phase_deg"]) <= IMB_PH_MAX
        gates["nf"] &= nf is not None and nf <= s["nf_max"]
        worst["imb_mag"] = max(worst["imb_mag"], abs(b["imb_mag_db"]))
        worst["imb_ph"] = max(worst["imb_ph"], abs(b["imb_phase_deg"]))
        print(f"{s['name']:<11}{b['f0']/1e9:>8.4f}{b['sd21_db']:>8.2f}"
              f"{s['s21_min']:>6.1f}{b['s21p_db']:>8.2f}{b['s21n_db']:>8.2f}"
              f"{b['imb_mag_db']:>8.3f}{b['imb_phase_deg']:>9.3f}"
              f"{(nf if nf is not None else float('nan')):>7.3f}"
              f"{s['nf_max']:>6.1f}")
    # THE GAIN READING IS A CONVENTION, and the verdict moves with it, so all
    # three are printed rather than one being quietly picked:
    #   per-leg      20log10|S21|            -- strictest
    #   Sds21        20log10|S21-S31|/sqrt2  -- the standard mixed-mode
    #                                          S-parameter; what is GATED here
    #   voltage      20log10|S21-S31|        -- = Sds21 + 3.0103, the direct
    #                                          analogue of the single-ended
    #                                          "voltage gain adopted as S21
    #                                          into 50 Ohm" mapping (REPORT S5)
    print("gain reading (S-band f0): per-leg %.2f | Sds21 %.2f (GATED) | "
          "voltage-gain analogue %.2f  vs target %.1f dB"
          % (r0["bands"][0]["s21p_db"], r0["bands"][0]["sd21_db"],
             r0["bands"][0]["sd21_db"] + 3.0103, sp[0]["s21_min"]))
    s11ok = r0["s11_max_db"] <= S11_MAX
    iddok = r0["idd_ma"] <= IDD_MAX
    print(f"S11_max (1.1-2.5 GHz) {r0['s11_max_db']:>8.3f}  "
          f"[{'PASS' if s11ok else 'FAIL %+.3f' % (r0['s11_max_db'] - S11_MAX)}]"
          f"     Idd {r0['idd_ma']:>7.3f} mA  "
          f"[{'PASS' if iddok else 'FAIL %+.3f' % (r0['idd_ma'] - IDD_MAX)}]")
    print(f"worst imbalance over the four f0: {worst['imb_mag']:.3f} dB "
          f"(<= {IMB_MAG_MAX}) / {worst['imb_ph']:.3f} deg (<= {IMB_PH_MAX})"
          f"   band-wide worst {r0['imb_mag_wc_db']:.3f} dB / "
          f"{r0['imb_phase_wc_deg']:.3f} deg")
    print(f"mixed-mode K_min {r0['mm_k_min']:.3g} (advisory)")
    verdict = {"imbalance_mag": gates["imb_mag"], "imbalance_phase": gates["imb_ph"],
               "s21_diff": gates["s21"], "s21_per_leg": gates["s21_leg"],
               "nf": gates["nf"], "s11": s11ok, "idd": iddok}
    print("four-band simultaneous gates with the balun attached: " +
          "  ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in verdict.items()))
    return r0, verdict, spread, worst


# --------------------------------------------------------------------- main
def _winner_path(kind, core, drop=()):
    tag = "" if core == "l5" else f"_{core}"
    if drop:
        tag += "_drop-" + "-".join(sorted(drop))
    return os.path.join(OUT, f"diff_balun_{kind}{tag}.params.json")


def _save(ctx, bp, r0, verdict, spread, worst):
    path = _winner_path(ctx["kind"], ctx["core"], tuple(ctx.get("drop") or ()))
    os.makedirs(OUT, exist_ok=True)
    blob = {
        "parent": f"ace8383c2fa68d03 @ {CORES[ctx['core']]} (core FROZEN)",
        "stage": f"templates.balun_stage('{ctx['kind']}')",
        "attribution": "assistant-authored generic textbook stage "
                       "(gmb_cg/nc_cgcs precedent); blind protocol",
        "recipe": "diff-balun-v1", "seed": ctx["seed"], "sims": ctx["sims"],
        "search_objective_dropped_terms": ctx.get("drop") or [],
        "balun_params": bp, "dof_kinds": ctx["dofs"],
        "phase1": {k: v for k, v in ctx["phase1"].items() if k != "params"},
        "result": {"s11_max_db": r0["s11_max_db"], "idd_ma": r0["idd_ma"],
                   "mm_k_min": r0["mm_k_min"],
                   "imb_mag_wc_db": r0["imb_mag_wc_db"],
                   "imb_phase_wc_deg": r0["imb_phase_wc_deg"],
                   "worst_f0_imb_mag_db": worst["imb_mag"],
                   "worst_f0_imb_phase_deg": worst["imb_ph"],
                   "bands": r0["bands"]},
        "verdict": verdict,
        "idd_cost_curve": [
            {k: v for k, v in row.items() if k != "params"}
            for row in (ctx.get("curve") or [])],
        "replay_spread_max": max(spread.values()),
    }
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(blob, fh, indent=1)
    print(f"wrote {path}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="cscg",
                    choices=("cscg", "dpair", "dpair_m", "both"))
    ap.add_argument("--core", default="l5", choices=tuple(CORES))
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--starts", type=int, default=24)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--show-deck", action="store_true")
    ap.add_argument("--curve", action="store_true",
                    help="Idd ceiling sweep -- the cost measurement")
    ap.add_argument("--drop", default="",
                    help="DIAGNOSTIC: comma list of gate terms to remove from "
                         "the search objective (s21/s11/imb). Never a claim.")
    a = ap.parse_args()

    moves.private_tmp(os.path.join(OUT, "_diff_tmp"))

    if a.show_deck:
        body, dofs = graft(a.kind)
        print(body)
        print("\nDOFs:", json.dumps(dofs, indent=1))
        return

    kinds = ("cscg", "dpair") if a.kind == "both" else (a.kind,)
    for kind in kinds:
        if a.replay:
            path = _winner_path(kind, a.core)
            blob = json.load(open(path, encoding="utf-8"))
            body, dofs = graft(kind)
            ctx = {"kind": kind, "core": a.core, "body": body,
                   "base": core_params(a.core), "sp": specs(),
                   "box": boxes(dofs), "dofs": dofs}
            audit(ctx, blob["balun_params"], label=f"{kind} (replay)")
            continue
        drop = tuple(x for x in a.drop.split(",") if x)
        if a.curve:
            ctx = cost_curve(kind, core=a.core, seed=a.seed,
                             n_starts=a.starts, drop=drop)
        else:
            ctx = search(kind, core=a.core, seed=a.seed, n_starts=a.starts,
                         drop=drop)
        r0, verdict, spread, worst = audit(ctx, ctx["params"])
        _save(ctx, ctx["params"], r0, verdict, spread, worst)


if __name__ == "__main__":
    main()
