#!/usr/bin/env python
"""baselines-v1 add-on (not pre-registered, no new sims): solve rate at budget B of the blind random-order
search bar (pilot-v0/eval/searchbar.json), stage-wise like E-c: T1 = random order over the library anchors'
seed-1 sized calls; T2 = random order over the shown anchor's sized single edits at seed 1 (seed-2 re-tries
ignored => conservative). P(solved within B) = 1 - C(N-K, B) / C(N, B). T3 has no bar (0 by construction of the
single-edit space). Note the blind bar is told WHERE to search (library for T1, single edits of the shown anchor
for T2) — knowledge of the bench construction neither the GA nor the LLMs get explicitly."""
import json
import os
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(HERE, "..", "pilot-v0", "eval", "searchbar.json")
BS = (1, 2, 4, 8, 16, 32, 64)


def p_within(n, k, b):
    if k <= 0:
        return 0.0
    b = min(b, n)
    return 1.0 - comb(n - k, b) / comb(n, b)


def main():
    it = json.load(open(SB))["items"]
    rows = {"T1": [], "T2": [], "T3": []}
    for t, x in it.items():
        if x["tier"] == "T1":
            rows["T1"].append([p_within(x["n_sized"], x["n_feasible"], b) for b in BS])
        elif x["tier"] == "T2":
            rows["T2"].append([p_within(x["n_sized"], x["n_feasible_s1"], b) for b in BS])
        else:
            rows["T3"].append([0.0 for b in BS])
    out = {}
    allr = rows["T1"] + rows["T2"] + rows["T3"]
    for g, rr in (("all", allr), ("T1", rows["T1"]), ("T2", rows["T2"]), ("T3", rows["T3"])):
        out[g] = {"n": len(rr), **{"blind@%d" % b: round(sum(r[i] for r in rr) / len(rr), 4) for i, b in enumerate(BS)}}
    json.dump(out, open(os.path.join(HERE, "blind-curve.json"), "w"), indent=1)
    L = ["| group | n | " + " | ".join("blind@%d" % b for b in BS) + " |", "|---|---|" + "---|" * len(BS)]
    for g, d in out.items():
        L.append("| %s | %d | " % (g, d["n"]) + " | ".join(str(d["blind@%d" % b]) for b in BS) + " |")
    open(os.path.join(HERE, "blind-curve.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
