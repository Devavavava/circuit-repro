#!/usr/bin/env python
"""VM step 3: markdown tables for README from results/ (no training)."""
import collections
import gzip
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from train import thr_at_recall, prune_at, subpop  # noqa: E402

M = json.load(open(f"{HERE}/results/metrics.json"))
FO = json.load(open(f"{HERE}/results/folds.json"))
rows_all = [json.loads(l) for l in gzip.open(f"{HERE}/data/rows.jsonl.gz", "rt")]
rows = [r for r in rows_all if r.get("incl")]
Y = np.array([r["y"] for r in rows])
WM = np.array([np.nan if r.get("wm") is None else r["wm"] for r in rows])


def mae_clipped(variant, s, m):
    """margin MAE with BOTH target and prediction clipped to [-2, 2] (non-fenced OOF)."""
    f = f"{HERE}/results/oof_{variant}_{s}_{m}.npz"
    if not os.path.exists(f):
        return None
    mm = np.load(f)["m"]
    ix = np.array([i for i in range(len(rows)) if not np.isnan(mm[i]) and not rows[i]["fenced"]
                   and not np.isnan(WM[i])])
    return float(np.mean(np.abs(np.clip(WM[ix], -2, 2) - np.clip(mm[ix], -2, 2))))
SPLITS = ["SF", "PA", "CELL", "TIME"]
MODELS = ["lr", "mlp", "gnn"]
CPU_PER_CAND = 116.0
out = []
P = out.append


def f3(x):
    return "–" if x is None else f"{x:.3f}"


# ---------------------------------------------------------------- data table
P("### Data table (`data/rows.jsonl.gz`, built by `build_data.py`)\n")
c = collections.Counter((r["src"], r.get("excl_reason") or "INCLUDED") for r in rows_all)
P("| source | rows | included | excluded: reason (count) |")
P("|---|---|---|---|")
for src in ["bench-v2", "E-c", "E-d", "R1", "R4", "verifier-rl-v1", "S-1", "stability-gate"]:
    tot = sum(v for (s, _), v in c.items() if s == src)
    inc = c.get((src, "INCLUDED"), 0)
    ex = "; ".join(f"{k} ({v})" for (s, k), v in sorted(c.items(), key=lambda kv: -kv[1])
                   if s == src and k != "INCLUDED")
    P(f"| {src} | {tot} | {inc} | {ex} |")
P("")
P("Included rows by source, profile and kind (n / feasible):\n")
cc = collections.defaultdict(lambda: [0, 0])
for r in rows:
    k = (r["src"], r["profile"], subpop(r) if r["src"] == "bench-v2" else "-", r["fenced"])
    cc[k][0] += 1
    cc[k][1] += r["y"]
