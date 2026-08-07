"""WP-LOOP — Stage-3 self-improvement cadence + tripwires (plans2/04-SELF-IMPROVE).

Stages 0-2 built every moving part (store, campaign, critic, finetune, search);
Stage 3 is the *cadence* that runs them as three feedback loops sharing one store,
plus the tripwires that keep the loops from eating each other. This module is the
governance layer: the five tripwire monitors (numbers, not vibes), the headline
curve (SPICE-minutes per feasible novel design), loop-iteration state, and the
adopt-only-if-better gate. The heavy actions (label / retrain critic / expert-
iterate generator / re-rerank) are the existing tools; `--iterate` sequences them.

    python lna/loop.py --status                 # store, versions, curve, tripwires
    python lna/loop.py --tripwires [--sample DIR]  # the 5 monitors + responses
    python lna/loop.py --curve                  # SPICE-min per feasible-novel design
    python lna/loop.py --baseline               # pin iteration-0 baselines (once)

One FINDINGS entry per loop iteration; reverted versions are results too. Exit:
two consecutive iterations with the curve improving and all tripwires quiet.
"""
import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds  # noqa: E402

STATE = os.path.join(HERE, "data", "loop_state.json")
SEC_PER_SIM = 1.0                    # ~1 s/ngspice eval (extract.py)
# tripwire thresholds (04-SELF-IMPROVE §4)
NDL_DROP = 0.20                      # trip if NDL falls > 20% vs pre-loop
FAM_DROP = 0.50                      # trip if distinct families < 50% pre-loop
SIGMA_DRIFT = 2.0                    # trip if repeat-probe sigma drifts > 2x
FEAS_RATE_MAX = 0.60                 # trip if labeled feasible/near-feas rate > 60%


# ------------------------------------------------------------------ state
def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    return {"iterations": [], "baseline": None}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(st, fh, indent=2)


# ------------------------------------------------------------------ metrics
def _near_feasible(r):
    mg = r.get("margins") or {}
    ms = [(mg.get(k) or {}).get("margin") for k in ("s11_db", "s21_db", "idd_ma")]
    return all(m is not None and m > -1.0 for m in ms)


def _is_novel(r):
    """A real *generated* token topology (not a hand reference deck) whose wl_hash
    is not a corpus circuit -- i.e. a design the pipeline discovered itself."""
    from novelty import corpus_reference
    ch, _ = corpus_reference()
    toks = (r.get("graph") or {}).get("tokens")
    return bool(toks and r.get("wl_hash") and r["wl_hash"] not in ch)


def spice_curve():
    """SPICE-minutes per feasible *novel* design over the whole store (iteration-0
    aggregate). Marginal per-iteration is computed from loop-iteration provenance
    once iterations run."""
    l2 = ds.load("topo_labels")
    sims = sum((r.get("n_evals") or 0) for r in l2)
    spice_min = sims * SEC_PER_SIM / 60.0
    feasible = [r for r in l2 if r.get("feasible")]
    feas_novel = [r for r in feasible if _is_novel(r)]
    n = len(feas_novel)
    per = spice_min / n if n else float("inf")
    return {"spice_minutes": round(spice_min, 1), "sims": sims,
            "feasible": len(feasible), "feasible_novel": n,
            "spice_min_per_feasible_novel": round(per, 1) if n else None}


def _sigma_s21():
    from collections import defaultdict
    by = defaultdict(list)
    for r in ds.load("topo_labels"):
        m = r.get("metrics") or {}
        if m.get("s21_db") is not None:
            by[(r.get("wl_hash"), r.get("spec"))].append(m["s21_db"])
    s = [statistics.pstdev(v) for v in by.values() if len(v) >= 2]
    return (sum(s) / len(s)) if s else None


