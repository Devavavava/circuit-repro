"""summarize.py: results.json (+ regress.json) -> tables.md + summary.json."""
import os, json, statistics as st
from collections import defaultdict, OrderedDict
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json")))
REG = json.load(open(os.path.join(HERE, "regress.json")))
rows = R["rows"]
picks = R["ec_picks"]
desc = {"ec:" + p["cid"]: p["desc"] for ps in picks.values() for p in ps}


def cname(c):
    return desc.get(c, c)


def flag(r):
    if r.get("feasible"):
        return "F"
    if r.get("spec_feasible"):
        return "s"
    return "x"


def f2(v):
    return "-" if v is None else f"{v:.2f}"


def joint_viol(r):
    """sum of normalized in-band shortfalls (from margins) + wide mu shortfall."""
    v = sum(-m for m in (r.get("margins") or {}).values()
            if isinstance(m, (int, float)) and m < 0)
    mw = r.get("mu_min_wide")
    v += max(0.0, 1.0 - mw) if isinstance(mw, (int, float)) else 1.0
    return v


main = [r for r in rows if r["exp"] in ("tpl", "ec", "anchors")]
by = defaultdict(lambda: {"gate": {}, "inloop": {}})
for r in main:
    by[(r["exp"], r["cell"], r["cand"])][r["mode"]][r["seed"]] = r

L = []
L.append("## (a) Regression: flags-off byte-identity vs recorded stability-gate rows\n")
L.append("Full `json.dumps(result, sort_keys=True)` equality against "
         "`../stability-gate/results.json`.\n")
L.append("| exp | cell | cand | spec | mode | seed | recorded in | identical full dict |")
L.append("|---|---|---|---|---|---|---|---|")
for x in REG["rows"]:
    L.append(f"| {x['exp']} | {x['cell']} | {x['cand']} | {x['specmode']} | {x['mode']} "
             f"| {x['seed']} | stability-gate/{x['recorded_exp']} | {x['identical_full_result']} |")
L.append(f"\n**{REG['n_identical']}/{REG['n']} identical.**\n")

L.append("## (b) Per candidate x cell, stability-enabled spec, 2500 evals, seeds 1/2/3\n")
L.append("F = final feasible (spec incl. in-band mu_min>=1 AND wide mu>=1), s = "
         "spec-feasible but wide-unstable, x = spec-infeasible. mu wide = wide "
         "mu_min of the reported winner. jv = joint violation of the inloop winner "
         "(sum of normalized in-band shortfalls + max(0, 1 - mu_wide)); min over seeds.\n")
L.append("| exp | cell | cand | gate-only 1/2/3 | mu wide gate | gate+inloop 1/2/3 "
         "| mu wide inloop | mu in-band inloop | min jv inloop | worst binding inloop (best-jv seed) |")
