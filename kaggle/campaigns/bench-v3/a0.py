#!/usr/bin/env python
"""bench-v3 phase A0 -- yield probe (kaggle/PREREG-BENCH-V3.md, frozen f56d45e11, sections 2 and 8).

  a0.py nominate
        Per eligible held-out task (pilot-v0 tiers.json: every non-T1 item = the T2/T3 tasks
        with a full seed-1 single-edit enumeration of the shown anchor), from CACHED rl-v1.2
        rows at the ORIGINAL spec (0 sims):
          designs d = library a1-a5 (seed 1) U every round-trip-valid single edit of the shown
                      anchor (pv0.f2_cands == bv2 f2space_build), seed 1; only SIZED rows
                      (n_evals > 0, metrics present) carry margins;
          a(d) = min normalized margin over the non-flavor constraints (MS._margins via
                 bv2.worst_margin) and mu_wide - 1;  b(d) = the flavor constraint's margin;
          delta_min = 0.05 + max{ b(d) : a(d) > -0.05 };
          witness (planted, its seed-1 rl-v1.2 row at the task spec): headroom iff
                 a_w >= 0.02 and b_w - 0.02 > delta_min;  delta* = (delta_min + b_w - 0.02)/2;
          stretched spec = original spec with ONLY the flavor limit moved by
                 delta* x Spec._scale(original flavor limit), written to a0/specs/ (sha recorded);
          references = top 3 designs by w_delta*(d) = min(a(d), b(d) - delta*).
        -> a0/nominate.json
  a0.py confirm [nproc<=8]
        sizes the witness + the 3 references of every nominated task at its stretched spec
        (seed 1, rl-v1.2, 2500 evals, bptm45) through the bv2 worker (pilot-v1 pv1_score path:
        bench_anchor_prep.smoke_run(tokens, spec, 1, 2500, "bptm45", profile="rl-v1.2")),
        scheduled by baselines-v1 ga.Sched (box-wide cap 8 sizing workers incl. other jobs'
        bv2.py workers counted from /proc, 4 while load1 > 22; D32 disk robustness; exact-key
        resume through a0/results.jsonl + read-only reuse of earlier rl-v1.2 rows).
        -> a0/results.jsonl
  a0.py summarize
        -> a0/a0-tasks.jsonl, a0/a0-summary.json, a0/a0-tables.md (go/no-go per section 8)

  --diag (any command)
        NOT pre-registered diagnostic (README D-A8): same computation with the a_w >= 0.02 condition
        dropped (nominate iff the witness is seed-1 feasible at the original spec and
        b_w - 0.02 > delta_min); outputs in a0/diag/, spec suffix -a0d; no verdict.

Run via the env wrapper (sources crenv, cd's to the worktree). Temp files: A0_TMPDIR (default
~/.claude/jobs/7cd7ffc3/tmp/a0/tmp), never /tmp. Witness netlists/tokens are EVAL-ONLY: they are
read from their existing files at run time and never written by this script (only token hashes);
worker job files holding tokens live in the temp dir and are deleted after each call.
"""
import hashlib
import json
import math
import os
import signal
import sys
import time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "a0")
SPECS = os.path.join(OUT, "specs")
DIAG = False           # --diag: NOT pre-registered diagnostic (README D-A8), outputs in a0/diag/
SUFFIX = "-a0s"
_T = os.environ.get("A0_TMPDIR") or os.path.expanduser("~/.claude/jobs/7cd7ffc3/tmp/a0/tmp")
os.makedirs(_T, exist_ok=True)
os.environ["GA_TMPDIR"] = _T          # ga.py: RAW worker dir + TMPDIR (ngspice scratch) under _T
sys.path.insert(0, os.path.join(REPO, "kaggle", "campaigns", "baselines-v1"))
import ga  # noqa: E402  (imports pv0, p1_score, bv2; read-only reuse)

