#!/usr/bin/env python
"""VM step 1: build the unified (topology, spec) -> sizing-outcome table.

PREREG-ADVERSARIAL-V0.md (commit 307673caf), experiment VM. Read-only over every
source; writes only into this directory:

  data/rows.jsonl.gz     one row per recorded sizing outcome (included AND excluded,
                         with `incl` / `excl_reason`)
  data/tokmap.json.gz    token hash -> harness token list (tokhash = sha1(json)[:16])
  data/build_manifest.json  source files, line counts, md5 of the bytes read, counts

Label semantics (README "Data"): `y` = feasible under rl-v1.1 semantics.
  rl-v1.1 row  -> res.feasible
  rl-v1 row    -> res.feasible AND port_dc_prefilter(tokens).pass   (bench-v2 D23:
                  for a pre-filter-passing topology the behavioural check is a
                  provable no-op)
  aux row      -> its own profile's verdict (legacy-lib / stab-gate / stab-inloop /
                  rl-v1); `profile` is a model feature; aux rows are never in a
                  primary test set.
Population: only candidates that would actually be SIZED under rl-v1.1 (they pass the
free pre-sizing checks: topo limits, structural degeneracy, port-DC pre-filter).
Pre-sizing rejects cost 0 sims, so pruning them saves nothing.
"""
import collections
import gzip
import hashlib
import json
import math
import os
import re
import sys

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/data"
SCR = f"{HERE}/_scratch"
BV2 = f"{REPO}/kaggle/campaigns/bench-v2/run"
CAMP = f"{REPO}/kaggle/campaigns"
V12LIB = f"{REPO}/kaggle/editcap-lib-v12-45nm"

GRID_RE = re.compile(r"((?:wb|nb)\d{3,4})-(noise|gain|power)")
# snapshot of the LIVE bench-v2 run taken 2026-10-01 20:48 IST (first N complete lines)
BV2_RESULTS_LIMIT = 21660
SPEC_KEYS = ["nf", "s11_max_db", "s21_db", "s21_ripple_db", "idd_ma", "mu_min"]


def th(tokens):
    return hashlib.sha1(json.dumps(list(tokens)).encode()).hexdigest()[:16]


def md5_bytes(b):
    return hashlib.md5(b).hexdigest()


MANI = {"sources": {}, "counts": {}}


def read_lines(path, limit=None):
    """Snapshot read: the bench-v2 run is LIVE, so results.jsonl is read once, up to
    the last complete line, and its md5/line count recorded."""
    b = open(path, "rb").read()
    if not b.endswith(b"\n"):
        b = b[:b.rfind(b"\n") + 1]
    lines = b.decode().splitlines()
    if limit:
        lines = lines[:limit]
        b = ("\n".join(lines) + "\n").encode()
    MANI["sources"][os.path.relpath(path, REPO)] = {"lines": len(lines), "md5": md5_bytes(b)}
    return [json.loads(l) for l in lines if l.strip()]


def read_json(path):
    b = open(path, "rb").read()
    MANI["sources"][os.path.relpath(path, REPO)] = {"bytes": len(b), "md5": md5_bytes(b)}
    return json.loads(b)


# ------------------------------------------------------------------ specs
import yaml  # noqa: E402

_SPEC = {}


