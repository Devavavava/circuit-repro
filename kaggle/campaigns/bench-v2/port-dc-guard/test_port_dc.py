#!/usr/bin/env python
"""Tests of the rl-v1.1 port-DC requirement (PREREG-BENCH-V2 AMENDMENT 2) ->
port-dc-guard/results.json. Read-only w.r.t. the bench-v2 run (reads its frozen
amendment-1 record, result cache and the motif-audit sized winners).

  T1 the 9 add:L:IN-G accepted cells     pre-filter + behavioural on the motif-
                                          audit sized winner (no re-sizing): FAIL
  T2 controls nb090-gain-007, wb1020-noise-003  same: PASS
  T3 the 5 library anchors               pre-filter + rl-v1.1 sizing (seed 1 x 2500
                                          at probe-amd1-nb240-gain) + behavioural
                                          on the captured winner: PASS
  T4 synthetic positive: a3 + shunt L VIN1-VSS   NOT pre-filtered; sized under
                                          rl-v1.1; behavioural on the winner: PASS
  T5 synthetic negative: each anchor with its input DC-block shorted (1 mOhm), at
                                          the T3 sizes: pre-filter FAIL; behavioural
  T6 cost of one behavioural check (2 op decks)
  T7 cache bridge exactness: derive_port_dc(recorded rl-v1 row) == a fresh
     rl-v1.1 smoke_run of the same call (byte-identical JSON); a feasible
     prefilter-passing row re-sized under rl-v1.1 == the rl-v1 row + port-DC keys
  T8 byte-identical: rl-v1 profile re-runs of recorded bench-v2 rows == recorded
     results; no profile: HEAD (pre-rl-v1.1) module vs this module, same call.
usage: envrun.sh python test_port_dc.py [--procs 4]
"""
import importlib.util
import json
import multiprocessing as mp
import os
import re
import statistics
import subprocess
import sys
import time

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop",
           REPO + "/kaggle/campaigns/bench-v2"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_anchor_prep as PREP  # noqa: E402
import size as SZ  # noqa: E402
import null_sizer as NS  # noqa: E402

CAMP = f"{REPO}/kaggle/campaigns/bench-v2"
RUN = f"{CAMP}/run"
REC = f"{RUN}/amendment-1-record"
AUDIT = f"{CAMP}/motif-audit/results"
OUT = f"{CAMP}/port-dc-guard"
PDK, BUDGET = "bptm45", 2500
LING = ["v2a-wb0530-noise-082", "v2a-wb0530-power-000", "v2a-wb0530-power-084",
        "v2a-wb0530-power-091", "v2a-wb0824-gain-002", "v2a-wb0824-gain-019",
        "v2a-wb0824-gain-074", "v2a-wb0824-gain-093", "v2a-wb0824-gain-126"]
CONTROLS = ["v2a-nb090-gain-007", "v2a-wb1020-noise-003"]
ANCHORS = {"a1": "lna-a1-inddegen-cascode", "a2": "lna-a2-current-reuse",
           "a3": "lna-a3-shunt-feedback", "a4": "lna-a4-twostage",
           "a5": "lna-a5-commongate"}
PROBE = f"{RUN}/specs/probe-amd1-nb240-gain.yaml"
# recorded amendment-1 rows (run/results.jsonl), picked by kind (see README)
ROWS = {"search_feasible_prefilter_pass": "857fd22770c140fb7062",
        "search_infeasible_prefilter_pass": "8288087cbdf19288c37e",
        "search_feasible_prefilter_fail": "d85774618dc3147005f4",
        "cal_anchor_feasible": "8d792c772de4114b7337",
        "inproc_pre_reject": "8db6d25c5f05be5c3bda"}


def norm(x):
    """the result minus its ONE wall-clock field, stab_inloop.wide_secs (the same
    exclusion smoke_checks.py's determinism check makes); key order kept."""
    if isinstance(x, dict) and isinstance(x.get("stab_inloop"), dict):
        x = dict(x, stab_inloop={k: v for k, v in x["stab_inloop"].items()
                                 if k != "wide_secs"})
    return x


