"""WP-SEARCH **rung 2** — evolutionary search over graph edits (plans2/03-SEARCH §2).

Rung 1 reranks a pool the generator happened to produce. Rung 2 *makes* the pool:
the LM/archetype/store designs seed a population, `moves.py`'s stratum-M edits and
the decomposition crossover produce offspring, critic v1 (the GNN ensemble,
02-CRITIC / FINDINGS §14.2) decides where SPICE minutes go, and the top elites of
every generation get a TRUE sizing run that is appended to the label store — so the
search manufactures its own training data (§2, the Stage-3 bridge).

Everything §4's trust rules demand is mechanical here:

  1. selection consumes `mean - beta*std`, never the raw mean;
  2. **uncertainty gate** — an individual whose ensemble std exceeds the 90th
     percentile of holdout std (calibrated by `evolve_score.py` on a family split
     the ensemble never trained on) cannot displace a trusted elite on its score;
     it is routed to the *exploration stratum*, which owns its own true-eval slot;
  3. **trust region** — an offspring further than the store's own family radius
     (`datastore.FAMILY_SIM`) from every labeled row is likewise untrusted until a
     true eval exists for it;
  4. only SPICE numbers are results. Critic scores never leave this file's logs.

The control (§1's fixed yardstick, feasible designs per equal sizing budget) is
`--arm random`: the identical seeds, move set, validity gates and true-eval recipe,
with selection replaced by uniform random choice. Both arms report SPICE-minutes,
so the comparison is at equal cost, not equal generation count.

    python lna/evolve.py --spec wideband-sdr --arm evolve --pop 48 --gens 20 \
        --elites 2 --explore 1 --out lna/out/_evolve_wb_evolve
    python lna/evolve.py --spec wideband-sdr --arm random --no-critic ...   # control
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import moves as M                                    # noqa: E402
import size                                          # noqa: E402
import bias                                          # noqa: E402
import datastore as ds                               # noqa: E402
import templates as T                                # noqa: E402
from topology import Topology, parse_arrow_file      # noqa: E402
from novelty import wl_features, wl_cosine           # noqa: E402

TORCH_PY = r"C:/Users/Devavrat/radioconda/envs/analoggenie/python.exe"
BETA = 1.0                       # §4 rule 1: mean - beta*std
NOVELTY_W = 0.30                 # §2 novelty bonus weight (WL-distance to store)
TRUST_SIM = ds.FAMILY_SIM        # §4 rule 3: the store's own family radius (0.9)
MARGIN_CLIP = (-4.0, 2.0)


# ------------------------------------------------------------------- utilities
def log(msg, fh=None):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if fh:
        fh.write(line + "\n")
        fh.flush()


def feasibility_score(vec):
    """05-SIZING's feasibility-first scalar over a margin vector: positive slack
    when every margin clears, else the (negative) summed shortfall. Local copy —
    `critic.py` is another agent's file tonight, and this is five lines."""
    short = sum(min(v, 0.0) for v in vec)
    if short < 0:
        return short
    return sum(max(v, 0.0) for v in vec)


def total_viol(spec, m):
    feas, viol = spec.feasible(m)
    return (0 if feas else 1, sum(viol.values()) if viol else 0.0)


def fmt_metrics(m):
    if not m:
        return "(no metrics)"
    g = lambda k, n=1: ("-" if m.get(k) is None else round(m[k], n))   # noqa: E731
    return (f"S11 {g('s11_db')} / S11max {g('s11_max_db')} / S21 {g('s21_db')} / "
            f"rip {g('s21_ripple_db',2)} / Idd {g('idd_ma',2)} / NF {g('nf_db',2)} / "
            f"K {g('k_min',2)}")