def spec_feats(path_or_dict, mu_override=None, rlv1_form=False):
    """Compact spec record: band + supported constraint limits (+ objective weights,
    max_inductors). rlv1_form applies bench_anchor_prep.rl_v1_spec's renames in
    memory (wb nf_db->nf_max_db + max_inductors 2; nb s11_db->s11_max_db; mu_min)."""
    key = (path_or_dict if isinstance(path_or_dict, str) else id(path_or_dict),
           mu_override, rlv1_form)
    if key in _SPEC:
        return _SPEC[key]
    d = yaml.safe_load(open(path_or_dict)) if isinstance(path_or_dict, str) else path_or_dict
    band = d.get("band") or {}
    cons = {k: v for k, v in (d.get("constraints") or {}).items()
            if (v or {}).get("status") != "unsupported"}
    topo = d.get("topology") or {}
    wide = band.get("type") == "wideband"
    if rlv1_form:
        cons = dict(cons)
        if wide and "nf_db" in cons:
            cons.setdefault("nf_max_db", cons.pop("nf_db"))
        if not wide and "s11_db" in cons:
            cons.setdefault("s11_max_db", cons.pop("s11_db"))
        cons["mu_min"] = {"min": 1.0}
        topo = dict(topo)
        if wide:
            topo["max_inductors"] = 2
    if mu_override is not None:
        cons = dict(cons)
        cons["mu_min"] = {"min": float(mu_override)}
    lim = {}
    for name, c in cons.items():
        lim[name] = {k: float(c[k]) for k in ("min", "max") if k in c}
    obj = {o.get("metric"): float(o.get("weight", 1.0)) for o in (d.get("objectives") or [])}
    rec = {"band_type": band.get("type"), "f0": band.get("f0"), "f_lo": band.get("f_lo"),
           "f_hi": band.get("f_hi"), "lim": lim, "obj": obj,
           "max_inductors": topo.get("max_inductors"),
           "device_budget": topo.get("device_budget"),
           "name": d.get("name")}
    rec["spec_sha"] = hashlib.sha1(json.dumps(
        {k: rec[k] for k in ("band_type", "f0", "f_lo", "f_hi", "lim", "obj", "max_inductors",
                             "device_budget")}, sort_keys=True).encode()).hexdigest()[:16]
    _SPEC[key] = rec
    return rec


def worst_margin(lim, metrics):
    """mysolve._margins re-implemented: normalized (scale max(|limit|,1)) margin of
    every supported constraint; worst = min. None if no metric is available."""
    if not metrics:
        return None, None
    worst, wname = None, None
    for name, c in lim.items():
        ach = metrics.get(name)
        if ach is None or not isinstance(ach, (int, float)):
            continue
        vals = [abs(v) for v in c.values()]
        sc = max(max(vals) if vals else 1.0, 1.0)
        mg = (ach - c["min"]) / sc if "min" in c else (c["max"] - ach) / sc if "max" in c else None
        if mg is not None and (worst is None or mg < worst):
            worst, wname = mg, name
    return worst, wname


# ------------------------------------------------------- free pre-sizing checks
import bench_anchor_prep as PREP  # noqa: E402
from topology import Topology  # noqa: E402
from spec import Spec  # noqa: E402

_PF, _FREE = {}, {}


def prefilter_pass(tok, tokens):
    if tok not in _PF:
        try:
            _PF[tok] = bool(PREP.port_dc_prefilter(list(tokens))["pass"])
        except Exception:                                        # noqa: BLE001
            _PF[tok] = False
    return _PF[tok]


_RLV1_PATH = {}


def rlv1_spec_obj(src):
    if src not in _RLV1_PATH:
        _RLV1_PATH[src] = Spec.load(PREP.rl_v1_spec(src, out_dir=f"{SCR}/rlv1-specs"))
    return _RLV1_PATH[src]


def free_checks_v11(tok, tokens, spec_obj, sk):
    """(passes, why) of the 0-sim rl-v1.1 pre-sizing checks smoke_run applies."""
    k = (tok, sk)
    if k in _FREE:
        return _FREE[k]
    try:
        topo = Topology(list(tokens))
        if not PREP.topo_limits(spec_obj, topo)["ok"]:
            r = (False, "topo_limits")
        elif PREP.structural_degeneracy(topo):
            r = (False, "structural_degeneracy")
        elif not prefilter_pass(tok, tokens):
            r = (False, "port_dc_prefilter")
        else:
            r = (True, None)
    except Exception as e:                                       # noqa: BLE001
        r = (False, f"parse_error:{e!r}"[:80])
    _FREE[k] = r
    return r