P("| source | profile | subpop | fenced | n | feasible | rate |")
P("|---|---|---|---|---|---|---|")
for k in sorted(cc, key=str):
    n, p = cc[k]
    P(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {n} | {p} | {p / n:.3f} |")
P("")

# ---------------------------------------------------------------- folds
P("### Split sizes (per fold: train / test / test rows dropped as (tok, spec) leaks / fenced in test)\n")
P("| split | folds |")
P("|---|---|")
for s in SPLITS:
    P(f"| {s} | " + "; ".join(f"f{f['fold']}: {f['n_train']}/{f['n_test']}/{f['dropped_leak']}/{f['n_test_fenced']}"
                             for f in FO["folds"][s]) + " |")
P(f"\nTIME split cut: `ts` ≥ {FO['t70']} is test.\n")

# ---------------------------------------------------------------- metrics
for variant in ("bv2", "aux"):
    P(f"### Metrics — variant `{variant}` (pooled out-of-fold, non-fenced bench-v2 test rows)\n")
    P("| split | model | n | pos | AUC | prune@95 oracle | per-fold oracle | prune@95 deployable (recall) | ECE | margin MAE | MAE (pred clipped) | search AUC | search prune@95 | F2 AUC | F2 prune@95 | stages AUC | stages prune@95 |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for s in SPLITS:
        for m in MODELS:
            k = f"{variant}|{s}|{m}"
            if k not in M:
                continue
            a = M[k]["all"]
            se, f2, st = M[k].get("search", {}), M[k].get("F2", {}), M[k].get("stages", {})
            P(f"| {s} | {m} | {a['n']} | {a['pos']} | {f3(a['auc'])} | **{f3(a.get('prune95_oracle'))}** | "
              f"{', '.join(f'{x:.2f}' for x in a.get('prune95_oracle_per_fold', []))} | "
              f"{f3(a['prune95_dep'])} ({f3(a['recall_dep'])}) | {f3(a['ece'])} | {f3(a.get('wm_mae'))} | {f3(mae_clipped(variant, s, m))} | "
              f"{f3(se.get('auc'))} | {f3(se.get('prune95_oracle'))} | {f3(f2.get('auc'))} | {f3(f2.get('prune95_oracle'))} | "
              f"{f3(st.get('auc'))} | {f3(st.get('prune95_oracle'))} |")
    P("")

P("### Fenced rows (accepted bench-v2 cells; eval-only, never trained or tuned on)\n")
P("| split | model | n | pos | AUC | prune@95 oracle | prune@95 deployable (recall) | ECE |")
P("|---|---|---|---|---|---|---|---|")
for s in SPLITS:
    for m in MODELS:
        k = f"bv2|{s}|{m}"
        if k in M and "fenced" in M[k]:
            a = M[k]["fenced"]
            P(f"| {s} | {m} | {a['n']} | {a['pos']} | {f3(a['auc'])} | {f3(a.get('prune95_oracle'))} | "
              f"{f3(a['prune95_dep'])} ({f3(a['recall_dep'])}) | {f3(a['ece'])} |")
P("")

# ---------------------------------------------------------------- recall/prune curve
P("### Prune fraction at other recall levels (oracle threshold, pooled OOF, bv2 variant)\n")
P("| split | model | pop | R=0.99 | R=0.95 | R=0.90 | R=0.80 |")
P("|---|---|---|---|---|---|---|")
curves = {}
for s in SPLITS:
    for m in MODELS:
        f = f"{HERE}/results/oof_bv2_{s}_{m}.npz"
        if not os.path.exists(f):
            continue
        p = np.load(f)["p"]
        for pop in ("all", "search"):
            ix = np.array([i for i in range(len(rows)) if not np.isnan(p[i]) and not rows[i]["fenced"]
                           and (pop == "all" or subpop(rows[i]) == pop)])
            vals = []
            for R in (0.99, 0.95, 0.90, 0.80):
                t = thr_at_recall(Y[ix], p[ix], R)
                vals.append(prune_at(Y[ix], p[ix], t)[0])
            curves[(s, m, pop)] = vals
            P(f"| {s} | {m} | {pop} | " + " | ".join(f"{v:.3f}" for v in vals) + " |")
P("")

# ---------------------------------------------------------------- decision
P("### Decision rule (prune@95 oracle ≥ 0.50 on the held-out split; primary variant bv2, population all)\n")
P("| model | " + " | ".join(SPLITS) + " | all four |")
P("|---|" + "---|" * (len(SPLITS) + 1))
verdict = {}
for m in MODELS:
    cells, ok_all = [], True
    for s in SPLITS:
        k = f"bv2|{s}|{m}"
        v = M.get(k, {}).get("all", {}).get("prune95_oracle")
        ok = v is not None and v >= 0.5
        ok_all &= ok
        cells.append(f"{f3(v)} {'PASS' if ok else 'fail'}")
    verdict[m] = ok_all
    P(f"| {m} | " + " | ".join(cells) + f" | **{'PASS' if ok_all else 'FAIL'}** |")
P(f"\nOverall: **{'PASS' if any(verdict.values()) else 'FAIL'}**\n")

# ---------------------------------------------------------------- transfer
P("### Transfer: full-data bv2 model → verifier-rl-v1 rows (rl-v1 on v1.2 cells, n=100)\n")
P("| model | n | pos | AUC | prune@95 oracle | prune / recall at the val threshold | ECE |")
P("|---|---|---|---|---|---|---|")
for m in MODELS:
    k = f"full|transfer-verifier-rl-v1|{m}"
    if k in M:
        a = M[k]
        P(f"| {m} | {a['n']} | {a['pos']} | {f3(a['auc'])} | {f3(a.get('prune95_oracle'))} | "
          f"{f3(a['prune_at_val_thr'])} / {f3(a['recall_at_val_thr'])} | {f3(a['ece'])} |")
P("")
P("Checkpoints:\n")
for m in MODELS:
    k = f"full|ckpt|{m}"
    if k in M:
        P(f"- `checkpoints/full_{m}.pt`: {M[k]['bytes']} bytes, sha256 `{M[k]['sha256']}`, "
          f"val threshold at 95 % recall = {M[k]['thr_val_recall95']:.4f}, "
          f"train {M[k]['n_train']} / val {M[k]['n_val']}")
P("")

# ---------------------------------------------------------------- CPU projection
bv_search = [r for r in rows if r["src"] == "bench-v2" and subpop(r) == "search"]
secs = np.array([r["secs"] for r in bv_search if r.get("secs")])
n_sized_bv2 = sum(1 for r in rows_all if r["src"] == "bench-v2" and r.get("n_evals"))
n_search = sum(1 for r in rows_all if r["src"] == "bench-v2" and r.get("kind") in ("search", "confirm")
               and r.get("n_evals"))
P("### CPU projection (descriptive; the decision rule governs the verdict)\n")
P(f"- Measured bench-v2 search sizing call: mean {secs.mean():.0f} s and median {np.median(secs):.0f} s of wall time per call "
  f"(n={len(secs)}, box load 8–15). The brief's figure is 116 CPU-s per candidate (R1).")
P(f"- Sized bench-v2 calls in the snapshot: {n_sized_bv2}. Of these, {n_search} are search/confirm.")
best = {}
for pop in ("all", "search"):
    for s in SPLITS:
        cand = [(curves[(s, m, pop)][1], m) for m in MODELS if (s, m, pop) in curves]
        if cand:
            best[(pop, s)] = max(cand)
P("\n| pop | split | best model | prune@95 | CPU-h saved per 1000 candidates (×116 s) | SPICE calls per feasible found (relative) |")
P("|---|---|---|---|---|---|")
for (pop, s), (v, m) in sorted(best.items()):
    P(f"| {pop} | {s} | {m} | {v:.3f} | {v * 1000 * CPU_PER_CAND / 3600:.1f} | {(1 - v) / 0.95:.2f} |")
P("")
open(f"{HERE}/results/report.md", "w").write("\n".join(out) + "\n")
print("\n".join(out))
