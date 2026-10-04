#!/usr/bin/env python
"""Tests of verifier rl-v1.2 / rl-v1.2-rl (PREREG-BENCH-V2 AMENDMENT 3) ->
amend3/test_rl_v12.json. Read-only w.r.t. the bench-v2 run and the EX record
(EX raw per-design records: /tmp/cr-7cd7ffc3-ex, see EX/README "Files").

  T0 static: kick_deck == r4_sim.tran_deck(r50/r50, 600 ns, 1 uA) text-identical;
     cp_ideal_body == EX resize_cp1.tb(body, "io") text-identical
  T1 byte-identity: rl-v1.1 and rl-v1 re-runs of recorded bench-v2 rows == the
     recorded result; no profile: HEAD module vs this module, same call
  T2 rl-v1.2 == EX's validated G-CP1io re-size (resize_cp1.py, D9): same
     feasible + identical winner metrics on 6 recorded D9 cases
  T3 C-cp1 instances (deterministic sample outside the D9 set): the rl-v1.1
     winner in the rl-v1.2 bench (no re-size) + a rl-v1.2 re-size (recovery)
  T4 library anchors: rl-v1.1 winner (captured) re-checked in the rl-v1.2 bench,
     then re-sized under rl-v1.2-rl (rl-v1.2 verdict + kick); one anchor also
     under plain rl-v1.2 (== rl-v1.2-rl minus the kick)
  T5 C-osc50 (6): recorded winner -> kick in the as-is bench (== EX R-b amps) and
     in the rl-v1.2 bench (FAIL expected) + rl-v1.2 bench metrics; re-size under
     rl-v1.2-rl
  T6 clean EX designs (no material R-a/R-b/R-c finding): re-size under rl-v1.2-rl
usage: envrun.sh python test_rl_v12.py [--procs 8]
"""
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop",
           REPO + "/kaggle/campaigns/bench-v2", REPO + "/kaggle/campaigns/rl-readiness/R4"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_anchor_prep as PREP  # noqa: E402
import size as SZ  # noqa: E402
import null_sizer as NS  # noqa: E402

CAMP = f"{REPO}/kaggle/campaigns/bench-v2"
RUN = f"{CAMP}/run"
OUT = f"{CAMP}/amend3"
EXR = "/tmp/cr-7cd7ffc3-ex"
EXD = f"{REPO}/kaggle/campaigns/adversarial-v0/EX"
PDK, BUDGET = "bptm45", 2500
ANCHORS = {"a1": "lna-a1-inddegen-cascode", "a2": "lna-a2-current-reuse",
           "a3": "lna-a3-shunt-feedback", "a4": "lna-a4-twostage",
           "a5": "lna-a5-commongate"}
PROBE_NB = f"{RUN}/specs/probe-amd1-nb090-gain.yaml"
PROBE_WB = f"{RUN}/specs/probe-amd1-wb0530-noise.yaml"
ROWS = {"rl-v1.1 A1 feasible (v2b-wb1020-noise-177 s1)": "6743670f379ab64daa9a",
        "rl-v1.1 F1 infeasible (v2b-wb1020-noise-177 a2 s1)": "f04ef0a4a391e4b0aaee",
        "rl-v1.1 F1 in-process topo reject (v2b-wb1020-noise-177 a1 s1)": "3ab4689e39617fc21b28",
        "rl-v1 cal anchor feasible": "8d792c772de4114b7337"}
D9 = ["v2b-wb0530-noise-166", "t2-nb090-noise-0335", "t2-nb240-power-0227",
      "t2-wb0824-noise-0061", "t2-nb158-gain-0093", "t2-wb1020-gain-0043"]
OSC50 = ["S014", "G018-01", "G018-09", "G027-03", "G036-00", "G047-06"]
N_CP1 = 12
N_CLEAN = 3


def norm(x):
    """minus the one wall-clock field stab_inloop.wide_secs (bench-v2 D30)."""
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


def ex_raw(did):
    if did.startswith("S"):
        p = f"{EXR}/raw/seeds/{did}.json"
    elif did.startswith("E"):
        p = f"{EXR}/raw/ext/{did}.json"
    elif did.startswith("I"):
        p = f"{EXR}/raw/impact/{did}.json"
    else:
        p = f"{EXR}/ex-jobs/{did}.out.json"
    return json.load(open(p))


