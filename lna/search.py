"""WP-SEARCH rung-1 (plans2/03-SEARCH §1) — best-of-N rerank, controlled.

Rung 1 spends SPICE only where the critic says to: rank a generated pool, size
the top-k, and compare to sizing k *random* picks from the same pool at equal
budget. The yardstick is **feasible-or-near-feasible designs per equal sizing
budget** (03-SEARCH's fixed metric); Gate S1 wants the critic-picked set to hold
>= 2x the control's.

Two modes live here.

**`--rerank` (offline, the original).** Runs the experiment retrospectively on
the already-sized generated pool: the campaign labeled 142 generated topologies,
so their true margins are real SPICE results (§4 rule 4 satisfied). The critic is
trained ONLY on non-generated rows, so the pool is out-of-sample -- the
source-shift scenario framed as a selection experiment, at no new compute.

**`--pool` / `--rank` / `--size` / `--s1` (LIVE, 2026-08-09).** The real rung-1
experiment 03-SEARCH §1 asks for and that had never been run: a fresh, never-sized
candidate pool, critic-v2 ranking, `--size` on the top-k, and an equal-budget
random control drawn from the identical pool. Split into four steps because the
critic needs torch (analoggenie py 3.8) while the sizer needs the py-3.14 analysis
stack -- the same two-interpreter split `evolve.py` / `evolve_score.py` use.

  1. `python lna/search.py --pool DIR --spec dhruva-s --out P.json`
        L0 screen -> WL-dedup -> drop anything already sized against THIS spec.
  2. `<analoggenie py> lna/search.py --rank --pool-json P.json --snapshot v5-train --out R.json`
        critic v2 (GNN ens-5) trained LEAK-FREE (every store row whose wl_hash is
        in the pool is dropped from training), scores `mean - beta*std`.
  3. `python lna/search.py --size --rank-json R.json --k 30 --out S.json`
        sizes the UNION of {critic top-k} and {k seeded-random picks} exactly once
        each -- shared candidates are simulated once and credited to both arms, so
        the budgets stay equal and neither arm is handicapped by the overlap.
  4. `python lna/search.py --s1 --sized-json S.json`
        the Gate-S1 scoreboard: raw >=2x bar AND the restated skill bar (§14.6).

    "C:/Users/Devavrat/radioconda/envs/analoggenie/python.exe" lna/search.py --rerank
    python lna/search.py --rerank --arm knn      # baseline only (torch-free)
"""
import argparse
import glob as globmod
import json
import os
import random
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import critic  # noqa: E402
import datastore as ds  # noqa: E402

BETA = 1.0                        # search consumes mean - beta*sigma (§4 rule 1)
# The fixed sizing protocol, byte-identical to the one FINDINGS §16 used for the
# control-experiment novel front: a light all-free ZOAF scan then a box-clamped
# bounded polish from its best point. Both rung-1 arms get exactly this.
SCAN_BUDGET = dict(n_candidates=4, sgd_iters=5, cgd_iters=1)
POLISH_BUDGET = 60
RECIPE = "rung1-v1"


def _split(data, spec_name):
    """train = non-generated (corpus+templates+refs); the generated rows split into
    old (P1/P2 arms) vs p5 by token_file -- ranked by the SAME critic so we can see
    whether the memorization-broken P5 distribution is more critic-rankable. The
    critic never trains on any generated row (either pool is out-of-sample)."""
    gen = [d for d in data if d["arm"].startswith("campaign-G")
           and d["spec"] == spec_name]
    train = [d for d in data if not d["arm"].startswith("campaign-G")
             and d["spec"] == spec_name]

    def tf(d):
        return (d["row"].get("provenance") or {}).get("token_file", "")
    pools = {"old(P1/P2)": [d for d in gen if "ft_p5" not in tf(d)],
             "p5-v1": [d for d in gen if "ft_p5_nb" in tf(d)],
             "p5-v2": [d for d in gen if "ft_p5v2" in tf(d)]}
    return train, {k: v for k, v in pools.items() if v}