def jd(x):
    return json.dumps(norm(x), sort_keys=False, default=repr)


def diff_keys(a, b):
    a, b = norm(a) or {}, norm(b) or {}
    return sorted(k for k in set(a) | set(b) if json.dumps(a.get(k), default=repr)
                  != json.dumps(b.get(k), default=repr))


def anchor_tokens(a):
    return json.load(open(f"{REPO}/kaggle/bench-anchors/lna/{ANCHORS[a]}.tokens.json"))


def anchor_net(a):
    return "\n".join(ln for ln in open(f"{REPO}/kaggle/bench-anchors/lna/{ANCHORS[a]}.net")
                     .read().splitlines() if ln.strip() and not ln.startswith("*")) + "\n"


def round_trip_tokens(net):
    import proposal as P
    rt = P.round_trip(net)
    assert rt.get("ok"), rt.get("error")
    return rt["tokens"]


def timed_check(spec, body, params):
    t = time.time()
    r = PREP.port_dc_check(spec, body, params)
    return r, round(time.time() - t, 3)


def sized_capture(tokens, spec_path, profile, seed=1, budget=BUDGET):
    """smoke_run verbatim + read-only capture of the prepared body and the final
    winner's decoded values (motif-audit sized_run pattern)."""
    cap = {}
    o_prep, o_mk, o_bud = SZ.prepared_body, SZ.make_objective, NS._Budget

    def prep(*a, **k):
        r = o_prep(*a, **k)
        if r is not None:
            cap["body"] = r[0]
        return r

    def mk(*a, **k):
        r = o_mk(*a, **k)
        cap["decode"] = r[2]
        return r

    class Bud(o_bud):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            cap["bud"] = self
    SZ.prepared_body, SZ.make_objective, NS._Budget = prep, mk, Bud
    t = time.time()
    try:
        res = PREP.smoke_run(list(tokens), spec_path, seed, budget, PDK, profile=profile)
    finally:
        SZ.prepared_body, SZ.make_objective, NS._Budget = o_prep, o_mk, o_bud
    secs = round(time.time() - t, 1)
    params = None
    if res is not None and "bud" in cap:
        bx, _ = cap["bud"].best()
        rep = res.get("stab_replacement")
        x = rep["x"] if (res.get("stab_winner_replaced") and rep) else bx
        params = cap["decode"](x) if x is not None else None
    return res, cap.get("body"), params, secs


def pf_summary(tokens):
    p = PREP.port_dc_prefilter(tokens)
    return {k: p[k] for k in ("pass", "why", "group", "reaches_vss")}


def chk_summary(r):
    return {k: r.get(k) for k in ("pass", "dVG_max_V", "dVG_max_dev", "dIdd_pct",
                                  "idd0_mA", "idd1_mA", "v_vin1_0_V", "v_vin1_1_V",
                                  "i_port_dc_mA", "n_gates", "error")}


# ------------------------------------------------------------------ cases
def case_cell(cell):
    toks = json.load(open(f"{RUN}/cells/{cell}/witness/witness.tokens.json"))
    s = json.load(open(f"{AUDIT}/{cell}/sized_P0.json"))
    spec = SZ._spec_for_sizing(f"{RUN}/cells/{cell}/spec.yaml", nf_gate=None, pdk=PDK)
    r, secs = timed_check(spec, s["body"], s["params"])
    pf = pf_summary(toks)
    return {"case": cell, "prefilter": pf, "behavioural": chk_summary(r), "check_secs": secs,
            "rl_v1_1_reject": (not pf["pass"]) or (not r["pass"])}


def short_input_block(body):
    """the anchor's own input DC block (the C element at VIN1) -> 1 mOhm."""
    m = re.search(r"^(?!Cp\d)(C\S+)\s+(VIN1\s+\S+|\S+\s+VIN1)\s+\S+\s*$", body, re.M)
    assert m, "no input DC-block cap at VIN1"
    return body.replace(m.group(0), f"Rshortdcblk {m.group(2)} 1m"), m.group(1)