pv0, PS, B = ga.pv0, ga.PS, ga.B
PROF = "rl-v1.2"
PREREG = "kaggle/PREREG-BENCH-V3.md (f56d45e11) sections 2 + 8"
EVAL = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0", "eval")
PV0_RUN = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0", "run")
A3RUN = os.path.join(pv0.A3, "run")
NEAR = 0.05            # section 8: reference designs must fail the stretch by >= 0.05
WCUSH = 0.02           # section 8: witness cushion
FLAVOR_METRIC = {("narrowband", "noise"): "nf_db", ("wideband", "noise"): "nf_max_db",
                 ("narrowband", "gain"): "s21_db", ("wideband", "gain"): "s21_db",
                 ("narrowband", "power"): "idd_ma", ("wideband", "power"): "idd_ma"}
NREF = 3


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def rel(p):
    return os.path.relpath(p, REPO)


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load_yaml(p):
    import yaml
    return yaml.safe_load(open(p))


# ------------------------------------------------------------------ margins
def ab(spec_path, flavor, metrics, mu_wide):
    """(a, b, per-constraint margins): a = min margin over non-flavor constraints and
    mu_wide - 1 (MS._margins definitions via bv2.worst_margin), b = flavor margin."""
    rows, _w = B.worst_margin(spec_path, metrics or {})
    mg = OrderedDict()
    missing = []
    for name, ach, _c, m, present in rows:
        if not present or m is None:
            missing.append(name)
            continue
        mg[name] = m
    b = mg.get(flavor)
    others = [v for k, v in mg.items() if k != flavor]
    if isinstance(mu_wide, (int, float)):
        others.append(mu_wide - 1.0)
        mg["mu_wide-1"] = mu_wide - 1.0
    a = min(others) if others else None
    return a, b, mg, missing


def flavor_of(task, spec_path, family, bt):
    """flavor metric = FLAVOR_METRIC[(band type, family flavor)]; cross-checked against the
    spec's top-weight objective (bv2.make_spec puts weight 1.0 on the flavor metric)."""
    fl = family.split("-")[1]
    m = FLAVOR_METRIC[(bt, fl)]
    d = load_yaml(spec_path)
    top = max(d["objectives"], key=lambda o: o["weight"])
    assert top["metric"] == m and top["weight"] == 1.0, (task, top, m)
    c = d["constraints"][m]
    side = "max" if "max" in c else "min"
    assert set(c) == {side}, (task, c)
    return fl, m, side, float(c[side])


# ------------------------------------------------------------------ inputs
def eligible_tasks():
    T = json.load(open(os.path.join(EVAL, "tiers.json")))
    out = OrderedDict()
    for n in sorted(T["items"]):
        it = T["items"][n]
        if it["tier"] == "T1":
            continue
        out[n] = it
    return T, out


def spec_for(task):
    pr = json.load(open(os.path.join(EVAL, "prompts", task + ".json")))
    sp = os.path.join(EVAL, pr["spec_file"])
    assert B.spec_sha(sp) == pr["spec_sha"], ("spec drift", task)
    return sp, pr


def witness_tokens(task, it):
    import proposal as P
    wf = os.path.join(REPO, it["witness"]["file"])
    rt = P.round_trip(open(wf).read())
    assert rt.get("ok"), (task, rt.get("error"))
    tk = rt["tokens"]
    assert B.tokhash(tk) == it["witness"]["tok"], (task, "witness token hash mismatch")
    return tk


def recorded_witness_jid(task, it):
    """the recorded seed-1 rl-v1.2 witness jid (train_amend3 'witness' / strict cell A1)."""
    if it.get("source") == "bench-v2 strict cell":
        c = B.load_jsonl_last(os.path.join(A3RUN, "cells_amend3.jsonl"), "name")[task]
        runs = c["stages"]["A1"]["runs"]
    else:
        runs = B.load_jsonl_last(os.path.join(A3RUN, "train_amend3.jsonl"), "name")[task]["witness"]
    s1 = [r for r in runs if r["seed"] == 1]
    return s1[0]["jid"] if s1 else None, [(r["seed"], r["feasible"]) for r in runs]


