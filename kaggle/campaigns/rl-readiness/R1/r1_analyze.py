"""rl-readiness R1 analysis -> summary.json + tables.md (run after r1_drv.py run).

Labels ("full"): lib spec, 2500 evals, seeds 1,2,3 -- recorded E-c/E-d verdicts plus
this campaign's completion runs (seeds 2,3 for sampled E-c-only negatives: all
near-miss A + 20 random per far bin). full_any = feasible at ANY seed; full_2of3 =
feasible at >= 2 of 3 seeds. Uncompleted E-c negatives (seed 1 only) are labelled
infeasible (assumption; tested by the completion runs, see README).
Levels: L600 / L1200 = this campaign's seed-1 runs; L2500 = recorded seed-1 x 2500.
"""
import json, os, sys, collections, math

R1 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R1)
import r1_drv as D                                           # noqa: E402

PRE = {"precision": 0.9, "recall": 0.8}


def ranks(x):
    idx = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and x[idx[j + 1]] == x[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    pr = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pr) < 3:
        return None, len(pr)
    ra, rb = ranks([p[0] for p in pr]), ranks([p[1] for p in pr])
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return (num / den if den else None), len(pr)


def conf(pairs, w=None):
    """pairs: [(cheap_bool, full_bool)], optional weights."""
    c = collections.Counter()
    for i, (p, t) in enumerate(pairs):
        c[("TP" if t else "FP") if p else ("FN" if t else "TN")] += (w[i] if w else 1)
    tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec == 0 or rec == 0 else None)
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": prec, "recall": rec,
            "F1": f1, "n": tp + fp + fn + tn}


