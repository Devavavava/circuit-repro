"""Verify the Session-6 headline designs: replay, in-box, stability (FINDINGS §17)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds, size as S
from novelty import wl_features, reference
from topology import Topology

TARGETS = [
    ("l3_tier1.json", 0, "dhruva-s", "tier-1 feasible, NF-descended"),
    ("j3_19f7_gain.json", 0, "dhruva-s", "program-best total violation"),
    ("p1_ce39_gain35.json", 1, "dhruva-s", "NF<=3.5 at the highest gain"),
    ("m1_moves.json", None, "dhruva-s", "lowest NF at a held match (aux_path_add)"),
]

toks = {}
for r in ds.load("topo_labels"):
    g = r.get("graph") or {}
    if r.get("wl_hash") and g.get("tokens"):
        toks.setdefault(r["wl_hash"], g["tokens"])

try:
    ref = reference()
    ref_hashes = set(ref["hashes"]) if isinstance(ref, dict) else set(ref)
except Exception as e:
    ref_hashes, ref = None, str(e)

for fn, idx, spec_name, label in TARGETS:
    recs = json.load(open(os.path.join(HERE, "out", "_nf", fn)))
    if idx is None:
        recs = sorted(recs, key=lambda r: (r["metrics"] or {}).get("nf_db") or 1e9)
        rec = recs[0]
    else:
        rec = recs[idx]
    h = rec.get("wl_hash") or (rec.get("origin") or {}).get("store_wl_hash")
    spec = S._spec_for_sizing(spec_name)
    topo = Topology(toks[h])
    prep = S.prepared_body(topo, inductor_q=12)
    m = S.eval_metrics(prep[0], rec["best_params"], spec, nf_gated=True)
    stored = rec["metrics"]
    ok = S.replay_ok(topo, rec["best_params"], spec, stored, sigma=1.0)
    rng = S.kind_ranges(spec)
    _, sizable, _ = prep
    oob = []
    for k, v in rec["best_params"].items():
        kind = sizable.get(k)
        if kind not in rng:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        lo, hi = rng[kind][0], rng[kind][1]
        if x < lo * (1 - 1e-9) or x > hi * (1 + 1e-9):
            oob.append((k, x, lo, hi))
    feas, viol = spec.feasible(m)
    novel = (h not in ref_hashes) if ref_hashes else None
    print(f"--- {label}\n    {fn}[{idx}]  wl {h}  devices {len(topo.devices)}")
    print(f"    replayed: S11* {m['s11_max_db']:.2f}  S21 {m['s21_db']:.2f}  "
          f"Idd {m['idd_ma']:.2f}  NF {m['nf_db']:.3f}  K_min {m['k_min']:.3g}")
    print(f"    stored  : S11* {stored['s11_max_db']:.2f}  S21 {stored['s21_db']:.2f}  "
          f"Idd {stored['idd_ma']:.2f}  NF {stored['nf_db']:.3f}")
    print(f"    replay_ok={ok}  in_box={not oob}{'' if not oob else ' OOB=' + str(oob)}  "
          f"K>=1={m['k_min'] >= 1}  tier2_feasible={feas}  viol={sum(viol.values()):.3f} "
          f"({','.join(viol) or '-'})  novel_vs_ref={novel}", flush=True)