# ------------------------------------------------------------------ nominate
def nominate():
    os.makedirs(SPECS, exist_ok=True)
    T, el = eligible_tasks()
    anch = B.anchor_data()
    f2 = pv0.load_f2space(PV0_RUN, anch)          # read-only (file exists)
    cache = PS.caches()                           # raw rl-v1.2 rows: pilot-v0 + AMENDMENT-3
    tasks = OrderedDict()
    for task, it in el.items():
        sp, pr = spec_for(task)
        bt, family, shown = it["band_type"], it["family"], it["shown_anchor"]
        assert pr["shown_anchor"] == shown
        fl, fm, side, L = flavor_of(task, sp, family, bt)
        designs, seen, cnt = [], set(), Counter()
        cand = [("lib:" + an, A["tokens"]) for an, A in anch.items()] + \
               [("edit:%s:%d:%s" % (shown, x["idx"], x["desc"]), x["tokens"])
                for x in f2[shown] if x["rt_ok"]]
        for did, tk in cand:
            h = B.tokhash(tk)
            if h in seen:
                cnt["dup_tokens"] += 1
                continue
            seen.add(h)
            jid = B.job_id(tk, sp, 1, B.BUDGET, PROF)
            r = cache.get(jid)
            if r is None:
                cnt["missing_row"] += 1
                designs.append({"id": did, "tok": h, "jid": jid, "status": "missing"})
                continue
            s = PS.summ(r)
            if not s["n_evals"]:
                cnt["prereject"] += 1
                continue
            if not s["metrics"]:
                cnt["no_metrics"] += 1
                designs.append({"id": did, "tok": h, "jid": jid, "status": "no_metrics"})
                continue
            a, b, mg, miss = ab(sp, fm, s["metrics"], s["mu_min_wide"])
            if miss:
                cnt["missing_metric:" + ",".join(miss)] += 1
            if b is None or a is None:
                cnt["no_flavor_margin"] += 1
                designs.append({"id": did, "tok": h, "jid": jid, "status": "no_flavor"})
                continue
            cnt["sized"] += 1
            designs.append({"id": did, "tok": h, "jid": jid, "status": "sized", "a": a, "b": b,
                            "flavor_value": s["metrics"][fm], "feasible": s["feasible"],
                            "port_dc_pass": s["port_dc_pass"], "src": r["_src"],
                            "binding_nonflavor": min((k for k in mg if k != fm), key=lambda k: mg[k])})
        sized = [d for d in designs if d["status"] == "sized"]
        near = [d for d in sized if d["a"] > -NEAR]
        R = max(near, key=lambda d: d["b"]) if near else None
        dmin = NEAR + R["b"] if R else None
        # witness
        wtk = witness_tokens(task, it)
        wjid = B.job_id(wtk, sp, 1, B.BUDGET, PROF)
        rjid, wruns = recorded_witness_jid(task, it)
        wr = cache.get(wjid)
        W = {"tok": it["witness"]["tok"], "jid": wjid, "recorded_seed1_jid": rjid,
             "jid_matches_record": rjid == wjid, "recorded_runs": wruns}
        if wr is None:
            W["status"] = "missing"
        else:
            s = PS.summ(wr)
            a, b, mg, miss = ab(sp, fm, s["metrics"], s["mu_min_wide"]) if s["metrics"] else (None, None, {}, [])
            W.update(status="sized" if s["n_evals"] else "unsized", a=a, b=b,
                     flavor_value=(s["metrics"] or {}).get(fm), feasible=s["feasible"],
                     port_dc_pass=s["port_dc_pass"], margins=mg, src=wr["_src"])
        head = (W.get("a") is not None and W.get("b") is not None and dmin is not None
                and W["a"] >= WCUSH and W["b"] - WCUSH > dmin)
        if DIAG:   # diagnostic: drop the a_w >= 0.02 condition, keep b_w - 0.02 > delta_min (+ witness
            #        feasible at the original spec at seed 1)
            head = bool(W.get("b") is not None and dmin is not None and W.get("feasible")
                        and W["b"] - WCUSH > dmin)
        rec = OrderedDict(task=task, tier=it["tier"], family=family, band_type=bt, shown_anchor=shown,
                          spec=rel(sp), spec_sha=pr["spec_sha"], flavor=fl, flavor_metric=fm,
                          flavor_side=side, flavor_limit=L, flavor_scale=max(abs(L), 1.0),
                          n_designs=len(cand), counts=dict(cnt), n_sized=len(sized), n_near=len(near),
                          R={k: R[k] for k in ("id", "a", "b", "flavor_value", "feasible")} if R else None,
                          delta_min=dmin, witness=W, headroom=bool(head))
        if dmin is None:
            rec["no_headroom_why"] = "no library/single-edit design with a(d) > -0.05 (delta_min undefined)"
        elif not head:
            why = []
            if W.get("a") is None:
                why.append("witness row missing/unsized")
            else:
                if W["a"] < WCUSH:
                    why.append("a_w %.4f < 0.02" % W["a"])
                if not W["b"] - WCUSH > dmin:
                    why.append("b_w - 0.02 = %.4f <= delta_min %.4f" % (W["b"] - WCUSH, dmin))
            rec["no_headroom_why"] = "; ".join(why)
        if head:
            ds = (dmin + W["b"] - WCUSH) / 2.0
            sc = rec["flavor_scale"]
            raw = L - ds * sc if side == "max" else L + ds * sc
            # rounded to 1e-4 in the STRICTER direction (bv2 planted-limit precision): the move is >= delta*
            newL = (math.floor(raw * 1e4 + 1e-9) / 1e4) if side == "max" else (math.ceil(raw * 1e4 - 1e-9) / 1e4)
            d = load_yaml(sp)
            d["constraints"][fm][side] = newL
            d["name"] = task + SUFFIX
            d["description"] = ("bench-v3 A0%s stretch of %s: %s %s %s -> %s (delta* %.4f x scale %.4f)"
                                % (" DIAGNOSTIC" if DIAG else "", task, fm, side, L, newL, ds, sc))
            p = os.path.join(SPECS, task + SUFFIX + ".yaml")
            B.write_spec(p, d)
            for d2 in sized:
                d2["w"] = min(d2["a"], d2["b"] - ds)
            refs = sorted(sized, key=lambda d2: -d2["w"])[:NREF]
            rec.update(delta_star=ds, stretched_limit=newL, stretched_limit_raw=raw,
                       stretched_spec=rel(p), stretched_spec_sha256=sha256_file(p),
                       stretched_spec_bv2_sha=B.spec_sha(p),
                       witness_pred_w=min(W["a"], W["b"] - ds),
                       refs=[{k: d2[k] for k in ("id", "tok", "a", "b", "w", "flavor_value", "feasible",
                                                  "binding_nonflavor")} for d2 in refs])
        rec["designs_top10_by_b_near"] = [{k: d2[k] for k in ("id", "a", "b", "flavor_value")}
                                          for d2 in sorted(near, key=lambda d2: -d2["b"])[:10]]
        tasks[task] = rec
        print("%-24s %s %-11s sized %3d near %3d dmin %s  w a=%s b=%s  headroom=%s %s" % (
            task, it["tier"], fm, len(sized), len(near), "%.4f" % dmin if dmin is not None else "-",
            "%.4f" % W["a"] if W.get("a") is not None else "-",
            "%.4f" % W["b"] if W.get("b") is not None else "-", head,
            ("delta* %.4f L %s -> %s" % (rec["delta_star"], L, rec["stretched_limit"])) if head
            else rec.get("no_headroom_why", "")), flush=True)
    out = OrderedDict(prereg=PREREG, diagnostic_not_preregistered=DIAG, built=now(), verifier=PROF, budget=B.BUDGET, pdk=B.PDK, seed=1,
                      n_eligible=len(tasks), n_nominated=sum(1 for t in tasks.values() if t["headroom"]),
                      tasks=tasks)
    B.atomic_write(os.path.join(OUT, "nominate.json"), json.dumps(out, indent=1, default=repr))
    print("eligible %d, nominated (headroom) %d" % (out["n_eligible"], out["n_nominated"]))