# --------------------------------------------------------------- critic client
class CriticClient(object):
    """Persistent `evolve_score.py --serve` subprocess (torch lives in another
    interpreter). One ensemble train at startup, then predictions are free."""

    def __init__(self, snapshot, n_models, logpath):
        self.errfh = open(logpath, "w", encoding="utf-8")
        self.p = subprocess.Popen(
            [TORCH_PY, os.path.join(HERE, "evolve_score.py"), "--serve",
             "--snapshot", snapshot, "--n-models", str(n_models)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.errfh,
            text=True, encoding="utf-8", cwd=os.path.dirname(HERE))
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError("critic worker died at startup; see "
                               + logpath)
        msg = json.loads(line)
        if not msg.get("ok"):
            raise RuntimeError("critic worker: %s" % msg)
        self.info = msg["info"]

    def score(self, items):
        self.p.stdin.write(json.dumps({"cmd": "score", "items": items}) + "\n")
        self.p.stdin.flush()
        msg = json.loads(self.p.stdout.readline())
        if not msg.get("ok"):
            raise RuntimeError("critic worker: %s" % msg.get("error"))
        return msg["mean"], msg["std"]

    def close(self):
        try:
            self.p.stdin.write(json.dumps({"cmd": "stop"}) + "\n")
            self.p.stdin.flush()
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()
        self.errfh.close()


# ------------------------------------------------------------------- seeding
def _screen_ok(spec, topo):
    try:
        return spec.structural_screen(topo)[0]
    except Exception:
        return False


_ARCH_CACHE = os.path.join(HERE, "out", "_evolve_arch_cache.json")


def archetype_seqs():
    """`templates.archetypes()` costs ~50 s (Eulerian emission + screen) and is
    called once per arm per spec. Cache it, keyed on templates.py's stat so an
    edit invalidates it. Own cache file — `novelty.py`'s ref-v2 cache belongs to
    another agent tonight."""
    st = os.stat(os.path.join(HERE, "templates.py"))
    key = f"{int(st.st_mtime)}:{st.st_size}"
    try:
        blob = json.load(open(_ARCH_CACHE, encoding="utf-8"))
        if blob.get("key") == key:
            return blob["rows"]
    except (OSError, ValueError, KeyError):
        pass
    rows = [{"name": a["name"], "seq": list(a["seq"])} for a in T.archetypes()]
    try:
        with open(_ARCH_CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"key": key, "rows": rows}, f)
    except OSError:
        pass
    return rows


def seed_pool(spec, args, fh):
    """Population seeds: templates.py archetypes + the store's rows for this spec
    + the generator pools (03-SEARCH §2 "the LM seeds the population")."""
    seeds, seen = [], set()

    def add(topo, origin):
        try:
            h = wl_features(topo)[0]
        except Exception:
            return
        if h in seen or not _screen_ok(spec, topo):
            return
        nl, _ = T.topo_to_netlist(topo)
        if not nl or not M.sane(nl, args.max_dev, args.min_dev):
            return
        seen.add(h)
        seeds.append({"nl": nl, "tokens": list(topo.tokens), "wl": h,
                      "n_dev": topo.n_devices, "origin": origin, "gen": 0,
                      "moves": []})

    n0 = 0
    for a in archetype_seqs():
        add(Topology(a["seq"]), "archetype:" + a["name"])
    n0 = len(seeds)
    log(f"seeds: {n0} archetypes pass the {spec.name} screen", fh)

    rows = [r for r in ds.load("topo_labels") if r.get("spec") == spec.name]
    rows.sort(key=lambda r: total_viol(spec, r.get("metrics") or {}))
    for r in rows:
        toks = (r.get("graph") or {}).get("tokens")
        if toks:
            try:
                add(Topology(toks), "store:" + str(r.get("wl_hash"))[:8])
            except Exception:
                pass
    log(f"seeds: +{len(seeds) - n0} from {len(rows)} store rows for {spec.name}", fh)

    n1 = len(seeds)
    import glob as _g
    for d in args.pools.split(","):
        d = d.strip()
        if not d:
            continue
        files = sorted(_g.glob(os.path.join(HERE, d, "seq*.txt")))
        for f in files[:args.pool_limit]:
            try:
                add(Topology(parse_arrow_file(f)), "gen:" + os.path.basename(d)
                    + "/" + os.path.basename(f))
            except Exception:
                pass
    log(f"seeds: +{len(seeds) - n1} from generator pools -> {len(seeds)} total", fh)
    return seeds


# --------------------------------------------------------------- gates & eval
def l1_ok(topo):
    """L1 (03-SEARCH §1/§2): bias-insertable, presents a two-port, and its DC
    operating point solves with at least one conducting MOS — checked before any
    critic score is spent on it.

    Deliberately **one** op solve, not `bias.feasibility_sweep`: the sweep is a
    grid over the inserted VBG knobs (up to 16 ngspice runs, ~5 s) and is the L1
    *label*, not the L1 gate. At 96 proposals a generation the sweep costs more
    wall-clock than every true sizing run put together — measured the hard way."""
    try:
        nl, _ins, rep, _sw = bias.insert_bias(topo, sweep=False, inductor_q=12)
    except Exception:
        return False
    if rep.get("skipped"):
        return False
    try:
        deck = nl.emit(mode="opcheck")       # `two_port` is set by emit(), not init
    except Exception:
        return False
    if not nl.two_port:
        return False
    try:
        op = bias.run_op(deck)
    except Exception:
        return False
    if not op:
        return False
    _all_on, per = bias.conducting(op)
    return sum(per.values()) >= 1