def sized_capture(tokens, spec_path, profile, seed=1, budget=BUDGET):
    """smoke_run verbatim + read-only capture of the PREPARED body (before any
    rl-v1.2 rewrite) and the final winner's decoded values."""
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
        res = PREP.smoke_run(list(tokens), spec_path, int(seed), budget, PDK, profile=profile)
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


def bench_v12_check(spec_path, body, params):
    """the recorded/captured winner (NO re-size) judged in the rl-v1.2 bench: spec
    metrics + wide mu (rl window) on cp_ideal_body(body); port DC unchanged (DC)."""
    spec = SZ._spec_for_sizing(spec_path, nf_gate=None, pdk=PDK)
    b, _ = PREP.cp_ideal_body(body)
    old = os.environ.get("STAB_WIDE_WINDOW")
    os.environ["STAB_WIDE_WINDOW"] = PREP.VERIFIER_PROFILES["rl-v1.2"]["STAB_WIDE_WINDOW"]
    try:
        m = SZ.eval_metrics(b, params, spec)
        feas, viol = spec.feasible(m) if m else (False, {})
        st, ok = PREP.wide_stability(spec, b, params)
    finally:
        if old is None:
            os.environ.pop("STAB_WIDE_WINDOW", None)
        else:
            os.environ["STAB_WIDE_WINDOW"] = old
    nv = {k: round(v, 4) for k, v in (viol or {}).items() if v}
    return {"pass": bool(feas and ok), "spec_feasible": bool(feas), "mu_wide": (st or {}).get("mu_min"),
            "violations_norm": nv, "worst_violation": max(nv.values()) if nv else 0.0}


def res_summary(r):
    r = r or {}
    k = r.get("kick") or {}
    return {"feasible": r.get("feasible"), "infeasible_reason": r.get("infeasible_reason"),
            "n_evals": r.get("n_evals"), "mu_min_wide": r.get("mu_min_wide"),
            "port_dc_pass": (r.get("port_dc") or {}).get("pass") if r.get("port_dc") else None,
            "cp_ideal": r.get("cp_ideal"),
            "kick": ({x: k.get(x) for x in ("pass", "verdict", "growing", "secs", "error")}
                     | {"lout": (k.get("amp") or {}).get("lout"),
                        "mout": (k.get("amp") or {}).get("mout")}) if r.get("kick") else r.get("kick"),
            "verifier_profile": (r.get("verifier") or {}).get("profile"),
            "verifier_flags_ext": {f: (r.get("verifier") or {}).get("flags", {}).get(f)
                                   for f in PREP.VERIFIER_FLAGS_EXT}}


def v12_feasible_before_kick(r):
    """rl-v1.2 verdict inside an rl-v1.2-rl result: the kick only runs on an
    otherwise feasible winner and is the only extra gate."""
    if not r:
        return False
    if r.get("kick") is not None:
        return True
    return bool(r.get("feasible"))


# ------------------------------------------------------------------ cases
def case_static():
    import r4_sim as S
    sys.path.insert(0, EXD)
    import resize_cp1 as RC
    out = []
    for did in OSC50[:2] + ["S076", "I010"]:
        r = ex_raw(did)
        d1 = S.tran_deck(r["body"], r["params"], term_src="r50", term_load="r50",
                         tstop=600e-9, kick=1e-6)
        out.append({"id": did, "kick_deck_identical": d1 == PREP.kick_deck(r["body"], r["params"]),
                    "cp_ideal_identical_to_EX_io": RC.tb(r["body"], "io")
                    == PREP.cp_ideal_body(r["body"])[0]})
    return {"case": "static", "rows": out}


def recorded_row(jid):
    for ln in open(f"{RUN}/results.jsonl"):
        if jid in ln[:40]:
            r = json.loads(ln)
            if r["jid"] == jid:
                return r
    raise KeyError(jid)


def row_tokens(r):
    import bv2
    m = r.get("meta") or {}
    if r["kind"] in ("cal", "F1", "T-F1"):
        return anchor_tokens(m["anchor"])
    if r["kind"] in ("A1", "A2", "A3"):
        d = f"{RUN}/cells/{m['cell']}/witness"
        for p in (f"{d}/witness.tokens.json", f"{d}/original/witness.tokens.json"):
            if os.path.exists(p):
                t = json.load(open(p))
                if bv2.job_id(t, f"{REPO}/{r['spec']}", r["seed"], r["budget"],
                              r.get("profile")) == r["jid"]:
                    return t
    raise KeyError(r["kind"])


