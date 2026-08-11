"""Pilot parent selection for WP-DIAGHEADS (deterministic, pre-registered).

Rule (fixed before any training or sizing):
  * multi-finger era only (`zoaf_cfg.w_finger == 2e-6`), tokens + best_params present;
  * the row's worst *gated* margin lies in (-0.5, 0.0)  -- a near miss, not a wreck;
  * `n_devices <= device_budget_max - 2`, so a growth move (cascode/degen/stage)
    is legal on the parent;
  * best row per wl_hash, then greedily take the 5 with the largest worst margin
    subject to distinct wl_hash, distinct WL family (datastore._families) and at
    most 3 parents per spec (so the pilot is not five copies of one campaign).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds        # noqa: E402
from spec import Spec         # noqa: E402

GATED = ("s11_db", "s11_max_db", "s21_db", "idd_ma", "nf_db")


def worst_margin(row):
    m = row.get("margins") or {}
    vals = {k: (v or {}).get("margin") for k, v in m.items()
            if k in GATED and (v or {}).get("supported")}
    vals = {k: v for k, v in vals.items() if v is not None}
    if not vals:
        return None, None
    k = min(vals, key=lambda kk: vals[kk])
    return vals[k], k


def select(n=5, lo=-0.5, hi=0.0):
    rows = ds.load("topo_labels")
    budget = {}
    best = {}
    for r in rows:
        if (r.get("zoaf_cfg") or {}).get("w_finger") != 2e-06:
            continue
        g = r.get("graph") or {}
        if not g.get("tokens") or not r.get("best_params"):
            continue
        wm, wk = worst_margin(r)
        if wm is None or not (lo < wm < hi):
            continue
        sp = r["spec"]
        if sp not in budget:
            budget[sp] = Spec.load(sp).topology.get("device_budget", [3, 16])
        if (g.get("n_devices") or 99) > budget[sp][1] - 2:
            continue
        key = (r["wl_hash"], sp)
        if key not in best or wm > best[key][0]:
            best[key] = (wm, wk, r)
    cands = sorted(best.values(), key=lambda t: -t[0])
    fams = ds._families([t[2] for t in cands])
    fam_of = {}
    for fi, mem in enumerate(fams):
        for i in mem:
            fam_of[i] = fi
    out, used_fam, used_wl, per_spec = [], set(), set(), {}
    for i, (wm, wk, r) in enumerate(cands):
        f = fam_of.get(i, -i)
        if f in used_fam or r["wl_hash"] in used_wl:
            continue
        if per_spec.get(r["spec"], 0) >= 3:
            continue
        per_spec[r["spec"]] = per_spec.get(r["spec"], 0) + 1
        used_fam.add(f)
        used_wl.add(r["wl_hash"])
        out.append({"wl_hash": r["wl_hash"], "spec": r["spec"], "worst": wm,
                    "binding": wk, "n_devices": (r.get("graph") or {}).get("n_devices"),
                    "arm": (r.get("provenance") or {}).get("source_arm"),
                    "ts": r.get("ts"), "row": r})
        if len(out) >= n:
            break
    return out


if __name__ == "__main__":
    for p in select(int(sys.argv[1]) if len(sys.argv) > 1 else 5):
        print("%-18s %-12s worst %+.4f (%s)  nd=%s  arm=%s"
              % (p["wl_hash"], p["spec"], p["worst"], p["binding"],
                 p["n_devices"], p["arm"]))
