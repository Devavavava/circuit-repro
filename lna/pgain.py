"""WP-PGAIN -- Gate D6: gain programmability on the D4-SIM design.

PROPOSED GATE MAPPING (a mapping DECISION, recorded here for user sign-off --
same class as the program's S21-for-voltage-gain decision; nothing below is
claimed as met until that sign-off):

  "Programmable" = ONE fixed netlist and ONE fixed set of device sizes, whose
  states differ ONLY in designated control-voltage parameters (`pVSWG*`) on the
  gates of inserted MOS switch devices. The switches are `nmos` instances from
  the same 45 nm card and the same multi-finger emission as every other device
  in the deck -- no ideal-switch elements, no per-state re-sizing.

  Gate D6 is MET iff, on one such netlist:
    1. >= 3 gain steps (>= 4 states), gain monotonic in the state index at
       EVERY band f0;
    2. span (max-gain state - min-gain state) >= 10.6 dB at EVERY band f0;
    3. in EVERY state: S11 <= -10 dB held over the whole 1.1-2.5 GHz range,
       and Idd <= 13 mA;
    4. the MAX-gain state still passes the full D4-SIM gate set on all four
       bands (S21 >= 30/25.4/22.3/22.3 dB, NF <= 3.5/2.7/2.5/2.5 dB) -- a
       programmable LNA that lost the benchmark in its top state has not
       gained programmability, it has traded it away;
    5. NF is gated at the MAX-gain state only; NF in the lower states is
       reported, not gated (the paper's NF is a high-gain number).
  K_min is reported per state (advisory everywhere in this program).

Substrate: the designated D4-SIM point -- topology `ace8383c2fa68d03`,
`repro/dhruva-best/dhruva-l5.params.json`, read-only. `--sizing simul` swaps in
the WP-HARDEN point (`dhruva-simul.params.json`, Idd 8.2 mA, S11 -11.01) as a
second substrate; every emitted row records which one it used.

  python lna/pgain.py --probe                 # where can this circuit be loaded?
  python lna/pgain.py --mech out-bank --tune  # size the switch DOFs, then table
  python lna/pgain.py --mech out-bank         # table from the stored DOFs
  python lna/pgain.py --replay --mech out-bank
  python lna/pgain.py --report                # every stored mechanism + verdict
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import size as S                              # noqa: E402
from topology import Topology                 # noqa: E402
from moves import private_tmp                 # noqa: E402
import _pgain_mech as M                       # noqa: E402

REPRO = os.path.join(HERE, "repro", "dhruva-best")
OUT = os.path.join(HERE, "out")
BANDS = ("dhruva-s", "dhruva-l1", "dhruva-l2", "dhruva-l5")
S21_TARGET = {"dhruva-s": 30.0, "dhruva-l1": 25.4,
              "dhruva-l2": 22.3, "dhruva-l5": 22.3}
SPAN_REQ = 10.6            # the paper's programmability range
SPAN_SET = 12.0           # --even target: SPAN_REQ plus a deliberate 1.4 dB
                          # of margin, so the shipped table is not a knife edge
S11_GATE, IDD_GATE = -10.0, 13.0
COARSE = "dhruva-l5"        # S11_max and Idd are band-independent (all four
                            # dhruva specs sweep the same 1.1-2.5 GHz), so one
                            # band carries every constraint but the other f0s.


# ------------------------------------------------------------- substrate

def base_design(sizing="l5"):
    tok = json.load(open(os.path.join(REPRO, "tokens.json"), encoding="utf-8"))
    prep = S.prepared_body(Topology(tok), inductor_q=12)
    if prep is None:
        raise SystemExit("pgain: bias insert skipped")
    body, sizable, _fixed = prep
    p = json.load(open(os.path.join(REPRO, f"dhruva-{sizing}.params.json"),
                       encoding="utf-8"))
    return body, dict(p), sizable


# ------------------------------------------------------------ evaluation

_SPECS = {}


def spec(band):
    if band not in _SPECS:
        _SPECS[band] = S._spec_for_sizing(band)
    return _SPECS[band]


def ev(body, params, band=COARSE, nf=False):
    return S.eval_metrics(body, params, spec(band), nf_gated=nf)


def eval_states(body, params, states, bands=BANDS, nf_state=0):
    """[(state_name, {band: metrics})] -- or None if any state fails to sim."""
    rows = []
    for k, (name, st) in enumerate(states):
        p = dict(params, **st)
        per = {}
        for b in bands:
            m = ev(body, p, b, nf=(nf_state is not None and k == nf_state))
            if m is None:
                return None
            per[b] = m
        rows.append((name, per))
    return rows


def coarse_states(body, params, states):
    """(s21, s11_max, idd) per state on the coarse band -- the descent's inner
    loop. One ngspice call per state."""
    out = []
    for _name, st in states:
        m = ev(body, dict(params, **st))
        if m is None:
            return None
        out.append((m["s21_db"], m["s11_max_db"], m["idd_ma"]))
    return out


# ------------------------------------------------------------ descent

def score(rows, even=False):
    """Lexicographic (violation, objective). `rows` = coarse_states output.

    violation counts, in dB/mA units so the terms are comparable:
      * S11 above -10 in ANY state (the constraint the task predicts will bind)
      * Idd above 13 mA in ANY state
      * the max-gain state falling below the coarse band's own S21 gate
      * any non-monotonic step (a 0.05 dB deadband keeps ties from counting)

    Objective: `even=False` maximizes the span (how much authority does this
    mechanism HAVE?); `even=True` instead asks for equal steps summing to
    SPAN_SET, i.e. the state table a programmable-gain part would actually
    ship, and treats a span below SPAN_REQ as a violation.
    """
    if rows is None:
        return (1e6, 0.0)
    v = 0.0
    for s21, s11, idd in rows:
        v += max(0.0, s11 - S11_GATE) + max(0.0, idd - IDD_GATE)
    v += max(0.0, S21_TARGET[COARSE] - rows[0][0])
    for k in range(len(rows) - 1):
        v += max(0.0, rows[k + 1][0] - rows[k][0] + 0.05)
    span = rows[0][0] - rows[-1][0]
    if not even:
        return (v, -span)
    v += max(0.0, SPAN_REQ - span)
    tgt = SPAN_SET / (len(rows) - 1)
    err = sum((rows[k][0] - rows[k + 1][0] - tgt) ** 2
              for k in range(len(rows) - 1))
    return (v, err)


def descent(body, params, dofs, states, budget=300, even=False, verbose=True):
    """Multiplicative pattern search over the switch DOFs ONLY.

    The core's 20 sized params are never touched -- they are the shipped,
    read-only D4-SIM point. Each DOF carries its own bounds; `in_box_report`
    flags any final value outside the spec's own sizing box
    (`size.kind_ranges`) rather than silently allowing or forbidding it.
    """
    starts = [{d["name"]: min(max(d["init"], d["lo"]), d["hi"]) for d in dofs},
              {d["name"]: d["lo"] for d in dofs},
              {d["name"]: d["hi"] for d in dofs}]
    # the all-lo start matters for honesty, not speed: for a shunt bank it is
    # the "bank barely present" point, which is feasible by construction (it is
    # the untouched D4-SIM design). A pattern search that starts feasible can
    # only report a wall it actually hit, never one its own initialisation
    # painted it into.
    per = max(len(states) * 8, budget // len(starts))
    gbest, gx, used = (float("inf"), 0.0), None, 0
    for s0 in starts:
        x = {d["name"]: (s0[d["name"]], d["lo"], d["hi"]) for d in dofs}
        cur = dict(params, **{k: v[0] for k, v in x.items()})
        best = score(coarse_states(body, cur, states), even)
        u, step = len(states), 4.0
        while u < per and step > 1.06:
            moved = False
            for d in dofs:
                n = d["name"]
                for f in (step, 1.0 / step):
                    if u >= per:
                        break
                    v, lo, hi = x[n]
                    nv = min(max(v * f, lo), hi)
                    if nv == v:
                        continue
                    trial = dict(cur, **{n: nv})
                    s = score(coarse_states(body, trial, states), even)
                    u += len(states)
                    if s < best:
                        best, cur, x[n], moved = s, trial, (nv, lo, hi), True
                        break
            if not moved:
                step **= 0.5
        used += u
        if best < gbest:
            gbest, gx = best, {k: v[0] for k, v in x.items()}
    if verbose:
        print(f"    descent: {len(starts)} starts, {used} evals, "
              f"viol={gbest[0]:.4g}, obj={gbest[1]:.4g} "
              f"({'even-step' if even else 'max-span'}) @ {COARSE}")
    return gx, gbest, used


# -------------------------------------------------------------- verdict

def verdict(rows, sizing):
    """The proposed-D6 checks, measured on the full four-band table."""
    c = {}
    spans = {b: rows[0][1][b]["s21_db"] - rows[-1][1][b]["s21_db"]
             for b in BANDS}
    c["steps"] = len(rows) - 1
    c["n_steps_ok"] = len(rows) - 1 >= 3
    c["monotonic"] = all(rows[k + 1][1][b]["s21_db"] < rows[k][1][b]["s21_db"]
                         for b in BANDS for k in range(len(rows) - 1))
    c["span_ok"] = all(spans[b] >= SPAN_REQ for b in BANDS)
    c["s11_ok"] = all(r[b]["s11_max_db"] <= S11_GATE
                      for _n, r in rows for b in BANDS)
    c["idd_ok"] = all(r[b]["idd_ma"] <= IDD_GATE for _n, r in rows for b in BANDS)
    top = rows[0][1]
    c["maxstate_s21_ok"] = all(top[b]["s21_db"] >= S21_TARGET[b] for b in BANDS)
    c["maxstate_nf_ok"] = all(
        top[b].get("nf_db") is not None
        and top[b]["nf_db"] <= spec(b).constraints["nf_db"]["max"] for b in BANDS)
    c["D6"] = all(c[k] for k in ("n_steps_ok", "monotonic", "span_ok", "s11_ok",
                                 "idd_ok", "maxstate_s21_ok", "maxstate_nf_ok"))
    # the wall, stated as a number whether or not the gate passes
    worst_s11 = max(r[BANDS[0]]["s11_max_db"] for _n, r in rows)
    c["worst_s11_max_db"] = worst_s11
    c["s11_break_db"] = round(max(0.0, worst_s11 - S11_GATE), 4)
    c["worst_span_db"] = min(spans.values())
    c["span_short_db"] = round(max(0.0, SPAN_REQ - min(spans.values())), 4)
    c["sizing"] = sizing
    return c, spans


def s11_limited_span(rows):
    """Deepest state that still holds S11 <= -10 on the whole range, and the
    span available up to it. This is the honest number for a mechanism that
    breaks the match: 'you may go this far, and no further'."""
    ok = 0
    for k, (_n, r) in enumerate(rows):
        if r[BANDS[0]]["s11_max_db"] <= S11_GATE:
            ok = k
        else:
            break
    return ok, min(rows[0][1][b]["s21_db"] - rows[ok][1][b]["s21_db"]
                   for b in BANDS)


# --------------------------------------------------------------- report

def in_box_report(dofs, tuned):
    """Which sized switch DOFs landed outside the spec's own W/R/C box."""
    rng = S.kind_ranges(spec(COARSE))
    out = {}
    for d in dofs:
        v = tuned.get(d["name"])
        if v is None:
            continue
        lo, hi = rng[d["kind"]][0], rng[d["kind"]][1]
        # same 1e-9 relative tolerance recreate.py's own in-box check uses, so a
        # DOF parked exactly on the box edge is not reported as an escape
        out[d["name"]] = dict(value=v, kind=d["kind"], box=[lo, hi],
                              in_box=bool(lo * (1 - 1e-9) <= v <= hi * (1 + 1e-9)))
    return out