def case_row(key, jid):
    r = recorded_row(jid)
    toks = row_tokens(r)
    spec = f"{REPO}/{r['spec']}"
    prof = r.get("profile") or "rl-v1"
    t = time.time()
    x = PREP.smoke_run(list(toks), spec, r["seed"], r["budget"], PDK, profile=prof)
    return {"case": key, "jid": jid, "profile": prof, "kind": r["kind"],
            "recorded_feasible": (r["res"] or {}).get("feasible"),
            "byte_identical": jd(x) == jd(r["res"]), "diff_keys": diff_keys(x, r["res"]),
            "has_v12_flags": any(f in ((x or {}).get("verifier") or {}).get("flags", {})
                                 for f in ("VERIFY_CP_IDEAL", "VERIFY_KICK")),
            "secs": round(time.time() - t, 1)}


def case_noprofile(a):
    src = subprocess.run(["git", "-C", REPO, "show", "HEAD:kaggle/bench_anchor_prep.py"],
                         capture_output=True, text=True, check=True).stdout
    p = f"/tmp/cr-a3/bap_head_{os.getpid()}.py"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(src)
    sp = importlib.util.spec_from_file_location("bap_head", p)
    old = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(old)
    for k in ("VERIFIER_PROFILE",) + PREP.VERIFIER_FLAGS + PREP.VERIFIER_FLAGS_EXT:
        assert k not in os.environ, k
    toks = anchor_tokens(a)
    t = time.time()
    r_old = old.smoke_run(list(toks), PROBE_NB, 1, BUDGET, PDK)
    r_new = PREP.smoke_run(list(toks), PROBE_NB, 1, BUDGET, PDK)
    return {"case": f"no profile, anchor {a} @ probe-amd1-nb090-gain s1",
            "byte_identical": jd(r_old) == jd(r_new), "has_verifier_key": "verifier" in (r_new or {}),
            "secs": round(time.time() - t, 1)}


def case_d9(task):
    rec = json.load(open(f"{EXR}/raw/resize/{task}.io.json"))
    src = next(ln.split("\t")[1].split()[-2] for ln in open(f"{EXR}/resize_cmds.txt")
               if ln.startswith(f"{EXR}/raw/resize/{task}.io.json"))
    raw = json.load(open(src))
    t = time.time()
    res = PREP.smoke_run(list(raw["tokens"]), f"{REPO}/{rec['spec']}", int(rec["seed"]), BUDGET,
                         PDK, profile="rl-v1.2")
    return {"case": f"D9 {task} ({rec['id']})", "ex_feasible": rec["feasible"],
            "v12_feasible": (res or {}).get("feasible"),
            "same_feasible": bool((res or {}).get("feasible")) == bool(rec["feasible"]),
            "metrics_identical": jd((res or {}).get("metrics")) == jd(rec.get("metrics")),
            "mu_wide_identical": (res or {}).get("mu_min_wide") == rec.get("mu_min_wide"),
            "summary": res_summary(res), "secs": round(time.time() - t, 1)}


def case_cp1(did):
    raw = ex_raw(did)
    spec = f"{REPO}/{raw['spec']}"
    chk = bench_v12_check(spec, raw["body"], raw["params"])
    t = time.time()
    res = PREP.smoke_run(list(raw["tokens"]), spec, int(raw.get("seed", 1)), BUDGET, PDK,
                         profile="rl-v1.2")
    return {"case": f"C-cp1 {did}", "spec": raw["spec"], "seed": raw.get("seed", 1),
            "rl_v1_1_winner_in_v12_bench": chk,
            "v12_resize": res_summary(res), "resize_secs": round(time.time() - t, 1)}