def _near_feasible(y):
    """all margins > -1 scale unit (03-SEARCH's 'feasible-or-near-feasible')."""
    return bool((np.asarray(y) > critic.NEAR_FEASIBLE).all())


def _knn_score(train, pool):
    pred = critic.pred_knn(train, pool)
    return critic._feasibility_score(pred), pred


def _gnn_models(train, sigma_norm, n=5):
    """Train the ensemble ONCE so every pool is ranked by the same critic."""
    import critic_gnn as G
    va_ids = {id(d) for d in train[::6]}
    va = [d for d in train if id(d) in va_ids]
    tr = [d for d in train if id(d) not in va_ids]
    return [G.train_one(tr, va, sigma_norm, seed=s) for s in range(n)]


def _gnn_score(models, pool):
    import critic_gnn as G
    P = np.stack([G.predict(m, pool) for m in models])
    mean, std = P.mean(0), P.std(0)
    return critic._feasibility_score(mean) - BETA * std.mean(1), mean


def _report_pool(name, pool, scorers, k_frac):
    Y = np.array([d["y"] for d in pool])
    near = np.array([_near_feasible(y) for y in Y])
    base = near.mean()
    kk = max(3, round(k_frac * len(pool)))
    rng = np.random.default_rng(0)
    for a, fn in scorers.items():
        score, pred = fn(pool)
        top = np.argsort(-score)[:kk]
        top_nf = int(near[top].sum())
        ctrl = float(np.median([near[rng.choice(len(pool), kk, replace=False)].sum()
                                for _ in range(1000)]))
        enrich = (top_nf / kk) / base if base > 0 else float("nan")
        rho = critic.spearman(Y[:, 1], pred[:, 1])
        print(f"{name:<11} {a:<4} {len(pool):>4} {base:>6.2f} {kk:>4} "
              f"{top_nf:>5} {ctrl:>6.1f} {enrich:>7.2f} {rho:>8.3f} "
              f"{'YES' if enrich >= 2.0 else 'no':>4}")


def rerank(spec_name="wifi24", arm="both", k_frac=0.2, snapshot=None):
    data = critic.load_dataset(snapshot=snapshot)
    sigma = critic._sigma_s21()
    train, pools = _split(data, spec_name)
    print(f"rung-1 rerank (offline, spec={spec_name}, snapshot={snapshot}): "
          f"train={len(train)} non-generated, sigma_S21={sigma:.3f}, "
          f"pools={ {k: len(v) for k, v in pools.items()} }")
    arms = ["knn", "gnn"] if arm == "both" else [arm]
    scorers = {}
    if "knn" in arms:
        scorers["knn"] = lambda pool: _knn_score(train, pool)
    if "gnn" in arms:
        try:
            models = _gnn_models(train, sigma / 12.0, n=5)
            scorers["gnn"] = lambda pool, m=models: _gnn_score(m, pool)
        except ImportError:
            print("(gnn skipped; run under the analoggenie python for torch)")
    print(f"\n{'pool':<11} {'arm':<4} {'n':>4} {'base':>6} {'topk':>4} "
          f"{'NF':>5} {'ctrl':>6} {'enrich':>7} {'rho_S21':>8} {'S1?':>4}")
    for name, pool in pools.items():
        if len(pool) >= 8:
            _report_pool(name, pool, scorers, k_frac)
        else:
            print(f"{name:<11} (pool too small: {len(pool)})")
    print("\nThe question: does the P5 (memorization-broken) pool rank better than "
          "old(P1/P2) under the same critic? Gate S1 = enrich@top-20% >= 2x. "
          "Near-feasible = all margins > -1; realized-vs-predicted rho feeds retrain.")
    return 0


# ===================================================================== LIVE rung 1
# 03-SEARCH §1, run for real: fresh pool -> critic rank -> size top-k, against an
# equal-budget random control drawn from the identical pool.

def _gated_cols(spec):
    """Which of the critic's 4 margin heads (S11,S21,Idd,NF) this spec gates."""
    cols = [0, 1, 2]
    c = spec.constraints.get("nf_db") or {}
    if c.get("status") != "unsupported" and c.get("max") is not None:
        cols.append(3)
    return cols


