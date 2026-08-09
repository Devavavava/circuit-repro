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

### The corpus is 41 dataset circuits PLUS an external set (`--stage external`)

Real LNA topologies converted from outside the AnalogGenie dataset -- open
tapeouts (IHP SG13G2), permissively-licensed example libraries (ALIGN), and
cited paper transcriptions -- live under `lna/data/external/<id>/` with a
`provenance.json` each, and are ingested through the *same* Stage-2 Eulerian
augmentation as the dataset circuits. They are deliberately NOT written into
`AnalogGenie/repo/Dataset/`: that tree is an untracked upstream clone (usually a
junction into the main checkout), so writing new indices there would mutate
shared state that nothing in this repo owns and that a fresh worktree does not
have. Instead each circuit keeps its sequences beside its own provenance, and
`external_manifest()` / `external_sequences()` are the read APIs -- see
`lna/data/external/corpus_manifest.json`, which carries the provenance id, the
WL hash, the screen score and the validation verdict for every ingested row.

    python lna/build_lna_corpus.py --stage all
    python lna/build_lna_corpus.py --stage graph --indices 461-470
    python lna/build_lna_corpus.py --stage external            # ingest lna/data/external
    python lna/build_lna_corpus.py --stage external --external-id ihp-gps-lna-npn
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "AnalogGenie", "repo")
REPO = os.path.abspath(REPO)

LNA_RANGES = [(461, 492), (1081, 1090)]

EXTERNAL_DIR = os.path.join(HERE, "data", "external")
EXTERNAL_MANIFEST = os.path.join(EXTERNAL_DIR, "corpus_manifest.json")
# Ingestion recipe tag. Bump if the augmentation budget or the validation gates
# change, the way label recipes are bumped -- the manifest stamps it per row.
INGEST_RECIPE = "ingest-v1"
SEQ_PAD = 1025                      # upstream's Sequence_total padding width

# Augmentation budget for the external set. The dataset stage uses 200/10; that
# is NOT affordable here and the reason is upstream's cover check, which rebuilds
# the whole edge set with pandas `.loc` scalar lookups (O(N^2) per candidate
# path) on every branch attempt. Measured on this batch at 20 solutions / 2 runs:
# 2.8 s (20-node matrix) to 53 s (81-node), ~200 s for all nine; a single
# 20-node circuit at the dataset's 200/10 did not finish in 10 minutes. 64/3
# lands every external circuit inside the dataset's own per-circuit spread
# (measured over the 41: min 1, median 69, mean 98, max 200 -- 16 of 41 sit on
# the 200 cap) at a few minutes for the batch. The budget is stamped in the
# manifest, so a future run that wants full parity can raise it knowingly (the
# real fix is an accelerated -- and equivalence-tested -- cover check).
EXT_MAX_SOLUTIONS = 64
EXT_RUN_NUM = 3
# ...and one circuit still will not finish at 64/3 in any reasonable time (the
# 21-device SiGe HBT LNA: an 81-node matrix and a 397-token Eulerian path, so the
# cover check costs ~6.5k pandas lookups per candidate branch). Rather than drop
# it, or let the whole batch hang on it, each circuit gets a wall-clock budget and
# falls back down this ladder until one completes. The budget that actually
# produced a circuit's sequences is recorded per circuit in the manifest, so the
# run stays reproducible even though it is deliberately not uniform.
EXT_BUDGET_LADDER = [(64, 3), (20, 2), (8, 1)]
EXT_TIMEOUT_S = 300


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


# --------------------------------------------------------- external corpus
def external_dirs(only=None):
    """Candidate external circuit directories (each holds a provenance.json)."""
    if not os.path.isdir(EXTERNAL_DIR):
        return []
    out = []
    for name in sorted(os.listdir(EXTERNAL_DIR)):
        if name.startswith("_"):                       # _tools/ etc.
            continue
        d = os.path.join(EXTERNAL_DIR, name)
        if os.path.isfile(os.path.join(d, "provenance.json")):
            if only is None or name in only:
                out.append((name, d))
    return out


def _external_paths(name, d):
    """(graph csv, token file, sequence npy) for one external circuit. The
    scout's converter names its artefacts after the circuit's own id with dashes
    turned into underscores, so both spellings are tried rather than assumed."""
    gen = os.path.join(d, "generated")
    stem = name.replace("-", "_")
    graph = os.path.join(gen, f"Graph_{stem}.csv")
    seq = os.path.join(gen, f"seq_{stem}.txt")
    npy = os.path.join(gen, f"Sequence_total_{stem}.npy")
    return graph, seq, npy


