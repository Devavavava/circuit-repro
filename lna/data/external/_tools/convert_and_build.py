"""Convert an external SPICE netlist into a token sequence and validate it.

This is a data-scout tool (owned under lna/data/external/**), not part of the
shared pipeline. It reuses:
  * spice2genie.py (adapted from the analoggenie-dataset-expansion worktree's
    dataset_expansion/spice2genie.py -- SPICE -> AnalogGenie .cir/Port format)
  * AnalogGenie/repo's own SPICE2GRAPH_compress.py / Augmentation.py functions,
    execed read-only exactly the way lna/build_lna_corpus.py does (only the
    function definitions, never the driver loop) -- no shared file is edited.
  * lna/topology.py, imported read-only for the structural screen.

It never writes into AnalogGenie/repo/Dataset -- everything lands under
lna/data/external/<name>/.

Usage: python convert_and_build.py
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
EXTERNAL = os.path.dirname(HERE)
LNA_DIR = os.path.dirname(os.path.dirname(EXTERNAL))          # .../lna
REPO_ROOT = os.path.dirname(LNA_DIR)                           # worktree root
ANALOGGENIE_REPO = os.path.join(REPO_ROOT, "AnalogGenie", "repo")

sys.path.insert(0, HERE)
sys.path.insert(0, LNA_DIR)
import spice2genie as s2g          # noqa: E402
from topology import Topology       # noqa: E402


def load_functions(script_name, driver_marker):
    path = os.path.join(ANALOGGENIE_REPO, script_name)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    idx = src.find(driver_marker)
    if idx == -1:
        raise RuntimeError(f"driver marker {driver_marker!r} not found in {script_name}")
    ns = {"__name__": "_ext_shim"}
    exec(compile(src[:idx], script_name, "exec"), ns)
    return ns


def build_matrix(cir_text, port_line):
    ns = load_functions("SPICE2GRAPH_compress.py", "\nstart = 1")
    netlist = [ln.replace("(", "").replace(")", "").split()
               for ln in cir_text.strip().splitlines() if ln.strip()]
    matrix, _ = ns["build_connection_matrix"](netlist, port_line.split())
    return matrix


def eulerian_path(matrix, max_solutions=50, run_num=10):
    ns = load_functions("Augmentation.py", "\nbase_dirs = {")
    paths = ns["dfs_all_paths"](matrix, start_node="VSS",
                                 max_solutions=max_solutions, run_num=run_num)
    covers = ns["check_if_path_covers_all_edges_exactly_once"]
    good = [p for p in paths if covers(matrix, p)]
    return good


def convert_one(name, source_path, outdir, declared_ports=None, strip_parens=False):
    with open(source_path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if strip_parens:
        text = text.replace("(", " ").replace(")", " ")

    cir, ports, stats = s2g.convert(text, declared_ports=declared_ports, name=name)

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"{name}.cir"), "w", encoding="utf-8") as fh:
        fh.write(cir)
    with open(os.path.join(outdir, f"Port_{name}.txt"), "w", encoding="utf-8") as fh:
        fh.write(ports)

    matrix = build_matrix(cir, ports)
    matrix.to_csv(os.path.join(outdir, f"Graph_{name}.csv"))

    paths = eulerian_path(matrix)
    result = {"name": name, "stats": stats, "n_eulerian_paths": len(paths)}
    if not paths:
        result["error"] = "no Eulerian path covering all edges from VSS"
        return result, None

    tokens = paths[0]
    seq_text = "->".join(tokens)
    seq_path = os.path.join(outdir, f"seq_{name}.txt")
    with open(seq_path, "w", encoding="utf-8") as fh:
        fh.write(seq_text)

    topo = Topology(list(tokens))
    score, crit = topo.lna_score()
    result.update({
        "seq_len": len(tokens),
        "valid_structure": topo.valid,
        "floating_devices": sorted(topo.floating_devices()),
        "lna_score": score,
        "lna_criteria": crit,
        "device_counts": topo.counts(),
        "seq_path": seq_path,
    })
    return result, seq_path


CIRCUITS = [
    dict(name="ihp_gps_lna_nmos",
         source=os.path.join(EXTERNAL, "ihp-gps-lna-nmos", "cleaned_core.spice"),
         outdir=os.path.join(EXTERNAL, "ihp-gps-lna-nmos", "generated"),
         strip_parens=False),
    dict(name="ihp_gps_lna_npn",
         source=os.path.join(EXTERNAL, "ihp-gps-lna-npn", "cleaned_core.spice"),
         outdir=os.path.join(EXTERNAL, "ihp-gps-lna-npn", "generated"),
         strip_parens=False),
    dict(name="align_lna_qm",
         source=os.path.join(EXTERNAL, "align-lna-qm", "cleaned_core.txt"),
         outdir=os.path.join(EXTERNAL, "align-lna-qm", "generated"),
         strip_parens=True),
]


def main():
    results = []
    for spec in CIRCUITS:
        try:
            res, seq_path = convert_one(spec["name"], spec["source"], spec["outdir"],
                                         strip_parens=spec.get("strip_parens", False))
        except s2g.ConversionError as exc:
            res = {"name": spec["name"], "error": f"ConversionError: {exc}"}
        results.append(res)
        print(json.dumps(res, indent=2, default=str))
        print("-" * 60)

    summary_path = os.path.join(EXTERNAL, "_tools", "convert_results.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nsummary written to {summary_path}")


if __name__ == "__main__":
    main()