def case_anchor(a):
    toks = anchor_tokens(a)
    res, body, params, secs = sized_capture(toks, PROBE, "rl-v1.1")
    spec = SZ._spec_for_sizing(PROBE, nf_gate=None, pdk=PDK)
    out = {"case": f"anchor {a}", "prefilter": pf_summary(toks), "sizing_secs": secs,
           "sized_feasible": (res or {}).get("feasible"),
           "infeasible_reason": (res or {}).get("infeasible_reason"),
           "result_port_dc": chk_summary(res["port_dc"]) if (res or {}).get("port_dc") else None}
    r, cs = timed_check(spec, body, params)
    out["behavioural"], out["check_secs"] = chk_summary(r), cs
    # T5 negative: same sizes, input DC-block shorted
    b2, cname = short_input_block(body)
    r2, cs2 = timed_check(spec, b2, params)
    net = anchor_net(a)
    m = re.search(r"^C\s+(\S+)\s+(VIN1)\s+(\S+)$|^C\s+(\S+)\s+(\S+)\s+(VIN1)$", net, re.M)
    other = m.group(3) or m.group(5)
    shorted = "\n".join(ln for ln in net.splitlines() if ln != m.group(0))
    shorted = re.sub(rf"\b{re.escape(other)}\b", "VIN1", shorted) + "\n"
    try:
        pf2 = pf_summary(round_trip_tokens(shorted))
    except AssertionError as e:
        pf2 = {"pass": None, "why": [f"round-trip failed: {e}"]}
    out["shorted_input_block"] = {"element": cname, "prefilter": pf2,
                                  "behavioural": chk_summary(r2), "check_secs": cs2}
    return out


def case_synth_shunt():
    net = anchor_net("a3") + "L Lsh VIN1 VSS\n"
    toks = round_trip_tokens(net)
    pf = pf_summary(toks)
    out = {"case": "synthetic positive: a3 + shunt L VIN1-VSS", "netlist": net,
           "prefilter": pf}
    res, body, params, secs = sized_capture(toks, PROBE, "rl-v1.1")
    spec = SZ._spec_for_sizing(PROBE, nf_gate=None, pdk=PDK)
    out.update(sizing_secs=secs, sized_feasible=(res or {}).get("feasible"),
               infeasible_reason=(res or {}).get("infeasible_reason"),
               result_port_dc=chk_summary(res["port_dc"]) if (res or {}).get("port_dc") else None)
    if params:
        r, cs = timed_check(spec, body, params)
        out["behavioural"], out["check_secs"] = chk_summary(r), cs
    return out


def recorded_row(jid):
    for ln in open(f"{RUN}/results.jsonl"):
        if jid in ln:
            r = json.loads(ln)
            if r["jid"] == jid:
                return r
    raise KeyError(jid)


def row_tokens(r):
    m = r.get("meta") or {}
    if r["kind"] in ("cal", "F1", "T-F1"):
        return anchor_tokens(m["anchor"])
    if r["kind"] == "search":
        for ln in open(f"{REC}/candidates.jsonl"):
            if m["cid"] in ln:
                c = json.loads(ln)
                if c["cid"] == m["cid"]:
                    return c["tokens"]
    if r["kind"] == "F2":
        import bv2
        cells = bv2.load_jsonl_last(f"{REC}/cells.jsonl", "name")
        a = cells[m["cell"]]["anchor"]
        net = anchor_net(a)
        lines = net.splitlines()
        if m["edit"].startswith("add "):
            _, t, pair = m["edit"].split()
            x, y = pair.split("-")
            return round_trip_tokens("\n".join(lines) + f"\n{t} {t}x {x} {y}\n")
    raise KeyError(r["kind"])


