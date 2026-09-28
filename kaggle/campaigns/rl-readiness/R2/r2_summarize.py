"""rl-readiness R2 summary -> summary.json + tables.md (definitions = E-d's ed_summarize).

feasible edit  = valid edit with >=1 of seeds 1,2,3 feasible (3x2500 bptm45); rate over ALL edits
cell solved    = any edit of any sample feasible at any seed;  >=2/3 = an edit feasible at >=2 seeds
SYN/RET/EDGE   = bench-v12-audit E-b retrieval / E-a edge labels (ed_score.labels)
shunt-fb       = ed_score.topo_flags wide_fb / wide_vin_fb over wideband valid edits
reasoning vs answer tokens: CAP exact (per-phase tokens_predicted); NT/BASE split the
    completion tokens by the char ratio reasoning:content, with chars/token calibrated
    per side on CAP (exact counts + chars) -- BASE/NT split is therefore an estimate.
GPU-min/compl  = llama-server prompt+eval time (BASE: log `total time`; CAP/NT: response timings)
decision rule (pre-reg R2): acceptable iff validity >= 95%, cells solved drop <= 1 vs BASE, and
    per-edit feasible rate not lower by > 5 points; choose the cheapest acceptable.
"""
import json, os, sys, statistics as st
R2 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R2)
import r2_score as S                                            # noqa: E402

CONDS = ("BASE", "CAP", "NT")


def f0(x):
    return "-" if x is None else "%.0f" % x