def realized_margins(spec, m):
    """Realized (S11,S21,Idd,NF) normalized margins on the critic's own scale and
    clipping, so predicted and realized are directly comparable (== evolve.py)."""
    mg = ds.margins_for(spec, m)
    v = next((mg[s]["margin"] for s in critic.S11_SLOTS
              if (mg.get(s) or {}).get("supported")
              and mg[s].get("margin") is not None), None)
    out = [v] + [(mg.get(k) or {}).get("margin")
                 for k in ("s21_db", "idd_ma", "nf_db")]
    return [None if x is None else
            min(max(x, critic.MARGIN_CLIP[0]), critic.MARGIN_CLIP[1]) for x in out]


def _feas_scalar(vec):
    """05-SIZING feasibility-first scalar (positive slack, else summed shortfall)."""
    short = sum(min(v, 0.0) for v in vec)
    return short if short < 0 else sum(max(v, 0.0) for v in vec)


def _near_feasible_vec(vec):
    """03-SEARCH's 'feasible-or-near-feasible': every gated margin above -1."""
    return all(v is None or v > critic.NEAR_FEASIBLE for v in vec)


def _write(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1)


# ---------------------------------------------------------------- step 1: pool
def build_pool(pool_dir, spec_name, out):
    """L0 screen -> WL-dedup -> drop anything already sized against THIS spec.

    "Fresh" is per (topology, spec): a graph already labeled against wifi24 is
    still an unsized candidate for dhruva-s, and its L2 key is free. Both facts
    are recorded per candidate so the S1 report can split the verdict by whether
    the critic had ever seen the *structure* under some other spec."""
    import size
    from novelty import ref_tag, reference, wl_features
    from topology import Topology, parse_arrow_file
    spec = size._spec_for_sizing(spec_name)
    ref_hashes, _, ref_meta = reference()
    rows = ds.load("topo_labels")
    sized_here = {r.get("wl_hash") for r in rows if r.get("spec") == spec_name}
    in_store = {r.get("wl_hash") for r in rows}
    seen, cands = set(), []
    n_files = n_screen = n_dup_spec = 0
    for f in sorted(globmod.glob(os.path.join(pool_dir, "seq*.txt"))):
        n_files += 1
        try:
            topo = Topology(parse_arrow_file(f))
        except Exception:
            continue
        if not spec.structural_screen(topo)[0]:
            continue
        n_screen += 1
        h = wl_features(topo)[0]
        if h in seen:
            continue
        seen.add(h)
        if h in sized_here:
            n_dup_spec += 1
            continue
        cands.append({"seq": os.path.basename(f), "file": f.replace("\\", "/"),
                      "wl": h, "tokens": list(topo.tokens),
                      "n_dev": topo.n_devices, "n_ind": topo.n_inductors,
                      "novel_ref2": h not in ref_hashes,
                      "seen_other_spec": h in in_store})
    obj = {"pool_dir": pool_dir.replace("\\", "/"), "spec": spec_name,
           "novelty_ref": ref_tag(ref_meta), "n_files": n_files,
           "l0_passing": n_screen, "wl_distinct": len(seen),
           "dropped_already_sized_vs_spec": n_dup_spec,
           "n_candidates": len(cands),
           "n_novel_ref2": sum(c["novel_ref2"] for c in cands),
           "n_seen_other_spec": sum(c["seen_other_spec"] for c in cands),
           "candidates": cands}
    print(f"pool {pool_dir} vs {spec_name}: {n_files} files -> L0 {n_screen} -> "
          f"WL-distinct {len(seen)} -> fresh-for-spec {len(cands)} "
          f"({obj['n_novel_ref2']} novel vs {obj['novelty_ref']}+store, "
          f"{obj['n_seen_other_spec']} already labeled under another spec)")
    if out:
        _write(out, obj)
        print(f"wrote {out}")
    return 0


