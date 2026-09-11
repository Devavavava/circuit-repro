#!/usr/bin/env python
"""externals-gf180-v0 prep: validate round-1 external templates and emit
tokens + per-family cells files for the x0v1_run.py sizing engine.

Gates per template (any failure -> family dropped and logged, per pre-reg):
parse -> round-trip (Eulerian tokens) -> Topology.valid -> WL hash + novelty
vs ref-v3 -> L0 structural_screen vs cap-e01-wifi -> gf180 bias sweep.

Zero store writes. Outputs under kaggle/externals/: <id>.tokens.json,
cells-<id>.json (all 24 ladder specs -> this family's tokens), MANIFEST.json.
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "kaggle" / "loop"))

import proposal  # kaggle/loop/proposal.py  # noqa: E402
from lna.topology import Topology  # noqa: E402
from lna import novelty  # noqa: E402
from lna.spec import Spec  # noqa: E402
from lna import bias  # noqa: E402

FAMILIES = ["c1-inddegen-cascode", "c3-current-reuse", "c4-shunt-feedback"]
EXT = REPO / "kaggle" / "externals"
LADDER = json.loads((REPO / "kaggle/specs-ladder/ladder.json").read_text())
L0_SPEC = REPO / "kaggle/specs-ladder/cap-e01-wifi.yaml"


def main():
    manifest = {"prepared": time.strftime("%Y-%m-%d %H:%M"), "families": {}}
    ok_all = True
    ref_hashes, _feats, ref_meta = novelty.reference()
    manifest["novelty_ref"] = {k: ref_meta.get(k) for k in
                               ("version", "n_hashes", "digest")}
    spec = Spec.load(str(L0_SPEC))
    for fam in FAMILIES:
        rec = {"net_file": f"kaggle/externals/{fam}.net", "gates": {}}
        manifest["families"][fam] = rec
        body = "\n".join(
            ln for ln in (EXT / f"{fam}.net").read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("*"))
        rt = proposal.round_trip(body)
        rec["gates"]["parse"] = rt["error"] is None or "Parse" not in str(rt["error"])
        if not rt["ok"]:
            rec["gates"]["round_trip"] = f"FAIL: {rt['error']}"
            ok_all = False
            continue
        rec["gates"]["round_trip"] = True
        tokens = rt["tokens"]
        topo = Topology(list(tokens))
        rec["gates"]["topology_valid"] = bool(topo.valid)
        if not topo.valid:
            ok_all = False
            continue
        rec["wl_hash"] = rt["wl_hash"]
        rec["novel_vs_ref"] = bool(rt["wl_hash"] not in ref_hashes)
        scr = spec.structural_screen(topo)
        rec["gates"]["l0"] = {k: bool(v) for k, v in scr.items()} \
            if isinstance(scr, dict) else bool(scr)
        l0_ok = all(scr.values()) if isinstance(scr, dict) else bool(scr)
        if not l0_ok:
            ok_all = False
            continue
        try:
            bs = bias.insert_bias(topo, sweep=True, pdk="gf180mcu")
            rec["gates"]["gf180_bias"] = bool(bs is not None)
        except Exception as e:
            rec["gates"]["gf180_bias"] = f"FAIL: {e}"
            ok_all = False
            continue
        tf = EXT / f"{fam}.tokens.json"
        tf.write_text(json.dumps(list(tokens)))
        rec["tokens_file"] = f"kaggle/externals/{fam}.tokens.json"
        rec["n_tokens"] = len(tokens)
        cells = {}
        for row in LADDER["specs"]:
            cells[row["name"]] = {
                "novel": rec["novel_vs_ref"] is True,
                "source_record": f"external-round1-{fam}",
                "tokens_file": rec["tokens_file"],
                "wl_hash": rec["wl_hash"],
            }
        (EXT / f"cells-{fam}.json").write_text(json.dumps(cells, indent=1))
        rec["cells_file"] = f"kaggle/externals/cells-{fam}.json"
        print(f"[{fam}] OK wl={rec['wl_hash']} novel={rec['novel_vs_ref']} "
              f"tokens={rec['n_tokens']}")
    (EXT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
