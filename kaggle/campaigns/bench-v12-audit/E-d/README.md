# E-d — Real Qwen baseline, matched zero-shot vs few-shot (bench-v1.2)

Pre-reg: `kaggle/PREREG-BENCH-V12-AUDIT.md` § E-d (frozen 2026-09-26). Scored 2026-09-26 on
this box. **Era stamp (git HEAD at scoring start): `a0e4edcc6ac10ee030730bbe0e40f958c5fc42be`.**
All three kernels ran the pinned code `cc5a836bb` (`*/editcap/KERNEL-MANIFEST.json`, clone_head
verified). **FINAL** — Qwen3-32B and Qwen3-14B, both conditions. (Interim 32B-only commit:
`2f4fa2fe4`; its 32B numbers are unchanged here.)

## What was run

| kernel (private, devavratpatni) | model | runs (16 cells each) | kernel wall |
|---|---|---|---|
| circuit-repro-bench-v12-audit-ed-32b-zs | Qwen3-32B Q4_K_S | ZS-s1, ZS-s2 | 204 min |
| circuit-repro-bench-v12-audit-ed-32b-fs | Qwen3-32B Q4_K_S | FS-s1, FS-s2 | 187 min |
| circuit-repro-bench-v12-audit-ed-14b | Qwen3-14B Q4_K_M (HF, sha256 verified) | ZS-s1, FS-s1, ZS-s2, FS-s2 | 217 min |

Arm B, k=3, temp 0.7, 8192-token cap, `EDITCAP_RECOVER_REASONING=1`, 2×T4 layer split. FS prompts
carry the generic `WORKED EXAMPLE` block (checked: present in every FS prompt, absent from every ZS
prompt). s1/s2 raw outputs byte-identical: 0/16 in every condition.

## Scoring (primary, pre-registered, local)

- `ed_score.py enumerate`: every archived `edit<i>.net` (384) → `proposal.round_trip`. Invalid
  edits are recorded with their error. Valid edits (349) are deduped per cell on the exact token
  sequence, giving 326 unique (cell, tokens) in `cand.json`. Each is sized once and credited to
  every edit that carries it.
- `ed_score.py run 6`: each unique (cell, tokens) × seeds 1,2,3 goes through
  `bench_anchor_prep.smoke_run(tokens, <lib>/<cell>/spec.yaml, seed, 2500, "bptm45")`.
  feasible = `result["feasible"]`; worst margin = `mysolve._margins`. One subprocess per job,
  ≤6 in parallel, appended to `score.jsonl` as each finishes. 978 rows, 0 crashes, and every
  valid edit has 3 seeds.
- `ed_summarize.py` → `summary.json` + **`tables.md`** (all tables, including per-cell margins and cost).

Other files:
- `edits.jsonl`: one row per edit — validity, token key, in-kernel outcome, topology flags.
- `completions.jsonl`: one row per completion — finish reason, tokens, empty/no-edit, and
  llama-server timing.
- `32b-zs/`, `32b-fs/`, `14b/`: kernel outputs verbatim, minus the llama.cpp (148 MB) and
  ngspice (9 MB) binary caches.
- `envrun.sh`: the environment wrapper.

## Main table

**Solved** means any edit of any sample is feasible at any of seeds 1–3 (3×2500, bptm45). The
split is SYN = 6 synthesis cells and RET = 10 E-b RETRIEVAL cells (all 8 nb + wb-s11n10-g10-b0824
+ wb-s11n10-g12-b0824). EDGE = wb-s11n8-g12-b0530 (E-a).

| model | cond | edits | valid | sizable | feasible edits | cells solved: all / SYN / RET | solved by an edit feasible at ≥2/3 seeds | EDGE | s1/s2 solved: both, s1-only, s2-only | in-kernel (3×600) solved | GPU min / completion (mean, median, max) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 32B | ZS | 96 | 82 (85%) | 81 | 5 (5.2%) | **3 / 2 / 1** | 2 | no | 1, 0, 2 | 0 | 4.90, 4.80, 9.6 |
| 32B | FS | 96 | 79 (82%) | 79 | 7 (7.3%) | **5 / 3 / 2** | 5 | no | 1, 2, 2 | 3 | 4.32, 3.20, 9.6 |
| 14B | ZS | 96 | 92 (96%) | 91 | 1 (1.0%) | **1 / 1 / 0** | 0 | no | 0, 1, 0 | 1 | 2.34, 2.34, 4.4 |
| 14B | FS | 96 | 96 (100%) | 95 | 11 (11.5%) | **6 / 4 / 2** | 5 | **yes** | 3, 1, 2 | 3 | 1.77, 1.78, 2.7 |