def wall_axis(mech, dofs):
    """The single 'authority' knob of a mechanism, and what the rest is pinned
    to, for the `--wall` trade-off sweep.

    For every shunt bank that knob is the switch width (all branches together);
    any series resistor is pinned at the spec box's 50 ohm floor, i.e. at its
    most favourable value. For the degeneration ladder it is the rung
    resistance, with the shorting switches at maximum width. In both cases the
    pinned half is set to give the mechanism its BEST case, so a wall found
    here is the mechanism's, not the sweep's.
    """
    if mech == "in-degen":
        sweep = [d for d in dofs if d["kind"] == "R"]
        pin = {d["name"]: d["hi"] for d in dofs if d["kind"] == "W"}
    else:
        sweep = [d for d in dofs if d["kind"] == "W"]
        pin = {d["name"]: d["lo"] for d in dofs if d["kind"] == "R"}
    return sweep, pin


def cmd_wall(mech, sizing="l5", n=13):
    """Trade-off sweep: how much gain span does this mechanism buy, and what
    does the band-wide match cost, as its authority is turned up from nothing
    to the box limit? This is the number the deliverable needs for every
    mechanism that does NOT close the gate."""
    body0, params, _sz = base_design(sizing)
    body, dofs, fixed, states = M.build(mech, body0)
    sweep, pin = wall_axis(mech, dofs)
    params = dict(params, **fixed, **pin)
    lo = min(d["lo"] for d in sweep)
    hi = max(d["hi"] for d in sweep)
    print(f"\n=== WALL [{mech} @ {sizing}] {M.MECHS[mech]}")
    print(f"    knob = {sweep[0]['kind']} on {len(sweep)} branch(es), "
          f"{lo:.4g} -> {hi:.4g}; pinned: {pin or '(none)'}")
    print(f"{'knob':>10}{'span_dB':>10}{'worstS11':>10}{'worstIdd':>10}"
          f"{'maxS21':>9}   legal")
    rows, best_legal = [], None
    for i in range(n):
        v = lo * (hi / lo) ** (i / (n - 1))
        p = dict(params, **{d["name"]: v for d in sweep})
        cs = coarse_states(body, p, states)
        if cs is None:
            print(f"{v:>10.4g}    SIM FAILED")
            continue
        span = cs[0][0] - cs[-1][0]
        ws11 = max(c[1] for c in cs)
        widd = max(c[2] for c in cs)
        legal = ws11 <= S11_GATE and widd <= IDD_GATE
        rows.append((v, span, ws11, widd, cs[0][0], legal))
        if legal and (best_legal is None or span > best_legal[1]):
            best_legal = rows[-1]
        print(f"{v:>10.4g}{span:>10.3f}{ws11:>10.3f}{widd:>10.3f}"
              f"{cs[0][0]:>9.2f}   {'yes' if legal else 'NO'}")
    if best_legal:
        print(f"  -> largest match-legal span (coarse band {COARSE}): "
              f"{best_legal[1]:.2f} dB at knob {best_legal[0]:.4g}")
    else:
        print("  -> NO knob setting is match-legal at all")
    over = [r for r in rows if r[1] >= SPAN_REQ]
    if over:
        r = over[0]
        print(f"  -> first setting reaching the {SPAN_REQ} dB span: knob "
              f"{r[0]:.4g}, worst S11 {r[2]:.3f} dB "
              f"({'holds' if r[2] <= S11_GATE else 'BREAKS the gate by %.3f dB' % (r[2] - S11_GATE)}), "
              f"worst Idd {r[3]:.3f} mA")
    else:
        print(f"  -> the {SPAN_REQ} dB span is UNREACHABLE anywhere on this "
              f"axis (max {max((r[1] for r in rows), default=0):.2f} dB)")
    return rows


