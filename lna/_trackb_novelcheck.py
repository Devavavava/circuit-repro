"""Classify a generation pool: archetype-copy vs corpus-copy vs truly novel."""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import Topology, parse_arrow_file
from novelty import wl_features
from spec import Spec

ref = json.load(open("lna/out/_trackb_ref_hashes.json", encoding="utf-8"))
arch = {a["wl"]: a["name"] for a in ref["archetypes"]}
corp = set(ref["corpus_hashes"])
spec = Spec.load(sys.argv[2] if len(sys.argv) > 2 else "dhruva-l1")
d = sys.argv[1]
seen, n_pass, rows = {}, 0, []
for f in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
    try:
        topo = Topology(parse_arrow_file(f))
    except Exception:
        continue
    if not spec.structural_screen(topo)[0]:
        continue
    n_pass += 1
    h = wl_features(topo)[0]
    seen.setdefault(h, []).append(os.path.basename(f))
na = sum(1 for h in seen if h in arch)
nc = sum(1 for h in seen if h in corp)
nn = sum(1 for h in seen if h not in arch and h not in corp)
print(f"{os.path.basename(d)} vs {spec.name}: {n_pass} screen-passing, "
      f"{len(seen)} distinct -> archetype-copies {na}, corpus-copies {nc}, "
      f"TRULY NOVEL {nn}")
# how many *samples* (not distinct) are archetype copies
sa = sum(len(v) for h, v in seen.items() if h in arch)
print(f"  samples that are archetype copies: {sa}/{n_pass} "
      f"({100.0*sa/max(n_pass,1):.1f}%)")
for h, v in sorted(seen.items(), key=lambda kv: -len(kv[1]))[:8]:
    if h in arch:
        print(f"  x{len(v):<3} {arch[h]:<28} {h}")
