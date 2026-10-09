#!/usr/bin/env python
"""exit-r1 tables (kaggle/PREREG-EXIT-R1.md).

  r1_summarize.py gen [policy,..]   step 2: per policy x difficulty label (x novelty):
        completions, valid, unique keys, seed-1-feasible, positives (feasible at seeds 1
        AND 2, rl-v1.2-rl), novel positives (target WL not in pilot-v0 data), copies of the
        task's own pilot-v0 targets, anchors; think-length summary
        -> verify/gen-summary.json, verify/gen-tables.md
  r1_summarize.py heldout <label2> <label8>   steps 5/6
"""
import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
VD = os.environ.get("R1_VERIFY_DIR") or os.path.join(HERE, "verify")
DIFFS = ("library-solvable", "single-edit-solvable", "witness-only")


def rj(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def pct(a, b):
    return "%d/%d (%.1f%%)" % (a, b, 100.0 * a / b) if b else "%d/0" % a


def gen(policies):
    ver = {(r["task"], r["key"], r["seed"]): r for r in rj(os.path.join(VD, "verify.jsonl"))}
    res = OrderedDict(prereg="kaggle/PREREG-EXIT-R1.md (573a21a89) step 2", profile="rl-v1.2-rl",
                      positive="valid edit feasible at seed 1 AND seed 2", policies=OrderedDict())
    L = ["| policy | difficulty | tasks | completions | valid | seed-1 feasible | positives | positive tasks | "
         "novel positives (distinct WLs) | own-target copies among positives | anchor positives |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    missing = Counter()
    for pol in policies:
        comps = rj(os.path.join(VD, pol, "completions.jsonl"))
        out = OrderedDict()
        for g in ("all",) + DIFFS:
            cs = [c for c in comps if g == "all" or c["difficulty"] == g]
            v = [c for c in cs if c.get("valid")]
            f1, pos = [], []
            for c in v:
                r1 = ver.get((c["task"], c["key"], 1))
                if r1 is None:
                    missing["seed1"] += 1
                    continue
                if r1.get("feasible"):
                    f1.append(c)
                    r2 = ver.get((c["task"], c["key"], 2))
                    if r2 is None:
                        missing["seed2"] += 1
                    elif r2.get("feasible"):
                        pos.append(c)
            nov = [c for c in pos if c.get("novel")]
            d = OrderedDict(tasks=len({c["task"] for c in cs}), completions=len(cs), valid=len(v),
                            unique_keys=len({(c["task"], c["key"]) for c in v}),
                            seed1_feasible=len(f1), positives=len(pos),
                            positive_tasks=len({c["task"] for c in pos}),
                            positive_unique=len({(c["task"], c["key"]) for c in pos}),
                            novel_positives=len(nov), novel_positive_wls=len({c["wl"] for c in nov}),
                            own_target_copies=sum(1 for c in pos if c.get("copy_own_target")),
                            anchor_positives=sum(1 for c in pos if c.get("anchor")),
                            valid_novel=sum(1 for c in v if c.get("novel")),
                            valid_own_copy=sum(1 for c in v if c.get("copy_own_target")),
                            valid_anchor=sum(1 for c in v if c.get("anchor")),
                            seed2_confirm_rate=round(len(pos) / len(f1), 4) if f1 else None)
            out[g] = d
            L.append("| %s | %s | %d | %d | %s | %s | %s | %d | %d (%d) | %d | %d |" % (
                pol, g, d["tasks"], d["completions"], pct(d["valid"], d["completions"]),
                pct(d["seed1_feasible"], d["valid"]), pct(d["positives"], d["valid"]), d["positive_tasks"],
                d["novel_positives"], d["novel_positive_wls"], d["own_target_copies"], d["anchor_positives"]))
        tt = sorted(c.get("think_tokens") or 0 for c in comps)
        rt = sorted(c.get("reasoning_tokens") or 0 for c in comps if c.get("reasoning_tokens") is not None)
        out["think"] = OrderedDict(
            stop=dict(Counter(str(c.get("think_stop")) for c in comps)),
            think_tokens_median=tt[len(tt) // 2] if tt else None, think_tokens_max=tt[-1] if tt else None,
            reasoning_tokens_lt20=sum(1 for x in rt if x < 20), reasoning_tokens_gt512=sum(1 for x in rt if x > 512),
            recovered=sum(1 for c in comps if c.get("recovered_from_reasoning")),
            llm_errors=sum(1 for c in comps if c.get("llm_error")))
        res["policies"][pol] = out
    res["missing_rows"] = dict(missing)
    both = defaultdict(set)
    for pol in policies:
        for c in rj(os.path.join(VD, pol, "completions.jsonl")):
            if c.get("valid") and (ver.get((c["task"], c["key"], 1)) or {}).get("feasible") and \
                    (ver.get((c["task"], c["key"], 2)) or {}).get("feasible"):
                both[pol].add(c["task"])
    if len(policies) == 2:
        a, b = (both[p] for p in policies)
        res["positive_task_overlap"] = OrderedDict(both=len(a & b), union=len(a | b), only_first=len(a - b),
                                                   only_second=len(b - a))
        L.append("")
        L.append("Tasks with >= 1 positive: " + json.dumps(res["positive_task_overlap"]))
    for pol in policies:
        L.append("")
        L.append("%s think: %s" % (pol, json.dumps(res["policies"][pol]["think"])))
    json.dump(res, open(os.path.join(VD, "gen-summary.json"), "w"), indent=1)
    open(os.path.join(VD, "gen-tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print("missing:", dict(missing))


# ======================================================================== eval (steps 5/6)
PV0 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0")
P1 = os.path.join(PV0, "P1")
PV1 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v1")
SCR = os.path.join(HERE, "score")
KS = (1, 2, 4, 8)
TIERS = ("T1", "T2", "T3")


def _pv1():
    os.environ["PV1_SCORE_DIR"] = SCR
    sys.path.insert(0, PV1)
    import pv1_summarize as S
    return S


def kmap(*paths):
    m = {}
    for p in paths:
        for r in rj(p):
            m[(r["task"], r["key"], r["seed"])] = r
    return m


def h1_model(S, comps, sm, km, it):
    """pilot-v1 H1: a sample passes iff valid and feasible at seed 1 (rl-v1.2); kick column:
    and the same sizing under rl-v1.2-rl is feasible."""
    by = defaultdict(list)
    for c in comps:
        by[c["task"]].append(c)
    per, missing = OrderedDict(), Counter()
    for t, tier in it.items():
        cs = by.get(t, [])
        c1 = ck = 0
        for c in cs:
            if not c.get("valid"):
                continue
            r1 = sm.get((t, c["key"], 1))
            if r1 is None:
                missing["seed1"] += 1
                continue
            if r1.get("feasible"):
                c1 += 1
                k = km.get((t, c["key"], 1))
                if k is None:
                    missing["kick"] += 1
                elif k.get("feasible"):
                    ck += 1
        per[t] = {"tier": tier, "n": len(cs), "c": c1, "ck": ck}
    g = OrderedDict()
    for grp in ("all",) + TIERS:
        rows = [r for r in per.values() if grp == "all" or r["tier"] == grp]
        d = OrderedDict(n_items=len(rows), min_n=min(r["n"] for r in rows) if rows else None)
        for crit, key in (("rl-v1.2", "c"), ("rl-v1.2-rl", "ck")):
            e = OrderedDict()
            for k in KS:
                vals = [S.passk(r["n"], r[key], k) for r in rows]
                vals = [v for v in vals if v is not None]
                e["pass@%d" % k] = round(sum(vals) / len(vals), 4) if len(vals) == len(rows) and vals else None
            e["coverage"] = sum(1 for r in rows if r[key] > 0)
            d[crit] = e
        g[grp] = d
    return g, per, dict(missing)


def two_model(comps, sm, km, it, samples=(1, 2)):
    """pilot-v0: solved = some valid sample (of `samples`) feasible at >= 1 of seeds 1-3
    (rl-v1.2); >= 2/3 seeds; kick column: feasible under rl-v1.2-rl at that seed."""
    by = defaultdict(list)
    for c in comps:
        if c["sample"] in samples:
            by[c["task"]].append(c)
    per, missing = OrderedDict(), Counter()
    for t, tier in it.items():
        sol = sol2 = solk = False
        nv = 0
        for c in by.get(t, []):
            if not c.get("valid"):
                continue
            nv += 1
            f, fk = [], []
            for s in (1, 2, 3):
                r = sm.get((t, c["key"], s))
                if r is None:
                    missing["rl-v1.2"] += 1
                f.append(bool(r and r.get("feasible")))
                if f[-1]:
                    k = km.get((t, c["key"], s))
                    if k is None:
                        missing["kick"] += 1
                    fk.append(bool(k and k.get("feasible")))
            sol |= any(f)
            sol2 |= sum(f) >= 2
            solk |= any(fk)
        per[t] = {"tier": tier, "n": len(by.get(t, [])), "n_valid": nv, "solved": sol, "solved_2of3": sol2,
                  "solved_kick": solk}
    g = OrderedDict()
    for grp in ("all",) + TIERS:
        rows = [r for r in per.values() if grp == "all" or r["tier"] == grp]
        n, v = sum(r["n"] for r in rows), sum(r["n_valid"] for r in rows)
        g[grp] = OrderedDict(n_items=len(rows), solved=sum(r["solved"] for r in rows),
                             solved_2of3=sum(r["solved_2of3"] for r in rows),
                             solved_kick=sum(r["solved_kick"] for r in rows),
                             validity=round(v / n, 4) if n else None)
    return g, per, dict(missing)


def eval_(label2, label8):
    S = _pv1()
    it = S.items()
    sm_r1 = S.score_map(os.path.join(SCR, "score.jsonl"))
    km_r1 = kmap(os.path.join(SCR, "kick.jsonl"))
    km_v1 = kmap(os.path.join(SCR, "kick-ref-pv1.jsonl"))
    km_v0 = kmap(os.path.join(SCR, "kick-ref-pv0.jsonl"))
    sm_v1 = S.score_map(os.path.join(PV1, "score", "score.jsonl"))
    sm_v0 = S.score_map(os.path.join(P1, "score", "score.jsonl"))
    res = OrderedDict(prereg="kaggle/PREREG-EXIT-R1.md (573a21a89) steps 5-6", h1=OrderedDict(),
                      two_sample=OrderedDict(), missing=OrderedDict())
    per_h1 = {}
    for lab, comps, sm, km in (
            ("sft300", rj(os.path.join(PV1, "score", "h1-sft300", "completions.jsonl")), sm_v1, km_v1),
            ("sft1000", rj(os.path.join(PV1, "score", "h1-sft1000", "completions.jsonl")), sm_v1, km_v1),
            ("sft-r1", rj(os.path.join(SCR, label8, "completions.jsonl")), sm_r1, km_r1)):
        g, per, miss = h1_model(S, comps, sm, km, it)
        res["h1"][lab] = g
        res["missing"]["h1:" + lab] = miss
        per_h1[lab] = per
    per_2 = {}
    for lab, comps, sm, km in (
            ("sft300", rj(os.path.join(P1, "score", "sft300", "completions.jsonl")), sm_v0, km_v0),
            ("sft1000", rj(os.path.join(P1, "score", "sft1000", "completions.jsonl")), sm_v0, km_v0),
            ("sft-r1", rj(os.path.join(SCR, label2, "completions.jsonl")), sm_r1, km_r1)):
        g, per, miss = two_model(comps, sm, km, it)
        res["two_sample"][lab] = g
        res["missing"]["2s:" + lab] = miss
        per_2[lab] = per
    H, T = res["h1"], res["two_sample"]
    loss = {t: T["sft1000"][t]["solved"] - T["sft-r1"][t]["solved"] for t in TIERS}
    dec = OrderedDict(
        pass1_r1=H["sft-r1"]["all"]["rl-v1.2"]["pass@1"], pass1_sft1000=H["sft1000"]["all"]["rl-v1.2"]["pass@1"],
        pass8_r1=H["sft-r1"]["all"]["rl-v1.2"]["pass@8"], pass8_sft1000=H["sft1000"]["all"]["rl-v1.2"]["pass@8"],
        tier_loss_vs_sft1000=loss)
    dec["cond_pass1"] = dec["pass1_r1"] is not None and dec["pass1_r1"] > dec["pass1_sft1000"]
    dec["cond_pass8"] = dec["pass8_r1"] is not None and dec["pass8_r1"] > dec["pass8_sft1000"]
    dec["cond_tiers"] = all(v < 3 for v in loss.values())
    dec["round1_succeeds"] = dec["cond_pass1"] and dec["cond_pass8"] and dec["cond_tiers"]
    dec["vs_sft300"] = OrderedDict(
        pass1=H["sft300"]["all"]["rl-v1.2"]["pass@1"], pass8=H["sft300"]["all"]["rl-v1.2"]["pass@8"],
        tier_loss={t: T["sft300"][t]["solved"] - T["sft-r1"][t]["solved"] for t in TIERS})
    cov = {lab: {t for t, r in per.items() if r["c"]} for lab, per in per_h1.items()}
    dec["coverage_any_of_8"] = {lab: len(v) for lab, v in cov.items()}
    dec["union_sft300_sft1000"] = len(cov["sft300"] | cov["sft1000"])
    dec["union_all_three"] = len(cov["sft300"] | cov["sft1000"] | cov["sft-r1"])
    dec["r1_covers_of_union"] = len(cov["sft-r1"] & (cov["sft300"] | cov["sft1000"]))
    dec["r1_only"] = sorted(cov["sft-r1"] - cov["sft300"] - cov["sft1000"])
    res["decision"] = dec
    ids = rj(os.path.join(HERE, "sft-data", "ids.jsonl"))
    if not ids and os.path.exists(os.path.join(HERE, "sft-data", "ids.json")):
        ids = json.load(open(os.path.join(HERE, "sft-data", "ids.json")))
    own = {x["target_wl"] for x in ids}
    for lab, d in ((label8, "h1"), (label2, "2s")):
        v = [c for c in rj(os.path.join(SCR, lab, "completions.jsonl")) if c.get("valid")]
        res["copy_" + d] = OrderedDict(valid=len(v), own_target_copies=sum(1 for c in v if c.get("wl") in own),
                                       distinct_wl=len({c.get("wl") for c in v}))
    res["per_item_h1"] = per_h1
    res["per_item_2s"] = per_2
    json.dump(res, open(os.path.join(SCR, "r1-summary.json"), "w"), indent=1)
    L = ["### H1 protocol (8 samples; pass = valid & feasible at seed 1); [kick column: rl-v1.2-rl]", "",
         "| model | group | pass@1 | pass@2 | pass@4 | pass@8 | coverage | kick pass@1 | kick pass@8 | kick coverage |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for lab in ("sft300", "sft1000", "sft-r1"):
        for grp in ("all",) + TIERS:
            a, k = H[lab][grp]["rl-v1.2"], H[lab][grp]["rl-v1.2-rl"]
            L.append("| %s | %s (%d) | %s | %s | %s | %s | %d | %s | %s | %d |" % (
                lab, grp, H[lab][grp]["n_items"], a["pass@1"], a["pass@2"], a["pass@4"], a["pass@8"],
                a["coverage"], k["pass@1"], k["pass@8"], k["coverage"]))
    L += ["", "### 2-sample protocol (pilot-v0: solved = some sample feasible at >= 1 of seeds 1-3)", "",
          "| model | solved | >= 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | validity | solved under kick |",
          "|---|---|---|---|---|---|---|---|"]
    for lab in ("sft300", "sft1000", "sft-r1"):
        x = T[lab]
        L.append("| %s | %d | %d | %d | %d | %d | %s | %d |" % (
            lab, x["all"]["solved"], x["all"]["solved_2of3"], x["T1"]["solved"], x["T2"]["solved"],
            x["T3"]["solved"], x["all"]["validity"], x["all"]["solved_kick"]))
    L += ["", "Decision: " + json.dumps(dec), "", "Copy: " + json.dumps({k: res[k] for k in ("copy_h1", "copy_2s")}),
          "", "Missing rows: " + json.dumps(res["missing"])]
    open(os.path.join(SCR, "r1-tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "gen":
        gen(a[1].split(",") if len(a) > 1 else ["sft1000", "sft300"])
    elif a[0] == "heldout":
        eval_(a[1], a[2])
