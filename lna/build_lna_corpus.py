"""Build an LNA-only corpus from the AnalogGenie dataset.

AnalogGenie's preprocessing scripts hardcode the full index range 1..3502 in a
module-level driver, so they cannot be pointed at a subset. Rather than patch
upstream, this script execs only the *function definitions* from each script
(everything above its driver) and then drives the pipeline itself over the LNA
indices only.

LNA indices come from Dataset/data_categorization.md:
    461-492   Razavi, RF Microelectronics -- "low noise amplifiers"
    1081-1090 assorted "LNA papers"

Stage 1  SPICE2GRAPH_compress  netlist  -> Graph<i>.csv     (adjacency matrix)
Stage 2  Augmentation          adjacency-> Sequence_total<i>.npy
                               (Eulerian DFS paths from VSS, padded to 1025)

Usage (from anywhere):
    python lna/build_lna_corpus.py --stage all
    python lna/build_lna_corpus.py --stage graph --indices 461-470
"""
import argparse
import os
import sys
import time

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "AnalogGenie", "repo")
REPO = os.path.abspath(REPO)

LNA_RANGES = [(461, 492), (1081, 1090)]


def lna_indices():
    out = []
    for lo, hi in LNA_RANGES:
        out.extend(range(lo, hi + 1))
    return out


def parse_indices(spec):
    if not spec:
        return lna_indices()
    out = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def load_functions(script_name, driver_marker):
    """Exec a script's function definitions, stopping before its driver loop."""
    path = os.path.join(REPO, script_name)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    idx = src.find(driver_marker)
    if idx == -1:
        raise RuntimeError(f"driver marker {driver_marker!r} not found in {script_name}; "
                           "upstream layout changed")
    ns = {"__name__": "_lna_shim"}
    exec(compile(src[:idx], script_name, "exec"), ns)
    return ns


def stage_graph(indices):
    ns = load_functions("SPICE2GRAPH_compress.py", "\nstart = 1")
    read_netlist = ns["read_netlist"]
    read_ports = ns["read_ports"]
    build_connection_matrix = ns["build_connection_matrix"]

    made, skipped = [], []
    for i in indices:
        n = str(i)
        netlist_file = os.path.join("Dataset", n, f"{n}.cir")
        port_file = os.path.join("Dataset", n, f"Port{n}.txt")
        if not os.path.isfile(netlist_file) or not os.path.isfile(port_file):
            skipped.append(i)
            continue
        netlist = read_netlist(netlist_file)
        ports = read_ports(port_file)
        matrix, _ = build_connection_matrix(netlist, ports)
        out = os.path.join("Dataset", n, f"Graph{n}.csv")
        matrix.to_csv(out)
        made.append((i, matrix.shape[0]))
    return made, skipped


def stage_augment(indices, max_solutions, run_num):
    import numpy as np
    ns = load_functions("Augmentation.py", "\nbase_dirs = {")
    read_connection_matrix = ns["read_connection_matrix"]
    dfs_all_paths = ns["dfs_all_paths"]
    covers = ns["check_if_path_covers_all_edges_exactly_once"]

    results, failed = [], []
    for i in indices:
        n = str(i)
        graph = os.path.join("Dataset", n, f"Graph{n}.csv")
        if not os.path.isfile(graph):
            failed.append((i, "no Graph csv"))
            continue
        t0 = time.time()
        try:
            matrix = read_connection_matrix(graph)
            paths = dfs_all_paths(matrix, start_node="VSS",
                                  max_solutions=max_solutions, run_num=run_num)
            if not paths:
                failed.append((i, "no Eulerian path from VSS"))
                continue
            if not all(covers(matrix, p) for p in paths):
                failed.append((i, "path does not cover edges exactly once"))
                continue
            padded = [p + ["TRUNCATE"] * (1025 - len(p)) for p in paths if len(p) <= 1025]
            if not padded:
                failed.append((i, "all paths longer than 1025"))
                continue
            np.save(os.path.join("Dataset", n, f"Sequence_total{n}.npy"), padded)
            results.append((i, len(padded), len(paths[0]), time.time() - t0))
        except Exception as exc:                      # upstream raises broadly
            failed.append((i, f"{type(exc).__name__}: {exc}"))
    return results, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["graph", "augment", "all"], default="all")
    ap.add_argument("--indices", default="", help="e.g. 461-470,1081")
    ap.add_argument("--max-solutions", type=int, default=200)
    ap.add_argument("--run-num", type=int, default=10)
    args = ap.parse_args()

    indices = parse_indices(args.indices)
    os.chdir(REPO)                      # upstream paths are relative to the repo
    print(f"repo      : {REPO}")
    print(f"indices   : {len(indices)} circuits")

    if args.stage in ("graph", "all"):
        t0 = time.time()
        made, skipped = stage_graph(indices)
        print(f"\n[graph]   built {len(made)} adjacency matrices in {time.time()-t0:.1f}s")
        if skipped:
            print(f"[graph]   skipped (missing files): {skipped}")
        if made:
            sizes = [s for _, s in made]
            print(f"[graph]   node counts: min={min(sizes)} max={max(sizes)} "
                  f"mean={sum(sizes)/len(sizes):.1f}")

    if args.stage in ("augment", "all"):
        t0 = time.time()
        res, failed = stage_augment(indices, args.max_solutions, args.run_num)
        total_seqs = sum(c for _, c, _, _ in res)
        print(f"\n[augment] {len(res)} circuits -> {total_seqs} sequences "
              f"in {time.time()-t0:.1f}s")
        if res:
            lens = [L for _, _, L, _ in res]
            print(f"[augment] raw path length: min={min(lens)} max={max(lens)} "
                  f"mean={sum(lens)/len(lens):.1f}")
            slow = sorted(res, key=lambda r: -r[3])[:5]
            print("[augment] slowest: " +
                  ", ".join(f"{i}({t:.1f}s,{c} seqs)" for i, c, _, t in slow))
        if failed:
            print(f"[augment] failed {len(failed)}:")
            for i, why in failed[:12]:
                print(f"            {i}: {why}")


if __name__ == "__main__":
    main()