L.append("|---|---|---|---|---|---|---|---|---|---|")
agg = OrderedDict()
for (exp, cell, cand), d in sorted(by.items()):
    g, i = d["gate"], d["inloop"]
    fg = "".join(flag(g[s]) if s in g else "?" for s in (1, 2, 3))
    fi = "".join(flag(i[s]) if s in i else "?" for s in (1, 2, 3))
    mwg = ", ".join(f2(g[s].get("mu_min_wide")) if s in g else "?" for s in (1, 2, 3))
    mwi = ", ".join(f2(i[s].get("mu_min_wide")) if s in i else "?" for s in (1, 2, 3))
    mbi = ", ".join(f2(i[s].get("mu_min")) if s in i else "?" for s in (1, 2, 3))
    jvs = [(joint_viol(i[s]), s) for s in i]
    jv, js = min(jvs) if jvs else (None, None)
    wb = i[js].get("worst") if js else None
    L.append(f"| {exp} | {cell.replace('v12-', '')} | {cname(cand)} | {fg} | {mwg} | {fi} "
             f"| {mwi} | {mbi} | {'-' if jv is None else f'{jv:.4f}'} "
             f"| {wb if not (js and i[js].get('feasible')) else 'feasible'} |")
    key = (exp, cand if exp != "ec" else ("ec:add R n1-n2" if cname(cand) == "add R n1-n2"
                                          else "ec:other edits"))
    a = agg.setdefault(key, {"cells": set(), "gate_F": 0, "gate_s": 0, "gate_n": 0,
                             "in_F": 0, "in_s": 0, "in_n": 0, "gate_cells": set(),
                             "in_cells": set(), "units": 0, "mu_w_gate": [], "mu_w_in": []})
    a["cells"].add(cell)
    a["units"] += 1
    for s, r in g.items():
        a["gate_n"] += 1
        a["gate_F"] += flag(r) == "F"
        a["gate_s"] += flag(r) == "s"
        if flag(r) == "F":
            a["gate_cells"].add(cell)
        if isinstance(r.get("mu_min_wide"), (int, float)):
            a["mu_w_gate"].append(r["mu_min_wide"])
    for s, r in i.items():
        a["in_n"] += 1
        a["in_F"] += flag(r) == "F"
        a["in_s"] += flag(r) == "s"
        if flag(r) == "F":
            a["in_cells"].add(cell)
        if isinstance(r.get("mu_min_wide"), (int, float)):
            a["mu_w_in"].append(r["mu_min_wide"])

L.append("\n## (c) Totals per candidate\n")
L.append("| exp | candidate | cells | (cell,cand) units | gate-only F / s / n | cells >=1 F (gate) "
         "| gate+inloop F / s / n | cells >=1 F (inloop) | wide mu range gate | wide mu range inloop |")
L.append("|---|---|---|---|---|---|---|---|---|---|")
tot = {}
for (exp, cand), a in agg.items():
    rng = lambda v: f"{min(v):.2f}..{max(v):.2f}" if v else "-"   # noqa: E731
    L.append(f"| {exp} | {cname(cand)} | {len(a['cells'])} | {a['units']} "
             f"| {a['gate_F']} / {a['gate_s']} / {a['gate_n']} | {len(a['gate_cells'])} "
             f"| {a['in_F']} / {a['in_s']} / {a['in_n']} | {len(a['in_cells'])} "
             f"| {rng(a['mu_w_gate'])} | {rng(a['mu_w_in'])} |")
    tot[f"{exp}|{cname(cand)}"] = {k: (sorted(v) if isinstance(v, set) else v)
                                   for k, v in a.items()}

# wb cells with >=1 stable-feasible seed from ANY wb candidate (template or E-c)
wb_any = {"gate": set(), "inloop": set()}
for r in main:
    if "-wb-" in r["cell"] and r.get("feasible"):
        wb_any[r["mode"]].add(r["cell"])
L.append(f"\nWideband cells with >=1 stable-feasible seed from ANY tested candidate "
         f"(template + E-c edits): gate-only {len(wb_any['gate'])}/8 "
         f"{sorted(wb_any['gate'])}; gate+inloop {len(wb_any['inloop'])}/8 "
         f"{sorted(wb_any['inloop'])}.\n")

# ---- edge analysis
L.append("## (d) 100 MHz edge: wide mu(f) of FINAL winners\n")
cur = [r for r in main if r.get("curve")]
stable = [r for r in cur if r.get("feasible")]
L.append(f"Stable winners (final feasible): {len(stable)}. With argmin at the "
         f"100 MHz edge: {sum(r['curve']['argmin_is_edge'] for r in stable)}.\n")
edge_rows = sorted([r for r in rows if r["exp"] in ("edge", "edgefail")],
                   key=lambda r: (r["exp"], r["cell"], r["seed"]))
show = edge_rows + sorted(stable, key=lambda r: (r["exp"], r["cell"], r["cand"],
                                                 r["mode"], r["seed"]))[:8]