# ------------------------------------------------------------------ confirm
def confirm(nproc):
    nom = json.load(open(os.path.join(OUT, "nominate.json")))["tasks"]
    T, el = eligible_tasks()
    anch = B.anchor_data()
    f2 = pv0.load_f2space(PV0_RUN, anch)
    os.makedirs(ga.RAW, exist_ok=True)
    signal.signal(signal.SIGTERM, ga._term)
    signal.signal(signal.SIGINT, ga._term)
    cache = ga.load_caches()
    S = ga.Sched(OUT, nproc, cache)
    gens = []
    for i, (task, rec) in enumerate(nom.items()):
        if not rec["headroom"]:
            continue
        sp = os.path.join(REPO, rec["stretched_spec"])
        assert sha256_file(sp) == rec["stretched_spec_sha256"], ("stretched spec changed", task)
        items = [("witness", witness_tokens(task, el[task]))]
        shown = rec["shown_anchor"]
        byid = {"lib:" + an: A["tokens"] for an, A in anch.items()}
        byid.update({"edit:%s:%d:%s" % (shown, x["idx"], x["desc"]): x["tokens"] for x in f2[shown] if x["rt_ok"]})
        for k, r in enumerate(rec["refs"]):
            tk = byid[r["id"]]
            assert B.tokhash(tk) == r["tok"]
            items.append(("ref%d" % (k + 1), tk))
        jobs = [{"task": task, "key": key, "seed": 1, "tokens": tk, "spec": sp,
                 "jid": B.job_id(tk, sp, 1, B.BUDGET, PROF)} for key, tk in items]

        def g(jobs=jobs):
            yield jobs
        gens.append([task, g(), i, (lambda: None)])
    print("[a0 confirm %s] %d nominated tasks, %d jobs, cache %d rows, nproc %d" % (
        now(), len(gens), 4 * len(gens), len(cache), S.nproc), flush=True)
    S.drive(gens, "a0")
    print("[a0 confirm %s] done: new sized calls %d, %.2f CPU-h, wall %.1f min" % (
        now(), S.n_new, S.cpu_new / 3600, (time.time() - S.t0) / 60), flush=True)


