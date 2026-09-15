"""bench-v1 STAGE 4 -- the null-filter campaign driver (box, sharded).

Runs the frozen inclusion nulls: for EVERY candidate cell (kaggle/bench-specs/
manifest.json, 200 cells) x EVERY anchor family of its class (kaggle/
bench-anchors/MANIFEST.json, 12 families -> 675 pairs), a matched-budget
sizing-only null of 3600 evals = seeds (1,2,3) x 1200, NO escalation.
Survivors = cells where NO (anchor, seed) run reaches feasibility.

INTERPRETATION NOTE (recorded loudly, pre-run): the validated 13-cell rule
reads "null on the cell's best known-good anchor FAILS it". The best anchor
for a NEW cell is unknowable a priori, and stage-6 library packaging needs
per-anchor worst-margins anyway -- so stage 4 runs the FULL cell x anchor
matrix at full per-pair budget (the strict generalization: the best anchor is
included by construction). Stage-4 campaign wording "every candidate x its
class anchors" agrees. Cost consequence accepted in the campaign doc
(~1-1.5 days at x6 parallel, PA-dominated).

ENGINE: bench_anchor_prep.smoke_run VERBATIM (solve_spec._spec_for_sizing ->
prepared_body -> make_objective -> _Budget -> run_cmaes -> UNGATED endpoint
re-eval). Feasibility per seed = Spec.feasible over the winner's ungated
endpoint metrics; per-seed normalized violations recorded for stage-6
margins. pdk=gf180mcu run-time override (specs default bptm45), same as the
24-cell ladder.

KILL-ROBUST + SHARDED: one JSON per pair under kaggle/bench-null/<class>/;
a pair with all 3 seeds on disk is skipped on re-run. `--shard K/N` takes
every pair whose position (in the cost-sorted deterministic order: pa first,
then mixer, balun, lna; manifest order within class) satisfies idx % N == K,
so N legs are cost-balanced. `--collect` assembles INDEX.json + the survivor
table (no sims). `--validate` runs ONE lna pair at 40 evals x 1 seed into
bench-null/validate-scratch/ (never collected) to prove the driver end-to-end.

Era: git HEAD at launch recorded in every result (single era for the whole
campaign per the frozen design; a dirty tree is recorded loudly, not hidden).
Zero store writes; lna/ READ-ONLY (novelty is never touched here). A pair
whose anchor is not sizable for a spec is RECORDED as such, never skipped
silently.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "lna"))
sys.path.insert(0, str(REPO / "kaggle" / "loop"))

import bench_anchor_prep as PREP                   # noqa: E402  (engine host)
from spec import Spec                              # noqa: E402

PDK = "gf180mcu"
SEEDS = (1, 2, 3)
EVALS_PER_SEED = 1200
OUT = REPO / "kaggle" / "bench-null"
SPECMAN = REPO / "kaggle" / "bench-specs" / "manifest.json"
ANCHMAN = REPO / "kaggle" / "bench-anchors" / "MANIFEST.json"

# spec-manifest circuit_class -> anchor-manifest class key
CLASS_MAP = {"lna": "lna", "pa": "pa", "mixer": "mixer", "balun-lna": "balun"}
# per-pair cost rank for shard balancing (desc): measured class eval costs
COST_RANK = {"pa": 3, "mixer": 2, "balun": 1, "lna": 0}


def _era():
    try:
        h = subprocess.run(["git", "rev-parse", "--short=8", "HEAD"],
                           cwd=REPO, capture_output=True, text=True,
                           check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"],
                                    cwd=REPO, capture_output=True,
                                    text=True).stdout.strip())
    except Exception:                                           # noqa: BLE001
        h, dirty = "unknown", True
    return {"era": f"era-bnull-{h}", "dirty_tree": dirty}


def _pairs():
    """Deterministic full matrix, cost-sorted desc for shard balance."""
    cells = json.loads(SPECMAN.read_text())["cells"]
    anch = json.loads(ANCHMAN.read_text())["classes"]
    pairs = []
    for cell in cells:
        acls = CLASS_MAP[cell["circuit_class"]]
        for fam, rec in anch[acls]["families"].items():
            pairs.append({"cell": cell["name"], "acls": acls, "fam": fam,
                          "spec": str(REPO / "kaggle" / cell["file"]),
                          "tokens_file": str(REPO / rec["tokens_file"])})
    pairs.sort(key=lambda p: (-COST_RANK[p["acls"]],))          # stable
    return pairs


def _round(x, n=4):
    if isinstance(x, float):
        return round(x, n)
    if isinstance(x, dict):
        return {k: _round(v, n) for k, v in x.items()}
    return x


def run_pair(p, era, seeds=SEEDS, budget=EVALS_PER_SEED, outdir=None):
    outdir = outdir or (OUT / p["acls"])
    outdir.mkdir(parents=True, exist_ok=True)
    rpath = outdir / f"{p['cell']}__{p['fam']}.json"
    if rpath.exists():
        try:
            prior = json.loads(rpath.read_text())
            if len(prior.get("seeds", [])) >= len(seeds):
                return prior, "skipped"
        except Exception:                                       # noqa: BLE001
            pass                                    # unreadable -> re-run
    tokens = json.loads(Path(p["tokens_file"]).read_text())
    rec = {"cell": p["cell"], "class": p["acls"], "anchor": p["fam"],
           "spec_file": os.path.relpath(p["spec"], REPO),
           "budget_per_seed": budget, "pdk": PDK, **era, "seeds": []}
    spec = Spec.load(p["spec"])
    t0 = time.time()
    for seed in seeds:
        res = PREP.smoke_run(tokens, p["spec"], seed, budget, PDK)
        if res is None:
            rec["seeds"].append({"seed": seed, "not_sizable": True,
                                 "feasible": False})
            continue
        ok, viol = (spec.feasible(res["metrics"]) if res["metrics"]
                    else (False, {"_no_winner": 1.0}))
        rec["seeds"].append({
            "seed": seed, "feasible": bool(ok),
            "violations": _round(dict(viol)),
            "metrics": _round(res["metrics"]),
            "winner_reeval_ungated": res["winner_reeval_ungated"],
            "n_evals": res["n_evals"], "n_sim_fail": res["n_sim_fail"],
            "sim_error": res["sim_error"]})
        rpath.write_text(json.dumps(rec, indent=1))    # progress durable
    rec["any_feasible"] = any(s.get("feasible") for s in rec["seeds"])
    rec["wall_s"] = round(time.time() - t0, 1)
    rpath.write_text(json.dumps(rec, indent=1))
    return rec, "ran"


def collect():
    cells = json.loads(SPECMAN.read_text())["cells"]
    era = _era()
    index = {"collected": time.strftime("%Y-%m-%d %H:%M"), **era,
             "evals_per_seed": EVALS_PER_SEED, "n_seeds": len(SEEDS),
             "cells": {}, "missing_pairs": [], "survivors": [],
             "null_reachable": []}
    for p in _pairs():
        rpath = OUT / p["acls"] / f"{p['cell']}__{p['fam']}.json"
        c = index["cells"].setdefault(
            p["cell"], {"class": p["acls"], "anchors": {}})
        if not rpath.exists():
            index["missing_pairs"].append(f"{p['cell']}__{p['fam']}")
            continue
        r = json.loads(rpath.read_text())
        if len(r.get("seeds", [])) < len(SEEDS):
            index["missing_pairs"].append(f"{p['cell']}__{p['fam']} PARTIAL")
            continue
        c["anchors"][p["fam"]] = {
            "any_feasible": r.get("any_feasible", False),
            "wall_s": r.get("wall_s"),
            "n_sim_fail": sum(s.get("n_sim_fail") or 0 for s in r["seeds"])}
    for name, c in index["cells"].items():
        if any(a["any_feasible"] for a in c["anchors"].values()):
            c["verdict"] = "NULL-REACHABLE (excluded)"
            index["null_reachable"].append(name)
        elif len(c["anchors"]) == 0 or any(
                f"{name}__" in m for m in index["missing_pairs"]):
            c["verdict"] = "INCOMPLETE"
        else:
            c["verdict"] = "SURVIVOR"
            index["survivors"].append(name)
    (OUT / "INDEX.json").write_text(json.dumps(index, indent=1))
    print(f"collect: {len(index['survivors'])} survivors / "
          f"{len(index['null_reachable'])} null-reachable / "
          f"{len(index['missing_pairs'])} missing-or-partial pairs "
          f"(of {len(_pairs())}); INDEX.json written")
    return 0 if not index["missing_pairs"] else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    era = _era()
    if "--collect" in argv:
        return collect()
    if "--validate" in argv:
        p = next(x for x in _pairs() if x["acls"] == "lna")
        rec, how = run_pair(p, era, seeds=(1,), budget=40,
                            outdir=OUT / "validate-scratch")
        print(f"validate [{how}]: {p['cell']}__{p['fam']} seeds="
              f"{len(rec['seeds'])} feasible={rec.get('any_feasible')} "
              f"wall={rec.get('wall_s')}s")
        return 0 if rec["seeds"] else 1
    shard_k, shard_n = 0, 1
    for a in argv:
        if a.startswith("--shard"):
            shard_k, shard_n = map(int, a.split("=", 1)[1].split("/"))
    pairs = [p for i, p in enumerate(_pairs()) if i % shard_n == shard_k]
    print(f"[shard {shard_k}/{shard_n}] {len(pairs)} pairs  {era['era']}"
          f"{' DIRTY-TREE' if era['dirty_tree'] else ''}", flush=True)
    for i, p in enumerate(pairs):
        rec, how = run_pair(p, era)
        print(f"[shard {shard_k}/{shard_n}] {i + 1}/{len(pairs)} "
              f"{p['cell']}__{p['fam']} {how} "
              f"any_feasible={rec.get('any_feasible')} "
              f"wall={rec.get('wall_s')}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
