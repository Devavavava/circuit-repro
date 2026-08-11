"""WP-OUTCOME step 3 -- the funnel, four arms, one code path (plans2/11).

Deliberately the same shape as `_attrib_pools.py`, and the same FIXED rung-0
selector, because the two work packages have to be readable side by side:

  A. generation stats   novelty.evaluate over each arm's 256-sample pool,
                        wifi24, ref-v3 -- the frozen protocol, unmodified.
  B. rung-0 pool        screen-passing AND novel-vs-ref-v3 AND WL-deduped AND
                        `_match_struct.analyze` reports `port_src`. All four
                        arms go into ONE pool JSON so a single critic ensemble
                        ranks them (FINDINGS 29.12: a capability claim is only
                        as strong as its selector, so the selector must not vary
                        between arms).

    python lna/_out_pool.py --stage gen
    python lna/_out_pool.py --stage pool --out lna/out/_o/pool.json
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

OUT = os.path.join(HERE, "out", "_o")

#: the adopted baseline's OWN published pool (FINDINGS 24.2: nb NDL 79), reused
#: rather than re-sampled so the control arm is literally the published one.
P5V7 = os.path.join(HERE, "out", "ft_p5v7_nb_s1337")

ARMS = [
    ("P5V7", "P5-v7 adopted baseline, plain class token", [P5V7]),
    ("OUT-U", "outcome arm, UNCONDITIONED (plain class token)",
     [os.path.join(OUT, "ft_p5out_nb_uncond_s1337")]),
    ("OUT-C", "outcome arm, conditioned all-bins-MET",
     [os.path.join(OUT, "ft_p5out_nb_met_s1337")]),
    ("OUT-S", "shuffled control, conditioned all-bins-MET",
     [os.path.join(OUT, "ft_p5outs_nb_met_s1337")]),
]


#: the wb channel is measured under `wideband-sdr`, the way every published wb
#: row in this program was (`_ndl_refv3.POOLS`). It is secondary here -- the
#: funnel is nb/`wifi24` -- so it gets the frozen-protocol row and nothing else.
WB_ARMS = [
    ("P5V7", [os.path.join(HERE, "out", "ft_p5v7_wb_s1337")]),
    ("OUT-U", [os.path.join(OUT, "ft_p5out_wb_uncond_s1337")]),
    ("OUT-C", [os.path.join(OUT, "ft_p5out_wb_met_s1337")]),
    ("OUT-S", [os.path.join(OUT, "ft_p5outs_wb_met_s1337")]),
]

#: sampling-noise replicates of the primary channel (registered in plans2/11 5.1)
REPLICA_ARMS = [
    ("OUT-C@2338", [os.path.join(OUT, "ft_p5out_nb_met_s2338")]),
    ("OUT-S@2338", [os.path.join(OUT, "ft_p5outs_nb_met_s2338")]),
]


def _files(dirs):
    out = []
    for d in dirs:
        out.extend(sorted(glob.glob(os.path.join(d, "seq*.txt"))))
    return out


def stage_gen(specs=("wifi24",)):
    rows = {}
    todo = [(n, k, d) for n in specs
            for k, _, d in ARMS] +            [("wifi24", k, d) for k, d in REPLICA_ARMS] +            [("wideband-sdr", k, d) for k, d in WB_ARMS]
    cache = {}
    for name, key, dirs in todo:
        spec = cache.setdefault(name, Spec.load(name))
        if not _files(dirs):
            print("  %-10s POOL MISSING %s" % (key, dirs))
            continue
        m = NV.evaluate(dirs, spec=spec, ref=NV.DEFAULT_REF)
        rows["%s|%s" % (name, key)] = m
        NV._print_row("%s/%s" % (name, key), m)
    with open(os.path.join(OUT, "gen_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    return rows


def stage_bias(spec_name="wifi24"):
    """All-MOS-conducting rate after rule-based bias, over each arm's
    SCREEN-PASSING samples (the population the sizer would ever see).

    NOT pre-registered: added after FINDINGS 31.8 landed, whose first
    recommendation is to report this number beside NDL because it is "the first
    number in the funnel with any discriminative power". It is reported here as a
    descriptive measurement, never as a decision input -- changing the adoption
    rule is a frozen-protocol decision and the user's, not an executor's. It is
    also the highest-powered readout this work package has of whether the model
    used the label, because it runs over ~170 samples per arm rather than the ~10
    the sizing budget allows. Default bias rules (v1 R-GATE only), inductor_q=12.
    """
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
        print("  %-6s screen-pass %4d  biased+simulable %4d  all-MOS-conducting "
              "%4d (%.1f%% of screen-pass)  %ss"
              % (key, n_pass, n_ok, n_all, pct, out[key]["wall_s"]), flush=True)
    with open(os.path.join(OUT, "bias_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


def stage_pool(spec_name="wifi24", out_path=None):
    """The FIXED rung-0 selector, applied identically to every arm."""
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
                          "port_src": True, "hops": a.get("hops"),
                          "n_series": a.get("n_series"),
                          "n_shunt": a.get("n_shunt")})
        summary[key] = {"n_files": n_files, "l0_pass": n_screen,
                        "novel": n_novel, "wl_distinct_novel": len(seen),
                        "qualifying": kept,
                        "port_src_rate_of_distinct": kept / max(len(seen), 1)}
        print("  %-6s files %4d -> L0 %4d -> novel %4d -> WL-distinct %4d -> "
              "port_src %3d" % (key, n_files, n_screen, n_novel, len(seen), kept))
    obj = {"spec": spec_name, "novelty_ref": ref_tag(ref_meta),
           "selector": "L0 AND novel-vs-ref-v3 AND WL-dedup AND port_src",
           "pool_dir": "WP-OUTCOME combined (4 arms)",
           "n_files": sum(s["n_files"] for s in summary.values()),
           "l0_passing": sum(s["l0_pass"] for s in summary.values()),
           "wl_distinct": sum(s["wl_distinct_novel"] for s in summary.values()),
           "dropped_already_sized_vs_spec": 0,
           "n_candidates": len(cands),
           "per_arm": summary, "candidates": cands}
    out_path = out_path or os.path.join(OUT, "pool.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
    print("wrote %s: %d qualifying candidates" % (out_path, len(cands)))
    return obj


def main():
    ap = argparse.ArgumentParser(description=__doc__)
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
