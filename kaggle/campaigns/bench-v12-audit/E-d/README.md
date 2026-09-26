# E-d — Real Qwen baseline, matched zero-shot vs few-shot (bench-v1.2)

Pre-reg: `kaggle/PREREG-BENCH-V12-AUDIT.md` § E-d (frozen 2026-09-26). Scored 2026-09-26 on
this box. **Era stamp (git HEAD at scoring start): `a0e4edcc6ac10ee030730bbe0e40f958c5fc42be`.**
Kernels ran the pinned code `cc5a836bb` (see `*/editcap/KERNEL-MANIFEST.json`).

STATUS: **INTERIM — Qwen3-32B only.** The 14B kernel (`…-ed-14b`) was still RUNNING at the
time of this commit; this README is replaced when its outputs are scored (or the 32B-only
result is declared final if 14B does not complete in time).

## What was run

| kernel (private, devavratpatni) | model | runs | wall |
|---|---|---|---|
| circuit-repro-bench-v12-audit-ed-32b-zs | Qwen3-32B Q4_K_S | ZS-s1, ZS-s2 (16 cells each) | 204 min |
| circuit-repro-bench-v12-audit-ed-32b-fs | Qwen3-32B Q4_K_S | FS-s1, FS-s2 | 187 min |
| circuit-repro-bench-v12-audit-ed-14b | Qwen3-14B Q4_K_M | ZS-s1, FS-s1, ZS-s2, FS-s2 | pending |

Arm B, k=3, temp 0.7, 8192-token cap, `EDITCAP_RECOVER_REASONING=1`; FS prompt contains the
generic `WORKED EXAMPLE` block (verified: 32/32 FS prompts, 0/32 ZS prompts).

## Scoring (primary, pre-registered, local)

`ed_score.py enumerate`: every archived `edit<i>.net` → `proposal.round_trip` (invalid recorded
with its error) → dedupe identical token sequences per cell (`cand.json`, 155 unique over 161
valid 32B edits; sized once, credited to every edit carrying it).
`ed_score.py run 6`: each unique (cell, tokens) × seeds 1,2,3 through
`bench_anchor_prep.smoke_run(tokens, <lib>/<cell>/spec.yaml, seed, 2500, "bptm45")`,
feasible = `result["feasible"]`, worst margin = `mysolve._margins`; one subprocess per job,
6 in parallel, appended to `score.jsonl` as each finishes (465 rows, 0 crashes, 119 min wall).
`ed_summarize.py` → `summary.json` + `tables.md` (full tables; key numbers below).

Files: `edits.jsonl` (one row per edit: validity, token key, in-kernel outcome, topology flags),
`completions.jsonl` (one row per completion: finish reason, tokens, empty/no-edit, llama-server
timing), `score.jsonl` (sizing rows), `32b-zs/`, `32b-fs/` (kernel outputs verbatim, minus the
148 MB llama.cpp and 9 MB ngspice binary caches).

## Results — Qwen3-32B (2 completions × 16 cells per condition)

| cond | edits | valid (round_trip) | sizable | feasible edits (any seed) | cells solved any seed: total / SYN(6) / RET(10) | cells solved by an edit feasible at ≥2/3 seeds | EDGE cell | s1/s2 solved: both / s1-only / s2-only | in-kernel (3×600) solved |
|---|---|---|---|---|---|---|---|---|---|
| ZS | 96 | 82 (85%) | 81 | 5 (5.2%) | **3 / 2 / 1** | 2 | no | 1 / 0 / 2 | 0 |
| FS | 96 | 79 (82%) | 79 | 7 (7.3%) | **5 / 3 / 2** | 5 | no | 1 / 2 / 2 | 3 |

Cells solved: ZS = wb-s11n10-g10-b0530 (SYN), wb-s11n9-g10-b0530 (SYN), wb-s11n10-g10-b0824 (RET).
FS = wb-s11n11-g10-b0824, wb-s11n11-g12-b0824, wb-s11n8-g10-b0530 (SYN), wb-s11n10-g10-b0824,
wb-s11n10-g12-b0824 (RET). **No narrowband cell solved in either condition** (0/8, all RETRIEVAL
cells whose fix is "use anchor a1/a2/a4"; best nb margins −0.10…−0.53). EDGE cell
wb-s11n8-g12-b0530 unsolved by both. Every feasible solution is razor-thin (worst margin
+0.0000…+0.0061), like the templates.

Completions: 0 empty, 0 with no edits, 0 finish=length, 0 recovered-from-reasoning, 0 LLM errors
(both conditions). Mean completion tokens ZS 3,336 (max 6,497), FS 2,688 (max 5,915).

