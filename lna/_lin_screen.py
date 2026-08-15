"""WP-LIN rung 1 -- the cheap OP/AC screen + the candidate-A probe (P4).

SIDECAR (16-WP-LIN.md D-9): every read-only harness (`pgain.py`,
`_pgain_mech.py`, `size.py`, `extract.py`) is imported and re-pointed by MODULE
attribute, never edited. Nothing here runs a two-tone; this rung produces the
tier-1 kill decisions of §3's screen column and the P4 match-wall answer only.

Two commands:

  --probe-A   Candidate A/A's P4 test (§4.1, §8 P4). Re-runs `pgain.py --probe`
              and `pgain.py --wall` on the `dhruva-simul` substrate at BOTH
              rails -- 1.1 V for a clean reproduction of §42.3/§42.4 on this
              host, and 1.2 V (the ruled nominal), which has never been done.
              §42.3's probe was measured on the l5 host (0.001 dB S11 margin);
              this host carries +1.484 dB. The match-legal span is MEASURED, not
              inherited. Kill (per §3 row A): band-wide S11 > -10 in any state,
              or match-legal span < 10.6 dB.

  --screen    The OP/AC screen over §3's candidate mechanisms B/C/D/E/F/G/H at
              1.2 V nominal. `size.eval_metrics(nf_gated=True)` + one `op`,
              giving S11 band-wide, S21 at four f0, NF, Idd, K_min, and the swing
              proxies Iq(MNM6), |Z_ac|, Vq-Vdsat, per-device region/gm-Id. Kill
              rules pre-stated in §4.1: any candidate breaking a tier-1/2 gate at
              1.2 V nominal is dropped; any candidate whose Iq*|Z_ac| product
              does not improve on the baseline is dropped unless it is an A/A'
              row (which does not act through that product). Rows stamped
              provenance.source_arm = "wplin-screen".

The pVDD override for the probe/wall (pgain has no --vdd flag, D-9 forbids
editing it): `pgain.base_design` is the SINGLE substrate entry point for both
cmd_probe and cmd_wall; we re-point it to a version that injects pVDD into the
read params. Every other line of pgain's probe/wall logic is untouched.

§42.2 / §6.7 node-name discipline: the screen's mechanism inserts reuse
`_pgain_mech.build` / `resolve_nodes` (structural role resolution, cross-checked)
and the in-box sizing moves touch only named .param values, never node names.
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import size as S            # noqa: E402
import extract as E         # noqa: E402
from topology import Topology  # noqa: E402
import _pgain_mech as M     # noqa: E402
import pgain as P           # noqa: E402

REPRO = os.path.join(HERE, "repro", "dhruva-best")
OUT = os.path.join(HERE, "out")
TOKENS = os.path.join(REPRO, "tokens.json")
SIMUL_PARAMS = os.path.join(REPRO, "dhruva-simul.params.json")
RECIPE = "wplin-v1"
SOURCE_ARM = "wplin-screen"

BANDS = ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5")
F0 = {"dhruva-l5": 1176.45e6, "dhruva-l2": 1227.6e6,
      "dhruva-l1": 1575.42e6, "dhruva-s": 2492.03e6}
S21_TARGET = {"dhruva-s": 30.0, "dhruva-l1": 25.4,
              "dhruva-l2": 22.3, "dhruva-l5": 22.3}
COARSE = "dhruva-l5"        # S11/Idd are band-independent
S11_GATE, IDD_GATE = -10.0, 13.0
SPAN_REQ = 10.6


# ------------------------------------------------------------ substrate
def base_body():
    tok = json.load(open(TOKENS, encoding="utf-8"))
    prep = S.prepared_body(Topology(tok), inductor_q=12)
    if prep is None:
        raise SystemExit("_lin_screen: bias insert skipped")
    return prep  # (body, sizable, fixed)


def simul_params(vdd="1.2"):
    p = json.load(open(SIMUL_PARAMS, encoding="utf-8"))
    p["pVDD"] = str(vdd)
    return dict(p)


def spec_for(band):
    return S._spec_for_sizing(band)


# ------------------------------------------------------------ swing proxies
def z_ac_mag(params, f0):
    """|Z_ac| at the output-stage drain (§2.2 construction): pR4V shunted by the
    50 ohm port seen through CC6 (pC6V) in series with Cp2 (10 pF)."""
    R = float(params["pR4V"])
    c6 = float(params["pC6V"])
    cp2 = 10e-12
    cser = c6 * cp2 / (c6 + cp2)
    w = 2 * math.pi * f0
    zc = 1.0 / (1j * w * cser)
    zport = zc + 50.0
    zpar = 1.0 / (1.0 / R + 1.0 / zport)
    return abs(zpar)


def proxies(body, params):
    """Iq(MNM6), |Z_ac|, product (mV), Vq-Vdsat at MNM6 drain, per-device region.
    One op run (via eval_metrics op_capture). Returns (dict, metrics)."""
    cap = {}
    m = S.eval_metrics(body, params, spec_for(COARSE), nf_gated=False,
                       op_capture=cap)
    if m is None:
        return None, None
    dev = cap.get("devices", {})
    d6 = dev.get("mnm6", {})
    iq = abs(d6.get("id", float("nan")))
    z = z_ac_mag(params, F0[COARSE])
    vds6, vdsat6 = d6.get("vds"), d6.get("vdsat")
    prox = dict(
        iq_mnm6_ma=iq * 1e3, z_ac_ohm=z, iq_z_mv=iq * z * 1e3,
        vq_minus_vdsat=(vds6 - vdsat6) if (vds6 is not None and vdsat6 is not None) else None,
        regions={n: dev.get(n, {}).get("region") for n in
                 ("mnm1", "mnm2", "mnm3", "mnm4", "mnm5", "mnm6")},
        gm_id={n: ((dev.get(n, {}).get("gm") or 0) / dev.get(n, {}).get("id"))
               if dev.get(n, {}).get("id") else None
               for n in ("mnm1", "mnm2", "mnm3", "mnm4", "mnm5", "mnm6")},
        all_sat=all(dev.get(n, {}).get("region") == "sat"
                    for n in ("mnm1", "mnm4", "mnm6")),
    )
    return prox, m


def four_band(body, params, nf=True):
    """S21 at four f0, plus S11/Idd/K_min/NF. Returns per-band metric dict or
    None if any band fails to sim."""
    per = {}
    for b in BANDS:
        m = S.eval_metrics(body, params, spec_for(b), nf_gated=nf)
        if m is None:
            return None
        per[b] = m
    return per


def tier_gates_ok(per):
    """Tier-1/2 legality at nominal, all four bands. Returns (ok, reasons)."""
    reasons = []
    s11 = max(per[b]["s11_max_db"] for b in BANDS)
    idd = max(per[b]["idd_ma"] for b in BANDS)
    if s11 > S11_GATE:
        reasons.append(f"S11 {s11:.3f}>-10")
    if idd > IDD_GATE:
        reasons.append(f"Idd {idd:.3f}>13")
    for b in BANDS:
        if per[b]["s21_db"] < S21_TARGET[b]:
            reasons.append(f"S21@{b.replace('dhruva-','')} {per[b]['s21_db']:.2f}<{S21_TARGET[b]}")
        nf = per[b].get("nf_db")
        nfmax = spec_for(b).constraints["nf_db"]["max"]
        if nf is not None and nf > nfmax:
            reasons.append(f"NF@{b.replace('dhruva-','')} {nf:.3f}>{nfmax}")
        if per[b].get("k_min") is not None and per[b]["k_min"] < 1.0:
            reasons.append(f"Kmin@{b.replace('dhruva-','')} {per[b]['k_min']:.2f}<1")
    return (len(reasons) == 0), reasons


# ============================================================ P4: probe A
def cmd_probe_A(vdds=("1.1", "1.2")):
    """Re-run pgain --probe and --wall on the simul substrate at each rail by
    re-pointing pgain.base_design to inject pVDD (D-9 override)."""
    orig_base = P.base_design

    results = {"recipe": RECIPE, "source_arm": SOURCE_ARM,
               "diagnosis": "front-end-gain-control-match-wall",
               "test": "P4-candidate-A-probe", "rails": {}}
    for vdd in vdds:
        def _base(sizing="simul", _vdd=vdd, _orig=orig_base):
            body, params, sizable = _orig(sizing="simul")
            params = dict(params, pVDD=str(_vdd))
            return body, params, sizable
        P.base_design = _base
        try:
            print(f"\n############## P4 PROBE: simul substrate @ pVDD = {vdd} V "
                  f"##############")
            print("\n--- pgain.py --probe (mechanism-independent load map) ---")
            P.cmd_probe("simul")
            print("\n--- pgain.py --wall (A/A' mechanisms: in-att, in-degen, "
                  "n0-bank) ---")
            wall = {}
            for mech in ("in-att", "in-degen", "n0-bank"):
                rows = P.cmd_wall(mech, "simul")
                # best match-legal span on the coarse band
                legal = [r for r in rows if r[5]]
                best = max((r[1] for r in legal), default=0.0)
                wall[mech] = dict(best_legal_span_db=round(best, 3),
                                  reaches_10p6=bool(best >= SPAN_REQ))
            results["rails"][vdd] = dict(wall=wall)
        finally:
            P.base_design = orig_base

    # verdict
    print("\n" + "=" * 68)
    print("P4 VERDICT -- has the §42.3 match wall lifted on the simul host?")
    for vdd in vdds:
        w = results["rails"][vdd]["wall"]
        print(f"  @ {vdd} V:")
        for mech, d in w.items():
            print(f"    {mech:<10} best match-legal span = "
                  f"{d['best_legal_span_db']:>6.2f} dB  "
                  f"{'>= 10.6 (P4 would HOLD here)' if d['reaches_10p6'] else '< 10.6 (wall stands)'}")
    any_lift = any(d["reaches_10p6"]
                   for vdd in vdds for d in results["rails"][vdd]["wall"].values())
    results["p4_wall_lifted"] = any_lift
    print(f"\n  P4 (a front-side node with >= 10.6 dB match-legal span): "
          f"{'CONFIRMED' if any_lift else 'REFUTED'}")
    path = os.path.join(OUT, "_lin_probe_A.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, default=float)
    print(f"  wrote {path}")
    return results


# ============================================================ the screen
def candidate_moves():
    """§3 candidate mechanisms as in-box parameter/insert families on the simul
    substrate. Each entry: (label, kind, builder) where builder(base_body,
    base_params) -> [(variant_name, body, params, acts_through_iqz)].

    The swing-directed in-box levers (§5.2) are pNM6W, pR4V, pC6V, pVB -- exactly
    candidates B/C/E. D/F/G/H need the spare device or an inserted element and are
    screened on the cheap evidence §3 names (budget / slope / authority), flagged
    rather than sized."""
    return None  # families are enumerated inline in cmd_screen


def _kr(spec):
    return S.kind_ranges(spec)


def clamp(v, lo, hi):
    return min(max(v, lo), hi)


def cmd_screen(vdd="1.2"):
    body, sizable, fixed = base_body()
    spec = spec_for(COARSE)
    kr = _kr(spec)
    Wlo, Whi = kr["W"][0], kr["W"][1]
    Rlo, Rhi = kr["R"][0], kr["R"][1]
    Clo, Chi = kr["C"][0], kr["C"][1]
    VBlo, VBhi = kr["VB"][0], kr["VB"][1]

    base = simul_params(vdd)
    print(f"\n########## RUNG 1 SCREEN @ pVDD = {vdd} V ##########")
    bprox, bper = proxies(body, base)
    bfour = four_band(body, base, nf=True)
    bok, brs = tier_gates_ok(bfour)
    base_iqz = bprox["iq_z_mv"]
    print(f"\nBASELINE (dhruva-simul @ {vdd} V): Iq(MNM6)={bprox['iq_mnm6_ma']:.3f} mA  "
          f"|Z_ac|={bprox['z_ac_ohm']:.2f}  Iq*|Z|={base_iqz:.2f} mV  "
          f"Vq-Vdsat={bprox['vq_minus_vdsat']*1e3:.1f} mV")
    print(f"  S11={max(bfour[b]['s11_max_db'] for b in BANDS):.3f}  "
          f"Idd={max(bfour[b]['idd_ma'] for b in BANDS):.3f}  "
          f"S21={[round(bfour[b]['s21_db'],2) for b in BANDS]}  "
          f"tier-legal={bok}")

    rows = []

    def eval_variant(label, cand, params, acts_iqz, note=""):
        prox, per = proxies(body, params)
        if prox is None:
            rows.append(dict(candidate=cand, variant=label, sim="FAILED", note=note))
            print(f"  [{cand}] {label:<22} SIM FAILED")
            return
        four = four_band(body, params, nf=True)
        if four is None:
            rows.append(dict(candidate=cand, variant=label, sim="FAILED", note=note))
            print(f"  [{cand}] {label:<22} SIM FAILED (four-band)")
            return
        ok, reasons = tier_gates_ok(four)
        iqz = prox["iq_z_mv"]
        iqz_improves = iqz > base_iqz + 1e-6
        # kill rules (§4.1)
        killed, why = False, []
        if not ok:
            killed = True
            why.append("tier-1/2 break: " + "; ".join(reasons))
        if not acts_iqz and not iqz_improves:
            # non-A/A' rows that do not improve Iq*|Z| are dropped
            pass  # handled below only for iqz-class rows
        if acts_iqz and not iqz_improves:
            killed = True
            why.append(f"Iq*|Z| {iqz:.2f} <= baseline {base_iqz:.2f} (no swing gain)")
        rec = dict(candidate=cand, variant=label,
                   s11_max_db=max(four[b]["s11_max_db"] for b in BANDS),
                   idd_ma=max(four[b]["idd_ma"] for b in BANDS),
                   s21_db={b: four[b]["s21_db"] for b in BANDS},
                   nf_db={b: four[b].get("nf_db") for b in BANDS},
                   k_min=min(four[b].get("k_min", 0) for b in BANDS),
                   iq_mnm6_ma=prox["iq_mnm6_ma"], z_ac_ohm=prox["z_ac_ohm"],
                   iq_z_mv=iqz, iq_z_delta_mv=iqz - base_iqz,
                   vq_minus_vdsat_mv=(prox["vq_minus_vdsat"] * 1e3
                                     if prox["vq_minus_vdsat"] is not None else None),
                   all_sat=prox["all_sat"], regions=prox["regions"],
                   tier_legal=ok, tier_reasons=reasons,
                   killed=killed, kill_why=why, acts_through_iqz=acts_iqz,
                   note=note, source_arm=SOURCE_ARM)
        rows.append(rec)
        flag = "KILL" if killed else "keep"
        print(f"  [{cand}] {label:<22} Iq={prox['iq_mnm6_ma']:.3f} "
              f"|Z|={prox['z_ac_ohm']:.1f} Iq*Z={iqz:.1f}(dz{iqz-base_iqz:+.1f}) "
              f"S11={rec['s11_max_db']:.2f} Idd={rec['idd_ma']:.2f} "
              f"S21s={rec['s21_db']['dhruva-s']:.1f} "
              f"NFl5={rec['nf_db']['dhruva-l5']:.2f} "
              f"sat={prox['all_sat']} -> {flag}"
              + (("  (" + "; ".join(why) + ")") if why else ""))

    # ---- Candidate B: output current re-allocation (pNM6W up, pNM4W down) ----
    print("\n-- Candidate B: output-stage current re-allocation (in-box) --")
    for fac6, fac4 in [(1.5, 1.0), (2.0, 1.0), (2.0, 0.8), (3.0, 0.7),
                       (1.5, 0.85), (4.0, 0.6)]:
        p = dict(base)
        p["pNM6W"] = str(clamp(float(base["pNM6W"]) * fac6, Wlo, Whi))
        p["pNM4W"] = str(clamp(float(base["pNM4W"]) * fac4, Wlo, Whi))
        eval_variant(f"NM6x{fac6}_NM4x{fac4}", "B", p, acts_iqz=True)

    # ---- Candidate C: raise output AC load impedance (pR4V up, pC6V down) ----
    print("\n-- Candidate C: raise output AC load impedance (in-box) --")
    for facR, facC in [(1.5, 1.0), (2.0, 1.0), (3.0, 1.0), (2.0, 0.5),
                       (3.0, 0.3), (5.0, 1.0)]:
        p = dict(base)
        p["pR4V"] = str(clamp(float(base["pR4V"]) * facR, Rlo, Rhi))
        p["pC6V"] = str(clamp(float(base["pC6V"]) * facC, Clo, Chi))
        eval_variant(f"R4x{facR}_C6x{facC}", "C", p, acts_iqz=True)

    # ---- Candidate B+C combined (fund current AND raise Z) ----
    print("\n-- Candidate B+C: current re-alloc + higher load Z (in-box) --")
    for fac6, facR, fac4 in [(2.0, 2.0, 0.8), (2.5, 1.5, 0.7), (3.0, 2.0, 0.7)]:
        p = dict(base)
        p["pNM6W"] = str(clamp(float(base["pNM6W"]) * fac6, Wlo, Whi))
        p["pR4V"] = str(clamp(float(base["pR4V"]) * facR, Rlo, Rhi))
        p["pNM4W"] = str(clamp(float(base["pNM4W"]) * fac4, Wlo, Whi))
        eval_variant(f"NM6x{fac6}_R4x{facR}_NM4x{fac4}", "BC", p, acts_iqz=True)

    # ---- Candidate E: bias re-centering (pVB sweep) ----
    print("\n-- Candidate E: bias re-centering via pVB (in-box; §2.2 predicts <2 dB) --")
    for vb in (0.2, 0.35, 0.5, 0.65, 0.8, 0.9):
        vb = clamp(vb, VBlo, VBhi)
        p = dict(base)
        p["pVB"] = str(vb)
        eval_variant(f"pVB={vb}", "E", p, acts_iqz=True)

    # ---- Candidates D, F, G, H: cheap-evidence screen (§3), flagged ----
    print("\n-- Candidates D/F/G/H: cheap-evidence screen (§3 kill columns) --")
    dfgh = [
        dict(candidate="D", variant="current-reuse/gm-boost",
             killed=True, acts_through_iqz=False,
             kill_why=["needs a stacked device to make one current serve two "
                       "gm's; the topology is at 20/21 (1 spare) and three input "
                       "devices already sit in sub-threshold (gm/Id 16.2) on the "
                       "1.2 V rail -- stacking spends the resource (voltage "
                       "headroom at the input) the corpus has least of (§41.6 "
                       "item 1, §3 row D). Cannot be built in-box without the "
                       "spare device -> §7 D-2 budget question, not sized."],
             note="budget-limited; queued as D-2 if the user widens the box"),
        dict(candidate="F", variant="output cascode / headroom re-stack",
             killed=True, acts_through_iqz=False,
             kill_why=["§2.2 measured the wall as current-limited (headroom "
                       "17 dB non-binding, §44.4); a cascode spends Vds headroom "
                       "to buy output impedance -- exactly the non-binding "
                       "resource. Costs the single spare device (§3 row F). P5's "
                       "expected-to-fail row, killed on the §44.4 evidence."],
             note="expected-fail (P5); the cascode-on-MNM2/5 S11 sub-use is a "
                  "candidate-A funding question, folded into --probe-A"),
        dict(candidate="G", variant="derivative superposition (post-distortion)",
             killed=True, acts_through_iqz=False,
             kill_why=["the discriminator §3 names is the IM3 SLOPE: g3-dominated "
                       "distortion shows slope exactly 3 well below compression, "
                       "clipping-dominated does not. Rung 0 measured slope "
                       "2.96-2.98 at max gain (§44.2/§44.9) -- clean cubic, but "
                       "the wall is CURRENT-CLIPPING (§44.4), which g3 "
                       "cancellation cannot fix. Costs the spare device + fails "
                       "§6.5's zero-flip bar (cancellation notches are bias-sharp; "
                       "§39.1 flips gates at +-1%). P5 expected-fail."],
             note="expected-fail (P5); killed on §44.4 (clipping) + §6.5 (sens)"),
        dict(candidate="H", variant="output-stage degeneration",
             killed=True, acts_through_iqz=False,
             kill_why=["series feedback trades gain for linearity but REDUCES "
                       "the drive at the output device under a current-clipping "
                       "limit (§3 row H, same objection as G) and costs S21 "
                       "margin (clause 4). At S band the simul point carries only "
                       "+3.45 dB of S21 margin (§1.1), so degeneration deep enough "
                       "to matter breaks the D4-SIM S21 floor. Composes with B "
                       "(more current affords more degen) but only after B lands."],
             note="expected-fail (P5) on S21 clause-4; re-openable only atop a "
                  "B survivor with S21 headroom"),
    ]
    for d in dfgh:
        d.update(recipe=RECIPE, source_arm=SOURCE_ARM, sim="not-sized")
        rows.append(d)
        print(f"  [{d['candidate']}] {d['variant']:<38} -> KILL "
              f"({d['note']})")

    # ------------------------------------------------ survivors + store
    survivors = [r for r in rows if r.get("sim") not in ("FAILED", "not-sized")
                 and not r.get("killed")]
    survivors.sort(key=lambda r: -r["iq_z_mv"])
    print("\n" + "=" * 68)
    print(f"RUNG 1 SURVIVORS (tier-legal at {vdd} V, Iq*|Z| improves), "
          f"ranked by Iq*|Z_ac|:")
    for r in survivors:
        print(f"  {r['candidate']:>3} {r['variant']:<24} "
              f"Iq*Z={r['iq_z_mv']:.1f} mV (dz {r['iq_z_delta_mv']:+.1f})  "
              f"S11={r['s11_max_db']:.2f}  Idd={r['idd_ma']:.2f}  "
              f"S21s={r['s21_db']['dhruva-s']:.1f}  NFl5={r['nf_db']['dhruva-l5']:.2f}")
    if not survivors:
        print("  (none)")

    payload = dict(recipe=RECIPE, source_arm=SOURCE_ARM,
                   diagnosis="output-swing-current-limit", vdd=vdd,
                   baseline=dict(iq_mnm6_ma=bprox["iq_mnm6_ma"],
                                 z_ac_ohm=bprox["z_ac_ohm"], iq_z_mv=base_iqz,
                                 s11_max_db=max(bfour[b]["s11_max_db"] for b in BANDS),
                                 idd_ma=max(bfour[b]["idd_ma"] for b in BANDS),
                                 tier_legal=bok),
                   rows=rows,
                   survivors=[dict(candidate=r["candidate"], variant=r["variant"],
                                   iq_z_mv=r["iq_z_mv"]) for r in survivors])
    path = os.path.join(OUT, "_lin_screen.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, default=float)
    print(f"\nwrote {path}")
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-A", action="store_true")
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--vdd", default="1.2")
    a = ap.parse_args()
    from moves import private_tmp
    private_tmp(os.path.join(OUT, "lin_screen_tmp"))
    if a.probe_A:
        cmd_probe_A()
    if a.screen:
        cmd_screen(a.vdd)
    if not (a.probe_A or a.screen):
        ap.error("--probe-A or --screen")


if __name__ == "__main__":
    main()