# ---------------------------------------------------------------- step 2: rank
def rank_pool(pool_json, snapshot, out, n_models=5, k_holdout=0.25,
              sigma_recipe="candidate-v1+bo3", seed0=0):
    """Critic v2 ranks the pool. Needs torch -> analoggenie python.

    **Leak-free by construction:** every store row whose wl_hash appears in the
    pool is dropped before training, so no candidate's structure carries its own
    label into the model. (Those rows are labeled against *other* specs, so this
    is stricter than necessary; it is also the only version of the number that can
    be quoted without a caveat.)"""
    import critic_gnn as G
    from spec import Spec
    from topology import Topology
    with open(pool_json, encoding="utf-8") as fh:
        pool = json.load(fh)
    spec = Spec.load(pool["spec"])
    cols = _gated_cols(spec)
    pool_hashes = {c["wl"] for c in pool["candidates"]}
    data = critic.load_dataset(snapshot=snapshot)
    kept = [d for d in data if d["row"].get("wl_hash") not in pool_hashes]
    n_dropped = len(data) - len(kept)
    sigma = critic._sigma_s21(recipe=sigma_recipe, snapshot=snapshot)
    sp = ds.family_split(k_holdout=k_holdout, rows=[d["row"] for d in kept])
    id2d = {id(d["row"]): d for d in kept}
    tr = [id2d[id(r)] for r in sp["train"] if id(r) in id2d]
    va = [id2d[id(r)] for r in sp["val"] if id(r) in id2d]
    te = [id2d[id(r)] for r in sp["test"] if id(r) in id2d]
    S = np.array([critic.spec_vector(d["spec"]) for d in tr], np.float32)
    G._SPEC_MU = (S.mean(0), S.std(0) + 1e-6)
    sigma_norm = sigma / 12.0
    t0 = time.time()
    models = [G.train_one(tr, va, sigma_norm, seed=seed0 + s)
              for s in range(n_models)]

    def ens(items):
        P = np.stack([G.predict(m, items) for m in models])
        return P.mean(0), P.std(0)

    hmean, hstd = ens(te)
    Yte = np.array([d["y"] for d in te])
    info = {"snapshot": snapshot, "n_store_rows": len(data),
            "n_dropped_pool_hashes": n_dropped, "n_train": len(tr),
            "n_val": len(va), "n_holdout": len(te), "sigma_s21": sigma,
            "n_models": n_models, "beta": BETA,
            "sigma_gate_p90": float(np.percentile(hstd[:, :3].mean(1), 90)),
            "holdout_rho_s21": critic.spearman(Yte[:, 1], hmean[:, 1]),
            "holdout_rho_s11": critic.spearman(Yte[:, 0], hmean[:, 0]),
            "holdout_rank_acc": critic.pairwise_rank_acc(Yte[:, 1], hmean[:, 1],
                                                         sigma_norm),
            "train_s": round(time.time() - t0, 1)}
    items = [{"topo": Topology(c["tokens"]), "spec": pool["spec"],
              "y": np.zeros(3), "y_nf": None} for c in pool["candidates"]]
    mean, std = ens(items)
    cands = []
    for i, c in enumerate(pool["candidates"]):
        cons = [float(mean[i][j] - BETA * std[i][j]) for j in range(4)]
        cands.append(dict(c, mean=[float(v) for v in mean[i]],
                          std=[float(v) for v in std[i]],
                          score=_feas_scalar([cons[j] for j in cols]),
                          score_mean=_feas_scalar([float(mean[i][j]) for j in cols]),
                          unc=float(std[i][:3].mean())))
    n_gated = sum(1 for c in cands if c["unc"] > info["sigma_gate_p90"])
    info["n_above_unc_gate"] = n_gated
    info["frac_above_unc_gate"] = n_gated / max(1, len(cands))
    print("critic v2 ranker: " + json.dumps(info))
    print(f"uncertainty gate (§4 rule 2): {n_gated}/{len(cands)} pool candidates "
          f"exceed the holdout p90 ensemble sigma {info['sigma_gate_p90']:.4f}")
    obj = dict({k: v for k, v in pool.items() if k != "candidates"},
               critic=info, gated_cols=cols, candidates=cands)
    if out:
        _write(out, obj)
        print(f"wrote {out}")
    return 0