L.append("Rows `edge` = 5 nb-template runs the stability-gate campaign recorded "
         "final-feasible (re-run gate-only, deterministic); `edgefail` = the 4 recorded "
         "spec-feasible nb runs that fail the wide gate with mu_wide >= 0.99; then the "
         "first 8 S-1 stable winners (all wideband, gate+inloop).\n")
L.append("| exp | cell | cand | mode | seed | argmin (GHz) | mu min | mu@100MHz | "
         "interior argmin (GHz) | interior mu min | pts mu<1.001 |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|")
for r in show:
    c = r["curve"]
    L.append(f"| {r['exp']} | {r['cell'].replace('v12-', '')} | {cname(r['cand'])} | {r['mode']} "
             f"| {r['seed']} | {c['argmin_hz'] / 1e9:.4f} | {c['mu_min']:.6f} "
             f"| {c['mu_at_100MHz']:.6f} | {c['interior_argmin_hz'] / 1e9:.3f} "
             f"| {c['interior_mu_min']:.4f} | {c['n_mu_lt_1p001']} |")
gated = [r for r in main if r.get("spec_feasible") is not None]
flip_up = [r for r in gated if r.get("spec_feasible") and not r.get("stab_wide_ok")
           and isinstance(r.get("mu_min_wide"), (int, float)) and r["mu_min_wide"] >= 0.999]
flip_dn = [r for r in gated if r.get("feasible") and r["mu_min_wide"] < 1.001]
edge_fail = [r for r in cur if r.get("spec_feasible") and not r.get("feasible")
             and r["curve"]["argmin_is_edge"]]
L.append(f"\n- Gated runs: {len(gated)}. Spec-feasible but wide-failing with mu_wide in "
         f"[0.999, 1): **{len(flip_up)}** (would flip fail->pass with tolerance 1e-3: "
         + "; ".join(f"{r['exp']}/{r['cell']}/{cname(r['cand'])}/{r['mode']}/s{r['seed']} "
                     f"mu={r['mu_min_wide']:.5f} at {r['curve']['argmin_hz'] / 1e9:.3f} GHz"
                     for r in flip_up) + ").")
L.append(f"- Final-feasible runs with mu_wide < 1.001 (would flip pass->fail if the "
         f"threshold were raised by 1e-3): **{len(flip_dn)}/{len(stable)}**; of these "
         f"{sum(r['curve']['argmin_is_edge'] for r in flip_dn)} have the argmin at 100 MHz.")
L.append(f"- Spec-feasible, wide-failing runs whose argmin is the 100 MHz edge point: "
         f"{len(edge_fail)}.")
all_edge = [r for r in cur if r["curve"]["argmin_is_edge"]]
SG = json.load(open(os.path.join(HERE, "..", "stability-gate", "results.json")))["rows"]
sg = [r for r in SG if r.get("spec_feasible") is not None]
sg_up = [r for r in sg if r.get("spec_feasible") and not r.get("feasible")
         and isinstance(r.get("mu_min_wide"), (int, float)) and r["mu_min_wide"] >= 0.999]
sg_up2 = [r for r in sg if r.get("spec_feasible") and not r.get("feasible")
          and isinstance(r.get("mu_min_wide"), (int, float)) and r["mu_min_wide"] >= 0.99]
sg_dn = [r for r in sg if r.get("feasible") and r["mu_min_wide"] < 1.001]
L.append(f"- stability-gate campaign ({len(sg)} gated rows): tolerance 1e-3 flips "
         f"fail->pass: **{len(sg_up)}**; within 1e-2 (mu_wide in [0.99,1)): {len(sg_up2)} "
         f"(the `edgefail` rows above + negctl s1, min at 1.29-1.34 GHz). Final-feasible "
         f"with mu_wide < 1.001 (flip pass->fail at +1e-3): **{len(sg_dn)}/"
         f"{sum(1 for r in sg if r.get('feasible'))}**.")
