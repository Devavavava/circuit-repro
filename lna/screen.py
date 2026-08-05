"""Score circuits with the LNA structural screen.

Two input modes:

  --corpus    score preprocessed Sequence_total<i>.npy files. Used to calibrate
              the screen: real LNAs (461-492, 1081-1090) should score high and
              other circuit classes should not.

  --generated score '->'-joined sequence files produced by sampling the model.

And two screens:

  (default)   the historical hard-coded 5-criterion screen (topology.lna_score).
  --spec NAME the spec-driven L0 screen derived from lna/specs/NAME.yaml, whose
              criteria vary per target (plans/01-SPEC.md D4). This is what makes
              inductorless LNAs pass under an inductorless-friendly spec instead
              of being rejected unconditionally (H-Q4). `--spec legacy-lna5`
              reproduces the hard-coded screen's numbers exactly.

    python lna/screen.py --corpus --indices 461-492,1081-1090 --label LNA
    python lna/screen.py --corpus --indices 461-492,1081-1090 --spec wifi24
    python lna/screen.py --generated "out/*.txt" --spec wideband-sdr
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import Topology, parse_arrow_file  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "AnalogGenie", "repo"))


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


def load_corpus(indices, per_circuit=None):
    import numpy as np
    seqs = []
    for i in indices:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        arr = np.load(p, allow_pickle=True)
        rows = arr if per_circuit is None else arr[:per_circuit]
        for row in rows:
            seqs.append((i, [str(t) for t in row]))
    return seqs


def report(tagged, label):
    if not tagged:
        print(f"{label}: nothing to score")
        return
    scores, crits = [], {}
    devs, inds, ratios = [], [], []
    valid = 0
    for _, toks in tagged:
        t = Topology(toks)
        s, c = t.lna_score()
        scores.append(s)
        for k, v in c.items():
            crits[k] = crits.get(k, 0) + int(v)
        devs.append(t.n_devices)
        inds.append(t.n_inductors)
        ratios.append(t.inductor_ratio)
        valid += int(t.valid)

    n = len(scores)
    print(f"=== {label}  (n={n}) ===")
    print(f"  structurally valid : {valid}/{n} ({100.0*valid/n:.1f}%)")
    print(f"  devices/circuit    : min={min(devs)} max={max(devs)} "
          f"mean={sum(devs)/n:.1f}")
    print(f"  inductors/circuit  : mean={sum(inds)/n:.2f}  ratio={sum(ratios)/n:.3f}")
    print("  criteria pass rate :")
    for k in ("has_inductor", "inductor_ratio", "has_transistor",
              "has_rf_ports", "lna_sized"):
        print(f"      {k:<16s} {100.0*crits.get(k,0)/n:5.1f}%")
    hist = {s: scores.count(s) for s in range(6)}
    print("  score histogram    : " +
          "  ".join(f"{s}:{hist[s]}" for s in range(6)))
    strict = sum(1 for s in scores if s == 5)
    loose = sum(1 for s in scores if s >= 4)
    print(f"  score==5 (strict)  : {strict}/{n} ({100.0*strict/n:.1f}%)")
    print(f"  score>=4 (loose)   : {loose}/{n} ({100.0*loose/n:.1f}%)")
    print()
    return scores


def report_spec(tagged, label, spec):
    """Spec-driven L0 screen: report per-criterion and overall pass rate.

    Unlike the legacy 0-5 score, the criteria set is derived from the spec, so the
    denominator question changes from "what fraction of all real LNAs pass" to
    "what fraction of real LNAs *of this spec's class* pass" (plans/01-SPEC.md D4).
    """
    if not tagged:
        print(f"{label}: nothing to score")
        return []
    passed = 0
    crit_pass = {}
    crit_seen = {}
    order = []
    devs, inds = [], []
    results = []
    for _, toks in tagged:
        t = Topology(toks)
        ok, crit = spec.structural_screen(t)
        results.append(ok)
        passed += int(ok)
        devs.append(t.n_devices)
        inds.append(t.n_inductors)
        for k, v in crit.items():
            if k not in crit_seen:
                order.append(k)
            crit_seen[k] = crit_seen.get(k, 0) + 1
            crit_pass[k] = crit_pass.get(k, 0) + int(v)

    n = len(results)
    print(f"=== {label}  spec={spec.name} ({spec.band_type})  (n={n}) ===")
    print(f"  devices/circuit    : min={min(devs)} max={max(devs)} "
          f"mean={sum(devs)/n:.1f}")
    print(f"  inductors/circuit  : mean={sum(inds)/n:.2f}")
    print("  L0 criteria (derived from spec) pass rate :")
    for k in order:
        seen = crit_seen[k]
        print(f"      {k:<16s} {100.0*crit_pass[k]/seen:5.1f}%")
    print(f"  PASS (all criteria): {passed}/{n} ({100.0*passed/n:.1f}%)")
    print()
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", action="store_true")
    ap.add_argument("--indices", default="")
    ap.add_argument("--per-circuit", type=int, default=None,
                    help="cap sequences taken per circuit (augmentation makes many)")
    ap.add_argument("--label", default="corpus")
    ap.add_argument("--generated", nargs="*", default=[])
    ap.add_argument("--spec", default=None,
                    help="use the spec-driven L0 screen from lna/specs/<name>.yaml")
    args = ap.parse_args()

    spec = None
    if args.spec:
        from spec import Spec
        spec = Spec.load(args.spec)

    def do(tagged, label):
        if spec is not None:
            report_spec(tagged, label, spec)
        else:
            report(tagged, label)

    if args.corpus:
        idx = parse_indices(args.indices)
        do(load_corpus(idx, args.per_circuit), args.label)

    if args.generated:
        files = []
        for pat in args.generated:
            files.extend(glob.glob(pat))
        tagged = [(f, parse_arrow_file(f)) for f in sorted(files)]
        do(tagged, args.label if not args.corpus else "generated")


if __name__ == "__main__":
    main()
