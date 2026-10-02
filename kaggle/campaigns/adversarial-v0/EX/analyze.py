"""EX analysis: search stats, exploit instances, mechanism classes, guard impact on
bench-v2 accepted cells / training witnesses, R-d/R-e fragility table.

usage: analyze.py <seeds raw dir> <state dir> <out summary.json>
Reads bench-v2/run/cells.jsonl READ-ONLY for the current accepted-cell list.
Class assignment is by the mechanism tags computed here (see classify());
the physical explanation of each class lives in README.md.
"""
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
RUN = f"{REPO}/kaggle/campaigns/bench-v2/run"
MATERIAL = 0.02


def load(seeds_dir, state):
    seeds = []
    for f in sorted(os.listdir(seeds_dir)):
        if f.endswith(".json"):
            r = json.load(open(f"{seeds_dir}/{f}"))
            r["did"] = r["sid"]
            r["is_seed"] = True
            seeds.append(r)
    kids = []
    p = f"{state}/results.jsonl"
    if os.path.exists(p):
        for ln in open(p):
            c = json.loads(ln)
            c["is_seed"] = False
            kids.append(c)
    return seeds, kids


def fail_tags(s):
    """Material reality-check failures of one design summary -> list of tags."""
    tags = []
    if not s:
        return tags
    for k in ("P1", "P2"):
        x = (s.get("Ra") or {}).get(k) or {}
        if x.get("mag", 0) > MATERIAL:
            tags.append(f"Ra-{k}:{x.get('worst')}")
    rb = s.get("Rb") or {}
    if rb.get("linear_osc"):
        tags.append("Rb:linear" + (":r50/r50" if "r50/r50" in rb["linear_osc"] else ":reactive"))
    rc = s.get("Rc") or {}
    if rc.get("mag", 0) > MATERIAL:
        tags.append(f"Rc:{rc.get('worst')}")
    return tags


def classify(tags):
    """Mechanism class of a design from its fail tags (one design may be in several)."""
    cls = set()
    for t in tags:
        if t.startswith("Rb:linear:r50/r50"):
            cls.add("C-osc50: oscillates in the verifier's own 50-ohm bench (internal loop)")
        elif t.startswith("Rb:linear"):
            cls.add("C-oscX: oscillates only under reactive terminations")
        elif t.startswith("Ra-P1") or t.startswith("Ra-P2"):
            cls.add("C-cp1: performance depends on the harness 10 pF input DC block")
        elif t.startswith("Rc:mu"):
            cls.add("C-grid-mu: mu<1 between the verifier's wide-mu grid points")
        elif t.startswith("Rc:"):
            cls.add("C-grid-band: band metric violated between the verifier's grid points")
    return sorted(cls)


