"""Cross-spec feasibility benchmark: how do the pipeline's candidate topologies do
under *different requested constraints*? Sizes a set of good token topologies (the
feasible + closest near-feasible designs) against each spec and tabulates, per
(candidate, spec): feasible?, the binding (worst) constraint, and the sized metrics.

Specs vary in difficulty: wifi24 (S21≥12/Idd≤5/NF≤2.5, 2.44 GHz), gps-l1 (harder:
S21≥15/Idd≤3/NF≤1.8, 1.58 GHz), wideband-sdr (wideband + ripple≤2, looser Idd≤8).
For the candidate's native spec (wifi24) it uses curated sizing (fix input match at
prior best -- the reliable path); for other bands it re-sizes all-free multi-seed
(the match must be re-derived for the new f0). Writes lna/data/benchmark.md + .json.

**Two tiers, one sizing (WP-D1/D4).** Cells are sized under TIER-1 gating
(S11/S21/Idd) so the numbers stay comparable with every historical claim in this
repo, and the series-Rs NF is then measured at that same sized point, giving a
tier-2 verdict for free -- exactly `nf_contrast.py`'s "re-judge unchanged"
protocol. A tier-2 FAIL here therefore means "this design, sized for tier-1, does
not also meet NF", NOT "no sizing of this topology can meet NF" (NF was not in the
objective). Rollett K_min is reported per cell as a stability advisory.

    python lna/benchmark.py --n 6 --specs wifi24,gps-l1,wideband-sdr
    python lna/benchmark.py --all-feasible --seeds 1,2,3 --budget 8,8,2
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds
import size
from spec import Spec
from topology import Topology, parse_arrow_file

METRICS = {"s11_db": "S11", "s21_db": "S21", "idd_ma": "Idd", "nf_db": "NF"}


def _iip3_spec_status(spec_name):
    """Return the iip3_dbm status for a spec: 'measured', 'unsupported', or None.

    Plans2/23-IIP3-RUNG.md: the scoreboard must never silently pass/fail IIP3.
    It renders MEASURED (with value+verdict) when status=measured and the metric
    is present, UNMEASURED when absent or status=unsupported."""
    try:
        s = Spec.load(spec_name)
        c = s.constraints.get("iip3_dbm")
        return c.get("status") if c else None
    except Exception:
        return None


def _wl(topo):
    from novelty import wl_features
    return wl_features(topo)[0]


def _row_name(r):
    p = r.get("provenance") or {}
    src = p.get("token_file") or p.get("gen_file") or p.get("archetype") \
        or p.get("ref_deck") or "?"
    return os.path.basename(src.replace("\\", "/")), src


def candidates(n, all_feasible=False):
    """The candidate set, each with its stored best_params (for curated wifi24
    sizing) + a source path.

    `all_feasible` (the honest post-WP-D4 set) takes every distinct topology that
    has ever been TIER-1 feasible against any spec, via
    `nf_contrast.feasible_designs()` -- which prefers an IN-BOX row over the
    superseded out-of-box polish rows (the box-clamp bug, FINDINGS §13.3) and so
    never restates a claim we know was overstated. That set includes the *generated*
    dhruva-l1 feasible `seq0192` and the 4-band `rfbcs3` archetype, neither of which
    the old wifi24-closeness ranking could reach. It is then topped up to `n` with
    the closest near-feasible wifi24 candidates (the original criterion).

    Reference decks are skipped: they are hand netlists, not token topologies, and
    the sizer's benchmark path goes through `Topology`."""
    picked, used, out = set(), set(), []

    def add(r, native, name=None, src=None):
        """Append a candidate, disambiguating basenames: `seq0009.txt` is a *file*
        name and two different generator runs reuse it for different topologies, so
        the display name carries the wl_hash prefix when it would otherwise clash."""
        # dedup on wl_hash, NOT on the token list: the same topology re-emitted by
        # a different Eulerian walk has different tokens and the identical circuit.
        toks = (r.get("graph") or {}).get("tokens")
        h = r.get("wl_hash") or ""
        if not toks or h in picked:
            return
        picked.add(h)
        if name is None:
            name, src = _row_name(r)
        h = h[:6]
        if name in used:
            name = f"{name}@{h}"
        used.add(name)
        out.append((name, src, Topology(list(toks)), r.get("best_params"), native))

    if all_feasible:
        import nf_contrast
        for r in nf_contrast.feasible_designs():
            add(r, r.get("spec"))
    spec = size._spec_for_sizing("wifi24", nf_gate=False)
    rows = []
    for r in ds.load("topo_labels"):
        toks = (r.get("graph") or {}).get("tokens")
        m = r.get("metrics")
        if not toks or not m or not (r.get("provenance") or {}).get("token_file"):
            continue
        feas, viol = spec.feasible(m)
        rows.append((0 if feas else 1, sum(viol.values()) if viol else 0.0, r))
    rows.sort(key=lambda x: (x[0], x[1]))
    for _, _, r in rows:                    # top up to n with near-feasible wifi24
        if len(out) >= n:
            break
        add(r, "wifi24")
    return out


