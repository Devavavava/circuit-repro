"""Audit what `templates.emit_winners` would actually select for P5-v8, BEFORE
emitting (FINDINGS §26).

Two things need checking and neither is visible from the emitted JSON:

 1. **Does the new NF-gated label domain get in at all?** `emit_winners` filters
    only on `spec`, never on `recipe` or `zoaf_cfg.nf_gated`, so the domain is
    included by construction -- but it also *ranks across* both domains with one
    `spec.objective`, which §13 warned against. If the spec gates `nf_db`, a
    tier-1-era row with no NF reads as fully violated and sinks. That is a real
    selection effect on the training data and it should be a measured number,
    not a guess.
 2. **Do the specific designs this iteration is supposed to teach survive the
    top-quartile cut?** The named Gate-D3 / novel tier-1 winners are the reason
    for the run; if the quartile drops them the run teaches something else.

    python lna/_v8_winners_audit.py --specs wifi24,gps-l1,dhruva-l1,dhruva-l5,dhruva-l2,dhruva-s,wideband-sdr
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds  # noqa: E402
from spec import Spec  # noqa: E402

# the designs this expert-iteration round is meant to feed back (coordinator's list)
NAMED = {
    "ace8383c2fa68d03": "dhruva-s Gate-D3 winner (NF 3.24)",
    "ced0d8bd36ed4890": "dhruva-s Gate-D3 winner (NF 3.253)",
    "f578743ae13296d0": "18-device dhruva-s",
    "8c7592ea859e489a": "evolved dhruva-s (rung 2)",
    "20bca9a7c3a5f263": "generated dhruva-l1 tier-1 (seq0192)",
    "396b90321529157a": "wifi24 tier-2 (seq0220)",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--specs", default="wifi24")
    ap.add_argument("--top-q", type=float, default=0.25)
    args = ap.parse_args()
    all_rows = list(ds.load("topo_labels"))
    print(f"store: {len(all_rows)} rows\n")
    kept_hashes = {}
    print(f"{'spec':<14} {'pool':>5} {'keep':>5} {'feas':>5} "
          f"{'kept nf_gated':>14} {'kept tier1':>11}  worst kept objective")
    for spec_name in [s for s in args.specs.split(",") if s]:
        spec = Spec.load(spec_name)
        scored = []
        for r in all_rows:
            if r.get("spec") != spec_name:
                continue
            toks = (r.get("graph") or {}).get("tokens")
            m = r.get("metrics")
            if toks and m:
                scored.append((spec.objective(m), bool(r.get("feasible")), r))
        scored.sort(key=lambda x: x[0])
        keep = scored[:max(1, int(args.top_q * len(scored)))] if scored else []
        ng = sum(1 for _, _, r in keep if (r.get("zoaf_cfg") or {}).get("nf_gated"))
        nf = sum(1 for _, f, _ in keep if f)
        for _, _, r in keep:
            kept_hashes.setdefault(r.get("wl_hash"), []).append(spec_name)
        worst = f"{keep[-1][0]:.3f}" if keep else "-"
        print(f"{spec_name:<14} {len(scored):>5} {len(keep):>5} {nf:>5} "
              f"{ng:>14} {len(keep)-ng:>11}  {worst}")

    print("\nnamed designs this round is meant to feed back:")
    for h, what in NAMED.items():
        hits = [r for r in all_rows if r.get("wl_hash") == h]
        specs = sorted({r.get("spec") for r in hits})
        got = kept_hashes.get(h)
        print(f"  {h}  {'KEPT ' + ','.join(got) if got else 'DROPPED':<28} "
              f"({len(hits)} store rows, specs {specs})  {what}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