def case_row(key, jid):
    r = recorded_row(jid)
    toks = row_tokens(r)
    spec = f"{REPO}/{r['spec']}"
    seed, budget = r["seed"], r["budget"]
    out = {"case": key, "jid": jid, "kind": r["kind"], "recorded_feasible": (r["res"] or {}).get("feasible"),
           "recorded_n_evals": (r["res"] or {}).get("n_evals"), "recorded_profile": r.get("profile")}
    t = time.time()
    v1 = PREP.smoke_run(list(toks), spec, seed, budget, PDK, profile="rl-v1")
    out["rl_v1_rerun_secs"] = round(time.time() - t, 1)
    out["rl_v1_byte_identical"] = jd(v1) == jd(r["res"])
    out["rl_v1_diff_keys"] = diff_keys(v1, r["res"])
    out["rl_v1_wide_secs_recorded_vs_rerun"] = [
        ((r["res"] or {}).get("stab_inloop") or {}).get("wide_secs"),
        ((v1 or {}).get("stab_inloop") or {}).get("wide_secs")]
    t = time.time()
    v11 = PREP.smoke_run(list(toks), spec, seed, budget, PDK, profile="rl-v1.1")
    out["rl_v1_1_secs"] = round(time.time() - t, 1)
    out["rl_v1_1_feasible"] = (v11 or {}).get("feasible")
    out["rl_v1_1_infeasible_reason"] = (v11 or {}).get("infeasible_reason")
    out["rl_v1_1_port_dc"] = chk_summary(v11["port_dc"]) if (v11 or {}).get("port_dc") else None
    ok, der = PREP.derive_port_dc(r["res"], toks, spec, seed, budget, PDK)
    out["derivable"] = ok
    if ok:
        out["derived_equals_fresh_rl_v1_1"] = jd(der) == jd(v11)
        out["derived_diff_keys"] = diff_keys(der, v11)
    else:
        # feasible rl-v1 twin: the re-size must reproduce the same winner, the
        # rl-v1.1 dict = the rl-v1 dict + port_dc_prefilter/port_dc (+ feasible /
        # infeasible_reason when the check fails) + the rl-v1.1 verifier record
        a = {k: v for k, v in r["res"].items() if k != "verifier"}
        b = {k: v for k, v in (v11 or {}).items()
             if k not in ("verifier", "port_dc_prefilter", "port_dc")}
        if not ((v11 or {}).get("port_dc") or {}).get("pass", True):
            b.pop("feasible", None)
            b.pop("infeasible_reason", None)
            a.pop("feasible", None)
        out["resized_same_as_rl_v1_plus_port_dc"] = jd(a) == jd(b)
        out["resized_diff_keys"] = diff_keys(a, b)
    return out


def case_noprofile(a):
    """no profile: HEAD's bench_anchor_prep (pre-rl-v1.1) vs this one."""
    src = subprocess.run(["git", "-C", REPO, "show", "HEAD:kaggle/bench_anchor_prep.py"],
                         capture_output=True, text=True, check=True).stdout
    p = f"{OUT}/_scratch/bap_head.py"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(src)
    spec_ = importlib.util.spec_from_file_location("bap_head", p)
    old = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(old)
    toks = anchor_tokens(a)
    for k in ("VERIFIER_PROFILE",) + PREP.VERIFIER_FLAGS + PREP.VERIFIER_FLAGS_EXT:
        assert k not in os.environ, k
    t = time.time()
    r_old = old.smoke_run(list(toks), PROBE, 1, BUDGET, PDK)
    r_new = PREP.smoke_run(list(toks), PROBE, 1, BUDGET, PDK)
    return {"case": f"no profile, anchor {a} @ probe-amd1-nb240-gain s1", "byte_identical":
            jd(r_old) == jd(r_new), "has_verifier_key": "verifier" in (r_new or {}),
            "secs": round(time.time() - t, 1)}


def run_case(spec):
    name, args = spec
    t = time.time()
    try:
        r = globals()[name](*args)
    except Exception:                                            # noqa: BLE001
        import traceback
        r = {"case": f"{name}{args}", "error": traceback.format_exc()[-2000:]}
    r["wall_secs"] = round(time.time() - t, 1)
    return name, args, r