**GPU wall-time per completion** (llama-server `total time`, 2×T4 layer split, ~11 tok/s):
ZS mean 4.90 min (median 4.80), FS mean 4.32 min (median 3.20).

### Topology classes emitted (valid edits)

| cond | wb valid edits | narrow shunt-fb (`analyze_qwen_vs_claude_topo`) | widened shunt-fb | widened, VIN-side variant | wb cells with ≥1 widened fb edit | widened-fb edits feasible | nb valid edits | nb tank | nb cascode |
|---|---|---|---|---|---|---|---|---|---|
| ZS | 36 | 0 | **0** | 0 | 0/8 | 0 | 46 | 36 | 0 |
| FS | 40 | 4 | **14** | 14 | **8/8** | 7 | 39 | 28 | 1 |

Widened detector (`ed_score.topo_flags`): any R between an input-transistor gate net (MOS gate
reachable from VIN1 through C/L only) and a non-diode drain / L–C tank node / VOUT1 outside the
input C/L component. It catches `R Rf n4 n1` (tank node → gate) and `R Rf VOUT1 n1` (post-DC-block
output → gate), which the narrow detector misses. The narrow detector's 5 nb hits (1 ZS, 4 FS)
are resistors to the common-gate anchor's AC-grounded bias gate — not input feedback (widened
detector: 0). No anchor triggers either detector.

What the feasible edits are (vs. the anchor):
- FS: all 7 feasible edits are single-resistor shunt feedback onto the input gate —
  `R n2 n1` (drain→gate, = the template move) ×3, `R n4 n1` (tank→gate) ×3, `R VOUT1 n1` ×1.
- ZS: no feedback at all — series input inductor(s) in front of the input DC-block cap
  (`L VIN1 n0`, `L VIN1 n0 + C n0 VSS`) ×4, plus one rewrite that routes VIN1 through two
  inductors via the PMOS bias-diode node. These are exactly the E-c single-edit class
  (`add L VIN1-n0` is screen-feasible in E-c).

### ZS vs FS (pre-reg rule: no claim unless ≥ 3 cells differ)

Solved-set symmetric difference = 6 cells (ZS-only 2, FS-only 4) → the rule **permits** a claim.
The claim that is supported: few-shot **changes what the model emits** (widened shunt-fb 0/36 → 14/40
wb edits, 0/8 → 8/8 wb cells) and FS solves more cells robustly (≥2/3 seeds: 5 vs 2; any seed 5 vs 3).
The net any-seed difference is only +2 cells with 2 samples/cell, so the *size* of the FS gain is
not established; ZS also solves 2 SYN cells by a different, non-feedback route.

### Against E-b / E-a / E-c labels

- RETRIEVAL (10): ZS 1, FS 2 — both wb retrieval cells; 0/8 nb.
- SYNTHESIS (6): ZS 2, FS 3 (union 5/6; only the EDGE cell is unsolved by both).
- E-c (brute-force single edit) was **still in its confirmation stage** when this was written
  (`E-c/summary.json` interim: every wb cell has screen-feasible single edits, `confirmed` not yet
  final). Interim cost comparison (tables.md): LLM cost per solving completion = 1.9–4.9 GPU-min +
  1.8–5.4 SPICE-min, vs E-c SPICE-min to first screen-feasible (fixed / E[random]) 1.1–56 / 6.4–26.
  Final comparison after E-c finalizes.

## Deviations / notes

1. `crenv.sh` could not be `source`d in this harness; `envrun.sh` is a verbatim inline copy of its
   exports + `TMPDIR=/tmp/cr-7cd7ffc3-d`.
2. Local scoring code is HEAD `a0e4edcc6`, kernels ran pin `cc5a836bb`; the only diff in the
   scoring path (`proposal`, `bench_anchor_prep`, `lna/`, lib) is `mysolve.py` (+14/−2, not in
   `_margins`).
3. The kernel skipped WL-duplicate edits (dup of the anchor or an earlier edit); locally every
   valid edit is scored (dedup is on exact token sequence, credit to all). No edit equals the anchor.
4. Invalid edits (ZS 14, FS 17) are round_trip ParseErrors: 25 are inline comments on device
   lines (`L L4 n5 n0  # Series inductor …`), 6 duplicate device names. Scored as invalid per
   pre-reg (not repaired).
5. Stability is not a spec constraint: most feasible Qwen solutions have μ_min < 1 (0.87–1.09) —
   so do the reference templates (E-a δ=0 seed 1: 0.86–1.01). Not used for scoring.
6. Sizing wall-times (SPICE-min) were measured on a shared, loaded box (~105 s per wb seed vs
   ~70–80 s in E-c); cost comparisons are indicative.
7. Completion GPU time is matched to cells by request order in `llama-server.log` (single slot);
   eval-token counts match `completion.meta.json` for all 64 completions.
