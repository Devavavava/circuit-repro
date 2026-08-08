"""Cross-spec feasibility benchmark: how do the pipeline's candidate topologies do
under *different requested constraints*? Sizes a set of good token topologies (the
feasible + closest near-feasible designs) against each spec and tabulates, per
(candidate, spec): feasible?, the binding (worst) constraint, and the sized metrics.

Specs vary in difficulty: wifi24 (S21≥12/Idd≤5/NF≤2.5, 2.44 GHz), gps-l1 (harder:
S21≥15/Idd≤3/NF≤1.8, 1.58 GHz), wideband-sdr (wideband + ripple≤2, looser Idd≤8).
For the candidate's native spec (wifi24) it uses curated sizing (fix input match at
prior best -- the reliable path); for other bands it re-sizes all-free multi-seed
(the match must be re-derived for the new f0). Writes lna/data/benchmark.md + .json.

    python lna/benchmark.py --n 6 --specs wifi24,gps-l1,wideband-sdr
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds
import size
from topology import Topology, parse_arrow_file

METRICS = {"s11_db": "S11", "s21_db": "S21", "idd_ma": "Idd", "nf_db": "NF"}


def candidates(n):
    """Top-n good token topologies by wifi24 closeness (feasible first), each with
    its stored best_params (for curated wifi24 sizing) + a seq path."""
    spec = size._spec_for_sizing("wifi24")
    rows = []
    for r in ds.load("topo_labels"):
        toks = (r.get("graph") or {}).get("tokens")
        m = r.get("metrics")
        tfp = (r.get("provenance") or {}).get("token_file", "")
        if not toks or not m or not tfp:
            continue
        feas, viol = spec.feasible(m)
        rows.append((0 if feas else 1, sum(viol.values()) if viol else 0.0,
                     tfp, toks, r.get("best_params")))
    rows.sort(key=lambda x: (x[0], x[1]))
    seen, out = set(), []
    for _, _, tfp, toks, bp in rows:
        h = tuple(toks)
        if h in seen:
            continue
        seen.add(h)
        out.append((os.path.basename(tfp), tfp, Topology(toks), bp))
        if len(out) >= n:
            break
    return out


def size_vs(topo, spec_name, bp, seeds=(1, 2), budget=(8, 8, 2)):
    spec = size._spec_for_sizing(spec_name)
    curated = (spec_name == "wifi24" and bool(bp))
    nc, sg, cg = budget
    best = None
    for s in seeds:
        try:
            res = size.size_topology(topo, spec, seed=s, inductor_q=12, log=False,
                                     curate=curated, prior_params=bp if curated else None,
                                     n_candidates=nc, sgd_iters=sg, cgd_iters=cg)
        except Exception:
            continue
        if not (res and res.get("metrics")):
            continue
        m = res["metrics"]
        feas, viol = spec.feasible(m)
        key = (0 if feas else 1, sum(viol.values()) if viol else 0.0)
        if best is None or key < best[0]:
            best = (key, m, feas, viol, curated)
    return best


def _binding(spec, viol):
    if not viol:
        return "-"
    return max(viol.items(), key=lambda kv: kv[1])[0].replace("_db", "").replace("_ma", "")


def run(n, spec_names, seeds=(1, 2), budget=(8, 8, 2)):
    cands = candidates(n)
    print(f"benchmark: {len(cands)} candidates x {len(spec_names)} specs "
          f"(curated on wifi24, all-free elsewhere; seeds={seeds} budget={budget})\n",
          flush=True)
    table, yields = [], {s: 0 for s in spec_names}
    binding = {s: {} for s in spec_names}
    for name, tfp, topo, bp in cands:
        row = {"candidate": name, "n_dev": topo.n_devices, "results": {}}
        cells = []
        for sp in spec_names:
            b = size_vs(topo, sp, bp, seeds=seeds, budget=budget)
            if b is None:
                cells.append(f"{sp}:sim-fail")
                row["results"][sp] = {"feasible": None}
                continue
            _, m, feas, viol, curated = b
            yields[sp] += int(feas)
            bind = _binding(size._spec_for_sizing(sp), viol)
            if not feas:
                binding[sp][bind] = binding[sp].get(bind, 0) + 1
            row["results"][sp] = {"feasible": feas, "binding": bind,
                                  "S11": round(m["s11_db"], 1), "S21": round(m["s21_db"], 1),
                                  "Idd": round(m.get("idd_ma") or 0, 2),
                                  "NF": round(m.get("nf_db") or 0, 1), "curated": curated}
            cells.append(f"{sp}:{'FEAS' if feas else 'bind=' + bind}")
        table.append(row)
        print(f"  {name:<12} dev={topo.n_devices:>2}  " + "  ".join(cells), flush=True)

    # write report
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    lines = ["# Cross-spec feasibility benchmark", "",
             f"{len(cands)} candidate topologies (feasible + closest near-feasible), "
             "sized against each spec (curated on wifi24, all-free multi-seed else).", "",
             "## Per-spec yield (feasible / total)", ""]
    for sp in spec_names:
        lines.append(f"- **{sp}**: {yields[sp]}/{len(cands)} feasible; "
                     f"binding when not: {binding[sp] or '-'}")
    lines += ["", "## Matrix (F = feasible, else binding constraint)", "",
              "| candidate | dev | " + " | ".join(spec_names) + " |",
              "|" + "---|" * (len(spec_names) + 2)]
    for row in table:
        cells = []
        for sp in spec_names:
            r = row["results"].get(sp, {})
            cells.append("**F**" if r.get("feasible") else
                         (r.get("binding", "?") if r.get("feasible") is not None else "sim-fail"))
        lines.append(f"| {row['candidate']} | {row['n_dev']} | " + " | ".join(cells) + " |")
    lines += ["", "## Detail (best sized metrics per cell)", "",
              "| candidate | spec | feas | S11 | S21 | Idd | NF | binding |",
              "|---|---|---|---|---|---|---|---|"]
    for row in table:
        for sp in spec_names:
            r = row["results"].get(sp)
            if r and r.get("feasible") is not None:
                lines.append(f"| {row['candidate']} | {sp} | {'yes' if r['feasible'] else 'no'} "
                             f"| {r['S11']} | {r['S21']} | {r['Idd']} | {r['NF']} | {r['binding']} |")
    md = os.path.join(HERE, "data", "benchmark.md")
    with open(md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(HERE, "data", "benchmark.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump({"yields": yields, "binding": binding, "table": table}, fh, indent=2)
    print(f"\nper-spec yield: {yields}")
    print(f"binding constraints (infeasible cells): {binding}")
    print(f"report -> {md}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=6, help="how many candidate topologies")
    ap.add_argument("--specs", default="wifi24,gps-l1,wideband-sdr")
    ap.add_argument("--seeds", default="1,2", help="comma list of ZOAF seeds per cell")
    ap.add_argument("--budget", default="8,8,2",
                    help="ZOAF n_candidates,sgd_iters,cgd_iters")
    args = ap.parse_args()
    seeds = tuple(int(s) for s in args.seeds.split(","))
    budget = tuple(int(b) for b in args.budget.split(","))
    return run(args.n, args.specs.split(","), seeds=seeds, budget=budget)


if __name__ == "__main__":
    sys.exit(main())