def true_eval(topo, spec, args, provenance, recipe, fh):
    """A TRUE evaluation: bias insertion -> ZOAF -> **box-clamped** bounded polish
    (never the pre-2026-08-08 unclamped polish) -> one L2 row in the store.
    Returns (result-dict, seconds). Seconds are the SPICE-minute accounting."""
    t0 = time.time()
    budget = dict(n_candidates=args.zoaf_cand, sgd_iters=args.zoaf_sgd,
                  cgd_iters=args.zoaf_cgd)
    best = None
    for seed in (1, 2):
        try:
            res = size.size_topology(topo, spec, seed=seed, inductor_q=12,
                                     log=False, enrich_nf=True, **budget)
        except Exception as e:
            log(f"    seed {seed}: ERROR {type(e).__name__}: {e}", fh)
            continue
        if not res or not res.get("metrics"):
            continue
        cand = {"metrics": res["metrics"], "params": res["best_params"],
                "feasible": res["feasible"], "how": f"zoaf-s{seed}",
                "n_evals": res["n_evals"]}
        try:
            pol = size.polish(topo, spec, res["best_params"],
                              budget=args.polish_budget, inductor_q=12)
        except Exception:
            pol = None
        if pol and pol.get("metrics") and \
                total_viol(spec, pol["metrics"]) < total_viol(spec, cand["metrics"]):
            cand = {"metrics": pol["metrics"], "params": pol["best_params"],
                    "feasible": pol["feasible"], "how": f"zoaf-s{seed}+bpolish",
                    "n_evals": res["n_evals"] + pol["n_evals"]}
        if best is None or total_viol(spec, cand["metrics"]) < \
                total_viol(spec, best["metrics"]):
            cand["n_evals"] += best["n_evals"] if best else 0
            best = cand
        # second seed only buys something when the first landed close (identical
        # rule in both arms, so the budget comparison stays honest)
        if best["feasible"] or total_viol(spec, best["metrics"])[1] > args.seed2_gate:
            break
    dt = time.time() - t0
    if best is None:
        return None, dt
    if not args.no_log:
        try:
            size.log_l2_result(spec, topo, best["metrics"], best["feasible"],
                               best["params"], provenance, recipe,
                               best["n_evals"], repeat_probe=True)
        except Exception as e:
            log(f"    [log] WARN {type(e).__name__}: {e}", fh)
    return best, dt


# ------------------------------------------------------------------- the loop
def margin_cols(spec):
    """Which of the critic's 4 margin heads this spec actually gates.
    (S11, S21, Idd, NF) — NF is a HARD constraint on wideband-sdr and the dhruva
    band specs since WP-D1, so it enters the fitness, not just the report."""
    cols = [0, 1, 2]
    c = spec.constraints.get("nf_db") or {}
    if c.get("status") != "unsupported" and c.get("max") is not None:
        cols.append(3)
    return cols


