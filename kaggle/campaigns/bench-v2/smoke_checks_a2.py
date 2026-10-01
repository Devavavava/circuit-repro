#!/usr/bin/env python
"""AMENDMENT-2 smoke checks (smoke/run-amend2, `bv2.py run --mode smoke-a2`) ->
smoke/smoke_checks_a2.json. Run after the smoke finished (and was finalized).

  1. PROFILE   every new sizing row is rl-v1.1 (row profile, res.verifier.profile,
               flags VERIFY_PORT_DC=1 + the rl-v1 flags), phase amendment-2
  2. RESTORE   the 5 restored cells got the intended action (tag / revalidate /
               revive / requeue) and the replant candidate was planted; the
               tagged ones are amend2-port-dc, not selectable, fenced
  3. REVALIDATE nb090-gain-007: every stage run is rl-v1.1; feasible winners carry
               port_dc (behavioural) records; outcome recorded
  4. BRIDGE    derived rows: re-run 2 of them fresh under rl-v1.1 -> byte-identical
  5. GENERATION every new bench/train candidate passes the port-DC pre-filter;
               pre-filter rejects counted
  6. TRAINING  tag / re-check / label re-check outcomes of the 3 restored tasks
  7. FENCE     finalize fence check rc 0; negative control: a training dir holding
               a copy of an amend2-port-dc cell is flagged (rc 1)
  8. BUDGET    the full run's bench end (start.json t_amend1 + 72 h) is unchanged
"""
import json
import os
import shutil
import subprocess
import sys
from collections import Counter

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop",
           REPO + "/kaggle/campaigns/bench-v2"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import bv2  # noqa: E402
import bench_anchor_prep as PREP  # noqa: E402

CAMP = bv2.CAMP
RD = f"{CAMP}/smoke/run-amend2"
OUT = f"{CAMP}/smoke/smoke_checks_a2.json"


def jl(path):
    out = []
    for ln in open(path):
        try:
            out.append(json.loads(ln))
        except Exception:                                        # noqa: BLE001
            pass
    return out


