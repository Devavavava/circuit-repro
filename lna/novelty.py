"""Is a generated topology novel, or a copy of *some* corpus LNA?

This is the measuring stick (04-GEN P0). It fixes two defects that made every
generation experiment untrustworthy:

  1. The old fingerprint compared a sample only against *its own seed* circuit,
     so a sample that copied a DIFFERENT corpus LNA counted as novel. Here every
     sample is compared against the WL hashes of all 41 corpus LNA graphs.
  2. The old fingerprint -- (device type, sorted node labels) -- was coarse and
     gameable. Here it is a Weisfeiler-Lehman graph hash over the device<->node
     bipartite graph (device vertices labelled by type, node vertices by net
     class, edges by pin role), plus a graded nearest-neighbour similarity (the
     normalized WL subtree kernel) so "how novel" is a number, not a boolean.

"Novel" means the WL graph hash is not in the corpus set. Eulerian augmentations
are reorderings of the same graph, so the WL hash is order-invariant and 41
canonical hashes suffice. Bias scaffolding (RBIAS/CBYP/VBGEN) is excluded by the
naming contract so inserted bias cannot change a topology's identity.

The self-contained WL implementation (no networkx) keeps this runnable under the
same torch-free Windows analysis Python as screen.py / spec.py.

    python lna/novelty.py --dir lna/out/sweep12                 # novelty report
    python lna/novelty.py --eval lna/out/sweep12 --spec wifi24  # frozen-protocol row
    python lna/novelty.py --rebaseline --spec wifi24            # sweep 4/8/12/24
"""
import argparse
import glob
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import (PIN_RE, Topology, base_of, is_scaffold,  # noqa: E402
                      parse_arrow_file)

REPO = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "AnalogGenie", "repo"))
LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))
WL_ITERS = 3


# ----------------------------------------------------------------- net class
def _net_class(members, nets):
    """Coarse class of an electrical node from its net members."""
    named = [m for m in members if m in nets]
    for pref, cls in (("VDD", "VDD"), ("VSS", "VSS"), ("VIN", "VIN"),
                      ("VOUT", "VOUT"), ("VB", "BIAS"), ("VCM", "BIAS"),
                      ("VREF", "BIAS"), ("IB", "IB")):
        if any(n == pref or n.startswith(pref) for n in named):
            return cls
    if any(n == "0" for n in named):
        return "VSS"
    return "NET" if named else "INT"


# --------------------------------------------------------- WL graph hashing
def _bipartite(topo):
    """(vertex->init label, vertex->list of (edge_label, neighbour))."""
    pin2root = {}
    for root, members in topo.nodes.items():
        for m in members:
            if PIN_RE.match(m):
                pin2root[m] = root

    labels, adj = {}, defaultdict(list)
    for d in topo.devices:
        if is_scaffold(d):
            continue
        labels[("D", d)] = base_of(d)
    for root, members in topo.nodes.items():
        labels[("N", root)] = _net_class(members, topo.nets)

    for p in topo.pins:
        m = PIN_RE.match(p)
        d, pin = m.group("dev"), m.group("pin")
        if is_scaffold(d) or d not in topo.devices:
            continue
        root = pin2root.get(p)
        if root is None:
            continue
        dv, nv = ("D", d), ("N", root)
        adj[dv].append((pin, nv))
        adj[nv].append((pin, dv))
    return labels, adj


def _h(obj):
    return hashlib.blake2b(repr(obj).encode(), digest_size=8).hexdigest()


def wl_features(topo, iters=WL_ITERS):
    """Return (graph_hash, feature Counter of WL subtree labels over all rounds).

    The graph hash is the digest of the final-round label multiset (order-
    invariant). The feature Counter accumulates labels from every round and is
    the WL subtree-kernel feature vector used for graded similarity.
    """
    labels, adj = _bipartite(topo)
    cur = dict(labels)
    feat = Counter((0, l) for l in cur.values())
    for it in range(1, iters + 1):
        nxt = {}
        for v, l in cur.items():
            neigh = sorted((el, cur[n]) for el, n in adj[v])
            nxt[v] = _h((l, neigh))
        cur = nxt
        for l in cur.values():
            feat[(it, l)] += 1
    graph_hash = _h(sorted(Counter(cur.values()).items()))
    return graph_hash, feat