def run(args):
    from spec import Spec
    os.makedirs(args.out, exist_ok=True)
    tmproot = M.private_tmp(os.path.join(args.out, "tmp"))
    fh = open(os.path.join(args.out, "run.log"), "a", encoding="utf-8")
    log(f"scratch temp root: {tmproot}", fh)
    spec = size._spec_for_sizing(args.spec)
    gated = [k for k, c in spec.constraints.items()
             if c.get("status") != "unsupported"]
    args.max_dev = spec.topology.get("device_budget", [3, 16])[1]
    args.min_dev = spec.topology.get("device_budget", [3, 16])[0]
    ctx = {"max_dev": args.max_dev, "min_dev": args.min_dev,
           "max_inductors": spec.topology.get("max_inductors", 99)}
    rng = random.Random(args.seed)
    cols = margin_cols(spec)
    log(f"=== rung-2 {args.arm} arm vs {spec.name} | gated {gated} | "
        f"margin cols {cols} | pop {args.pop} gens {args.gens} | seed {args.seed}", fh)

    # novelty reference (frozen before the run writes anything)
    ref = json.load(open(os.path.join(HERE, "out", "_trackb_ref_hashes.json"),
                         encoding="utf-8"))
    arch_hash = {a["wl"]: a["name"] for a in ref["archetypes"]}
    corpus_hash = set(ref["corpus_hashes"])
    store_hash = {r.get("wl_hash") for r in ds.load("topo_labels")}
    log(f"novelty reference frozen: {len(arch_hash)} archetypes, "
        f"{len(corpus_hash)} corpus, {len(store_hash)} store hashes", fh)

    critic_cli = None
    if not args.no_critic:
        critic_cli = CriticClient(args.snapshot, args.n_models,
                                  os.path.join(args.out, "critic_worker.log"))
        log("critic v1 ready: " + json.dumps(critic_cli.info), fh)

    # labeled WL features for the trust region + novelty bonus (one per distinct
    # labeled graph -- the store carries ~1.4 rows per topology)
    labeled, _lab_seen = [], set()
    for r in ds.load("topo_labels"):
        toks = (r.get("graph") or {}).get("tokens")
        h = r.get("wl_hash")
        if not toks or h in _lab_seen:
            continue
        _lab_seen.add(h)
        try:
            labeled.append(wl_features(Topology(toks))[1])
        except Exception:
            pass
    log(f"trust region: {len(labeled)} labeled graphs, family radius {TRUST_SIM}", fh)

    def enrich(ind):
        """critic prediction + trust flags for one individual (batched by caller)."""
        try:
            feat = wl_features(Topology(ind["tokens"]))[1]
            sims = [wl_cosine(feat, g) for g in labeled]
            ind["max_sim"] = max(sims) if sims else 0.0
        except Exception:
            ind["max_sim"] = 1.0
        ind["far"] = ind["max_sim"] < TRUST_SIM

    def score_batch(inds):
        if not inds:
            return
        for ind in inds:
            enrich(ind)
        if critic_cli is None:                    # control arm: no critic at all
            for ind in inds:
                ind.update(pred_mean=None, pred_std=None, unc=0.0,
                           high_unc=False, fit=rng.random())
            return
        mean, std = critic_cli.score(
            [{"tokens": i["tokens"], "spec": spec.name} for i in inds])
        gate = critic_cli.info["sigma_gate_p90"]
        for ind, mu, sd in zip(inds, mean, std):
            mu = [min(max(v, MARGIN_CLIP[0]), MARGIN_CLIP[1]) for v in mu]
            cons = [mu[c] - BETA * sd[c] for c in cols]      # §4 rule 1
            unc = sum(sd[c] for c in cols[:3]) / 3.0
            nov = max(0.0, 1.0 - ind["max_sim"])
            ind.update(pred_mean=mu, pred_std=list(sd), unc=unc,
                       high_unc=unc > gate,
                       fit=feasibility_score(cons) + NOVELTY_W * nov)

    # ---- seed the population
    seeds = seed_pool(spec, args, fh)
    rng.shuffle(seeds)
    keep = []
    for s in seeds:
        if len(keep) >= args.pop * 2:
            break
        if l1_ok(Topology(s["tokens"])):
            keep.append(s)
    log(f"L1 gate: {len(keep)}/{min(len(seeds), args.pop*2)} seeds bias-insert "
        f"and present a two-port", fh)
    score_batch(keep)
    keep.sort(key=lambda i: -i["fit"])
    pop = keep[:args.pop]
    evaluated, seen_wl = {}, {i["wl"] for i in keep}
    log(f"population {len(pop)} (from {len(keep)} L1-passing seeds)", fh)

    stats, elites_log = [], []
    spice_s, n_true = 0.0, 0
    t_start = time.time()

    for gen in range(1, args.gens + 1):
        # ---------- offspring
        children, tries = [], 0
        t_gen = time.time()
        while (len(children) < args.children and tries < args.children * 6
               and time.time() - t_gen < args.gen_budget_s):
            tries += 1
            if tries % 40 == 0:
                M.sweep_tmp(tmproot)
            nl, mv, par = None, None, None
            if len(pop) >= 2 and rng.random() < args.p_cross:
                a, b = rng.sample(pop, 2)
                nl = M.crossover(a["nl"], b["nl"], rng, ctx)
                mv, par = "crossover", [a["wl"], b["wl"]]
            if not nl:                       # no cut, or the splice was invalid
                p = (max(rng.sample(pop, min(3, len(pop))), key=lambda i: i["fit"])
                     if args.arm == "evolve" else rng.choice(pop))
                nl, mv = M.mutate(p["nl"], rng, ctx)
                par = [p["wl"]]
            if not nl:
                continue
            r = M.realize(nl, spec)
            if not r:
                continue
            topo, seq, h, canon = r
            if h in seen_wl:
                continue
            if not l1_ok(topo):
                seen_wl.add(h)
                continue
            seen_wl.add(h)
            children.append({"nl": canon, "tokens": list(seq), "wl": h,
                             "n_dev": topo.n_devices, "origin": mv, "gen": gen,
                             "parents": par})
        t_off = time.time() - t_gen
        M.sweep_tmp(tmproot)
        score_batch(children)

        # ---------- selection (mu + lambda) under the trust rules
        pool = pop + children
        for i in pool:
            i["trusted"] = (i["wl"] in evaluated) or (
                not i.get("high_unc") and not i.get("far"))
        if args.arm == "evolve":
            trusted = sorted([i for i in pool if i["trusted"]],
                             key=lambda i: -i["fit"])
            explore = sorted([i for i in pool if not i["trusted"]],
                             key=lambda i: -i["fit"])
            n_ex = min(len(explore), int(round(args.explore_frac * args.pop)))
            pop = trusted[:args.pop - n_ex] + explore[:n_ex]
        else:
            rng.shuffle(pool)
            pop = pool[:args.pop]

        # ---------- true evaluations (§2 ground truth in the loop)
        todo = []
        if args.arm == "evolve":
            cand_t = [i for i in pop if i["trusted"] and i["wl"] not in evaluated]
            cand_e = [i for i in pop if not i["trusted"] and i["wl"] not in evaluated]
            todo = sorted(cand_t, key=lambda i: -i["fit"])[:args.elites]
            todo += sorted(cand_e, key=lambda i: -i["fit"])[:args.explore]
        else:
            free = [i for i in pop if i["wl"] not in evaluated]
            rng.shuffle(free)
            todo = free[:args.elites + args.explore]

        for ind in todo:
            if n_true >= args.true_evals:
                break
            topo = Topology(ind["tokens"])
            prov = {"source_arm": f"evolve-{args.arm}", "wl_hash": ind["wl"],
                    "gen": gen, "move": ind.get("origin"),
                    "parents": ind.get("parents"),
                    "critic": ("v1-gnn@" + args.snapshot) if critic_cli else None,
                    "pred_fit": ind.get("fit"), "pred_unc": ind.get("unc"),
                    "trusted": ind.get("trusted"), "max_sim_labeled": ind["max_sim"],
                    "evolve_seed": args.seed, "nf_gated": True}
            res, dt = true_eval(topo, spec, args, prov, args.recipe, fh)
            spice_s += dt
            n_true += 1
            if not res:
                log(f"  g{gen} {ind['wl'][:8]} [{ind.get('origin')}] "
                    f"-> no metrics ({dt:.0f}s)", fh)
                ind["true"] = None
                evaluated[ind["wl"]] = None
                continue
            m = res["metrics"]
            tv = total_viol(spec, m)
            novel = (ind["wl"] not in arch_hash and ind["wl"] not in corpus_hash
                     and ind["wl"] not in store_hash)
            rec = {"wl": ind["wl"], "gen": gen, "arm": args.arm,
                   "origin": ind.get("origin"), "n_dev": ind["n_dev"],
                   "feasible": bool(res["feasible"]), "viol": tv[1],
                   "metrics": m, "how": res["how"], "novel": novel,
                   "trusted": ind.get("trusted"), "fit": ind.get("fit"),
                   "pred_mean": ind.get("pred_mean"), "unc": ind.get("unc"),
                   "max_sim": ind["max_sim"], "sec": round(dt, 1)}
            elites_log.append(rec)
            evaluated[ind["wl"]] = rec
            ind["true"] = rec
            kmin = m.get("k_min")
            flag = "  <== FEASIBLE" if res["feasible"] else ""
            kflag = "  [K<1 UNSTABLE]" if (kmin is not None and kmin < 1) else ""
            log(f"  g{gen} {ind['wl'][:8]} [{ind.get('origin')}] viol={tv[1]:.3f} "
                f"novel={novel} {fmt_metrics(m)} ({dt:.0f}s){flag}{kflag}", fh)

        M.sweep_tmp(tmproot)
        fits = [i["fit"] for i in pop]
        st = {"gen": gen, "n_children": len(children), "pop": len(pop),
              "offspring_s": round(t_off, 1), "tries": tries,
              "fit_max": max(fits), "fit_mean": sum(fits) / len(fits),
              "n_trusted": sum(1 for i in pop if i["trusted"]),
              "n_high_unc": sum(1 for i in pop if i.get("high_unc")),
              "n_far": sum(1 for i in pop if i.get("far")),
              "n_dev_mean": sum(i["n_dev"] for i in pop) / len(pop),
              "distinct_wl": len(seen_wl), "n_true": n_true,
              "spice_min": round(spice_s / 60.0, 1),
              "best_viol": min([e["viol"] for e in elites_log], default=None),
              "n_feasible": sum(1 for e in elites_log if e["feasible"]),
              "elapsed_min": round((time.time() - t_start) / 60.0, 1)}
        stats.append(st)
        log(f"gen {gen:>2}: children {len(children)}/{tries} in {t_off:.0f}s "
            f"fit max {st['fit_max']:.3f} "
            f"mean {st['fit_mean']:.3f} | trusted {st['n_trusted']} "
            f"highunc {st['n_high_unc']} far {st['n_far']} | true {n_true} "
            f"({st['spice_min']:.1f} SPICE-min) best viol {st['best_viol']} "
            f"feasible {st['n_feasible']}", fh)
        _checkpoint(args, spec, critic_cli, stats, elites_log, pop, spice_s, n_true)
        if n_true >= args.true_evals:
            log(f"true-eval budget {args.true_evals} spent -- stopping at gen {gen}",
                fh)
            break

    _checkpoint(args, spec, critic_cli, stats, elites_log, pop, spice_s, n_true)
    if critic_cli:
        critic_cli.close()
    feas = [e for e in elites_log if e["feasible"]]
    log(f"=== {args.arm} done: {n_true} true evals, {spice_s/60:.1f} SPICE-min, "
        f"{len(feas)} feasible ({sum(1 for e in feas if e['novel'])} novel)", fh)
    fh.close()
    return 0


