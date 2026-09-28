"""Summarize the rl-v1 difficulty re-check (b) and loophole re-check (c).

usage: summarize.py <results.json>   -> summary.json, tables.md (next to this file)

Baselines (same candidates, same 3 seeds x 2500 evals, bptm45):
  gate   : stability-gate campaign (stab spec, post-hoc 0.1-20 GHz gate only)
  inloop : S-1 (wb template + E-c picks) and R4 tag `nb` (nb template + a1),
           stab spec + STAB_WIDE_INLOOP=1, 0.1-20 GHz window, library metrics
rl-v1 cause of a failing run (final result):
  topo / struct       pre-sizing reject (infeasible_reason)
  W5 band NF          final winner violates nf_max_db
  band S11 (W6 if nb) final winner violates s11_max_db (new for nb = W6; wb specs always had it)
  wide mu 0.01-50GHz  spec-feasible but wide-unstable over the rl-v1 window
  in-band mu / legacy other violated constraints (mu_min, s21_db, idd_ma, nf_db, ...)
Static attribution (attrib.json): each baseline in-loop FEASIBLE winner (same
design, no re-sizing) re-checked against every rl-v1 piece.
"""
import sys, os, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
AUD = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/"
R4 = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/rl-readiness/R4/"
A1 = "anchor:lna-a1-inddegen-cascode"
CAUSE = {"nf_max_db": "W5 band NF", "s11_max_db": "band S11 (W6 if nb)", "mu_min": "in-band mu",
         "s21_db": "s21", "idd_ma": "idd", "nf_db": "nf@f0", "s21_ripple_db": "ripple"}


def cause_of(row):
    r = row["result"] or {}
    if r.get("feasible"):
        return []
    why = r.get("infeasible_reason") or ""
    if why.startswith("topology limits"):
        return ["topo:" + why.split(": ", 1)[1]]
    if why.startswith("structural"):
        return ["struct:" + ",".join(sorted((r.get("structural_degeneracy") or {})))]
    out = [CAUSE.get(k, k) for k in (row.get("spec_violations") or {})]
    if r.get("spec_feasible") and r.get("stab_wide_ok") is False:
        out.append("wide mu 0.01-50GHz")
    if why:
        out.append("posthoc:" + why)
    return out or ["?"]


def pat(rows, key=lambda r: bool(r)):
    return "".join("F" if key(x) else "x" for x in rows)