def sample_stats(sample_dir, spec_name="wifi24"):
    """Frozen NDL@256 + distinct WL-families for a generation dir: novel (not a
    corpus circuit), spec-L0-passing, distinct-by-WL -- the same protocol as
    FINDINGS §5 so the tripwire baseline matches the reported NDL."""
    import glob
    from topology import Topology, parse_arrow_file
    from novelty import wl_features, corpus_reference, wl_cosine
    from spec import Spec
    spec = Spec.load(spec_name)
    ch, _ = corpus_reference()
    hashes, feats = set(), []
    for f in sorted(glob.glob(os.path.join(sample_dir, "seq*.txt")))[:256]:
        try:
            topo = Topology(parse_arrow_file(f))
        except Exception:
            continue
        if not spec.structural_screen(topo)[0]:
            continue
        h, ft = wl_features(topo)
        if h not in ch and h not in hashes:
            hashes.add(h)
            feats.append(ft)
    # distinct families = single-linkage clusters at cosine>=0.9 among novel hashes
    fam = 0
    seen = [False] * len(feats)
    for i in range(len(feats)):
        if seen[i]:
            continue
        fam += 1
        for j in range(i + 1, len(feats)):
            if not seen[j] and wl_cosine(feats[i], feats[j]) >= 0.9:
                seen[j] = True
    return {"ndl": len(hashes), "families": fam}


# ------------------------------------------------------------------ tripwires
def tripwires(sample_dir=None):
    st = load_state()
    base = st.get("baseline") or {}
    rows = []

    # 5. labeled feasible/near-feasible rate (margins compressing)
    l2 = [r for r in ds.load("topo_labels") if r.get("metrics")]
    nf_rate = sum(_near_feasible(r) for r in l2) / max(len(l2), 1)
    rows.append(("feasible-rate", f"{nf_rate:.2f}", nf_rate > FEAS_RATE_MAX,
                 "add hard negatives (stratum-M mutations of winners + random screened)"))

    # 4. repeat-probe sigma drift
    sig = _sigma_s21()
    base_sig = base.get("sigma")
    trip_sig = (sig is not None and base_sig and sig > SIGMA_DRIFT * base_sig)
    rows.append(("sigma-drift", f"{sig:.3f}" if sig else "n/a", trip_sig,
                 "stop labeling; re-baseline the harness (ngspice/env change?)"))

    # 1+2. NDL / family collapse on the latest adopted generator sample
    if sample_dir:
        s = sample_stats(sample_dir)
        b_ndl, b_fam = base.get("ndl"), base.get("families")
        trip_ndl = bool(b_ndl and s["ndl"] < (1 - NDL_DROP) * b_ndl)
        trip_fam = bool(b_fam and s["families"] < FAM_DROP * b_fam)
        rows.append(("ndl@256", f"{s['ndl']} (base {b_ndl})", trip_ndl,
                     "revert checkpoint; raise replay %; halve winner oversampling"))
        rows.append(("wl-families", f"{s['families']} (base {b_fam})", trip_fam,
                     "same as NDL -- mode collapse showing early"))

    # 3. critic holdout regression is enforced by adopt-only-if-better (§1), noted
    print(f"{'tripwire':<14} {'value':<20} {'state':<8} response")
    any_trip = False
    for name, val, trip, resp in rows:
        any_trip = any_trip or trip
        print(f"{name:<14} {val:<20} {'TRIPPED' if trip else 'ok':<8} "
              f"{resp if trip else ''}")
    print(f"\n{'[!] ONE OR MORE TRIPPED' if any_trip else '[ok] all tripwires quiet'}"
          "  (critic-holdout tripwire = adopt-only-if-better, automatic in loop A)")
    return not any_trip


# ------------------------------------------------------------------ CLI
def cmd_baseline():
    """Pin iteration-0 baselines (the pre-loop reference the tripwires compare to):
    P5 generator NDL/families + repeat-probe sigma."""
    st = load_state()
    p5 = os.path.join(HERE, "out", "ft_p5_nb_s1337")
    s = sample_stats(p5) if os.path.exists(p5) else {"ndl": None, "families": None}
    st["baseline"] = {"ndl": s["ndl"], "families": s["families"],
                      "sigma": _sigma_s21(), "curve": spice_curve()}
    save_state(st)
    print("iteration-0 baseline pinned:", json.dumps(st["baseline"], indent=2))
    return 0