def case_anchor(a, probe):
    toks = anchor_tokens(a)
    r11, body, params, s11 = sized_capture(toks, probe, "rl-v1.1")
    out = {"case": f"anchor {a} @ {os.path.basename(probe)} s1", "rl_v1_1": res_summary(r11),
           "rl_v1_1_secs": s11}
    if r11 and params:
        out["rl_v1_1_winner_in_v12_bench"] = bench_v12_check(probe, body, params)
    t = time.time()
    rr = PREP.smoke_run(list(toks), probe, 1, BUDGET, PDK, profile="rl-v1.2-rl")
    out["rl_v1_2_rl"] = res_summary(rr)
    out["rl_v1_2_verdict"] = v12_feasible_before_kick(rr)
    out["rl_v1_2_rl_secs"] = round(time.time() - t, 1)
    out["rl_v1_1_feasible"] = bool((r11 or {}).get("feasible"))
    if a == "a3" and probe == PROBE_NB:
        t = time.time()
        r12 = PREP.smoke_run(list(toks), probe, 1, BUDGET, PDK, profile="rl-v1.2")
        out["rl_v1_2_secs"] = round(time.time() - t, 1)
        a_ = {k: v for k, v in (r12 or {}).items() if k != "verifier"}
        b_ = {k: v for k, v in (rr or {}).items() if k not in ("verifier", "kick")}
        if rr and rr.get("kick") and not rr["kick"]["pass"]:
            b_.pop("feasible", None)
            b_.pop("infeasible_reason", None)
            a_.pop("feasible", None)
        out["v12_equals_v12rl_minus_kick"] = jd(a_) == jd(b_)
        out["v12_vs_v12rl_diff"] = diff_keys(a_, b_)
    return out


def case_osc50(did):
    raw = ex_raw(did)
    spec_path = f"{REPO}/{raw['spec']}"
    spec = SZ._spec_for_sizing(spec_path, nf_gate=None, pdk=PDK)
    k0 = PREP.kick_check(spec, raw["body"], raw["params"])
    rb = (((raw.get("checks") or {}).get("Rb") or {}).get("rows") or {}).get("r50/r50") or {}
    b12, _ = PREP.cp_ideal_body(raw["body"])
    k12 = PREP.kick_check(spec, b12, raw["params"])
    chk = bench_v12_check(spec_path, raw["body"], raw["params"])
    t = time.time()
    rr = PREP.smoke_run(list(raw["tokens"]), spec_path, int(raw.get("seed", 1)), BUDGET, PDK,
                        profile="rl-v1.2-rl")
    return {"case": f"C-osc50 {did}",
            "kick_as_is_bench": {k: k0[k] for k in ("pass", "verdict", "growing", "secs")},
            "kick_as_is_amp_equals_EX_Rb_small": (k0["amp"] == rb.get("small_amp")) if rb.get("small_amp") else None,
            "kick_v12_bench": {k: k12[k] for k in ("pass", "verdict", "growing", "secs")}
            | {"lout": (k12["amp"] or {}).get("lout"), "mout": (k12["amp"] or {}).get("mout")},
            "recorded_winner_in_v12_bench": chk,
            "rl_v1_2_rl_resize": res_summary(rr), "rl_v1_2_verdict_resize": v12_feasible_before_kick(rr),
            "resize_secs": round(time.time() - t, 1)}


def case_clean(did):
    raw = ex_raw(did)
    spec_path = f"{REPO}/{raw['spec']}"
    t = time.time()
    rr = PREP.smoke_run(list(raw["tokens"]), spec_path, int(raw.get("seed", 1)), BUDGET, PDK,
                        profile="rl-v1.2-rl")
    return {"case": f"clean {did}", "spec": raw["spec"], "rl_v1_2_rl": res_summary(rr),
            "rl_v1_2_verdict": v12_feasible_before_kick(rr), "secs": round(time.time() - t, 1)}


def run_case(spec):
    name, args = spec
    t = time.time()
    try:
        r = globals()[name](*args)
    except Exception:                                            # noqa: BLE001
        import traceback
        r = {"case": f"{name}{args}", "error": traceback.format_exc()[-2500:]}
    r["wall_secs"] = round(time.time() - t, 1)
    print(f"done {name}{args} {r['wall_secs']} s", flush=True)
    return name, args, r


def pick_cp1():
    s = json.load(open(f"{EXD}/results/summary.json"))
    d9 = set(s["G-CP1io_recoverability"]["rows"])
    inst = s["classes"]["C-cp1"]["instances"]
    out = []
    for did in sorted(inst, key=lambda d: hashlib.sha1(f"amend3-T3|{d}".encode()).hexdigest()):
        try:
            raw = ex_raw(did)
        except Exception:                                        # noqa: BLE001
            continue
        name = ((raw.get("meta") or {}).get("task") or (raw.get("meta") or {}).get("cell"))
        if name in d9 or not raw.get("params"):
            continue
        out.append(did)
        if len(out) >= N_CP1:
            break
    return out


