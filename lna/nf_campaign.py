"""Gate-D3 NF campaign: descend NF inside a tier-1 trust region (Session 6).

Session 5 left dhruva-s at **one** violated constraint -- noise, 5.58 vs 3.5 dB --
on a tier-1-clean, stable, novel design (`8c7592ea859e489a`), with 4.9 dB of S21
surplus and 1.2 mA of Idd surplus that the min-margin polish is structurally
unable to spend (raising a non-binding margin cannot raise the minimum). This
driver runs `size.constrained_descent`: minimize nf_db directly, refuse any step
that takes a tier-1 margin below `--floor`.

Sources (`--source`, comma-separated):
    store:<wl_hash prefix>   a stored design; its `best_params` is the start
    arch:<archetype name>    a templates.py archetype (sized match-first first)
    ext:<dir name>           a transcribed external topology under
                             lna/data/external/<dir>/generated/seq_*.txt

Modes:
    --mode nf     minimize nf_db, keep {s11_max_db, s21_db, idd_ma} feasible
    --mode gain   maximize s21_db, keep {s11_max_db, idd_ma} feasible and
                  nf_db <= --nf-cap

Every result is appended as an L2 row with recipe `nf-v1` (NF gated), provenance
`source_arm: nf-campaign`. Reruns of the same (wl_hash, spec) are repeat probes,
which is what we want here -- the store is append-only.

    python lna/nf_campaign.py --spec dhruva-s --source store:8c7592ea \
        --mode nf --seeds 0,1,2 --budget 300
"""
import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds            # noqa: E402
import size as S                  # noqa: E402
from novelty import wl_features   # noqa: E402
from topology import Topology, parse_arrow_file   # noqa: E402

RECIPE = "nf-v1"
# tier-1 == every gated constraint except the tier-2 NF; the match constraint is
# `s11_max_db` on the dhruva (held-over-band) specs and `s11_db` on wideband-sdr.
MATCH = ("s11_max_db", "s11_db")


def tier1_names(spec):
    return tuple(n for n, c in spec.constraints.items()
                 if c.get("status") != "unsupported" and n != "nf_db")


# ------------------------------------------------------------------ candidates
def _store_rows():
    return ds.load("topo_labels")


