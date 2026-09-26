"""Summarize E-a / E-b results.json into per-cell tables + decision verdicts."""
import json, sys
from collections import defaultdict

BASE = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/"


def fmt(x):
    return "n/a" if x is None else f"{x:+.4f}"


def ea():
    rows = json.load(open(BASE + "E-a/results.json"))["rows"]
    by = defaultdict(list)
    for r in rows:
        by[(r["cell"], r["delta"])].append(r)
    cells = sorted({r["cell"] for r in rows})
    out = ["| cell | d=0 feas seeds | d=0 best worst-margin (binding) | d=0.02 | d=0.05 | d=0.10 | headroom | EDGE |",
           "|---|---|---|---|---|---|---|---|"]
    n_edge = 0
    verdict = {}
    for c in cells:
        feas = {d: sum(bool(r.get("feasible")) for r in by[(c, d)]) for d in (0.0, 0.02, 0.05, 0.10)}
        b0 = [r for r in by[(c, 0.0)] if r.get("worst") is not None]
        best = max(b0, key=lambda r: r["worst"]) if b0 else None
        head = 0.0 if feas[0.0] else None
        for d in (0.02, 0.05, 0.10):
            if feas[d]:
                head = d
        edge = head is None or head < 0.02
        n_edge += edge
        verdict[c] = {"headroom": head, "edge": edge, "feas_seeds": feas}
        hs = "none (d=0 fails)" if head is None else f"{head:.2f}"
        out.append(f"| {c} | {feas[0.0]}/3 | {fmt(best['worst']) if best else 'n/a'} ({best['binding'] if best else '-'}) "
                   f"| {feas[0.02]}/3 | {feas[0.05]}/3 | {feas[0.10]}/3 | {hs} | {'EDGE' if edge else '-'} |")
    rule = ("RE-CALIBRATE (>= 8/16 EDGE)" if n_edge >= 8 else "OK (< 8/16 EDGE)")
    out.append(f"\n**EDGE cells: {n_edge}/16 -> {rule}**")
    return "\n".join(out), verdict, n_edge


def eb():
    rows = json.load(open(BASE + "E-b/results.json"))["rows"]
    by = defaultdict(list)
    for r in rows:
        by[(r["cell"], r["cand"])].append(r)
    cells = sorted({r["cell"] for r in rows})
    fams = sorted({r["cand"] for r in rows})
    short = {f: f.split("-")[1] for f in fams}
    hdr = "| cell | " + " | ".join(f"{short[f]} feas / best worst (binding)" for f in fams) + " | RETRIEVAL |"
    out = [hdr, "|" + "---|" * (len(fams) + 2)]
    verdict, n_ret = {}, 0
    for c in cells:
        cols, solvers = [], []
        for f in fams:
            rs = by[(c, f)]
            nf = sum(bool(r.get("feasible")) for r in rs)
            ns = sum(bool(r.get("not_sizable")) for r in rs)
            ok = [r for r in rs if r.get("worst") is not None]
            if nf:
                solvers.append(short[f])
            if not ok:
                cols.append(f"unsizable ({ns}/3)" if ns else "no metrics")
            else:
                b = max(ok, key=lambda r: r["worst"])
                cols.append(f"{nf}/3 {fmt(b['worst'])} ({b['binding']})")
        ret = bool(solvers)
        n_ret += ret
        verdict[c] = {"retrieval": ret, "solved_by": solvers}
        out.append(f"| {c} | " + " | ".join(cols) + f" | {'RETRIEVAL (' + ','.join(solvers) + ')' if ret else '-'} |")
    out.append(f"\n**RETRIEVAL cells: {n_ret}/16; synthesis benchmark = {16 - n_ret} non-RETRIEVAL cells**")
    return "\n".join(out), verdict, n_ret


if __name__ == "__main__":
    which = sys.argv[1]
    t, v, n = ea() if which == "E-a" else eb()
    print(t)
    json.dump(v, open(BASE + f"{which}/verdicts.json", "w"), indent=1)
