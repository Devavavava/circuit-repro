"""Build the STRICTLY template-free winners file for FINDINGS §16's ctrl-v1s arm.

`emit_winners` draws the store's own top quartile, and the store contains
stratum-T rows -- hand `templates.py` archetypes the sizing loop promoted. On the
P5-v3-era emission that is 42 of 77 distinct topologies and 42.3% of the rows, so
"corpus + winners only" still leaks archetypes into a supposedly template-free
control. This drops every row whose WL hash is in the novelty reference (ref-v2 =
corpus + archetypes), leaving only winners the pipeline genuinely discovered.

    python lna/_ctrl_strict_winners.py [--src PATH] [--out PATH]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from novelty import reference, wl_features  # noqa: E402
from topology import Topology  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "out",
                                                  "winners_train.pre_dhruva.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "out",
                                                  "winners_train.ctrl_strict.json"))
    args = ap.parse_args()
    ref_hashes, _, meta = reference()
    rows = json.load(open(args.src, encoding="utf-8"))["rows"]
    keep = [r for r in rows
            if wl_features(Topology(r["seq"]))[0] not in ref_hashes]
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"rows": keep, "derived_from": os.path.basename(args.src),
                   "filter": f"drop rows whose WL hash is in {meta['version']}",
                   "ref_digest": meta["digest"]}, fh)
    n_dis = len({wl_features(Topology(r["seq"]))[0] for r in keep})
    print(f"kept {len(keep)} of {len(rows)} rows ({n_dis} distinct topologies) "
          f"-> {args.out}   [{meta['version']}/{meta['digest'][:8]}]")


if __name__ == "__main__":
    main()
