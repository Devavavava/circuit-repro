"""bench-v12-audit E-d summarizer: edits.jsonl + completions.jsonl + score.jsonl
-> summary.json + tables.md (run with the cr python; no SPICE)."""
import json, os, sys, statistics, collections

ED = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.dirname(ED)
sys.path.insert(0, ED)
import ed_score as S                                              # noqa: E402

CELLS = S.cells()
LAB = S.labels()
SYN = [c for c in CELLS if not LAB[c]["retrieval"]]
RET = [c for c in CELLS if LAB[c]["retrieval"]]
EDGE = [c for c in CELLS if LAB[c]["edge"]]


def load(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def ec_labels():
    p = AUD + "/E-c/summary.json"
    if not os.path.exists(p):
        return None
    out = {}
    for r in json.load(open(p)):
        out[r["cell"]] = {"search_trivial": bool(r.get("search_trivial")),
                          "search_trivial_if_stability_required":
                              r.get("search_trivial_if_stability_required"),
                          "screen_feasible": r.get("screen_feasible"),
                          "confirmed": r.get("confirmed"),
                          "spice_min_first_fixed": r.get("spice_min_first_fixed"),
                          "spice_min_first_random": r.get("spice_min_first_expected_random")}
    return out


def main():
    edits = load(ED + "/edits.jsonl")
    comps = load(ED + "/completions.jsonl")
    score = load(ED + "/score.jsonl")
    sc = collections.defaultdict(dict)                 # (cell,key) -> seed -> rec
    for r in score:
        sc[(r["cell"], r["key"])][r["seed"]] = r

    def ev(e):
        """per-edit local outcome"""
        if not e["valid"]:
            return {"valid": False, "scored": True, "sizable": False, "n_feas": 0,
                    "feas": False, "worst": None, "seeds_run": 0}
        rr = sc.get((e["cell"], e["key"]), {})
        n_run = len(rr)
        nf = sum(1 for s in rr.values() if s.get("feasible"))
        ws = [s.get("worst") for s in rr.values() if s.get("worst") is not None]
        return {"valid": True, "scored": n_run == 3,
                "sizable": any(s.get("sizable") for s in rr.values()),
                "n_feas": nf, "feas": nf > 0, "feas2": nf >= 2,
                "worst": max(ws) if ws else None, "seeds_run": n_run,
                "secs_s1": (rr.get(1) or {}).get("secs"),
                "secs_all": sum((s.get("secs") or 0) for s in rr.values()),
                "mu_min_feas": [s.get("mu_min") for s in rr.values() if s.get("feasible")]}

    for e in edits:
        e["local"] = ev(e)
    groups = sorted({(e["model"], e["cond"]) for e in edits} |
                    {(c["model"], c["cond"]) for c in comps})
    out = {"era": S.ERA, "labels": LAB, "synthesis": SYN, "retrieval": RET, "edge": EDGE,
           "n_score_rows": len(score), "groups": {}}
    for g in groups:
        E = [e for e in edits if (e["model"], e["cond"]) == g]
        Cm = [c for c in comps if (c["model"], c["cond"]) == g]
        samples = sorted({c["sample"] for c in Cm})
        solved_any, solved_2, per_sample = set(), set(), {s: set() for s in samples}
        best_worst = {}
        for e in E:
            L = e["local"]
            if L["feas"]:
                solved_any.add(e["cell"])
                per_sample[e["sample"]].add(e["cell"])
            if L.get("feas2"):
                solved_2.add(e["cell"])
            if L["worst"] is not None:
                best_worst[e["cell"]] = max(best_worst.get(e["cell"], -9e9), L["worst"])
        ink = {c["cell"] for c in Cm if c["inkernel_feasible"]}
        valid = [e for e in E if e["valid"]]
        wb = [e for e in valid if "-wb-" in e["cell"]]
        nb = [e for e in valid if "-nb-" in e["cell"]]
        tims = [c["timing"]["total_ms"] / 60000 for c in Cm if c.get("timing")]
        topo = {}
        for band, EE in (("wb", wb), ("nb", nb)):
            topo[band] = {k: sum(1 for e in EE if e["topo"][k]) for k in
                          ("narrow_fb", "wide_fb", "wide_vin_fb", "cascode", "tank")}
            topo[band]["n_valid_edits"] = len(EE)
            topo[band]["cells_any_narrow"] = sorted({e["cell"] for e in EE if e["topo"]["narrow_fb"]})
            topo[band]["cells_any_wide"] = sorted({e["cell"] for e in EE if e["topo"]["wide_fb"]})
            topo[band]["wide_fb_feasible_edits"] = sum(1 for e in EE if e["topo"]["wide_fb"] and e["local"]["feas"])
        agree = None
        if len(samples) == 2:
            a, b = per_sample[samples[0]], per_sample[samples[1]]
            agree = {"both": len(a & b), "only_s1": len(a - b), "only_s2": len(b - a),
                     "neither": len(set(CELLS) - a - b)}
        out["groups"][f"{g[0]}|{g[1]}"] = {
            "model": g[0], "cond": g[1], "samples": samples,
            "n_completions": len(Cm),
            "empty_content": sum(1 for c in Cm if c["empty_content"]),
            "no_edits": sum(1 for c in Cm if c["n_edits"] == 0),
            "finish_length": sum(1 for c in Cm if c["finish_reason"] == "length"),
            "recovered_from_reasoning": sum(1 for c in Cm if c["recovered_from_reasoning"]),
            "llm_error": sum(1 for c in Cm if c["llm_error"]),
            "completion_tokens_mean": (statistics.mean([c["completion_tokens"] for c in Cm if c["completion_tokens"]]) if Cm else None),
            "gpu_min_per_completion_mean": statistics.mean(tims) if tims else None,
            "gpu_min_per_completion_median": statistics.median(tims) if tims else None,
            "gpu_min_per_completion_max": max(tims) if tims else None,
            "n_edits": len(E), "n_valid": len(valid),
            "n_scored": sum(1 for e in valid if e["local"]["scored"]),
            "n_sizable": sum(1 for e in valid if e["local"]["sizable"]),
            "n_feasible": sum(1 for e in valid if e["local"]["feas"]),
            "n_feasible_2of3": sum(1 for e in valid if e["local"].get("feas2")),
            "invalid_reasons": collections.Counter(
                ("inline-comment/extra tokens" if "got " in (e["error"] or "") else
                 "duplicate device name" if "duplicate device" in (e["error"] or "") else
                 (e["error"] or "")[:50]) for e in E if not e["valid"]),
            "solved_any": sorted(solved_any), "solved_2of3": sorted(solved_2),
            "solved_syn": sorted(solved_any & set(SYN)),
            "solved_ret": sorted(solved_any & set(RET)),
            "solved_edge": sorted(solved_any & set(EDGE)),
            "per_sample_solved": {s: sorted(v) for s, v in per_sample.items()},
            "s1_s2_agreement": agree,
            "inkernel_solved": sorted(ink),
            "best_worst_margin": best_worst,
            "topo": topo}
    # ZS vs FS per model (pre-reg: no claim unless >= 3 cells differ)
    zf = {}
    for m in sorted({g[0] for g in groups}):
        z, f = out["groups"].get(f"{m}|ZS"), out["groups"].get(f"{m}|FS")
        if not z or not f:
            continue
        a, b = set(z["solved_any"]), set(f["solved_any"])
        nd = len(a ^ b)
        zf[m] = {"zs_only": sorted(a - b), "fs_only": sorted(b - a), "n_differ": nd,
                 "verdict": ("difference claimable (>=3 cells differ)" if nd >= 3 else
                             "NO ZS-FS difference claimable (<3 cells differ)")}
    out["zs_vs_fs"] = zf
    # E-c comparison (if present)
    ec = ec_labels()
    if ec:
        out["ec"] = ec
        costs = []
        for c in comps:
            if not c.get("timing"):
                continue
            EE = sorted([e for e in edits if (e["model"], e["cond"], e["sample"], e["cell"]) ==
                         (c["model"], c["cond"], c["sample"], c["cell"])], key=lambda e: e["edit"])
            spice = 0.0
            first = None
            for e in EE:
                if not e["valid"]:
                    continue
                rr = sc.get((e["cell"], e["key"]), {})
                s1 = rr.get(1) or {}
                spice += (s1.get("secs") or 0) / 60
                if s1.get("feasible"):
                    first = e["edit"]
                    break
            costs.append({"model": c["model"], "cond": c["cond"], "sample": c["sample"],
                          "cell": c["cell"], "gpu_min": c["timing"]["total_ms"] / 60000,
                          "spice_min_seed1_to_first": spice, "first_feasible_edit_seed1": first})
        out["llm_cost"] = costs
    json.dump(out, open(ED + "/summary.json", "w"), indent=1, default=list)
    write_tables(out)


def write_tables(out):
    L = []
    L.append(f"E-d summary (era {out['era'][:9]}; {out['n_score_rows']} sizing rows). "
             f"Synthesis cells = {len(out['synthesis'])}, retrieval = {len(out['retrieval'])}, "
             f"EDGE = {', '.join(out['edge'])}.\n")
    L.append("| model | cond | compl. | empty/no-edit | edits | valid | sizable | feasible (any seed) | feas >=2/3 | cells solved (any) | syn /6 | ret /10 | >=2/3 seeds | EDGE | s1/s2: both, s1-only, s2-only | in-kernel solved | GPU min/compl (mean, med) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, g in out["groups"].items():
        ag = g["s1_s2_agreement"] or {}
        L.append(f"| {g['model']} | {g['cond']} | {g['n_completions']} | {g['empty_content']}/{g['no_edits']} | "
                 f"{g['n_edits']} | {g['n_valid']} ({g['n_valid']/max(1,g['n_edits']):.0%}) | {g['n_sizable']} | "
                 f"{g['n_feasible']} ({g['n_feasible']/max(1,g['n_edits']):.1%} of all) | {g['n_feasible_2of3']} | "
                 f"{len(g['solved_any'])}/16 | {len(g['solved_syn'])} | {len(g['solved_ret'])} | {len(g['solved_2of3'])} | "
                 f"{'yes' if g['solved_edge'] else 'no'} | {ag.get('both')}, {ag.get('only_s1')}, {ag.get('only_s2')} | "
                 f"{len(g['inkernel_solved'])} | {g['gpu_min_per_completion_mean']:.2f}, {g['gpu_min_per_completion_median']:.2f} |")
    L.append("\n### Topology classes emitted (valid edits)\n")
    L.append("| model | cond | wb valid edits | wb narrow shunt-fb | wb wide shunt-fb | wb wide(VIN-side) | wb cells w/ wide | wide-fb edits feasible | nb valid edits | nb cascode | nb tank | nb narrow-fb |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, g in out["groups"].items():
        w, n = g["topo"]["wb"], g["topo"]["nb"]
        L.append(f"| {g['model']} | {g['cond']} | {w['n_valid_edits']} | {w['narrow_fb']} | {w['wide_fb']} | "
                 f"{w['wide_vin_fb']} | {len(w['cells_any_wide'])}/8 | {w['wide_fb_feasible_edits']} | {n['n_valid_edits']} | "
                 f"{n['cascode']} | {n['tank']} | {n['narrow_fb']} |")
    L.append("\n### Cells solved (local, any edit/sample/seed)\n")
    L.append("| cell | label | " + " | ".join(f"{g['model'].split('-')[1]} {g['cond']}" for g in out["groups"].values()) + " |")
    L.append("|---|---|" + "---|" * len(out["groups"]))
    for c in S.cells():
        lab = ("SYN" if c in out["synthesis"] else "RET") + (" EDGE" if c in out["edge"] else "")
        if out.get("ec") and c in out["ec"]:
            lab += " ST" if out["ec"][c]["search_trivial"] else ""
        row = []
        for g in out["groups"].values():
            bw = g["best_worst_margin"].get(c)
            row.append(("**Y**" if c in g["solved_any"] else "n") + (f" ({bw:+.3f})" if bw is not None else ""))
        L.append(f"| {c} | {lab} | " + " | ".join(row) + " |")
    L.append("\n### ZS vs FS (pre-reg: no claim unless >= 3 cells differ)\n")
    for m, z in out["zs_vs_fs"].items():
        L.append(f"- {m}: ZS-only {z['zs_only']}, FS-only {z['fs_only']} -> {z['n_differ']} differ -> **{z['verdict']}**")
    L.append("\n### Invalid-edit reasons\n")
    for k, g in out["groups"].items():
        L.append(f"- {g['model']} {g['cond']}: {dict(g['invalid_reasons'])}")
    if out.get("ec"):
        L.append("\n### Cost vs E-c brute-force single-edit search (SPICE-min = seed-1 2500-eval screens)\n")
        L.append("E-c: SEARCH-TRIVIAL / confirmed / SPICE-min to first screen-feasible (fixed order, E[random]). "
                 "LLM: per completion that reaches a seed-1-feasible edit, GPU-min (llama-server total time) + "
                 "SPICE-min of its edits sized in index order up to the first seed-1-feasible one.\n")
        L.append("| cell | label | E-c trivial | E-c confirmed | E-c SPICE-min fixed / E[random] | LLM completions reaching seed-1 feasible: model cond sample (GPU-min + SPICE-min) |")
        L.append("|---|---|---|---|---|---|")
        for c in S.cells():
            e = out["ec"].get(c) or {}
            hits = [x for x in out.get("llm_cost", []) if x["cell"] == c and x["first_feasible_edit_seed1"] is not None]
            hs = "; ".join(f"{x['model'].split('-')[1]} {x['cond']} s{x['sample']} ({x['gpu_min']:.1f}+{x['spice_min_seed1_to_first']:.1f})" for x in hits) or "-"
            f1, fr = e.get("spice_min_first_fixed"), e.get("spice_min_first_random")
            lab = ("SYN" if c in out["synthesis"] else "RET") + (" EDGE" if c in out["edge"] else "")
            L.append(f"| {c} | {lab} | {e.get('search_trivial')} | {e.get('confirmed')} | "
                     f"{'-' if f1 is None else f'{f1:.1f}'} / {'-' if fr is None else f'{fr:.1f}'} | {hs} |")
        allc = out.get("llm_cost", [])
        for g in sorted({(x["model"], x["cond"]) for x in allc}):
            xs = [x for x in allc if (x["model"], x["cond"]) == g]
            L.append(f"\n- {g[0]} {g[1]}: {len(xs)} completions, total GPU-min {sum(x['gpu_min'] for x in xs):.0f}, "
                     f"seed-1 SPICE-min of all their edits (to first feasible or exhaustion) {sum(x['spice_min_seed1_to_first'] for x in xs):.0f}")
    open(ED + "/tables.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
