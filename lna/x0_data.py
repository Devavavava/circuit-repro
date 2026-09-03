"""x0_data.py -- training-set builder for the learned starting-sizing prior.

Turns stored evaluated designs into (input_features, per-device x0) training rows
for `x0_prior.py`. Read-only over the label stores; never writes them.

WHERE THE ROWS COME FROM
------------------------
The one clean source is the box-era L2 label store `lna/data/topo_labels.jsonl`.
Every row there carries `graph.tokens` (the topology), `best_params` (the
DECODED winning sizing) and `metrics` (what that sizing measured). We recover the
NORMALISED starting vector x in [0,1]^d by INVERTING `size.make_objective`'s
decode with the same `kind_ranges` (log/linear per kind), so a row needs only
tokens+params -- not the rarely-stored `best_x`. That takes the usable pool from
~370 rows (best_x present) to ~4000 rows (params present).

HINDSIGHT RELABELLING (documented transform)
--------------------------------------------
A stored design was sized FOR some target spec, but the sizing it found is a
valid demonstration for the spec it ACTUALLY ACHIEVED, whatever the original
target. So the training TARGET VECTOR for a row is synthesised from the MEASURED
metrics, not the row's nominal spec constraints:

    achieved_target[nf_db]   = measured nf_db      (a "<= this" NF gate it met)
    achieved_target[s11_db]  = measured s11_db     (a "<= this" match it met)
    achieved_target[s21_db]  = measured s21_db     (a ">= this" gain it met)
    achieved_target[idd_ma]  = measured idd_ma     (a "<= this" current it met)
    + band f0 (Hz, log-scaled) carried from the row's spec band.

The model thus learns "to hit THIS (nf,s11,s21,idd) at THIS band on THIS pdk,
start the devices HERE" -- a demonstration that is true by construction for every
evaluated design, feasible or not. `feasible` is kept only as an optional filter
/ sample weight, never as a gate on inclusion (a near-miss is still a valid
demonstration for the slightly-relaxed spec it achieved).

LEAKAGE RULE (critical -- see CAMPAIGN-X0-V0.md)
------------------------------------------------
The adoption eval runs on the 24-spec ladder (`kaggle/specs-ladder/ladder.json`).
Any row produced ON a ladder spec, or on the cross-pdk campaigns that re-run the
ladder, is EXCLUDED. In this store that is a no-op today (all rows are the box
LNA specs wifi24/dhruva-*/wideband-sdr/gps-l1, none of which is a ladder spec_id)
but the exclusion is enforced mechanically by spec-id AND by (band-f0, pdk)
proximity so it stays correct if ladder-derived rows ever land here. We also
EXCLUDE every `kaggle/campaigns/*` design by construction: this builder never
reads that tree.

BAND-OVERLAP CAVEAT (honest): several box specs share a BAND with ladder specs
(wifi24/dhruva-s at 2.44 GHz == cap-*-wifi; gps-l1/dhruva-l1 at 1.575 GHz ==
cap-*-gpsband). We do NOT drop those rows -- dropping every 2.44 GHz design would
gut the corpus -- but the pre-reg records this as the residual leakage vector and
the adoption bar (beat BOTH null and retrieval on the ladder) is set with it in
mind.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.dirname(HERE)
for _p in (os.path.join(ROOT, "lna"), os.path.join(ROOT, "misc", "ZOAF"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import size as S                     # noqa: E402
from topology import Topology        # noqa: E402

TOPO_LABELS = os.path.join(ROOT, "lna", "data", "topo_labels.jsonl")
LADDER = os.path.join(ROOT, "kaggle", "specs-ladder", "ladder.json")

# device kinds the sizer emits (see size.classify_params). Fixed order == the
# per-kind output head order in x0_prior.
KINDS = ["W", "L", "R", "C", "VB"]
# spec target metrics the prior conditions on, with (direction, typical-scale)
# used to squash into a comparable feature. dir=+1 -> "<= target", -1 -> ">= target".
TARGET_METRICS = [
    ("nf_db", +1.0, 6.0),      # NF gate: lower is better, ~0..6 dB
    ("s11_db", +1.0, 20.0),    # match: more-negative better; stored as dB (<0)
    ("s21_db", -1.0, 40.0),    # gain: higher better, ~0..40 dB
    ("idd_ma", +1.0, 20.0),    # current: lower better, ~0..20 mA
]


def _ladder_spec_ids():
    try:
        d = json.load(open(LADDER))
        return {s.get("name") for s in d.get("specs", [])} | \
               {s.get("spec_id") for s in d.get("specs", [])}
    except Exception:                                              # noqa: BLE001
        return set()


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def spec_band_f0(spec):
    """f0 in Hz for a Spec (narrowband f0, wideband geometric-mean of edges)."""
    b = getattr(spec, "band", None) or {}
    f0 = _f(b.get("f0"))
    if f0:
        return f0
    lo, hi = _f(b.get("f_lo")), _f(b.get("f_hi"))
    if lo and hi:
        return (lo * hi) ** 0.5
    return 2.4e9


def target_feature_from_metrics(metrics):
    """Hindsight ACHIEVED-spec target vector, squashed to a stable feature.

    For each TARGET_METRIC we take the measured value as the target the design
    demonstrably met, then map to a monotone feature in roughly [0,1] via
    v/scale (clipped). Direction is folded in so a *tighter* spec always reads as
    a *larger* feature (harder -> higher), which is what the prior should react
    to. Missing metrics -> 0.5 (neutral)."""
    feat = []
    for name, direction, scale in TARGET_METRICS:
        v = _f((metrics or {}).get(name))
        if v is None:
            feat.append(0.5)
            continue
        # s11/s21 are dB and s21 is "higher better": normalise magnitude/scale.
        z = (v / scale) if direction > 0 else (v / scale)
        # fold direction: for ">= target" (gain) a higher achieved value == a
        # harder demonstration, so invert-then-shift to keep "harder -> larger".
        if direction < 0:
            z = z            # already grows with achieved gain
        feat.append(max(-1.0, min(2.0, z)))
    return feat


def graph_feature(graph):
    """Fixed-length topology summary: per-kind device counts (normalised),
    total device count, inductor ratio. Order matches KINDS for the counts."""
    counts = (graph or {}).get("counts") or {}
    n_dev = (graph or {}).get("n_devices") or sum(
        int(v) for v in counts.values() if isinstance(v, (int, float)))
    n_dev = max(1, int(n_dev or 1))
    # map raw kind labels (NM/PM/R/C/L) to sizer KINDS (W covers NM+PM, VB rare)
    kmap = {"NM": "W", "PM": "W", "L": "L", "R": "R", "C": "C"}
    kc = {k: 0 for k in KINDS}
    for raw, n in counts.items():
        k = kmap.get(raw)
        if k:
            kc[k] += int(n or 0)
    feat = [kc[k] / n_dev for k in KINDS]         # kind fractions
    feat.append(min(n_dev / 20.0, 1.5))           # size (cap ~20 devices)
    ind = (graph or {}).get("inductor_ratio")
    feat.append(_f(ind, kc["L"] / n_dev))
    return feat


def pdk_onehot(pdk):
    pdks = ["bptm45", "sky130", "gf180mcu", "ihp_sg13g2"]
    v = [0.0] * len(pdks)
    try:
        v[pdks.index(pdk or "bptm45")] = 1.0
    except ValueError:
        v[0] = 1.0
    return v


def feature_vector(graph, metrics, band_f0, pdk):
    """Assemble the full model input for one row (fixed length across topologies).

    [ graph summary (7) | achieved-target (4) | log10(f0) scaled (1) | pdk 1-hot (4) ]
    """
    gf = graph_feature(graph)
    tf = target_feature_from_metrics(metrics)
    ff = [(math.log10(max(band_f0, 1.0)) - 8.0) / 3.0]   # ~ [0,1] over 100M..100G
    return gf + tf + ff + pdk_onehot(pdk)


FEATURE_DIM = 7 + len(TARGET_METRICS) + 1 + 4


def _invert_params_to_perkind(sizable, ranges, best_params):
    """Recover per-DEVICE normalised x from decoded params, then average per KIND.

    Returns {kind: mean_x} over the sizable devices of that kind (the per-kind
    label the prior regresses). Per-device x is the exact inverse of decode."""
    acc = {k: [] for k in KINDS}
    for nm, kind in sizable.items():
        if nm not in best_params or kind not in ranges:
            continue
        lo, hi, islog = ranges[kind]
        v = _f(best_params[nm])
        if v is None or lo <= 0 or hi <= 0:
            continue
        if islog:
            if v <= 0:
                continue
            xi = (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
        else:
            xi = (v - lo) / (hi - lo)
        acc[kind].append(min(max(xi, 0.0), 1.0))
    return {k: (sum(vs) / len(vs)) for k, vs in acc.items() if vs}


def build_rows(limit=None, feasible_only=False, verbose=False, cache=None):
    """Yield training rows: dict(feat=[...], target={kind:x}, weight, meta).

    meta carries provenance for the audit (spec, wl_hash, pdk, feasible, git_sha,
    source_arm). Rows on ladder spec-ids are skipped (leakage rule).

    `cache` (optional path): if the file exists it is loaded and yielded
    directly (the expensive per-row `prepared_body` is skipped); if it does not,
    the full build runs and its result is written there. The cache is keyed only
    by feasible_only (encoded in the row weight) -- callers that need a fresh
    build should delete it. Cache is an internal accelerator; the store is still
    the source of truth."""
    if cache and not limit and os.path.exists(cache):
        for row in json.load(open(cache)):
            if feasible_only and not row["meta"]["feasible"]:
                continue
            yield row
        return
    _collected = [] if (cache and not limit) else None
    ladder_ids = _ladder_spec_ids()
    n_seen = n_kept = n_leak = n_badtopo = 0
    if not os.path.exists(TOPO_LABELS):
        return
    for line in open(TOPO_LABELS):
        if limit and n_kept >= limit:
            break
        try:
            r = json.loads(line)
        except Exception:                                          # noqa: BLE001
            continue
        n_seen += 1
        spec_name = r.get("spec")
        if spec_name in ladder_ids:                # LEAKAGE: drop ladder rows
            n_leak += 1
            continue
        graph = r.get("graph") or {}
        toks = graph.get("tokens")
        bp = r.get("best_params")
        metrics = r.get("metrics")
        if not toks or not bp or not metrics:
            continue
        # When building a cache we collect the FULL set and filter on yield, so
        # the cached file is complete regardless of this call's feasible_only.
        if feasible_only and _collected is None and not r.get("feasible"):
            continue
        try:
            spec = S._spec_for_sizing(spec_name, nf_gate=None, pdk=None)
            topo = Topology(list(toks))
            prep = S.prepared_body(topo, inductor_q=12, pdk=S._pdk_name(spec))
            if prep is None:
                n_badtopo += 1
                continue
            _body, sizable, _fixed = prep
            if not sizable:
                n_badtopo += 1
                continue
            ranges = S.kind_ranges(spec)
        except Exception:                                          # noqa: BLE001
            n_badtopo += 1
            continue
        target = _invert_params_to_perkind(sizable, ranges, bp)
        if not target:
            continue
        pdk = S._pdk_name(spec)
        feat = feature_vector(graph, metrics, spec_band_f0(spec), pdk)
        prov = r.get("provenance") or {}
        row = {
            "feat": feat,
            "target": target,                       # {kind: mean normalised x}
            "weight": 2.0 if r.get("feasible") else 1.0,
            "meta": {
                "spec": spec_name, "wl_hash": r.get("wl_hash"), "pdk": pdk,
                "feasible": bool(r.get("feasible")),
                "git_sha": (r.get("git_sha") or "")[:8],
                "source_arm": prov.get("source_arm"),
                "n_devices": graph.get("n_devices"),
            },
        }
        n_kept += 1
        if _collected is not None:
            _collected.append(row)
            if feasible_only and not row["meta"]["feasible"]:
                continue
        yield row
    if _collected is not None and cache:
        try:
            os.makedirs(os.path.dirname(cache) or ".", exist_ok=True)
            json.dump(_collected, open(cache, "w"))
        except Exception:                                          # noqa: BLE001
            pass
    if verbose:
        print(f"[x0_data] seen={n_seen} kept={n_kept} ladder_leak_dropped={n_leak} "
              f"unsizable_topo={n_badtopo}", file=sys.stderr)


def audit(out=None):
    """Print/return a provenance table over the buildable training rows."""
    from collections import Counter
    by_spec = Counter()
    by_pdk = Counter()
    by_era = Counter()
    by_arm = Counter()
    feas = 0
    n = 0
    for row in build_rows(verbose=True):
        m = row["meta"]
        by_spec[m["spec"]] += 1
        by_pdk[m["pdk"]] += 1
        by_era[m["git_sha"]] += 1
        by_arm[m["source_arm"]] += 1
        feas += int(m["feasible"])
        n += 1
    lines = [f"x0 training-set audit: {n} rows ({feas} feasible)",
             f"  feature_dim = {FEATURE_DIM}",
             "  by spec:  " + ", ".join(f"{k}={v}" for k, v in by_spec.most_common()),
             "  by pdk:   " + ", ".join(f"{k}={v}" for k, v in by_pdk.most_common()),
             "  by era:   " + ", ".join(f"{k}={v}" for k, v in by_era.most_common(8)),
             "  by arm:   " + ", ".join(f"{k}={v}" for k, v in by_arm.most_common(10))]
    txt = "\n".join(lines)
    print(txt)
    if out:
        open(out, "w").write(txt + "\n")
    return n


if __name__ == "__main__":
    if "--audit" in sys.argv:
        audit()
    else:
        n = sum(1 for _ in build_rows(verbose=True))
        print(f"buildable training rows: {n}")
