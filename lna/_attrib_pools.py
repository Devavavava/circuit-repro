"""WP-ATTRIB step 2 -- the identical funnel, four arms (plans2/10 section 1.3).

One code path measures every arm, so no stage can be asymmetric by accident:

  A. generation stats     novelty.evaluate over the arm's two 128-sample halves,
                          against wifi24 AND (addendum) dhruva-l5, ref-v3.
  B. bias / conduction    bias.insert_bias(sweep=True, inductor_q=12) at DEFAULT
                          rules (v1 R-GATE; the v3 DC-return rules stay off, as
                          they are for every other arm in the program).
  C. rung-0 pool          screen-passing AND novel-vs-ref-v3 AND WL-deduped AND
                          _match_struct.port_src -- the FIXED selector. Every
                          arm's qualifying candidates go into ONE pool JSON so a
                          single critic ensemble ranks all four (FINDINGS 29.12:
                          a capability claim is only as strong as its selector,
                          so the selector must not vary between arms).

    python lna/_attrib_pools.py --stage gen
    python lna/_attrib_pools.py --stage bias
    python lna/_attrib_pools.py --stage pool --out lna/out/_at/pool.json
"""
import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _match_struct as MS                                        # noqa: E402
import novelty as NV                                              # noqa: E402
from spec import Spec                                             # noqa: E402
from topology import Topology, parse_arrow_file                   # noqa: E402

OUT = os.path.join(HERE, "out", "_at")

ARMS = [
    ("GR", "grammar-only (no learning)",
     [os.path.join(OUT, "gr_s1337"), os.path.join(OUT, "gr_s2338")]),
    ("GR+RAG", "grammar + retrieval (no learning)",
     [os.path.join(OUT, "rag_s1337"), os.path.join(OUT, "rag_s2338")]),
    ("G2", "AnalogGenie Pretrain.pth, prefix-12 (no fine-tune)",
     [os.path.join(HERE, "out", "sweep12repro"),
      os.path.join(HERE, "out", "sweep12repro_s2338")]),
    ("G3", "P5-v7 (adopted), unconditioned nb",
     [os.path.join(OUT, "p5v7_s1337"), os.path.join(OUT, "p5v7_s2338")]),
]


def _files(dirs):
    out = []
    for d in dirs:
        out.extend(sorted(glob.glob(os.path.join(d, "seq*.txt"))))
    return out


def stage_gen(specs=("wifi24", "dhruva-l5")):
    rows = {}
    for name in specs:
        spec = Spec.load(name)
        for key, _, dirs in ARMS:
            m = NV.evaluate(dirs, spec=spec, ref=NV.DEFAULT_REF)
            rows[(name, key)] = m
            NV._print_row(f"{name}/{key}", m)
    with open(os.path.join(OUT, "gen_stats.json"), "w", encoding="utf-8") as fh:
        json.dump({f"{s}|{a}": v for (s, a), v in rows.items()}, fh, indent=2)
    return rows


def stage_bias(spec_name="wifi24"):
    """Conduction after rule-based bias, over the arm's SCREEN-PASSING samples
    (the population the sizer would ever see). Default bias rules only."""
    import bias
    spec = Spec.load(spec_name)
    out = {}
    for key, _, dirs in ARMS:
        n_pass = n_ok = n_cond = n_all = n_skip = 0
        t0 = time.time()
        for f in _files(dirs):
            try:
                topo = Topology(parse_arrow_file(f))
            except Exception:                                     # noqa: BLE001
                continue
            if not spec.structural_screen(topo)[0]:
                continue
            n_pass += 1
            try:
                nl, ins, rep, swept = bias.insert_bias(topo, sweep=True,
                                                       inductor_q=12)
            except Exception:                                     # noqa: BLE001
                continue
            if rep.get("skipped") or swept is None:
                n_skip += 1
                continue
            n_ok += 1
            n_cond += swept.get("n_conducting") or 0
            n_all += int(bool(swept.get("all_conduct")))
        pct = 100.0 * n_all / max(n_pass, 1)
        out[key] = {"screen_pass": n_pass, "biased_ok": n_ok, "skipped": n_skip,
                    "all_conduct": n_all, "sum_conducting_mos": n_cond,
                    "all_conduct_pct": pct,
                    "wall_s": round(time.time() - t0, 1)}
        print(f"  {key:<7} screen-pass {n_pass:>4}  biased+simulable {n_ok:>4}  "
              f"all-MOS-conducting {n_all:>4} ({pct:.1f}% of screen-pass)  "
              f"{out[key]['wall_s']}s", flush=True)
    with open(os.path.join(OUT, "bias_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


def stage_pool(spec_name="wifi24", out_path=None):
    """The FIXED rung-0 selector, applied identically to all four arms."""
    from novelty import ref_tag, reference, wl_features
    spec = Spec.load(spec_name)
    ref_hashes, _, ref_meta = reference()
    cands, summary = [], {}
    for key, _, dirs in ARMS:
        n_files = n_screen = n_novel = 0
        seen, kept = set(), 0
        for f in _files(dirs):
            n_files += 1
            try:
                topo = Topology(parse_arrow_file(f))
            except Exception:                                     # noqa: BLE001
                continue
            if not spec.structural_screen(topo)[0]:
                continue
            n_screen += 1
            h = wl_features(topo)[0]
            if h in ref_hashes:
                continue
            n_novel += 1
            if h in seen:
                continue
            seen.add(h)
            a = MS.analyze(topo)
            if not a.get("ok") or not a.get("port_src"):
                continue
            kept += 1
            cands.append({"arm": key, "seq": os.path.basename(f),
                          "file": f.replace("\\", "/"), "wl": h,
                          "tokens": list(topo.tokens),
                          "n_dev": topo.n_devices, "n_ind": topo.n_inductors,
                          "novel_ref2": True, "seen_other_spec": False,
                          "port_src": True, "hops": a.get("hops"),
                          "n_series": a.get("n_series"),
                          "n_shunt": a.get("n_shunt")})
        summary[key] = {"n_files": n_files, "l0_pass": n_screen,
                        "novel": n_novel, "wl_distinct_novel": len(seen),
                        "qualifying": kept,
                        "port_src_rate_of_distinct": kept / max(len(seen), 1)}
        print(f"  {key:<7} files {n_files:>4} -> L0 {n_screen:>4} -> novel "
              f"{n_novel:>4} -> WL-distinct {len(seen):>4} -> port_src "
              f"{kept:>3}")
    obj = {"spec": spec_name, "novelty_ref": ref_tag(ref_meta),
           "selector": "L0 AND novel-vs-ref-v3 AND WL-dedup AND port_src",
           "pool_dir": "WP-ATTRIB combined (4 arms)",
           "n_files": sum(s["n_files"] for s in summary.values()),
           "l0_passing": sum(s["l0_pass"] for s in summary.values()),
           "wl_distinct": sum(s["wl_distinct_novel"] for s in summary.values()),
           "dropped_already_sized_vs_spec": 0,
           "n_candidates": len(cands),
           "n_novel_ref2": len(cands), "n_seen_other_spec": 0,
           "per_arm": summary, "candidates": cands}
    out_path = out_path or os.path.join(OUT, "pool.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
    print(f"wrote {out_path}: {len(cands)} qualifying candidates")
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["gen", "bias", "pool"], required=True)
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--out")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.stage == "gen":
        stage_gen()
    elif a.stage == "bias":
        stage_bias(a.spec)
    else:
        stage_pool(a.spec, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
