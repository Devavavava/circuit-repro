#!/usr/bin/env python
"""baselines-v1 part O summary (kaggle/PREREG-BASELINES-V1.md): Opus (4 samples x 58) vs sft-r1 at the
same k, H1 protocol (pass = valid & feasible at seed 1, rl-v1.2) and the 2-sample protocol (samples 1-2,
feasible at >= 1 of seeds 1-3). Reuses exit-r1/r1_summarize.py (h1_model, two_model, boot_pass1).
-> opus/opus-tables.md, opus/opus-summary.json"""
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "kaggle", "campaigns", "exit-r1"))
import r1_summarize as RS  # noqa: E402

SC = os.path.join(HERE, "score")
KS = (1, 2, 4)


def main():
    S = RS._pv1()                      # sets PV1_SCORE_DIR to exit-r1/score; only S.items/score_map/passk used
    it = S.items()
    sm_o = S.score_map(os.path.join(SC, "score.jsonl"))
    sm_r = S.score_map(os.path.join(RS.SCR, "score.jsonl"))
    co4 = RS.rj(os.path.join(SC, "opus-4", "completions.jsonl"))
    co2 = RS.rj(os.path.join(SC, "opus-2", "completions.jsonl"))
    cr8 = RS.rj(os.path.join(RS.SCR, "r1-8", "completions.jsonl"))
    cr2 = RS.rj(os.path.join(RS.SCR, "r1-2", "completions.jsonl"))
    cr4 = [c for c in cr8 if c["sample"] <= 4]          # sft-r1 samples 1-4: same k, same n as Opus
    res = OrderedDict(prereg="kaggle/PREREG-BASELINES-V1.md part O", h1=OrderedDict(), two_sample=OrderedDict(),
                      missing=OrderedDict())
    per = {}
    for lab, comps, sm in (("opus", co4, sm_o), ("sft-r1 (samples 1-4)", cr4, sm_r)):
        g, p, miss = RS.h1_model(S, comps, sm, {}, it)
        res["h1"][lab], per[lab] = g, p
        res["missing"]["h1:" + lab] = {k: v for k, v in miss.items() if k != "kick"}
    for lab, comps, sm in (("opus", co2, sm_o), ("sft-r1", cr2, sm_r)):
        g, p, miss = RS.two_model(comps, sm, {}, it)
        res["two_sample"][lab] = g
        res["missing"]["2s:" + lab] = {k: v for k, v in miss.items() if k != "kick"}
    res["bootstrap_pass1_opus_minus_sftr1"] = RS.boot_pass1(per["opus"], per["sft-r1 (samples 1-4)"])
    cov = {lab: {t for t, r in p.items() if r["c"]} for lab, p in per.items()}
    res["coverage_any_of_4"] = {lab: len(v) for lab, v in cov.items()}
    res["opus_only"] = sorted(cov["opus"] - cov["sft-r1 (samples 1-4)"])
    res["sftr1_only"] = sorted(cov["sft-r1 (samples 1-4)"] - cov["opus"])
    v = [c for c in co4 if c.get("valid")]
    res["opus_validity"] = "%d/%d" % (len(v), len(co4))
    res["opus_any_anchor"] = sum(1 for c in v if c.get("is_any_anchor"))
    res["opus_distinct_keys"] = len({(c["task"], c.get("key")) for c in v})
    res["per_item_h1"] = per
    json.dump(res, open(os.path.join(HERE, "opus-summary.json"), "w"), indent=1)
    L = ["### H1 protocol, k <= 4 (pass = valid & feasible at seed 1, rl-v1.2)", "",
         "| model | group | pass@1 | pass@2 | pass@4 | coverage@4 |", "|---|---|---|---|---|---|"]
    for lab in res["h1"]:
        for grp in ("all",) + RS.TIERS:
            a = res["h1"][lab][grp]["rl-v1.2"]
            L.append("| %s | %s (%d) | %s | %s | %s | %d |" % (lab, grp, res["h1"][lab][grp]["n_items"],
                                                             a["pass@1"], a["pass@2"], a["pass@4"], a["coverage"]))
    L += ["", "### 2-sample protocol (samples 1-2; feasible at >= 1 of seeds 1-3)", "",
          "| model | solved | >= 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | validity |", "|---|---|---|---|---|---|---|"]
    for lab, x in res["two_sample"].items():
        L.append("| %s | %d | %d | %d | %d | %d | %s |" % (lab, x["all"]["solved"], x["all"]["solved_2of3"],
                 x["T1"]["solved"], x["T2"]["solved"], x["T3"]["solved"], x["all"]["validity"]))
    L += ["", "Bootstrap pass@1 (opus - sft-r1 samples 1-4): " + json.dumps(res["bootstrap_pass1_opus_minus_sftr1"]),
          "Coverage any of 4: " + json.dumps(res["coverage_any_of_4"]),
          "Opus-only tasks: " + json.dumps(res["opus_only"]), "sft-r1-only tasks: " + json.dumps(res["sftr1_only"]),
          "Opus validity %s; answers equal to a library anchor: %d; distinct (task, topology): %d" % (
              res["opus_validity"], res["opus_any_anchor"], res["opus_distinct_keys"]),
          "Missing rows: " + json.dumps(res["missing"])]
    open(os.path.join(HERE, "opus-tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
