"""Build the editcap failure-library for bench-v1's 53 LNA survivors, from the
already-computed null-filter results (no new sims). One dir per survivor cell:
anchor.net + anchor.tokens.json (the best-worst-margin anchor) + evidence.json
(that anchor's sized-and-missed metrics + per-constraint margins), matching the
schema editcap_run.py::_evidence_block reads. Read-only on tracked code.

Best anchor per cell = the (anchor, seed) whose WORST normalized margin is the
least-negative (closest to solving) -- the campaign's stage-6 selection rule.
"""
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "lna"))

from spec import Spec  # noqa: E402

NULL = REPO / "kaggle" / "bench-null-bptm45"
ANCH = REPO / "kaggle" / "bench-anchors" / "lna"
SPECS = REPO / "kaggle" / "bench-specs" / "lna"
OUT = REPO / "kaggle" / "editcap-lib-v11-45nm"
INDEX = json.loads((NULL / "INDEX.json").read_text())


def margins_for(spec, metrics):
    """Per-gated-constraint {achieved, margin, supported}; margin normalized,
    negative==failing (same convention as the null's violations)."""
    out = {}
    worst = None
    for name, c in (spec.constraints or {}).items():
        if c.get("status") == "unsupported":
            continue
        ach = metrics.get(name)
        supported = ach is not None
        margin = None
        if supported:
            scale = spec._scale(c)
            if "min" in c:
                margin = (ach - c["min"]) / scale
            elif "max" in c:
                margin = (c["max"] - ach) / scale
        out[name] = {"achieved": ach, "margin": margin, "supported": supported}
        if margin is not None and (worst is None or margin < worst[1]):
            worst = [name, margin]
    return out, worst


def best_anchor(cell):
    """Return (anchor_fam, seed_record, spec) with the least-negative worst margin."""
    spec = Spec.load(str(SPECS / f"{cell}.yaml"))
    best = None
    for f in NULL.glob(f"lna/{cell}__*.json"):
        r = json.loads(f.read_text())
        fam = r["anchor"]
        for s in r.get("seeds", []):
            m = s.get("metrics") or {}
            if not m:
                continue
            _mg, worst = margins_for(spec, m)
            wm = worst[1] if worst else -1e9
            if best is None or wm > best[0]:
                best = (wm, fam, s, spec)
    return best


def main():
    survivors = [c for c, d in INDEX["cells"].items()
                 if d["class"] == "lna" and d["verdict"] == "SURVIVOR"]
    OUT.mkdir(exist_ok=True)
    built = 0
    for cell in sorted(survivors):
        b = best_anchor(cell)
        if b is None:
            print(f"[skip] {cell}: no sized metrics"); continue
        _wm, fam, srec, spec = b
        m = srec["metrics"]
        mg, worst = margins_for(spec, m)
        band = (spec.raw or {}).get("band", {})
        ev = {
            "spec": cell,
            "band": f"{getattr(spec,'band_type','')} f0={band.get('f0')}",
            "band_type": getattr(spec, "band_type", None),
            "pdk": "bptm45",
            "anchor_family": fam,
            "feasible": False,
            "worst_margin": worst,
            "margins": mg,
            "metrics": m,
            "total_evals": srec.get("n_evals"),
        }
        d = OUT / cell
        d.mkdir(exist_ok=True)
        shutil.copy(ANCH / f"{fam}.net", d / "anchor.net")
        shutil.copy(ANCH / f"{fam}.tokens.json", d / "anchor.tokens.json")
        shutil.copy(SPECS / f"{cell}.yaml", d / "spec.yaml")   # self-contained lib
        (d / "evidence.json").write_text(json.dumps(ev, indent=1))
        built += 1
    print(f"built {built}/{len(survivors)} survivor cell dirs under "
          f"{os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()
