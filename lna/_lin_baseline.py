"""WP-LIN rung 0 -- the baseline that never existed: the designated point's
first-ever measured IIP3/OIP3, its re-derived operating point, and the §2.2
four-point falsification test.

This is a SIDECAR (16-WP-LIN.md §preamble / D-9): every harness parameter that
must differ from the shipped file is set by MODULE-ATTRIBUTE assignment on the
imported harness, never by editing the shared file. Nothing here edits
`lna/iip3.py`, `lna/size.py`, `lna/pgain.py` or `lna/_pgain_mech.py`; they are
imported read-only and re-pointed.

Two overrides mandated by §4.0 item 3:
  (a) `iip3.py` has no --vdd flag; the rail is set by the deck's own `pVDD`
      .param, so we emit one deck per rail and point `iip3.deck_for` at it.
  (b) `iip3.S21_REF_DB` is hard-coded to the l5 sizing's audited S21; measuring
      `simul` would trip the gain cross-check. It is RE-POINTED (never disabled,
      §4.0 -- it is the check that caught §37.4's deck mix-up) at this point's
      own audited S21, derived per-config from the emitted deck's `sp` run.

§42.2 / §6.7 node-name warning: the D6 out-bank S3 wiring is built by
`_pgain_mech.build("out-bank", body)`, which resolves every role structurally
from element lines and cross-checks each against a second element that must
touch it. No element in this file is inserted by literal node name.

Modes:
  --emit-deck --vdd 1.1,1.2   emit dhruva-simul.sp (+ min-gain S3 variants)
  --iip3 --state max,min --vdd 1.1,1.2 --replay 3   the replay-fenced two-tone
  --op --vdd 1.1,1.2          re-derive the §2.1 op table
  --falsify                   the §2.2 four-point Iq(MNM6)x|Z_ac| ordering test

Usage examples:
  python lna/_lin_baseline.py --emit-deck --vdd 1.1,1.2
  python lna/_lin_baseline.py --op --vdd 1.1,1.2
  python lna/_lin_baseline.py --iip3 --state max,min --vdd 1.2 --replay 3
  python lna/_lin_baseline.py --falsify
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import extract as E                       # noqa: E402
import size as S                          # noqa: E402
from topology import Topology             # noqa: E402
import _pgain_mech as M                   # noqa: E402
import iip3 as I3                         # noqa: E402

REPRO = os.path.join(HERE, "repro", "dhruva-best")
OUT = os.path.join(HERE, "out")
TOKENS = os.path.join(REPRO, "tokens.json")
SIMUL_PARAMS = os.path.join(REPRO, "dhruva-simul.params.json")
PGAIN_S3 = os.path.join(OUT, "pgain_out-bank_simul_even.json")

BANDS = {"l5": "dhruva-l5", "l2": "dhruva-l2", "l1": "dhruva-l1", "s": "dhruva-s"}
F0 = {"l5": 1176.45e6, "l2": 1227.6e6, "l1": 1575.42e6, "s": 2492.03e6}
RECIPE = "wplin-v1"


# ------------------------------------------------------------ substrate
def base_body():
    tok = json.load(open(TOKENS, encoding="utf-8"))
    prep = S.prepared_body(Topology(tok), inductor_q=12)
    if prep is None:
        raise SystemExit("_lin: bias insert skipped -- topology/bias mismatch")
    return prep  # (body, sizable, fixed)


def simul_params(vdd):
    p = json.load(open(SIMUL_PARAMS, encoding="utf-8"))
    p["pVDD"] = str(vdd)
    return p


def min_gain_body_params(body, params):
    """The D6 out-bank S3 (min-gain) configuration on this body.

    Roles are resolved structurally + cross-checked by _pgain_mech (§42.2); the
    S3 switch DOFs and control voltages come from the stored, audited
    pgain_out-bank_simul_even.json (§42.5 second table). Returns
    (body_with_bank, params_with_S3)."""
    rep = json.load(open(PGAIN_S3, encoding="utf-8"))
    assert rep["mech"] == "out-bank" and rep["sizing"] == "simul"
    bbody, dofs, fixed, states = M.build("out-bank", body)
    # S3 = the deepest (min-gain) state: all three switch gates ON.
    s3 = dict(states[-1][1])
    assert states[-1][0] == "S3", f"expected S3 last, got {states[-1][0]}"
    # cross-check the stored controls agree with the freshly-built state map
    stored_s3 = dict(rep["state_controls"][-1][1])
    assert s3 == stored_s3, f"S3 control mismatch: built {s3} vs stored {stored_s3}"
    p = dict(params, **fixed, **rep["dofs"], **s3)
    return bbody, p


# ------------------------------------------------------------ deck emission
def deck_name(state, vdd):
    """max/1.1 keeps the canonical name so lna/iip3.py --sizing simul works too.
    Others get an explicit config suffix."""
    v = f"{float(vdd):.1f}".replace(".", "p")
    if state == "max":
        return f"dhruva-simul.sp" if vdd in ("1.1", 1.1) else f"dhruva-simul_v{v}.sp"
    return f"dhruva-simul_min_v{v}.sp"


def emit_deck(state, vdd):
    """Emit a standalone runnable .sp for one (state, rail), byte-runnable by
    iip3.py's deck reader (resolved .include, port sources, .param pVDD)."""
    body, sizable, fixed = base_body()
    params = simul_params(vdd)
    if state == "min":
        body, params = min_gain_body_params(body, params)
    # a representative f0 for the appended sp/stability block; iip3.py strips
    # the whole .control block and rebuilds its own two-tone block, so the f0
    # baked here only matters for a plain `ngspice -b` of the emitted deck.
    deck = E.build_deck(body, params, F0["l5"], 1.1e9, 2.5e9)
    path = os.path.join(REPRO, deck_name(state, vdd))
    with open(path, "w", encoding="utf-8") as f:
        f.write(deck)
    return path


