"""Device-count evidence for the device_budget widening (FINDINGS 21)."""
import os, sys, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from topology import Topology, parse_arrow_file
import numpy as np
from bias import REPO

rows = []
for i in list(range(461, 493)) + list(range(1081, 1091)):
    p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
    if not os.path.exists(p):
        continue
    try:
        t = Topology([str(x) for x in np.load(p, allow_pickle=True)[0]])
    except Exception:
        continue
    rows.append((f"corpus:{i}", t.n_devices, t.n_inductors))
for p in sorted(glob.glob(os.path.join(HERE, "data", "external", "*", "generated", "seq_*.txt"))):
    name = os.path.basename(os.path.dirname(os.path.dirname(p)))
    t = Topology(parse_arrow_file(p))
    rows.append((f"ext:{name}", t.n_devices, t.n_inductors))
rows.sort(key=lambda r: -r[1])
print(f"{'circuit':<26}{'devices':>8}{'L':>4}")
for n, d, l in rows[:14]:
    print(f"{n:<26}{d:>8}{l:>4}")
cnt = collections.Counter(d for _, d, _ in rows)
print("\nhistogram:", dict(sorted(cnt.items())))
ds = sorted(d for _, d, _ in rows)
print(f"n={len(ds)} max={ds[-1]} p90={ds[int(0.9*len(ds))-1]} median={ds[len(ds)//2]}")
print("above 16:", [(n, d) for n, d, _ in rows if d > 16])
