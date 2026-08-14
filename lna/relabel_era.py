"""Re-label stored designs under the CURRENT harness era (plans2/15 section 5.1).

**The era problem is the first problem.** Every one of the 2,827 L2 rows and all
66,664+ `sim_points` rows in this store was measured in a harness that has since
moved under them. Three cutovers landed after most of the corpus was written:

    mf2-v1   2026-08-10  multi-finger MOS emission (FINDINGS 26/27). Single-finger
                         devices put 26-40% of the excess noise factor into BSIM4
                         gate-electrode resistance -- and removing it also MOVES
                         THE INPUT MATCH, so this is a circuit change, not just a
                         measurement change.
    nfrs-v1  2026-08-08  series-Rs noise figure (FINDINGS 13). Rows before it
                         carry the retired port-referred NF (finding #7), which
                         is a different quantity, not a worse estimate of the
                         same one.
    stab     2026-08-12+ the K / |D| / mu stability harness, and WP-STABGUARD's
                         acceptance guard on top of it (2026-08-13).

`surrogate.py`'s ERA CAVEAT states the consequence for the learned side; this
script is the supply-side fix. It does NOT re-size anything -- a re-sized design
is a different design, and that is a campaign, not a re-label. It re-measures
the SAME stored point in the CURRENT harness and appends the result as a new
row, so every learned component downstream (critic, surrogate, diagnosis heads)
can be trained on numbers that describe the simulator it actually runs against.

Doctrine, inherited from `relabel_nf.py` (WP-D1) and `relabel_mf.py` (WP-MF):

  * **A new harness is a new label domain.** New rows are stamped, never merged
    with the rows they supersede, and never pooled silently.
  * **Append-only, always.** Nothing already in the store is mutated or deleted.
    `datastore.append_l2(row, repeat_probe=True)` is the sanctioned mechanism for
    writing a second row against an existing (wl_hash, spec) key -- the store's
    own docstring names re-labeling as its purpose -- and it is the only write
    path used here.
  * **Measurement is reused, never reimplemented.** The circuit is rebuilt with
    `size.prepared_body` and measured with `size.eval_metrics`, the same two
    calls the sizing loop makes; this file contains no ngspice knowledge.
  * **The circuit is rebuilt from the row's OWN `graph.tokens`**, never from a
    `token_file` path (07-EXIT's polish bug: the file on disk drifts).
  * **The op hook rides along** (`size.OpSink`, WP-OBSERVE / 15 section 5.2):
    a re-label campaign is a campaign, so it fills `op_points.jsonl` with
    current-era, converged, `stage="label"` rows -- exactly the population
    `critic_gnn.load_op_index` selects.

What comes out: for each re-labeled design, old-era vs new-era NF / S21 / S11 /
Idd, and -- where the gap exceeds the pre-registered tolerances in `ERA_TOL` --
a `diagnosis` of `era-mismatch` on the new row carrying the verbatim deltas, so
the store becomes queryable by *which designs the era shift actually moved*.

    python lna/relabel_era.py --audit                     # what is stale, by axis
    python lna/relabel_era.py --dry-run --limit 10        # the exact work plan
    python lna/relabel_era.py --run --limit 10 --spec wifi24
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds          # noqa: E402
import extract as E             # noqa: E402
import size as S                # noqa: E402
from topology import Topology   # noqa: E402

# The era this script labels INTO. Bump it (and only it) when a fourth cutover
# lands; rows keep their own tag forever, so two relabel generations stay
# separable the way `nf_method` and `w_finger` already keep their eras separable.
ERA_TAG = "2026-08-14-relabel"
RECIPE_SUFFIX = "+era-" + ERA_TAG

INDUCTOR_Q = 12                 # the program's standing default (HANDOVER-EXEC 6.1)

# Metrics compared old-era vs new-era, and the tolerance beyond which the row is
# called ERA-STALE. PRE-REGISTERED here, chosen from what each harness change is
# known to be able to move -- not from the results.
#   nf_db        0.10 dB : the golden NF harness agrees with its analytic
#                          reference to 0.002 dB (check_nf) and with VACASK HB to
#                          0.08 dB, so 0.10 dB is "outside the harness's own
#                          agreement", i.e. a real change.
#   s21/s11      0.25 dB : one decimal place of the number this program quotes.
#   idd_ma       2% rel  : DC current is the most reproducible quantity in the
#                          deck; anything above measurement grass is structural.
ERA_TOL = {"nf_db": 0.10, "s21_db": 0.25, "s11_db": 0.25,
           "s11_max_db": 0.25, "idd_ma": ("rel", 0.02)}
COMPARE = ("nf_db", "s21_db", "s11_db", "s11_max_db", "idd_ma")


# --------------------------------------------------------------- the era itself
def era_fingerprint():
    """The live harness fingerprint stamped on every row this run writes.

    Read from the modules themselves rather than hard-coded, so a row can never
    claim an era the code it ran under did not have."""
    from to_spice import W_FINGER
    return {
        "era": ERA_TAG,
        "w_finger": W_FINGER,
        "mos_fingers": "ceil(W/w_finger)" if W_FINGER else 1,
        "nf_method": "series_rs",
        "op_schema": E.OP_SCHEMA,
        "stab_guard": S._stab_guard_on(),
        "nf_gate_default": S._nf_gate_default(),
        "inductor_q": INDUCTOR_Q,
        "git_sha": ds.git_sha(),
    }


# The three axes on which a re-measurement of a FIXED point can differ. The
# fourth stamp, `stab_guard`, is deliberately NOT here: WP-STABGUARD changes what
# `polish`/`constrained_descent` will ACCEPT during a search, so it separates
# label domains for search-derived points -- but it cannot move a number when the
# point is held fixed, which is all this script does. Every stored row predates
# it, so selecting on it would mean "re-label everything" while promising a
# change that cannot happen. It is still reported, because a row's era record
# should be complete even where it is inert.
MEASUREMENT_AXES = ("mf2-v1", "nfrs-v1", "stab-harness")


def era_gaps(row):
    """Which cutovers a stored row predates. Empty list = already current-era.

    Each test asks the row itself, not its timestamp: a stamp that is absent is
    the evidence, because every one of these stamps was introduced BY the
    cutover it names."""
    z = row.get("zoaf_cfg") or {}
    m = row.get("metrics") or {}
    gaps = []
    if "w_finger" not in z:
        gaps.append("mf2-v1")                      # single-finger emission
    if m.get("nf_method") != "series_rs":
        gaps.append("nfrs-v1")                     # retired port-referred NF
    if m.get("k_min") is None:
        gaps.append("stab-harness")                # no K/|D|/mu on the row
    if "stab_guard" not in z:
        gaps.append("stabguard")                   # pre-WP-STABGUARD acceptance
    return gaps


def measurement_gaps(row):
    """`era_gaps` restricted to the axes that can actually change a number when
    the design point is held fixed -- the selection criterion."""
    return [g for g in era_gaps(row) if g in MEASUREMENT_AXES]


# ------------------------------------------------------------------- selection
def _achieved(row):
    """The stored metric vector, preferring `metrics` and falling back to the
    margins block (older rows carry the value in both)."""
    m = dict(row.get("metrics") or {})
    for k, v in (row.get("margins") or {}).items():
        if m.get(k) is None and isinstance(v, dict):
            m[k] = v.get("achieved")
    return m


def _min_margin(row):
    """Worst normalized margin over the supported constraints; None if unknown.

    This is the same quantity the critic predicts and the sizer maximizes, so
    ranking by it ranks by 'how close to the gate this design actually is'."""
    vals = [v.get("margin") for v in (row.get("margins") or {}).values()
            if isinstance(v, dict) and v.get("margin") is not None
            and v.get("supported")]
    return min(vals) if vals else None


def rank_key(row):
    """Sort key: gate-relevant first, then NF-gated, then closest to the gate.

    Rationale (15 section 5.1 says 'top-K by critic rank + all gate-relevant
    points'): a feasible row is a claim the program has quoted, so it is the row
    whose era-staleness costs the most; an `nf_gated` row is one whose NF is a
    real constraint rather than an advisory number, so its era matters more; and
    among the rest, the near-boundary designs are where a small era shift flips
    a verdict. Ascending sort -- every term is negated."""
    z = row.get("zoaf_cfg") or {}
    mm = _min_margin(row)
    return (0 if row.get("feasible") else 1,
            0 if z.get("nf_gated") else 1,
            -(mm if mm is not None else -1e9))


def _point_key(row):
    return (row.get("wl_hash"), row.get("spec"),
            json.dumps(row.get("best_params") or {}, sort_keys=True))


def already_relabeled(rows):
    """Point keys that already carry a successor row written in THIS era.

    Makes the tool idempotent and resumable, the same property `backfill_corpus`
    has: an interrupted campaign relaunches without re-simulating, and a second
    `--limit K` walks K NEW designs instead of re-writing the first K. Re-labeling
    a point twice in one era buys nothing -- the harness is the same, so the
    numbers are the same -- while spending a key's worth of store noise."""
    return {_point_key(r) for r in rows
            if (r.get("provenance") or {}).get("era") == ERA_TAG}


def candidates(spec_filter=None, include_current=False, feasible_only=False,
               redo=False):
    """Re-labelable L2 rows, best first, deduped by (wl_hash, spec, params).

    A repeat probe of a point that is already in the list adds no information to
    a re-label -- the same design at the same values measures the same way -- so
    only the first occurrence is kept and the duplicate count is reported."""
    all_rows = ds.load("topo_labels")
    done = set() if redo else already_relabeled(all_rows)
    seen, out, total, dup, skipped = {}, [], 0, 0, 0
    for r in all_rows:
        if r.get("kind") != "L2":
            continue
        g = r.get("graph") or {}
        if not g.get("tokens") or not r.get("best_params"):
            continue                     # reference decks / failed rows: not rebuildable
        if spec_filter and r.get("spec") != spec_filter:
            continue
        if feasible_only and not r.get("feasible"):
            continue
        if not include_current and not measurement_gaps(r):
            continue                     # already current-era: nothing to learn
        total += 1
        key = _point_key(r)
        if key in done:
            skipped += 1
            continue
        if key in seen:
            dup += 1
            continue
        seen[key] = True
        out.append(r)
    out.sort(key=rank_key)
    return out, total, dup, skipped


# ----------------------------------------------------------------- re-labeling
def _delta(old, new, name):
    """(delta, stale?) for one metric, or (None, False) when it cannot be judged."""
    a, b = old.get(name), new.get(name)
    if a is None or b is None:
        return None, False
    d = b - a
    tol = ERA_TOL.get(name)
    if isinstance(tol, tuple):                       # relative tolerance
        stale = abs(d) > abs(a) * tol[1] if a else abs(d) > 0
    else:
        stale = abs(d) > tol
    return d, stale


def old_domain_spec(row):
    """The spec under the GATING the stored row was judged by, or None if it was
    judged by today's gating anyway.

    Necessary for an honest verdict. Until WP-D1 the sizer forced `nf_db` to
    `unsupported`, so a pre-WP-D1 "feasible" is a **tier-1 claim** (S11/S21/Idd
    only) that "stays valid on its own terms" (`size._spec_for_sizing`). Judging
    such a row's re-measurement against today's NF-gated spec and calling the
    difference an ERA effect would blame the harness for a change of question.
    So the flip that this script attributes to the era is computed like-for-like,
    under the old row's own gating, and the gating difference is reported
    separately."""
    old_gated = (row.get("zoaf_cfg") or {}).get("nf_gated")
    if bool(old_gated) == bool(S._nf_gate_default()):
        return None
    return S._spec_for_sizing(row.get("spec"), nf_gate=bool(old_gated))


def nf_comparable(row):
    """Is the stored `nf_db` the same QUANTITY as the one measured today?

    Pre-nfrs-v1 rows carry the port-referred NF that finding #7 retired -- a
    different quantity, not a worse estimate of the same one. Differencing the
    two would manufacture a delta out of a definition change."""
    return (row.get("metrics") or {}).get("nf_method") == "series_rs"


# Old-geometry replay fence tolerances, inherited from `relabel_mf.py` step 4.
FENCE_TOL = {"s21_db": 1.0, "s11_db": 2.0, "s11_max_db": 2.0}


def replay_fence(topo, params, spec, stored):
    """Re-measure the stored point under the OLD (single-finger) geometry.

    This is what turns a delta into a **proof**. Without it, "the new harness
    reads 3 dB different" has three possible causes: the era, a stale
    (topology, params) pair that never produced the stored numbers, or simulator
    noise. Reproducing the stored numbers under the old geometry eliminates the
    other two, and only then is the remaining difference attributable to the
    cutover. Measured on the pilot: 20/20 designs reproduced to 0.000 dB.

    Costs one extra evaluation per design (~0.1 s here, ~12% of the per-design
    wall) -- cheap enough that it is on by default and `--no-fence` is the
    escape hatch, not the other way round.

    Always returns a dict, so `fence is None` means exactly one thing upstream:
    the fence was not run at all (`--no-fence`)."""
    old = S.prepared_body(topo, inductor_q=INDUCTOR_Q, w_finger=None)
    if old is None:
        return {"ok": False, "deltas": {},
                "reason": "old-geometry deck could not be built"}
    m = S.eval_metrics(old[0], params, spec, nf_gated=True)
    if m is None:
        return {"ok": False, "deltas": {}, "reason": "old-geometry sim failed"}
    deltas, ok = {}, True
    for name, tol in FENCE_TOL.items():
        a, b = stored.get(name), m.get(name)
        if a is None or b is None:
            continue
        deltas[name] = b - a
        if abs(b - a) > tol:
            ok = False
    return {"ok": ok, "deltas": deltas}


def relabel_one(row, spec, keep_noise_budget=True, spec_old=None, fence=True):
    """Re-measure ONE stored point under the current harness. Returns a result
    dict; appends nothing (the caller decides). Pure measurement + comparison.

    The two calls that do the work -- `prepared_body` and `eval_metrics` -- are
    size.py's own, taken as-is with current-era defaults (`w_finger` unset means
    to_spice's multi-finger default; `nf_gated=True` means the series-Rs NF).
    Nothing about ngspice is reimplemented here."""
    topo = Topology(row["graph"]["tokens"])
    params = row["best_params"]
    prep = S.prepared_body(topo, inductor_q=INDUCTOR_Q)
    if prep is None:
        return {"status": "bias-skipped", "topo": topo}
    body = prep[0]
    cap = {} if S._op_enabled() else None
    t0 = time.time()
    m_new = S.eval_metrics(body, params, spec, nf_gated=True, op_capture=cap)
    secs = time.time() - t0
    if m_new is None:
        return {"status": "sim-failed", "topo": topo, "secs": secs, "body": body}
    nb = None
    if keep_noise_budget and S.nf_is_gated(spec) and m_new.get("nf_db") is not None:
        nb = S._noise_budget_row(body, params, spec)   # critic input features (WP-L5)
    old = _achieved(row)
    nf_ok = nf_comparable(row)
    deltas, stale, incomparable = {}, [], []
    for name in COMPARE:
        if name == "nf_db" and not nf_ok:
            incomparable.append("nf_db")     # port-referred vs series-Rs: not a delta
            continue
        d, is_stale = _delta(old, m_new, name)
        if d is not None:
            deltas[name] = d
            if is_stale:
                stale.append(name)
    fenced = replay_fence(topo, params, spec, old) if fence else None
    feas_now = spec.feasible(m_new)[0]
    # like-for-like: the new numbers judged by the OLD row's gating, so the flip
    # attributed to the era is not contaminated by WP-D1's change of question.
    feas_like = spec_old.feasible(m_new)[0] if spec_old is not None else feas_now
    return {"status": "ok", "topo": topo, "params": params, "metrics": m_new,
            "old": old, "deltas": deltas, "stale": stale,
            "incomparable": incomparable, "op": cap, "fence": fenced,
            "noise_budget": nb, "secs": secs, "feasible": feas_now,
            "feasible_like": feas_like, "gating_changed": spec_old is not None,
            "viol": spec.feasible(m_new)[1]}


def _diagnosis_for(res, row):
    """`era-mismatch` with the verbatim deltas when the row did not reproduce.

    The detail string keeps the numbers themselves rather than a verdict about
    them (the store's context-attrition rule): a later reader must be able to
    see WHICH metric moved and by how much without re-running anything."""
    if not res["stale"]:
        return None
    gaps = ",".join(era_gaps(row)) or "none"
    detail = "; ".join(
        f"{k} {res['old'].get(k):+.3f} -> {res['metrics'].get(k):+.3f} "
        f"(d={res['deltas'][k]:+.3f})" for k in res["stale"])
    if res.get("incomparable"):
        detail += ("; not compared (different quantity pre-nfrs-v1): "
                   + ",".join(res["incomparable"]))
    f = res.get("fence")
    if f is None:
        detail += "; old-geometry replay fence NOT RUN (attribution unverified)"
    elif not f.get("ok"):
        detail += ("; old-geometry replay FENCE FAILED "
                   + (f.get("reason") or
                      json.dumps({k: round(v, 3) for k, v in f["deltas"].items()}))
                   + " -- delta NOT attributable to the era alone")
    else:
        detail += ("; old-geometry replay fence PASS "
                   + json.dumps({k: round(v, 3) for k, v in f["deltas"].items()})
                   + " -- the stored numbers reproduce, so the delta is the era")
    flip = ""
    if bool(row.get("feasible")) != bool(res["feasible_like"]):
        flip = (f"; FEASIBILITY FLIP (like-for-like gating) "
                f"{bool(row.get('feasible'))} -> {bool(res['feasible_like'])}")
    if res.get("gating_changed") and bool(res["feasible_like"]) != bool(res["feasible"]):
        flip += (f"; separately, today's gating alone moves it to "
                 f"{bool(res['feasible'])} (tier-1 row judged under WP-D1 NF gating)")
    return ds.diagnosis(
        "era-mismatch",
        f"pre-era axes [{gaps}] re-measured under {ERA_TAG}: {detail}{flip}",
        "relabel_era.py")


def append_result(row, spec, res):
    """Append the new-era L2 row (+ its op row) through the legal paths.

    `repeat_probe=True` is required and is the point: the (wl_hash, spec) key
    already exists, and `append_l2` refuses a duplicate key without it. That is
    not a loophole -- datastore's own contract names re-labeling as the reason
    the flag exists ('a re-label is a new row (repeat-probe)')."""
    old_recipe = (row.get("zoaf_cfg") or {}).get("recipe", "?")
    cfg = S._zoaf_cfg(0, 0, 0, 0, old_recipe + RECIPE_SUFFIX,
                      inductor_q=INDUCTOR_Q, spec=spec)
    prov = dict(row.get("provenance") or {},
                relabel="era", relabel_of=row.get("ts"),
                relabel_of_git_sha=row.get("git_sha"),
                era=ERA_TAG, era_gaps=era_gaps(row),
                era_fingerprint=era_fingerprint())
    if res.get("noise_budget"):
        prov["noise_budget"] = res["noise_budget"]
    l2 = ds.row_l2(spec, res["metrics"], res["feasible"], 0,
                   best_params=res["params"], topo=res["topo"],
                   wl_hash=row.get("wl_hash"), provenance=prov, zoaf_cfg=cfg,
                   diagnosis=_diagnosis_for(res, row))
    status, _ = ds.append_l2(l2, repeat_probe=True)
    n_op = 0
    if status == "appended" and res.get("op") and res["op"].get("devices"):
        # stage="label": a converged, quoted point -- the population
        # critic_gnn.load_op_index selects (it filters stage in {label, final}).
        sink = S.OpSink(row.get("wl_hash"), spec, harness=S._op_harness(cfg),
                        provenance=prov, repeat_probe=True)
        sink.add(res["op"], params=res["params"], metrics=res["metrics"],
                 stage="label", noise_budget=res.get("noise_budget"))
        n_op = sink.flush()
    return status, n_op


# ------------------------------------------------------------------------ CLI
def _audit(rows, total, dup, skipped):
    by_spec, by_gap, n_feas = {}, {}, 0
    for r in rows:
        by_spec[r.get("spec")] = by_spec.get(r.get("spec"), 0) + 1
        n_feas += int(bool(r.get("feasible")))
        for g in era_gaps(r):
            by_gap[g] = by_gap.get(g, 0) + 1
    print(f"pre-era L2 rows: {total}   still to do: {len(rows)}   "
          f"({dup} duplicate points, {skipped} already re-labeled in {ERA_TAG})")
    print(f"  feasible among them: {n_feas}")
    print("  by spec:")
    for k, v in sorted(by_spec.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<16} {v}")
    print("  by missing cutover (a row can miss several; * = selection axis):")
    for k, v in sorted(by_gap.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<16} {v}{'  *' if k in MEASUREMENT_AXES else ''}")
    print("  current era fingerprint:")
    for k, v in sorted(era_fingerprint().items()):
        print(f"    {k:<16} {v}")


def main():
    ap = argparse.ArgumentParser(
        description="re-label stored designs under the current harness era "
                    "(plans2/15-ENGINEER-PROPOSAL section 5.1)")
    ap.add_argument("--audit", action="store_true",
                    help="census of what is stale, by spec and by cutover")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the exact top-K work plan; simulate nothing")
    ap.add_argument("--run", action="store_true", help="re-label and append")
    ap.add_argument("--limit", type=int, default=10, metavar="K",
                    help="top-K rows to re-label (default 10)")
    ap.add_argument("--spec", help="restrict to one spec name")
    ap.add_argument("--feasible-only", action="store_true",
                    help="only rows the program has quoted as feasible")
    ap.add_argument("--include-current", action="store_true",
                    help="also consider rows that are already current-era")
    ap.add_argument("--no-noise-budget", action="store_true",
                    help="skip the per-element noise budget (one call/row less)")
    ap.add_argument("--no-fence", action="store_true",
                    help="skip the old-geometry replay fence -- saves ~0.1 s per "
                         "design and gives up the era attribution with it")
    ap.add_argument("--redo", action="store_true",
                    help="also re-label points that already have a row in this "
                         "era (off by default: the harness has not moved, so the "
                         "numbers would not either)")
    ap.add_argument("--out", metavar="JSON", help="write per-row results here")
    a = ap.parse_args()

    rows, total, dup, skipped = candidates(a.spec, a.include_current,
                                           a.feasible_only, a.redo)
    if a.audit or not (a.run or a.dry_run):
        _audit(rows, total, dup, skipped)
        return 0

    todo = rows[:a.limit] if a.limit else rows
    print(f"selected {len(todo)} of {len(rows)} re-labelable rows "
          f"(era -> {ERA_TAG})\n")
    if a.dry_run:
        print(f"{'wl_hash':<14}{'spec':<14}{'feas':>5}{'minmarg':>9}"
              f"{'NF':>8}{'S21':>8}{'Idd':>7}  missing-cutovers")
        for r in todo:
            m, mm = _achieved(r), _min_margin(r)
            print(f"{(r.get('wl_hash') or '')[:12]:<14}{r.get('spec'):<14}"
                  f"{('yes' if r.get('feasible') else 'no'):>5}"
                  f"{(mm if mm is not None else float('nan')):>9.3f}"
                  f"{(m.get('nf_db') or float('nan')):>8.2f}"
                  f"{(m.get('s21_db') or float('nan')):>8.2f}"
                  f"{(m.get('idd_ma') or float('nan')):>7.2f}"
                  f"  {','.join(era_gaps(r))}")
        print("\n(dry run: nothing simulated, nothing appended)")
        return 0

    print(f"{'wl_hash':<14}{'spec':<12}{'dNF':>8}{'dS21':>8}{'dS11':>8}"
          f"{'dIdd%':>8}{'s':>6}  verdict")
    n_ok = n_stale = n_flip = n_gateflip = n_fail = n_op_total = n_fence_bad = 0
    results, secs = [], []
    t0 = time.time()
    for r in todo:
        try:
            spec = S._spec_for_sizing(r.get("spec"))
            spec_old = old_domain_spec(r)
        except Exception as e:
            print(f"{(r.get('wl_hash') or '')[:12]:<14}{r.get('spec'):<12}"
                  f"  spec load failed: {e}")
            n_fail += 1
            continue
        res = relabel_one(r, spec, keep_noise_budget=not a.no_noise_budget,
                          spec_old=spec_old, fence=not a.no_fence)
        if res["status"] != "ok":
            n_fail += 1
            print(f"{(r.get('wl_hash') or '')[:12]:<14}{r.get('spec'):<12}"
                  f"  {res['status'].upper()}")
            continue
        status, n_op = append_result(r, spec, res)
        n_op_total += n_op
        secs.append(res["secs"])
        was = bool(r.get("feasible"))
        flip = was != bool(res["feasible_like"])          # the ERA's doing
        gateflip = bool(res["feasible_like"]) != bool(res["feasible"])  # WP-D1's
        n_ok += 1
        n_stale += int(bool(res["stale"]))
        n_flip += int(flip)
        n_gateflip += int(gateflip)
        d = res["deltas"]
        old_idd = res["old"].get("idd_ma")
        didd_pct = (100.0 * d["idd_ma"] / old_idd
                    if "idd_ma" in d and old_idd else float("nan"))
        s11k = "s11_max_db" if "s11_max_db" in d else "s11_db"
        verdict = ("STALE:" + ",".join(res["stale"])) if res["stale"] else "reproduces"
        if res.get("fence") is not None and not res["fence"].get("ok"):
            n_fence_bad += 1
            verdict += "  [FENCE FAILED -- not era-attributable]"
        if flip:
            verdict += f"  ERA-FLIP {was}->{bool(res['feasible_like'])}"
        if gateflip:
            verdict += f"  gating->{bool(res['feasible'])}"
        print(f"{(r.get('wl_hash') or '')[:12]:<14}{r.get('spec'):<12}"
              f"{d.get('nf_db', float('nan')):>8.3f}"
              f"{d.get('s21_db', float('nan')):>8.3f}"
              f"{d.get(s11k, float('nan')):>8.3f}"
              f"{didd_pct:>8.2f}{res['secs']:>6.1f}  {verdict}", flush=True)
        results.append({"wl_hash": r.get("wl_hash"), "spec": r.get("spec"),
                        "era_gaps": era_gaps(r), "old": res["old"],
                        "new": res["metrics"], "deltas": d,
                        "stale": res["stale"],
                        "incomparable": res["incomparable"],
                        "feasible_old": was,
                        "feasible_new_like_for_like": bool(res["feasible_like"]),
                        "feasible_new": bool(res["feasible"]),
                        "viol_new": res.get("viol"), "append": status,
                        "fence": res.get("fence"),
                        "secs": res["secs"], "n_op_rows": n_op})

    wall = time.time() - t0
    print(f"\nre-labeled {n_ok}, era-stale {n_stale}, ERA feasibility flips "
          f"{n_flip} (like-for-like gating), further flips from WP-D1 NF gating "
          f"{n_gateflip}, failed {n_fail}; +{n_op_total} op rows; {wall:.0f}s "
          f"wall ({(wall / n_ok if n_ok else float('nan')):.1f}s/design)")
    if not a.no_fence and n_ok:
        fd = [abs(v) for r in results if r.get("fence")
              for v in (r["fence"].get("deltas") or {}).values()]
        worst = f"  (worst |delta| {max(fd):.4f} dB)" if fd else ""
        tail = (" -- the stored numbers reproduce, so the deltas above ARE the era"
                if not n_fence_bad else
                f" -- {n_fence_bad} FAILED, those deltas are not era-attributable")
        print(f"old-geometry replay fence: {n_ok - n_fence_bad}/{n_ok} PASS"
              + worst + tail)
    if secs:
        secs_sorted = sorted(secs)
        print(f"eval-only seconds: min {secs_sorted[0]:.2f}  "
              f"median {secs_sorted[len(secs_sorted) // 2]:.2f}  "
              f"max {secs_sorted[-1]:.2f}")
    for name in COMPARE:
        ds_ = sorted(r["deltas"][name] for r in results if name in r["deltas"])
        if ds_:
            n = len(ds_)
            print(f"  d{name:<12} n={n:<4} min {ds_[0]:+.3f}  "
                  f"median {ds_[n // 2]:+.3f}  max {ds_[-1]:+.3f}  "
                  f"mean {sum(ds_) / n:+.3f}")
    if a.out and results:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(results, fh, indent=1, default=str)
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