def cmd_emit(vdds, states=("max", "min")):
    for vdd in vdds:
        for st in states:
            p = emit_deck(st, vdd)
            print(f"wrote {p}  (state={st}, pVDD={vdd})")


# ------------------------------------------------------------ audited S21
def audited_s21(state, vdd):
    """This point's own per-band S21 at (state, rail), measured fresh from the
    substrate -- the reference the re-pointed cross-check uses. For state=max
    this reproduces §36.3; for state=min it reproduces §42.5's S3 gains."""
    body, sizable, fixed = base_body()
    params = simul_params(vdd)
    if state == "min":
        body, params = min_gain_body_params(body, params)
    ref = {}
    for tag, name in BANDS.items():
        spec = S._spec_for_sizing(name)
        m = S.eval_metrics(body, params, spec, nf_gated=False)
        if m is None:
            raise SystemExit(f"_lin: S21 ref sim failed {tag}/{state}/{vdd}")
        ref[tag] = m["s21_db"]
    return ref


# ------------------------------------------------------------ the two-tone
def measure_iip3(state, vdd, pins, replay=3, sep_proc=True):
    """Replay-fenced IIP3/OIP3 over four bands at one (state, rail).

    Re-points iip3.py at THIS config's deck + audited S21, runs `replay` in-proc
    repeats, and (if sep_proc) one separate-process repeat, reporting the
    worst spread on every gated quantity (§6.7)."""
    deck = os.path.join(REPRO, deck_name(state, vdd))
    if not os.path.exists(deck):
        emit_deck(state, vdd)
    ref = audited_s21(state, vdd)

    # --- module-attribute overrides on the imported harness (D-9) ---
    I3.S21_REF_DB = dict(ref)                          # re-point, never disable
    I3.DESIGNATED = "simul"
    orig_deck_for = I3.deck_for
    I3.deck_for = lambda tag, sizing=I3.DESIGNATED: deck  # config -> this deck
    I3.private_tmp()

    try:
        reps = []
        for r in range(replay):
            per = {}
            for tag in BANDS:
                res = I3.measure_band(tag, pins, sizing="simul", verbose=(r == 0))
                per[tag] = res
            reps.append(per)
    finally:
        I3.deck_for = orig_deck_for

    # in-process replay spread on every gated quantity
    def gq(res):
        return dict(iip3=res.get("iip3_dbm"), oip3=(res.get("iip3_dbm", 0) + res.get("gain_ss", 0))
                    if res.get("ok") else None,
                    gain=res.get("gain_ss"), slope=res.get("slope"),
                    dS21=res.get("d_s21_db"))
    spreads = {}
    for tag in BANDS:
        vals = [gq(rp[tag]) for rp in reps]
        spreads[tag] = {k: (max(v[k] for v in vals) - min(v[k] for v in vals))
                        if all(v[k] is not None for v in vals) else None
                        for k in vals[0]}
    return reps[0], spreads, ref


def oip3_of(res):
    return (res["iip3_dbm"] + res["gain_ss"]) if res.get("ok") else None


