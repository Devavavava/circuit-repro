"""bench-v2 motif audit: is `add:L:IN-G` (inductor VIN1 -> input-gate net, across
the circuit's own input DC-block C1) a real RF move or a testbench artefact?

READ-ONLY w.r.t. the running bench-v2 build: reads cells/<cell>/ (witness tokens,
spec.yaml, witness/results.json) and writes ONLY under motif-audit/results/.

Per cell:
  size   : re-run bench_anchor_prep.smoke_run(witness tokens, cell spec, seed 1,
           2500, bptm45, profile="rl-v1") -- the A1 call verbatim -- with three
           read-only monkeypatches that CAPTURE the prepared body, decode() and
           the final winner x (the historical code path is otherwise untouched).
           Cached in results/<cell>/sized_P0.json.
  probe  : at the SAME sized params, evaluate body variants (no re-sizing):
             P0      testbench as-is: Vp1 (dc 0, z0 50) -> Cp1 10p -> VIN1
             P1      ideal AC-coupled 50 ohm source: Cp1 = 1 uF (no DC path,
                     no in-band series reactance from the harness cap)
             P2      DC-coupled 50 ohm source: Cp1 shorted (source sets VIN1 DC
                     through 50 ohm to 0 V -- generator / grounded-feed antenna)
             P3      P0 + DC-only 50 ohm-to-ground at VIN1 through a 1 H choke
                     (AC identical to P0; isolates the DC question)
             noL     P0 with the IN-G inductor removed (its L + Q resistor)
             parent  the parent anchor topology at the witness's values for
                     the anchor devices (edits reverted, same sizes)
           and record DC op (VIN1/gate node V, input-device VGS/ID/VDS/region,
           port-1 DC branch current, Idd), sp/NF metrics, spec + tight-spec
           feasibility and the rl-v1 wide-stability verdict.
  resize : re-size the SAME witness topology once under P1 and P2 (seed 1 x
           2500, rl-v1), recording feasibility.

usage: motif_audit.py <cell> [<cell> ...] [--no-resize]
"""
import copy
import json
import math
import os
import re
import sys
import time

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_anchor_prep as PREP  # noqa: E402
import size as SZ  # noqa: E402
import null_sizer as NS  # noqa: E402
from topology import Topology  # noqa: E402

RUN = f"{REPO}/kaggle/campaigns/bench-v2/run"
OUT = f"{REPO}/kaggle/campaigns/bench-v2/motif-audit/results"
ANCH = f"{REPO}/kaggle/bench-anchors/lna"
PDK, SEED, BUDGET, PROFILE = "bptm45", 1, 2500, "rl-v1"
CP1_LINE = "Cp1 p1 VIN1 10p"


# ------------------------------------------------------------ port variants
def port_variant(body, kind):
    assert CP1_LINE in body, "testbench port line not found"
    if kind == "P0":
        return body
    if kind == "P1":
        return body.replace(CP1_LINE, "Cp1 p1 VIN1 1u")
    if kind == "P2":
        return body.replace(CP1_LINE, "Rp1dc p1 VIN1 1m")
    if kind == "P3":
        return body.replace(CP1_LINE, CP1_LINE + "\nLaudchk VIN1 naudchk 1\n"
                            "Raudchk naudchk 0 50")
    raise ValueError(kind)


def gate_of_input_device(body):
    m = re.search(r"^MNM1\s+(\S+)\s+(\S+)\s+(\S+)", body, re.M)
    return m.group(2) if m else None


def ing_inductors(body):
    """L elements from VIN1 to the input device gate (direct, or via their
    finite-Q series resistor RQ<name>)."""
    gate = gate_of_input_device(body)
    out = []
    for m in re.finditer(r"^(L\S+)\s+(\S+)\s+(\S+)\s+(\S+)", body, re.M):
        name, a, b = m.group(1), m.group(2), m.group(3)
        ends = {a, b}
        rq = re.search(rf"^RQ{name[1:]}\s+(\S+)\s+(\S+)", body, re.M) if True else None
        if rq:
            ends = ({a, b} | {rq.group(1), rq.group(2)}) - {f"nq{name[1:]}"}
        if ends == {"VIN1", gate}:
            out.append(name)
    return out, gate


def drop_inductor(body, lname):
    lines = [ln for ln in body.splitlines()
             if not re.match(rf"^({lname}|RQ{lname[1:]})\s", ln)]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------ verifier env
def set_rl_v1_env():
    _name, eff, _over = PREP.resolve_verifier(PROFILE)
    for k, v in eff.items():
        os.environ[k] = v


def load_spec(path):
    return SZ._spec_for_sizing(path, nf_gate=None, pdk=PDK)