def main(seeds_dir, state, out):
    seeds, kids = load(seeds_dir, state)
    sized = [k for k in kids if k.get("sized")]
    allp = [d for d in seeds + sized if d.get("verifier_pass") and d.get("summary")]
    stats = {
        "seeds": {"n": len(seeds), "verifier_pass": sum(bool(s.get("verifier_pass")) for s in seeds),
                  "reproduced": sum(bool(s.get("reproduced")) for s in seeds),
                  "by_origin": dict(Counter(s["origin"] for s in seeds))},
        "search": {"children_generated": len(kids), "sized": len(sized),
                   "pre_sizing_rejects": dict(Counter(k["why"].split(":")[0]
                                                      for k in kids if not k.get("sized"))),
                   "verifier_pass": sum(bool(k.get("verifier_pass")) for k in sized),
                   "not_sizable": sum(1 for k in sized if k.get("sizable") is False),
                   "infeasible_reasons": dict(Counter(
                       ((k.get("res") or {}).get("infeasible_reason") or "spec/stability")
                       .split(":")[0][:40] for k in sized if not k.get("verifier_pass"))),
                   "gens": sum(1 for _ in open(f"{state}/gens.jsonl")) if os.path.exists(
                       f"{state}/gens.jsonl") else 0},
    }
    inst = []
    for d in allp:
        tags = fail_tags(d["summary"])
        if not tags:
            continue
        inst.append({"did": d["did"], "seed": d["is_seed"], "root": d.get("root") or d["did"],
                     "spec": os.path.basename(d["spec"]), "tags": tags, "classes": classify(tags),
                     "mags": d["summary"]["mags"], "kinds": d.get("kinds"),
                     "meta": d.get("meta"), "parent": d.get("parent")})
    classes = defaultdict(list)
    for i in inst:
        for c in i["classes"]:
            classes[c].append(i)
    cls_out = {}
    for c, L in sorted(classes.items()):
        roots = sorted({i["root"] for i in L})
        cls_out[c] = {"n_instances": len(L), "n_independent_roots": len(roots),
                      "n_seed_instances": sum(i["seed"] for i in L),
                      "n_search_instances": sum(not i["seed"] for i in L),
                      "qualifies": len(roots) >= 2,
                      "instances": [i["did"] for i in L]}
    # guard impact: accepted bench-v2 cells and rl-v1.1 training witnesses (seeds)
    acc = set()
    for ln in open(f"{RUN}/cells.jsonl"):
        c = json.loads(ln)
        if c.get("status") == "accepted":
            acc.add(c["name"])
    acc_seeds = [s for s in seeds if (s.get("meta") or {}).get("cell") in acc
                 and "A1" in (s.get("kinds") or [])]
    wit = [s for s in seeds if "T-wit" in (s.get("kinds") or [])]
    impact = {}
    for c in cls_out:
        impact[c] = {
            "accepted_cells": sorted({(s.get("meta") or {}).get("cell") for s in acc_seeds
                                      if c in classify(fail_tags(s.get("summary")))}),
            "n_accepted_cells_total": len(acc),
            "training_witnesses": sorted({(s.get("meta") or {}).get("task") for s in wit
                                          if c in classify(fail_tags(s.get("summary")))}),
            "n_training_witnesses_total": len({(s.get("meta") or {}).get("task") for s in wit})}
    # fragility (R-d / R-e)
    frag = {}
    for grp, L in (("seeds", [d for d in allp if d["is_seed"]]),
                   ("search", [d for d in allp if not d["is_seed"]])):
        row = {"n": len(L)}
        for k in ("T-40", "T85", "V0.9", "V1.1"):
            v = [((d["summary"].get("Rde") or {}).get(k) or {}) for d in L]
            row[k] = {"perf_within_cushion": sum(bool(x.get("perf_ok")) for x in v),
                      "stable": sum(bool(x.get("stable")) for x in v),
                      "both": sum(bool(x.get("perf_ok") and x.get("stable")) for x in v)}
        row["all_4_corners_ok"] = sum(all(((d["summary"].get("Rde") or {}).get(k) or {}).get("perf_ok")
                                          and ((d["summary"].get("Rde") or {}).get(k) or {}).get("stable")
                                          for k in ("T-40", "T85", "V0.9", "V1.1")) for d in L)
        frag[grp] = row
    res = {"stats": stats, "n_verifier_pass_with_checks": len(allp),
           "n_exploit_designs": len(inst),
           "check_fail_counts": dict(Counter(t.split(":")[0] for i in inst for t in i["tags"])),
           "classes": cls_out, "guard_impact": impact,
           "accepted_cells_now": sorted(acc), "fragility": frag, "instances": inst}
    json.dump(res, open(out, "w"), indent=1, default=repr)
    print(json.dumps({k: res[k] for k in ("stats", "n_verifier_pass_with_checks",
                                          "n_exploit_designs", "check_fail_counts")}, indent=1))
    for c, v in cls_out.items():
        print(c, {k: v[k] for k in v if k != "instances"}, impact[c]["accepted_cells"],
              len(impact[c]["training_witnesses"]))
    print(json.dumps(frag, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