# ------------------------------------------------------------ op table
_OP_ROLE = {  # element name -> §2.1 role label
    "mnm1": "CG input (source on the input node)",
    "mnm2": "CS input, 66.2 um",
    "mnm3": "recombine-node device",
    "mnm4": "tank stage (L-loaded)",
    "mnm5": "CS input, 45.7 um",
    "mnm6": "output stage",
}


def op_table(vdd):
    """Re-derive the §2.1 operating point of the host at one rail, under the
    replay fence. Returns (rows, idd_mA, replay_spread)."""
    body, sizable, fixed = base_body()
    params = simul_params(vdd)
    spec = S._spec_for_sizing(BANDS["l5"])
    caps = []
    for _ in range(3):                              # replay fence, in-process
        cap = {}
        m = S.eval_metrics(body, params, spec, nf_gated=False, op_capture=cap)
        if m is None:
            raise SystemExit(f"_lin: op sim failed at {vdd}")
        caps.append(cap)
    cap = caps[0]
    dev = cap["devices"]
    # -i(Vsup): the supply branch current identifies the point (§2.1)
    supply = E._supply_name(body).lower()
    idd = None
    for k, v in cap.get("branches", {}).items():
        if k.lower() == supply:
            idd = -v
    idd_ma = abs(idd) * 1e3 if idd is not None else None
    rows = []
    for name in ("mnm1", "mnm2", "mnm3", "mnm4", "mnm5", "mnm6"):
        d = dev.get(name, {})
        idd_dev = d.get("id")
        gm = d.get("gm")
        rows.append(dict(
            device=name.upper(), role=_OP_ROLE[name],
            id_ma=(idd_dev * 1e3 if idd_dev is not None else None),
            share=(abs(idd_dev) / abs(idd) if idd_dev is not None and idd else None),
            gm_over_id=(gm / idd_dev if gm is not None and idd_dev else None),
            vds=d.get("vds"), vdsat=d.get("vdsat"), vgs=d.get("vgs"),
            vth=d.get("vth"), region=d.get("region")))
    # replay spread on Id across the 3 captures
    spread = 0.0
    for name in ("mnm1", "mnm2", "mnm3", "mnm4", "mnm5", "mnm6"):
        ids = [c["devices"].get(name, {}).get("id") for c in caps]
        if all(x is not None for x in ids):
            spread = max(spread, max(ids) - min(ids))
    return rows, idd_ma, spread