# ------------------------------------------------------------------ summarize
def summarize():
    nomf = json.load(open(os.path.join(OUT, "nominate.json")))
    nom = nomf["tasks"]
    res = OrderedDict()
    for r in B.read_jsonl(os.path.join(OUT, "results.jsonl")):
        res[(r["task"], r["key"])] = r                      # last row per key wins
    rows = []
    for task, rec in nom.items():
        o = OrderedDict((k, rec.get(k)) for k in (
            "task", "tier", "family", "flavor_metric", "flavor_side", "flavor_limit", "flavor_scale",
            "n_sized", "n_near", "delta_min", "headroom", "no_headroom_why", "delta_star",
            "stretched_limit", "stretched_spec", "stretched_spec_sha256"))
        W = rec["witness"]
        o["a_w"], o["b_w"], o["witness_feasible_orig"] = W.get("a"), W.get("b"), W.get("feasible")
        o["R"] = rec["R"]
        if rec["headroom"]:
            sp = os.path.join(REPO, rec["stretched_spec"])
            conf = OrderedDict()
            for key in ["witness"] + ["ref%d" % (k + 1) for k in range(len(rec["refs"]))]:
                r = res.get((task, key))
                if r is None:
                    conf[key] = None
                    continue
                m = None
                if not r.get("crashed") and r.get("n_evals"):
                    m = pv0.Runner.margin(sp, {"metrics": r.get("metrics") or {},
                                               "mu_min_wide": r.get("mu_min_wide")})
                fv = (r.get("metrics") or {}).get(rec["flavor_metric"])
                a, b = (None, None)
                if r.get("metrics"):
                    a, b, _mg, _ms = ab(sp, rec["flavor_metric"], r["metrics"], r.get("mu_min_wide"))
                conf[key] = {"worst": m, "a": a, "b": b, "flavor_value": fv, "feasible": r.get("feasible"),
                             "port_dc_pass": r.get("port_dc_pass"), "crashed": bool(r.get("crashed")),
                             "secs": r.get("secs"), "source": r.get("source"),
                             "id": rec["refs"][int(key[3:]) - 1]["id"] if key != "witness" else "witness",
                             "pred_w": (rec["refs"][int(key[3:]) - 1]["w"] if key != "witness"
                                        else rec["witness_pred_w"])}
            o["confirm"] = conf
            done = all(v is not None for v in conf.values())
            o["confirm_complete"] = done
            if done:
                wok = conf["witness"]["worst"] is not None and conf["witness"]["worst"] >= 0
                rok = all((v["worst"] is None or v["worst"] < 0) for k, v in conf.items() if k != "witness")
                o["accepted"] = bool(wok and rok)
                o["reject_why"] = None if o["accepted"] else "; ".join(
                    (["witness worst %s < 0" % _f(conf["witness"]["worst"])] if not wok else []) +
                    ["%s worst %s >= 0" % (k, _f(v["worst"])) for k, v in conf.items()
                     if k != "witness" and v["worst"] is not None and v["worst"] >= 0])
                o["flags"] = [k + (" crashed/unsized" if v["worst"] is None else
                                   " margin>=0 but infeasible (port-DC/other)")
                              for k, v in conf.items()
                              if v["worst"] is None or (v["worst"] >= 0 and not v["feasible"])]
            else:
                o["accepted"] = None
        else:
            o["accepted"] = False
        rows.append(o)
    with open(os.path.join(OUT, "a0-tasks.jsonl"), "w") as fh:
        for o in rows:
            fh.write(json.dumps(o, default=repr) + "\n")
    n_el = len(rows)
    nomd = [o for o in rows if o["headroom"]]
    acc = [o for o in rows if o["accepted"]]
    pending = [o["task"] for o in rows if o["accepted"] is None]

    def by(lst, k):
        return dict(sorted(Counter(o[k] for o in lst).items()))
    n_acc = len(acc)
    verdict = ("DIAGNOSTIC ONLY (not pre-registered, README D-A8): %d of %d would-be-nominated tasks "
               "confirmed" % (n_acc, len(nomd)) if DIAG else
               "INCOMPLETE (%d tasks unconfirmed)" % len(pending) if pending else
               "BUILD (>= 15 accepted: build bench-v3 H from them)" if n_acc >= 15 else
               "REPORT (8-14 accepted: report and propose adding T1 tasks, which need their "
               "single-edit enumeration)" if n_acc >= 8 else
               "STOP (< 8 accepted: the stretch form fails here; stop and report)")
    new_rows = [r for r in res.values() if r.get("source") == "sized"]
    cpu = sum(r.get("secs") or 0 for r in new_rows)
    summ = OrderedDict(
        prereg=PREREG, diagnostic_not_preregistered=DIAG, built=now(), verifier=PROF, seed=1, budget=B.BUDGET, pdk=B.PDK,
        n_eligible=n_el, eligible_by_tier=by(rows, "tier"), eligible_by_family=by(rows, "family"),
        n_nominated=len(nomd), nominated_by_tier=by(nomd, "tier"), nominated_by_family=by(nomd, "family"),
        n_accepted=n_acc, accepted_by_tier=by(acc, "tier"), accepted_by_family=by(acc, "family"),
        accepted_tasks=[o["task"] for o in acc], unconfirmed=pending,
        go_no_go_rule=">= 15 accepted => build; 8-14 => report (propose T1 tasks); < 8 => stop",
        verdict=verdict,
        confirmation_calls={"rows": len(res), "new_sized": len(new_rows), "reused": len(res) - len(new_rows),
                            "new_cpu_s": round(cpu, 1), "new_cpu_h": round(cpu / 3600, 3)},
        no_headroom_reasons=dict(Counter(_why_class(o.get("no_headroom_why")) for o in rows
                                         if not o["headroom"])))
    B.atomic_write(os.path.join(OUT, "a0-summary.json"), json.dumps(summ, indent=1, default=repr))
    B.atomic_write(os.path.join(OUT, "a0-tables.md"), tables_md(rows, summ))
    print(json.dumps({k: summ[k] for k in ("n_eligible", "n_nominated", "n_accepted", "accepted_by_tier",
                                           "accepted_by_family", "verdict", "confirmation_calls")}, indent=1))