def resolve(source, spec_name):
    """source string -> list of {name, topo, params, origin}."""
    kind, _, arg = source.partition(":")
    out = []
    if kind == "store":
        best = {}
        for r in _store_rows():
            g = r.get("graph") or {}
            h = r.get("wl_hash") or g.get("wl_hash") or ""
            if not h.startswith(arg) or not g.get("tokens"):
                continue
            if not r.get("best_params"):
                continue
            nf = ((r.get("margins") or {}).get("nf_db") or {}).get("achieved")
            key = (h, r.get("spec"))
            # prefer this spec's own row, then the lowest NF seen for the graph
            rank = (0 if r.get("spec") == spec_name else 1,
                    nf if nf is not None else 1e9)
            if h not in best or rank < best[h][0]:
                best[h] = (rank, r)
        for h, (_, r) in sorted(best.items()):
            out.append({"name": "store:" + h[:12], "topo": Topology(r["graph"]["tokens"]),
                        "params": r["best_params"],
                        "origin": {"store_wl_hash": h, "store_spec": r.get("spec"),
                                   "store_recipe": (r.get("zoaf_cfg") or {}).get("recipe")}})
    elif kind == "arch":
        import templates as T
        for a in T.archetypes():
            if a["name"] == arg or (arg.endswith("*") and a["name"].startswith(arg[:-1])):
                out.append({"name": "arch:" + a["name"], "topo": Topology(a["seq"]),
                            "params": None, "origin": {"archetype": a["name"],
                                                       "cls": a["cls"]}})
    elif kind == "json":
        # json:<results file>[:<index>] -- resume from a previous run's point.
        # The results file carries best_params but not tokens, so the graph is
        # recovered from the store by the origin's wl_hash.
        path, _, idx = arg.rpartition(":")
        if not path or not idx.isdigit():
            path, idx = arg, None
        recs = json.load(open(path))
        recs = [recs[int(idx)]] if idx is not None else recs
        toks = {}
        for r in _store_rows():
            g = r.get("graph") or {}
            if r.get("wl_hash") and g.get("tokens"):
                toks.setdefault(r["wl_hash"], g["tokens"])
        for i, rec in enumerate(recs):
            h = (rec.get("origin") or {}).get("store_wl_hash")
            if not h or h not in toks:
                continue
            out.append({"name": f"json:{h[:10]}#{i}", "topo": Topology(toks[h]),
                        "params": rec["best_params"],
                        "origin": dict(rec.get("origin") or {},
                                       resumed_from=os.path.basename(path),
                                       resumed_mode=rec.get("mode"),
                                       resumed_idx=i)})
    elif kind == "pool":
        # pool:<generated dir>[:N] -- screen a generator pool against the spec and
        # take the N candidates whose structure is FURTHEST from the families we
        # already know (nc_cgcs / gmb_cg / rfb). The l5 question is whether the
        # learned system proposes a different input stage, so ranking by novelty
        # against the incumbents is the whole point of the ordering.
        import templates as T
        from novelty import wl_features, nn_similarity
        d, _, n = arg.rpartition(":")
        if not d or not n.isdigit():
            d, n = arg, "12"
        spec = S._spec_for_sizing(spec_name)
        known = []
        for aa in T.archetypes():
            if aa["name"].startswith(("nccgcs", "gmbcg", "rfb")):
                known.append((aa["name"], wl_features(Topology(aa["seq"]))[1]))
        scored = []
        for p in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
            try:
                t = Topology(parse_arrow_file(p))
            except Exception:
                continue
            if not t.valid or not spec.structural_screen(t)[0]:
                continue
            sim, who = nn_similarity(wl_features(t)[1], known)
            scored.append((sim, p, t, who))
        scored.sort(key=lambda s: s[0])          # least like the incumbents first
        print(f"  pool {os.path.basename(d)}: {len(scored)} of "
              f"{len(glob.glob(os.path.join(d, 'seq*.txt')))} pass the {spec_name} "
              f"screen; taking the {min(int(n), len(scored))} most structurally distinct")
        for sim, p, t, who in scored[:int(n)]:
            out.append({"name": "pool:" + os.path.basename(p).replace(".txt", ""),
                        "topo": t, "params": None,
                        "origin": {"pool": os.path.basename(d),
                                   "token_file": os.path.relpath(p, HERE),
                                   "nn_sim_to_known": round(sim, 4),
                                   "nn_nearest_known": who}})
    elif kind == "ext":
        pats = sorted(glob.glob(os.path.join(
            HERE, "data", "external", arg, "generated", "seq_*.txt")))
        for p in pats:
            out.append({"name": "ext:" + arg, "topo": Topology(parse_arrow_file(p)),
                        "params": None,
                        "origin": {"external": arg, "seq_file": os.path.relpath(p, HERE)}})
    else:
        raise SystemExit(f"unknown source kind {kind!r}")
    return out


# ------------------------------------------------------------------- reporting
def _row(m):
    f = lambda v, d="   -  ": (f"{v:6.2f}" if isinstance(v, float) else d)  # noqa: E731
    s11 = m.get('s11_max_db')
    s11 = m.get('s11_db') if s11 is None else s11
    return (f"{f(s11)} {f(m.get('s21_db'))} "
            f"{f(m.get('idd_ma'))} {f(m.get('nf_db'))} "
            f"{(f'{m.get('k_min'):7.3g}' if m.get('k_min') is not None else '      -')}")


HDR = (f"{'candidate':<22} {'seed':>4} {'sims':>5} {'S11*':>6} {'S21':>6} "
       f"{'Idd':>6} {'NF':>6} {'K_min':>7} {'viol':>7}  verdict")