# ---------------------------------------------------------------- step 3: size
def _selection(rk, k, seed):
    """The two arms. Declared before any SPICE runs and recorded in the output."""
    cands = rk["candidates"]
    order = sorted(range(len(cands)), key=lambda i: (-cands[i]["score"],
                                                     cands[i]["wl"]))
    crit = order[:k]
    ctrl = sorted(random.Random(seed).sample(range(len(cands)), k))
    return crit, ctrl


def size_arms(rank_json, k, seed, out, shard=None, limit=None, no_log=False):
    """Size the UNION of the two arms once each, timing every candidate.

    Shared candidates (the critic's top-k and the random draw will overlap) are
    simulated ONCE and credited to both arms: that keeps each arm's budget exactly
    k sizings of the identical protocol, which is what "equal budget" means, and
    avoids double-labeling a (wl_hash, spec) key."""
    import size
    from topology import Topology
    with open(rank_json, encoding="utf-8") as fh:
        rk = json.load(fh)
    spec = size._spec_for_sizing(rk["spec"])
    cands = rk["candidates"]
    crit, ctrl = _selection(rk, k, seed)
    rank_of = {i: r for r, i in enumerate(
        sorted(range(len(cands)), key=lambda i: (-cands[i]["score"], cands[i]["wl"])))}
    arms_of = {i: [a for a, sel in (("critic", set(crit)), ("control", set(ctrl)))
                   if i in sel] for i in set(crit) | set(ctrl)}
    union = sorted(set(crit) | set(ctrl))
    if shard:
        si, sn = (int(x) for x in shard.split("/"))
        union = [u for n, u in enumerate(union) if n % sn == si]
    if limit:
        union = union[:limit]
    print(f"rung-1 LIVE: spec={rk['spec']} pool={len(cands)} k={k} seed={seed}; "
          f"critic|control overlap={len(set(crit) & set(ctrl))}; "
          f"union={len(set(crit) | set(ctrl))} sizings"
          + (f"; shard {shard} -> {len(union)}" if shard else ""))
    results, t_all = [], time.time()
    for n, i in enumerate(union):
        c = cands[i]
        topo = Topology(c["tokens"])
        t0 = time.time()
        rec = {"idx": i, "seq": c["seq"], "wl": c["wl"], "score": c["score"],
               "rank": rank_of[i], "arms": arms_of[i],
               "n_dev": c["n_dev"], "novel_ref2": c["novel_ref2"],
               "seen_other_spec": c["seen_other_spec"]}
        try:
            res = size.size_topology(topo, spec, seed=1, inductor_q=12, log=False,
                                     **SCAN_BUDGET)
        except Exception as e:
            res = None
            rec["error"] = f"{type(e).__name__}: {e}"
        if not res or not res.get("metrics"):
            rec.update(ok=False, secs=round(time.time() - t0, 1))
            results.append(rec)
            print(f"  [{n+1}/{len(union)}] {c['seq']:<12} FAILED "
                  f"{rec.get('error', 'no metrics')}", flush=True)
            _write(out, {"rank_json": rank_json, "k": k, "seed": seed,
                         "shard": shard, "spec": rk["spec"],
                         "results": results})
            continue
        m, params, feas = res["metrics"], res["best_params"], res["feasible"]
        n_ev, how = res.get("n_evals") or 0, "scan"
        pol = size.polish(topo, spec, params, budget=POLISH_BUDGET)
        if pol and pol.get("metrics"):
            n_ev += pol.get("n_evals") or 0
            if _viol(spec, pol["metrics"]) < _viol(spec, m):
                m, params, feas, how = (pol["metrics"], pol["best_params"],
                                        pol["feasible"], "bounded-polish")
        mar = realized_margins(spec, m)
        rec.update(ok=True, how=how, feasible=bool(feas),
                   viol=round(_viol(spec, m), 4), margins=mar,
                   near=_near_feasible_vec([mar[j] for j in rk["gated_cols"]]),
                   fs_real=_feas_scalar([-4.0 if mar[j] is None else mar[j]
                                         for j in rk["gated_cols"]]),
                   metrics=m, n_evals=n_ev, secs=round(time.time() - t0, 1))
        if not no_log:
            prov = {"source_arm": "rung1-live", "experiment": "rung1-s1",
                    "how": how, "novel": bool(c["novel_ref2"]),
                    "novelty_ref": rk.get("novelty_ref"), "wl_hash": c["wl"],
                    "critic_snapshot": rk["critic"]["snapshot"],
                    "critic_score": c["score"], "rung1_seed": seed,
                    "rung1_k": k, "rung1_arms": arms_of[i],
                    "rung1_rank": rank_of[i], "token_file": c["file"]}
            size.log_l2_result(spec, topo, m, feas, params, prov, RECIPE, n_ev,
                               repeat_probe=False)
        results.append(rec)
        print(f"  [{n+1}/{len(union)}] {c['seq']:<12} {how:<15} "
              f"viol={rec['viol']:7.3f} near={rec['near']} feas={rec['feasible']} "
              f"{_fmt(m)} {rec['secs']:.0f}s", flush=True)
        _write(out, {"rank_json": rank_json, "k": k, "seed": seed,
                     "shard": shard, "spec": rk["spec"], "results": results})
    print(f"done: {len(results)} sizings, {(time.time()-t_all)/60:.1f} min wall")
    return 0


