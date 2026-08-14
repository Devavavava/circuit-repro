"""Regression runner for the reference LNA(s) (WP-REF, plans/02-REFERENCE-LNA.md §5).

Runs each reference deck through ngspice, extracts {S11, S21, NF, Idd, Zin},
and checks two things:

  * stability -- every metric within tolerance of its stored baseline
    (+-0.5 dB for dB quantities, +-10% for Idd/Zin), so a future harness change
    that silently shifts a measurement is caught;
  * the ACCEPTANCE gate for that deck -- for the stage-A anchor, S11 <= -10 dB
    across the band (the real Gate G1 requirement) and the measured Re(Zin)
    within +-25% of 1/(gm+gmb) read at the operating point (the end-to-end proof
    that the harness measures impedance correctly -- H-Q2).

Exit code 0 iff every deck passes. Add this to the regression trio (making it a
quartet) once it is green.

    python lna/ref/check_ref.py
    python lna/ref/check_ref.py --update   # re-baseline stored expectations
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from extract import rewrite_includes  # noqa: E402  (portable model-card include)
NGSPICE = os.environ.get("NGSPICE", r"C:\msys64\ucrt64\bin\ngspice_con.exe")
BASELINE = os.path.join(HERE, "ref_baseline.json")

# metric label in the deck's .control output -> (regex, scale to report units)
FIELDS = {
    "idd_ma":         (r"idd\s*=\s*([-\d.eE+]+)", 1e3),
    "gm_mS":          (r"@m1\[gm\]\s*=\s*([-\d.eE+]+)", 1e3),
    "gmb_mS":         (r"@m1\[gmbs\]\s*=\s*([-\d.eE+]+)", 1e3),
    "s11_f0_db":      (r"ref_s11_f0\s*=\s*([-\d.eE+]+)", 1.0),
    "s11_bandmax_db": (r"ref_s11_bandmx\s*=\s*([-\d.eE+]+)", 1.0),
    "s21_f0_db":      (r"ref_s21_f0\s*=\s*([-\d.eE+]+)", 1.0),
    "re_zin":         (r"ref_zre_f0\s*=\s*([-\d.eE+]+)", 1.0),
    "im_zin":         (r"ref_zim_f0\s*=\s*([-\d.eE+]+)", 1.0),
    "nf_f0_db":       (r"ref_nf_f0\s*=\s*([-\d.eE+]+)", 1.0),
}

# per-metric tolerance for the stability check
TOL = {"idd_ma": ("frac", 0.10), "gm_mS": ("frac", 0.10),
       "gmb_mS": ("frac", 0.25), "re_zin": ("frac", 0.10),
       "im_zin": ("abs", 3.0)}
DEFAULT_TOL = ("abs", 0.5)   # dB quantities: +-0.5 dB

DECKS = {
    "ref24_cg.cir": "stage-A common-gate match anchor",
    "ref24_csdeg.cir": "stage-B CS+Cex inductive-degeneration match (F1 fix)",
}


def run_deck(deck):
    path = os.path.join(HERE, deck)
    # The deck's baked `.include ...45nm_bulk.txt` is a dead Windows path off the
    # author's box; run a temp copy with it resolved to this host's model card.
    src = open(path, encoding="utf-8").read()
    fixed = rewrite_includes(src)
    if fixed == src:
        run_path = path
        cleanup = None
    else:
        fd, run_path = tempfile.mkstemp(suffix="_" + deck, prefix="ref_")
        with os.fdopen(fd, "w") as fh:
            fh.write(fixed)
        cleanup = run_path
    try:
        p = subprocess.run([NGSPICE, "-b", run_path], capture_output=True,
                           text=True, timeout=120)
    finally:
        if cleanup:
            os.remove(cleanup)
    text = (p.stdout or "") + (p.stderr or "")
    metrics = {}
    for name, (rx, scale) in FIELDS.items():
        m = re.search(rx, text, re.IGNORECASE)
        if m:
            metrics[name] = float(m.group(1)) * scale
    return metrics


def within(name, got, want):
    kind, tol = TOL.get(name, DEFAULT_TOL)
    if kind == "frac":
        return abs(got - want) <= abs(want) * tol
    return abs(got - want) <= tol


def check_gates(deck, m):
    """Deck-specific acceptance. Returns list of (label, ok, detail)."""
    gates = []
    if deck == "ref24_cg.cir":
        gates.append(("S11 <= -10 dB across band",
                      m["s11_bandmax_db"] <= -10.0,
                      f"S11_bandmax = {m['s11_bandmax_db']:.2f} dB"))
        z_pred = 1e3 / (m["gm_mS"] + abs(m["gmb_mS"]))   # 1/(gm+gmb) in ohm
        rel = abs(m["re_zin"] - z_pred) / z_pred
        gates.append(("Re(Zin) within +-25% of 1/(gm+gmb)  [H-Q2]",
                      rel <= 0.25,
                      f"Re(Zin) = {m['re_zin']:.1f} ohm vs 1/(gm+gmb) = "
                      f"{z_pred:.1f} ohm ({100*rel:.1f}%)"))
    if deck == "ref24_csdeg.cir":
        gates.append(("S11 <= -12 dB across band (the F1-fix match holds)",
                      m["s11_bandmax_db"] <= -12.0,
                      f"S11_bandmax = {m['s11_bandmax_db']:.2f} dB"))
        gates.append(("Re(Zin) within +-20% of 50 ohm",
                      abs(m["re_zin"] - 50.0) / 50.0 <= 0.20,
                      f"Re(Zin) = {m['re_zin']:.1f} ohm"))
        # S21 >= 12 dB and NF <= 2.5 dB are NOT gated here -- deferred to the
        # sizer (WP-SIZE); this deck ships the topology + starting values.
    return gates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true",
                    help="store current metrics as the baseline")
    args = ap.parse_args()

    baseline = {}
    if os.path.exists(BASELINE):
        baseline = json.load(open(BASELINE))

    ok = True
    results = {}
    for deck, desc in DECKS.items():
        m = run_deck(deck)
        results[deck] = m
        print(f"== {deck}: {desc} ==")
        if not m:
            print("   FAILED to extract any metrics (ngspice error?)")
            ok = False
            continue
        for k in ("s11_f0_db", "s11_bandmax_db", "s21_f0_db", "nf_f0_db",
                  "idd_ma", "re_zin", "im_zin", "gm_mS", "gmb_mS"):
            if k not in m:
                continue
            unit = {"idd_ma": "mA", "re_zin": "ohm", "im_zin": "ohm",
                    "gm_mS": "mS", "gmb_mS": "mS"}.get(k, "dB")
            line = f"   {k:<16} {m[k]:>9.3f} {unit}"
            if not args.update and deck in baseline and k in baseline[deck]:
                w = baseline[deck][k]
                good = within(k, m[k], w)
                ok &= good
                line += f"   (baseline {w:.3f}, {'ok' if good else 'DRIFT'})"
            print(line)
        print("   acceptance gates:")
        for label, good, detail in check_gates(deck, m):
            ok &= good
            print(f"     [{'PASS' if good else 'FAIL'}] {label} -- {detail}")
        print()

    if args.update:
        json.dump(results, open(BASELINE, "w"), indent=2)
        print(f"baseline written to {BASELINE}")
        return 0

    print("check_ref: GREEN" if ok else "check_ref: FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
