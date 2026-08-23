"""E-12 P0.2 -- answer-exclusion filter (ZERO sims).

Binding pre-reg: engineer/E12-TRAINEDIT.md §3.1 (answer exclusion), §3.2
(leave-base-task-out: dhruva-l1 held out entirely), §11.3.

For every SCORED goal (DEV, HELD-OUT, FRESH) this lists every training row whose
TOPOLOGY passes that goal's extended spec (base-feasible + delta), so those rows
never enter training. Training rows live in two banks:

  * topo_labels store rows (lna/data/topo_labels.jsonl): each carries a full
    metrics dict -> base-feasibility + delta is RECOMPUTED from raw metrics
    (no stored flag), giving the excluded wl_hashes.
  * the E-11 edit log (engineer/data/e11_edit_log/edits.jsonl): rows carry a
    realized_wl (the topology) and content-addressed sequence shas, but NO full
    metrics (E-11 L1-screened at x0=0.5; it never re-sized to feasibility, and
    scored 0 solves). A topology "passes the extended spec" iff a store row with
    the SAME wl_hash passes it. So an edit-log row / sequence is excluded iff its
    realized_wl is in the goal's excluded store wl set. (This is the only sound
    zero-sim topology->pass test for the log.)

s22 note: store rows carry no s22_max_db, so no store row can be *shown* to pass
an s22 delta from raw metrics. The only banked s22 measurements are the 8
e10_s22_instrument designs; those wl_hashes are checked for the s22 goals (G2'',
FRESH if it uses s22) and any matching edit-log realized_wl excluded too.

l1 ban (§3.2): ALL dhruva-l1 store rows and ALL edit-log rows touching a
dhruva-l1 topology (anchor_wl or realized_wl == a dhruva-l1 store wl) are
training-banned, independent of any goal.

ZERO ngspice calls. Output: engineer/data/e12/excluded_rows.json.

    python e12_exclude.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import datastore as ds          # noqa: E402
from spec import Spec           # noqa: E402

EDIT_LOG = os.path.join(HERE, "data", "e11_edit_log", "edits.jsonl")
S22_DIR = os.path.join(HERE, "data", "e10_s22_instrument")
OUT = os.path.join(HERE, "data", "e12", "excluded_rows.json")

# Scored goals: base spec + in-memory delta (extended spec = base + delta).
# FRESH n78 is filled in from engineer/data/e12/fresh_task.json when present.
SCORED = {
    # DEV
    "G2pp": {"base": "dhruva-s",  "delta": {"s22_max_db": {"max": -10.0}},
             "tier": "DEV"},
    "G13":  {"base": "dhruva-l2", "delta": {"nf_db": {"max": 1.45}},
             "tier": "DEV"},
    "G9":   {"base": "dhruva-l5", "delta": {"s21_ripple_db": {"max": 3.0}},
             "tier": "DEV"},
    "G7pp": {"base": "dhruva-l5", "delta": {"idd_ma": {"max": 9.0},
                                            "s21_db": {"min": 22.3}},
             "tier": "DEV"},
    "G12":  {"base": "dhruva-l5", "delta": {"s11_max_db": {"max": -15.0}},
             "tier": "DEV"},
    # HELD-OUT
    "G1pp": {"base": "dhruva-l1", "delta": {"s21_db": {"min": 33.0}},
             "tier": "HELD-OUT"},
    "H2":   {"base": "dhruva-l1", "delta": {"nf_db": {"max": 1.25}},
             "tier": "HELD-OUT"},
}


def _ext_spec(base, delta):
    sp = Spec.load(base)
    sp.constraints = dict(sp.constraints)
    for k, v in delta.items():
        sp.constraints[k] = dict(v)
    return sp


def _passes_ext(base_spec, ext_spec, metrics):
    """base-feasible AND ext-feasible on RAW metrics; no stored flag."""
    if not metrics:
        return False
    ok, _ = base_spec.feasible(metrics)
    if not ok:
        return False
    ok2, _ = ext_spec.feasible(metrics)
    return bool(ok2)


def load_store():
    return ds.load("topo_labels")


def load_s22_measured():
    """wl_hash -> measured_metrics (with s22_max_db) for the 8 instrument rows."""
    out = {}
    for fn in sorted(os.listdir(S22_DIR)):
        if fn.startswith("topo_") and fn.endswith(".json"):
            d = json.load(open(os.path.join(S22_DIR, fn)))
            out[d.get("wl_hash")] = d.get("measured_metrics") or {}
    return out


def main():
    rows = load_store()
    s22_meas = load_s22_measured()

    # Attach a fresh n78 goal if the fresh task exists.
    fresh_path = os.path.join(HERE, "data", "e12", "fresh_task.json")
    if os.path.exists(fresh_path):
        fr = json.load(open(fresh_path))
        g = fr.get("goal")
        if g:
            SCORED[g["id"]] = {"base": "__n78__", "delta": g["delta"],
                               "tier": "FRESH", "n78_spec": fr["spec"]}

    # Precompute edit-log index: realized_wl -> set(row ids), anchor_wl usage,
    # and dhruva-l1 topology set.
    l1_store_wls = set(r.get("wl_hash") for r in rows
                       if r.get("spec") == "dhruva-l1")

    # Walk edit log once, bucket by realized_wl and record l1 touches.
    log_by_wl = {}            # realized_wl -> [line_no,...]
    log_seq_by_wl = {}        # realized_wl -> set(seq shas)
    l1_log_rows = []          # line numbers touching a dhruva-l1 topology
    n_log = 0
    with open(EDIT_LOG) as fh:
        for i, line in enumerate(fh):
            n_log += 1
            try:
                d = json.loads(line)
            except Exception:
                continue
            rw = d.get("realized_wl")
            aw = d.get("anchor_wl")
            shas = set()
            for key in ("regrown_tokens_sha", "anchor_seq_sha"):
                if d.get(key):
                    shas.add(d[key])
            if rw:
                log_by_wl.setdefault(rw, []).append(i)
                log_seq_by_wl.setdefault(rw, set()).update(shas)
            # l1 ban: anchor or realized topology is a dhruva-l1 store topology
            if (aw in l1_store_wls) or (rw in l1_store_wls):
                l1_log_rows.append(i)

    # ---- l1 ban list (§3.2) -------------------------------------------------
    l1_ban = {
        "reason": "leave-base-task-out (§3.2): dhruva-l1 held out entirely",
        "store_rows": {
            "n": len(l1_store_wls),
            "wl_hashes": sorted(l1_store_wls),
        },
        "edit_log_rows": {
            "n": len(l1_log_rows),
            "line_numbers": l1_log_rows,
        },
    }

    # ---- per-goal exclusion -------------------------------------------------
    goals_out = {}
    for gid, cfg in SCORED.items():
        if cfg["base"] == "__n78__":
            base_spec = Spec(cfg["n78_spec"], source="n78(in-memory)")
            ext = Spec(cfg["n78_spec"], source="n78(in-memory)")
            ext.constraints = dict(ext.constraints)
            for k, v in cfg["delta"].items():
                ext.constraints[k] = dict(v)
            base_task_specname = None   # fresh n78: no store rows to match spec
        else:
            base_spec = Spec.load(cfg["base"])
            ext = _ext_spec(cfg["base"], cfg["delta"])
            base_task_specname = cfg["base"]

        excl_wls = set()
        excl_rows = []      # store row identities that pass
        is_s22 = any(k == "s22_max_db" for k in cfg["delta"])

        # Store rows: only rows of the SAME base spec can be base-feasible for
        # that spec (feasibility is spec-relative). For the fresh n78 there are
        # no store rows on that spec, so store exclusion is empty (fresh task).
        if base_task_specname is not None:
            for r in rows:
                if r.get("spec") != base_task_specname:
                    continue
                m = r.get("metrics")
                if is_s22:
                    # store rows carry no s22; fall through to s22-measured set.
                    continue
                if _passes_ext(base_spec, ext, m):
                    excl_wls.add(r.get("wl_hash"))
                    excl_rows.append({"wl_hash": r.get("wl_hash"),
                                      "ts": r.get("ts"),
                                      "spec": r.get("spec")})

        # s22 goals: use the instrument-measured designs (only banked s22).
        s22_hits = []
        if is_s22 and base_task_specname is not None:
            for wl, mm in s22_meas.items():
                # instrument designs are dhruva-s; only relevant if base matches
                if base_task_specname != "dhruva-s":
                    break
                if _passes_ext(base_spec, ext, mm):
                    excl_wls.add(wl)
                    s22_hits.append(wl)
                    excl_rows.append({"wl_hash": wl, "source": "e10_s22_instrument"})

        # Edit-log rows/seqs whose realized topology is in excl_wls.
        log_rows = []
        log_seqs = set()
        for wl in excl_wls:
            for ln in log_by_wl.get(wl, []):
                log_rows.append(ln)
            log_seqs.update(log_seq_by_wl.get(wl, set()))

        goals_out[gid] = {
            "tier": cfg["tier"],
            "base_task": (cfg["base"] + "-t2-a") if base_task_specname else "n78",
            "delta": cfg["delta"],
            "store_rows_excluded": {
                "n_wl": len(excl_wls),
                "wl_hashes": sorted(excl_wls),
                "s22_instrument_hits": sorted(s22_hits) if is_s22 else None,
            },
            "edit_log_rows_excluded": {
                "n": len(set(log_rows)),
                "line_numbers": sorted(set(log_rows)),
                "n_seq_shas": len(log_seqs),
                "seq_shas": sorted(log_seqs),
            },
            "note": ("s22 delta: store rows carry no s22 metric; excluded set "
                     "derived from e10_s22_instrument measured designs."
                     if is_s22 else
                     "topology passes = base-feasible + delta on raw metrics."),
        }

    result = {
        "campaign": "e12", "phase": "P0.2 answer-exclusion filter",
        "ngspice_calls": 0,
        "store_rows_total": len(rows),
        "edit_log_rows_total": n_log,
        "l1_ban": l1_ban,
        "goals": goals_out,
        "method": ("A training row is excluded iff its topology is "
                   "base-feasible AND passes the goal delta, recomputed from "
                   "raw metrics (no stored flag). Edit-log rows carry no "
                   "metrics; a log row/seq is excluded iff its realized_wl "
                   "matches an excluded store/instrument topology."),
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    os.replace(tmp, OUT)

    print("E-12 answer-exclusion filter (0 sims)\n")
    print(f"store rows total: {len(rows)}   edit-log rows total: {n_log}")
    print(f"l1 ban: {l1_ban['store_rows']['n']} store wls, "
          f"{l1_ban['edit_log_rows']['n']} edit-log rows\n")
    print(f"{'goal':<7}{'tier':<10}{'store_wl':>9}{'log_rows':>10}{'seqs':>7}")
    for gid, g in goals_out.items():
        print(f"{gid:<7}{g['tier']:<10}"
              f"{g['store_rows_excluded']['n_wl']:>9}"
              f"{g['edit_log_rows_excluded']['n']:>10}"
              f"{g['edit_log_rows_excluded']['n_seq_shas']:>7}")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