def _checkpoint(args, spec, cli, stats, elites, pop, spice_s, n_true):
    out = {"arm": args.arm, "spec": spec.name, "seed": args.seed,
           "snapshot": args.snapshot, "recipe": args.recipe,
           "critic": cli.info if cli else None,
           "config": {k: v for k, v in vars(args).items() if k != "func"},
           "generations": stats, "true_evals": elites,
           "spice_min": round(spice_s / 60.0, 2), "n_true": n_true,
           "population": [{"wl": i["wl"], "origin": i.get("origin"),
                           "gen": i.get("gen"), "n_dev": i["n_dev"],
                           "fit": i.get("fit"), "unc": i.get("unc"),
                           "max_sim": i.get("max_sim"),
                           "trusted": i.get("trusted"),
                           "tokens": i["tokens"]} for i in pop]}
    with open(os.path.join(args.out, "state.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(out, f, indent=1)


# ------------------------------------------------------------------- reporting
S11_SLOTS = ("s11_max_db", "s11_db")


def realized_margins(spec, m):
    """The realized 4-vector on the critic's own scale: (S11, S21, Idd, NF)
    normalized margins, clipped exactly as `critic._margins` clips its labels, so
    predicted and realized are directly comparable."""
    mg = ds.margins_for(spec, m)
    out = []
    v = next((mg[s]["margin"] for s in S11_SLOTS
              if (mg.get(s) or {}).get("supported")
              and mg[s].get("margin") is not None), None)
    out.append(v)
    for k in ("s21_db", "idd_ma", "nf_db"):
        out.append((mg.get(k) or {}).get("margin"))
    return [None if v is None else min(max(v, MARGIN_CLIP[0]), MARGIN_CLIP[1])
            for v in out]


def _rank(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 3:
        return float("nan")
    ra, rb = _rank([p[0] for p in pairs]), _rank([p[1] for p in pairs])
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return num / (da * db) if da and db else float("nan")


def report(paths):
    """Two-arm scoreboard + the S2 verdict, computed only from SPICE numbers."""
    from spec import Spec
    states = [json.load(open(p, encoding="utf-8")) for p in paths]
    spec = Spec.load(states[0]["spec"])
    cols = margin_cols(spec)
    print(f"# rung-2 scoreboard — {spec.name}\n")
    print(f"{'arm':<10} {'true':>5} {'SPICEmin':>9} {'feas':>5} {'novel':>6} "
          f"{'near':>5} {'best viol':>10} {'min/feas':>9} {'K<1':>4}")
    summ = {}
    for st in states:
        te = st["true_evals"]
        feas = [e for e in te if e["feasible"]]
        nov = [e for e in feas if e["novel"]]
        near = [e for e in te if all(
            (v is None or v > -1.0) for v in realized_margins(spec, e["metrics"]))]
        kbad = [e for e in te if (e["metrics"].get("k_min") or 9e9) < 1]
        best = min((e["viol"] for e in te), default=float("nan"))
        mpf = (st["spice_min"] / len(nov)) if nov else float("inf")
        print(f"{st['arm']:<10} {len(te):>5} {st['spice_min']:>9.1f} "
              f"{len(feas):>5} {len(nov):>6} {len(near):>5} {best:>10.3f} "
              f"{mpf:>9.1f} {len(kbad):>4}")
        summ[st["arm"]] = dict(n=len(te), spice=st["spice_min"], feas=len(feas),
                               novel=len(nov), near=len(near), best=best)
    # ---- equal-budget truncation (03-SEARCH's yardstick is per SPICE-minute, and
    # the two arms do not end on the same count: a generation spends fewer true
    # evals when the exploration stratum is empty). Truncate BOTH to the smaller
    # arm's cumulative SPICE-minutes so the comparison is at identical cost.
    if len(states) == 2:
        budget = min(sum(e["sec"] for e in st["true_evals"]) for st in states)
        print(f"\nat an equal budget of {budget/60:.1f} SPICE-min (both arms "
              f"truncated to the smaller arm's spend):")
        print(f"{'arm':<10} {'true':>5} {'feas':>5} {'novel':>6} {'near':>5} "
              f"{'best viol':>10}")
        for st in states:
            acc, keep = 0.0, []
            for e in st["true_evals"]:
                if acc + e["sec"] > budget:
                    break
                acc += e["sec"]
                keep.append(e)
            nov = [e for e in keep if e["feasible"] and e["novel"]]
            near = [e for e in keep if all(
                (v is None or v > -1.0)
                for v in realized_margins(spec, e["metrics"]))]
            print(f"{st['arm']:<10} {len(keep):>5} "
                  f"{sum(1 for e in keep if e['feasible']):>5} {len(nov):>6} "
                  f"{len(near):>5} "
                  f"{min((e['viol'] for e in keep), default=float('nan')):>10.3f}")
    if "evolve" in summ and "random" in summ:
        e, r = summ["evolve"], summ["random"]
        print(f"\nGate S2 (03-SEARCH §2): evolutionary feasible-novel >= 2x the "
              f"control at equal true-eval budget")
        print(f"  evolve {e['novel']} novel-feasible in {e['spice']:.1f} SPICE-min "
              f"({e['n']} true evals) vs control {r['novel']} in "
              f"{r['spice']:.1f} SPICE-min ({r['n']} true evals)")
        if r["novel"] == 0:
            v = "MET" if e["novel"] > 0 else "NOT MET (both arms 0)"
        else:
            v = "MET" if e["novel"] >= 2 * r["novel"] else "NOT MET"
        print(f"  verdict: {v}")
        print(f"  near-feasible (all margins > -1 scale unit): evolve {e['near']} "
              f"vs control {r['near']} "
              f"(ratio {e['near']/r['near'] if r['near'] else float('inf'):.2f}x)")
        print(f"  best total violation: evolve {e['best']:.3f} vs control "
              f"{r['best']:.3f}")
    for st in states:
        te = [e for e in st["true_evals"] if e.get("pred_mean")]
        if len(te) < 3:
            continue
        real = [realized_margins(spec, e["metrics"]) for e in te]
        print(f"\ncritic-vs-SPICE on {st['arm']} elites (n={len(te)}, "
              f"critic v1 @ {st['snapshot']}):")
        for k, nm in enumerate(("S11", "S21", "Idd", "NF")):
            rho = spearman([e["pred_mean"][k] for e in te], [r[k] for r in real])
            print(f"  rho({nm:<3} margin) = {rho:+.3f}")
        fs_pred = [feasibility_score([e["pred_mean"][c] for c in cols]) for e in te]
        fs_real = [feasibility_score([r[c] if r[c] is not None else -4.0
                                      for c in cols]) for r in real]
        print(f"  rho(feasibility scalar) = "
              f"{spearman(fs_pred, fs_real):+.3f}")
        print(f"  rho(selection fitness)  = "
              f"{spearman([e['fit'] for e in te], fs_real):+.3f}")
        unc = [e.get("unc") for e in te]
        err = [abs(p - q) for p, q in zip(fs_pred, fs_real)]
        print(f"  rho(ensemble std, |error|) = {spearman(unc, err):+.3f}"
              f"   <- the uncertainty gate's premise")
    # ---- where the front actually stalls
    from collections import Counter
    print("\nbinding constraints over every true eval (what the topology "
          "search is up against):")
    for st in states:
        cnt, worst = Counter(), {}
        for e in st["true_evals"]:
            _f, v = spec.feasible(e["metrics"])
            for k, x in (v or {}).items():
                cnt[k] += 1
                worst[k] = min(worst.get(k, 9e9), x)
        n = len(st["true_evals"])
        print(f"  {st['arm']:<8} n={n}: " + ", ".join(
            f"{k} {c}/{n} (best gap {worst[k]:.3f})"
            for k, c in cnt.most_common()))
    print("\nmove attribution — which edits produced the 10 lowest-violation "
          "designs:")
    allrows = sorted(((e["viol"], st["arm"], e) for st in states
                      for e in st["true_evals"]), key=lambda t: t[0])[:10]
    print("  " + ", ".join(f"{m}x{c}" for m, c in
                           Counter(e.get("origin") for _v, _a, e in allrows)
                           .most_common()))
    print("\nbest designs by realized total violation (SPICE, not critic):")
    rows = [(e["viol"], st["arm"], e) for st in states for e in st["true_evals"]]
    rows.sort(key=lambda t: t[0])
    for v, arm, e in rows[:10]:
        m = e["metrics"]
        print(f"  {arm:<7} g{e['gen']:<2} {e['wl'][:12]} viol={v:7.3f} "
              f"novel={str(e['novel']):<5} dev={e['n_dev']:<3} "
              f"[{str(e.get('origin'))[:16]:<16}] {fmt_metrics(m)}")
    return 0


def calibrate(paths, snapshot, n_models, out):
    """Unbiased critic-vs-SPICE calibration on the CONTROL arm's true evals.

    The evolve arm's realized correlation is measured on the elites the critic
    itself picked, so it is range-restricted by construction. The control arm's
    true evals were drawn at random from the same mutant distribution and the
    critic never saw them, so scoring them *after the fact* gives the honest
    deployment-distribution number. Topologies come back from the store (the
    state file keeps hashes, the store keeps tokens)."""
    from spec import Spec
    states = [json.load(open(p, encoding="utf-8")) for p in paths]
    rows = list(ds.load("topo_labels"))
    cli = CriticClient(snapshot, n_models, out + ".worker.log")
    print("critic v1: " + json.dumps(cli.info))
    for st in states:
        spec = Spec.load(st["spec"])
        cols = margin_cols(spec)
        want = {e["wl"]: e for e in st["true_evals"]}
        arm_tag = "evolve-" + st["arm"]
        items, keep = [], []
        seen = set()
        for r in rows:
            p = r.get("provenance") or {}
            h = r.get("wl_hash")
            if (p.get("source_arm") != arm_tag or r.get("spec") != st["spec"]
                    or h not in want or h in seen):
                continue
            toks = (r.get("graph") or {}).get("tokens")
            if not toks or not r.get("metrics"):
                continue
            seen.add(h)
            items.append({"tokens": toks, "spec": st["spec"]})
            keep.append(r)
        if len(keep) < 5:
            print(f"{st['arm']}: only {len(keep)} recoverable rows, skipping")
            continue
        mean, std = cli.score(items)
        real = [realized_margins(spec, r["metrics"]) for r in keep]
        print(f"\n{st['arm']} arm, n={len(keep)} (critic scored POST HOC, never "
              f"used for selection):" if st["arm"] == "random" else
              f"\n{st['arm']} arm, n={len(keep)} (selection-biased):")
        for k, nm in enumerate(("S11", "S21", "Idd", "NF")):
            print(f"  rho({nm:<3} margin) = "
                  f"{spearman([m[k] for m in mean], [r[k] for r in real]):+.3f}")
        fp = [feasibility_score([m[c] for c in cols]) for m in mean]
        fr = [feasibility_score([r[c] if r[c] is not None else -4.0 for c in cols])
              for r in real]
        print(f"  rho(feasibility scalar) = {spearman(fp, fr):+.3f}")
        cons = [feasibility_score([mean[i][c] - BETA * std[i][c] for c in cols])
                for i in range(len(mean))]
        print(f"  rho(mean - beta*std)    = {spearman(cons, fr):+.3f}")
        err = [abs(a - b) for a, b in zip(fp, fr)]
        unc = [sum(std[i][c] for c in cols[:3]) / 3.0 for i in range(len(std))]
        print(f"  rho(ensemble std, |error|) = {spearman(unc, err):+.3f}")
        # near-feasible uses the SAME definition as `report()` and critic.py:
        # every individual margin above -1 scale unit (not the summed scalar).
        near = [all((v is None or v > -1.0) for v in m) for m in real]
        top = sorted(range(len(fp)), key=lambda i: -fp[i])[:max(1, len(fp) // 5)]
        base = sum(near) / len(near)
        prec = sum(1 for i in top if near[i]) / len(top)
        print(f"  precision@top-20% = {prec:.3f} vs base rate {base:.3f} "
              f"-> enrichment {prec/base if base else float('nan'):.2f}x "
              f"(ceiling {1/base if base else float('inf'):.2f}x)")
    cli.close()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibrate", nargs="+", metavar="STATE_JSON",
                    help="post-hoc critic-vs-SPICE calibration on stored rows")
    ap.add_argument("--report", nargs="+", metavar="STATE_JSON",
                    help="two-arm scoreboard + S2 verdict from state.json files")
    ap.add_argument("--spec", default="wideband-sdr")
    ap.add_argument("--arm", choices=["evolve", "random"], default="evolve")
    ap.add_argument("--pop", type=int, default=48)
    ap.add_argument("--children", type=int, default=48)
    ap.add_argument("--gens", type=int, default=20)
    ap.add_argument("--elites", type=int, default=2,
                    help="trusted elites given a TRUE eval per generation")
    ap.add_argument("--explore", type=int, default=1,
                    help="exploration-stratum true evals per generation (§4 r2)")
    ap.add_argument("--explore-frac", type=float, default=0.25)
    ap.add_argument("--true-evals", type=int, default=60)
    ap.add_argument("--p-cross", type=float, default=0.25)
    ap.add_argument("--gen-budget-s", type=float, default=150,
                    help="wall-clock cap on offspring generation per generation")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--snapshot", default="v4-train")
    ap.add_argument("--n-models", type=int, default=5)
    ap.add_argument("--no-critic", action="store_true",
                    help="control arm: no critic process at all")
    ap.add_argument("--pools", default="out/ft_p5v2_wb_s1337,out/ft_p5v2_nb_s1337")
    ap.add_argument("--pool-limit", type=int, default=256)
    ap.add_argument("--zoaf-cand", type=int, default=8)
    ap.add_argument("--zoaf-sgd", type=int, default=8)
    ap.add_argument("--zoaf-cgd", type=int, default=2)
    ap.add_argument("--polish-budget", type=int, default=80)
    ap.add_argument("--seed2-gate", type=float, default=1.2,
                    help="run a 2nd ZOAF seed only when total violation is below "
                         "this (same rule in both arms)")
    ap.add_argument("--recipe", default="evolve-v1")
    ap.add_argument("--out", default="lna/out/_evolve")
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()
    if args.calibrate:
        return calibrate(args.calibrate, args.snapshot, args.n_models, args.out)
    if args.report:
        return report(args.report)
    if args.arm == "random":
        args.no_critic = True
        if args.recipe == "evolve-v1":
            args.recipe = "evolve-ctrl-v1"
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
