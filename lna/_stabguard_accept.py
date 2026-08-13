"""WP-STABGUARD acceptance (FINDINGS §38): the two known K<1 wifi24 cases,
re-run through the polish path with the stability guard OFF vs ON.

Cases (Session 4 / FINDINGS §13): `seq0009` -- curated sizing read K_min
0.352/0.242 (single-finger era); `seq0220` -- polish walked the curated point
K_min 4.08 -> 0.832 because stability was in no objective. Under the current
multi-finger harness both anchors are the stored `curated-v1+mf2-v1` rows;
polish runs from those points at its ORIGINAL default budget (80), guard off
vs on, identical in everything else (polish has no RNG, so the arms differ
only in the guard). Also: a fresh re-measurement of `seq0220`'s tier-2 claim
row, and a no-SPICE truth table of `_stab_ok`.

Usage:  python lna/_stabguard_accept.py
"""
import json
import os
import sys

LNA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LNA)

import size as S                    # noqa: E402
from topology import Topology       # noqa: E402

SPEC = "wifi24"
ANCHOR_RECIPE = "curated-v1+mf2-v1"
CASES = {"seq0009": "624fc609363db6f9", "seq0220": "396b90321529157a"}


def selftest():
    """_stab_ok truth table, no SPICE."""
    mk = lambda k: None if k is None else {"k_min": k}
    os.environ["LNA_STAB_GUARD"] = "1"
    assert S._stab_ok(mk(4.0), mk(0.8)) is False      # >=1 -> <1 : refused
    assert S._stab_ok(mk(4.0), mk(1.2)) is True       # stays stable: allowed
    assert S._stab_ok(mk(0.5), mk(0.4)) is True       # unstable incumbent: free
    assert S._stab_ok(mk(0.5), mk(1.2)) is True       # recovery: allowed
    assert S._stab_ok(mk(None), mk(0.4)) is True      # unmeasured: never blocks
    assert S._stab_ok(mk(4.0), mk(None)) is True
    assert S._stab_ok(None, mk(0.4)) is True
    os.environ["LNA_STAB_GUARD"] = "0"
    assert S._stab_ok(mk(4.0), mk(0.8)) is True       # hatch disables
    os.environ["LNA_STAB_GUARD"] = "1"
    print("selftest: _stab_ok truth table OK (8/8)")


