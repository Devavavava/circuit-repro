#!/usr/bin/env python
"""Label-noise ceiling: how often does the SAME (tokens, spec) flip feasibility across
sizing seeds? (bench-v2 included rows; descriptive, no model.)"""
import collections
import gzip
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in gzip.open(f"{HERE}/data/rows.jsonl.gz", "rt")]
rows = [r for r in rows if r.get("incl") and r["src"] == "bench-v2"]
g = collections.defaultdict(dict)
for r in rows:
    g[(r["tok"], r["spec_sha"])][r["seed"]] = r["y"]
multi = {k: v for k, v in g.items() if len(v) >= 2}
mixed = sum(1 for v in multi.values() if len(set(v.values())) > 1)
anypos = sum(1 for v in multi.values() if any(v.values()))
# seed-1 verdict as a predictor of the seed-2 verdict
pairs = [(v[1], v[2]) for v in multi.values() if 1 in v and 2 in v]
tp = sum(1 for a, b in pairs if a and b)
fn = sum(1 for a, b in pairs if not a and b)
fp = sum(1 for a, b in pairs if a and not b)
res = {"n_pairs_multi_seed": len(multi), "mixed_label": mixed, "any_pos": anypos,
       "mixed_frac_of_anypos": mixed / max(anypos, 1),
       "seed1_predicts_seed2": {"n": len(pairs), "tp": tp, "fn": fn, "fp": fp,
                                "recall": tp / max(tp + fn, 1), "precision": tp / max(tp + fp, 1)}}
json.dump(res, open(f"{HERE}/results/noise.json", "w"), indent=1)
print(json.dumps(res, indent=1))