def pick_clean():
    s = json.load(open(f"{EXD}/results/summary.json"))
    bad = set()
    for c in s["classes"].values():
        bad |= set(c.get("instances") or [])
    out = []
    for did in sorted((f"S{i:03d}" for i in range(182)),
                      key=lambda d: hashlib.sha1(f"amend3-T6|{d}".encode()).hexdigest()):
        if did in bad:
            continue
        try:
            raw = ex_raw(did)
        except Exception:                                        # noqa: BLE001
            continue
        sm = raw.get("summary") or {}
        if raw.get("verifier_pass") and not sm.get("material") and \
                not (sm.get("Rb") or {}).get("linear_osc"):
            out.append(did)
        if len(out) >= N_CLEAN:
            break
    return out


def main_t4b(procs):
    """T4b (added after the first pass: no anchor is rl-v1.1-feasible at the
    floor-tightened probe-amd1 specs, so T4 cannot show a passing anchor winner):
    the same anchor case at the LOOSE probes probe-nb090-gain (all 5 anchors) and
    probe-wb1020-noise (a2/a3/a5). Merged into test_rl_v12.json."""
    nb, wb = f"{RUN}/specs/probe-nb090-gain.yaml", f"{RUN}/specs/probe-wb1020-noise.yaml"
    jobs = ([("case_anchor", (a, nb)) for a in ANCHORS]
            + [("case_anchor", (a, wb)) for a in ("a2", "a3", "a5")])
    with mp.Pool(procs) as pool:
        rows = pool.map(run_case, jobs, chunksize=1)
    p = f"{OUT}/test_rl_v12.json"
    res = json.load(open(p))
    res["T4b_anchors_loose"] = [r for _n, _a, r in rows]
    res["summary"]["T4b_anchors_loose"] = [
        [r["case"], r["rl_v1_1_feasible"], (r.get("rl_v1_1_winner_in_v12_bench") or {}).get("pass"),
         r["rl_v1_2_verdict"], ((r["rl_v1_2_rl"].get("kick") or {}).get("pass"))]
        for r in res["T4b_anchors_loose"] if "error" not in r]
    res["summary"]["T4b_errors"] = [r["case"] for r in res["T4b_anchors_loose"] if "error" in r]
    json.dump(res, open(p + ".tmp", "w"), indent=1, default=repr)
    os.replace(p + ".tmp", p)
    print(json.dumps(res["summary"]["T4b_anchors_loose"], indent=1))