# ================================================================ bench-v2
def load_bv2(tokmap):
    rtc = read_lines(f"{BV2}/rtcache.jsonl")
    for r in rtc:
        t = (r.get("v") or {}).get("tokens")
        if t:
            tokmap[th(t)] = t
    cand, cells, tasks, accepted = {}, {}, {}, set()
    for sub in ("pre-amendment", "amendment-1-record", ""):
        d = f"{BV2}/{sub}" if sub else BV2
        for c in read_lines(f"{d}/candidates.jsonl"):
            cand[c["cid"]] = {"anchor": c.get("anchor"), "g": c.get("g"), "stream": c.get("stream")}
            if c.get("tokens"):
                tokmap[th(c["tokens"])] = c["tokens"]
        for c in read_lines(f"{d}/cells.jsonl"):
            prev = cells.get(c["name"], {})
            st = set(prev.get("statuses", ())) | {c.get("status")}
            cells[c["name"]] = {"anchor": c.get("anchor"), "g": c.get("g"), "statuses": sorted(
                s for s in st if s), "era_tag": c.get("era_tag")}
            if c.get("status") == "accepted":
                accepted.add(c["name"])
            if c.get("tokens"):
                tokmap[th(c["tokens"])] = c["tokens"]
        for t in read_lines(f"{d}/train.jsonl"):
            tasks[t["name"]] = {"anchor": t.get("anchor"), "g": t.get("g")}
    res = read_lines(f"{BV2}/results.jsonl", limit=BV2_RESULTS_LIMIT)
    MANI["counts"]["bv2_results_rows"] = len(res)
    MANI["counts"]["bv2_accepted_cells_any_era"] = sorted(accepted)
    rows = []
    for d in res:
        meta = d.get("meta") or {}
        r = d.get("res")
        spec_rel = d["spec"]
        sp = spec_feats(f"{REPO}/{spec_rel}")
        m = GRID_RE.search(os.path.basename(spec_rel))
        g = f"{m.group(1)}-{m.group(2)}" if m else None
        kind = d.get("kind")
        cell = meta.get("cell")
        task = meta.get("task")
        cid = meta.get("cid")
        if kind == "cal":
            lineage, grp = meta.get("anchor"), f"cal:{g}:{meta.get('anchor')}"
        elif kind in ("search", "confirm"):
            lineage, grp = (cand.get(cid) or {}).get("anchor"), f"cid:{cid}"
        elif cell:
            lineage = meta.get("anchor") if kind == "F1" else (cells.get(cell) or {}).get("anchor")
            grp = f"cell:{cell}"
        elif task:
            lineage = meta.get("anchor") if kind == "T-F1" else (tasks.get(task) or {}).get("anchor")
            grp = f"task:{task}"
        else:
            lineage, grp = None, f"misc:{d['jid']}"
        row = {"src": "bench-v2", "rid": d["jid"], "ts": d.get("ts"), "kind": kind,
               "cls": d.get("cls"), "profile": d.get("profile"), "budget": d.get("budget"),
               "seed": d.get("seed"), "tok": d.get("tok"), "spec_sha": sp["spec_sha"],
               "spec": spec_rel, "g": g, "grp": grp, "lineage": lineage,
               "cell": cell, "task": task, "cid": cid,
               "fenced": bool(cell and cell in accepted),
               "derived": bool(d.get("derived_from")), "incl": False, "excl_reason": None}
        if r is None:
            row["excl_reason"] = "worker_error"
            rows.append(row)
            continue
        tokens = tokmap.get(d.get("tok"))
        if tokens is None:
            row["excl_reason"] = "no_tokens"
            rows.append(row)
            continue
        pf = prefilter_pass(d["tok"], tokens)
        row["prefilter_pass"] = pf
        feas = bool(r.get("feasible"))
        row["feasible_own"] = feas
        row["y"] = int(feas and (pf if d.get("profile") == "rl-v1" else True))
        wm, wn = worst_margin(sp["lim"], r.get("metrics") or {})
        row["wm"], row["wm_name"] = wm, wn
        row["n_evals"] = r.get("n_evals")
        row["secs"] = d.get("secs")
        row["infeasible_reason"] = (r.get("infeasible_reason") or "")[:60] or None
        pd = r.get("port_dc")
        row["port_dc_behav"] = None if not isinstance(pd, dict) else bool(pd.get("pass"))
        if d.get("inproc_reject") or (r.get("n_evals") == 0 and (r.get("infeasible_reason") or "").startswith(
                ("topology limits", "structural degeneracy", "port_dc_prefilter"))):
            row["excl_reason"] = "pre_sizing_reject_free"
        elif row["derived"]:
            row["excl_reason"] = "derived_copy_of_rl-v1_twin"
        elif not pf:
            row["excl_reason"] = "port_dc_prefilter_fail_(free_reject_under_rl-v1.1)"
        elif not r.get("n_evals"):
            row["excl_reason"] = "zero_evals_other"
        else:
            row["incl"] = True
        rows.append(row)
    return rows


