"""Summarize stability-gate results.json -> tables.md (+ regression verdicts)."""
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.dirname(HERE)
rows = json.load(open(os.path.join(HERE, "results.json")))["rows"]
out = []


def f(x, n=3):
    return "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


# ---- (a) regression vs recorded rows
ea = json.load(open(f"{AUD}/E-a/results.json"))["rows"]
eb = json.load(open(f"{AUD}/E-b/results.json"))["rows"]
ec = [json.loads(l) for l in open(f"{AUD}/E-c/results.jsonl")]


def recorded(cell, cand, seed):
    if cand == "template":
        return next(r for r in ea if r["cell"] == cell and r["cand"] == cand
                    and r["delta"] == 0 and r["seed"] == seed), "E-a/results.json"
    if cand.startswith("ec:"):
        return next(r for r in ec if r["cell"] == cell and r["cid"] == cand[3:]
                    and r["seed"] == seed and r["phase"] == "confirm"), "E-c/results.jsonl"
    return next(r for r in eb if r["cell"] == cell and r["cand"] == cand
                and r["seed"] == seed), "E-b/results.json"


def scal(m):
    return {k: v for k, v in (m or {}).items()
            if isinstance(v, (int, float, str, bool)) or v is None}


reg = []
for r in rows:
    if r["exp"] not in ("regress", "negctl") or r["specmode"] != "lib":
        continue
    rec, src = recorded(r["cell"], r["cand"], r["seed"])
    new_m = r["result"]["metrics"]
    old_m = rec["metrics"]
    same_m = (scal(new_m) == scal(old_m)) if src.endswith("jsonl") else (
        json.loads(json.dumps(new_m, default=repr)) == old_m)
    extra = sorted(set(r["result"]) - {"feasible", "metrics", "winner_reeval_ungated",
                                       "best_idd_ma", "best_s21_db", "best_conv_gain_db",
                                       "best_sds21_db", "n_evals", "n_sim_fail",
                                       "sim_error"})
    reg.append({"exp": r["exp"], "cell": r["cell"], "cand": r["cand"], "seed": r["seed"],
                "recorded_in": src, "metrics_identical": same_m,
                "feasible_new": r["feasible"], "feasible_recorded": rec["feasible"],
                "feasible_identical": r["feasible"] == rec["feasible"],
                "extra_keys": extra, "mu_min_inband": new_m.get("mu_min")})
out.append("## (a) Regression: lib specs (no mu_min) vs recorded rows\n")
out.append("| exp | cell | cand | seed | recorded in | metrics identical | feasible new/rec | extra keys |")
out.append("|---|---|---|---|---|---|---|---|")
for g in reg:
    out.append(f"| {g['exp']} | {g['cell']} | {g['cand']} | {g['seed']} | {g['recorded_in']} | "
               f"{g['metrics_identical']} | {g['feasible_new']}/{g['feasible_recorded']} | "
               f"{g['extra_keys'] or 'none'} |")

# ---- (b) negative control
out.append("\n## (b) Negative control: v12-nb-f15-g16, a5-CG anchor + `add L VIN1-n1`\n")
out.append("| spec | seed | feasible | spec_feasible | mu_min in-band | mu_min wide | k_min wide | |D|max wide | stab_wide_ok | pts checked | replaced | worst (metric, margin) |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in sorted((r for r in rows if r["exp"] == "negctl"),
                key=lambda r: (r["specmode"], r["seed"])):
    out.append(f"| {r['specmode']} | {r['seed']} | {r['feasible']} | {f(r.get('spec_feasible'))} | "
               f"{f(r.get('mu_min'))} | {f(r.get('mu_min_wide'))} | {f(r.get('k_min_wide'))} | "
               f"{f(r.get('delta_max_wide'))} | {f(r.get('stab_wide_ok'))} | "
               f"{f(r.get('stab_points_checked'))} | {f(r.get('stab_winner_replaced'))} | "
               f"{r.get('worst')} |")


def cell_table(exp, title, cands):
    out.append(f"\n## {title}\n")
    out.append("Per seed: F = final feasible (spec incl. in-band mu_min>=1 AND wide mu>=1), "
               "s = spec-feasible but wide-unstable, x = spec-infeasible. "
               "mu = in-band mu_min / wide mu_min of the reported winner.\n")
    out.append("| cell | cand | seeds 1/2/3 | final feasible | mu in-band (s1,s2,s3) | mu wide (s1,s2,s3) | replaced | worst binding (best seed) |")
    out.append("|---|---|---|---|---|---|---|---|")
    by = defaultdict(list)
    for r in rows:
        if r["exp"] == exp:
            by[(r["cell"], r["cand"])].append(r)
    agg = {}
    for (cell, cand), rs in sorted(by.items()):
        rs.sort(key=lambda r: r["seed"])
        marks = "".join("F" if r["feasible"] else ("s" if r.get("spec_feasible") else "x")
                        for r in rs)
        nf = sum(r["feasible"] for r in rs)
        best = max(rs, key=lambda r: (r["feasible"], (r.get("worst") or [0, -9])[1]))
        agg[(cell, cand)] = nf
        out.append(f"| {cell} | {cand} | {marks} | {nf}/{len(rs)} | "
                   f"{', '.join(f(r.get('mu_min'), 2) for r in rs)} | "
                   f"{', '.join(f(r.get('mu_min_wide'), 2) for r in rs)} | "
                   f"{sum(bool(r.get('stab_winner_replaced')) for r in rs)} | "
                   f"{best.get('worst')} |")
    return agg


tpl = cell_table("tpl", "(c1) Reference templates x 16 cells, stability-enabled spec (2500 evals)", None)
anc = cell_table("anchors", "(c2) Library anchors a1..a5 x 8 nb cells, stability-enabled spec (2500 evals)", None)

ws = [r for r in rows if r.get("wide_sims")]
out.append("\n## Cost\n")
if ws:
    n = sum(r["wide_sims"] for r in ws)
    s = sum(r["wide_secs"] for r in ws)
    out.append(f"- wide-stability sims: {n} over {len(ws)} gated runs, "
               f"{s:.1f} s total, {s / n:.2f} s per sim; "
               f"max per run {max(r['wide_sims'] for r in ws)}; "
               f"median run wall {sorted(r['secs'] for r in ws)[len(ws) // 2]} s.")

open(os.path.join(HERE, "tables.md"), "w").write("\n".join(out) + "\n")
json.dump({"regression": reg,
           "tpl_feasible_seeds": {f"{c}|{a}": v for (c, a), v in tpl.items()},
           "anchor_feasible_seeds": {f"{c}|{a}": v for (c, a), v in anc.items()}},
          open(os.path.join(HERE, "summary.json"), "w"), indent=1)
print("\n".join(out))
