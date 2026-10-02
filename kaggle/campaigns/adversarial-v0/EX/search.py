"""EX exploit search (PREREG-ADVERSARIAL-V0 § EX).

Population = every rl-v1.1-passing design with reality checks (the seeds, then every
verifier-passing child). Each generation (fixed RNG `EX-v0:<gen>`) draws GEN_SIZE
children:
  parent   : with prob 0.35 uniform over the population (breadth), else a 3-way
             tournament on exploit score (ties -> population order)
  mutation : bv2.random_script on the PARENT's netlist = 2-4 primitive edits (add
             R/C/L/MOS, delete, rewire, series-insert, stack), then bv2.repair (prune
             dead passives, DC-return completion, coherence) -> proposal.round_trip
  dedupe   : (WL hash, spec) never sized twice (seeds included)
  verifier : rl-v1.1's pre-sizing rejects (spec topology limits, structural
             degeneracy, port-DC pre-filter) are evaluated in-process with the
             verifier's own functions (0 evals, identical to smoke_run's) and logged;
             the rest are sized under rl-v1.1 at seed 1 x 2500 on the parent's spec
             (ex_drv child), and on a verifier PASS the reality checks R-a..R-e run on
             the sized winner.
  score    : exploit_score = [passes rl-v1.1] x max(mag R-a, R-b, R-c)
Generations are synchronous (all children sized before the next draw), so the run is
deterministic given the (deterministic) verifier. Everything is logged to
<state>/results.jsonl (every child, rejected or not) and <state>/gens.jsonl.

usage: search.py <seeds raw dir> <state dir> <n_gens> [--cpu-cap-h H]
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402
import bv2  # noqa: E402
import ex_pool as POOL  # noqa: E402
import proposal as P  # noqa: E402
from topology import Topology  # noqa: E402

GEN_SIZE = 16
P_UNIFORM = 0.35
MAX_TRIES = 600
TMP = os.environ.get("TMPDIR", "/tmp")
COMPACT_DROP = ("checks",)


def load_pop(seeds_dir, state):
    pop, seen = [], set()
    for f in sorted(os.listdir(seeds_dir)):
        if not f.endswith(".json"):
            continue
        r = json.load(open(f"{seeds_dir}/{f}"))
        rt = P.round_trip(X.tokens_to_net(r["tokens"]))
        seen.add((rt["wl_hash"], r["spec"]))
        if r.get("verifier_pass") and r.get("summary") is not None:
            pop.append({"did": r["sid"], "tokens": r["tokens"], "spec": r["spec"],
                        "score": float(r.get("exploit_score") or 0.0), "gen": -1,
                        "root": r["sid"], "parent": None, "fails": _fails(r["summary"])})
    res = f"{state}/results.jsonl"
    if os.path.exists(res):
        for ln in open(res):
            c = json.loads(ln)
            if c.get("wl"):
                seen.add((c["wl"], c["spec"]))
            if c.get("verifier_pass") and c.get("summary") is not None:
                pop.append({"did": c["did"], "tokens": c["tokens"], "spec": c["spec"],
                            "score": float(c.get("exploit_score") or 0.0), "gen": c["gen"],
                            "root": c["root"], "parent": c["parent"],
                            "fails": _fails(c["summary"])})
    return pop, seen


SEL2_FROM_GEN = 4      # selection v2 (deviation D3): class-balanced exploit pressure


def pick_parent(rng, pop, gen=0):
    if gen >= SEL2_FROM_GEN:
        return pick_parent_v2(rng, pop)
    if rng.random() < P_UNIFORM:
        return rng.choice(pop)
    k = [rng.randrange(len(pop)) for _ in range(3)]
    best = max(k, key=lambda i: (pop[i]["score"], -i))
    return pop[best]


def pick_parent_v2(rng, pop):
    """0.30 uniform over the population; 0.35 class-balanced (a failing check
    class drawn uniformly among those with >= 1 material instance, then a member
    uniformly); 0.35 a 3-way score tournament among material exploit designs."""
    r = rng.random()
    expl = [p for p in pop if p["score"] > X.MATERIAL]
    if r < 0.30 or not expl:
        return rng.choice(pop)
    if r < 0.65:
        by = {}
        for p in expl:
            for c in p.get("fails") or []:
                by.setdefault(c, []).append(p)
        if by:
            c = rng.choice(sorted(by))
            return rng.choice(by[c])
    k = [rng.randrange(len(expl)) for _ in range(3)]
    best = max(k, key=lambda i: (expl[i]["score"], -i))
    return expl[best]


def _fails(summary):
    m = (summary or {}).get("mags") or {}
    return sorted(k for k, v in m.items() if v > X.MATERIAL or (k == "Rb" and v > 0))


def pre_reject(tokens, spec):
    topo = Topology(list(tokens))
    chk = X.PREP.topo_limits(spec, topo)
    if not chk["ok"]:
        return "topo_limits:" + ",".join(chk.get("failed") or [])
    sd = X.PREP.structural_degeneracy(topo)
    if sd:
        return "structural:" + ",".join(sorted(sd))
    pre = X.PREP.port_dc_prefilter(topo)
    if not pre["pass"]:
        return "port_dc_prefilter"
    return None


def make_generation(gen, pop, seen, specs, ns="EX-v0"):
    rng = random.Random(f"{ns}:{gen}")
    jobs, rejects, tries = [], [], 0
    while len(jobs) < GEN_SIZE and tries < MAX_TRIES:
        tries += 1
        par = pick_parent(rng, pop, gen)
        base = bv2.parse_net(X.tokens_to_net(par["tokens"]))
        script = bv2.random_script(rng, base)
        rec = {"gen": gen, "parent": par["did"], "root": par["root"], "spec": par["spec"],
               "parent_score": par["score"], "script": script}
        if not script:
            rejects.append(dict(rec, why="sample"))
            continue
        try:
            el, reps = bv2.repair(bv2.apply_script(base, script))
        except bv2.Bad as e:
            rejects.append(dict(rec, why=f"repair:{e}"))
            continue
        rec["repairs"] = reps
        rt = P.round_trip(bv2.net_text(el))
        if not rt["ok"]:
            rejects.append(dict(rec, why="round_trip"))
            continue
        key = (rt["wl_hash"], par["spec"])
        rec.update(wl=rt["wl_hash"], tokens=rt["tokens"], net=bv2.net_text(el))
        if key in seen:
            rejects.append(dict(rec, why="dup"))
            continue
        seen.add(key)
        if par["spec"] not in specs:
            specs[par["spec"]] = X.load_spec(f"{X.REPO}/{par['spec']}")
        why = pre_reject(rt["tokens"], specs[par["spec"]])
        if why:
            rec.update(why=why, verifier_pass=False, sized=False)
            rejects.append(rec)
            continue
        rec["did"] = f"G{gen:03d}-{len(jobs):02d}"
        jobs.append(rec)
    return jobs, rejects, tries


def cpu_used_h(state):
    tot = 0.0
    for f in (f"{TMP}/seed_pool.jsonl", f"{TMP}/seed_pool_aborted1.jsonl", f"{state}/pool.jsonl",
              f"{TMP}/val_pool.jsonl"):
        if os.path.exists(f):
            for ln in open(f):
                tot += json.loads(ln).get("cpu_s", 0.0)
    return tot / 3600.0


def main(seeds_dir, state, n_gens, cpu_cap_h=70.0):
    os.makedirs(state, exist_ok=True)
    jd = f"{TMP}/ex-jobs"
    os.makedirs(jd, exist_ok=True)
    pop, seen = load_pop(seeds_dir, state)
    done_gens = set()
    if os.path.exists(f"{state}/gens.jsonl"):
        done_gens = {json.loads(ln)["gen"] for ln in open(f"{state}/gens.jsonl")}
    specs = {}
    for gen in range(n_gens):
        if gen in done_gens:
            continue
        used = cpu_used_h(state)
        if used >= cpu_cap_h:
            print(f"cpu cap reached: {used:.1f} h", flush=True)
            break
        t0 = time.time()
        jobs, rejects, tries = make_generation(gen, pop, seen, specs)
        pj = []
        for j in jobs:
            jf = f"{jd}/{j['did']}.job.json"
            json.dump(dict(j, seed=1), open(jf, "w"))
            out = f"{jd}/{j['did']}.out.json"
            pj.append((out, [f"{HERE}/envrun.sh", "python", f"{HERE}/ex_drv.py", "child", jf, out]))
        POOL.run(pj, f"{state}/pool.jsonl", quiet=True)
        n_pass = n_mat = 0
        with open(f"{state}/results.jsonl", "a") as fh:
            for r in rejects:
                fh.write(X.jdump(r) + "\n")
            for j, (out, _a) in zip(jobs, pj):
                try:
                    c = json.load(open(out))
                except Exception as e:                           # noqa: BLE001
                    c = dict(j, error=f"no output: {e!r}", verifier_pass=False)
                c = {k: v for k, v in c.items() if k not in COMPACT_DROP}
                c["sized"] = True
                if not c.get("verifier_pass"):
                    c.pop("body", None)
                    c.pop("params", None)
                else:
                    n_pass += 1
                    n_mat += bool((c.get("summary") or {}).get("material"))
                    pop.append({"did": c["did"], "tokens": c["tokens"], "spec": c["spec"],
                                "score": float(c.get("exploit_score") or 0.0), "gen": gen,
                                "root": c["root"], "parent": c["parent"],
                                "fails": _fails(c.get("summary"))})
                fh.write(X.jdump(c) + "\n")
        g = {"gen": gen, "tries": tries, "sized": len(jobs), "rejects": len(rejects),
             "reject_why": {}, "pass": n_pass, "material": n_mat, "pop": len(pop),
             "wall_s": round(time.time() - t0, 1), "cpu_used_h": round(cpu_used_h(state), 2),
             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        for r in rejects:
            w = r["why"].split(":")[0]
            g["reject_why"][w] = g["reject_why"].get(w, 0) + 1
        with open(f"{state}/gens.jsonl", "a") as fh:
            fh.write(json.dumps(g) + "\n")
        print(json.dumps(g), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    cap = 70.0
    if "--cpu-cap-h" in a:
        i = a.index("--cpu-cap-h")
        cap = float(a[i + 1])
        a = a[:i] + a[i + 2:]
    main(a[0], a[1], int(a[2]), cap)