def run(spec_name, sources, seeds, budget, mode, nf_cap, floor, jitter,
        pre_budget, log, out_json, keep_set="tier1", fresh=False,
        s21_floor=None):
    spec = S._spec_for_sizing(spec_name)
    assert S.nf_is_gated(spec), f"{spec_name} does not gate nf_db"
    nf_lim = (spec.constraints.get("nf_db") or {}).get("max")
    cands = []
    for s in sources:
        cands += resolve(s, spec_name)
    if not cands:
        raise SystemExit("no candidates resolved")
    def _c(names):
        return {n: {k: c[k] for k in ("min", "max") if k in c}
                for n, c in spec.constraints.items() if n in names}

    if mode == "nf":
        # `keep_set` selects the trust region. `none` measures the family's raw NF
        # floor (degenerate -- a passive network has NF ~ 0); `s11` is the
        # physically meaningful floor: the lowest noise reachable while the
        # broadband match still holds; `tier1` is the Gate-D3 question.
        target = ("nf_db", "min")
        t1 = tier1_names(spec)
        keep = {"tier1": _c(t1), "none": {}, "s11": _c(MATCH),
                "s11idd": _c(MATCH + ("idd_ma",)),
                "s11gain": _c(MATCH + ("s21_db",))}[keep_set]
    elif mode == "match":
        # The opposite attack. Most of the *generated* pool already has the noise
        # and the gain and no input match at all (§20's rung-1 lead `seq0126`:
        # NF 2.73 at S21 16.0, s11_max -0.01). Descend the worst-case S11 with NF
        # and gain as the trust region instead of the other way round.
        target = ("s11_max_db" if "s11_max_db" in spec.constraints else "s11_db",
                  "min")
        keep = {n: {k: c[k] for k in ("min", "max") if k in c}
                for n, c in spec.constraints.items()
                if n in ("s21_db", "idd_ma", "s21_ripple_db")}
        keep["nf_db"] = {"max": nf_cap}
        if s21_floor is not None:
            keep["s21_db"] = {"min": s21_floor}
    else:
        target = ("s21_db", "max")
        keep = {n: {k: c[k] for k in ("min", "max") if k in c}
                for n, c in spec.constraints.items()
               if n in MATCH + ("idd_ma", "s21_ripple_db")}
        keep["nf_db"] = {"max": nf_cap}
    print(f"NF campaign vs {spec_name} (nf gated <= {nf_lim} dB) | mode={mode} "
          f"target={target[0]}:{target[1]} floor={floor} "
          f"keep={ {k: v for k, v in keep.items()} }")
    print(f"{len(cands)} candidate(s) x {len(seeds)} seed(s) x budget {budget}\n")
    print(HDR)
    results = []
    for c in cands:
        topo, params = c["topo"], c["params"]
        prep = S.prepared_body(topo, inductor_q=12)
        if prep is None:
            print(f"{c['name']:<22}    -     -   (bias insert skipped)")
            continue
        if params:
            m0 = S.eval_metrics(prep[0], params, spec, nf_gated=True)
            if m0 is None:
                print(f"{c['name']:<22}    -     -   (start point does not simulate)")
                continue
            ok = S.replay_ok(topo, params, spec, m0, sigma=1.0)
            print(f"{c['name']:<22} {'start':>4} {1:>5} {_row(m0)} "
                  f"{sum(spec.feasible(m0)[1].values()):>7.3f}  replay_ok={ok}")
        else:
            t0 = time.time()
            pre = S.size_match_first(topo, spec, seed=1, inductor_q=12,
                                     budget=pre_budget, polish_budget=200)
            if pre is None or pre.get("metrics") is None:
                print(f"{c['name']:<22}    -     -   (match-first sizing failed)")
                continue
            params, m0 = pre["best_params"], pre["metrics"]
            print(f"{c['name']:<22} {'mf':>4} {pre['n_evals']:>5} {_row(m0)} "
                  f"{sum(spec.feasible(m0)[1].values()):>7.3f}  [{time.time()-t0:.0f}s]")
        best = None
        for seed in seeds:
            t0 = time.time()
            start = params
            if fresh:
                # An independent GLOBAL start per seed: re-run the match-first
                # ZOAF with this seed and descend from *that* matched point. A
                # coordinate descent only ever reports a local floor; the family
                # floor needs several basins, and re-sizing is the only way to
                # get a genuinely different one.
                pre = S.size_match_first(topo, spec, seed=seed + 1, inductor_q=12,
                                         budget=pre_budget, polish_budget=0)
                if pre is None or pre.get("metrics") is None:
                    print(f"{c['name']:<22} {seed:>4}     -   (restart sizing failed)")
                    continue
                start = pre["best_params"]
                print(f"{c['name']:<22} {'r' + str(seed):>4} {pre['n_evals']:>5} "
                      f"{_row(pre['metrics'])} "
                      f"{sum(spec.feasible(pre['metrics'])[1].values()):>7.3f}  restart")
            res = S.constrained_descent(
                topo, spec, start, target=target, keep=keep, budget=budget,
                floor=floor, seed=seed, jitter=(0.0 if fresh else (jitter if seed else 0.0)),
                prepared=prep)
            if res is None or res.get("metrics") is None:
                print(f"{c['name']:<22} {seed:>4}     -   (descent failed)")
                continue
            m, bp, ne = res["metrics"], res["best_params"], res["n_evals"]
            feas, viol = spec.feasible(m)
            tot = sum(viol.values()) if viol else 0.0
            t1_ok = all(k not in viol for k in tier1_names(spec))
            print(f"{c['name']:<22} {seed:>4} {ne:>5} {_row(m)} {tot:>7.3f}  "
                  f"{'** TIER-2 FEASIBLE **' if feas else ('tier-1 ok' if t1_ok else '')}"
                  f"  [{time.time()-t0:.0f}s]")
            rec = {"candidate": c["name"], "seed": seed, "mode": mode,
                   "spec": spec_name, "n_evals": ne, "metrics": m,
                   "feasible": feas, "tier1_ok": t1_ok, "violation": tot,
                   "best_params": bp, "origin": c["origin"]}
            results.append(rec)
            if best is None or (m.get(target[0]) is not None and
                                ((target[1] == "min" and m[target[0]] < best[0]) or
                                 (target[1] == "max" and -m[target[0]] < best[0]))
                                and t1_ok >= best[3]):
                best = ((m[target[0]] if target[1] == "min" else -m[target[0]]),
                        m, bp, t1_ok, ne, feas)
            if log:
                S.log_l2_result(spec, topo, m, feas, bp,
                                dict({"source_arm": "nf-campaign", "mode": mode,
                                      "keep": keep_set,
                                      "seed": seed, "floor": floor, "fresh": fresh,
                                      "inductor_q": 12}, **c["origin"]),
                                RECIPE, ne, inductor_q=12, repeat_probe=True)
        if best:
            print(f"{'':<22} {'BEST':>4}       {_row(best[1])}")
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w") as fh:
            json.dump(results, fh, indent=1, default=str)
        print(f"\nwrote {len(results)} result(s) -> {out_json}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="dhruva-s")
    ap.add_argument("--source", required=True,
                    help="comma-separated store:<hash>|arch:<name>|ext:<dir>")
    ap.add_argument("--mode", default="nf", choices=("nf", "gain", "match"))
    ap.add_argument("--keep", default="tier1",
                    choices=("tier1", "none", "s11", "s11idd", "s11gain"),
                    help="mode=nf trust region")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--budget", type=int, default=300)
    ap.add_argument("--pre-budget", type=int, default=8,
                    help="ZOAF budget for the match-first pre-size (no prior params)")
    ap.add_argument("--nf-cap", type=float, default=4.0, help="mode=gain NF ceiling")
    ap.add_argument("--floor", type=float, default=0.0,
                    help="required normalized margin on kept constraints")
    ap.add_argument("--jitter", type=float, default=0.10,
                    help="log-uniform start jitter for seeds != 0")
    ap.add_argument("--s21-floor", dest="s21_floor", type=float, default=None,
                    help="mode=match: gain floor to hold (default: the spec min)")
    ap.add_argument("--fresh", action="store_true",
                    help="per-seed independent match-first restart (global multi-start)")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(a.spec, [s for s in a.source.split(",") if s],
        [int(s) for s in a.seeds.split(",") if s != ""],
        a.budget, a.mode, a.nf_cap, a.floor, a.jitter, a.pre_budget,
        not a.no_log, a.out, a.keep, a.fresh, a.s21_floor)


if __name__ == "__main__":
    main()
