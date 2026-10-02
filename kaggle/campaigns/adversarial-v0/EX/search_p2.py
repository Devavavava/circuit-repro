"""EX search phase 2 (deviation D6, declared before running; README § Deviations).

After 60 generations the R-a class (harness Cp1 reliance) dominated the exploit
pressure and the only linear R-b oscillator family descended from ONE seed (S014).
Phase 2 asks whether R-b exploits arise from OTHER roots, so it changes only the
parent choice; mutation, repair, pre-sizing rejects, sizing (rl-v1.1, seed 1 x 2500),
dedupe, checks and logging are search.py's, in the same state dir (gens continue at
60, RNG namespace `EX-v0-p2:<gen>`).

  eligible parents : verifier-passing population (seeds + children; extended-record
                     rows stay out, as in phase 1) whose ROOT has no linear R-b
                     instance yet (roots gain that status as phase 2 finds them, so
                     each new family is only expanded until it is found)
  parent           : 0.30 uniform over the eligible set; 0.70 a 3-way tournament on
                     R-b proximity  prox = (# of the 25 R-b terminations whose 80 ns
                     verdict is ringing / marginal / dc_shift / oscillates) / 25
                     (a slow-decay / near-jw-pole proxy; full check rows from the
                     raw outputs)
  stop             : n_gens, or total EX CPU (all pools + 1.5 h unlogged diagnostics)
                     >= --cpu-cap-h
usage: search_p2.py <seeds raw dir> <state dir> <last_gen_exclusive> [--cpu-cap-h H]
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import search as S  # noqa: E402
import ex_lib as X  # noqa: E402
import ex_pool as POOL  # noqa: E402

TMP = S.TMP
FIRST_GEN = 60
NEAR = ("ringing", "marginal", "dc_shift", "oscillates")
UNLOGGED_H = 1.5


def total_cpu_h():
    tot = 0.0
    for f in ("seed_pool.jsonl", "seed_pool_aborted1.jsonl", "state/pool.jsonl", "val_pool.jsonl",
              "ext_pool.jsonl", "impact_pool.jsonl"):
        p = f"{TMP}/{f}"
        if os.path.exists(p):
            for ln in open(p):
                try:
                    tot += json.loads(ln).get("cpu_s", 0.0)
                except ValueError:
                    pass
    return tot / 3600.0 + UNLOGGED_H


def prox_of(rec):
    rows = (((rec.get("checks") or {}).get("Rb") or {}).get("rows")) or {}
    if not rows:
        return 0.0
    return sum(v.get("short") in NEAR for v in rows.values()) / len(rows)


def is_rb(rec):
    return bool(((rec.get("summary") or {}).get("Rb") or {}).get("linear_osc"))


def raw_index(seeds_dir):
    """did -> (prox, rb linear) from the full raw outputs (seeds + children)."""
    idx = {}
    for f in sorted(glob.glob(f"{seeds_dir}/S*.json")) + sorted(glob.glob(f"{TMP}/ex-jobs/G*.out.json")):
        try:
            r = json.load(open(f))
        except Exception:                                        # noqa: BLE001
            continue
        if not r.get("verifier_pass"):
            continue
        idx[r.get("sid") or r.get("did")] = (prox_of(r), is_rb(r))
    return idx


def main(seeds_dir, state, last_gen, cap_h):
    pop, seen = S.load_pop(seeds_dir, state)
    idx = raw_index(seeds_dir)
    rb_roots = set()
    for p in pop:
        pr, rb = idx.get(p["did"], (0.0, False))
        p["prox"] = pr
        if rb:
            rb_roots.add(p["root"])
    done = {json.loads(ln)["gen"] for ln in open(f"{state}/gens.jsonl")}
    specs = {}

    def pick(rng, popl, gen=0):
        el = [p for p in popl if p["root"] not in rb_roots]
        if rng.random() < 0.30:
            return rng.choice(el)
        k = [rng.randrange(len(el)) for _ in range(3)]
        return el[max(k, key=lambda i: (el[i]["prox"], -i))]

    S.pick_parent = pick
    jd = f"{TMP}/ex-jobs"
    print(json.dumps({"phase2_start": time.strftime("%Y-%m-%dT%H:%M:%S"), "pop": len(pop),
                      "rb_roots": sorted(rb_roots), "cpu_h": round(total_cpu_h(), 2)}), flush=True)
    for gen in range(FIRST_GEN, last_gen):
        if gen in done:
            continue
        used = total_cpu_h()
        if used >= cap_h:
            print(f"cpu cap reached: {used:.1f} h", flush=True)
            break
        t0 = time.time()
        jobs, rejects, tries = S.make_generation(gen, pop, seen, specs, ns="EX-v0-p2")
        pj = []
        for j in jobs:
            jf = f"{jd}/{j['did']}.job.json"
            json.dump(dict(j, seed=1, phase=2), open(jf, "w"))
            out = f"{jd}/{j['did']}.out.json"
            pj.append((out, [f"{HERE}/envrun.sh", "python", f"{HERE}/ex_drv.py", "child", jf, out]))
        POOL.run(pj, f"{state}/pool.jsonl", quiet=True)
        n_pass = n_mat = n_rb = 0
        with open(f"{state}/results.jsonl", "a") as fh:
            for r in rejects:
                fh.write(X.jdump(dict(r, phase=2)) + "\n")
            for j, (out, _a) in zip(jobs, pj):
                try:
                    full = json.load(open(out))
                except Exception as e:                           # noqa: BLE001
                    full = dict(j, error=f"no output: {e!r}", verifier_pass=False)
                c = {k: v for k, v in full.items() if k not in S.COMPACT_DROP}
                c["sized"] = True
                c["phase"] = 2
                if not c.get("verifier_pass"):
                    c.pop("body", None)
                    c.pop("params", None)
                else:
                    n_pass += 1
                    n_mat += bool((c.get("summary") or {}).get("material"))
                    rb = is_rb(c)
                    n_rb += rb
                    if rb:
                        rb_roots.add(c["root"])
                    pop.append({"did": c["did"], "tokens": c["tokens"], "spec": c["spec"],
                                "score": float(c.get("exploit_score") or 0.0), "gen": gen,
                                "root": c["root"], "parent": c["parent"],
                                "fails": S._fails(c.get("summary")), "prox": prox_of(full)})
                fh.write(X.jdump(c) + "\n")
        g = {"gen": gen, "phase": 2, "tries": tries, "sized": len(jobs), "rejects": len(rejects),
             "reject_why": {}, "pass": n_pass, "material": n_mat, "rb_linear": n_rb,
             "rb_roots": sorted(rb_roots), "pop": len(pop), "wall_s": round(time.time() - t0, 1),
             "cpu_total_h": round(total_cpu_h(), 2), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
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
