import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import templates as T
A = list(T.archetypes())
out = []
for k in range(120, 125):
    a = A[k]
    t0 = time.time()
    try:
        seqs = T.augment(a["netlist"])
    except Exception as e:
        print(f"{k} {a['name']} FAILED {e}", flush=True); continue
    for s in seqs:
        out.append({"arch": k, "cls": a["cls"], "seq": s})
    print(f"{k} {a['name']}: {len(seqs)} seqs in {time.time()-t0:.0f}s", flush=True)
json.dump({"rows": out}, open("lna/out/_rfbcs3_rows.json", "w"))
print("total", len(out))