def med(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def load():
    S = json.load(open(D.SAMPLE))
    res = {}
    for l in open(D.RES):
        if l.strip():
            j = json.loads(l)
            if j.get("crashed"):
                continue
            res[D.jkey(j["uid"], j["mode"], j["seed"], j["budget"])] = j
    return S, res


def weights(S):
    """Inverse-probability weights of the main sample w.r.t. the E-c+E-d sizable
    population (only the E-c-only far negatives B/C/D were subsampled)."""
    U = D.population()
    stratum = lambda u: (D.wbin(u["w1"]), u["cell"])           # noqa: E731
    popn = collections.Counter(stratum(u) for u in U.values() if u["sizable"]
                               and not u["any_feas"] and "ed" not in u["src"]
                               and D.wbin(u["w1"]) != "A[-0.1,0)")
    smp = collections.Counter(stratum(S["units"][x]) for x in S["main"]
                              if not S["units"][x]["any_feas"]
                              and "ed" not in S["units"][x]["src"]
                              and D.wbin(S["units"][x]["w1"]) != "A[-0.1,0)")
    w = {}
    for x in S["main"]:
        u = S["units"][x]
        k = stratum(u)
        w[x] = popn[k] / smp[k] if k in smp else 1.0
    return w


def main():
    S, res = load()
    U = S["units"]
    W = weights(S)
    out = {"n_results": len(res)}
    # ---------------- full labels (lib)
    lab = {}
    flips = []
    for x in S["main"]:
        u = U[x]
        seeds = {int(s): v for s, v in u["full"].items()}
        for s in (2, 3):
            r = res.get(D.jkey(x, "lib", s, 2500))
            if r is not None and s not in seeds:
                seeds[s] = {"feasible": r["feasible"], "worst": r.get("worst"),
                            "secs": r.get("secs"), "from": "R1"}
                if r["feasible"]:
                    flips.append({"uid": x, "seed": s, "w1": u["w1"], "bin": D.wbin(u["w1"])})
        nf = sum(v["feasible"] for v in seeds.values())
        ws = [v.get("worst") for v in seeds.values() if v.get("worst") is not None]
        lab[x] = {"any": nf >= 1, "2of3": nf >= 2, "nseeds": len(seeds), "nfeas": nf,
                  "s1": bool(seeds[1]["feasible"]), "w1": seeds[1].get("worst"),
                  "wbest": max(ws) if ws else None, "complete": len(seeds) == 3}
    comp_done = [x for x in S["completion"]
                 if all(D.jkey(x, "lib", s, 2500) in res for s in (2, 3))]
    out["completion"] = {
        "planned": len(S["completion"]), "done": len(comp_done),
        "by_bin": dict(collections.Counter(D.wbin(U[x]["w1"]) for x in comp_done)),
        "flips_to_feasible": flips}
    # ---------------- levels (lib)
    lv = {}
    for b in (600, 1200):
        lv[f"1x{b}"] = {x: res.get(D.jkey(x, "lib", 1, b)) for x in S["main"]}
    lv["1x2500"] = {x: {"feasible": lab[x]["s1"], "worst": lab[x]["w1"],
                        "secs": U[x]["full"]["1"].get("secs")} for x in S["main"]}
    tabs = {}
    for name, L in lv.items():
        xs = [x for x in S["main"] if L.get(x) is not None]
        row = {"n": len(xs)}
        for tgt in ("any", "2of3"):
            pairs = [(bool(L[x]["feasible"]), lab[x][tgt]) for x in xs]
            row[f"vs_{tgt}"] = conf(pairs)
            row[f"vs_{tgt}_popw"] = conf(pairs, [W[x] for x in xs])
        for grp, f in (("wb", lambda x: U[x]["band"] == "wb"),
                       ("nb", lambda x: U[x]["band"] == "nb"),
                       ("qwen(E-d)", lambda x: "ed" in U[x]["src"]),
                       ("search(E-c)", lambda x: "ed" not in U[x]["src"])):
            g = [x for x in xs if f(x)]
            row[f"vs_any[{grp}]"] = conf([(bool(L[x]["feasible"]), lab[x]["any"]) for x in g])
        sp, nsp = spearman([L[x].get("worst") for x in xs], [lab[x]["wbest"] for x in xs])
        sp1, _ = spearman([L[x].get("worst") for x in xs], [lab[x]["w1"] for x in xs])
        row["spearman_vs_best_seed"] = sp
        row["spearman_vs_seed1_2500"] = sp1
        row["spearman_n"] = nsp
        # among full-feasible and near-miss only (the ranking an RL reward must get right)
        nm = [x for x in xs if (lab[x]["wbest"] or -9) >= -0.1]
        row["spearman_near(wbest>=-0.1)"], row["n_near"] = spearman(
            [L[x].get("worst") for x in nm], [lab[x]["wbest"] for x in nm])
        secs = [L[x].get("secs") for x in xs]
        row["secs_median"], row["secs_mean"] = med(secs), mean(secs)
        if name != "1x2500":
            row["load_mean"] = mean([L[x].get("load_start") for x in xs])
        # prefix property: cheap-feasible => seed-1 x 2500 feasible?
        row["cheap_pos_not_s1_2500"] = [x for x in xs if L[x]["feasible"] and not lab[x]["s1"]]
        row["pass_rule_vs_any"] = (row["vs_any"]["precision"] or 0) >= PRE["precision"] and \
            (row["vs_any"]["recall"] or 0) >= PRE["recall"]
        tabs[name] = row
    out["lib"] = tabs
    # cost of a fresh 2500 call measured in this campaign (same load conditions)
    c2500 = [r["secs"] for r in res.values() if r["budget"] == 2500 and r["mode"] == "lib"]
    c2500s = [r["secs"] for r in res.values() if r["budget"] == 2500 and r["mode"] == "stab"]
    out["cost"] = {"lib_2500_this_run_median": med(c2500), "lib_2500_n": len(c2500),
                   "stab_2500_this_run_median": med(c2500s),
                   "lib_600_median": tabs["1x600"]["secs_median"],
                   "lib_1200_median": tabs["1x1200"]["secs_median"],
                   "lib_2500_recorded_median(E-c/E-d)": tabs["1x2500"]["secs_median"]}
    # ---------------- two-stage (screen at level, confirm cheap-positives with full)
    full_cost = 3 * (med(c2500) or tabs["1x2500"]["secs_median"])
    two = {}
    for name, row in tabs.items():
        c = row["vs_any"]
        n = c["n"]
        ppos = (c["TP"] + c["FP"]) / n if n else None
        cw = row["vs_any_popw"]
        ppos_w = (cw["TP"] + cw["FP"]) / cw["n"] if cw["n"] else None
        cheap = row["secs_median"] if name != "1x2500" else (med(c2500) or row["secs_median"])
        # a 1x2500 screen's seed-1 run is reused by the confirm (2 more seeds)
        conf_cost = full_cost * (2 / 3 if name == "1x2500" else 1)
        cheap = cheap or float("nan")
        two[name] = {"recall": c["recall"], "precision": 1.0,
                     "screen_cpu_s": cheap, "confirm_cpu_s": conf_cost,
                     "p_cheap_pos_sample": ppos, "p_cheap_pos_popw": ppos_w,
                     "cpu_s_per_cand_sample": cheap + (ppos or 0) * conf_cost,
                     "cpu_s_per_cand_popw": cheap + (ppos_w or 0) * conf_cost,
                     "full_only_cpu_s": full_cost}
    out["two_stage"] = two
    # ---------------- EXPLORATORY (not pre-registered): margin-gated escalation.
    # cheap-positive -> accept (prefix property: no FP observed); cheap-negative with
    # cheap worst >= tau -> escalate to seed-1 x 2500 (verdict = recorded s1x2500);
    # else reject. Reward label compared with full any-seed.
    c25 = med(c2500) or tabs["1x2500"]["secs_median"]
    esc = {}
    for name in ("1x600", "1x1200"):
        L = lv[name]
        xs = [x for x in S["main"] if L.get(x) is not None]
        if not xs:
            continue
        for tau in (-0.02, -0.05, -0.1, -0.2, -0.3, -0.5, -1.0):
            e = [x for x in xs if not L[x]["feasible"] and L[x].get("worst") is not None
                 and L[x]["worst"] >= tau]
            es = set(e)
            pred = {x: bool(L[x]["feasible"]) or (x in es and lab[x]["s1"]) for x in xs}
            c = conf([(pred[x], lab[x]["any"]) for x in xs])
            wsum = sum(W[x] for x in xs)
            pe_w = sum(W[x] for x in e) / wsum
            cheap = tabs[name]["secs_median"]
            esc[f"{name}|tau={tau}"] = {
                "recall": c["recall"], "precision": c["precision"], "FN": c["FN"],
                "p_escalate_sample": len(e) / len(xs), "p_escalate_popw": pe_w,
                "cpu_s_sample": cheap + len(e) / len(xs) * c25,
                "cpu_s_popw": cheap + pe_w * c25}
    out["escalation_exploratory"] = esc
    # ---------------- stability subsample (gate-only "stab", gate+inloop "stabil")
    for mode in ("stab", "stabil"):
        stab_section(out, S, res, U, mode)
    json.dump(out, open(R1 + "/summary.json", "w"), indent=1, default=repr)
    tables(out)


def stab_section(out, S, res, U, mode):
    st = {}
    slab = {}
    for x in S["stab"]:
        rs = [res.get(D.jkey(x, mode, s, 2500)) for s in (1, 2, 3)]
        if any(r is None for r in rs):
            continue
        ws = [r.get("worst") for r in rs if r.get("worst") is not None]
        slab[x] = {"any": any(r["feasible"] for r in rs),
                   "2of3": sum(r["feasible"] for r in rs) >= 2,
                   "spec_any": any(r.get("spec_feasible") for r in rs),
                   "wbest": max(ws) if ws else None, "s1": rs[0],
                   "lib_any": U[x]["any_feas"]}
    for b in (600, 1200, 2500):
        L = {x: (res.get(D.jkey(x, mode, 1, b)) if b != 2500 else slab[x]["s1"])
             for x in slab}
        xs = [x for x in slab if L.get(x) is not None]
        row = {"n": len(xs)}
        for tgt in ("any", "2of3"):
            row[f"vs_{tgt}"] = conf([(bool(L[x]["feasible"]), slab[x][tgt]) for x in xs])
        row["spec_only_vs_spec_any"] = conf([(bool(L[x].get("spec_feasible")), slab[x]["spec_any"])
                                             for x in xs])
        row["spearman_vs_best_seed"], row["spearman_n"] = spearman(
            [L[x].get("worst") for x in xs], [slab[x]["wbest"] for x in xs])
        row["secs_median"] = med([L[x].get("secs") for x in xs])
        row["pass_rule_vs_any"] = (row["vs_any"]["precision"] or 0) >= PRE["precision"] and \
            (row["vs_any"]["recall"] or 0) >= PRE["recall"]
        st[f"1x{b}"] = row
    if not slab:
        return
    out[mode] = st
    out[mode + "_labels"] = {
        "n": len(slab), "full_any": sum(v["any"] for v in slab.values()),
        "full_2of3": sum(v["2of3"] for v in slab.values()),
        "spec_any": sum(v["spec_any"] for v in slab.values()),
        "lib_full_any_in_subsample": sum(v["lib_any"] for v in slab.values()),
        "band|lib_full|stab_full": dict(collections.Counter(
            f"{U[x]['band']}|{v['lib_any']}|{v['any']}" for x, v in slab.items())),
        "stab_2500_secs_median": med([res[D.jkey(x, mode, s, 2500)].get("secs")
                                      for x in slab for s in (1, 2, 3)])}


def f3(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def tables(o):
    L = ["# R1 tables (auto-generated by r1_analyze.py)", ""]
    L.append("## Main sample, lib spec (no stability gate): cheap level vs full (3 seeds x 2500)")
    L.append("")
    L.append("| level | n | full=any-seed P / R / F1 | TP FP FN TN | full>=2/3 P / R | pop-weighted P / R | Spearman worst (vs best-seed / vs s1x2500 / near-only n) | s/call median (mean) | rule P>=0.9 & R>=0.8 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for k, r in o["lib"].items():
        a, b, w = r["vs_any"], r["vs_2of3"], r["vs_any_popw"]
        L.append(f"| {k} | {r['n']} | {f3(a['precision'])} / {f3(a['recall'])} / {f3(a['F1'])} | "
                 f"{a['TP']} {a['FP']} {a['FN']} {a['TN']} | {f3(b['precision'])} / {f3(b['recall'])} | "
                 f"{f3(w['precision'])} / {f3(w['recall'])} | {f3(r['spearman_vs_best_seed'])} / "
                 f"{f3(r['spearman_vs_seed1_2500'])} / {f3(r['spearman_near(wbest>=-0.1)'])} (n={r['n_near']}) | "
                 f"{f3(r['secs_median'])} ({f3(r['secs_mean'])}) | {'PASS' if r['pass_rule_vs_any'] else 'fail'} |")
    L.append("")
    L.append("### Recall / precision by group (vs full any-seed)")
    L.append("")
    L.append("| level | wb P/R (TP,FP,FN) | nb P/R (TP,FP,FN) | Qwen E-d P/R (TP,FP,FN) | search E-c P/R (TP,FP,FN) | cheap-pos not feasible at s1x2500 |")
    L.append("|---|---|---|---|---|---|")
    for k, r in o["lib"].items():
        cells = []
        for g in ("wb", "nb", "qwen(E-d)", "search(E-c)"):
            c = r[f"vs_any[{g}]"]
            cells.append(f"{f3(c['precision'])}/{f3(c['recall'])} ({c['TP']},{c['FP']},{c['FN']})")
        L.append(f"| {k} | " + " | ".join(cells) + f" | {len(r['cheap_pos_not_s1_2500'])} |")
    L.append("")
    L.append("## Two-stage reward: cheap screen -> full confirm (3 x 2500) of every cheap-positive")
    L.append("")
    L.append("| screen | recall | precision | P(cheap+) sample / pop-weighted | CPU-s per candidate sample / pop-weighted | full-only CPU-s |")
    L.append("|---|---|---|---|---|---|")
    for k, r in o["two_stage"].items():
        L.append(f"| {k} | {f3(r['recall'])} | 1.000 | {f3(r['p_cheap_pos_sample'])} / {f3(r['p_cheap_pos_popw'])} | "
                 f"{f3(r['cpu_s_per_cand_sample'])} / {f3(r['cpu_s_per_cand_popw'])} | {f3(r['full_only_cpu_s'])} |")
    L.append("")
    L.append("## EXPLORATORY (not pre-registered): margin-gated escalation")
    L.append("")
    L.append("cheap-positive -> accept; cheap-negative with cheap worst >= tau -> seed-1 x 2500; else reject.")
    L.append("")
    L.append("| screen, tau | recall | precision | FN | P(escalate) sample / pop-w | CPU-s per candidate sample / pop-w |")
    L.append("|---|---|---|---|---|---|")
    for k, r in o.get("escalation_exploratory", {}).items():
        L.append(f"| {k} | {f3(r['recall'])} | {f3(r['precision'])} | {r['FN']} | "
                 f"{f3(r['p_escalate_sample'])} / {f3(r['p_escalate_popw'])} | "
                 f"{f3(r['cpu_s_sample'])} / {f3(r['cpu_s_popw'])} |")
    L.append("")
    for mode, title in (("stab", "GATE-ONLY (wide gate after sizing; STAB_WIDE_INLOOP unset)"),
                        ("stabil", "gate + STAB_WIDE_INLOOP=1 (final verifier config, S-1 f3677bb08)")):
        if mode not in o:
            continue
        L.append(f"## Stability subsample, {title}; stability_spec mu_min>=1")
        L.append("")
        L.append(f"labels: {o[mode + '_labels']}")
        L.append("")
        L.append("| level | n | P / R / F1 (vs any-seed) | TP FP FN TN | vs >=2/3 P / R | spec-part only P / R | Spearman worst | s/call median | rule |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for k, r in o[mode].items():
            a, b, s = r["vs_any"], r["vs_2of3"], r["spec_only_vs_spec_any"]
            L.append(f"| {k} | {r['n']} | {f3(a['precision'])} / {f3(a['recall'])} / {f3(a['F1'])} | "
                     f"{a['TP']} {a['FP']} {a['FN']} {a['TN']} | {f3(b['precision'])} / {f3(b['recall'])} | "
                     f"{f3(s['precision'])} / {f3(s['recall'])} | {f3(r['spearman_vs_best_seed'])} | "
                     f"{f3(r['secs_median'])} | {'PASS' if r['pass_rule_vs_any'] else 'fail'} |")
        L.append("")
    L.append(f"cost: {o['cost']}")
    L.append("")
    L.append(f"completion: planned {o['completion']['planned']} done {o['completion']['done']} "
             f"by bin {o['completion']['by_bin']}; flips to feasible at seed 2/3: "
             f"{len(o['completion']['flips_to_feasible'])} {o['completion']['flips_to_feasible']}")
    open(R1 + "/tables.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