ee = [r for r in edge_rows if r["exp"] == "edge"]
ef = [r for r in edge_rows if r["exp"] == "edgefail"]
L.append(f"- `edge` rows: argmin at 100 MHz in {sum(r['curve']['argmin_is_edge'] for r in ee)}/"
         f"{len(ee)} (mu there {min(r['curve']['mu_min'] for r in ee):.5f}.."
         f"{max(r['curve']['mu_min'] for r in ee):.5f}); `edgefail` rows: argmin at 100 MHz "
         f"in {sum(r['curve']['argmin_is_edge'] for r in ef)}/{len(ef)} (interior dips at "
         + ", ".join(f"{r['curve']['argmin_hz'] / 1e9:.2f}" for r in ef) + " GHz).")
L.append(f"- Any final winner (all {len(cur)} curves) with argmin at 100 MHz: {len(all_edge)}; "
         f"their mu@100MHz range "
         + (f"{min(r['curve']['mu_at_100MHz'] for r in all_edge):.6f}.."
            f"{max(r['curve']['mu_at_100MHz'] for r in all_edge):.6f}" if all_edge else "-")
         + ".")

# ---- overhead
L.append("\n## (e) Wall-time overhead of the in-loop term\n")
pairs = []
for (exp, cell, cand), d in by.items():
    for s in (1, 2, 3):
        if s in d["gate"] and s in d["inloop"]:
            pairs.append((d["gate"][s]["secs"], d["inloop"][s]["secs"],
                          d["inloop"][s]["wide_sims_loop"], d["inloop"][s]["wide_secs_loop"]))
if pairs:
    g = [p[0] for p in pairs]
    i = [p[1] for p in pairs]
    n = sum(p[2] for p in pairs)
    ws = sum(p[3] for p in pairs)
    L.append(f"- Paired runs: {len(pairs)} (same cell/cand/seed, gate-only vs gate+inloop, "
             f"8 parallel processes, shared box).")
    L.append(f"- Median wall: gate-only {st.median(g):.1f} s, gate+inloop {st.median(i):.1f} s; "
             f"median ratio {st.median([b / a for a, b in zip(g, i)]):.2f}x.")
    L.append(f"- In-loop wide sims: {n} total, {ws:.0f} s, {1000 * ws / max(n, 1):.1f} ms/sim "
             f"(~{ws / len(pairs):.1f} s per 2500-eval run).")
    OV = {"n_pairs": len(pairs), "median_gate_s": st.median(g), "median_inloop_s": st.median(i),
          "median_ratio": st.median([b / a for a, b in zip(g, i)]),
          "inloop_wide_sims": n, "inloop_wide_secs": ws}
else:
    OV = {}

open(os.path.join(HERE, "tables.md"), "w").write("\n".join(L) + "\n")
json.dump({"totals": tot, "wb_cells_any_feasible": {k: sorted(v) for k, v in wb_any.items()},
           "edge": {"n_stable": len(stable),
                    "n_stable_argmin_edge": sum(r["curve"]["argmin_is_edge"] for r in stable),
                    "flip_fail_to_pass_tol1e-3": len(flip_up),
                    "flip_pass_to_fail_plus1e-3": len(flip_dn),
                    "stabgate_flip_fail_to_pass_tol1e-3": len(sg_up),
                    "stabgate_flip_pass_to_fail_plus1e-3": len(sg_dn),
                    "edge_rows": [{k: r[k] for k in ("exp", "cell", "cand", "seed",
                                                    "mu_min_wide", "curve")}
                                  for r in edge_rows],
                    "spec_feasible_fail_argmin_edge": len(edge_fail)},
           "overhead": OV, "regress": {"n": REG["n"], "identical": REG["n_identical"]}},
          open(os.path.join(HERE, "summary.json"), "w"), indent=1)
print("\n".join(L))