# ================================================================ aux sources
def load_aux(tokmap):
    rows = []
    # token maps of the v1.2 audit
    ec_c = {}
    for c in read_lines(f"{CAMP}/bench-v12-audit/E-c/candidates.jsonl"):
        if c.get("tokens"):
            ec_c[c["cid"]] = c["tokens"]
            tokmap[th(c["tokens"])] = c["tokens"]
    ed_c = read_json(f"{CAMP}/bench-v12-audit/E-d/cand.json")
    for k, v in ed_c.items():
        if isinstance(v, list):
            tokmap[th(v)] = v
    for cell in sorted(os.listdir(V12LIB)):
        p = f"{V12LIB}/{cell}/anchor.tokens.json"
        if os.path.exists(p):
            t = json.load(open(p))
            tokmap[th(t)] = t

    def add(src, rid, ts, cell, profile, budget, seed, tokens, feasible, sizable, metrics,
            spec_mode, extra=None):
        src_spec = f"{V12LIB}/{cell}/spec.yaml"
        if spec_mode == "lib":
            sp = spec_feats(src_spec)
        elif spec_mode == "mu1":
            sp = spec_feats(src_spec, mu_override=1.0)
        else:
            sp = spec_feats(src_spec, rlv1_form=True)
        row = {"src": src, "rid": rid, "ts": ts, "kind": src, "cls": "aux", "profile": profile,
               "budget": budget, "seed": seed, "tok": th(tokens) if tokens else None,
               "spec_sha": sp["spec_sha"], "spec": f"{os.path.relpath(src_spec, REPO)}#{spec_mode}",
               "g": cell, "grp": f"aux:{cell}", "lineage": None, "cell": cell, "task": None,
               "cid": None, "fenced": False, "derived": False, "incl": False, "excl_reason": None}
        row.update(extra or {})
        if tokens is None:
            row["excl_reason"] = "no_tokens"
            return rows.append(row)
        tokmap[row["tok"]] = list(tokens)
        if not sizable:
            row["excl_reason"] = "not_sizable"
            return rows.append(row)
        ok, why = free_checks_v11(row["tok"], tokens, rlv1_spec_obj(src_spec), cell)
        row["prefilter_pass"] = prefilter_pass(row["tok"], tokens)
        row["feasible_own"] = bool(feasible)
        row["y"] = int(bool(feasible))
        wm, wn = worst_margin(sp["lim"], metrics or {})
        row["wm"], row["wm_name"] = wm, wn
        if not ok:
            row["excl_reason"] = f"fails_rl-v1.1_free_check:{why}"
        else:
            row["incl"] = True
        rows.append(row)

    # E-c (legacy lib spec, single-edit search of the v1.2 anchors)
    for r in read_lines(f"{CAMP}/bench-v12-audit/E-c/results.jsonl"):
        add("E-c", f"{r['cid']}|{r['seed']}|{r.get('phase')}", r.get("ts"), r["cell"], "legacy-lib",
            r["budget"], r["seed"], ec_c.get(r["cid"]), r.get("feasible"), r.get("sizable"),
            r.get("metrics"), "lib")
    # E-d (Qwen edits, legacy lib spec)
    for r in read_lines(f"{CAMP}/bench-v12-audit/E-d/score.jsonl"):
        t = ed_c.get(f"{r['cell']}|{r['key']}")
        add("E-d", f"{r['cell']}|{r['key']}|{r['seed']}", r.get("ts"), r["cell"], "legacy-lib",
            r["budget"], r["seed"], t if isinstance(t, list) else None, r.get("feasible"),
            r.get("sizable") and not r.get("error"), r.get("metrics"), "lib")
    # R1 (lib / stab gate-only / stab gate+in-loop, budgets 600/1200/2500)
    pm = {"lib": ("legacy-lib", "lib"), "stab": ("stab-gate", "mu1"), "stabil": ("stab-inloop", "mu1")}
    for r in read_lines(f"{CAMP}/rl-readiness/R1/results.jsonl"):
        cell, key = r["uid"].split("|")
        prof, sm = pm[r["mode"]]
        add("R1", f"{r['uid']}|{r['mode']}|{r['budget']}|{r['seed']}", r.get("ts"), cell, prof,
            r["budget"], r["seed"], tokmap.get(key), r.get("feasible"),
            r.get("sizable") and not r.get("error"), r.get("metrics"), sm)
    # R4 (stability loophole tests; only the plain verifier configs)
    pm4 = {"inloop": ("stab-inloop", "mu1"), "gate": ("stab-gate", "mu1"), "lib": ("legacy-lib", "lib")}
    for i, r in enumerate(read_json(f"{CAMP}/rl-readiness/R4/results.json")["rows"]):
        res = r.get("result") or {}
        if r["mode"] not in pm4 or r.get("tag", "").startswith("reg"):
            rows.append({"src": "R4", "rid": f"R4#{i}", "incl": False, "fenced": False,
                         "excl_reason": f"special_config:{r.get('tag')}/{r['mode']}"})
            continue
        prof, sm = pm4[r["mode"]]
        add("R4", f"R4#{i}", None, r["cell"], prof, r["budget"], r["seed"], r.get("tokens"),
            res.get("feasible"), r.get("result") is not None, res.get("metrics"), sm)
    # verifier-rl-v1 tests (rl-v1 profile on v1.2 cells)
    for i, r in enumerate(read_json(f"{CAMP}/rl-readiness/verifier-rl-v1/results.json")["rows"]):
        res = r.get("result") or {}
        if r["mode"] != "rlv1" or r.get("tag") == "reg":
            rows.append({"src": "verifier-rl-v1", "rid": f"V1#{i}", "incl": False, "fenced": False,
                         "excl_reason": f"special_config:{r.get('tag')}/{r['mode']}"})
            continue
        add("verifier-rl-v1", f"V1#{i}", None, r["cell"], "rl-v1", r["budget"], r["seed"],
            r.get("tokens"), res.get("feasible") and prefilter_pass(th(r["tokens"]), r["tokens"]),
            r.get("result") is not None, res.get("metrics"), "rlv1")
    # S-1 / stability-gate: recorded without token sequences -> excluded
    for f, tag in (("bench-v12-audit/S-1-stab-inloop/results.json", "S-1"),
                   ("bench-v12-audit/stability-gate/results.json", "stability-gate")):
        for i, r in enumerate(read_json(f"{CAMP}/{f}")["rows"]):
            rows.append({"src": tag, "rid": f"{tag}#{i}", "incl": False, "fenced": False,
                         "excl_reason": "no_tokens_recorded"})
    return rows


