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


def _split(data, spec_name):
    """train = non-generated (corpus+templates+refs); the generated rows split into
    old (P1/P2 arms) vs p5 by token_file -- ranked by the SAME critic so we can see
    whether the memorization-broken P5 distribution is more critic-rankable. The
    critic never trains on any generated row (either pool is out-of-sample)."""
    gen = [d for d in data if d["arm"].startswith("campaign-G")
           and d["spec"] == spec_name]
    train = [d for d in data if not d["arm"].startswith("campaign-G")
             and d["spec"] == spec_name]

    def tf(d):
        return (d["row"].get("provenance") or {}).get("token_file", "")
    pools = {"old(P1/P2)": [d for d in gen if "ft_p5" not in tf(d)],
             "p5": [d for d in gen if "ft_p5" in tf(d)]}
    return train, {k: v for k, v in pools.items() if v}


def _near_feasible(y):
    """all margins > -1 scale unit (03-SEARCH's 'feasible-or-near-feasible')."""
    return bool((np.asarray(y) > critic.NEAR_FEASIBLE).all())


def _knn_score(train, pool):
    pred = critic.pred_knn(train, pool)
    return critic._feasibility_score(pred), pred


def _gnn_models(train, sigma_norm, n=5):
    """Train the ensemble ONCE so every pool is ranked by the same critic."""
    import critic_gnn as G
    va_ids = {id(d) for d in train[::6]}
    va = [d for d in train if id(d) in va_ids]
    tr = [d for d in train if id(d) not in va_ids]
    return [G.train_one(tr, va, sigma_norm, seed=s) for s in range(n)]


def _gnn_score(models, pool):
    import critic_gnn as G
    P = np.stack([G.predict(m, pool) for m in models])
    mean, std = P.mean(0), P.std(0)
    return critic._feasibility_score(mean) - BETA * std.mean(1), mean


def _report_pool(name, pool, scorers, k_frac):
    Y = np.array([d["y"] for d in pool])
    near = np.array([_near_feasible(y) for y in Y])
    base = near.mean()
    kk = max(3, round(k_frac * len(pool)))
    rng = np.random.default_rng(0)
    for a, fn in scorers.items():
        score, pred = fn(pool)
        top = np.argsort(-score)[:kk]
        top_nf = int(near[top].sum())
        ctrl = float(np.median([near[rng.choice(len(pool), kk, replace=False)].sum()
                                for _ in range(1000)]))
        enrich = (top_nf / kk) / base if base > 0 else float("nan")
        rho = critic.spearman(Y[:, 1], pred[:, 1])
        print(f"{name:<11} {a:<4} {len(pool):>4} {base:>6.2f} {kk:>4} "
              f"{top_nf:>5} {ctrl:>6.1f} {enrich:>7.2f} {rho:>8.3f} "
              f"{'YES' if enrich >= 2.0 else 'no':>4}")


def rerank(spec_name="wifi24", arm="both", k_frac=0.2, snapshot=None):
    data = critic.load_dataset(snapshot=snapshot)
    sigma = critic._sigma_s21()
    train, pools = _split(data, spec_name)
    print(f"rung-1 rerank (offline, spec={spec_name}, snapshot={snapshot}): "
          f"train={len(train)} non-generated, sigma_S21={sigma:.3f}, "
          f"pools={ {k: len(v) for k, v in pools.items()} }")
    arms = ["knn", "gnn"] if arm == "both" else [arm]
    scorers = {}
    if "knn" in arms:
        scorers["knn"] = lambda pool: _knn_score(train, pool)
    if "gnn" in arms:
        try:
            models = _gnn_models(train, sigma / 12.0, n=5)
            scorers["gnn"] = lambda pool, m=models: _gnn_score(m, pool)
        except ImportError:
            print("(gnn skipped; run under the analoggenie python for torch)")
    print(f"\n{'pool':<11} {'arm':<4} {'n':>4} {'base':>6} {'topk':>4} "
          f"{'NF':>5} {'ctrl':>6} {'enrich':>7} {'rho_S21':>8} {'S1?':>4}")
    for name, pool in pools.items():
        if len(pool) >= 8:
            _report_pool(name, pool, scorers, k_frac)
        else:
            print(f"{name:<11} (pool too small: {len(pool)})")
    print("\nThe question: does the P5 (memorization-broken) pool rank better than "
          "old(P1/P2) under the same critic? Gate S1 = enrich@top-20% >= 2x. "
          "Near-feasible = all margins > -1; realized-vs-predicted rho feeds retrain.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--arm", choices=["knn", "gnn", "both"], default="both")
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--k-frac", type=float, default=0.2)
    ap.add_argument("--snapshot")
    args = ap.parse_args()
    if args.rerank:
        return rerank(args.spec, arm=args.arm, k_frac=args.k_frac,
                      snapshot=args.snapshot)
    ap.error("give --rerank")


if __name__ == "__main__":
    sys.exit(main())
