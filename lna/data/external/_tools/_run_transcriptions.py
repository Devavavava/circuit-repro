import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from transcriptions import CIRCUITS
from topology import Topology
import convert_and_build as cab

results_path = os.path.join(os.path.dirname(__file__), "transcription_results.json")
results = []
for name, spec in CIRCUITS.items():
    t0 = time.time()
    print(f"[{name}] starting...", flush=True)
    outdir = os.path.join(os.path.dirname(__file__), "..", name.replace("_", "-"), "generated")
    os.makedirs(outdir, exist_ok=True)
    cir, ports = spec["cir"], spec["ports"]
    matrix = cab.build_matrix(cir, ports)
    print(f"[{name}] matrix built, {matrix.shape[0]} nodes, {time.time()-t0:.1f}s", flush=True)
    matrix.to_csv(os.path.join(outdir, f"Graph_{name}.csv"))
    paths = cab.eulerian_path(matrix, max_solutions=20, run_num=5)
    print(f"[{name}] eulerian search done, {len(paths)} paths, {time.time()-t0:.1f}s", flush=True)
    res = {"name": name, "n_eulerian_paths": len(paths)}
    if not paths:
        res["error"] = "no Eulerian path"
        results.append(res)
        with open(results_path, "w") as fh:
            json.dump(results, fh, indent=2)
        continue
    tokens = paths[0]
    seq_text = "->".join(tokens)
    with open(os.path.join(outdir, f"seq_{name}.txt"), "w") as fh:
        fh.write(seq_text)
    topo = Topology(list(tokens))
    score, crit = topo.lna_score()
    res.update({
        "seq_len": len(tokens), "valid_structure": topo.valid,
        "floating_devices": sorted(topo.floating_devices()),
        "lna_score": score, "lna_criteria": crit,
        "device_counts": topo.counts(),
    })
    results.append(res)
    with open(results_path, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"[{name}] DONE score={score}/5 {time.time()-t0:.1f}s", flush=True)

print("ALL DONE")