def dedupe(rows):
    """One row per (tok, spec_sha, seed, budget, profile-family). Within bench-v2, an
    rl-v1.1 re-size of an rl-v1 row is the SAME deterministic sizing run (+ port-DC
    check), so they collapse; the rl-v1.1 row wins. Label conflicts are counted."""
    best, conflicts = {}, 0
    order = {"rl-v1.1": 0, "rl-v1": 1}
    for i, r in enumerate(rows):
        if not r.get("incl"):
            continue
        fam = "rl" if r["profile"] in ("rl-v1", "rl-v1.1") else r["profile"]
        k = (r["tok"], r["spec_sha"], r["seed"], r["budget"], fam)
        if k in best:
            j = best[k]
            if rows[j]["y"] != r["y"]:
                conflicts += 1
            keep, drop = (i, j) if order.get(r["profile"], 9) < order.get(rows[j]["profile"], 9) else (j, i)
            rows[drop]["incl"] = False
            rows[drop]["excl_reason"] = "duplicate_(tok,spec,seed,budget)"
            best[k] = keep
        else:
            best[k] = i
    return conflicts


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(f"{SCR}/rlv1-specs", exist_ok=True)
    tokmap = {}
    rows = load_bv2(tokmap)
    rows += load_aux(tokmap)
    MANI["counts"]["dedupe_label_conflicts"] = dedupe(rows)
    c = collections.Counter((r["src"], r.get("incl"), r.get("excl_reason")) for r in rows)
    MANI["counts"]["by_src_incl_reason"] = [[*k, v] for k, v in sorted(c.items(), key=str)]
    used = {r["tok"] for r in rows if r.get("tok")}
    with gzip.open(f"{OUT}/rows.jsonl.gz", "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    with gzip.open(f"{OUT}/tokmap.json.gz", "wt") as fh:
        json.dump({k: v for k, v in tokmap.items() if k in used}, fh)
    with gzip.open(f"{OUT}/specs.json.gz", "wt") as fh:
        json.dump({v["spec_sha"]: v for v in _SPEC.values()}, fh)
    json.dump(MANI, open(f"{OUT}/build_manifest.json", "w"), indent=1)
    for k, v in sorted(c.items(), key=str):
        print(k, v)
    inc = [r for r in rows if r.get("incl")]
    print("included", len(inc), "pos", sum(r["y"] for r in inc))


if __name__ == "__main__":
    main()
