"""x0_prior.py -- learned starting-sizing prior ("learned x0"), flag-gated.

Predicts a per-device NORMALISED starting vector x0 in [0,1]^d for a (topology,
achieved-spec target, pdk) from evaluated designs, to seed the sizer instead of
the dumb midpoint [0.5]^d / uniform CMA restart. DEFAULT OFF: nothing imports or
calls this unless `LNA_X0_PRIOR=1` (or an explicit arg) is set, so the sizer's
byte-identity is preserved (goldens prove it).

MODEL (justified small model, CPU ~seconds to train)
----------------------------------------------------
A per-KIND conditional MLP. Input is the fixed-length feature vector from
`x0_data.feature_vector` (graph summary + hindsight achieved-target + band + pdk,
dim = x0_data.FEATURE_DIM). Output is one value per sizer KIND (W,L,R,C,VB) in
[0,1] (sigmoid). At sizing time we look up each device's kind and read the
predicted per-kind x0, giving a full x0 in [0,1]^d for ANY topology WITHOUT a
per-topology output dimension.

Why per-kind and not the GNN critic (critic_gnn.py): the GNN is a natural
backbone and has per-device heads, but (a) it is NOT in the editor/sizer loop and
wiring it in is a large, byte-risky change; (b) the corpus that has recoverable
normalised targets is ~4k rows over 7 specs -- a per-device MPNN would overfit
and cost minutes/epoch on CPU; (c) the per-kind conditional prior already beats
the midpoint by construction (kind means differ from 0.5: L~0.66, R~0.41 in the
box corpus) and trains in seconds. A per-device refinement is left as future
work behind the same flag. If it never beats retrieval on the ladder it is not
adopted -- that is the whole point of the pre-registered A0/A1/A2 comparison.

The model is pure-numpy (no torch dependency for inference) so it loads with zero
import cost inside the sizer; training is also pure-numpy SGD. A .npz holds the
weights + normalisation stats + the feature/kind schema, so a stale schema is
detected rather than silently mis-applied.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.dirname(HERE)
for _p in (os.path.join(ROOT, "lna"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import x0_data as XD                 # noqa: E402

DEFAULT_MODEL = os.path.join(ROOT, "lna", "out", "x0_prior.npz")
ENV_FLAG = "LNA_X0_PRIOR"            # "1"/"on"/"retrieval" enables warm start
ENV_MODEL = "LNA_X0_PRIOR_MODEL"     # optional model-path override


def enabled():
    """True iff the learned-x0 warm start is switched on. DEFAULT OFF."""
    v = (os.environ.get(ENV_FLAG) or "").strip().lower()
    return v in ("1", "on", "true", "yes", "learned", "prior", "retrieval", "a1", "a2")


def mode():
    """'off' | 'learned' (A2) | 'retrieval' (A1). Controls which warm start runs."""
    v = (os.environ.get(ENV_FLAG) or "").strip().lower()
    if v in ("retrieval", "a1"):
        return "retrieval"
    if v in ("1", "on", "true", "yes", "learned", "prior", "a2"):
        return "learned"
    return "off"


# ----------------------------------------------------------------------------- model
class X0Prior:
    """One-hidden-layer MLP: feat -> per-kind x0 in [0,1]. Pure numpy."""

    def __init__(self, W1, b1, W2, b2, mu, sd, feat_dim, kinds):
        self.W1, self.b1, self.W2, self.b2 = W1, b1, W2, b2
        self.mu, self.sd = mu, sd
        self.feat_dim, self.kinds = feat_dim, list(kinds)

    def predict_perkind(self, feat):
        x = (np.asarray(feat, dtype=float) - self.mu) / self.sd
        h = np.tanh(x @ self.W1 + self.b1)
        o = h @ self.W2 + self.b2
        y = 1.0 / (1.0 + np.exp(-o))                     # sigmoid -> [0,1]
        return {k: float(y[i]) for i, k in enumerate(self.kinds)}

    def x0_for(self, graph, metrics, band_f0, pdk, sizable):
        """Full x0 in [0,1]^len(sizable), device order == list(sizable)."""
        if self.feat_dim != XD.FEATURE_DIM:
            raise ValueError("x0_prior: feature schema mismatch (retrain)")
        feat = XD.feature_vector(graph, metrics, band_f0, pdk)
        pk = self.predict_perkind(feat)
        return [pk.get(kind, 0.5) for kind in sizable.values()]

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez(path, W1=self.W1, b1=self.b1, W2=self.W2, b2=self.b2,
                 mu=self.mu, sd=self.sd, feat_dim=self.feat_dim,
                 kinds=np.array(self.kinds))

    @staticmethod
    def load(path=None):
        path = path or os.environ.get(ENV_MODEL) or DEFAULT_MODEL
        if not os.path.exists(path):
            return None
        d = np.load(path, allow_pickle=True)
        return X0Prior(d["W1"], d["b1"], d["W2"], d["b2"], d["mu"], d["sd"],
                       int(d["feat_dim"]), [str(k) for k in d["kinds"]])


# --------------------------------------------------------------------------- training
def train(rows, hidden=16, epochs=400, lr=0.05, l2=1e-4, seed=0, verbose=True):
    """Pure-numpy SGD. rows come from x0_data.build_rows. Returns X0Prior + stats.

    Target per row is a per-kind dict; kinds ABSENT in a row are masked out of the
    loss (a topology with no inductor contributes no L gradient)."""
    rng = np.random.default_rng(seed)
    kinds = XD.KINDS
    X = np.array([r["feat"] for r in rows], dtype=float)
    n, fd = X.shape
    Y = np.full((n, len(kinds)), np.nan)
    Wt = np.array([r.get("weight", 1.0) for r in rows], dtype=float)
    for i, r in enumerate(rows):
        for j, k in enumerate(kinds):
            if k in r["target"]:
                Y[i, j] = r["target"][k]
    mask = ~np.isnan(Y)
    Yf = np.nan_to_num(Y, nan=0.5)
    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-6] = 1.0
    Xn = (X - mu) / sd

    h = hidden
    W1 = rng.standard_normal((fd, h)) * math.sqrt(1.0 / fd)
    b1 = np.zeros(h)
    W2 = rng.standard_normal((h, len(kinds))) * math.sqrt(1.0 / h)
    b2 = np.zeros(len(kinds))

    for ep in range(epochs):
        H = np.tanh(Xn @ W1 + b1)
        O = H @ W2 + b2
        P = 1.0 / (1.0 + np.exp(-O))
        # masked, sample-weighted MSE on the sigmoid output
        err = (P - Yf) * mask * Wt[:, None]
        dO = err * P * (1 - P)
        gW2 = H.T @ dO / n + l2 * W2
        gb2 = dO.sum(0) / n
        dH = (dO @ W2.T) * (1 - H ** 2)
        gW1 = Xn.T @ dH / n + l2 * W1
        gb1 = dH.sum(0) / n
        W1 -= lr * gW1; b1 -= lr * gb1; W2 -= lr * gW2; b2 -= lr * gb2
        if verbose and (ep % 100 == 0 or ep == epochs - 1):
            loss = float((err ** 2).sum() / max(mask.sum(), 1))
            print(f"  epoch {ep:4d}  masked-wMSE {loss:.5f}", file=sys.stderr)
    return X0Prior(W1, b1, W2, b2, mu, sd, fd, kinds)


def _baseline_midpoint_loss(rows):
    """MSE of the midpoint 0.5 prior against the per-kind targets -- the null the
    learned prior must beat on held-out data to be worth anything."""
    se = w = 0.0
    for r in rows:
        for k, v in r["target"].items():
            se += (0.5 - v) ** 2
            w += 1
    return se / max(w, 1)


def _perkind_mean_loss(rows_train, rows_eval):
    """MSE of a per-kind-mean prior fit on train, eval on eval (the simplest
    non-trivial baseline -- ignores spec/topology conditioning)."""
    from collections import defaultdict
    acc = defaultdict(list)
    for r in rows_train:
        for k, v in r["target"].items():
            acc[k].append(v)
    mean = {k: (sum(v) / len(v)) for k, v in acc.items()}
    se = w = 0.0
    for r in rows_eval:
        for k, v in r["target"].items():
            se += (mean.get(k, 0.5) - v) ** 2
            w += 1
    return se / max(w, 1)


def _model_loss(model, rows):
    se = w = 0.0
    for r in rows:
        pk = model.predict_perkind(r["feat"])
        for k, v in r["target"].items():
            se += (pk.get(k, 0.5) - v) ** 2
            w += 1
    return se / max(w, 1)


def cli():
    import argparse
    ap = argparse.ArgumentParser(description="train / eval the learned x0 prior")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--out", default=DEFAULT_MODEL)
    ap.add_argument("--hidden", type=int, default=16)
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--holdout-spec", default=None,
                    help="hold ALL rows of this box spec out of training "
                         "(honesty check for spec generalisation)")
    ap.add_argument("--feasible-only", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = list(XD.build_rows(feasible_only=args.feasible_only, verbose=True,
                              cache=XD.rows_cache_path()))
    if not rows:
        sys.exit("no training rows (is topo_labels.jsonl present?)")
    rng = np.random.default_rng(args.seed)
    idx = rng.permutation(len(rows))
    rows = [rows[i] for i in idx]

    if args.holdout_spec:
        tr = [r for r in rows if r["meta"]["spec"] != args.holdout_spec]
        ev = [r for r in rows if r["meta"]["spec"] == args.holdout_spec]
    else:
        cut = int(0.85 * len(rows))
        tr, ev = rows[:cut], rows[cut:]
    print(f"train rows={len(tr)}  eval rows={len(ev)}", file=sys.stderr)

    model = train(tr, hidden=args.hidden, epochs=args.epochs, seed=args.seed)
    l_mid = _baseline_midpoint_loss(ev)
    l_km = _perkind_mean_loss(tr, ev)
    l_model = _model_loss(model, ev)
    print(json.dumps({
        "n_train": len(tr), "n_eval": len(ev),
        "holdout_spec": args.holdout_spec,
        "eval_mse_midpoint_null": round(l_mid, 5),
        "eval_mse_perkind_mean": round(l_km, 5),
        "eval_mse_learned": round(l_model, 5),
        "learned_beats_midpoint": bool(l_model < l_mid),
        "learned_beats_perkind_mean": bool(l_model < l_km),
    }, indent=1))
    if args.train:
        model.save(args.out)
        print(f"saved model -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    cli()