Across all 128 completions:
- 0 were empty, 0 had no edits, 0 hit finish=length, 0 were recovered from reasoning, and 0 had
  an LLM error.
- Mean completion tokens: 32B ZS 3,336, 32B FS 2,688, 14B ZS 3,233, 14B FS 2,451.
- GPU time is the llama-server `total time` per request. It is matched to cells by request order;
  the eval-token count equals `completion_tokens` for all 128.

Per cell (full margins in `tables.md`):
- **No narrowband cell was solved by any model or condition (0/8 × 4).** These are all RETRIEVAL
  cells. Best nb margins are −0.10…−0.53, and FS nb edits are sometimes much worse (−2…−4.7).
- The union over all four groups covers all 6 SYN cells and both wb RET cells.
- 14B FS is the only group that solves the EDGE cell (`R Rf n2 n1`, 3/3 seeds).
- Every feasible solution is razor-thin (worst margin +0.0000…+0.009), like the reference
  templates.

## Topology classes emitted (valid edits)

| model | cond | wb valid edits | narrow shunt-fb (`analyze_qwen_vs_claude_topo`) | widened shunt-fb | widened, VIN-side variant | wb cells with ≥1 widened fb edit | widened-fb edits feasible | nb valid | nb tank | nb cascode |
|---|---|---|---|---|---|---|---|---|---|---|
| 32B | ZS | 36 | 0 | **0** | 0 | 0/8 | 0 | 46 | 36 | 0 |
| 32B | FS | 40 | 4 | **14** | 14 | 8/8 | 7 | 39 | 28 | 1 |
| 14B | ZS | 45 | 2 | **0** | 0 | 0/8 | 0 | 47 | 29 | 1 |
| 14B | FS | 48 | 6 | **14** | 21 | 8/8 | 7 | 48 | 15 | 1 |

The widened detector is `ed_score.topo_flags`:
- It flags any R between an input-transistor gate net and a target net outside the input C/L
  component.
- An input-transistor gate net is a MOS gate reachable from VIN1 through C/L elements only.
- A target net is a non-diode drain, an L–C tank node, or VOUT1.

It catches `R n4 n1` (tank → gate) and `R VOUT1 n1`, which the narrow detector misses.

The "VIN-side" variant also counts an R from VIN1 itself (the 14B FS `R Rf VOUT1 VIN1` /
`R Rf n4 VIN1` edits, feedback around the input DC-block cap).

The narrow detector's nb hits (32B 1+4, 14B 0+3) are resistors to the common-gate anchor's
AC-grounded bias gate, not input feedback; the widened detector gives 0 on nb. No anchor triggers
either detector.

**What the feasible edits are:**
- **FS, both models:** every feasible edit adds a single feedback resistor. The forms are
  `R n2 n1` (drain→gate, the template move), `R n4 n1`, `R VOUT1 n1`, `R n2 n3` (to the AC-coupled
  PMOS gate), and on 14B also `R VOUT1 VIN1` / `R n4 VIN1`.
- **ZS, both models:** no feedback at all. The solves come from series input inductors in front
  of the DC-block cap (`L VIN1 n0`, `L VIN1 n0 + C n0 VSS`; 14B: `L VIN1 n_in` + re-wired C4/L1),
  plus one 32B rewrite that routes VIN1 through two inductors via the PMOS bias-diode node.
- **Narrowband:** no model ever proposes E-c's only nb solution `L VIN1-n1` (input → CG gate).
  FS models mostly add resistors to the nb cells as well, i.e. they transfer the wideband example
  to the wrong problem.

## ZS vs FS (pre-reg: no claim unless ≥ 3 cells differ)

- **14B:** ZS-only 0, FS-only 5 → 5 differ → **claim permitted: FS > ZS** (6 vs 1 cells; 5 vs 0
  at ≥2/3 seeds; all differences in the FS direction).
- **32B:** ZS-only 2, FS-only 4 → 6 differ → **a claim is permitted, but the direction is mixed**.
  The net any-seed gain is +2 cells (5 vs 3). At ≥2/3 seeds it is 5 vs 2. With 2 samples/cell the
  size of the 32B FS gain is not established.
- **Robust in both models:** few-shot changes the topology class emitted. Widened shunt-fb goes
  from 0 of 81 ZS wideband edits to 28 of 88 FS wideband edits, and appears in 8/8 wb cells under
  FS. Every FS solve is a feedback resistor. This confirms the earlier finding that the move is
  "knowledge, not capacity", now with a matched ZS control.

## 32B vs 14B

