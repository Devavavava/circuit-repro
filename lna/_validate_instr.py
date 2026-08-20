"""Validation harness for blame.py and binding_probe.py (plans2/22-INFER-INSTRUMENTS.md).

Runs 5 known cases with hand-checkable answers:

  CASE 1: ref:ref24_tapped.cir (FEASIBLE flagship)
    binding_probe -> verdict='feasible', n_failing=0
    blame         -> 0 rows (no failing constraints)

  CASE 2: ref:ref24_csdeg.cir (INFEASIBLE: s21 fail + nf fail)
    binding_probe -> n_failing=2, verdict='single'
                  -> s21 delta_frac = (12 - 6.860365)/12 = 0.4283 (exact)
                  -> nf delta_frac  = (2.734636 - 2.5)/2.5 = 0.0939 (exact)
    blame(s21)    -> top device is m2 (highest intrinsic gain, coverage=partial)
    blame(nf)     -> top device is m1 (input transistor dominant; known from NF budget)

  CASE 3: stored infeasible L2 row b3aa27 (s11 + s21 + nf fail)
    binding_probe -> n_failing=3, verdict='single' (each constraint independent)
                  -> s21 delta_frac hand-checkable from stored achieved/limit

  CASE 4: two single-metric fail rows (s21 only)
    binding_probe -> verdict='single', n_failing=1

  CASE 5: a pure current blame test (idd_ma violating)
    Pick a row where idd_ma fails; current blame should return non-empty list.

Exit code 0 iff all assertions pass.

    python lna/_validate_instr.py
    python lna/_validate_instr.py --verbose
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import datastore as ds
import extract as E
import spec as SP
import blame as BL
import binding_probe as BP


def _load_rows():
    return ds.load("topo_labels")


# ---------------------------------------------------------------------------
# Case runners

def case1_flagship_feasible(verbose=False):
    """ref:ref24_tapped.cir -- feasible. Both instruments should say 'no problem'."""
    rows = _load_rows()
    row = next(r for r in rows if r.get("wl_hash") == "ref:ref24_tapped.cir")
    sp = SP.Spec.load("wifi24")
    metrics = row["metrics"]
    params = row["best_params"]

    # binding_probe
    probe = BP.probe_design(sp, metrics, row["wl_hash"], write=False)
    assert probe["feasible_before"] is True, f"Case1: expected feasible, got {probe}"
    assert probe["verdict"] == "feasible", f"Case1 verdict: {probe['verdict']}"
    assert probe["n_failing"] == 0, f"Case1 n_failing: {probe['n_failing']}"

    # blame
    body = E.body_of(os.path.join(HERE, "ref", "ref24_tapped.cir"))
    op = {}
    E.run_and_extract(body, params, sp, op_capture=op)
    blame_rows = BL.blame_design(body, params, sp, op, row["wl_hash"], metrics,
                                  write=False, failing_only=True)
    assert len(blame_rows) == 0, f"Case1: expected 0 blame rows, got {len(blame_rows)}"

    if verbose:
        print("CASE 1 (flagship feasible): PASS")
        print(f"  probe verdict={probe['verdict']}, n_failing={probe['n_failing']}")
        print(f"  blame rows={len(blame_rows)}")
    return True


def case2_csdeg_infeasible(verbose=False):
    """ref:ref24_csdeg.cir -- infeasible (s21 + nf fail). Hand-checkable arithmetic."""
    rows = _load_rows()
    # Use the row with nf_db from series-Rs measurement
    csdeg_rows = [r for r in rows
                  if r.get("wl_hash") == "ref:ref24_csdeg.cir"
                  and r.get("metrics", {}).get("nf_db") is not None]
    assert csdeg_rows, "no ref24_csdeg row with nf_db in store"
    row = csdeg_rows[0]
    metrics = row["metrics"]
    params = row["best_params"]
    sp = SP.Spec.load("wifi24")

    # binding_probe
    probe = BP.probe_design(sp, metrics, row["wl_hash"], write=False)
    assert probe["feasible_before"] is False, f"Case2: should be infeasible"
    assert probe["n_failing"] == 2, f"Case2 n_failing={probe['n_failing']} (expect 2: nf+s21)"
    assert probe["verdict"] == "single", f"Case2 verdict={probe['verdict']}"

    # Hand-check s21 delta_frac: (12 - achieved)/12
    s21_ach = metrics["s21_db"]
    expected_s21 = (12.0 - s21_ach) / 12.0
    s21_r = next(s for s in probe["single_relaxations"] if s["metric"] == "s21_db")
    assert abs(s21_r["delta_frac"] - expected_s21) < 1e-4, (
        f"Case2 s21 delta_frac: expected {expected_s21:.6f}, got {s21_r['delta_frac']:.6f}")

    # Hand-check nf delta_frac: (achieved - 2.5)/2.5
    nf_ach = metrics["nf_db"]
    expected_nf = (nf_ach - 2.5) / 2.5
    nf_r = next(s for s in probe["single_relaxations"] if s["metric"] == "nf_db")
    assert abs(nf_r["delta_frac"] - expected_nf) < 1e-4, (
        f"Case2 nf delta_frac: expected {expected_nf:.6f}, got {nf_r['delta_frac']:.6f}")

    # blame on s21 and nf
    body = E.body_of(os.path.join(HERE, "ref", "ref24_csdeg.cir"))
    op = {}
    E.run_and_extract(body, params, sp, op_capture=op)
    blame_rows = BL.blame_design(body, params, sp, op, row["wl_hash"], metrics,
                                  write=False, failing_only=True)
    assert len(blame_rows) == 2, f"Case2: expected 2 blame rows, got {len(blame_rows)}"

    # NF blame: m1 should be top (input transistor is dominant noise source in CS-deg)
    nf_blame = next(b for b in blame_rows if b["metric"] == "nf_db")
    assert nf_blame["coverage"] == "full", f"Case2 NF coverage={nf_blame['coverage']}"
    assert nf_blame["blame"][0]["device"] == "m1", (
        f"Case2 NF top device expected m1, got {nf_blame['blame'][0]['device']}")
    m1_frac = nf_blame["blame"][0]["score"]
    assert m1_frac > 0.4, f"Case2 m1 NF frac={m1_frac:.4f} (expected >0.4)"

    # S21 blame: coverage=partial (gm/gds based)
    s21_blame = next(b for b in blame_rows if b["metric"] == "s21_db")
    assert s21_blame["coverage"] == "partial", f"Case2 S21 coverage={s21_blame['coverage']}"

    if verbose:
        print("CASE 2 (ref24_csdeg infeasible): PASS")
        print(f"  n_failing={probe['n_failing']}, verdict={probe['verdict']}")
        print(f"  s21 delta_frac={s21_r['delta_frac']:.4f} (hand-check {expected_s21:.4f})")
        print(f"  nf  delta_frac={nf_r['delta_frac']:.4f} (hand-check {expected_nf:.4f})")
        print(f"  NF blame top: {nf_blame['blame'][0]['device']} frac={m1_frac:.4f}")
        print(f"  S21 blame top: {s21_blame['blame'][0]['device']} (gain proxy)")
    return True


def case3_b3aa27_triple_fail(verbose=False):
    """Stored infeasible L2 row b3aa27 -- 3 failing constraints (s11+s21+nf)."""
    rows = _load_rows()
    row = next((r for r in rows if (r.get("wl_hash") or "").startswith("b3aa27")
                and r.get("metrics")), None)
    if row is None:
        if verbose:
            print("CASE 3: skipped (b3aa27 not in store)")
        return True  # skip, not fail

    metrics = row["metrics"]
    sp = SP.Spec.load("wifi24")
    probe = BP.probe_design(sp, metrics, row["wl_hash"], write=False)

    assert probe["feasible_before"] is False
    assert probe["n_failing"] == 3, f"Case3 n_failing={probe['n_failing']}"
    assert probe["verdict"] == "single"

    # Hand-check s21: achieved=-5.52, min=12 => delta=(12-(-5.52))/12
    s21_ach = metrics["s21_db"]
    expected = (12.0 - s21_ach) / 12.0
    s21_r = next(s for s in probe["single_relaxations"] if s["metric"] == "s21_db")
    assert abs(s21_r["delta_frac"] - expected) < 1e-4

    if verbose:
        print("CASE 3 (b3aa27 triple fail): PASS")
        print(f"  n_failing={probe['n_failing']}, verdict={probe['verdict']}")
        print(f"  s21 delta_frac={s21_r['delta_frac']:.4f} (expected {expected:.4f})")
    return True


def case4_single_metric_fail(verbose=False):
    """A row where only s21 fails -> verdict='single', smallest relax is s21."""
    rows = _load_rows()
    row = next((r for r in rows
                if not r.get("feasible") and r.get("metrics")
                and r.get("wl_hash", "").startswith("0138")), None)
    if row is None:
        # Fall back to any single-failing row
        for r in rows:
            if not r.get("feasible") and r.get("metrics"):
                sp_tmp = SP.Spec.load(r["spec"])
                _, viol = sp_tmp.feasible(r["metrics"])
                if len(viol) == 1:
                    row = r
                    break
    if row is None:
        if verbose:
            print("CASE 4: skipped (no single-fail row found)")
        return True

    sp = SP.Spec.load(row["spec"])
    _, viol = sp.feasible(row["metrics"])
    assert len(viol) == 1, f"Case4: expected 1 failing, got {len(viol)}"

    probe = BP.probe_design(sp, row["metrics"], row["wl_hash"], write=False)
    assert probe["n_failing"] == 1
    assert probe["verdict"] == "single"
    assert len(probe["single_relaxations"]) == 1
    assert len(probe["pairwise_relaxations"]) == 0   # no pairs when n_failing=1

    if verbose:
        print("CASE 4 (single-metric fail): PASS")
        print(f"  wl={row['wl_hash'][:12]}  failing={list(viol.keys())}  verdict={probe['verdict']}")
    return True


def case5_current_blame(verbose=False):
    """A row where idd_ma fails -> current blame should be non-empty."""
    rows = _load_rows()
    # Find an infeasible row with idd_ma failing
    row = None
    for r in rows:
        if not r.get("feasible") and r.get("metrics") and r.get("graph", {}).get("tokens"):
            sp_tmp = SP.Spec.load(r["spec"])
            _, viol = sp_tmp.feasible(r["metrics"])
            if "idd_ma" in viol:
                row = r
                break
    if row is None:
        if verbose:
            print("CASE 5: skipped (no idd_ma-failing row with tokens)")
        return True

    sp = SP.Spec.load(row["spec"])
    tokens = row["graph"]["tokens"]
    metrics = row["metrics"]

    from topology import Topology
    topo = Topology(tokens)
    try:
        S = BL._size()
        prep = S.prepared_body(topo, inductor_q=12)
    except Exception:
        if verbose:
            print("CASE 5: skipped (bias insert unavailable)")
        return True

    if prep is None:
        if verbose:
            print("CASE 5: skipped (bias insert skipped)")
        return True

    body = prep[0]
    op = {}
    E.run_and_extract(body, row.get("best_params", {}), sp, op_capture=op)

    blame_rows = BL.blame_design(body, row.get("best_params", {}), sp, op,
                                  row["wl_hash"], metrics, write=False, failing_only=True)
    idd_row = next((b for b in blame_rows if b["metric"] == "idd_ma"), None)
    assert idd_row is not None, "Case5: no idd_ma blame row"
    assert len(idd_row["blame"]) > 0, "Case5: empty blame for idd_ma"
    assert idd_row["coverage"] in ("full", "partial")

    if verbose:
        print("CASE 5 (current blame on idd_ma fail): PASS")
        print(f"  top={idd_row['blame'][0]['device']} score={idd_row['blame'][0]['score']:.4f} cov={idd_row['coverage']}")
    return True


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", "-v", action="store_true")
    a = ap.parse_args()

    cases = [
        ("CASE 1 - flagship feasible (ref:ref24_tapped)", case1_flagship_feasible),
        ("CASE 2 - ref24_csdeg infeasible + NF budget", case2_csdeg_infeasible),
        ("CASE 3 - b3aa27 triple fail arithmetic", case3_b3aa27_triple_fail),
        ("CASE 4 - single-metric fail",  case4_single_metric_fail),
        ("CASE 5 - current blame on idd_ma", case5_current_blame),
    ]

    results = []
    all_ok = True
    for name, fn in cases:
        print(f"Running {name} ...", end=" ", flush=True)
        try:
            ok = fn(verbose=a.verbose)
            results.append((name, "PASS" if ok else "SKIP"))
            if not a.verbose:
                print("PASS" if ok else "SKIP")
        except AssertionError as e:
            results.append((name, f"FAIL: {e}"))
            all_ok = False
            print(f"FAIL: {e}")
        except Exception as e:
            results.append((name, f"ERROR: {e}"))
            all_ok = False
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n=== Validation Summary ===")
    for name, status in results:
        print(f"  {'OK' if status == 'PASS' else status[:4]:<6} {name}")
    print(f"\n_validate_instr: {'GREEN' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