def stored_points(wl_hash):
    """{spec: best_params} for a topology, from the store -- the best point the
    pipeline has ever found for that (topology, spec), preferring an IN-BOX row.

    A benchmark that only ever re-searches would report a *worse* answer than the
    program already owns (the stored feasibles were earned with multi-seed heavy
    sizing + polish, far past this table's per-cell budget) -- so every cell also
    re-measures the stored point, which is the `nf_contrast.py` protocol, and keeps
    whichever is better. Off-diagonal cells simply have no stored point."""
    import nf_contrast
    out = {}
    for r in ds.load("topo_labels"):
        if r.get("wl_hash") != wl_hash or not r.get("best_params"):
            continue
        sp = r.get("spec")
        t1 = size._spec_for_sizing(sp, nf_gate=False)
        t2 = size._spec_for_sizing(sp, nf_gate=True)
        m = r.get("metrics") or {}
        feas, viol = t1.feasible(m)
        # in-box first, then tier-1 feasibility/violation, then TIER-2: with two
        # tier-1-feasible rows for the same key (e.g. seq0220's curated and
        # polished sizings) the tie must not go to file order -- the one that also
        # clears NF is strictly the better known point.
        rank = (1 if nf_contrast.out_of_box(r, t1) else 0, 0 if feas else 1,
                sum(viol.values()) if viol else 0.0,
                0 if t2.feasible(m)[0] else 1)
        if sp not in out or rank < out[sp][0]:
            out[sp] = (rank, r["best_params"])
    return {k: v[1] for k, v in out.items()}


def size_vs(topo, spec_name, bp, seeds=(1, 2), budget=(8, 8, 2), native=None,
            stored=None):
    """Size one cell under tier-1 gating and return the tier-1/tier-2 verdicts.

    Curated sizing (input match fixed at the stored best point) is used when this
    spec is the candidate's OWN spec -- the band it was found on -- because that is
    where `best_params` is a valid warm start; on any other band the match must be
    re-derived, so the cell is all-free multi-seed."""
    t1 = size._spec_for_sizing(spec_name, nf_gate=False)
    t2 = size._spec_for_sizing(spec_name, nf_gate=True)
    curated = (spec_name == (native or "wifi24") and bool(bp))
    nc, sg, cg = budget
    best = None

    def offer(m, how):
        nonlocal best
        if m is None:
            return
        feas, viol = t1.feasible(m)
        key = (0 if feas else 1, sum(viol.values()) if viol else 0.0)
        if best is None or key < best[0]:
            f2, _ = t2.feasible(m)
            best = (key, m, feas, viol, how, f2, None)

    for s in seeds:
        try:
            res = size.size_topology(topo, t1, seed=s, inductor_q=12, log=False,
                                     enrich_nf=True, curate=curated,
                                     prior_params=bp if curated else None,
                                     n_candidates=nc, sgd_iters=sg, cgd_iters=cg)
        except Exception:
            continue
        if res:
            offer(res.get("metrics"), "curated" if curated else "all-free")
    sp_params = (stored or {}).get(spec_name)
    if sp_params:
        try:
            import nf_contrast
            body, _ = nf_contrast._body_for({"graph": {"tokens": list(topo.tokens)}})
            if body is not None:
                offer(size.eval_metrics(body, sp_params, t2), "stored")
        except Exception:
            pass
    return best