def _why_class(s):
    if not s:
        return "?"
    if "undefined" in s:
        return "delta_min undefined"
    k = []
    if "a_w" in s:
        k.append("a_w < 0.02")
    if "b_w" in s:
        k.append("b_w - 0.02 <= delta_min")
    if "missing" in s:
        k.append("witness row missing")
    return " & ".join(k)


def _f(x, n=4):
    return "-" if x is None else ("%.*f" % (n, x))


def tables_md(rows, s):
    L = ["# bench-v3 A0 yield probe -- tables" + (
        " -- DIAGNOSTIC (not pre-registered; a_w >= 0.02 dropped; README D-A8)" if DIAG else ""), "",
         "Pre-reg: %s. Verifier %s, seed 1, budget %d, %s. Built %s by `a0.py summarize`." % (
             s["prereg"], s["verifier"], s["budget"], s["pdk"], s["built"]), "",
         "**Verdict: %s** -- eligible %d, nominated (headroom) %d, accepted %d." % (
             s["verdict"], s["n_eligible"], s["n_nominated"], s["n_accepted"]), "",
         "| | eligible | nominated | accepted |", "|---|---|---|---|"]
    for grp, ek, nk, ak in (("tier", "eligible_by_tier", "nominated_by_tier", "accepted_by_tier"),
                            ("family", "eligible_by_family", "nominated_by_family", "accepted_by_family")):
        for k in s[ek]:
            L.append("| %s %s | %d | %d | %d |" % (grp, k, s[ek][k], s[nk].get(k, 0), s[ak].get(k, 0)))
    L += ["", "Confirmation calls: %(rows)d rows (%(new_sized)d newly sized, %(reused)d reused), "
          "new CPU %(new_cpu_h).2f CPU-h." % s["confirmation_calls"], "",
          "No-headroom reasons: " + ", ".join("%s %d" % kv for kv in sorted(s["no_headroom_reasons"].items())), "",
          "## Per task", "",
          "a = min non-flavor margin (incl. mu_wide-1), b = flavor margin, at the ORIGINAL spec (cached seed-1 "
          "rows). delta_min = 0.05 + max{b(d): a(d) > -0.05} over library + single edits. Confirmation = new "
          "seed-1 sizing at the stretched spec: worst normalized margin incl. mu_wide-1 (witness, ref1-3).", "",
          "| task | tier | flavor metric | limit | a_w | b_w | R (id, b) | delta_min | headroom | delta* | "
          "stretched limit | witness worst | ref1 | ref2 | ref3 | accepted |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for o in rows:
        c = o.get("confirm") or {}

        def cw(k):
            v = c.get(k)
            if v is None:
                return "-" if not o["headroom"] else "pending"
            return _f(v["worst"]) + ("" if v["feasible"] or (v["worst"] or -1) < 0 else " (infeas)")
        R = o["R"]
        L.append("| %s | %s | %s %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            o["task"], o["tier"], o["flavor_metric"], o["flavor_side"], o["flavor_limit"], _f(o["a_w"]),
            _f(o["b_w"]), ("%s, %s" % (R["id"].replace("|", "/"), _f(R["b"]))) if R else "-",
            _f(o["delta_min"]), "yes" if o["headroom"] else "no", _f(o["delta_star"]),
            o["stretched_limit"] if o["stretched_limit"] is not None else "-",
            cw("witness"), cw("ref1"), cw("ref2"), cw("ref3"),
            {True: "**yes**", False: "no", None: "pending"}[o["accepted"]]))
    L += ["", "## Nominated tasks: references and confirmation detail", ""]
    for o in rows:
        if not o["headroom"]:
            continue
        L.append("- **%s** (%s, %s; stretched spec `%s`, sha256 `%s`)" % (
            o["task"], o["tier"], o["family"], o["stretched_spec"], o["stretched_spec_sha256"]))
        for k, v in (o.get("confirm") or {}).items():
            if v is None:
                L.append("  - %s: pending" % k)
                continue
            L.append("  - %s `%s`: predicted w %s -> sized worst %s (a %s, b %s, %s %s, feasible %s, port-DC %s, %s)"
                     % (k, v["id"], _f(v["pred_w"]), _f(v["worst"]), _f(v["a"]), _f(v["b"]),
                        o["flavor_metric"], _f(v["flavor_value"]), v["feasible"], v["port_dc_pass"], v["source"]))
        if o.get("reject_why"):
            L.append("  - rejected: " + o["reject_why"])
        if o.get("flags"):
            L.append("  - flags: " + "; ".join(o["flags"]))
    return "\n".join(L) + "\n"


def main():
    a = sys.argv[1:]
    global DIAG, OUT, SPECS, SUFFIX
    if not a:
        sys.exit(__doc__)
    if "--diag" in a:
        a.remove("--diag")
        DIAG, SUFFIX = True, "-a0d"
        OUT = os.path.join(HERE, "a0", "diag")
        SPECS = os.path.join(OUT, "specs")
    if a[0] == "nominate":
        nominate()
    elif a[0] == "confirm":
        confirm(int(a[1]) if len(a) > 1 else 8)
    elif a[0] == "summarize":
        summarize()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