def main(resp):
    rows = json.load(open(resp))["rows"]
    diff = [r for r in rows if r["tag"] == "diff"]
    loop = [r for r in rows if r["tag"] == "loop"]
    sg = json.load(open(AUD + "stability-gate/results.json"))["rows"]
    s1 = json.load(open(AUD + "S-1-stab-inloop/results.json"))["rows"]
    r4 = json.load(open(R4 + "results.json"))["rows"]
    att = json.load(open(HERE + "/attrib.json"))

    def base_gate(cell, cand, seed):
        c = "lna-a1-inddegen-cascode" if cand == A1 else cand
        if cand.startswith("ec:"):
            m = [x for x in s1 if x["cell"] == cell and x["cand"] == cand and x["mode"] == "gate"
                 and x["seed"] == seed and x["exp"] == "ec"]
        else:
            m = [x for x in sg if x["cell"] == cell and x["cand"] == c and x["specmode"] == "stab"
                 and x["seed"] == seed]
        return bool(m[0]["feasible"]) if m else None

    def base_inloop(cell, cand, seed):
        if "-nb-" in cell:
            m = [x for x in r4 if x["tag"] == "nb" and x["cell"] == cell and x["cand"] == cand
                 and x["seed"] == seed]
            return bool((m[0]["result"] or {}).get("feasible")) if m else None
        m = [x for x in s1 if x["cell"] == cell and x["cand"] == cand and x["mode"] == "inloop"
             and x["seed"] == seed and x["exp"] in ("tpl", "ec")]
        return bool(m[0]["feasible"]) if m else None

    per = collections.defaultdict(list)
    for r in diff:
        per[(r["cell"], r["cand"])].append(r)
    table, groups = [], collections.defaultdict(lambda: collections.Counter())
    csets = collections.defaultdict(lambda: collections.defaultdict(set))
    for (cell, cand), rs in sorted(per.items()):
        rs.sort(key=lambda r: r["seed"])
        seeds = [r["seed"] for r in rs]
        g = [base_gate(cell, cand, s) for s in seeds]
        il = [base_inloop(cell, cand, s) for s in seeds]
        v1 = [bool((r["result"] or {}).get("feasible")) for r in rs]
        causes = collections.Counter(c for r in rs for c in cause_of(r))
        st = [a for a in att if a["cell"] == cell and a["cand"] == cand and a["baseline_final_feasible"]]
        st_fail = collections.Counter(f.split("(")[0] for a in st for f in a["rlv1_fails"])
        grp = ("nb template" if cand == "template" and "-nb-" in cell else
               "wb template" if cand == "template" else
               "nb a1" if cand == A1 else "wb E-c (S-1 picks)")
        rec = {"cell": cell, "cand": cand, "group": grp, "seeds": seeds,
               "gate": pat(g), "inloop": pat(il), "rlv1": pat(v1),
               "rlv1_causes": dict(causes),
               "static_baseline_winners": len(st),
               "static_pass_rlv1": sum(a["rlv1_pass"] for a in st),
               "static_fail_checks": dict(st_fail),
               "inert_counts": [(r["result"] or {}).get("n_inert_devices") for r in rs],
               "nf_max_db": [((r["result"] or {}).get("metrics") or {}).get("nf_max_db") for r in rs],
               "s11_max_db": [((r["result"] or {}).get("metrics") or {}).get("s11_max_db") for r in rs],
               "mu_min_wide": [(r["result"] or {}).get("mu_min_wide") for r in rs],
               "secs": [r["secs"] for r in rs]}
        table.append(rec)
        band = "nb" if "-nb-" in cell else "wb"
        for gname in (grp, f"{band} ANY candidate"):
            G, C = groups[gname], csets[gname]
            G["pairs"] += 1
            G["runs"] += len(rs)
            G["gate_F"] += sum(bool(x) for x in g)
            G["inloop_F"] += sum(bool(x) for x in il)
            G["rlv1_F"] += sum(v1)
            C["cells"].add(cell)
            for k, v in (("gate", g), ("inloop", il), ("rlv1", v1)):
                if any(v):
                    C[k].add(cell)
    for gname, C in csets.items():
        G = groups[gname]
        G["cells"] = len(C["cells"])
        for k in ("gate", "inloop", "rlv1"):
            G[k + "_cells"] = len(C[k])
        G["lost_cells"] = sorted(c[4:] for c in C["inloop"] - C["rlv1"])
        G["gained_cells"] = sorted(c[4:] for c in C["rlv1"] - C["inloop"])
        G["rlv1_cell_list"] = sorted(c[4:] for c in C["rlv1"])
    # (c) loophole re-check
    r4mut = {(x["cand"][4:], x["cell"]): x["result"] for x in r4 if x["tag"] == "mut" and x["seed"] == 1}
    lp = []
    for r in sorted(loop, key=lambda r: (r["cand"], r["cell"])):
        res = r["result"] or {}
        name = r["cand"][4:]
        old = r4mut.get((name, r["cell"]))
        tpl = [x for x in diff if x["cell"] == r["cell"] and x["cand"] == "template"
               and x.get("sizable")]
        junk = sorted(set(r.get("sizable") or {}) - set(tpl[0]["sizable"])) if tpl else None
        lp.append({"mutant": name, "cell": r["cell"],
                   "junk_sized_devices": junk,
                   "junk_flagged_inert": (sorted(set(junk or []) & set(res.get("inert_devices") or []))
                                          if res.get("feasible") else None),
                   "r4_inloop_feasible": (old or {}).get("feasible") if old else None,
                   "rlv1_feasible": res.get("feasible"),
                   "rlv1_reason": res.get("infeasible_reason"),
                   "n_evals": res.get("n_evals"),
                   "inert_devices": res.get("inert_devices"),
                   "n_inert_devices": res.get("n_inert_devices"),
                   "causes": cause_of(r), "secs": r["secs"]})
    secs = [r["secs"] for r in diff if (r["result"] or {}).get("n_evals")]
    summ = {"groups": {k: dict(v) for k, v in groups.items()}, "per_cell": table,
            "loop": lp, "median_secs_rlv1_sized": sorted(secs)[len(secs) // 2] if secs else None}
    json.dump(summ, open(HERE + "/summary.json", "w"), indent=1)

    L = ["## (b) difficulty under rl-v1 (rl-v1-form specs, profile rl-v1, seeds 1,2,3 x 2500)", "",
         "F = final feasible (spec incl. in-band mu, AND wide mu >= 1). gate = stability-gate "
         "(0.1-20 GHz, post-hoc), inloop = S-1 / R4-nb (0.1-20 GHz in-loop, library metrics).", "",
         "Runs F / runs; (cells) = distinct cells with >= 1 F run.", "",
         "| group | cells | runs | gate F (cells) | inloop F (cells) | **rl-v1 F (cells)** | cells lost vs inloop | gained |",
         "|---|---|---|---|---|---|---|---|"]
    for k in ("nb template", "nb a1", "nb ANY candidate", "wb template", "wb E-c (S-1 picks)",
              "wb ANY candidate"):
        G = groups.get(k)
        if G:
            L.append(f"| {k} | {G['cells']} | {G['runs']} | {G['gate_F']} ({G['gate_cells']}) | "
                     f"{G['inloop_F']} ({G['inloop_cells']}) | **{G['rlv1_F']} ({G['rlv1_cells']})** | "
                     f"{', '.join(G['lost_cells']) or '-'} | {', '.join(G['gained_cells']) or '-'} |")
    L += ["", "| cell | cand | gate | inloop | rl-v1 | rl-v1 failing-run causes | baseline winners pass rl-v1 as-is | their failing checks | inert (per seed) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for t in table:
        cs = ", ".join(f"{k}x{v}" for k, v in sorted(t["rlv1_causes"].items())) or "-"
        sf = ", ".join(f"{k}x{v}" for k, v in sorted(t["static_fail_checks"].items())) or "-"
        L.append(f"| {t['cell'][4:]} | {t['cand'].replace(A1, 'a1')} | {t['gate']} | {t['inloop']} | "
                 f"**{t['rlv1']}** | {cs} | {t['static_pass_rlv1']}/{t['static_baseline_winners']} | {sf} | "
                 f"{t['inert_counts']} |")
    L += ["", "## (c) loophole re-check: R4 junk add-on mutants under rl-v1 (seed 1)", "",
          "| mutant | cell | R4 inloop feasible | rl-v1 feasible | caught by / cause | n_evals | inert devices (W2) | junk device(s) flagged inert |",
          "|---|---|---|---|---|---|---|---|"]
    for x in lp:
        L.append(f"| {x['mutant']} | {x['cell'][4:]} | {x['r4_inloop_feasible']} | {x['rlv1_feasible']} | "
                 f"{', '.join(x['causes']) or '-'} | {x['n_evals']} | {x['inert_devices']} | "
                 f"{x['junk_flagged_inert'] if x['rlv1_feasible'] else '-'} (junk: {x['junk_sized_devices']}) |")
    open(HERE + "/tables.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1])