- **Few-shot:** 14B is at least as good as 32B on every metric:
  - cells 6 vs 5, including EDGE;
  - edit validity 100% vs 82%;
  - feasible-edit rate 11.5% vs 7.3%;
  - ≥2/3-seed solves 5 vs 5;
  - about 2.4× less GPU time per completion (1.8 vs 4.3 min).
- **Zero-shot:** 14B is worse (1 vs 3 cells). 32B finds the series-input-L route more often.
- 32B's validity loss is almost entirely formatting. Of 31 invalid 32B edits, 25 have inline
  `# comment` text on device lines and 6 reuse a device name. 14B has 4 invalid edits.
- For the learner path (E-e), 14B is therefore not a weaker proposer on this benchmark once shown
  the technique.

## Against E-b / E-a / E-c labels (E-c final: 16/16 SEARCH-TRIVIAL)

- **RETRIEVAL (10):** ZS 1 / 0, FS 2 / 2 (32B / 14B) — only the two wb RET cells; 0/8 nb.
- **SYNTHESIS (6):** 32B ZS 2, 32B FS 3, 14B ZS 1, 14B FS 4.
- **SEARCH-TRIVIAL:** every cell is SEARCH-TRIVIAL (E-c `README.md`). So per the pre-reg a solve is
  topology-reasoning evidence only if it is cheaper than the search.

**Sequential cost, load-independent** (`tables.md`, "Sequential LLM cost"). Each group runs sample
1, then sample 2. Each completion costs its GPU time plus one seed-1 sizing call per new valid edit,
in order, stopping at the first seed-1-feasible edit.

Wideband (8 cells):

| group | cells solved | seed-1 sizing calls | GPU-min |
|---|---|---|---|
| 14B FS | 6/8 | 22 | 19 |
| 32B FS | 5/8 | 24 | 36 |
| 32B ZS | 3/8 | 29 | 54 |
| 14B ZS | 1/8 | 37 | 35 |

E-c needs Σ E[random] = 68.6 calls (Σ fixed-order 126) to solve 8/8.

- **Per solved wb cell:** 14B FS uses ≈3.7 calls + 3.2 GPU-min. E-c random order needs ≈8.6 calls.
- **Cells where E-c is expensive:** the LLM is clearly cheaper when it succeeds.
  - EDGE wb-s11n8-g12: 14B FS takes 1 call vs E-c 39 fixed / 11.8 random.
  - wb-s11n10-g10-b0530: 32B ZS takes 6 calls vs 43 / 19.7.
  - wb-s11n9-g10: 32B ZS takes 4 calls vs 31 / 8.9.
- **Easy b0824 cells** (E-c 3 fixed / 4.5–6.8 random): about parity.

Narrowband (8 cells): every LLM group spends 39–47 calls (+31–100 GPU-min) and solves 0/8. E-c
solves 8/8 at 23–46 calls per cell with one inductor move.

Calls are CPU sizing calls at 2500 evals (≈0.5–1.8 min each here, depending on box load). GPU-min
is 2×T4 time, so the two units are not additive.

## Deviations / notes

1. `crenv.sh` could not be `source`d in this harness. `envrun.sh` is a verbatim inline copy of its
   exports plus `TMPDIR=/tmp/cr-7cd7ffc3-d`.
2. Local scoring code is HEAD `a0e4edcc6`; the kernels ran pin `cc5a836bb`. In the scoring path
   (`loop/proposal.py`, `bench_anchor_prep.py`, `lna/`, the v12 lib), the only difference is
   `mysolve.py` (+14/−2, outside `_margins`).
3. The kernel skipped WL-duplicate edits (duplicates of the anchor or of an earlier edit). Locally,
   every valid edit is scored: dedup is on the exact token sequence, with credit to all carriers.
   No edit equals the anchor.
4. Invalid edits are round_trip ParseErrors: inline comments on device lines, or duplicate device
   names. They are scored as invalid per the pre-reg (not repaired).
5. Stability is not a spec constraint. Many feasible LLM solutions have μ_min < 1, as do the
   reference templates and most E-c solutions. Cells solved with ≥1 feasible seed at μ_min ≥ 1:
   32B ZS 1, 32B FS 3, 14B ZS 1, 14B FS 3 (`summary.json` `solved_with_mu_min_ge_1`).
6. Sizing wall times were measured on a shared box whose load changed during the run (≈50–110 s
   per wb seed). Cost comparisons therefore use sizing-call counts; SPICE-minutes are indicative.
7. Widened detector definition: the pre-reg says "R from any drain/tank node to the input gate".
   The implemented definition is above. The VIN1-inclusive variant is reported separately, not
   substituted.
8. The 14B kernel ran runs interleaved (ZS-s1, FS-s1, ZS-s2, FS-s2); the 32B conditions ran in
   separate kernels. Same pinned code, lib, and settings.
