"""Structural triage of a pool: find truly-novel, rfb_cs3-LIKE (multi-stage) candidates."""
import sys, os, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import Topology, parse_arrow_file, base_of
from novelty import wl_features
from spec import Spec

ref = json.load(open("lna/out/_trackb_ref_hashes.json", encoding="utf-8"))
arch = {a["wl"]: a["name"] for a in ref["archetypes"]}
corp = set(ref["corpus_hashes"])
spec = Spec.load("dhruva-l1")
d = sys.argv[1]
rows, seen = [], set()
for f in sorted(glob.glob(os.path.join(d, "seq*.txt"))):
    try:
        topo = Topology(parse_arrow_file(f))
    except Exception:
        continue
    if not spec.structural_screen(topo)[0]:
        continue
    h = wl_features(topo)[0]
    if h in seen:
        continue
    seen.add(h)
    if h in arch or h in corp:
        continue
    c = collections.Counter(base_of(x) for x in topo.devices)
    n_act = c.get("NM", 0) + c.get("PM", 0)
    rows.append((n_act, topo.n_inductors, c.get("R", 0), topo.n_devices,
                 os.path.basename(f), h))
rows.sort(key=lambda r: (-r[0], -r[1]))
print(f"{d}: {len(rows)} truly-novel screen-passing distinct")
print(f"{'file':<14} {'act':>3} {'L':>2} {'R':>2} {'dev':>3}  wl")
for r in rows[:22]:
    print(f"{r[4]:<14} {r[0]:>3} {r[1]:>2} {r[2]:>2} {r[3]:>3}  {r[5]}")
multi = [r for r in rows if r[0] >= 2 and r[1] >= 2 and r[2] >= 1]
print(f"\nmulti-stage-like (>=2 active, >=2 L, >=1 R): {len(multi)}")
for r in multi:
    print(f"  {r[4]:<14} act={r[0]} L={r[1]} R={r[2]} dev={r[3]} {r[5]}")