# ------------------------------------------------------------ sizing w/ capture
def sized_run(tokens, spec_path, body_kind="P0"):
    """smoke_run (rl-v1) verbatim, with capture patches; body_kind != P0 swaps
    the port model in the prepared body BEFORE sizing."""
    cap = {}
    orig_prep, orig_mk, orig_bud = SZ.prepared_body, SZ.make_objective, NS._Budget

    def prep(*a, **k):
        r = orig_prep(*a, **k)
        if r is None:
            return r
        body, sizable, fixed = r
        body = port_variant(body, body_kind)
        cap["body"], cap["sizable"], cap["fixed"] = body, sizable, fixed
        return body, sizable, fixed

    def mk(*a, **k):
        r = orig_mk(*a, **k)
        cap["decode"] = r[2]
        return r

    class Bud(orig_bud):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            cap["bud"] = self

    SZ.prepared_body, SZ.make_objective, NS._Budget = prep, mk, Bud
    t0 = time.time()
    try:
        res = PREP.smoke_run(list(tokens), spec_path, SEED, BUDGET, PDK,
                             profile=PROFILE)
    finally:
        SZ.prepared_body, SZ.make_objective, NS._Budget = orig_prep, orig_mk, orig_bud
    secs = time.time() - t0
    if res is None or "bud" not in cap:
        return {"res": res, "params": None, "body": cap.get("body"), "secs": secs}
    bx, _bm = cap["bud"].best()
    x = (res.get("stab_replacement") or {}).get("x") or bx
    params = cap["decode"](x) if x is not None else None
    return {"res": res, "params": params, "body": cap["body"],
            "sizable": cap["sizable"], "fixed": cap["fixed"], "secs": round(secs, 1)}


# ------------------------------------------------------------ probing
def summarize_op(op):
    devs = {}
    for n, d in (op.get("devices") or {}).items():
        if n.startswith("m"):
            devs[n] = {k: d.get(k) for k in ("vgs", "vds", "id", "vth", "vov",
                                              "gm", "region")}
    nodes = op.get("nodes") or {}
    br = op.get("branches") or {}
    return {"devices": devs,
            "nodes": {k: nodes.get(k) for k in sorted(nodes)},
            "i_port1_dc_A": br.get("vp1"), "i_vsup_A": br.get("vsup"),
            "i_choke_note": "port DC current under P3 = V(VIN1)/50 (choke path)"}


def probe(body, params, spec, tight_spec):
    cap = {}
    m = SZ.eval_metrics(body, params, spec, op_capture=cap)
    out = {"metrics": m, "op": summarize_op(cap) if cap else None}
    if not m:
        out.update(spec_feasible=False, tight_feasible=False, wide_ok=False)
        return out
    feas, viol = spec.feasible(m)
    out["spec_feasible"] = bool(feas)
    out["violations"] = {k: v for k, v in (viol or {}).items() if v}
    out["tight_feasible"] = bool(tight_spec.feasible(m)[0]) if tight_spec else None
    st, ok = PREP.wide_stability(spec, body, params)
    out["mu_min_wide"] = (st or {}).get("mu_min")
    out["wide_ok"] = bool(ok)
    out["final_ok"] = bool(feas and ok)
    return out


def reactances(params, spec, lname):
    b = spec.band
    f0, flo, fhi = float(b["f0"]), float(b["f_lo"]), float(b["f_hi"])
    r = {"band_Hz": [flo, f0, fhi]}
    if lname:
        L = float(params[f"p{lname[1:]}V"])
        r["L_IN_G_H"] = L
        r["XL_ohm"] = [2 * math.pi * f * L for f in (flo, f0, fhi)]
        r["L_Q_series_R_ohm"] = float(params["pINDW0"]) * L / float(params["pINDQ"])
    if "pC1V" in params:
        C = float(params["pC1V"])
        r["C1_F"] = C
        r["XC1_ohm"] = [1 / (2 * math.pi * f * C) for f in (flo, f0, fhi)]
        if lname:
            r["L_par_C1_resonance_Hz"] = 1 / (2 * math.pi * math.sqrt(L * C))
    r["XCp1_10p_ohm"] = [1 / (2 * math.pi * f * 10e-12) for f in (flo, f0, fhi)]
    if lname:
        r["L_ser_Cp1_resonance_Hz"] = 1 / (2 * math.pi * math.sqrt(L * 10e-12))
    return r


def parent_body_params(anchor_name, params):
    toks = json.load(open(f"{ANCH}/{anchor_name}.tokens.json"))
    if isinstance(toks, dict):
        toks = toks.get("tokens", toks)
    r = SZ.prepared_body(Topology(list(toks)), inductor_q=PREP.INDUCTOR_Q, pdk=PDK)
    if r is None:
        return None, None, None
    body, sizable, fixed = r
    p = dict(fixed)
    missing = []
    for k in sizable:
        if k in params:
            p[k] = params[k]
        else:
            missing.append(k)
    return body, p, missing