def store_path(mech, sizing, even=False):
    return os.path.join(OUT, f"pgain_{mech}_{sizing}{'_even' if even else ''}.json")


def run_mech(mech, sizing="l5", tune=False, budget=300, nf_all=False, even=False):
    body0, params, _sz = base_design(sizing)
    body, dofs, fixed, states = M.build(mech, body0)
    params = dict(params, **fixed)
    path = store_path(mech, sizing, even)
    if tune:
        print(f"[{mech}/{sizing}] {M.MECHS[mech]}")
        print(f"    {len(states)} states, {len(dofs)} switch DOFs, "
              f"budget {budget} coarse evals")
        tuned, best, used = descent(body, params, dofs, states,
                                    budget=budget, even=even)
    else:
        if not os.path.exists(path):
            raise SystemExit(f"pgain: no stored DOFs at {path}; run --tune")
        tuned = json.load(open(path, encoding="utf-8"))["dofs"]
        best, used = None, 0
    params = dict(params, **tuned)

    rows = eval_states(body, params, states, nf_state=(None if nf_all else 0))
    if rows is None:
        raise SystemExit(f"pgain: mechanism {mech} failed to simulate")
    chk, spans = verdict(rows, sizing)
    deep, deep_span = s11_limited_span(rows)
    ins = [ln for ln in body.splitlines()
           if ln.strip().startswith(("MSWG", "RSWG", "CSWG", "VSWG"))]
    rep = dict(mech=mech, desc=M.MECHS[mech], sizing=sizing,
               roles=M.resolve_nodes(body0), inserted=ins,
               dofs=tuned, fixed=fixed, n_states=len(states), objective=("even-step" if even else "max-span"),
               dof_box=in_box_report(dofs, tuned),
               states=[(n, {b: {k: r[b].get(k) for k in
                                ("s21_db", "s11_max_db", "idd_ma", "nf_db",
                                 "k_min")} for b in BANDS}) for n, r in rows],
               state_controls=[(n, st) for n, st in states],
               spans=spans, checks=chk,
               s11_ok_depth=deep, s11_ok_span_db=deep_span,
               descent=dict(evals=used, best=list(best) if best else None))
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    print_table(rep)
    return rep