def anchor_row(case):
    """Last store row for (case token_file, wifi24, curated-v1+mf2-v1)."""
    best = None
    with open(os.path.join(LNA, "data", "topo_labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (r.get("spec") == SPEC
                    and (r.get("zoaf_cfg") or {}).get("recipe") == ANCHOR_RECIPE
                    and case in str((r.get("provenance") or {}).get("token_file", ""))
                    and r.get("wl_hash") == CASES[case]):
                best = r
    return best


def fmt(m, feas):
    return (f"S11max={m['s11_max_db']:>8.3f}  S21={m['s21_db']:>7.3f}  "
            f"Idd={m['idd_ma']:>6.3f}  NF={m.get('nf_db'):>6.3f}  "
            f"K_min={m.get('k_min'):>8.4g}  {'FEAS' if feas else 'infeas'}")


def legacy_repro():
    """The historical failure surface: SINGLE-FINGER deck (pre-cutover, the
    harness Session 4 measured seq0220's polish walk 4.08 -> 0.832 on), from
    the single-finger `curated-v1` anchor. polish() builds its own deck via
    bias.insert_bias, so the legacy emission is injected by wrapping it with
    w_finger=None -- clearly a REPRODUCTION harness, not the current label
    domain. NF gating off (that era was tier-1)."""
    import bias
    spec = S._spec_for_sizing(SPEC)
    case, recipe = "seq0220", os.environ.get("STABG_LEGACY_ANCHOR", "polish-v1")
    row = None
    with open(os.path.join(LNA, "data", "topo_labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (r.get("spec") == SPEC and (r.get("zoaf_cfg") or {}).get("recipe") == recipe
                    and case in str((r.get("provenance") or {}).get("token_file", ""))
                    and r.get("wl_hash") == CASES[case]):
                row = r
    if row is None:
        print("legacy: no anchor row")
        return
    topo = Topology(row["graph"]["tokens"])
    prior = row["best_params"]
    orig = bias.insert_bias
    bias.insert_bias = lambda t, **kw: orig(t, **dict(kw, w_finger=None))
    os.environ["LNA_NF_GATE"] = "0"           # tier-1 era gating
    try:
        prep = S.prepared_body(topo, inductor_q=12)  # w_finger forced None by wrap
        body, _, _ = prep
        m0 = S.eval_metrics(body, prior, spec, nf_gated=False)
        print(f"\n== LEGACY single-finger repro: {case} anchor {recipe}, re-measured:")
        print(f"   S11max={m0['s11_max_db']:>8.3f}  S21={m0['s21_db']:>7.3f}  "
              f"Idd={m0['idd_ma']:>6.3f}  K_min={m0.get('k_min'):>8.4g}")
        for arm, env in (("guard-off", "0"), ("guard-on", "1")):
            os.environ["LNA_STAB_GUARD"] = env
            res = S.polish(topo, spec, prior, budget=80, inductor_q=12)
            os.environ["LNA_STAB_GUARD"] = "1"
            if not (res and res.get("metrics")):
                print(f"   polish {arm}: FAILED")
                continue
            g = res.get("stab_guard") or {}
            m = res["metrics"]
            print(f"   polish {arm:<10} S11max={m['s11_max_db']:>8.3f}  "
                  f"S21={m['s21_db']:>7.3f}  Idd={m['idd_ma']:>6.3f}  "
                  f"K_min={m.get('k_min'):>8.4g}  "
                  f"{'FEAS' if res['feasible'] else 'infeas'}  "
                  f"refused={g.get('n_refused')}")
    finally:
        bias.insert_bias = orig
        os.environ.pop("LNA_NF_GATE", None)


def main():
    selftest()
    spec = S._spec_for_sizing(SPEC)
    out = {}
    for case in CASES:
        r = anchor_row(case)
        if r is None:
            print(f"{case}: NO ANCHOR ROW -- abort")
            continue
        topo = Topology(r["graph"]["tokens"])
        prior = r["best_params"]
        # 1. fresh re-measure of the stored anchor (claim survival)
        prep = S.prepared_body(topo, inductor_q=12)
        if prep is None:
            print(f"{case}: bias skip -- abort")
            continue
        body, _, _ = prep
        m0 = S.eval_metrics(body, prior, spec, nf_gated=True)
        f0 = spec.feasible(m0)[0] if m0 else False
        print(f"\n== {case} (wl {r['wl_hash']}) anchor {ANCHOR_RECIPE}, re-measured:")
        print(f"   {fmt(m0, f0)}")
        # 2. polish A/B at the original default budget, guard off vs on
        arms = {}
        for arm, env in (("guard-off", "0"), ("guard-on", "1")):
            os.environ["LNA_STAB_GUARD"] = env
            res = S.polish(topo, spec, prior, budget=80, inductor_q=12)
            os.environ["LNA_STAB_GUARD"] = "1"
            if not (res and res.get("metrics")):
                print(f"   polish {arm}: FAILED")
                continue
            g = res.get("stab_guard") or {}
            print(f"   polish {arm:<10} {fmt(res['metrics'], res['feasible'])}  "
                  f"refused={g.get('n_refused')}")
            arms[arm] = res
        out[case] = dict(anchor=dict(metrics=m0, feasible=f0), arms={
            a: dict(metrics=res["metrics"], feasible=res["feasible"],
                    stab_guard=res.get("stab_guard"), n_evals=res["n_evals"])
            for a, res in arms.items()})
        # 3. if guard-off landed K<1, restart guard-on from there: flag demo
        off = arms.get("guard-off")
        if off and (off["metrics"].get("k_min") or 9e9) < 1.0:
            res = S.polish(topo, spec, off["best_params"], budget=20, inductor_q=12)
            g = (res or {}).get("stab_guard") or {}
            print(f"   restart guard-on from unstable landing: "
                  f"start_unstable={g.get('start_unstable')} "
                  f"start_k={g.get('start_k_min')} final_k={g.get('final_k_min')}")
            out[case]["restart"] = g
    legacy_repro()
    p = os.path.join(LNA, "out", "_stabguard_accept.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1, default=str)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