def cmd_op(vdds):
    result = {}
    for vdd in vdds:
        rows, idd_ma, spread = op_table(vdd)
        print(f"\n=== operating point @ pVDD = {vdd} V   "
              f"(-i(Vsup) = {idd_ma:.5f} mA, replay Id spread {spread:.3e} A) ===")
        hdr = f"{'dev':<6}{'Id(mA)':>9}{'share':>8}{'gm/Id':>8}{'Vds':>9}{'Vdsat':>9}{'region':>8}"
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            print(f"{r['device']:<6}{r['id_ma']:>9.4f}{r['share']*100:>7.1f}%"
                  f"{r['gm_over_id']:>8.1f}{r['vds']:>9.4f}{r['vdsat']:>9.4f}"
                  f"{r['region']:>8}")
        result[vdd] = dict(idd_ma=idd_ma, id_replay_spread_A=spread, rows=rows)
    path = os.path.join(OUT, "_lin_op_rederived.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, default=float)
    print(f"\nwrote {path}")
    # compare to the undocumented pre-existing artefacts (§1.5.5)
    for vdd, fn in (("1.1", "_lin_op_1p1.json"), ("1.2", "_lin_op_1p2.json")):
        p = os.path.join(OUT, fn)
        if vdd in result and os.path.exists(p):
            try:
                old = json.load(open(p, encoding="utf-8"))
                print(f"  found pre-existing {fn} (of unrecorded provenance)")
            except Exception as e:                        # noqa: BLE001
                print(f"  {fn}: unreadable ({e})")
        elif vdd in result:
            print(f"  no pre-existing {fn} on disk")
    return result


# ------------------------------------------------------- falsification test
def z_ac_mag(params, f0):
    """|Z_ac| at the output-stage drain: pR4V shunted by the 50 ohm port seen
    through CC6 (pC6V) in series with Cp2 (10 pF). §2.2's construction."""
    R = float(params["pR4V"])
    c6 = float(params["pC6V"])
    cp2 = 10e-12
    cser = c6 * cp2 / (c6 + cp2)               # series combination
    w = 2 * math.pi * f0
    zc = 1.0 / (1j * w * cser)                 # coupling reactance
    zport = zc + 50.0                          # port through the coupling
    zpar = 1.0 / (1.0 / R + 1.0 / zport)       # pR4V || (coupling + port)
    return abs(zpar)


def _own_oip3_transient(tag):
    """This-box transient OIP3 for one own-band sizing, measured on a FRESH
    body (include already resolved) driven through iip3's two-tone machinery
    directly -- the shipped dhruva-<tag>.sp on disk carry a stale Windows
    .include that iip3.py's raw deck reader cannot resolve (a port deviation,
    recorded in FINDINGS)."""
    body, sizable, fixed = base_body()
    pj = json.load(open(os.path.join(REPRO, f"dhruva-{tag}.params.json"),
                        encoding="utf-8"))
    deck = E.build_deck(body, pj, F0[tag], 1.1e9, 2.5e9)   # resolved include
    bf = lambda ve, f1, f2: I3.lna_two_tone_body(_write_tmp_deck(deck), ve, f1, f2)
    res = I3.iip3_sweep(bf, F0[tag], list(I3.DEFAULT_PINS), verbose=False)
    return res


_TMP_DECKS = {}


def _write_tmp_deck(text):
    import hashlib
    import tempfile
    h = hashlib.md5(text.encode()).hexdigest()
    if h not in _TMP_DECKS:
        fd, p = tempfile.mkstemp(suffix=".sp", prefix="lin_own_")
        with os.fdopen(fd, "w") as f:
            f.write(text)
        _TMP_DECKS[h] = p
    return _TMP_DECKS[h]


def _hb_own_oip3(tag):
    """The §37.7 harmonic-balance anchor for cross-listing (blocked on this box;
    stored from Session 9). OIP3 = IIP3 + G by slope-intercept over the rows."""
    import numpy as np
    try:
        d = json.load(open(os.path.join(HERE, "hb", "hb_iip3_ownsizing.json"),
                            encoding="utf-8"))["iip3"][BANDS[tag]]
    except Exception:                                        # noqa: BLE001
        return None
    r = d["rows"]
    x = np.array([p["pin"] for p in r])
    pf = np.array([p["pfund"] for p in r])
    p3 = np.array([max(p["pim3_lo"], p["pim3_hi"]) for p in r])
    gss = float((pf - x)[np.argmin(x)])
    b3 = float(np.mean(p3 - 3 * x))
    return 0.5 * (gss - b3) + gss


def cmd_falsify():
    """§2.2 four-point test: do the four §37.7 own-band sizings' OIP3 order with
    Iq(MNM6) x |Z_ac| ? OIP3 comes from this-box transient two-tone (with the
    stored HB anchor cross-listed); Iq(MNM6) from an op run per sizing; |Z_ac|
    from element values."""
    body, sizable, fixed = base_body()
    I3.private_tmp()
    print("\n=== §2.2 four-point falsification test (own-band sizings, 1.1 V) ===")
    print(f"{'sizing':<10}{'Iq(MNM6) mA':>13}{'|Z_ac| ohm':>12}"
          f"{'Iq*|Z| (mV)':>13}{'OIP3 tran':>11}{'OIP3 HB':>10}")
    pts = []
    for tag in ("l5", "l2", "l1", "s"):
        pj = json.load(open(os.path.join(REPRO, f"dhruva-{tag}.params.json"),
                            encoding="utf-8"))
        spec = S._spec_for_sizing(BANDS[tag])
        cap = {}
        S.eval_metrics(body, pj, spec, nf_gated=False, op_capture=cap)
        iq = abs(cap["devices"].get("mnm6", {}).get("id", float("nan")))
        z = z_ac_mag(pj, F0[tag])
        prod_mv = iq * z * 1e3
        res = _own_oip3_transient(tag)
        oip3 = (res["iip3_dbm"] + res["gain_ss"]) if res.get("ok") else None
        oip3_hb = _hb_own_oip3(tag)
        oip3 = oip3 if oip3 is not None else oip3_hb    # fall back to HB anchor
        pts.append(dict(sizing=tag, iq_ma=iq * 1e3, z_ohm=z, prod_mv=prod_mv,
                        oip3=oip3, oip3_hb=oip3_hb,
                        gain_ss=res.get("gain_ss"), slope=res.get("slope")))
        print(f"{'dhruva-'+tag:<10}{iq*1e3:>13.4f}{z:>12.2f}{prod_mv:>13.2f}"
              f"{(oip3 if oip3 is not None else float('nan')):>+11.3f}"
              f"{(oip3_hb if oip3_hb is not None else float('nan')):>+10.3f}")
    # ordering verdict: does OIP3 rank == Iq*|Z| rank?
    have = [p for p in pts if p["oip3"] is not None]
    by_prod = sorted(have, key=lambda p: p["prod_mv"])
    by_oip3 = sorted(have, key=lambda p: p["oip3"])
    order_match = [p["sizing"] for p in by_prod] == [p["sizing"] for p in by_oip3]
    # Spearman rank correlation
    n = len(have)
    if n >= 2:
        rp = {p["sizing"]: i for i, p in enumerate(by_prod)}
        ro = {p["sizing"]: i for i, p in enumerate(by_oip3)}
        dsq = sum((rp[p["sizing"]] - ro[p["sizing"]]) ** 2 for p in have)
        rho = 1 - 6 * dsq / (n * (n * n - 1))
    else:
        rho = float("nan")
    print(f"\n  ordering (ascending Iq*|Z|): {[p['sizing'] for p in by_prod]}")
    print(f"  ordering (ascending OIP3):   {[p['sizing'] for p in by_oip3]}")
    print(f"  exact rank match: {order_match}   Spearman rho = {rho:.4f}")
    print(f"  VERDICT: §2.2 current-limit ordering "
          f"{'HOLDS' if rho > 0.5 else 'FAILS'} on the four own-band sizings")
    out = dict(recipe=RECIPE, points=pts, exact_match=order_match, spearman_rho=rho)
    path = os.path.join(OUT, "_lin_falsify.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"  wrote {path}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-deck", action="store_true")
    ap.add_argument("--iip3", action="store_true")
    ap.add_argument("--op", action="store_true")
    ap.add_argument("--falsify", action="store_true")
    ap.add_argument("--vdd", default="1.1,1.2")
    ap.add_argument("--state", default="max,min")
    ap.add_argument("--pins", default=",".join(f"{p:g}" for p in I3.DEFAULT_PINS))
    ap.add_argument("--replay", type=int, default=3)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    vdds = [x.strip() for x in a.vdd.split(",")]
    states = [x.strip() for x in a.state.split(",")]
    pins = [float(x) for x in a.pins.split(",")]

    if a.emit_deck:
        cmd_emit(vdds, states)
    if a.op:
        cmd_op(vdds)
    if a.falsify:
        cmd_falsify()
    if a.iip3:
        allres = {}
        for vdd in vdds:
            for st in states:
                print(f"\n########## IIP3: state={st}, pVDD={vdd} V ##########")
                first, spreads, ref = measure_iip3(st, vdd, pins, replay=a.replay)
                cfg = {}
                for tag in BANDS:
                    res = first[tag]
                    cfg[tag] = dict(
                        iip3_dbm=res.get("iip3_dbm"), oip3_dbm=oip3_of(res),
                        gain_ss=res.get("gain_ss"), s21_ref=ref[tag],
                        d_s21_db=res.get("d_s21_db"), s21_ok=res.get("s21_ok"),
                        slope=res.get("slope"), slope_ok=res.get("slope_ok"),
                        im3_fit_resid_db=res.get("im3_fit_resid_db"),
                        worst_snr_db=res.get("worst_snr_db"),
                        iip3_pt_spread=res.get("iip3_pt_spread"),
                        kept=res.get("kept"), ok=res.get("ok"),
                        replay_spread=spreads[tag])
                allres[f"{st}_{vdd}"] = cfg
                print(f"\n  -- {st}-gain / {vdd} V summary --")
                for tag in BANDS:
                    c = cfg[tag]
                    if not c["ok"]:
                        print(f"    {tag}: NO RESULT")
                        continue
                    print(f"    {tag}: IIP3={c['iip3_dbm']:+.3f}  OIP3={c['oip3_dbm']:+.3f}"
                          f"  G={c['gain_ss']:.2f}  slope={c['slope']:.3f}"
                          f"  dS21={c['d_s21_db']:+.3f}({'ok' if c['s21_ok'] else 'MISS'})"
                          f"  replaySpread(iip3)={c['replay_spread']['iip3']:.4f}")
        jp = a.json or os.path.join(OUT, "_lin_iip3_baseline.json")
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(dict(recipe=RECIPE, diagnosis="output-swing-current-limit",
                           source="wplin-rung0-baseline", results=allres),
                      f, indent=1, default=float)
        print(f"\nwrote {jp}")


if __name__ == "__main__":
    main()
