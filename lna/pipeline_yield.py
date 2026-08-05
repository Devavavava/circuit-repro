"""End-to-end pipeline yield: topology -> netlist -> ngspice.

Runs the whole chain over a set of circuits and reports where candidates are
lost. Run it against the dataset's own LNA circuits first: they are known-good
topologies, so anything they lose is a limitation of the *pipeline*, not of the
generative model. That separates the two failure sources before any generated
topology is judged.

    python lna/pipeline_yield.py --indices 461-492,1081-1090
"""
import argparse
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import Topology  # noqa: E402
from to_spice import Netlist  # noqa: E402
from genie_common import REPO  # noqa: E402

NGSPICE = os.environ.get("NGSPICE", r"C:\msys64\ucrt64\bin\ngspice_con.exe")


def parse_indices(spec):
    out = []
    for part in spec.split(","):
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return out


def run_ngspice(path, timeout=90):
    try:
        p = subprocess.run([NGSPICE, "-b", path], capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timeout", ""
    out = (p.stdout or "") + (p.stderr or "")
    low = out.lower()
    if "fatal error" in low or "error:" in low:
        first = next((ln for ln in out.splitlines() if "rror" in ln), "error")
        return False, first.strip()[:90], out
    if "singular matrix" in low:
        return False, "singular matrix", out
    return True, "ok", out


def iter_sources(args):
    """Yield (label, tokens) from either the dataset corpus or a generated dir."""
    if args.generated:
        import glob as _glob
        from topology import parse_arrow_file
        files = sorted(_glob.glob(os.path.join(args.generated, "seq*.txt")))
        for f in files:
            yield os.path.splitext(os.path.basename(f))[0], parse_arrow_file(f)
    else:
        import numpy as np
        for i in parse_indices(args.indices):
            p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
            if not os.path.exists(p):
                yield i, None
                continue
            arr = np.load(p, allow_pickle=True)
            yield i, [str(t) for t in arr[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indices", default="461-492,1081-1090")
    ap.add_argument("--generated", default="",
                    help="directory of generated seq*.txt instead of the corpus")
    ap.add_argument("--min-score", type=int, default=0,
                    help="only evaluate topologies with at least this LNA score")
    ap.add_argument("--keep", default="", help="directory to keep netlists in")
    args = ap.parse_args()

    workdir = args.keep or tempfile.mkdtemp(prefix="lna_yield_")
    os.makedirs(workdir, exist_ok=True)

    stats = {"no_corpus": [], "below_score": [], "invalid": [],
             "not_emittable": [], "sim_fail": [], "ok": []}
    reasons = {}
    considered = 0

    for i, toks in iter_sources(args):
        considered += 1
        if toks is None:
            stats["no_corpus"].append(i)
            continue
        topo = Topology(toks)
        if args.min_score and topo.lna_score()[0] < args.min_score:
            stats["below_score"].append(i)
            continue
        if not topo.valid:
            stats["invalid"].append(i)
            continue
        nl = Netlist(topo)
        bad = nl.missing_pins()
        if bad:
            stats["not_emittable"].append(i)
            reasons[i] = bad[0][1]
            continue
        path = os.path.join(workdir, f"c{i}.cir")
        open(path, "w").write(nl.emit())
        ok, why, _ = run_ngspice(path)
        if ok:
            stats["ok"].append(i)
        else:
            stats["sim_fail"].append(i)
            reasons[i] = why

    total = considered
    print(f"netlists in: {workdir}")
    print(f"\n{'stage':<22}{'count':>7}   {'of total':>9}")
    print("-" * 42)
    for k, label in (("no_corpus", "no preprocessed seq"),
                     ("below_score", "below --min-score"),
                     ("invalid", "structurally invalid"),
                     ("not_emittable", "netlist not emittable"),
                     ("sim_fail", "ngspice failed"),
                     ("ok", "SIMULATES")):
        n = len(stats[k])
        print(f"{label:<22}{n:>7}   {100.0*n/total:>8.1f}%")

    for k in ("not_emittable", "sim_fail"):
        if stats[k]:
            print(f"\n{k} detail:")
            for i in stats[k][:10]:
                print(f"   {i}: {reasons.get(i,'')}")


if __name__ == "__main__":
    main()