def _viol(spec, m):
    feas, viol = spec.feasible(m)
    return sum(viol.values()) if viol else 0.0


def _fmt(m):
    s11 = m.get("s11_max_db")
    s11 = s11 if s11 is not None else m.get("s11_db")
    g = lambda v: "None" if v is None else f"{v:.2f}"          # noqa: E731
    return (f"S11={g(s11)} S21={g(m.get('s21_db'))} "
            f"Idd={g(m.get('idd_ma'))} NF={g(m.get('nf_db'))}")


# ---------------------------------------------------------------- step 4: S1
def s1_report(rank_json, sized_jsons, k, seed):
    with open(rank_json, encoding="utf-8") as fh:
        rk = json.load(fh)
    got = {}
    for p in sized_jsons:
        with open(p, encoding="utf-8") as fh:
            for r in json.load(fh)["results"]:
                got[r["idx"]] = r
    crit, ctrl = _selection(rk, k, seed)
    cands = rk["candidates"]
    n_pool = len(cands)
    print(f"\n=== Gate S1 (03-SEARCH §1) — LIVE rung-1 rerank, spec={rk['spec']} ===")
    print(f"pool {rk['pool_dir']} -> {n_pool} fresh candidates; k={k}; "
          f"control seed={seed}; overlap={len(set(crit) & set(ctrl))}; "
          f"critic snapshot={rk['critic']['snapshot']} "
          f"(holdout rho_S21={rk['critic']['holdout_rho_s21']:.3f})")
    print(f"\n{'arm':<9} {'k':>3} {'sized':>6} {'ok':>4} {'feas':>5} {'near':>5} "
          f"{'base':>6} {'bestviol':>9} {'medviol':>8} {'SPICE-min':>10}")
    stats = {}
    for name, sel in (("critic", crit), ("control", ctrl)):
        rs = [got[i] for i in sel if i in got]
        ok = [r for r in rs if r.get("ok")]
        near = sum(1 for r in ok if r["near"])
        feas = sum(1 for r in ok if r["feasible"])
        viols = sorted(r["viol"] for r in ok)
        secs = sum(r["secs"] for r in rs)
        stats[name] = {"k": len(sel), "sized": len(rs), "ok": len(ok),
                       "feasible": feas, "near": near,
                       "rate": near / len(sel) if sel else float("nan"),
                       "best_viol": viols[0] if viols else None,
                       "med_viol": viols[len(viols) // 2] if viols else None,
                       "spice_min": secs / 60.0}
        s = stats[name]
        print(f"{name:<9} {len(sel):>3} {len(rs):>6} {len(ok):>4} {feas:>5} "
              f"{near:>5} {s['rate']:>6.3f} "
              f"{(s['best_viol'] if s['best_viol'] is not None else float('nan')):>9.3f} "
              f"{(s['med_viol'] if s['med_viol'] is not None else float('nan')):>8.3f} "
              f"{s['spice_min']:>10.1f}")
    base = stats["control"]["rate"]
    prec = stats["critic"]["rate"]
    ratio = prec / base if base > 0 else float("nan")
    # The pool's near-feasible count is unobserved; the control arm is its unbiased
    # estimator, so the attainable ceiling is estimated as min(base*n_pool, k)/k.
    ceil_prec = min(base * n_pool, k) / k if k else float("nan")
    skill = ((prec - base) / (ceil_prec - base)
             if ceil_prec - base > 1e-12 else float("nan"))
    se = (base * (1 - base) / max(1, stats["control"]["k"])) ** 0.5
    print(f"\nnear-feasible rate: critic {prec:.3f} vs control (= base) {base:.3f} "
          f"+- {se:.3f} (binomial SE, n={stats['control']['k']})")
    print(f"S1 as written (>= 2x the control's feasible-or-near-feasible count): "
          f"{stats['critic']['near']} vs {stats['control']['near']} = "
          f"{ratio:.2f}x -> {'MET' if ratio >= 2.0 else 'NOT MET'}")
    print(f"S1 under the restated skill bar (FINDINGS §14.6; base estimated from "
          f"the control arm, ceiling precision {ceil_prec:.3f}): skill = "
          f"{skill:.3f} vs theta {critic.C1_THETA} -> "
          f"{'MET' if (not np.isnan(skill) and skill >= critic.C1_THETA) else 'NOT MET'}")
    # deployment-distribution correlation over every sized candidate (§1's
    # "report alongside", and the number that feeds the next retrain)
    ok = [r for r in got.values() if r.get("ok")]
    if len(ok) >= 3:
        rho = critic.spearman(np.array([r["score"] for r in ok]),
                              np.array([r["fs_real"] for r in ok]))
        print(f"\nrealized-vs-predicted rho (feasibility scalar, n={len(ok)} sized, "
              f"the deployment-distribution test): {rho:+.3f}")
        for tag, sub in (("novel-vs-ref-v2", [r for r in ok if r["novel_ref2"]]),
                         ("seen-under-another-spec",
                          [r for r in ok if r["seen_other_spec"]]),
                         ("structure-never-labeled",
                          [r for r in ok if not r["seen_other_spec"]])):
            if len(sub) >= 5:
                print(f"    {tag:<24} n={len(sub):>3} rho="
                      f"{critic.spearman(np.array([r['score'] for r in sub]), np.array([r['fs_real'] for r in sub])):+.3f}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--arm", choices=["knn", "gnn", "both"], default="both")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--k-frac", type=float, default=0.2)
    ap.add_argument("--snapshot")
    # live rung-1
    ap.add_argument("--pool", metavar="DIR", help="build a live candidate pool")
    ap.add_argument("--rank", action="store_true", help="critic-v2 rank a pool")
    ap.add_argument("--size", action="store_true", help="size both arms")
    ap.add_argument("--s1", action="store_true", help="Gate-S1 scoreboard")
    ap.add_argument("--pool-json")
    ap.add_argument("--rank-json")
    ap.add_argument("--sized-json", nargs="+")
    ap.add_argument("--k", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--shard", help="i/n -- split the union across processes")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--n-models", type=int, default=5)
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.rerank:
        return rerank(args.spec, arm=args.arm, k_frac=args.k_frac,
                      snapshot=args.snapshot)
    if args.pool:
        return build_pool(args.pool, args.spec, args.out)
    if args.rank:
        return rank_pool(args.pool_json, args.snapshot, args.out,
                         n_models=args.n_models)
    if args.size:
        return size_arms(args.rank_json, args.k, args.seed, args.out,
                         shard=args.shard, limit=args.limit, no_log=args.no_log)
    if args.s1:
        return s1_report(args.rank_json, args.sized_json, args.k, args.seed)
    ap.error("give --rerank, --pool, --rank, --size or --s1")


if __name__ == "__main__":
    sys.exit(main())
