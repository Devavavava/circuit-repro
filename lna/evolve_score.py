"""WP-SEARCH rung-2 — critic v1 scoring worker (plans2/03-SEARCH §4-5).

The evolutionary driver (`lna/evolve.py`) runs under the torch-free analysis
python; critic v1 (the GNN ensemble of 02-CRITIC / FINDINGS §14.2) needs torch
2.0.1, which lives in the analoggenie env. Retraining a 5-model ensemble costs
~4 minutes, so the driver cannot afford to shell out per generation. This is a
**persistent scorer**: it trains the ensemble once against a pinned snapshot,
then answers newline-delimited JSON requests on stdin.

    <analoggenie py> lna/evolve_score.py --serve --snapshot v4-train
    >>> {"cmd":"score","items":[{"tokens":[...],"spec":"wideband-sdr"}]}
    <<< {"ok":true,"mean":[[...4...]],"std":[[...4...]]}

Trust-rule machinery it owns (03-SEARCH §4):
  * predictions are the ensemble MEAN and STD over the 4-margin head
    (S11 / S21 / Idd / NF) — the driver consumes `mean - beta*std`, never mean;
  * the **uncertainty gate** threshold: the 90th percentile of ensemble std on a
    held-out family split the scoring ensemble never trained on. The same
    holdout gives the realized rho / rank accuracy printed at startup, so the
    critic's deployment-time skill is recorded with the run (00-OVERVIEW rule 4).

Nothing here is a result: critic numbers never enter FINDINGS as measurements
(§4 rule 4). They only decide where SPICE minutes go.
"""
from __future__ import print_function

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import critic                      # noqa: E402
import critic_gnn as G             # noqa: E402
import datastore as ds             # noqa: E402
from topology import Topology      # noqa: E402


def _emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _log(msg):
    sys.stderr.write("[score] %s\n" % msg)
    sys.stderr.flush()


class Scorer(object):
    def __init__(self, snapshot="v4-train", n_models=5, k_holdout=0.25,
                 sigma_recipe="candidate-v1+bo3", seed0=0):
        t0 = time.time()
        data = critic.load_dataset(snapshot=snapshot)
        sigma = critic._sigma_s21(recipe=sigma_recipe, snapshot=snapshot)
        sp = ds.family_split(k_holdout=k_holdout, rows=[d["row"] for d in data])
        id2d = {id(d["row"]): d for d in data}
        tr = [id2d[id(r)] for r in sp["train"] if id(r) in id2d]
        va = [id2d[id(r)] for r in sp["val"] if id(r) in id2d]
        te = [id2d[id(r)] for r in sp["test"] if id(r) in id2d]
        # spec scaler fit on TRAIN only, then frozen for every later prediction
        S = np.array([critic.spec_vector(d["spec"]) for d in tr], np.float32)
        G._SPEC_MU = (S.mean(0), S.std(0) + 1e-6)
        self.sigma_norm = sigma / 12.0
        self.models = [G.train_one(tr, va, self.sigma_norm, seed=seed0 + s)
                       for s in range(n_models)]
        # --- holdout calibration: uncertainty gate + realized skill
        mean, std = self._raw(te)
        Yte = np.array([d["y"] for d in te])
        self.sigma_gate = float(np.percentile(std[:, :3].mean(1), 90))
        err = np.abs(mean[:, 1] - Yte[:, 1])
        self.info = {
            "snapshot": snapshot, "sigma_s21": sigma, "n_models": n_models,
            "n_train": len(tr), "n_val": len(va), "n_holdout": len(te),
            "sigma_gate_p90": self.sigma_gate,
            "rho_s11": critic.spearman(Yte[:, 0], mean[:, 0]),
            "rho_s21": critic.spearman(Yte[:, 1], mean[:, 1]),
            "rho_idd": critic.spearman(Yte[:, 2], mean[:, 2]),
            "unc_cal": critic.spearman(std[:, 1], err),
            "rank_acc": critic.pairwise_rank_acc(Yte[:, 1], mean[:, 1],
                                                 self.sigma_norm),
            "train_s": round(time.time() - t0, 1),
        }
        # WL features of every labeled row -> trust region (§4 rule 3)
        self.labeled_wl = [d["wl"] for d in data]
        self.labeled_hash = set()
        for d in data:
            h = d["row"].get("wl_hash")
            if h:
                self.labeled_hash.add(h)

    def _raw(self, items):
        P = np.stack([G.predict(m, items) for m in self.models])
        return P.mean(0), P.std(0)

    def score(self, reqs):
        items = []
        for r in reqs:
            topo = Topology(r["tokens"])
            items.append({"topo": topo, "spec": r["spec"],
                          "y": np.zeros(3), "y_nf": None})
        mean, std = self._raw(items)
        return mean, std


def serve(args):
    sc = Scorer(snapshot=args.snapshot, n_models=args.n_models,
                k_holdout=args.k_holdout)
    _log("ready: " + json.dumps(sc.info))
    _emit({"ok": True, "cmd": "ready", "info": sc.info})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError as e:
            _emit({"ok": False, "error": "bad json: %s" % e})
            continue
        cmd = req.get("cmd")
        if cmd == "stop":
            _emit({"ok": True, "cmd": "stop"})
            return 0
        if cmd == "score":
            try:
                mean, std = sc.score(req["items"])
                _emit({"ok": True, "mean": mean.tolist(), "std": std.tolist()})
            except Exception as e:                     # never kill the server
                _emit({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})
            continue
        _emit({"ok": False, "error": "unknown cmd %r" % cmd})
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--snapshot", default="v4-train")
    ap.add_argument("--n-models", type=int, default=5)
    ap.add_argument("--k-holdout", type=float, default=0.25)
    args = ap.parse_args()
    if args.serve:
        return serve(args)
    ap.error("give --serve")


if __name__ == "__main__":
    sys.exit(main())