def main():
    rows = [r for r in jl(f"{RD}/results.jsonl")]
    cells = bv2.load_jsonl_last(f"{RD}/cells.jsonl", "name")
    tasks = bv2.load_jsonl_last(f"{RD}/train.jsonl", "name")
    cands = jl(f"{RD}/candidates.jsonl")
    chk = {}
    # 1 profile
    want = dict(PREP.VERIFIER_PROFILES["rl-v1.1"])
    bad = []
    for r in rows:
        v = (r.get("res") or {}).get("verifier")
        fl = (v or {}).get("flags") or {}
        ok = (r.get("profile") == "rl-v1.1" and r.get("phase") == "amendment-2"
              and (r.get("res") is None or (v.get("profile") == "rl-v1.1"
                                            and all(fl.get(k) == x for k, x in want.items()))))
        if not ok:
            bad.append(r["jid"])
    chk["1_profile"] = {"rows": len(rows), "derived": sum(1 for r in rows if r.get("derived_from")),
                        "resized_or_new": sum(1 for r in rows if not r.get("derived_from")
                                              and not r.get("inproc_reject")),
                        "inproc": sum(1 for r in rows if r.get("inproc_reject")),
                        "bad": bad, "pass": not bad}
    # 2 restore
    exp = {"v2a-nb090-gain-007": "revalidate", "v2a-wb0530-power-000": "tag",
           "v2a-nb158-noise-149": "tag", "v2a-nb090-gain-038": "revive",
           "v2a-wb0824-gain-033": "requeue"}
    got = {n: (cells.get(n, {}).get("amend2") or {}).get("action") for n in exp}
    rep = [c for c in cells.values() if (c.get("amend2") or {}).get("action") == "replant"]
    tagged = [n for n, c in cells.items() if c["status"] == bv2.TAG_PDC]
    chk["2_restore"] = {"actions": got, "status": {n: cells.get(n, {}).get("status") for n in exp},
                        "outcomes": {n: (cells.get(n, {}).get("amend2") or {}).get("outcome")
                                     for n in exp},
                        "replanted": [[c["name"], c["status"], c["amend2"].get("void_prekill")]
                                      for c in rep],
                        "tagged_not_selectable": all(not cells[n].get("selectable") for n in tagged),
                        "pass": got == exp and len(rep) == 1 and set(tagged) >= {
                            "v2a-wb0530-power-000", "v2a-nb158-noise-149"}}
    # 3 revalidation of the control
    c = cells.get("v2a-nb090-gain-007") or {}
    byjid = {r["jid"]: r for r in rows}
    runs = [x for stg in (c.get("stages") or {}).values() if isinstance(stg, dict)
            for x in stg.get("runs") or [] if isinstance(x, dict) and x.get("jid")]
    v11 = [byjid.get(x["jid"], {}).get("profile") == "rl-v1.1" for x in runs]
    pdc = [(byjid.get(x["jid"], {}).get("res") or {}).get("port_dc") for x in runs if x.get("feasible")]
    chk["3_revalidate_control"] = {
        "status": c.get("status"), "outcome": (c.get("amend2") or {}).get("outcome"),
        "why": c.get("why"), "n_stage_runs": len(runs), "all_rl_v1_1": all(v11),
        "feasible_runs_with_port_dc": sum(1 for p in pdc if isinstance(p, dict)),
        "feasible_runs": len(pdc),
        "port_dc_all_pass": all(isinstance(p, dict) and p.get("pass") for p in pdc),
        "primary_atom": c.get("primary_atom"), "core": (c.get("core") or {}).get("signature"),
        "pass": all(v11) and bool(runs) and all(isinstance(p, dict) and p.get("pass") for p in pdc)}
    # 4 bridge exactness (fresh rl-v1.1 re-run of derived rows)
    import proposal as PR
    anch = bv2.anchor_data()

    def toks_of(r):
        m = r.get("meta") or {}
        if r["kind"] in ("F1", "T-F1", "cal"):
            return anch[m["anchor"]]["tokens"]
        if m.get("task") and m["task"] in tasks:
            return PR.round_trip(tasks[m["task"]]["netlist"])["tokens"]
        if m.get("cell") in cells and r["kind"] in ("A1", "A2", "A3"):
            return PR.round_trip(cells[m["cell"]]["netlist"])["tokens"]
        return None

    def wall(x):                     # the one wall-clock field (smoke_checks.py)
        x = dict(x or {})
        if isinstance(x.get("stab_inloop"), dict):
            x["stab_inloop"] = {k: v for k, v in x["stab_inloop"].items() if k != "wide_secs"}
        return json.dumps(x)
    pool = [r for r in rows if r.get("derived_from") and toks_of(r) is not None]
    der = [r for r in pool if (r.get("res") or {}).get("n_evals")][:1] + \
          [r for r in pool if r.get("res") and not r["res"].get("n_evals")][:1]
    ex = []
    for r in der:
        toks = toks_of(r)
        if bv2.tokhash(toks) != r["tok"]:
            ex.append({"jid": r["jid"], "skipped": "token hash mismatch"})
            continue
        fresh = PREP.smoke_run(list(toks), f"{REPO}/{r['spec']}", r["seed"], r["budget"],
                               "bptm45", profile="rl-v1.1")
        ex.append({"jid": r["jid"], "kind": r["kind"], "n_evals": r["res"].get("n_evals"),
                   "byte_identical_excl_wide_secs": wall(fresh) == wall(r["res"])})
    chk["4_bridge"] = {"checked": ex,
                       "pass": all(x.get("byte_identical_excl_wide_secs", True) for x in ex)
                       and any("byte_identical_excl_wide_secs" in x for x in ex)}
    # 5 generation pre-filter
    newc = [x for x in cands if x.get("era_tag") == "amendment-2" or
            (x["stream"] == "train" and x.get("gen", 0) >= 41)]
    pf_bad = [x["cid"] for x in newc if not PREP.port_dc_prefilter(x["tokens"])["pass"]]
    pr = json.load(open(f"{RD}/progress.json"))
    chk["5_generation"] = {"new_candidates": len(newc), "prefilter_fail": pf_bad,
                           "gen_rejects_prefilter": pr["amendment2"]["port_dc"]["gen_rejects_prefilter"],
                           "pass": bool(newc) and not pf_bad}
    # 6 training
    chk["6_training"] = {n: {"status": t["status"], "amend2": t.get("amend2"),
                             "witness": (t.get("stages") or {}).get("witness")}
                         for n, t in tasks.items()}
    t1, t2, t3 = (tasks.get(n, {}) for n in ("t2-nb158-gain-0003", "t2-wb1020-gain-0001",
                                              "t2-nb090-noise-0012"))
    chk["6_training_pass"] = (t1.get("status") == bv2.TAG_PDC and t2.get("status") in ("ok", bv2.TAG_PDC, "unproved")
                              and (t2.get("amend2") or {}).get("action") == "recheck"
                              and (t3.get("amend2") or {}).get("action") == "recheck")
    # 7 fence (+ negative control)
    lib = f"{CAMP}/smoke/amend2-editcap-lib-v2"
    tp = f"{CAMP}/smoke/amend2-train-pool-v2"
    r0 = subprocess.run([sys.executable, f"{CAMP}/fence_check.py", "--bench", lib, "--train", tp,
                         "--cells-jsonl", f"{RD}/cells.jsonl"], capture_output=True, text=True)
    neg = f"{CAMP}/smoke/_neg_train_a2"
    shutil.rmtree(neg, ignore_errors=True)
    tg = cells["v2a-wb0530-power-000"]
    d = f"{neg}/neg-copy-of-tagged-cell/witness"
    os.makedirs(d)
    shutil.copy(f"{REPO}/kaggle/campaigns/bench-v2/run/cells/v2a-wb0530-power-000/spec.yaml",
                f"{neg}/neg-copy-of-tagged-cell/spec.yaml")
    open(f"{d}/witness.net", "w").write("* neg control\n" + tg["netlist"])
    json.dump({"tok_hash": tg["tok"], "wl_hash": tg["wl"]}, open(f"{d}/edit_script.json", "w"))
    r1 = subprocess.run([sys.executable, f"{CAMP}/fence_check.py", "--bench", lib, "--train", neg,
                         "--cells-jsonl", f"{RD}/cells.jsonl"], capture_output=True, text=True)
    shutil.rmtree(neg, ignore_errors=True)
    chk["7_fence"] = {"finalize_rc": r0.returncode, "finalize_out": r0.stdout[-600:],
                      "negative_control_rc": r1.returncode, "negative_out": r1.stdout[-900:],
                      "pass": r0.returncode == 0 and r1.returncode == 1}
    # 8 budget clock of the FULL run
    st = json.load(open(f"{CAMP}/run/start.json"))
    import time
    end = st["t_amend1"] + 3600 * bv2.CONFIGS["full"]["bench_max_hours"]
    chk["8_budget"] = {"t_amend1": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st["t_amend1"])),
                       "bench_end": time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime(end)),
                       "pass": time.strftime("%Y-%m-%dT%H:%M", time.localtime(end)) == "2026-10-03T14:51"}
    chk["status_hist"] = dict(Counter(c["status"] for c in cells.values()))
    chk["all_pass"] = all(v.get("pass") for k, v in chk.items() if isinstance(v, dict) and "pass" in v) \
        and chk["6_training_pass"]
    json.dump(chk, open(OUT, "w"), indent=1, default=repr)
    print(json.dumps({k: (v.get("pass") if isinstance(v, dict) else v) for k, v in chk.items()},
                     indent=1, default=repr))


if __name__ == "__main__":
    main()