def stage_external(only=None, max_solutions=EXT_MAX_SOLUTIONS,
                   run_num=EXT_RUN_NUM):
    """Eulerian-augment every external circuit, exactly as `stage_augment` does
    for a dataset index. Returns (results, failed).

    The augmentation is the upstream code, execed read-only from
    `Augmentation.py` -- same `dfs_all_paths`, same `check_if_path_covers...`
    edge-cover gate, same 1025 padding -- so an ingested circuit is
    indistinguishable from a dataset one at the point where a trainer or the
    novelty reference consumes it."""
    import numpy as np
    ns = load_functions("Augmentation.py", "\nbase_dirs = {")
    read_connection_matrix = ns["read_connection_matrix"]
    dfs_all_paths = ns["dfs_all_paths"]
    covers = ns["check_if_path_covers_all_edges_exactly_once"]

    results, failed = [], []
    for name, d in external_dirs(only):
        graph, seq, npy = _external_paths(name, d)
        if not os.path.isfile(graph):
            failed.append((name, "no Graph csv"))
            continue
        t0 = time.time()
        try:
            matrix = read_connection_matrix(graph)
            paths = dfs_all_paths(matrix, start_node="VSS",
                                  max_solutions=max_solutions, run_num=run_num)
            if not paths:
                failed.append((name, "no Eulerian path from VSS"))
                continue
            if not all(covers(matrix, p) for p in paths):
                failed.append((name, "path does not cover edges exactly once"))
                continue
            padded = [p + ["TRUNCATE"] * (SEQ_PAD - len(p))
                      for p in paths if len(p) <= SEQ_PAD]
            if not padded:
                failed.append((name, f"all paths longer than {SEQ_PAD}"))
                continue
            np.save(npy, padded)
            results.append((name, len(padded), len(paths[0]), time.time() - t0))
        except Exception as exc:                      # upstream raises broadly
            failed.append((name, f"{type(exc).__name__}: {exc}"))
    return results, failed


def _external_budget_path(d):
    return os.path.join(d, "generated", "augment_budget.json")


def external_budget(cid, d=None):
    """The (max_solutions, run_num) that actually produced this circuit's
    sequences, or None if it has not been augmented."""
    d = d or os.path.join(EXTERNAL_DIR, cid)
    p = _external_budget_path(d)
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def stage_external_guarded(only=None, ladder=None, timeout=EXT_TIMEOUT_S):
    """Run `stage_external` per circuit in a worker subprocess with a wall-clock
    guard, stepping down `ladder` on timeout.

    A subprocess (rather than a thread) because upstream's `dfs_all_paths` is a
    tight pure-Python loop with no cancellation point -- there is nothing to
    interrupt from inside the interpreter. Each success writes
    `generated/augment_budget.json` beside the sequences."""
    import subprocess
    ladder = ladder or EXT_BUDGET_LADDER
    done, failed = [], []
    for name, d in external_dirs(only):
        chosen = None
        for ms, rn in ladder:
            t0 = time.time()
            cmd = [sys.executable, os.path.abspath(__file__), "--stage", "external",
                   "--external-id", name, "--max-solutions", str(ms),
                   "--run-num", str(rn)]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=timeout)
            except subprocess.TimeoutExpired:
                print(f"  {name:<22} {ms}/{rn} timed out after {timeout}s, "
                      f"stepping down", flush=True)
                continue
            _, _, npy = _external_paths(name, d)
            if r.returncode == 0 and os.path.exists(npy):
                chosen = {"max_solutions": ms, "run_num": rn,
                          "seconds": round(time.time() - t0, 1),
                          "timeout_s": timeout, "pad": SEQ_PAD}
                with open(_external_budget_path(d), "w", encoding="utf-8",
                          newline="\n") as fh:
                    json.dump(chosen, fh, indent=1)
                break
            print(f"  {name:<22} {ms}/{rn} failed: "
                  f"{(r.stdout + r.stderr).strip().splitlines()[-1:] or ['?']}",
                  flush=True)
        if chosen:
            import numpy as np
            n = np.load(_external_paths(name, d)[2], allow_pickle=True).shape[0]
            print(f"  {name:<22} OK  {n:>3} seqs at "
                  f"{chosen['max_solutions']}/{chosen['run_num']} "
                  f"in {chosen['seconds']}s", flush=True)
            done.append((name, n, chosen))
        else:
            failed.append((name, "no budget on the ladder completed in time"))
    return done, failed