def wl_cosine(a, b):
    """Normalized WL subtree kernel (cosine) in [0,1]; 1.0 == identical features."""
    dot = sum(cnt * b.get(k, 0) for k, cnt in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


# ------------------------------------------------------------- corpus set
_CORPUS_CACHE = None


def corpus_reference(indices=LNA_INDICES, iters=WL_ITERS):
    """(set of corpus WL graph-hashes, list of (index, feature Counter))."""
    global _CORPUS_CACHE
    if _CORPUS_CACHE is not None:
        return _CORPUS_CACHE
    hashes, feats = set(), []
    for i in indices:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        topo = Topology([str(t) for t in np.load(p, allow_pickle=True)[0]])
        gh, feat = wl_features(topo, iters)
        hashes.add(gh)
        feats.append((i, feat))
    _CORPUS_CACHE = (hashes, feats)
    return _CORPUS_CACHE


def nn_similarity(feat, corpus_feats):
    """Max WL-cosine of a sample against the corpus (its nearest neighbour)."""
    best, who = 0.0, None
    for i, cf in corpus_feats:
        s = wl_cosine(feat, cf)
        if s > best:
            best, who = s, i
    return best, who


# ------------------------------------------------------------- evaluation
def _terminated_map(directory):
    meta_path = os.path.join(directory, "meta.json")
    if not os.path.exists(meta_path):
        return {}
    meta = json.load(open(meta_path)).get("meta", [])
    return {m["file"]: m.get("terminated") for m in meta}


def evaluate(directory, spec=None, iters=WL_ITERS):
    """Frozen-protocol metrics for one or more directories of seq*.txt (04-GEN §1).

    `directory` may be a single path or a list of paths; multiple paths are
    concatenated (used to combine the seed-1337 and seed-2338 halves into the
    256-sample protocol). Files are keyed (dir, basename) so same-named files
    across dirs do not collide.
    """
    dirs = [directory] if isinstance(directory, str) else list(directory)
    corpus_hashes, corpus_feats = corpus_reference(iters=iters)
    files = []
    term = {}
    for d in dirs:
        tmap = _terminated_map(d)
        for f in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
            files.append(f)
            term[f] = tmap.get(os.path.basename(f))
    rows = []
    for f in files:
        topo = Topology(parse_arrow_file(f))
        gh, feat = wl_features(topo, iters)
        nn, _ = nn_similarity(feat, corpus_feats)
        rows.append({
            "gh": gh,
            "valid": topo.valid,
            "terminated": term.get(f),
            "n_ind": topo.n_inductors,
            "ind_ratio": topo.inductor_ratio,
            "spec_pass": spec.structural_screen(topo)[0] if spec else None,
            "novel": gh not in corpus_hashes,
            "nn": nn,
        })
    n = len(rows)
    if n == 0:
        return None

    valid = sum(r["valid"] for r in rows)
    term_n = sum(1 for r in rows if r["terminated"])
    term_known = sum(1 for r in rows if r["terminated"] is not None)
    ind_ratio = sum(r["ind_ratio"] for r in rows) / n
    any_ind = sum(1 for r in rows if r["n_ind"] >= 1) / n

    passing = [r for r in rows if r["spec_pass"]] if spec else []
    # NDL@N: distinct WL hashes among samples that are spec-passing AND novel
    ndl_set = {r["gh"] for r in passing if r["novel"]}
    med_nn = float(np.median([r["nn"] for r in passing])) if passing else float("nan")
    copies = sum(1 for r in rows if not r["novel"])   # whole-corpus copies

    return {
        "n": n,
        "valid_pct": 100.0 * valid / n,
        "term_pct": (100.0 * term_n / term_known) if term_known else float("nan"),
        "spec_pass": len(passing),
        "spec_pass_pct": (100.0 * len(passing) / n) if spec else float("nan"),
        "ndl": len(ndl_set),
        "median_nn": med_nn,
        "ind_ratio": ind_ratio,
        "any_ind_pct": 100.0 * any_ind,
        "copies_pct": 100.0 * copies / n,
        "distinct": len({r["gh"] for r in rows}),
    }


def _print_row(label, m):
    if m is None:
        print(f"  {label}: (empty)")
        return
    sp = f"{m['spec_pass']:>3} ({m['spec_pass_pct']:4.1f}%)" if not math.isnan(
        m["spec_pass_pct"]) else "   n/a    "
    print(f"  {label:<10} n={m['n']:<4} valid={m['valid_pct']:5.1f}% "
          f"term={m['term_pct']:5.1f}% specL0={sp} "
          f"NDL={m['ndl']:<3} med_nn={m['median_nn']:.3f} "
          f"indR={m['ind_ratio']:.3f} anyL={m['any_ind_pct']:4.1f}% "
          f"copies={m['copies_pct']:4.1f}%")


# ---------------------------------------------------------- legacy report
def report_dir(directory, spec, iters):
    corpus_hashes, corpus_feats = corpus_reference(iters=iters)
    term = _terminated_map(directory)
    files = sorted(glob.glob(os.path.join(directory, "seq*.txt")))
    print(f"corpus reference: {len(corpus_hashes)} distinct WL hashes "
          f"from {len(corpus_feats)} LNA graphs")
    m = evaluate(directory, spec, iters)
    if m is None:
        print("  (no samples)")
        return
    print(f"generated circuits      : {m['n']}")
    print(f"distinct topologies (WL): {m['distinct']} "
          f"({100.0*m['distinct']/m['n']:.1f}%)")
    print(f"copies of *some* corpus : {m['copies_pct']:.1f}%  "
          "(old metric only caught copies of the seed)")
    if spec:
        print(f"spec-pass@L0 ({spec.name}) : {m['spec_pass']} "
              f"({m['spec_pass_pct']:.1f}%)")
        print(f"NDL@{m['n']} (novel distinct spec-passing): {m['ndl']}")
        print(f"median NN-sim of passing: {m['median_nn']:.3f}")
    print(f"inductor ratio          : {m['ind_ratio']:.3f}  "
          f"(any inductor: {m['any_ind_pct']:.1f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="directory of seq*.txt to report on")
    ap.add_argument("--eval", help="directory -> one frozen-protocol metrics row")
    ap.add_argument("--rebaseline", action="store_true",
                    help="run the 4/8/12/24 prefix sweep under the frozen protocol")
    ap.add_argument("--rebaseline256", action="store_true",
                    help="full protocol: combine sweep{P} (1337) + sweep{P}_s2338")
    ap.add_argument("--sweep-dir", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "out"))
    ap.add_argument("--spec", default=None)
    ap.add_argument("--iters", type=int, default=WL_ITERS)
    args = ap.parse_args()

    spec = None
    if args.spec:
        from spec import Spec
        spec = Spec.load(args.spec)

    if args.dir:
        report_dir(args.dir, spec, args.iters)
    if args.eval:
        _print_row(os.path.basename(args.eval.rstrip("/\\")),
                   evaluate(args.eval, spec, args.iters))
    if args.rebaseline:
        print(f"frozen-protocol re-baseline  spec={spec.name if spec else None}  "
              f"(existing runs are 128 samples @ seed 1337; the full protocol is "
              f"256 @ seeds 1337+2338 -- generate the second half on the GPU)")
        for p in (4, 8, 12, 24):
            d = os.path.join(args.sweep_dir, f"sweep{p}")
            if os.path.isdir(d):
                _print_row(f"prefix{p}", evaluate(d, spec, args.iters))

    if args.rebaseline256:
        print(f"FULL frozen protocol (256 = 128@1337 + 128@2338)  "
              f"spec={spec.name if spec else None}")
        for p in (4, 8, 12, 24):
            dirs = [os.path.join(args.sweep_dir, f"sweep{p}"),
                    os.path.join(args.sweep_dir, f"sweep{p}_s2338")]
            dirs = [d for d in dirs if os.path.isdir(d)]
            if dirs:
                _print_row(f"prefix{p}", evaluate(dirs, spec, args.iters))


if __name__ == "__main__":
    main()