def main():
    procs = 8
    if "--procs" in sys.argv:
        procs = int(sys.argv[sys.argv.index("--procs") + 1])
    if "--t4b" in sys.argv:
        return main_t4b(procs)
    cp1, clean = pick_cp1(), pick_clean()
    jobs = ([("case_static", ())]
            + [("case_row", (k, j)) for k, j in ROWS.items()]
            + [("case_noprofile", ("a2",))]
            + [("case_d9", (t,)) for t in D9]
            + [("case_cp1", (d,)) for d in cp1]
            + [("case_anchor", (a, PROBE_NB)) for a in ANCHORS]
            + [("case_anchor", (a, PROBE_WB)) for a in ("a2", "a3", "a5")]
            + [("case_osc50", (d,)) for d in OSC50]
            + [("case_clean", (d,)) for d in clean])
    t0 = time.time()
    with mp.Pool(procs) as pool:
        rows = pool.map(run_case, jobs, chunksize=1)
    res = {"T0_static": None, "T1_rows": [], "T1_noprofile": [], "T2_D9": [], "T3_cp1": [],
           "T4_anchors": [], "T5_osc50": [], "T6_clean": []}
    key = {"case_static": "T0_static", "case_row": "T1_rows", "case_noprofile": "T1_noprofile",
           "case_d9": "T2_D9", "case_cp1": "T3_cp1", "case_anchor": "T4_anchors",
           "case_osc50": "T5_osc50", "case_clean": "T6_clean"}
    for name, _a, r in rows:
        if key[name] == "T0_static":
            res["T0_static"] = r
        else:
            res[key[name]].append(r)
    g = lambda lst, f: [f(r) for r in lst if "error" not in r]   # noqa: E731
    kick_secs = [x for r in res["T5_osc50"] if "error" not in r
                 for x in (r["kick_as_is_bench"]["secs"], r["kick_v12_bench"]["secs"])]
    kick_secs += [((r.get("rl_v1_2_rl") or {}).get("kick") or {}).get("secs")
                  for r in res["T4_anchors"] + res["T6_clean"] if "error" not in r]
    kick_secs = sorted(x for x in kick_secs if isinstance(x, (int, float)))
    pairs = [(r["rl_v1_1_secs"], r["rl_v1_2_rl_secs"] - (((r.get("rl_v1_2_rl") or {}).get("kick") or {}).get("secs") or 0))
             for r in res["T4_anchors"] if "error" not in r]
    s = {
        "T0_static_all": all(x["kick_deck_identical"] and x["cp_ideal_identical_to_EX_io"]
                             for x in (res["T0_static"] or {}).get("rows", [])),
        "T1_byte_identical": g(res["T1_rows"], lambda r: [r["profile"], r["byte_identical"], r["has_v12_flags"]]),
        "T1_noprofile_byte_identical": g(res["T1_noprofile"], lambda r: [r["byte_identical"], r["has_verifier_key"]]),
        "T2_D9_same_feasible": g(res["T2_D9"], lambda r: r["same_feasible"]),
        "T2_D9_metrics_identical": g(res["T2_D9"], lambda r: r["metrics_identical"]),
        "T3_cp1_n": len(res["T3_cp1"]),
        "T3_cp1_rl_v1_1_winner_fails_v12_bench": sum(1 for r in res["T3_cp1"] if "error" not in r
                                                     and not r["rl_v1_1_winner_in_v12_bench"]["pass"]),
        "T3_cp1_v12_resize_feasible": sum(1 for r in res["T3_cp1"] if "error" not in r
                                          and r["v12_resize"]["feasible"]),
        "T4_anchors": g(res["T4_anchors"], lambda r: [r["case"], r["rl_v1_1_feasible"],
                                                      (r.get("rl_v1_1_winner_in_v12_bench") or {}).get("pass"),
                                                      r["rl_v1_2_verdict"],
                                                      ((r["rl_v1_2_rl"].get("kick") or {}).get("pass"))]),
        "T4_v12_equals_v12rl_minus_kick": g(res["T4_anchors"], lambda r: r.get("v12_equals_v12rl_minus_kick")),
        "T5_osc50_kick_fail_v12_bench_recorded_winner": sum(
            1 for r in res["T5_osc50"] if "error" not in r and not r["kick_v12_bench"]["pass"]),
        "T5_osc50_recorded_winner_passes_v12_bench": sum(
            1 for r in res["T5_osc50"] if "error" not in r and r["recorded_winner_in_v12_bench"]["pass"]),
        "T5_osc50_kick_amp_equals_EX": g(res["T5_osc50"], lambda r: r["kick_as_is_amp_equals_EX_Rb_small"]),
        "T5_osc50_resize": g(res["T5_osc50"], lambda r: [r["case"], r["rl_v1_2_verdict_resize"],
                                                         (r["rl_v1_2_rl_resize"].get("kick") or {}).get("pass"),
                                                         r["rl_v1_2_rl_resize"]["feasible"]]),
        "T6_clean": g(res["T6_clean"], lambda r: [r["case"], r["rl_v1_2_verdict"],
                                                  (r["rl_v1_2_rl"].get("kick") or {}).get("pass")]),
        "cost_kick_secs": {"n": len(kick_secs), "median": kick_secs[len(kick_secs) // 2] if kick_secs else None,
                           "max": kick_secs[-1] if kick_secs else None},
        "cost_sizing_secs_rl_v1_1_vs_rl_v1_2": pairs,
        "errors": [r["case"] for k in res if isinstance(res[k], list) for r in res[k] if "error" in r],
        "wall_min": round((time.time() - t0) / 60, 1)}
    res["summary"] = s
    tmp = f"{OUT}/test_rl_v12.json.tmp"
    json.dump(res, open(tmp, "w"), indent=1, default=repr)
    os.replace(tmp, f"{OUT}/test_rl_v12.json")
    print(json.dumps(s, indent=1, default=repr))


if __name__ == "__main__":
    main()
