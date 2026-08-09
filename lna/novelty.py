"""Is a generated topology novel, or a copy of something it was trained on?

This is the measuring stick (04-GEN P0). It fixes two defects that made every
generation experiment untrustworthy:

  1. The old fingerprint compared a sample only against *its own seed* circuit,
     so a sample that copied a DIFFERENT corpus LNA counted as novel. Here every
     sample is compared against the WL hashes of the whole reference set.
  2. The old fingerprint -- (device type, sorted node labels) -- was coarse and
     gameable. Here it is a Weisfeiler-Lehman graph hash over the device<->node
     bipartite graph (device vertices labelled by type, node vertices by net
     class, edges by pin role), plus a graded nearest-neighbour similarity (the
     normalized WL subtree kernel) so "how novel" is a number, not a boolean.

"Novel" means the WL graph hash is not in the *reference set*. Eulerian
augmentations are reorderings of the same graph, so the WL hash is
order-invariant and one canonical hash per reference circuit suffices. Bias
scaffolding (RBIAS/CBYP/VBGEN) is excluded by the naming contract so inserted
bias cannot change a topology's identity.

### The reference set is VERSIONED (read this before quoting an NDL number)

    ref-v1  the 41-circuit AnalogGenie LNA corpus only        (the P0 freeze)
    ref-v2  the 41 corpus circuits + every templates.py        (the default)
            archetype, as WL hashes of their token topologies

**ref-v1 systematically overstates novelty for every P5-era generator.** P5 arms
are fine-tuned on the Eulerian-augmented `templates.py` archetype set, so a
verbatim regeneration of a hand-written archetype is a *copy of training data* --
but ref-v1 never looked at the archetypes and scored it "novel". Measured, this
is not a rounding error: ~51% of the P5-v6 pool's screen-passing samples are
archetype regenerations (Track B, `data/reports/trackb-p5v6-2026-08-08.md`).

ref-v1 stays reachable (`--ref v1`) so every historical number remains
reproducible, and **every protocol row records which reference produced it**
plus the reference's size and digest -- the archetype set has grown 92 -> 118 ->
135 -> 148 over the program, so "ref-v2" alone does not pin a number. The digest
does.

The self-contained WL implementation (no networkx) keeps this runnable under the
same torch-free Windows analysis Python as screen.py / spec.py.

    python lna/novelty.py --dir lna/out/sweep12                 # novelty report
    python lna/novelty.py --eval lna/out/sweep12 --spec wifi24  # frozen-protocol row
    python lna/novelty.py --eval <dir> [<dir> ...] --ref both --spec wifi24
    python lna/novelty.py --rebaseline --spec wifi24            # sweep 4/8/12/24
    python lna/novelty.py --show-ref [--refresh-ref]            # reference audit
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

REF_V1 = "ref-v1"          # 41-circuit corpus only -- the original P0 freeze
REF_V2 = "ref-v2"          # corpus + every templates.py archetype
DEFAULT_REF = REF_V2       # what a run uses unless told otherwise
_HERE = os.path.dirname(os.path.abspath(__file__))
REF_CACHE_PATH = os.path.join(_HERE, "data", "novelty_ref_v2.json")
# The archetype set is a function of these files; any edit invalidates the cache.
_REF_SOURCES = ["templates.py", "spec.py", "topology.py", "novelty.py",
                os.path.join("specs", "wifi24.yaml"),
                os.path.join("specs", "wideband-sdr.yaml")]


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
    """(set of corpus WL graph-hashes, list of (index, feature Counter)).

    This is **ref-v1** and its behaviour is deliberately frozen: campaign.py,
    loop.py, size.py and trackb_g4.py call it for their own novelty checks, and
    every pre-2026-08-09 NDL number was measured against it. New work should
    call `reference()` instead."""
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


# --------------------------------------------------- archetype set (ref-v2)
def _sources_sha256():
    """Digest of every file the archetype set is a function of, so a stale
    on-disk reference cache can never silently answer a novelty question."""
    h = hashlib.sha256()
    for rel in _REF_SOURCES:
        p = os.path.join(_HERE, rel)
        h.update(rel.encode())
        h.update(open(p, "rb").read() if os.path.exists(p) else b"<missing>")
    return h.hexdigest()


def _emit_archetypes():
    """Archetype rows straight from the `templates.py` emission path -- the same
    `archetypes()` generator that mints the P5 training set, so the reference is
    by construction exactly what the generator was trained on. Lazy import:
    templates.py imports wl_features from here."""
    import templates                                    # noqa: E402  (circular)
    return [{"name": a["name"], "cls": a["cls"], "wl": a["wl"],
             "seq": list(a["seq"])} for a in templates.archetypes()]


def archetype_rows(refresh=False, path=REF_CACHE_PATH):
    """Cached archetype rows (name, cls, wl, seq). Enumerating them costs ~40 s
    (netlist emission + structural screen), so the result is cached on disk and
    keyed by `_sources_sha256()`; a mismatched key rebuilds rather than lies."""
    key = _sources_sha256()
    if not refresh and os.path.exists(path):
        try:
            blob = json.load(open(path, encoding="utf-8"))
            if blob.get("sources_sha256") == key:
                return blob["archetypes"]
        except (ValueError, KeyError):
            pass
    rows = _emit_archetypes()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"version": REF_V2, "wl_iters": WL_ITERS,
                   "sources_sha256": key, "n_archetypes": len(rows),
                   "archetypes": rows}, fh, indent=1)
    return rows


# ------------------------------------------------------ versioned reference
_REF_CACHE = {}


def reference(version=DEFAULT_REF, iters=WL_ITERS, refresh=False):
    """The novelty reference set.

    Returns (hashes:set, feats:list[(name, Counter)], meta:dict). `meta` carries
    `version`, `n_corpus`, `n_archetypes`, `n_hashes`, `wl_iters` and `digest` --
    a blake2b over the sorted hash list, which is what actually pins a published
    NDL number (the archetype set has grown over the program's life)."""
    version = {"v1": REF_V1, "v2": REF_V2}.get(version, version)
    if version not in (REF_V1, REF_V2):
        raise ValueError(f"unknown novelty reference {version!r}")
    ck = (version, iters)
    if ck in _REF_CACHE and not refresh:
        return _REF_CACHE[ck]

    chashes, cfeats = corpus_reference(iters=iters)
    hashes = set(chashes)
    feats = [(f"corpus:{i}", f) for i, f in cfeats]
    n_arch = 0
    if version == REF_V2:
        rows = archetype_rows(refresh=refresh)
        n_arch = len(rows)
        for a in rows:
            gh, feat = wl_features(Topology(a["seq"]), iters)
            hashes.add(gh)
            feats.append((f"arch:{a['name']}", feat))

    meta = {"version": version, "n_corpus": len(cfeats), "n_archetypes": n_arch,
            "n_hashes": len(hashes), "wl_iters": iters,
            "digest": _h(sorted(hashes))}
    _REF_CACHE[ck] = (hashes, feats, meta)
    return _REF_CACHE[ck]


def ref_tag(meta):
    """Compact provenance stamp for a protocol row: ref-v2[189h/8d1c...]."""
    return f"{meta['version']}[{meta['n_hashes']}h/{meta['digest'][:8]}]"


def nn_similarity(feat, ref_feats):
    """Max WL-cosine of a sample against the reference (its nearest neighbour)."""
    best, who = 0.0, None
    for i, cf in ref_feats:
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


def evaluate(directory, spec=None, iters=WL_ITERS, ref=DEFAULT_REF):
    """Frozen-protocol metrics for one or more directories of seq*.txt (04-GEN §1).

    `directory` may be a single path or a list of paths; multiple paths are
    concatenated (used to combine the seed-1337 and seed-2338 halves into the
    256-sample protocol). Files are keyed (dir, basename) so same-named files
    across dirs do not collide.

    `ref` selects the novelty reference (see the module docstring). The returned
    row records `ref` / `ref_n` / `ref_digest`, so no NDL number ever travels
    without the measuring stick that produced it.
    """
    dirs = [directory] if isinstance(directory, str) else list(directory)
    ref_hashes, ref_feats, ref_meta = reference(ref, iters=iters)
    corpus_hashes, _ = corpus_reference(iters=iters)
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
        nn, _ = nn_similarity(feat, ref_feats)
        rows.append({
            "gh": gh,
            "valid": topo.valid,
            "terminated": term.get(f),
            "n_ind": topo.n_inductors,
            "ind_ratio": topo.inductor_ratio,
            "spec_pass": spec.structural_screen(topo)[0] if spec else None,
            "novel": gh not in ref_hashes,
            "corpus_copy": gh in corpus_hashes,
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
    copies = sum(1 for r in rows if not r["novel"])        # copies of the reference
    corpus_copies = sum(1 for r in rows if r["corpus_copy"])
    # The whole point of ref-v2: how much of the pool is regurgitated training
    # archetype rather than anything new.
    arch_copies = copies - corpus_copies

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
        "corpus_copies_pct": 100.0 * corpus_copies / n,
        "arch_copies_pct": 100.0 * arch_copies / n,
        "distinct": len({r["gh"] for r in rows}),
        "ref": ref_meta["version"],
        "ref_n": ref_meta["n_hashes"],
        "ref_digest": ref_meta["digest"],
        "ref_tag": ref_tag(ref_meta),
    }


def _print_row(label, m):
    if m is None:
        print(f"  {label}: (empty)")
        return
    sp = f"{m['spec_pass']:>3} ({m['spec_pass_pct']:4.1f}%)" if not math.isnan(
        m["spec_pass_pct"]) else "   n/a    "
    print(f"  {label:<22} n={m['n']:<4} valid={m['valid_pct']:5.1f}% "
          f"term={m['term_pct']:5.1f}% specL0={sp} "
          f"NDL={m['ndl']:<3} med_nn={m['median_nn']:.3f} "
          f"indR={m['ind_ratio']:.3f} anyL={m['any_ind_pct']:4.1f}% "
          f"copies={m['copies_pct']:4.1f}% "
          f"(arch {m['arch_copies_pct']:4.1f}% / corpus {m['corpus_copies_pct']:4.1f}%) "
          f"{m['ref_tag']}")


# ---------------------------------------------------------- legacy report
def report_dir(directory, spec, iters, ref=DEFAULT_REF):
    _, _, meta = reference(ref, iters=iters)
    print(f"novelty reference: {ref_tag(meta)} = {meta['n_hashes']} distinct WL "
          f"hashes from {meta['n_corpus']} corpus LNAs + "
          f"{meta['n_archetypes']} templates.py archetypes")
    m = evaluate(directory, spec, iters, ref=ref)
    if m is None:
        print("  (no samples)")
        return
    print(f"generated circuits      : {m['n']}")
    print(f"distinct topologies (WL): {m['distinct']} "
          f"({100.0*m['distinct']/m['n']:.1f}%)")
    print(f"copies of the reference : {m['copies_pct']:.1f}%  "
          f"(archetype {m['arch_copies_pct']:.1f}% / corpus "
          f"{m['corpus_copies_pct']:.1f}%)")
    if spec:
        print(f"spec-pass@L0 ({spec.name}) : {m['spec_pass']} "
              f"({m['spec_pass_pct']:.1f}%)")
        print(f"NDL@{m['n']} (novel distinct spec-passing): {m['ndl']}")
        print(f"median NN-sim of passing: {m['median_nn']:.3f}")
    print(f"inductor ratio          : {m['ind_ratio']:.3f}  "
          f"(any inductor: {m['any_ind_pct']:.1f}%)")


def _refs_for(arg):
    return [REF_V1, REF_V2] if arg == "both" else [arg]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="directory of seq*.txt to report on")
    ap.add_argument("--eval", nargs="+", metavar="DIR",
                    help="directories -> one frozen-protocol metrics row each")
    ap.add_argument("--rebaseline", action="store_true",
                    help="run the 4/8/12/24 prefix sweep under the frozen protocol")
    ap.add_argument("--rebaseline256", action="store_true",
                    help="full protocol: combine sweep{P} (1337) + sweep{P}_s2338")
    ap.add_argument("--sweep-dir", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "out"))
    ap.add_argument("--spec", default=None)
    ap.add_argument("--iters", type=int, default=WL_ITERS)
    ap.add_argument("--ref", default=DEFAULT_REF,
                    choices=["v1", "v2", REF_V1, REF_V2, "both"],
                    help="novelty reference set (default ref-v2: corpus + "
                         "templates.py archetypes; 'both' prints old vs new)")
    ap.add_argument("--show-ref", action="store_true",
                    help="print the reference audit stamp and exit")
    ap.add_argument("--refresh-ref", action="store_true",
                    help="rebuild the archetype reference cache from templates.py")
    args = ap.parse_args()
    refs = _refs_for(args.ref)

    if args.refresh_ref:
        archetype_rows(refresh=True)
    if args.show_ref or args.refresh_ref:
        for v in (REF_V1, REF_V2):
            _, _, m = reference(v, iters=args.iters, refresh=args.refresh_ref)
            print(f"{ref_tag(m):<28} corpus={m['n_corpus']} "
                  f"archetypes={m['n_archetypes']} wl_iters={m['wl_iters']} "
                  f"digest={m['digest']}")
        print(f"cache: {REF_CACHE_PATH}")
        if not (args.dir or args.eval or args.rebaseline or args.rebaseline256):
            return

    spec = None
    if args.spec:
        from spec import Spec
        spec = Spec.load(args.spec)

    if args.dir:
        for v in refs:
            report_dir(args.dir, spec, args.iters, ref=v)
    if args.eval:
        for d in args.eval:
            for v in refs:
                _print_row(os.path.basename(d.rstrip("/\\")),
                           evaluate(d, spec, args.iters, ref=v))
    if args.rebaseline:
        print(f"frozen-protocol re-baseline  spec={spec.name if spec else None}  "
              f"(existing runs are 128 samples @ seed 1337; the full protocol is "
              f"256 @ seeds 1337+2338 -- generate the second half on the GPU)")
        for p in (4, 8, 12, 24):
            d = os.path.join(args.sweep_dir, f"sweep{p}")
            if os.path.isdir(d):
                for v in refs:
                    _print_row(f"prefix{p}", evaluate(d, spec, args.iters, ref=v))

    if args.rebaseline256:
        print(f"FULL frozen protocol (256 = 128@1337 + 128@2338)  "
              f"spec={spec.name if spec else None}")
        for p in (4, 8, 12, 24):
            dirs = [os.path.join(args.sweep_dir, f"sweep{p}"),
                    os.path.join(args.sweep_dir, f"sweep{p}_s2338")]
            dirs = [d for d in dirs if os.path.isdir(d)]
            if dirs:
                for v in refs:
                    _print_row(f"prefix{p}", evaluate(dirs, spec, args.iters, ref=v))


if __name__ == "__main__":
    main()