def print_table(rep):
    print(f"\n=== {rep['mech']} @ sizing {rep['sizing']}: {rep['desc']} ===")
    hdr = (f"{'state':<5}" + "".join(f"{b.replace('dhruva-',''):>9}" for b in BANDS)
           + f"{'S11max':>9}{'Idd':>8}{'Kmin':>8}   NF@max-gain")
    print(hdr)
    print("-" * len(hdr))
    for name, r in rep["states"]:
        nfs = "  ".join(f"{r[b]['nf_db']:.3f}" for b in BANDS
                        if r[b].get("nf_db") is not None)
        print(f"{name:<5}" + "".join(f"{r[b]['s21_db']:>9.2f}" for b in BANDS)
              + f"{r[BANDS[0]]['s11_max_db']:>9.3f}"
              + f"{r[BANDS[0]]['idd_ma']:>8.3f}"
              + f"{min(r[b]['k_min'] for b in BANDS):>8.2f}   {nfs}")
    print("span (dB): " + "  ".join(
        f"{b.replace('dhruva-','')}={rep['spans'][b]:.2f}" for b in BANDS))
    c = rep["checks"]
    print(f"checks: D6={c['D6']}  steps={c['steps']}({c['n_steps_ok']})  "
          f"mono={c['monotonic']}  span>={SPAN_REQ}:{c['span_ok']}  "
          f"s11:{c['s11_ok']}  idd:{c['idd_ok']}  "
          f"maxS21:{c['maxstate_s21_ok']}  maxNF:{c['maxstate_nf_ok']}")
    if not c["s11_ok"]:
        print(f"  WALL: worst S11_max = {c['worst_s11_max_db']:.3f} dB "
              f"(breaks the -10 dB gate by {c['s11_break_db']:.3f} dB); "
              f"deepest S11-legal state = {rep['s11_ok_depth']} "
              f"=> only {rep['s11_ok_span_db']:.2f} dB of span is match-legal")
    if not c["span_ok"]:
        print(f"  WALL: worst-band span {c['worst_span_db']:.2f} dB, "
              f"{c['span_short_db']:.2f} dB short of {SPAN_REQ}")


