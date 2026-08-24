#!/usr/bin/env python3
"""E-13a aggregation + parity + correctness recompute. Read-only over result JSONs.
Does NOT trust `solved`/`evals_spent` flags -- recomputes from raw metrics."""
import json, glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
E13A = os.path.join(HERE, "data", "e13", "a_results")
P3   = os.path.join(HERE, "data", "e12", "p3_results")

PAIRS = [("GN78","b"),("G13","c2"),("H2","b"),("G1pp","c2"),("G2pp","c2")]
SEEDS = [1,2,3]
B_EXPECT = 600


def best_s2(j):
    """Best (min) stage-2 objective across survivors; None if no sized survivor."""
    vals = []
    for s in (j.get("survivors") or []):
        st = s.get("stage2") if isinstance(s, dict) else None
        if st and st.get("best_objective") is not None:
            vals.append(st["best_objective"])
    return min(vals) if vals else None


def recompute_feasible(ext, sm):
    """Recompute spec feasibility from raw solve_metrics against frozen ext spec.
    ext: {metric: {max|min: val, status}}; sm: {metric: value}.
    Returns (feasible_bool, detail_str)."""
    if not ext or not sm:
        return None, "no ext/solve_metrics"
    ok = True
    parts = []
    for metric, bound in ext.items():
        v = sm.get(metric)
        if v is None:
            ok = False; parts.append(f"{metric}=MISSING"); continue
        if "max" in bound:
            good = v <= bound["max"]; parts.append(f"{metric}={v:.4f}<= {bound['max']}?{good}")
        elif "min" in bound:
            good = v >= bound["min"]; parts.append(f"{metric}={v:.4f}>= {bound['min']}?{good}")
        else:
            good = False; parts.append(f"{metric}=?bound?")
        ok = ok and good
    return ok, "; ".join(parts)


def load_cell(goal, arm, m, seed):
    f = os.path.join(E13A, f"cell_{goal}_{arm}_m{m}_s{seed}.json")
    if not os.path.exists(f):
        return None, f
    return json.load(open(f)), f


def main():
    print("="*72)
    print("E-13a AGGREGATION / PARITY / CORRECTNESS")
    print("="*72)

    # ---- Parity + correctness over all 30 E-13a cells ----
    parity_fail = []
    correctness = {}  # (goal,arm,m,seed) -> (recomputed_feasible, flag_solved, detail)
    missing = []
    for goal, arm in PAIRS:
        for m in (1, 2):
            for seed in SEEDS:
                j, f = load_cell(goal, arm, m, seed)
                if j is None:
                    missing.append(os.path.basename(f)); continue
                es = j.get("evals_spent")
                if es != B_EXPECT:
                    parity_fail.append((os.path.basename(f), es))
                feas, detail = recompute_feasible(j.get("ext"), j.get("solve_metrics"))
                correctness[(goal,arm,m,seed)] = (feas, j.get("solved"), detail)

    print(f"\n[PARITY] cells checked={len(correctness)}  missing={len(missing)}")
    if missing:
        print("  MISSING:", missing)
    if parity_fail:
        print("  OFF-PARITY (evals_spent != 600) -> VOID+RERUN:")
        for name, es in parity_fail:
            print(f"    {name}: evals_spent={es}")
    else:
        print("  all cells evals_spent == 600  [PASS]")

    print("\n[CORRECTNESS] recomputed feasibility vs `solved` flag:")
    mism = 0
    for key, (feas, flag, detail) in sorted(correctness.items()):
        agree = (bool(feas) == bool(flag))
        if not agree:
            mism += 1
            print(f"  MISMATCH {key}: recomputed={feas} flag={flag} | {detail}")
    print(f"  mismatches={mism} (0 = flags trustworthy; solves below use RECOMPUTED)")

    # ---- Per-goal aggregation table: best stage-2 obj at m=1,2,4 ----
    print("\n" + "="*72)
    print("PER-GOAL BEST STAGE-2 OBJECTIVE  (min across seeds; <1.0=feasible)")
    print("="*72)
    hdr = f"{'goal':6} {'arm':4} | {'m=1':>10} {'m=2':>10} {'m=4(bank)':>11} | solve?"
    print(hdr); print("-"*len(hdr))

    solves = []  # (goal,arm,m,seed, spice_min_to_solve, evals_to_solve, nf/metric)
    for goal, arm in PAIRS:
        row_best = {}
        for m in (1, 2):
            best = None
            for seed in SEEDS:
                j, _ = load_cell(goal, arm, m, seed)
                if j is None: continue
                b = best_s2(j)
                if b is not None and (best is None or b < best):
                    best = b
                # collect recomputed solves
                feas, _ = recompute_feasible(j.get("ext"), j.get("solve_metrics"))
                if feas:
                    solves.append((goal,arm,m,seed,
                                   j.get("spice_min_to_solve"),
                                   j.get("evals_to_solve"),
                                   j.get("solve_metrics")))
            row_best[m] = best
        # banked m=4
        b4 = None
        for f in glob.glob(f"{P3}/cell_{goal}_{arm}_*.json"):
            j = json.load(open(f))
            b = best_s2(j)
            if b is not None and (b4 is None or b < b4):
                b4 = b
        def fmt(x): return f"{x:.5f}" if isinstance(x,(int,float)) else "  --  "
        anysolve = any(s[0]==goal and s[1]==arm for s in solves)
        print(f"{goal:6} {arm:4} | {fmt(row_best.get(1)):>10} {fmt(row_best.get(2)):>10} {fmt(b4):>11} | {'YES' if anysolve else 'no'}")

    # ---- Solves detail ----
    print("\n" + "="*72)
    print("RECOMPUTED SOLVES (feasible against frozen ext spec)")
    print("="*72)
    if not solves:
        print("  NONE")
    else:
        for goal,arm,m,seed,spice,evals,sm in sorted(solves):
            print(f"  {goal} {arm} m={m} s{seed}: spice_min_to_solve={spice} "
                  f"evals_to_solve={evals}")
            print(f"      solve_metrics={json.dumps(sm)}")

    # ---- SPICE minutes total ----
    print("\n[SPICE-MINUTES] total across the 30 E-13a cells:")
    tot = 0.0
    for goal, arm in PAIRS:
        for m in (1,2):
            for seed in SEEDS:
                j,_ = load_cell(goal,arm,m,seed)
                if j: tot += j.get("spice_min_total", 0.0) or 0.0
    print(f"  {tot:.2f} SPICE-min")


if __name__ == "__main__":
    main()
