#!/usr/bin/env python
"""pilot-v1 tables (kaggle/PREREG-PILOT-V1.md).

  pv1_summarize.py h1 <label>[,<label>..]   -> score/h1-summary.json, score/h1-tables.md
  pv1_summarize.py m1 <label>               -> score/m1-summary.json, score/m1-tables.md

H1 (per label, k = 8 fresh samples per held-out item):
  a sample PASSES iff its edit is round-trip valid and feasible at seed 1 (rl-v1.2, 2500);
  seeds 2,3 are sized for every seed-1-feasible key and reported as confirmation
  ("confirmed" = feasible at >= 2 of the 3 seeds, secondary pass@k).
  pass@k = mean over items of 1 - C(n-c, k) / C(n, k)  (unbiased; n samples, c passes);
  coverage = items with c >= 1; per-item solve frequency c/n.
  Reading (pre-declared): pass@8 >= 1.5 x pass@1 -> strong verifier-selection headroom;
  pass@8 ~ pass@1 -> narrow distribution (coded: ratio <= 1.1); else intermediate.
M1 (label = the sft-mix1000 run, 2 samples, seeds 1-3 for every valid key):
  pilot-v0 definitions (solved = some valid sample feasible at >= 1 seed; >= 2/3 seeds),
  per tier; compared with pilot-v0's sft300 / sft1000 rows (pilot-v0/P1/score/summary.json).
  copy rate = valid outputs whose WL equals a target WL of the model's OWN training set.
  Decision: works iff T2 solved(mix) - T2 solved(sft1000) >= 3 AND
            T1 solved(sft1000) - T1 solved(mix) < 3 AND copy(mix) < copy(sft1000) / 2.
"""
import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PV0 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0")
P1 = os.path.join(PV0, "P1")
SC = os.environ.get("PV1_SCORE_DIR") or os.path.join(HERE, "score")
KS = (1, 2, 4, 8)
GROUPS = ("all", "T1", "T2", "T3")


