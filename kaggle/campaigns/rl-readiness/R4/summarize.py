"""R4 summary: static.json + post.json + raw mutation rows -> summary.json, tables.md
usage: summarize.py <rawdir>"""
import sys, os, json, statistics as st
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def pct(a, b):
    return f"{a}/{b} ({100.0 * a / b:.0f}%)" if b else "0/0"


def main(rawdir):
    S = json.load(open(HERE + "/static.json"))
    P = json.load(open(HERE + "/post.json"))["designs"]
    # re-derive every transient verdict with the FINAL rule (r4_sim.tran_verdict);
    # where a 600-ns confirmation run exists (tran_long.json) it decides.
    import r4_sim as SIM
    TL = json.load(open(HERE + "/tran_long.json")) if os.path.exists(HERE + "/tran_long.json") else {}
    for d in P:
        for k, v in d["tran"].items():
            lv = TL.get(d["id"] + "|" + k)
            v["verdict80"] = SIM.tran_verdict(v["amp"])
            v["verdict"] = lv["long_verdict"] if lv else v["verdict80"]
            g = (v["amp"] or {}).get("gear_verdict")
            if v["verdict"] == "oscillates" and g and g != "oscillates" and not lv:
                v["verdict"] = "osc_trap_only"
        d["tran_r50"] = d["tran"]["r50/r50"]["verdict"]
        d["tran_n_osc"] = sum(1 for v in d["tran"].values() if v["verdict"] == "oscillates")
    out, md = {}, []
    out["tran_long_n"] = len(TL)
    out["tran_long_transitions"] = dict(Counter(f"{v['short_verdict']}->{v['long_verdict']}"
                                                for v in TL.values()))
    # ------------------------------------------------------------ (a)
    md.append("## (a) spec topology limits over recorded solutions\n")
    md.append("| source | solutions | cells | violate any spec.topology criterion | by criterion | cells with >=1 compliant solution |")
    md.append("|---|---|---|---|---|---|")
    for src, v in S["summary"].items():
        md.append(f"| {src} | {v['n']} | {v['cells']} | {v['screen_fail_any']} | "
                  f"{v['screen_fail_by_criterion'] or '-'} | {v['cells_with_any_passing']} |")
    out["a"] = S["summary"]
    # ------------------------------------------------------------ run-level
    runs = []
    for f in sorted(os.listdir(rawdir)):
        if f.endswith(".json"):
            r = json.load(open(os.path.join(rawdir, f)))
            res = r.get("result") or {}
            runs.append({"f": f, "tag": r["tag"], "cell": r["cell"], "cand": r["cand"],
                         "mode": r["mode"], "seed": r["seed"],
                         "feasible": res.get("feasible"), "spec_feasible": res.get("spec_feasible"),
                         "stab_wide_ok": res.get("stab_wide_ok"),
                         "replaced": res.get("stab_winner_replaced"),
                         "worst": r.get("worst"), "metrics": res.get("metrics"),
                         "reason": res.get("infeasible_reason"), "secs": r["secs"]})
    rc = Counter((x["tag"], x["mode"], bool(x["feasible"]), bool(x["spec_feasible"])) for x in runs)
    out["runs"] = {"|".join(map(str, k)): v for k, v in sorted(rc.items())}
    md.append("\n## sizing runs (tag, mode, final feasible, spec feasible): count\n")
    for k, v in sorted(rc.items()):
        md.append(f"- {k}: {v}")
    # per candidate-group solved cells under the RL verifier (inloop)
    grp = defaultdict(lambda: defaultdict(list))
    for x in runs:
        if x["mode"] != "inloop" or x["tag"] in ("reg", "reg2", "mut"):
            continue
        g = x["tag"] + ":" + ("template" if x["cand"] == "template" else
                              x["cand"].split(":")[0] if not x["cand"].startswith("anchor:")
                              else x["cand"])
        grp[g][x["cell"]].append(bool(x["feasible"]))
    md.append("\n| group (inloop) | runs | final feasible | cells | cells with >=1 feasible |")
    md.append("|---|---|---|---|---|")
    out["inloop_groups"] = {}
    for g, cells in sorted(grp.items()):
        n = sum(len(v) for v in cells.values())
        k = sum(sum(v) for v in cells.values())
        cs = sum(1 for v in cells.values() if any(v))
        out["inloop_groups"][g] = {"runs": n, "feasible": k, "cells": len(cells), "cells_solved": cs}
        md.append(f"| {g} | {n} | {k} | {len(cells)} | {cs} |")
    # ------------------------------------------------------------ designs
    AUDIT_TAGS = ("s1", "nb", "ed", "gf", "dir")
    wins = [d for d in P if d["role"] == "win" and d["tag"] in AUDIT_TAGS and d["mode"] == "inloop"]
    fails = [d for d in P if d["role"] == "fail" and d["tag"] in AUDIT_TAGS]
    dirlib = [d for d in P if d["tag"] == "dir" and d["mode"] == "lib"]
    out["n_win"], out["n_fail"] = len(wins), len(fails)
    md.append(f"\nDesigns analysed: {len(wins)} stable-feasible winners, {len(fails)} gate-rejected (spec-feasible, wide-unstable) designs (mutation runs excluded).\n")
    rep = [d.get("repro_identical") for d in wins]
    md.append(f"Winner re-eval through SZ.eval_metrics reproduces the recorded metrics: {pct(sum(bool(x) for x in rep), len(rep))}\n")
    # ------------------------------------------------------------ (b)
    b = {"n_mos_lt_1uA": Counter(d["n_mos_lt_1uA"] for d in wins),
         "n_mos_off_50uA": Counter(d["n_mos_off_50uA"] for d in wins),
         "idd_ma": [round((d["metrics"] or {}).get("idd_ma", 0), 3) for d in wins],
         "vbgen_current_max_a": max((d["vbgen_current_a"] for d in wins), default=None),
         "inert_count": Counter(len(d["inert_passives"]) for d in wins),
         "designs_with_inert": sum(1 for d in wins if d["inert_passives"])}
    out["b_dynamic"] = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in b.items()}
    md.append("## (b) dynamic degeneracy over stable-feasible winners\n")
    md.append(f"- MOS with |Id| < 1 uA per design: {dict(b['n_mos_lt_1uA'])}")
    md.append(f"- MOS below 50 uA ('off' region) per design: {dict(b['n_mos_off_50uA'])}")
    ids = b["idd_ma"]
    if ids:
        md.append(f"- Idd (mA): min {min(ids)}, median {st.median(ids)}, max {max(ids)}")
    md.append(f"- max total VBGEN (bias-source) current: {b['vbgen_current_max_a']} A")
    md.append(f"- designs with >=1 INERT passive (opening it keeps the design final-feasible): "
              f"{pct(b['designs_with_inert'], len(wins))}; inert-count histogram {dict(b['inert_count'])}")
    # ------------------------------------------------------------ (c)
    md.append("\n## (c) fragility: 10 draws x (1+U[-5%,+5%]) on every sized value\n")
    ff = [d["frag_final_feasible"] for d in wins]
    sf = [d["frag_spec_feasible"] for d in wins]
    wo = [d["frag_wide_ok"] for d in wins]
    tot = 10 * len(wins)
    viol = Counter(v for d in wins for x in d["frag"] if not x["final_feasible"]
                   for v in (x["viol"] + ([] if x["wide_ok"] else ["WIDE_mu"])))
    out["c"] = {"n_designs": len(wins), "draws": tot,
                "final_feasible_draws": sum(ff), "spec_feasible_draws": sum(sf),
                "wide_ok_draws": sum(wo),
                "designs_all10": sum(1 for x in ff if x == 10),
                "designs_ge5": sum(1 for x in ff if x >= 5),
                "designs_zero": sum(1 for x in ff if x == 0),
                "hist": dict(Counter(ff)), "violations": dict(viol),
                "winner_worst_margin_median": st.median([d["worst_margin"] for d in wins]) if wins else None}
    md.append(f"- draws still FINAL-feasible: {pct(sum(ff), tot)}; spec-feasible {pct(sum(sf), tot)}; wide-stable {pct(sum(wo), tot)}")
    md.append(f"- designs feasible in 10/10 draws: {out['c']['designs_all10']}; >=5/10: {out['c']['designs_ge5']}; 0/10: {out['c']['designs_zero']} (of {len(wins)})")
    md.append(f"- histogram (#feasible draws: #designs): {dict(sorted(Counter(ff).items()))}")
    md.append(f"- what breaks (count over failing draws): {dict(viol.most_common())}")
    # by group
    byg = defaultdict(list)
    for d in wins:
        byg[("wb" if "-wb-" in d["cell"] else "nb") + " " + d["tag"]].append(d["frag_final_feasible"])
    md.append("\n| group | designs | feasible draws | median winner worst margin |")
    md.append("|---|---|---|---|")
    for g, v in sorted(byg.items()):
        wm = [d["worst_margin"] for d in wins
              if (("wb" if "-wb-" in d["cell"] else "nb") + " " + d["tag"]) == g]
        md.append(f"| {g} | {len(v)} | {pct(sum(v), 10 * len(v))} | {st.median(wm):.4f} |")
    # ------------------------------------------------------------ (d)
    md.append("\n## (d) stability-window sensitivity (pass = mu_min >= 1)\n")
    md.append("| window | stable winners pass | gate-rejected designs pass |")
    md.append("|---|---|---|")
    out["d"] = {}
    for w in ("w0p1_10", "w0p1_20", "w0p1_20_fine", "w0p01_50", "w0p01_50_dec"):
        pw = sum(1 for d in wins if (d["windows"].get(w) or {}).get("mu_min", -9) >= 1)
        pf = sum(1 for d in fails if (d["windows"].get(w) or {}).get("mu_min", -9) >= 1)
        out["d"][w] = {"wins_pass": pw, "wins": len(wins), "fails_pass": pf, "fails": len(fails)}
        md.append(f"| {w} | {pct(pw, len(wins))} | {pct(pf, len(fails))} |")
    both = sum(1 for d in wins
               if min((d["windows"].get(w) or {}).get("mu_min", -9)
                      for w in ("w0p01_50", "w0p01_50_dec")) >= 1)
    out["d"]["w0p01_50_lin_and_dec"] = {"wins_pass": both}
    md.append(f"| 0.01-50 lin AND dec | {pct(both, len(wins))} | |")
    am = Counter()
    for d in fails:
        s = (d["windows"].get("w0p01_50") or {}).get("unstable_span_hz")
        if s:
            am["<0.1GHz" if s[0] < 1e8 else "0.1-10GHz" if s[0] < 1e10 else
               "10-20GHz" if s[0] < 2e10 else ">20GHz"] += 1
    out["d"]["fail_unstable_span_start"] = dict(am)
    md.append(f"\nGate-rejected designs, where the 0.01-50 GHz mu<1 span starts: {dict(am)}")
    fm = [(d["windows"].get("w0p1_20") or {}).get("mu_min") for d in fails]
    md.append(f"Gate-rejected designs, gate-window mu_min: " +
              ", ".join(f"{x:.3f}" for x in sorted(v for v in fm if v is not None)))
    # ------------------------------------------------------------ (e)
    md.append("\n## (e) transient with real terminations (80 ns, 1 mA x 10 ps kick at VIN1+VOUT1)\n")
    md.append("| population | designs | r50/r50 oscillates | r50/r50 dc_shift | oscillates under >=1 of 25 terminations | median # oscillating terminations |")
    md.append("|---|---|---|---|---|---|")
    out["e"] = {}
    for name, pop in (("gate-rejected", fails), ("stable winners", wins)):
        o50 = sum(1 for d in pop if d["tran_r50"] == "oscillates")
        s50 = sum(1 for d in pop if d["tran_r50"] == "dc_shift")
        any_ = sum(1 for d in pop if d["tran_n_osc"] > 0)
        ver = Counter(v["verdict"] for d in pop for v in d["tran"].values())
        out["e"][name] = {"n": len(pop), "r50_osc": o50, "r50_dcshift": s50, "any_osc": any_,
                          "verdicts_all_terms": dict(ver),
                          "r50_verdicts": dict(Counter(d["tran_r50"] for d in pop))}
        md.append(f"| {name} | {len(pop)} | {o50} | {s50} | {any_} | "
                  f"{st.median([d['tran_n_osc'] for d in pop]) if pop else '-'} |")
        md.append(f"\n{name}: verdicts over all termination pairs: {dict(ver)}\n")
    term = Counter(k for d in fails for k, v in d["tran"].items() if v["verdict"] == "oscillates")
    out["e"]["fail_osc_by_termination"] = dict(term)
    md.append(f"Gate-rejected designs, oscillating termination pairs (source/load): {dict(term.most_common())}")
    # ------------------------------------------------------------ (f)
    md.append("\n## (f) other loopholes\n")
    wbw = [d for d in wins if "-wb-" in d["cell"]]
    nbw = [d for d in wins if "-nb-" in d["cell"]]
    nfbad = [d for d in wbw if d.get("nf_band_ok") is False]
    out["f_nf_band"] = {"wb_wins": len(wbw), "nf_band_violations": len(nfbad),
                        "nb_wins": len(nbw),
                        "nb_nf_band_violations": sum(1 for d in nbw if d.get("nf_band_ok") is False),
                        "wb_excess_db": sorted(round(d["nf_band_max_db"] - d["metrics"]["nf_db"], 3)
                                               for d in wbw if d.get("nf_band_max_db") is not None)}
    md.append(f"- NF checked at f0 only: wideband winners whose NF over the band exceeds the spec max: "
              f"{pct(len(nfbad), len(wbw))}; narrowband {out['f_nf_band']['nb_nf_band_violations']}/{len(nbw)}")
    # nb s21/s11 at f0 vs band
    def _lim(cell, key):
        import yaml
        c = yaml.safe_load(open(f"/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/editcap-lib-v12-45nm/{cell}/spec.yaml"))["constraints"]
        return c.get(key)
    nb_s21 = sum(1 for d in nbw if d["metrics"].get("s21_min_db") is not None
                 and d["metrics"]["s21_min_db"] < _lim(d["cell"], "s21_db")["min"])
    nb_s11 = sum(1 for d in nbw if d["metrics"].get("s11_max_db") is not None
                 and d["metrics"]["s11_max_db"] > _lim(d["cell"], "s11_db")["max"])
    out["f_nb_band"] = {"nb_wins": len(nbw), "s21_band_min_below_spec": nb_s21,
                        "s11_band_max_above_spec": nb_s11}
    md.append(f"- narrowband (spec checks s21/s11 at f0 only): winners whose in-band (f0 +/-2%) s21_min < spec: {nb_s21}/{len(nbw)}; s11_max > spec: {nb_s11}/{len(nbw)}")
    pk = [(d["s21_peak_db"] - d["metrics"]["s21_db"], d["s21_peak_hz"]) for d in wins if "s21_peak_db" in d]
    out["f_s21_peak"] = {"n": len(pk), "peak_minus_f0_db_max": max((p[0] for p in pk), default=None),
                         "n_peak_gt_f0_by_3db": sum(1 for p in pk if p[0] > 3)}
    md.append(f"- out-of-band |S21| peak above in-band s21 by > 3 dB: {out['f_s21_peak']['n_peak_gt_f0_by_3db']}/{len(pk)} winners (max excess {out['f_s21_peak']['peak_minus_f0_db_max']:.2f} dB)" if pk else "")
    bnd = Counter((k, s) for d in wins for _n, k, s in d["at_bounds"])
    out["f_bounds"] = {"designs_with_any_bound": sum(1 for d in wins if d["at_bounds"]),
                       "by_kind_side": {f"{k}-{s}": v for (k, s), v in bnd.items()}}
    md.append(f"- sized values pinned at a range limit: {pct(out['f_bounds']['designs_with_any_bound'], len(wins))} winners; by kind/side {out['f_bounds']['by_kind_side']}")
    # mutations
    muts = [x for x in runs if x["tag"] == "mut"]
    par = {(x["cell"], x["seed"]): x for x in runs
           if x["cand"] == "template" and x["mode"] == "inloop" and x["tag"] in ("s1", "nb")}
    mp = {d["id"]: d for d in P if d["tag"] == "mut"}
    md.append("\n### adversarial mutations of the reference templates (inloop verifier, seed 1)\n")
    md.append("| mutation | cell | seed | parent final feasible | mutant final feasible | mutant worst margin (parent) | inert passives in mutant winner (parent) |")
    md.append("|---|---|---|---|---|---|---|")
    pmap = {(d["cell"], d["seed"]): d for d in P if d["cand"] == "template" and d["role"] == "win" and d["mode"] == "inloop"}
    out["f_mut"] = []
    for x in muts:
        p = par.get((x["cell"], x["seed"]))
        dm = next((d for d in P if d["tag"] == "mut" and d["cand"] == x["cand"] and d["seed"] == x["seed"] and d["role"] == "win"), None)
        dp = pmap.get((x["cell"], x["seed"]))
        row = {"mut": x["cand"][4:], "cell": x["cell"], "seed": x["seed"],
               "parent_feasible": (p or {}).get("feasible"), "mutant_feasible": x["feasible"],
               "mutant_worst": x["worst"], "parent_worst": (p or {}).get("worst"),
               "mutant_inert": dm["inert_passives"] if dm else None,
               "parent_inert": dp["inert_passives"] if dp else None}
        out["f_mut"].append(row)
        fw = lambda w: f"{w[1]:+.4f} {w[0]}" if w else "-"
        md.append(f"| {row['mut']} | {x['cell'][4:]} | {x['seed']} | {row['parent_feasible']} | {row['mutant_feasible']} | "
                  f"{fw(row['mutant_worst'])} ({fw(row['parent_worst'])}) | {row['mutant_inert']} ({row['parent_inert']}) |")
    json.dump(out, open(HERE + "/summary.json", "w"), indent=1, default=repr)
    open(HERE + "/tables.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main(sys.argv[1])