def cmd_replay(mech, sizing, reps=3, even=False):
    """House replay fence: re-measure every state `reps` times from the stored
    DOFs and print the worst spread over states x bands x gated metrics."""
    body0, params, _sz = base_design(sizing)
    body, dofs, fixed, states = M.build(mech, body0)
    rep = json.load(open(store_path(mech, sizing, even), encoding="utf-8"))
    params = dict(params, **fixed, **rep["dofs"])
    worst, ok = 0.0, True
    for i in range(reps):
        rows = eval_states(body, params, states, nf_state=0)
        if rows is None:
            print("replay: SIM FAILED")
            return False
        if i == 0:
            ref = rows
            continue
        for (n0, r0), (n1, r1) in zip(ref, rows):
            for b in BANDS:
                for k in ("s21_db", "s11_max_db", "idd_ma", "nf_db"):
                    a, c = r0[b].get(k), r1[b].get(k)
                    if a is None or c is None:
                        continue
                    worst = max(worst, abs(a - c))
            _ = (n0, n1)
    chk, _ = verdict(ref, sizing)
    print(f"replay x{reps} [{mech}/{sizing}]: worst spread over "
          f"{len(states)} states x 4 bands x 4 metrics = {worst:.6g}; "
          f"D6={chk['D6']}")
    return ok