ANCHOR_NAMES = {"a1": "lna-a1-inddegen-cascode", "a2": "lna-a2-current-reuse",
                "a3": "lna-a3-shunt-feedback", "a4": "lna-a4-twostage",
                "a5": "lna-a5-commongate"}


def audit_cell(cell, do_resize=True):
    cdir = f"{RUN}/cells/{cell}"
    odir = f"{OUT}/{cell}"
    os.makedirs(odir, exist_ok=True)
    meta = json.load(open(f"{cdir}/cell.json"))
    tokens = json.load(open(f"{cdir}/witness/witness.tokens.json"))
    spec_path = f"{cdir}/spec.yaml"
    tight_path = f"{RUN}/specs/{cell}__tight.yaml"
    spec = load_spec(spec_path)
    tight = load_spec(tight_path) if os.path.exists(tight_path) else None
    stored = json.load(open(f"{cdir}/witness/results.json"))
    stored_a1 = ((stored.get("runs") or {}).get("A1_seed1") or {}).get("result") or {}

    f = f"{odir}/sized_P0.json"
    if os.path.exists(f):
        s0 = json.load(open(f))
    else:
        s0 = sized_run(tokens, spec_path, "P0")
        json.dump(s0, open(f, "w"), indent=1, default=str)
    res0 = s0["res"] or {}
    params, body = s0["params"], s0["body"]
    rep = {"cell": cell, "anchor": meta.get("anchor"), "cls": meta.get("cls"),
           "script": meta.get("script"), "repairs": meta.get("repairs"),
           "rerun_feasible": res0.get("feasible"),
           "stored_A1_feasible": stored_a1.get("feasible"),
           "rerun_matches_stored_A1": {
               k: (res0.get("metrics", {}).get(k), stored_a1.get("metrics", {}).get(k))
               for k in ("s11_max_db", "s21_db", "idd_ma", "nf_max_db")},
           "params": params}
    if not params:
        json.dump(rep, open(f"{odir}/audit.json", "w"), indent=1, default=str)
        return rep
    lnames, gate = ing_inductors(body)
    rep["input_gate_net"] = gate
    rep["ing_inductors"] = lnames
    rep["has_L_IN_G"] = bool(lnames)
    rep["reactance"] = reactances(params, spec, lnames[0] if lnames else None)
    pr = {}
    for kind in ("P0", "P1", "P2", "P3"):
        pr[kind] = probe(port_variant(body, kind), params, spec, tight)
    if lnames:
        b_nol = body
        for ln in lnames:
            b_nol = drop_inductor(b_nol, ln)
        pr["noL"] = probe(b_nol, params, spec, tight)
    pb, pp, missing = parent_body_params(ANCHOR_NAMES[meta["anchor"]], params)
    if pb:
        pr["parent_same_sizes"] = probe(pb, pp, spec, tight)
        pr["parent_same_sizes"]["missing_params_defaulted"] = missing
    rep["probe"] = pr
    if do_resize:
        rs = {}
        for kind in ("P1", "P2"):
            ff = f"{odir}/sized_{kind}.json"
            if os.path.exists(ff):
                sk = json.load(open(ff))
            else:
                sk = sized_run(tokens, spec_path, kind)
                json.dump(sk, open(ff, "w"), indent=1, default=str)
            r = sk["res"] or {}
            entry = {"feasible": r.get("feasible"),
                     "spec_feasible": r.get("spec_feasible"),
                     "metrics": {k: (r.get("metrics") or {}).get(k) for k in
                                 ("s11_max_db", "s21_db", "s21_ripple_db",
                                  "idd_ma", "nf_max_db")},
                     "mu_min_wide": r.get("mu_min_wide"), "secs": sk.get("secs")}
            if sk.get("params"):
                entry["op_at_winner"] = probe(sk["body"], sk["params"], spec,
                                              tight)["op"]
            rs[kind] = entry
        rep["resize"] = rs
    json.dump(rep, open(f"{odir}/audit.json", "w"), indent=1, default=str)
    return rep


def main(argv):
    set_rl_v1_env()
    do_resize = "--no-resize" not in argv
    cells = [a for a in argv if not a.startswith("--")]
    for c in cells:
        t = time.time()
        try:
            r = audit_cell(c, do_resize)
            print(c, "done", round(time.time() - t), "s",
                  {k: (v.get("final_ok") if isinstance(v, dict) else v)
                   for k, v in (r.get("probe") or {}).items()},
                  {k: v.get("feasible") for k, v in (r.get("resize") or {}).items()},
                  flush=True)
        except Exception as e:  # noqa: BLE001
            import traceback
            print(c, "ERROR", traceback.format_exc()[-2000:], flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
