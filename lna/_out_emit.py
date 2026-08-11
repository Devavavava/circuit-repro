"""WP-OUTCOME step 1 -- emit the conditioned training channel from the store.

The shape of `templates.emit_winners` (Loop B channel) with one difference that
is the entire experiment: a row does not get in because it WON, it gets in
because it was MEASURED, and it carries what it measured as four conditioning
tokens. Every (topology, spec) key inside the current label domain contributes,
whatever its outcome -- VIOLATED rows are as informative as MET rows to a
conditioned model, and dropping them would turn this back into winners feedback.

TRUE SPICE numbers only. Critic scores never select or label training data
(standing rule, see the `templates.emit_winners` docstring).

Two files are written from ONE augmentation pass, so the real and control arms
differ in nothing but the bin vectors:

  outcome_train.json        bins as measured
  outcome_train.shuf.json   the SAME rows with the multiset of 4-tuples randomly
                            permuted across rows (seed 1337). Per-slot token
                            marginals AND the joint bin-vector distribution are
                            preserved exactly; only the label-to-topology
                            correspondence is destroyed.

    python lna/_out_emit.py --out lna/out/outcome_train.json
"""
import argparse
import json
import os
import random
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _out_tokens as OT                                          # noqa: E402
import datastore as ds                                            # noqa: E402
import templates as T                                             # noqa: E402
from spec import Spec                                             # noqa: E402
from topology import Topology                                     # noqa: E402

#: Eulerian traversals per DISTINCT topology. The winners channel uses (10, 2);
#: this channel is capped at (4, 1) so that plain-class-token rows stay the
#: majority of the training mix -- the design requires the base distribution to
#: be preserved and the conditioning to be additive, which a channel bigger than
#: everything else would not be. Registered in plans2/11-WP-OUTCOME.md.
MAX_SOLUTIONS = 4
RUN_NUM = 1
SHUFFLE_SEED = 1337


def _cls_for(spec_name, cache={}):
    """Class token of a row = the band class of its spec, exactly the rule
    emit_winners uses (metrics live at the frequency of the spec they were
    measured against, so the spec decides which channel is reinforced)."""
    if spec_name not in cache:
        cache[spec_name] = "wb" if Spec.load(spec_name).allow_inductorless else "nb"
    return cache[spec_name]


def emit(out_path, limit=None, verbose=True):
    rows = ds.load("topo_labels")
    best = OT.best_per_key(rows)
    keys = sorted(best)
    if limit:
        keys = keys[:limit]
    n_domain = sum(1 for r in rows if OT.in_domain(r))

    # one augmentation per DISTINCT topology; a topology measured against two
    # specs reuses the same traversals under two different bin prefixes.
    aug_cache, t0 = {}, time.time()
    out_rows, per_key, n_netlist_fail = [], {}, 0
    for n, k in enumerate(keys):
        wl, spec_name = k
        row = best[k]
        toks = (row.get("graph") or {}).get("tokens")
        if wl not in aug_cache:
            nl, ports = T.topo_to_netlist(Topology(toks))
            if nl is None:
                aug_cache[wl] = []
                n_netlist_fail += 1
            else:
                try:
                    aug_cache[wl] = T.augment(nl, ports,
                                              max_solutions=MAX_SOLUTIONS,
                                              run_num=RUN_NUM)
                except Exception as e:                            # noqa: BLE001
                    print("  augment failed on %s: %s" % (wl, e), flush=True)
                    aug_cache[wl] = []
        seqs = aug_cache[wl]
        if not seqs:
            continue
        bins = OT.bins_of(row)
        cls = _cls_for(spec_name)
        for s in seqs:
            out_rows.append({"cls": cls, "bins": bins, "seq": s,
                             "wl": wl, "spec": spec_name})
        per_key[k] = len(seqs)
        if verbose and (n + 1) % 50 == 0:
            print("  [%d/%d] keys, %d rows, %.1f min"
                  % (n + 1, len(keys), len(out_rows), (time.time() - t0) / 60),
                  flush=True)

    # ---- the control: permute the multiset of bin vectors across rows
    rnd = random.Random(SHUFFLE_SEED)
    vecs = [tuple(r["bins"]) for r in out_rows]
    rnd.shuffle(vecs)
    shuf_rows = [dict(r, bins=list(v)) for r, v in zip(out_rows, vecs)]

    stats = _stats(best, keys, out_rows, per_key, n_netlist_fail)
    stats.update(n_l2_rows_in_domain=n_domain, max_solutions=MAX_SOLUTIONS,
                 run_num=RUN_NUM, shuffle_seed=SHUFFLE_SEED, tau=OT.TAU,
                 wall_min=round((time.time() - t0) / 60, 1))

    _write(out_path, out_rows, stats)
    shuf_path = out_path.replace(".json", ".shuf.json")
    _write(shuf_path, shuf_rows, dict(stats, arm="shuffled-control"))
    with open(out_path.replace(".json", ".stats.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(stats, fh, indent=2, sort_keys=True)
    print("wrote %d rows -> %s (and the shuffled control -> %s)"
          % (len(out_rows), out_path, shuf_path))
    _report(stats)
    return stats


def _write(path, rows, stats):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"rows": rows, "stats": stats}, fh)


def _stats(best, keys, out_rows, per_key, n_netlist_fail):
    per_metric = [Counter() for _ in OT.METRICS]
    row_metric = [Counter() for _ in OT.METRICS]
    combos, by_spec, by_cls = Counter(), Counter(), Counter()
    for k in keys:
        b = OT.bins_of(best[k])
        for i, x in enumerate(b):
            per_metric[i][x] += 1
        combos[tuple(b)] += 1
        by_spec[k[1]] += 1
    for r in out_rows:
        for i, x in enumerate(r["bins"]):
            row_metric[i][x] += 1
        by_cls[r["cls"]] += 1
    allmet = sum(v for c, v in combos.items() if all(x == "MET" for x in c))
    return {
        "n_keys": len(keys),
        "n_keys_emitted": len(per_key),
        "n_keys_no_augmentation": len(keys) - len(per_key),
        "n_netlist_fail": n_netlist_fail,
        "n_distinct_wl": len(set(k[0] for k in keys)),
        "n_rows": len(out_rows),
        "rows_per_key_mean": round(len(out_rows) / max(len(per_key), 1), 2),
        "keys_all_four_MET": allmet,
        "bins_per_metric_keys": dict((OT.METRICS[i], dict(per_metric[i]))
                                     for i in range(4)),
        "bins_per_metric_rows": dict((OT.METRICS[i], dict(row_metric[i]))
                                     for i in range(4)),
        "keys_per_spec": dict(by_spec),
        "rows_per_class": dict(by_cls),
        "top_combos": [[list(c), v] for c, v in combos.most_common(15)],
    }


def _report(s):
    print("\n  keys %d (distinct wl %d) -> emitted %d, rows %d (mean %.2f/key)"
          % (s["n_keys"], s["n_distinct_wl"], s["n_keys_emitted"], s["n_rows"],
             s["rows_per_key_mean"]))
    print("  all-four-MET keys: %d" % s["keys_all_four_MET"])
    for m in OT.METRICS:
        d = s["bins_per_metric_keys"][m]
        print("    %-4s " % m + "  ".join("%s %d" % (b, d.get(b, 0))
                                          for b in OT.BINS))
    print("  rows per class: %s" % s["rows_per_class"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(HERE, "out",
                                                  "outcome_train.json"))
    ap.add_argument("--limit", type=int, default=None,
                    help="only the first N keys (smoke test)")
    a = ap.parse_args()
    emit(a.out, limit=a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