def cmd_status():
    st = load_state()
    print("=== Stage-3 loop status ===")
    print("iterations run:", len(st.get("iterations", [])))
    ds._summary()
    print("\nheadline curve:", json.dumps(spice_curve(), indent=2))
    if st.get("baseline"):
        print("\niteration-0 baseline:", json.dumps(st["baseline"]))
    print("\ntripwires:")
    tripwires(sample_dir=os.path.join(HERE, "out", "ft_p5_nb_s1337"))
    return 0


CADENCE = """cadence for one loop turn (04-SELF-IMPROVE; each is an existing tool):
  A  label     python lna/campaign.py --night [--gen-glob <new P5 dir>]   # + acquisition picks (uncertainty/disagreement) for half the quota
  A  critic    <analoggenie py> lna/critic.py --eval  &  critic_gnn.py --eval   # retrain; adopt-only-if-better on the family holdout
  B  generator python lna/templates.py --emit-winners lna/out/winners_train.json ; <wsl gpu> lna/finetune.py --arm p5 --do both --winners --n 256
  C  rerank    <analoggenie py> lna/search.py --rerank   # the curve's next point
  gate         python lna/loop.py --tripwires --sample <new gen dir>   # must be quiet"""


def cmd_iterate(note=""):
    """Record a loop iteration: gate on tripwires, snapshot the curve + trend, and
    print the cadence. The heavy steps are the existing tools; this is the
    governance record + the tripwire gate (04-SELF-IMPROVE §5)."""
    from datetime import date
    st = load_state()
    quiet = tripwires(sample_dir=os.path.join(HERE, "out", "ft_p5_nb_s1337"))
    curve = spice_curve()
    prev = (st["iterations"][-1]["curve"] if st["iterations"]
            else (st.get("baseline") or {}).get("curve", {}))
    p = prev.get("spice_min_per_feasible_novel")
    c = curve.get("spice_min_per_feasible_novel")
    trend = ("n/a" if (p is None or c is None)
             else f"{p} -> {c} SPICE-min/design ({'IMPROVING' if c < p else 'worse' if c > p else 'flat'})")
    st["iterations"].append({"n": len(st["iterations"]) + 1, "date": date.today().isoformat(),
                             "curve": curve, "tripwires_quiet": quiet, "note": note})
    save_state(st)
    print(f"\n=== loop iteration {len(st['iterations'])} recorded ===")
    print(f"headline curve: {trend}")
    print(f"tripwires: {'quiet' if quiet else 'TRIPPED -- apply the response above before continuing'}")
    print(f"feasible-novel designs so far: {curve['feasible_novel']}")
    print(f"\n{CADENCE}")
    print("\nexit criterion: two consecutive iterations with the curve improving "
          "and all tripwires quiet.")
    return 0 if quiet else 1


def main():
    ap = argparse.ArgumentParser(description="Stage-3 self-improvement loop")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--tripwires", action="store_true")
    ap.add_argument("--curve", action="store_true")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--iterate", action="store_true",
                    help="record a loop iteration + gate on tripwires + print cadence")
    ap.add_argument("--note", default="", help="note for the iteration record")
    ap.add_argument("--sample", help="generation dir for the NDL/family tripwires")
    args = ap.parse_args()
    if args.baseline:
        return cmd_baseline()
    if args.iterate:
        return cmd_iterate(note=args.note)
    if args.curve:
        print(json.dumps(spice_curve(), indent=2))
        return 0
    if args.tripwires:
        return 0 if tripwires(sample_dir=args.sample) else 1
    if args.status:
        return cmd_status()
    ap.error("give --status / --tripwires / --curve / --baseline")


if __name__ == "__main__":
    sys.exit(main())
