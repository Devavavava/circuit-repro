#!/usr/bin/env python
"""bench-v2 AMENDMENT-1 smoke checks (run via envrun.sh after `launch.sh smoke-a1`
has finished). Writes smoke/smoke_checks_a1.json.

  1. FLOORS: every pre-amendment ACCEPTED cell spec is refused by the floor rule
     (its spec.yaml limits and its re-planted limits); every smoke bench probe
     carries the derived floor probe values; every post-amendment planted smoke
     cell meets the floors.
  2. CORE CLASSES of the 10 pre-amendment accepted cells (abl_core on real data,
     smoke/run-amend1/pre-amendment-core-classes.json): signatures + class count.
  3. QUOTAS: select_cells unit tests on synthetic cells (parent <= 40 %,
     narrowband >= 25 %, class <= 25 %, WL dedupe) and on the real pre-amendment
     accepted cells re-tagged as if post-amendment (all a3 / all wideband ->
     empty quota-compliant selection, shortfall reported).
  4. STEERING: one `steer` event per bench generation with point / parent weights
     and child allocation; the pre-amendment seeds were used in generation 0.
  5. DETERMINISM: recorded post-amendment calls (feasible + infeasible + an ABL
     call) re-run from scratch in a fresh worker are byte-identical (wall-clock
     keys excluded).
  6. FENCE: finalize's fence check rc 0; negative control: a training dir holding
     a copy of a post-amendment PLANTED (not accepted) bench cell is flagged.
  7. ERA: post-amendment cells/rows tagged, pre-amendment never selectable,
     all new result rows rl-v1.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bv2  # noqa: E402
import yaml  # noqa: E402

RD = f"{HERE}/smoke/run-amend1"
PRE = f"{HERE}/run/pre-amendment"


def strip(r):
    r = json.loads(json.dumps(r, default=repr))
    if isinstance(r, dict) and isinstance(r.get("stab_inloop"), dict):
        r["stab_inloop"].pop("wide_secs", None)
    return r


def last(path, key="name"):
    return bv2.load_jsonl_last(path, key)


def main():
    import bench_anchor_prep as PREP
    out = {}
    pre = last(f"{PRE}/cells.jsonl")
    pre_acc = [c for c in pre.values() if c["status"] == "accepted"]
    cells = last(f"{RD}/cells.jsonl")
    post = [c for c in cells.values() if c.get("era_tag") == bv2.AMEND]
    rows = [json.loads(ln) for ln in open(f"{RD}/results.jsonl")]
    # ---- 1 floors
    ref = []
    for c in pre_acc:
        lim_yaml = {m: list(v.values())[0] for m, v in yaml.safe_load(
            open(c["spec"]))["constraints"].items() if m in bv2.FLOORS}
        replant = bv2.planted_limits(c["bt"], c["planted_from"])
        ref.append({"cell": c["name"], "s11_max_db": lim_yaml.get("s11_max_db"),
                    "s21_db": lim_yaml.get("s21_db"),
                    "spec_violations": bv2.floor_violations(lim_yaml),
                    "replant_violations": bv2.floor_violations(replant)})
    probes = {}
    for f in sorted(os.listdir(f"{RD}/specs")):
        if f.startswith("probe-amd1-"):
            cons = yaml.safe_load(open(f"{RD}/specs/{f}"))["constraints"]
            probes[f] = {"s11_max_db": cons["s11_max_db"], "s21_db": cons["s21_db"]}
    want = {m: bv2.floor_probe_value(sd, F) for m, (sd, F) in bv2.FLOORS.items()}
    post_viol = {c["name"]: bv2.floor_violations(c["limits"]) for c in post
                 if bv2.floor_violations(c["limits"])}
    prog = json.load(open(f"{RD}/progress.json"))
    out["floors"] = {
        "pre_amendment_accepted_refused": ref,
        "probe_expected": want, "probe_files": probes,
        "post_planted": len(post), "post_planted_violating": post_viol,
        "floor_rejects_in_run": prog["bench"].get("floor_rejects"),
        "pass": (bool(ref) and all(r["spec_violations"] and r["replant_violations"] for r in ref)
                 and bool(probes) and all(
                     p["s11_max_db"]["max"] == want["s11_max_db"]
                     and p["s21_db"]["min"] == want["s21_db"] for p in probes.values())
                 and not post_viol)}
    # ---- 2 core classes of the pre-amendment accepted cells
    pc = json.load(open(f"{RD}/pre-amendment-core-classes.json"))
    sigs = {n: {"signature": v["signature"], "primary_atom": v.get("primary_atom"),
                "primary_ranking": (v.get("primary") or {}).get("ranking"),
                "old_class": v["old_class"],
                "core_groups": v["core_groups"], "inert_groups": v["inert_groups"],
                "essential_drop_one": v["essential_drop_one"],
                "strip": v["strip"].get("flag")} for n, v in pc["cells"].items()}
    atom_cnt = {}
    for v in pc["cells"].values():
        for a in set(bv2.sig_atoms(v["signature"])):
            atom_cnt[a] = atom_cnt.get(a, 0) + 1
    out["pre_amendment_core_classes"] = {
        "n_cells": len(sigs), "n_classes": len(pc["class_hist"]),
        "class_hist": pc["class_hist"], "atom_hist": dict(sorted(
            atom_cnt.items(), key=lambda kv: -kv[1])),
        "primary_atom_hist": pc.get("primary_atom_hist"),
        "atom_prevalence": pc.get("atom_prevalence"),
        "cells": sigs, "pending": pc["pending"],
        "one_class": len(pc["class_hist"]) == 1,
        "pass": len(sigs) == len(pre_acc) and not pc["pending"]}
    # ---- 3 quotas
    cfg = dict(bv2.CONFIGS["full"])

    def syn(i, bt, anchor, cls, wl=None, prim=None):
        return {"name": f"s{i}", "seq": i, "bt": bt, "band": "wb0530" if bt == "wideband"
                else "nb240", "anchor": anchor, "cls": cls, "wl": wl or f"w{i}",
                "primary_atom": prim or f"p-{cls}", "era_tag": bv2.AMEND}
    S = []
    for i in range(20):                                   # 20 wideband a3, 10 classes
        S.append(syn(i, "wideband", "a3", f"c{i % 10}"))
    for i in range(20, 26):                               # 6 narrowband a1
        S.append(syn(i, "narrowband", "a1", f"n{i}"))
    for i in range(26, 34):                               # 8 wideband a2 / a5
        S.append(syn(i, "wideband", "a2" if i % 2 else "a5", f"m{i}"))
    S.append(syn(34, "wideband", "a2", "m27", wl="w27"))  # duplicate WL
    sel = bv2.select_cells(S, cfg)
    n = len(sel)
    cnt = lambda k: max([sum(1 for c in sel if c[k] == v) for v in {c[k] for c in sel}] or [0])  # noqa: E731
    q = {"n": n, "max_parent": cnt("anchor"), "max_class": cnt("cls"),
         "n_narrowband": sum(1 for c in sel if c["bt"] == "narrowband"),
         "dup_wl": n - len({c["wl"] for c in sel})}
    q_ok = (n > 0 and q["max_parent"] <= math.floor(0.4 * n)
            and q["max_class"] <= max(1, math.floor(0.25 * n))
            and q["n_narrowband"] >= math.ceil(0.25 * n) and q["dup_wl"] == 0)
    # narrowband-bound case: only 2 narrowband cells -> n limited to 8
    S2 = [c for c in S if c["bt"] == "wideband"] + [syn(40, "narrowband", "a4", "z1"),
                                                    syn(41, "narrowband", "a5", "z2")]
    sel2 = bv2.select_cells(S2, cfg)
    sel2_nonb = bv2.select_cells(S2, cfg, nb_quota=False)
    # rule (b): 10 wideband cells with distinct signatures but one shared primary
    # atom -> (a) may select several, (b) at most floor(0.25 n) of them
    S3 = [syn(50 + i, "wideband", ["a2", "a3", "a5"][i % 3], f"sig{i}", prim="add:L:IN-G")
          for i in range(10)] + [syn(70 + i, "narrowband", ["a1", "a4"][i % 2], f"nsig{i}",
                                     prim=f"nb-{i}") for i in range(10)]
    a_sel = bv2.select_cells(S3, cfg, rule="signature")
    b_sel = bv2.select_cells(S3, cfg, rule="primary_atom")
    nL = lambda lst: sum(1 for c in lst if c["primary_atom"] == "add:L:IN-G")  # noqa: E731
    rule_b = {"a_n": len(a_sel), "a_n_primary_L": nL(a_sel), "b_n": len(b_sel),
              "b_n_primary_L": nL(b_sel),
              "pass": nL(b_sel) <= max(1, math.floor(0.25 * len(b_sel))) and nL(a_sel) > nL(b_sel)}
    real = [dict(c, era_tag=bv2.AMEND, cls=sigs.get(c["name"], {}).get("signature", c["cls"]),
                 primary_atom=sigs.get(c["name"], {}).get("primary_atom"))
            for c in pre_acc]
    rep, rsel = bv2.selection_report(real, cfg)
    out["quotas"] = {
        "synthetic_35": q, "synthetic_pass": q_ok,
        "nb_bound_case": {"with_quota": len(sel2), "without_nb_quota": len(sel2_nonb),
                          "n_nb_selected": sum(1 for c in sel2 if c["bt"] == "narrowband")},
        "primary_atom_rule_test": rule_b,
        "pre_amendment_as_if_post": {"selected": len(rsel), "report": rep},
        "pre_amendment_really_selectable": len(bv2.select_cells(pre_acc, cfg)),
        "pass": q_ok and rule_b["pass"] and len(sel2) == 8 and len(sel2_nonb) > len(sel2) and len(rsel) == 0
        and len(bv2.select_cells(pre_acc, cfg)) == 0}
    # ---- 4 steering
    ev = [json.loads(ln) for ln in open(f"{RD}/events.jsonl")]
    steer = [e for e in ev if e["kind"] == "steer"]
    cands = [json.loads(ln) for ln in open(f"{RD}/candidates.jsonl")]
    bc = [c for c in cands if c["stream"] == "bench"]
    out["steering"] = {
        "steer_events": [{k: e[k] for k in ("gen", "m_nb", "point_w", "alloc", "parent_w",
                                            "counts", "capped_cores")} for e in steer],
        "bench_candidates": len(bc),
        "origins": {k: sum(1 for c in bc if c["origin"]["kind"] == k)
                    for k in {c["origin"]["kind"] for c in bc}},
        "pass": len(steer) >= 2 and any(c["origin"]["kind"] == "seed_pre_amendment"
                                        for c in bc)}
    # ---- 5 determinism
    own = [r for r in rows if r.get("res") and (r["res"].get("n_evals") or 0) > 0
           and r.get("phase") == bv2.AMEND]
    tokmap = {}
    for c in cands:
        tokmap[c["tok"]] = c["tokens"]
    for a in bv2.anchor_data().values():
        tokmap[a["tok"]] = a["tokens"]
    # ABL / S-A* tokens: recompute from the pre-amendment core file netlists
    pick = ([r for r in own if r["res"].get("feasible") and r["tok"] in tokmap][:1]
            + [r for r in own if not r["res"].get("feasible") and r["tok"] in tokmap][:1])
    ablrows = [r for r in own if r["kind"] == "ABL" and (r.get("meta") or {}).get("kept")]
    det = []
    for r in pick:
        det.append(rerun(r, tokmap[r["tok"]]))
    if ablrows:
        # rebuild tokens of an ABL trial from its cell's script + kept groups
        import proposal as P
        r = ablrows[0]
        c = pre[r["meta"]["cell"]]
        A = bv2.anchor_data()[c["anchor"]]
        kept = set(r["meta"].get("kept") or [])
        s2 = [o for o in c["script"] if o["grp"] in kept] if kept else c["script"]
        el, _ = bv2.repair(bv2.apply_script(A["elems"], s2))
        rt = P.round_trip(bv2.net_text(el))
        if bv2.tokhash(rt["tokens"]) == r["tok"]:
            det.append(rerun(r, rt["tokens"]))
    out["determinism"] = {"rerun": det,
                          "pass": len(det) >= 2 and all(d["identical"] for d in det)}
    # ---- 6 fence
    fc = open(f"{RD}/fence_check.txt").read() if os.path.exists(f"{RD}/fence_check.txt") else ""
    neg = None
    np_ = [c for c in post if c["status"] != "accepted"]
    if np_:
        c = np_[0]
        td = tempfile.mkdtemp(prefix="bv2fence_", dir=os.environ.get("TMPDIR", "/tmp"))
        os.makedirs(f"{td}/train/fake/witness")
        shutil.copy(c["spec"], f"{td}/train/fake/spec.yaml")
        open(f"{td}/train/fake/witness/witness.net", "w").write("* fake\n" + c["netlist"])
        json.dump({"tok_hash": c["tok"], "wl_hash": c["wl"]},
                  open(f"{td}/train/fake/witness/edit_script.json", "w"))
        os.makedirs(f"{td}/bench")
        p = subprocess.run([sys.executable, f"{HERE}/fence_check.py", "--bench", f"{td}/bench",
                            "--train", f"{td}/train", "--cells-jsonl", f"{RD}/cells.jsonl"],
                           capture_output=True, text=True)
        neg = {"planted_not_accepted_cell": c["name"], "status": c["status"],
               "rc": p.returncode, "out": p.stdout.strip().splitlines()}
    out["fence"] = {"finalize_fence_check": fc.strip().splitlines(),
                    "negative_control": neg,
                    "pass": "violations=0" in fc and (neg is None or neg["rc"] == 1)}
    # ---- 7 era / profile
    want_flags = {k: PREP.VERIFIER_PROFILES["rl-v1"].get(k) for k in PREP.VERIFIER_FLAGS}
    bad = [r["jid"] for r in rows if r.get("res") and (
        (r["res"].get("verifier") or {}).get("profile") != "rl-v1"
        or (r["res"].get("verifier") or {}).get("flags") != want_flags
        or r.get("phase") != bv2.AMEND)]
    idx = json.load(open(f"{HERE}/smoke/amend1-editcap-lib-v2/INDEX.json"))
    out["era"] = {"own_rows": len(rows), "bad_rows": bad,
                  "post_cells": len(post), "post_untagged": [
                      c["name"] for c in cells.values() if c["name"].startswith("v2a-")
                      and c.get("era_tag") != bv2.AMEND],
                  "index_selected": list(idx["cells"]),
                  "index_has_pre": [n for n in idx["cells"] if not n.startswith("v2a-")],
                  "pass": not bad and not [n for n in idx["cells"] if not n.startswith("v2a-")]}
    out["all_pass"] = all(v.get("pass") for v in out.values() if isinstance(v, dict))
    json.dump(out, open(f"{HERE}/smoke/smoke_checks_a1.json", "w"), indent=1, default=repr)
    print(json.dumps({k: (v.get("pass") if isinstance(v, dict) else v)
                      for k, v in out.items()}, indent=1))


def rerun(r, tokens):
    td = tempfile.mkdtemp(prefix="bv2det_", dir=os.environ.get("TMPDIR", "/tmp"))
    jf, of = f"{td}/j.json", f"{td}/o.json"
    json.dump({"jid": r["jid"], "tokens": tokens, "spec": f"{bv2.REPO}/{r['spec']}",
               "seed": r["seed"], "budget": r["budget"]}, open(jf, "w"))
    subprocess.run([sys.executable, f"{HERE}/bv2.py", "worker", jf, of], check=True,
                   capture_output=True)
    new = json.load(open(of))
    return {"jid": r["jid"], "kind": r["kind"], "feasible": r["res"]["feasible"],
            "identical": strip(new["res"]) == strip(r["res"])}


if __name__ == "__main__":
    main()