def _binding(spec, viol):
    if not viol:
        return "-"
    name = max(viol.items(), key=lambda kv: kv[1])[0]
    for suf in ("_db", "_ma"):        # strip only a trailing unit suffix; a naive
        if name.endswith(suf):        # .replace mangled s11_max_db -> "s11x"
            return name[: -len(suf)]
    return name


def run(n, spec_names, seeds=(1, 2), budget=(8, 8, 2), all_feasible=False,
        out_json=None, resume=None):
    cands = candidates(n, all_feasible=all_feasible)
    print(f"benchmark: {len(cands)} candidates x {len(spec_names)} specs "
          f"(curated on the candidate's own band, all-free elsewhere; "
          f"seeds={seeds} budget={budget})\n", flush=True)
    table = list(resume or [])
    done = {r["candidate"] for r in table}
    for name, tfp, topo, bp, native in cands:
        if name in done:
            continue
        row = {"candidate": name, "n_dev": topo.n_devices, "native": native,
               "source": tfp, "results": {}}
        cells = []
        stored = stored_points(_wl(topo))
        for sp in spec_names:
            b = size_vs(topo, sp, bp, seeds=seeds, budget=budget, native=native,
                        stored=stored)
            if b is None:
                cells.append(f"{sp}:sim-fail")
                row["results"][sp] = {"feasible": None}
                continue
            _, m, feas, viol, how, f2, _v2 = b
            bind = _binding(size._spec_for_sizing(sp, nf_gate=False), viol)
            iip3_val = (round(m["iip3_dbm"], 2)
                        if m.get("iip3_dbm") is not None else None)
            row["results"][sp] = {"feasible": feas, "tier2": f2, "binding": bind,
                                  "S11": round(m["s11_db"], 1),
                                  "S11max": (round(m["s11_max_db"], 1)
                                             if m.get("s11_max_db") is not None else None),
                                  "S21": round(m["s21_db"], 1),
                                  "Idd": round(m.get("idd_ma") or 0, 2),
                                  "NF": (round(m["nf_db"], 2)
                                         if m.get("nf_db") is not None else None),
                                  "IIP3": iip3_val,
                                  "Kmin": (round(m["k_min"], 3)
                                           if m.get("k_min") is not None else None),
                                  "how": how}
            cells.append(f"{sp}:{('T2' if f2 else 'T1') if feas else 'bind=' + bind}")
        table.append(row)
        print(f"  {name:<22} dev={topo.n_devices:>2}  " + "  ".join(cells), flush=True)
        if out_json:
            with open(out_json, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(table, fh, indent=1)
    return write_report(table, spec_names, seeds, budget)


def write_report(table, spec_names, seeds, budget):
    n = len(table)
    y1 = {s: sum(1 for r in table if (r["results"].get(s) or {}).get("feasible"))
          for s in spec_names}
    y2 = {s: sum(1 for r in table if (r["results"].get(s) or {}).get("tier2"))
          for s in spec_names}
    # Tier-3: per spec, count cells where IIP3 was actually measured (status=measured
    # AND the metric is present in the result). NEVER silently pass/fail IIP3.
    iip3_status = {s: _iip3_spec_status(s) for s in spec_names}
    y3_iip3 = {s: sum(1 for r in table
                      if iip3_status[s] == "measured"
                      and (r["results"].get(s) or {}).get("IIP3") is not None)
               for s in spec_names}
    binding = {s: {} for s in spec_names}
    for r in table:
        for s in spec_names:
            c = r["results"].get(s) or {}
            if c.get("feasible") is False:
                binding[s][c.get("binding", "?")] = \
                    binding[s].get(c.get("binding", "?"), 0) + 1
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    lines = ["# Cross-spec feasibility benchmark", "",
             f"{n} candidate topologies sized against each spec at "
             f"**seeds={list(seeds)}, ZOAF budget={list(budget)}** (curated on the "
             "candidate's own band, all-free multi-seed elsewhere).", "",
             "**tier-1** = S11/S21/Idd (the gating every historical claim in this "
             "repo was made under). **tier-2** = tier-1 **and** the golden-validated "
             "series-Rs NF, measured at the *same* tier-1-sized point (the "
             "`nf_contrast.py` re-judge-unchanged protocol). A tier-2 miss therefore "
             "says *this sizing* does not meet NF, not that no sizing could — NF is "
             "not in the objective here. **tier-3** = tier-2 **and** IIP3 measured "
             "by the ngspice two-tone transient harness (transient-v1), only for specs "
             "that declare `iip3_dbm: {status: measured}` — specs that leave it "
             "`unsupported` show UNMEASURED in the IIP3 column, never a silent pass "
             "or fail (plans2/23-IIP3-RUNG.md). `K_min` is the worst in-band Rollett "
             "K, advisory only: **K < 1 flags a potentially unstable sizing.**", "",
             "> **What changed vs the previous table (Session 4, Track C).** The old "
             "one was a *lean-budget* artefact (`seeds=1, budget=5,5,1`) and said so: "
             "wifi24 read 4/6 there against 6/6 at full budget. This run is at full "
             "budget. Three further corrections: (1) the candidate set is now taken "
             "from the **feasible record** (`--all-feasible`), preferring the "
             "**in-box** rows after the `size.polish` box-clamp fix, so it includes "
             "the *generated* dhruva-l1 feasible `seq0192` and the 4-band `rfbcs3` "
             "archetype that a wifi24-closeness ranking could never reach; (2) every "
             "cell also re-measures the pipeline's **stored best point** for that "
             "(topology, spec) and keeps the better of that and a fresh search — "
             "without it the table reports worse than the program already owns, "
             "because the stored feasibles were earned with multi-seed heavy sizing "
             "plus polish; (3) the **NF column is real** (series-Rs). The old table's "
             "NF was the retired port-referred number and printed *negative* noise "
             "figures. Candidates are deduped on `wl_hash`, not on the token list — "
             "the same circuit re-emitted by a different Eulerian walk had been "
             "entering twice — and a `name@hash` suffix disambiguates two different "
             "topologies that share a `seqNNNN.txt` file name.", "",
             "## Per-spec yield", "",
             "| spec | tier-1 | tier-2 | IIP3 (tier-3) | binding when infeasible |",
             "|---|---|---|---|---|"]
    for sp in spec_names:
        b = ", ".join(f"`{k}` ×{v}" for k, v in
                      sorted(binding[sp].items(), key=lambda kv: -kv[1])) or "–"
        ist = iip3_status[sp]
        if ist == "measured":
            iip3_cell = f"**{y3_iip3[sp]}/{n} measured**"
        elif ist == "unsupported":
            iip3_cell = "UNMEASURED (no harness)"
        else:
            iip3_cell = "–"
        lines.append(f"| {sp} | **{y1[sp]}/{n}** | **{y2[sp]}/{n}** | {iip3_cell} | {b} |")
    lines += ["", "## Matrix (T2 = tier-2 feasible, T1 = tier-1 only, else binding "
              "constraint)", "",
              "| candidate | dev | " + " | ".join(spec_names) + " |",
              "|" + "---|" * (len(spec_names) + 2)]
    for row in table:
        cells = []
        for sp in spec_names:
            r = row["results"].get(sp, {})
            if r.get("feasible") is None:
                cells.append("sim-fail")
            elif r.get("tier2"):
                cells.append("**T2**")
            elif r.get("feasible"):
                cells.append("**T1**")
            else:
                cells.append(r.get("binding", "?"))
        lines.append(f"| {row['candidate']} | {row['n_dev']} | " + " | ".join(cells) + " |")
    lines += ["", "## Detail (best sized metrics per cell)", "",
              "| candidate | spec | tier-1 | tier-2 | S11@f0 | S11max | S21 | Idd | "
              "NF | IIP3 | K_min | binding | how |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in table:
        for sp in spec_names:
            r = row["results"].get(sp)
            if not r or r.get("feasible") is None:
                continue
            k = r.get("Kmin")
            kcell = "-" if k is None else (f"**{k}** ⚠" if k < 1.0 else f"{k}")
            ist = iip3_status.get(sp)
            iip3_v = r.get("IIP3")
            if ist == "measured" and iip3_v is not None:
                iip3_cell = f"{iip3_v} MEASURED"
            elif ist == "measured":
                iip3_cell = "UNMEASURED"
            else:
                iip3_cell = "-"
            lines.append(
                f"| {row['candidate']} | {sp} | {'yes' if r['feasible'] else 'no'} "
                f"| {'yes' if r.get('tier2') else 'no'} | {r['S11']} "
                f"| {r.get('S11max') if r.get('S11max') is not None else '-'} "
                f"| {r['S21']} | {r['Idd']} "
                f"| {r['NF'] if r['NF'] is not None else '-'} | {iip3_cell} | {kcell} "
                f"| {r['binding']} | {r.get('how', '-')} |")
    md = os.path.join(HERE, "data", "benchmark.md")
    with open(md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(HERE, "data", "benchmark.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump({"yields_tier1": y1, "yields_tier2": y2,
                   "yields_tier3_iip3": y3_iip3, "iip3_spec_status": iip3_status,
                   "binding": binding,
                   "seeds": list(seeds), "budget": list(budget), "table": table},
                  fh, indent=2)
    print(f"\ntier-1 yield: {y1}\ntier-2 yield: {y2}")
    print(f"tier-3 IIP3 measured: {y3_iip3}  (spec status: {iip3_status})")
    print(f"binding constraints (infeasible cells): {binding}")
    print(f"report -> {md}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=6, help="how many candidate topologies")
    ap.add_argument("--all-feasible", action="store_true",
                    help="seed the set with every distinct tier-1-feasible topology")
    ap.add_argument("--specs", default="wifi24,gps-l1,wideband-sdr")
    ap.add_argument("--seeds", default="1,2", help="comma list of ZOAF seeds per cell")
    ap.add_argument("--budget", default="8,8,2",
                    help="ZOAF n_candidates,sgd_iters,cgd_iters")
    ap.add_argument("--out-json", help="checkpoint the per-candidate table here "
                                       "(chunked/resumable long runs)")
    ap.add_argument("--resume", help="resume from a checkpoint written by --out-json")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild benchmark.md from --resume, simulate nothing")
    args = ap.parse_args()
    seeds = tuple(int(s) for s in args.seeds.split(","))
    budget = tuple(int(b) for b in args.budget.split(","))
    resume = None
    if args.resume and os.path.exists(args.resume):
        resume = json.load(open(args.resume, encoding="utf-8"))
    if args.report_only:
        return write_report(resume or [], args.specs.split(","), seeds, budget)
    return run(args.n, args.specs.split(","), seeds=seeds, budget=budget,
               all_feasible=args.all_feasible, out_json=args.out_json, resume=resume)


if __name__ == "__main__":
    sys.exit(main())