def main():
    procs = 4
    if "--procs" in sys.argv:
        procs = int(sys.argv[sys.argv.index("--procs") + 1])
    jobs = ([("case_cell", (c,)) for c in LING + CONTROLS]
            + [("case_anchor", (a,)) for a in ANCHORS]
            + [("case_synth_shunt", ())]
            + [("case_row", (k, j)) for k, j in ROWS.items()]
            + [("case_noprofile", ("a3",)), ("case_noprofile", ("a1",))])
    only = None
    if "--only" in sys.argv:                 # re-run some case kinds, keep the rest
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
        jobs = [j for j in jobs if j[0] in only]
    with mp.get_context("fork").Pool(procs) as pool:
        got = pool.map(run_case, jobs, chunksize=1)
    if only:
        prev = json.load(open(f"{OUT}/raw_cases.json"))
        keep = [x for x in prev if x[0] not in only]
        got = [tuple(x) for x in keep] + [(n, list(a), r) for n, a, r in got]
    with open(f"{OUT}/raw_cases.json", "w") as fh:
        json.dump([[n, list(a), r] for n, a, r in got], fh, default=repr)
    res = {"T1_LING": [], "T2_controls": [], "T3_T5_anchors": [], "T4_synth_shunt": None,
           "T7_T8_rows": [], "T8_noprofile": []}
    for name, args, r in got:
        if name == "case_cell":
            res["T1_LING" if args[0] in LING else "T2_controls"].append(r)
        elif name == "case_anchor":
            res["T3_T5_anchors"].append(r)
        elif name == "case_synth_shunt":
            res["T4_synth_shunt"] = r
        elif name == "case_row":
            res["T7_T8_rows"].append(r)
        else:
            res["T8_noprofile"].append(r)
    secs = [r.get("check_secs") for k in ("T1_LING", "T2_controls", "T3_T5_anchors")
            for r in res[k] if r.get("check_secs")]
    secs += [r["shorted_input_block"]["check_secs"] for r in res["T3_T5_anchors"]
             if r.get("shorted_input_block")]
    res["T6_cost"] = {"n": len(secs), "median_s": statistics.median(secs) if secs else None,
                      "max_s": max(secs) if secs else None,
                      "note": "one behavioural check = 2 op-only ngspice decks (P0, P3)"}
    s = {"T1_all_LING_rejected": all(r.get("rl_v1_1_reject") for r in res["T1_LING"]),
         "T1_prefilter_rejects": sum(1 for r in res["T1_LING"] if not r["prefilter"]["pass"]),
         "T1_behavioural_fails": sum(1 for r in res["T1_LING"] if not r["behavioural"]["pass"]),
         "T2_controls_pass": all(r["prefilter"]["pass"] and r["behavioural"]["pass"]
                                 for r in res["T2_controls"]),
         "T3_anchors_pass": all(r["prefilter"]["pass"] and r["behavioural"]["pass"]
                                for r in res["T3_T5_anchors"]),
         "T4_shunt_L_not_prefiltered": (res["T4_synth_shunt"] or {}).get("prefilter", {}).get("pass"),
         "T4_shunt_L_behavioural_pass": ((res["T4_synth_shunt"] or {}).get("behavioural") or {}).get("pass"),
         "T5_shorted_prefilter_fail": sum(1 for r in res["T3_T5_anchors"]
                                          if r["shorted_input_block"]["prefilter"]["pass"] is False),
         "T5_shorted_behavioural_fail": sum(1 for r in res["T3_T5_anchors"]
                                            if not r["shorted_input_block"]["behavioural"]["pass"]),
         "T7_derived_equal_fresh": [r.get("derived_equals_fresh_rl_v1_1") for r in res["T7_T8_rows"]
                                    if r.get("derivable")],
         "T7_resized_equal_v1_plus_port_dc": [r.get("resized_same_as_rl_v1_plus_port_dc")
                                              for r in res["T7_T8_rows"] if r.get("derivable") is False],
         "T8_rl_v1_byte_identical": [r.get("rl_v1_byte_identical") for r in res["T7_T8_rows"]],
         "T8_noprofile_byte_identical": [r.get("byte_identical") for r in res["T8_noprofile"]],
         "errors": [r for k, v in res.items() if isinstance(v, list) for r in v if r.get("error")]}
    res["summary"] = s
    with open(f"{OUT}/results.json", "w") as fh:
        json.dump(res, fh, indent=1, default=repr)
    print(json.dumps(s, indent=1, default=repr))


if __name__ == "__main__":
    main()
