"""WP-DIAGHEADS: read-only operating-point harvest at each design's OWN best point.

Pre-registered in plans2/13-WP-DIAGHEADS.md section 1b. `op_points.jsonl` as
WP-OBSERVE left it is thin (391 device rows) and degenerate (374 of them off,
164 of its 194 rows the inner-ZOAF trajectory of one 2-device demo circuit), and
inner-ZOAF rows are the wrong LABEL anyway: the critic's input is (topology,
spec) and carries no `x`, so a conduction label taken at an arbitrary point of a
sizing trajectory is not a function of the model's input. A *converged* point is.

So, exactly the method FINDINGS 30.5 used for its six designs, applied to every
multi-finger-era L2 row that already carries a noise budget: rebuild the deck
with `size.prepared_body`, run ONE bare `op` at that row's stored `best_params`,
append one `stage="label"` op row. No re-sizing, no metric is re-measured, no
store row is mutated, nothing is adopted -- it is instrumentation over designs
that were already labelled, and it makes the SAME design carry both diagnosis
labels (noise share, already stored; conduction, harvested here).

    python lna/_diag_harvest.py [--limit N] [--dry-run]

Rows are stamped `harness.recipe = "diagheads-v1"` and `harness.deck =
"op_probe"` -- a third deck value alongside WP-OBSERVE's `sizing` / `noise`, so
this population stays separable from theirs forever (Block 6).
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datastore as ds        # noqa: E402
import extract as E           # noqa: E402
import size as S              # noqa: E402
from topology import Topology  # noqa: E402

RECIPE = "diagheads-v1"
ARM = "diagheads-harvest"


def bare_op(body, params, timeout=60):
    """One `op`, print the MOSFET instance parameters, stop.

    Deliberately the same shape as `ref/check_op.independent_op` (the golden
    that validated the read-out): no `sp`, no `meas`, no stability expressions,
    and no `save` (gotcha N1)."""
    mos, bjt = E.op_devices(body)
    if not mos and not bjt:
        return None
    vecs = [f"@{d}[{p}]" for d in mos for p in E.MOS_OP_PARAMS]
    vecs += [f"@{d}[{p}]" for d in bjt for p in E.BJT_OP_PARAMS]
    ctrl = [".control", "op"]
    ctrl += ["print " + " ".join(vecs[i:i + 8]) for i in range(0, len(vecs), 8)]
    ctrl += [".endc", ".end"]
    lines = [body.rstrip()]
    if params:
        lines.append(".param " + " ".join(f"{k}={v}" for k, v in params.items()))
    lines.append("\n".join(ctrl))
    out = E.run_deck("\n".join(lines) + "\n", "diagop_", "d.cir", timeout=timeout)
    if out is None or "singular matrix" in out.lower():
        return None
    op = E.parse_op(out)
    return op if op.get("devices") else None


def targets():
    """The pre-registered harvest set: multi-finger era, tokens + best_params +
    a stored noise budget, deduplicated by (wl_hash, spec, best_params)."""
    seen, out = set(), []
    for r in ds.load("topo_labels"):
        z = r.get("zoaf_cfg") or {}
        if z.get("w_finger") != 2e-06:
            continue
        g = r.get("graph") or {}
        if not g.get("tokens") or not r.get("best_params"):
            continue
        if not (r.get("provenance") or {}).get("noise_budget"):
            continue
        key = (r["wl_hash"], r["spec"],
               hashlib.md5(json.dumps(r["best_params"], sort_keys=True)
                           .encode()).hexdigest())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _already():
    """Resume support: (wl_hash, spec, params-hash) already harvested."""
    done = set()
    for r in ds.load("op_points"):
        if (r.get("harness") or {}).get("recipe") != RECIPE:
            continue
        done.add((r.get("wl_hash"), r.get("spec"),
                  hashlib.md5(json.dumps(r.get("params") or {}, sort_keys=True)
                              .encode()).hexdigest()))
    return done


def _key(r):
    return (r["wl_hash"], r["spec"],
            hashlib.md5(json.dumps(r["best_params"], sort_keys=True)
                        .encode()).hexdigest())


def harvest(limit=None, dry_run=False, cap_secs=3600):
    done = _already()
    tg = [r for r in targets() if _key(r) not in done]
    if done:
        print("resume: %d already harvested" % len(done))
    if limit:
        tg = tg[:limit]
    print("harvest targets: %d (cap %d runs / %d s)" % (len(tg), len(tg), cap_secs),
          flush=True)
    if dry_run:
        return 0
    t0 = time.time()
    n_ok = n_prep_fail = n_op_fail = 0
    census = {}
    for i, r in enumerate(tg):
        if time.time() - t0 > cap_secs:
            print("WALL-CLOCK CAP hit at %d/%d" % (i, len(tg)), flush=True)
            break
        z = r.get("zoaf_cfg") or {}
        try:
            topo = Topology(r["graph"]["tokens"])
            prep = S.prepared_body(topo, inductor_q=z.get("inductor_q") or 12)
        except Exception:
            prep = None
        if prep is None:
            n_prep_fail += 1
            continue
        op = bare_op(prep[0], r["best_params"])
        if op is None:
            n_op_fail += 1
            continue
        op["deck"] = "op_probe"
        harness = {"recipe": RECIPE, "w_finger": z.get("w_finger"),
                   "mos_fingers": z.get("mos_fingers"),
                   "inductor_q": z.get("inductor_q") or 12,
                   "nf_method": "series_rs", "nf_gated": z.get("nf_gated"),
                   "op_schema": E.OP_SCHEMA, "bias_rules": None}
        prov = {"source_arm": ARM,
                "parent_arm": (r.get("provenance") or {}).get("source_arm"),
                "parent_recipe": z.get("recipe"), "parent_ts": r.get("ts")}
        row = ds.row_op(r["wl_hash"], r["spec"], op, metrics=r.get("metrics"),
                        x=r.get("best_x"), params=r["best_params"],
                        stage="label", harness=harness, provenance=prov,
                        noise_budget=(r.get("provenance") or {}).get("noise_budget"))
        ds.append("op_points", row)
        n_ok += 1
        for k, v in (row.get("regions") or {}).items():
            census[k] = census.get(k, 0) + v
        if (i + 1) % 100 == 0:
            print("  %d/%d  ok=%d prep_fail=%d op_fail=%d  %.1fs  %s"
                  % (i + 1, len(tg), n_ok, n_prep_fail, n_op_fail,
                     time.time() - t0, json.dumps(census)), flush=True)
    print("DONE ok=%d prep_fail=%d op_fail=%d in %.1fs; device regions %s"
          % (n_ok, n_prep_fail, n_op_fail, time.time() - t0, json.dumps(census)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cap-secs", type=int, default=3600)
    a = ap.parse_args()
    return harvest(limit=a.limit, dry_run=a.dry_run, cap_secs=a.cap_secs)


if __name__ == "__main__":
    sys.exit(main())