def external_manifest(path=EXTERNAL_MANIFEST):
    """The ingested external corpus: {"circuits": [...]} or None if not built.

    Only rows with `ingested: true` belong to the corpus; a quarantined row stays
    in the file with the reason it failed, because "we looked at it and rejected
    it" is a different (and more useful) statement than silence."""
    if not os.path.isfile(path):
        return None
    return json.load(open(path, encoding="utf-8"))


def external_ids(path=EXTERNAL_MANIFEST):
    m = external_manifest(path)
    return [c["id"] for c in m["circuits"] if c.get("ingested")] if m else []


def external_sequences(path=EXTERNAL_MANIFEST, ingested_only=True):
    """[(id, [token-list, ...]), ...] -- the augmented rows, ready to be mixed
    into a training set the same way `Sequence_total<i>.npy` rows are. Padding is
    left on, so a caller's existing `_rows_from_npy`-style loader needs no
    special case."""
    import numpy as np
    m = external_manifest(path)
    if not m:
        return []
    out = []
    for c in m["circuits"]:
        if ingested_only and not c.get("ingested"):
            continue
        npy = os.path.join(EXTERNAL_DIR, c["id"], "generated",
                           f"Sequence_total_{c['id'].replace('-', '_')}.npy")
        if not os.path.exists(npy):
            continue
        arr = np.load(npy, allow_pickle=True)
        out.append((c["id"], [[str(t) for t in row] for row in arr]))
    return out


def external_topologies(path=EXTERNAL_MANIFEST, ingested_only=True):
    """[(id, Topology), ...] built from each circuit's first augmented path --
    the canonical representative, matching how novelty.corpus_reference() takes
    row 0 of a dataset circuit's Sequence_total."""
    sys.path.insert(0, HERE)
    from topology import Topology                       # noqa: E402
    return [(cid, Topology(rows[0]))
            for cid, rows in external_sequences(path, ingested_only) if rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["graph", "augment", "all", "external"],
                    default="all")
    ap.add_argument("--indices", default="", help="e.g. 461-470,1081")
    ap.add_argument("--external-id", action="append", default=None,
                    help="restrict --stage external to these ids (repeatable)")
    ap.add_argument("--max-solutions", type=int, default=None,
                    help=f"default 200 (dataset stages) / {EXT_MAX_SOLUTIONS} "
                         f"(--stage external)")
    ap.add_argument("--run-num", type=int, default=None,
                    help=f"default 10 (dataset stages) / {EXT_RUN_NUM} "
                         f"(--stage external)")
    ap.add_argument("--timeout", type=int, default=EXT_TIMEOUT_S,
                    help="per-circuit wall-clock guard for --stage external")
    args = ap.parse_args()

    if args.stage == "external" and args.max_solutions is None:
        # orchestrated path: per-circuit wall-clock guard + budget ladder
        print(f"external  : {EXTERNAL_DIR}  (ladder {EXT_BUDGET_LADDER}, "
              f"{EXT_TIMEOUT_S}s each)")
        t0 = time.time()
        done, failed = stage_external_guarded(args.external_id,
                                              timeout=args.timeout)
        print(f"[external] {len(done)} circuits -> "
              f"{sum(n for _, n, _ in done)} sequences in {time.time()-t0:.1f}s")
        for name, why in failed:
            print(f"[external] FAILED {name}: {why}")
        return

    if args.stage == "external":
        print(f"external  : {EXTERNAL_DIR}")
        t0 = time.time()
        res, failed = stage_external(
            args.external_id,
            EXT_MAX_SOLUTIONS if args.max_solutions is None else args.max_solutions,
            EXT_RUN_NUM if args.run_num is None else args.run_num)
        total = sum(c for _, c, _, _ in res)
        print(f"[external] {len(res)} circuits -> {total} sequences "
              f"in {time.time()-t0:.1f}s")
        for name, c, raw, dt in res:
            print(f"           {name:<22} {c:>4} seqs  path_len {raw:>4}  {dt:5.1f}s")
        if failed:
            print(f"[external] failed {len(failed)}:")
            for name, why in failed:
                print(f"           {name}: {why}")
        return

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
        res, failed = stage_augment(
            indices,
            200 if args.max_solutions is None else args.max_solutions,
            10 if args.run_num is None else args.run_num)
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