def rj(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def items():
    idx = json.load(open(os.path.join(P1, "prompts", "INDEX.json")))["items"]
    tiers = json.load(open(os.path.join(PV0, "ev" + "al", "tiers.json")))["items"]
    out = OrderedDict()
    for t, v in idx.items():
        if v.get("excluded"):
            continue
        out[t] = "T3" if v.get("strict_cell") else tiers[t]["tier"]
    return out


def score_map(path):
    return {(r["task"], r["key"], r["seed"]): r for r in rj(path)}


def train_wls(sft_file):
    ex = {}
    for e in rj(os.path.join(PV0, "data", "train-all.jsonl")):
        ex[e["id"]] = e["target_wl"]
    return {ex[r["id"]] for r in rj(sft_file)}


def all_train_wls():
    return {e["target_wl"] for e in rj(os.path.join(PV0, "data", "train-all.jsonl"))}


def copy_rate(comps, wls):
    """own = the model's own training targets (decision rule); any = any of pilot-v0's 1013
    training targets (the pilot-v0 README convention: zs 1/111 ... sft1000 46/115)."""
    v = [c for c in comps if c.get("valid")]
    n = sum(1 for c in v if c.get("wl") in wls)
    aw = all_train_wls()
    na = sum(1 for c in v if c.get("wl") in aw)
    return OrderedDict(copies=n, valid=len(v), rate=round(n / len(v), 4) if v else None,
                       copies_any_train=na, rate_any_train=round(na / len(v), 4) if v else None,
                       distinct_wl=len({c.get("wl") for c in v}))


def passk(n, c, k):
    if n < k:
        return None
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


TRAIN_SETS = {"h1-sft300": os.path.join(P1, "sft-data", "sft-300.jsonl"),
              "h1-sft1000": os.path.join(P1, "sft-data", "sft-1000.jsonl"),
              "sft300": os.path.join(P1, "sft-data", "sft-300.jsonl"),
              "sft1000": os.path.join(P1, "sft-data", "sft-1000.jsonl")}


def h1(labels):
    it = items()
    sm = score_map(os.path.join(SC, "score.jsonl"))
    res = OrderedDict(prereg="kaggle/PREREG-PILOT-V1.md (e46157ccf) H1", labels=labels, models=OrderedDict())
    L = []
    missing = 0
    for lab in labels:
        comps = rj(os.path.join(SC, lab, "completions.jsonl"))
        by = defaultdict(list)
        for c in comps:
            by[c["task"]].append(c)
        per = OrderedDict()
        for t, tier in it.items():
            cs = sorted(by.get(t, []), key=lambda c: c["sample"])
            p1, conf, feas_keys = 0, 0, set()
            for c in cs:
                if not c.get("valid"):
                    continue
                r1 = sm.get((t, c["key"], 1))
                if r1 is None:
                    missing += 1
                    continue
                if r1.get("feasible"):
                    p1 += 1
                    feas_keys.add(c["key"])
                    r2, r3 = sm.get((t, c["key"], 2)), sm.get((t, c["key"], 3))
                    if r2 is None or r3 is None:
                        missing += 1
                    if bool(r2 and r2.get("feasible")) or bool(r3 and r3.get("feasible")):
                        conf += 1
            per[t] = OrderedDict(tier=tier, n=len(cs), n_valid=sum(1 for c in cs if c.get("valid")),
                                 c_seed1=p1, c_confirmed=conf, distinct_feasible_keys=len(feas_keys),
                                 distinct_wl=len({c.get("wl") for c in cs if c.get("valid")}))
        groups = OrderedDict()
        for g in GROUPS:
            rows = [r for r in per.values() if g == "all" or r["tier"] == g]
            ag = OrderedDict(n_items=len(rows), samples=sum(r["n"] for r in rows),
                             min_n=min(r["n"] for r in rows) if rows else None)
            for crit, key in (("seed1", "c_seed1"), ("confirmed", "c_confirmed")):
                d = OrderedDict()
                for k in KS:
                    vals = [passk(r["n"], r[key], k) for r in rows]
                    vals = [v for v in vals if v is not None]
                    d["pass@%d" % k] = round(sum(vals) / len(vals), 4) if vals else None
                    d["n_items@%d" % k] = len(vals)
                d["coverage"] = sum(1 for r in rows if r[key] > 0)
                ag[crit] = d
            hist = Counter(r["c_seed1"] for r in rows)
            ag["freq_hist_c_seed1"] = {str(k): hist[k] for k in sorted(hist)}
            groups[g] = ag
        a = groups["all"]["seed1"]
        ratio = (a["pass@8"] / a["pass@1"]) if a["pass@1"] and a["pass@8"] is not None else None
        reading = (None if ratio is None else
                   "strong verifier-selection headroom (pass@8 >= 1.5 x pass@1)" if ratio >= 1.5 else
                   "narrow distribution (pass@8 ~ pass@1)" if ratio <= 1.1 else
                   "intermediate (1.1 < pass@8/pass@1 < 1.5)")
        sfile = TRAIN_SETS.get(lab)
        n_s1 = sum(r["c_seed1"] for r in per.values())
        n_cf = sum(r["c_confirmed"] for r in per.values())
        res["models"][lab] = OrderedDict(
            groups=groups, ratio_pass8_over_pass1=round(ratio, 3) if ratio else None, reading=reading,
            completions=len(comps), valid=sum(1 for c in comps if c.get("valid")),
            seed1_feasible_samples=n_s1, confirmed_samples=n_cf,
            confirmation_rate=round(n_cf / n_s1, 4) if n_s1 else None,
            copy=copy_rate(comps, train_wls(sfile)) if sfile else None,
            per_item=per)
        L.append("### %s — %d completions, %d valid; seed-1-feasible samples %d, confirmed at a 2nd seed %d" % (
            lab, len(comps), res["models"][lab]["valid"], n_s1, n_cf))
        L.append("")
        L.append("| group | items | pass@1 | pass@2 | pass@4 | pass@8 | coverage | pass@1 conf. | pass@8 conf. | coverage conf. |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for g, ag in groups.items():
            s, c = ag["seed1"], ag["confirmed"]
            L.append("| %s | %d | %s | %s | %s | %s | %d | %s | %s | %d |" % (
                g, ag["n_items"], s["pass@1"], s["pass@2"], s["pass@4"], s["pass@8"], s["coverage"],
                c["pass@1"], c["pass@8"], c["coverage"]))
        L.append("")
        L.append("pass@8 / pass@1 = %s -> %s; per-item c (of n) histogram: %s; copy rate %s" % (
            res["models"][lab]["ratio_pass8_over_pass1"], reading,
            json.dumps(groups["all"]["freq_hist_c_seed1"]), json.dumps(res["models"][lab]["copy"])))
        L.append("")
    res["missing_score_rows"] = missing
    if len(labels) == 2:
        a, b = (res["models"][l]["per_item"] for l in labels)
        sa = {t for t, r in a.items() if r["c_seed1"]}
        sb = {t for t, r in b.items() if r["c_seed1"]}
        res["overlap"] = OrderedDict(both=len(sa & sb), union=len(sa | sb), only_first=len(sa - sb),
                                     only_second=len(sb - sa))
        L.append("Coverage overlap (seed 1): " + json.dumps(res["overlap"]))
    json.dump(res, open(os.path.join(SC, "h1-summary.json"), "w"), indent=1)
    open(os.path.join(SC, "h1-tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print("missing score rows:", missing)


def m1(label):
    it = items()
    sm = score_map(os.path.join(SC, "score.jsonl"))
    comps = rj(os.path.join(SC, label, "completions.jsonl"))
    by = defaultdict(list)
    for c in comps:
        by[c["task"]].append(c)
    missing = 0
    per = OrderedDict()
    for t, tier in it.items():
        cs = sorted(by.get(t, []), key=lambda c: c["sample"])
        feas = {}
        for c in cs:
            if c.get("valid"):
                f = []
                for s in (1, 2, 3):
                    r = sm.get((t, c["key"], s))
                    if r is None:
                        missing += 1
                    f.append(bool(r and r.get("feasible")))
                feas[c["sample"]] = f
        per[t] = OrderedDict(tier=tier, n=len(cs), n_valid=sum(1 for c in cs if c.get("valid")),
                             seeds_feasible={str(k): v for k, v in feas.items()},
                             solved=any(any(f) for f in feas.values()),
                             solved_2of3=any(sum(f) >= 2 for f in feas.values()))
    pv0s = json.load(open(os.path.join(P1, "score", "summary.json")))
    mix = json.load(open(os.path.join(HERE, "sft-data", "MIX.json")))
    mix_file = os.path.join(REPO, mix["sft_file"])
    rows = OrderedDict()
    for g in GROUPS:
        sel = [r for r in per.values() if g == "all" or r["tier"] == g]
        nc = sum(r["n"] for r in sel)
        nv = sum(r["n_valid"] for r in sel)
        rows[g] = OrderedDict(n_tasks=len(sel), solved=sum(1 for r in sel if r["solved"]),
                              solved_2of3=sum(1 for r in sel if r["solved_2of3"]),
                              validity=round(nv / nc, 3) if nc else None, valid=nv, completions=nc)
    copies = OrderedDict()
    for lab in ("sft300", "sft1000"):
        copies[lab] = copy_rate(rj(os.path.join(P1, "score", lab, "completions.jsonl")), train_wls(TRAIN_SETS[lab]))
    copies[label] = copy_rate(comps, train_wls(mix_file))
    G = pv0s["groups"]
    t2_gain = rows["T2"]["solved"] - G["sft1000"]["T2"]["solved"]
    t1_loss = G["sft1000"]["T1"]["solved"] - rows["T1"]["solved"]
    cm, c1 = copies[label]["rate"], copies["sft1000"]["rate"]
    dec = OrderedDict(t2_gain_vs_sft1000=t2_gain, t1_loss_vs_sft1000=t1_loss,
                      copy_rate_mix=cm, copy_rate_sft1000=c1,
                      cond_t2=t2_gain >= 3, cond_t1=t1_loss < 3, cond_copy=(cm is not None and cm < c1 / 2),
                      t2_gain_vs_sft300=rows["T2"]["solved"] - G["sft300"]["T2"]["solved"],
                      t1_loss_vs_sft300=G["sft300"]["T1"]["solved"] - rows["T1"]["solved"])
    dec["works"] = dec["cond_t2"] and dec["cond_t1"] and dec["cond_copy"]
    sol = {t for t, r in per.items() if r["solved"]}
    ov = OrderedDict()
    for lab in ("sft300", "sft1000"):
        so = {t for t, r in pv0s["per_task"][lab].items() if r["solved"]}
        ov[lab] = OrderedDict(both=len(sol & so), union=len(sol | so), only_mix=len(sol - so), only_other=len(so - sol))
    res = OrderedDict(prereg="kaggle/PREREG-PILOT-V1.md (e46157ccf) M1", label=label, n_train=mix["n"],
                      groups=rows, copy=copies, decision=dec, overlap_solved=ov,
                      missing_score_rows=missing, per_task=per)
    json.dump(res, open(os.path.join(SC, "m1-summary.json"), "w"), indent=1)
    L = ["| model | train ex. | solved | >= 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | T1/T2/T3 >= 2/3 | validity | copy rate: own training targets | copy: any pilot-v0 training target | distinct WLs |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for lab, ntr, gg in (("sft300", 298, G["sft300"]), ("sft1000", 994, G["sft1000"]), (label, mix["n"], rows)):
        cp = copies[lab]
        L.append("| %s | %d | %d | %d | %d | %d | %d | %d/%d/%d | %s | %d/%d = %s | %d/%d | %d |" % (
            lab, ntr, gg["all"]["solved"], gg["all"]["solved_2of3"], gg["T1"]["solved"], gg["T2"]["solved"],
            gg["T3"]["solved"], gg["T1"]["solved_2of3"], gg["T2"]["solved_2of3"], gg["T3"]["solved_2of3"],
            gg["all"]["validity"], cp["copies"], cp["valid"], cp["rate"], cp["copies_any_train"], cp["valid"],
            cp["distinct_wl"]))
    L.append("")
    L.append("Decision: " + json.dumps(dec))
    L.append("Solved overlap: " + json.dumps(ov))
    open(os.path.join(SC, "m1-tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))
    print("missing score rows:", missing)


if __name__ == "__main__":
    if sys.argv[1] == "h1":
        h1(sys.argv[2].split(","))
    else:
        m1(sys.argv[2])
