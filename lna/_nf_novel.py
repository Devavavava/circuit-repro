import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import datastore as ds
from novelty import reference, wl_features, nn_similarity
from topology import Topology
TARGET = "ce39a77c91974013"
hashes, feats, meta = reference()
print("ref:", {k: meta.get(k) for k in ("version", "n_corpus", "n_external",
                                        "n_archetypes", "n_hashes", "digest")})
toks = None
pre_run = set()
for r in ds.load("topo_labels"):
    g = r.get("graph") or {}
    if r.get("wl_hash") == TARGET and g.get("tokens"):
        toks = g["tokens"]
    rec = (r.get("zoaf_cfg") or {}).get("recipe") or ""
    if r.get("wl_hash") and not rec.startswith("nf-v1"):
        pre_run.add(r["wl_hash"])
h, f = wl_features(Topology(toks))
print(f"{TARGET}: wl_hash_in_reference={h in hashes}  in_prior_store={h in pre_run}")
sims = nn_similarity(f, feats)
print("nn_similarity vs reference:", sims)