def cmd_probe(sizing="l5"):
    """Mechanism-independent map: an IDEAL 10 pF-blocked shunt resistor at each
    circuit role, R swept. Answers the question the task flags as the hard one
    -- where can this design be loaded without spending its band-wide match?"""
    body, params, _sz = base_design(sizing)
    roles = M.resolve_nodes(body)
    m0 = ev(body, params)
    print(f"baseline [{sizing}]: S21={m0['s21_db']:.3f} "
          f"S11max={m0['s11_max_db']:.3f} Idd={m0['idd_ma']:.3f}")
    print("\nideal AC shunt (10 pF + R) per role -- S21 drop / S11_max over "
          "1.1-2.5 GHz")
    order = ["comb", "g2", "cgd", "g3", "recomb", "g4", "tank", "g6", "outd"]
    rs = (1000.0, 300.0, 100.0, 50.0, 20.0, 5.0)
    print(f"{'role':<8}{'node':<6}" + "".join(f"{'R=%g' % r:>17}" for r in rs))
    for role in order + ["VOUT1"]:
        node = roles.get(role, "VOUT1")
        cells = []
        for r in rs:
            b = body.rstrip() + f"\nCPRB {node} nprb 1e-11\nRPRB nprb 0 {r}\n"
            m = ev(b, params)
            cells.append("      SIMFAIL   " if m is None else
                         f"{m0['s21_db']-m['s21_db']:>7.2f}/{m['s11_max_db']:>8.3f}")
        print(f"{role:<8}{node:<6}" + "".join(f"{c:>17}" for c in cells))
    print("\n(cell = gain drop in dB / S11_max in dB; the -10 dB gate is the "
          "second number's ceiling)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mech", choices=list(M.MECHS))
    ap.add_argument("--sizing", default="l5", choices=["l5", "simul", "s", "l1", "l2"])
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--budget", type=int, default=300)
    ap.add_argument("--nf-all", action="store_true",
                    help="measure NF in every state (default: max-gain only)")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--wall", action="store_true",
                    help="authority-vs-match trade-off sweep for --mech (or --all)")
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--even", action="store_true",
                    help="size for equal gain steps summing to SPAN_SET "
                         "instead of maximum span")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--all", action="store_true", help="--tune every mechanism")
    a = ap.parse_args()
    private_tmp(os.path.join(OUT, "pgain_tmp"))

    if a.probe:
        cmd_probe(a.sizing)
        return
    if a.wall:
        for m in ([a.mech] if a.mech else list(M.MECHS)):
            cmd_wall(m, a.sizing)
        return
    if a.report:
        for f in sorted(os.listdir(OUT)):
            if f.startswith("pgain_") and f.endswith(".json"):
                print_table(json.load(open(os.path.join(OUT, f), encoding="utf-8")))
        return
    if a.all:
        for m in M.MECHS:
            try:
                run_mech(m, a.sizing, tune=True, budget=a.budget,
                         nf_all=a.nf_all, even=a.even)
            except SystemExit as e:
                print(f"[{m}] ABORTED: {e}")
        return
    if not a.mech:
        ap.error("--mech, --probe, --wall, --report or --all")
    if a.replay:
        sys.exit(0 if cmd_replay(a.mech, a.sizing, a.reps, a.even) else 1)
    run_mech(a.mech, a.sizing, tune=a.tune, budget=a.budget,
             nf_all=a.nf_all, even=a.even)


if __name__ == "__main__":
    main()
