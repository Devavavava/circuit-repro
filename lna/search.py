"""WP-SEARCH rung-1 (plans2/03-SEARCH §1) — best-of-N rerank, controlled.

Rung 1 spends SPICE only where the critic says to: rank a generated pool, size
the top-k, and compare to sizing k *random* picks from the same pool at equal
budget. The yardstick is **feasible-or-near-feasible designs per equal sizing
budget** (03-SEARCH's fixed metric); Gate S1 wants the critic-picked set to hold
>= 2x the control's.

This runs the experiment **retrospectively on the already-sized generated pool**:
the campaign labeled 142 generated topologies, so their true margins are real
SPICE results (§4 rule 4 satisfied). The critic is trained ONLY on non-generated
rows (corpus + templates + references), so the pool is genuinely out-of-sample --
this is the source-shift scenario framed as a selection experiment, and it needs
no new compute. A live run (fresh generation, size only the top-k) is the
confirmatory follow-up; here we measure what the critic *would* have selected.

    "C:/Users/Devavrat/radioconda/envs/analoggenie/python.exe" lna/search.py --rerank
    python lna/search.py --rerank --arm knn      # baseline only (torch-free)
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import critic  # noqa: E402
import datastore as ds  # noqa: E402

BETA = 1.0                        # search consumes mean - beta*sigma (§4 rule 1)


def _pool_and_train(data, spec_name):
    """pool = generated (campaign-G) rows for this spec; train = everything else
    (corpus + templates + references) -- the critic never sees the pool."""
    pool = [d for d in data if d["arm"].startswith("campaign-G")
            and d["spec"] == spec_name]
    train = [d for d in data if not d["arm"].startswith("campaign-G")
             and d["spec"] == spec_name]
    return pool, train


def _near_feasible(y):
    """all margins > -1 scale unit (03-SEARCH's 'feasible-or-near-feasible')."""
    return bool((np.asarray(y) > critic.NEAR_FEASIBLE).all())


def _score_knn(train, pool):
    pred = critic.pred_knn(train, pool)
    return critic._feasibility_score(pred), pred


def _score_gnn(train, pool, sigma_norm):
    import critic_gnn as G
    va = train[::6]
    va_ids = {id(d) for d in va}
    tr = [d for d in train if id(d) not in va_ids]
    mean, std = G.ensemble_predict(tr, va, pool, sigma_norm, n=5)
    return critic._feasibility_score(mean) - BETA * std.mean(1), mean


def rerank(spec_name="wifi24", arm="both", k=30, snapshot=None):
    data = critic.load_dataset(snapshot=snapshot)
    sigma = critic._sigma_s21()
    pool, train = _pool_and_train(data, spec_name)
    Y = np.array([d["y"] for d in pool])
    near = np.array([_near_feasible(y) for y in Y])
    base = near.mean()
    s21 = Y[:, 1]
    print(f"rung-1 rerank (offline, spec={spec_name}, snapshot={snapshot}): "
          f"pool={len(pool)} generated, train={len(train)} non-generated, "
          f"sigma_S21={sigma:.3f}")
    print(f"pool base rate near-feasible: {near.sum()}/{len(pool)} = {base:.3f}; "
          f"true S21 margin range [{s21.min():.2f}, {s21.max():.2f}]")
    print(f"\n{'arm':<8} {'top-k NF':>9} {'ctrl NF':>9} {'enrich':>7} "
          f"{'top-k bestS21':>14} {'rho_S21':>8} {'S1?':>5}")

    arms = ["knn", "gnn"] if arm == "both" else [arm]
    rng = np.random.default_rng(0)
    for a in arms:
        if a == "knn":
            score, pred = _score_knn(train, pool)
        else:
            try:
                score, pred = _score_gnn(train, pool, sigma / 12.0)
            except ImportError:
                print(f"{a:<8}  (torch unavailable; run under analoggenie python)")
                continue
        order = np.argsort(-score)
        top = order[:k]
        top_nf = int(near[top].sum())
        # control: expected NF in k random + a seeded actual draw for concreteness
        ctrl_exp = base * k
        draws = [near[rng.choice(len(pool), k, replace=False)].sum()
                 for _ in range(1000)]
        ctrl_med = float(np.median(draws))
        enrich = (top_nf / k) / base if base > 0 else float("nan")
        rho = critic.spearman(Y[:, 1], pred[:, 1])
        best_s21_top = s21[top].max()
        s1 = enrich >= 2.0
        print(f"{a:<8} {top_nf:>9} {ctrl_med:>9.1f} {enrich:>7.2f} "
              f"{best_s21_top:>14.2f} {rho:>8.3f} {'YES' if s1 else 'no':>5}"
              f"   (ctrl E[NF]={ctrl_exp:.1f})")
    print(f"\nGate S1: critic-top-{k} holds >= 2x the control's near-feasible count."
          "\nNote: 0 fully-feasible in the generated pool (Gate G4 is the tapped "
          "reference, by hand), so 'near-feasible' (all margins > -1) is the "
          "achievable target; realized-vs-predicted rho feeds 02-CRITIC retrain.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--arm", choices=["knn", "gnn", "both"], default="both")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--size-top", type=int, default=30)
    ap.add_argument("--snapshot")
    args = ap.parse_args()
    if args.rerank:
        return rerank(args.spec, arm=args.arm, k=args.size_top,
                      snapshot=args.snapshot)
    ap.error("give --rerank")


if __name__ == "__main__":
    sys.exit(main())