def rows(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def main():
    lab = S.E.labels()
    edits, comps = rows(R2 + "/edits.jsonl"), rows(R2 + "/completions.jsonl")
    scores = {m: {} for m in ("plain", "gate", "inloop")}
    for m in scores:
        for r in rows(R2 + f"/score-{m}.jsonl"):
            if r.get("crashed"):
                continue
            scores[m][(r["cell"], r["key"], r["seed"])] = r
    # chars/token calibration from CAP
    cap = [c for c in comps if c["cond"] == "CAP" and c.get("reasoning_tokens")]
    cpt_r = (sum(c["reasoning_chars"] for c in cap) / max(1, sum(c["reasoning_tokens"] for c in cap))) if cap else None
    cap_a = [c for c in comps if c["cond"] == "CAP" and c.get("answer_tokens")]
    cpt_a = (sum(c["content_chars"] for c in cap_a) / max(1, sum(c["answer_tokens"] for c in cap_a))) if cap_a else None
    out = {"chars_per_token": {"reasoning": cpt_r, "answer": cpt_a}, "conds": {}}
    for cond in CONDS:
        C = [c for c in comps if c["cond"] == cond]
        Ed = [e for e in edits if e["cond"] == cond]
        if not C:
            continue
        g = {"n_completions": len(C), "n_edits": len(Ed),
             "n_valid": sum(e["valid"] for e in Ed)}
        ct = [c["completion_tokens"] for c in C if c.get("completion_tokens") is not None]
        g["completion_tokens_mean"] = st.mean(ct) if ct else None
        rt, at = [], []
        for c in C:
            if c.get("reasoning_tokens") is not None:
                rt.append(c["reasoning_tokens"]); at.append(c["answer_tokens"])
            elif cpt_r and cpt_a and c.get("completion_tokens") is not None:
                wr = (c["reasoning_chars"] or 0) / cpt_r
                wa = (c["content_chars"] or 0) / cpt_a
                f = wr / (wr + wa) if (wr + wa) else 0
                rt.append(c["completion_tokens"] * f); at.append(c["completion_tokens"] * (1 - f))
        g["reasoning_tokens_mean"] = st.mean(rt) if rt else None
        g["answer_tokens_mean"] = st.mean(at) if at else None
        g["token_split_exact"] = cond == "CAP"
        g["finish_length"] = sum(c.get("finish_reason") == "length" for c in C)
        g["empty"] = sum(bool(c.get("empty_content")) for c in C)
        g["no_edit"] = sum(c.get("n_edits") == 0 for c in C)
        g["recovered_from_reasoning"] = sum(bool(c.get("recovered_from_reasoning")) for c in C)
        g["think_closed_naturally"] = sum(bool(c.get("think_closed_naturally")) for c in C) if cond == "CAP" else None
        gm = [c["gpu_ms"] / 60000 for c in C if c.get("gpu_ms")]
        g["gpu_min_per_completion"] = [st.mean(gm), st.median(gm), max(gm)] if gm else None
        g["gpu_min_total"] = sum(gm) if gm else None
        g["validity"] = g["n_valid"] / max(1, g["n_edits"])
        wb = [e for e in Ed if e["valid"] and lab[e["cell"]]["band"] == "wb"]
        g["wb_valid"] = len(wb)
        g["wb_wide_fb"] = sum(e["topo"]["wide_fb"] for e in wb)
        g["wb_wide_vin_fb"] = sum(e["topo"]["wide_vin_fb"] for e in wb)
        g["wb_cells_with_wide_fb"] = len({e["cell"] for e in wb if e["topo"]["wide_fb"]})
        for m, sc in scores.items():
            per = []
            complete = True
            for e in Ed:
                if not e["valid"]:
                    continue
                rr = [sc.get((e["cell"], e["key"], s)) for s in S.SEEDS]
                if any(r is None for r in rr):
                    complete = False
                nf = sum(1 for r in rr if r and r.get("feasible"))
                per.append((e, nf))
            solved = sorted({e["cell"] for e, nf in per if nf > 0})
            solved2 = sorted({e["cell"] for e, nf in per if nf >= 2})
            nfe = sum(1 for _e, nf in per if nf > 0)
            if not per or not any(sc.get((e["cell"], e["key"], s)) for e, _ in per for s in S.SEEDS):
                continue
            g[m] = {"complete": complete,
                    "n_feasible_edits": nfe,
                    "feasible_rate_all_edits": nfe / max(1, g["n_edits"]),
                    "feasible_rate_valid_edits": nfe / max(1, g["n_valid"]),
                    "cells_solved": len(solved),
                    "syn": sum(not lab[c]["retrieval"] for c in solved),
                    "ret": sum(lab[c]["retrieval"] for c in solved),
                    "edge": any(lab[c]["edge"] for c in solved),
                    "cells_solved_2of3": len(solved2),
                    "solved": solved,
                    "s1_s2": [len({e["cell"] for e, nf in per if nf and e["sample"] == k}) for k in (1, 2)]}
        out["conds"][cond] = g
    # decision rule (plain scores)
    B = out["conds"].get("BASE", {}).get("plain")
    dec = {}
    for cond in ("CAP", "NT"):
        g = out["conds"].get(cond)
        if not g or "plain" not in g or not B:
            continue
        p = g["plain"]
        v_ok = g["validity"] >= 0.95
        c_ok = (B["cells_solved"] - p["cells_solved"]) <= 1
        f_ok = (B["feasible_rate_all_edits"] - p["feasible_rate_all_edits"]) <= 0.05
        dec[cond] = {"validity_ok": v_ok, "cells_drop_ok": c_ok, "feasible_rate_ok": f_ok,
                     "acceptable": v_ok and c_ok and f_ok,
                     "cells_drop": B["cells_solved"] - p["cells_solved"],
                     "feasible_rate_drop_pts": 100 * (B["feasible_rate_all_edits"] - p["feasible_rate_all_edits"])}
    acc = [c for c in dec if dec[c]["acceptable"]]
    cost = {c: (out["conds"][c]["gpu_min_per_completion"] or [9e9])[0] for c in acc}
    out["decision"] = {"per_condition": dec,
                       "chosen": (min(cost, key=cost.get) if cost else "BASE (thinking on)")}
    json.dump(out, open(R2 + "/summary.json", "w"), indent=1)
    # table
    L = ["| cond | compl. | tokens mean (reasoning / answer) | finish=length | GPU-min/compl mean, med, max | edits | valid | feasible edits (% all) | cells solved all/SYN/RET | >=2/3 | EDGE | wb wide shunt-fb (VIN-side) / wb valid, cells | gate-only solved | gate+inloop solved |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cond in CONDS:
        g = out["conds"].get(cond)
        if not g:
            continue
        p = g.get("plain") or {}
        gm = g["gpu_min_per_completion"] or [0, 0, 0]

        def sv(m):
            x = g.get(m)
            return "-" if not x else f"{x['cells_solved']} ({x['syn']}/{x['ret']}){'' if x['complete'] else ' PARTIAL'}"
        L.append(f"| {cond} | {g['n_completions']} | {f0(g['completion_tokens_mean'])} ({f0(g['reasoning_tokens_mean'])} / {f0(g['answer_tokens_mean'])}){'' if g['token_split_exact'] else ' est.'} | "
                 f"{g['finish_length']} | {gm[0]:.2f}, {gm[1]:.2f}, {gm[2]:.2f} | {g['n_edits']} | {g['n_valid']} ({g['validity']:.0%}) | "
                 f"{p.get('n_feasible_edits', '-')} ({100 * p.get('feasible_rate_all_edits', 0):.1f}%) | "
                 f"{p.get('cells_solved', '-')}/{p.get('syn', '-')}/{p.get('ret', '-')}{'' if p.get('complete', True) else ' PARTIAL'} | {p.get('cells_solved_2of3', '-')} | "
                 f"{'yes' if p.get('edge') else 'no'} | {g['wb_wide_fb']} ({g['wb_wide_vin_fb']}) / {g['wb_valid']}, {g['wb_cells_with_wide_fb']}/8 | {sv('gate')} | {sv('inloop')} |")
    L.append("")
    L.append("Decision: " + json.dumps(out["decision"]))
    open(R2 + "/tables.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
