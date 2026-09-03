"""x0_retrieval.py -- arm A1 warm start: nearest stored winner's sizing as x0.

The retrieval baseline the learned prior must BEAT (alongside the midpoint null)
to ever be adopted. Given (topology sizable-spec, achieved-target, pdk) it finds
the most similar stored evaluated design and returns ITS decoded best_params
re-encoded to this topology's [0,1]^d. No learning -- just k-NN over the same box
corpus `x0_data.build_rows` reads (ladder rows already excluded there).

Similarity = same wl_hash first (exact topology match), else nearest feature
vector (the same feature `x0_data.feature_vector` builds). When the retrieved
design's device kinds cover the query topology's kinds we map per-DEVICE where
the param name matches, else fall back to the retrieved design's per-kind mean.
DEFAULT OFF: only used when `x0_prior.mode() == 'retrieval'`.
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


class Retriever:
    """In-memory k-NN over the box corpus, keyed by feature vector + wl_hash.

    Each entry stores the per-kind normalised x (the same target `x0_data`
    builds) so retrieval returns a ready-to-use x0 without re-inverting."""

    def __init__(self, entries):
        self.entries = entries
        self.F = np.array([e["feat"] for e in entries], dtype=float) if entries else None
        if self.F is not None and len(self.F):
            self.mu = self.F.mean(0)
            self.sd = self.F.std(0)
            self.sd[self.sd < 1e-6] = 1.0
            self.Fn = (self.F - self.mu) / self.sd
        else:
            self.mu = self.sd = self.Fn = None

    @staticmethod
    def build(feasible_only=False):
        entries = []
        for r in XD.build_rows(feasible_only=feasible_only,
                               cache=XD.rows_cache_path()):
            entries.append({"feat": r["feat"], "target": r["target"],
                            "wl_hash": r["meta"]["wl_hash"],
                            "pdk": r["meta"]["pdk"],
                            "feasible": r["meta"]["feasible"]})
        return Retriever(entries)

    def query_perkind(self, graph, metrics, band_f0, pdk, wl_hash=None):
        """Return {kind: x} from the nearest stored winner, or None if empty."""
        if not self.entries:
            return None
        # 1) exact/prefix topology match wins (prefer feasible ones). Callers
        #    often only hold a 12-char wl_hash prefix (the solve_spec label), so
        #    match on the shorter of the two lengths.
        if wl_hash:
            def _hit(e):
                eh = e["wl_hash"] or ""
                k = min(len(eh), len(wl_hash))
                return k >= 8 and eh[:k] == wl_hash[:k]
            exact = [e for e in self.entries if _hit(e)]
            exact.sort(key=lambda e: (not e["feasible"],))
            if exact:
                return dict(exact[0]["target"])
        # 2) nearest feature vector
        q = (np.asarray(XD.feature_vector(graph, metrics, band_f0, pdk), dtype=float)
             - self.mu) / self.sd
        d = np.linalg.norm(self.Fn - q, axis=1)
        # break ties toward feasible neighbours
        order = np.argsort(d)
        best = order[0]
        for i in order[:8]:
            if self.entries[i]["feasible"]:
                best = i
                break
        return dict(self.entries[best]["target"])

    def x0_for(self, graph, metrics, band_f0, pdk, sizable, wl_hash=None):
        pk = self.query_perkind(graph, metrics, band_f0, pdk, wl_hash=wl_hash)
        if pk is None:
            return None
        return [pk.get(kind, 0.5) for kind in sizable.values()]


_CACHE = {}


def get_retriever(feasible_only=False):
    key = bool(feasible_only)
    if key not in _CACHE:
        _CACHE[key] = Retriever.build(feasible_only=feasible_only)
    return _CACHE[key]


if __name__ == "__main__":
    r = Retriever.build()
    print(f"retriever entries: {len(r.entries)}")
