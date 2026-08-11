# WP-OBSERVE — stop discarding the internal-circuit data

**Status:** pre-registered 2026-08-11, before a line of feature code was written.
**Branch:** `lna-data`. **Owner:** the WP-OBSERVE executor (Session 7).
**Series:** continues `plans2/01-DATA … 08-DHRUVA-GOAL`.

---

## 0. Why this work package exists

Block 6 of `STRUCTURE_LOGIC.md` exists because of one lesson: *the pipeline was
throwing away its most expensive byproduct.* Before `datastore.py`, thousands of
ngspice evaluations produced one number each and were discarded; `sim_points.jsonl`
(66,664 rows, 26 MB) is what stopping that looks like.

**The same mistake is still in progress one level down.** Every one of those
66,664 evaluations solved a full DC operating point — every device's drain
current, transconductance, output conductance, terminal voltages, threshold — and
then threw all of it away to keep a seven-number metric vector. `run_and_extract`
literally runs `op` and parses one scalar (`idd`) out of it.

That discarded data is not a nicety:

* It is **causal where the metric vector is correlational.** `s21_db` says a
  design has gain; `gm`/`gds` per device says *which device* makes it and whether
  the sizer is buying it with current or with width.
* It is the **only** thing that distinguishes "infeasible because the topology
  cannot" from "infeasible because half the transistors are in cutoff" — a
  distinction this program has had to re-diagnose by hand at least four times
  (finding #9's off-MOS split, 19.2's four blocked externals, 21's DC-return
  rules, 24's gate-vs-source input motif).
* It is **free**. The `.op` is already solved. Reading it out costs `print`
  lines, not simulation time.

## 1. Scope

1. `lna/extract.py` gains a *passive* operating-point read-out: per-device
   `id/gm/gds/gmbs/vgs/vds/vbs/vth/vdsat` (+ derived region) for MOSFETs and
   `ic/ib/vbe/vbc/gm/cpi/cmu` for bipolars, plus node voltages and source branch
   currents, taken from the `op` the deck **already runs**.
2. A new gitignored append-only table `lna/data/op_points.jsonl`, written through
   `lna/datastore.py` (`row_op` / `TABLES["op_points"]`).
3. `lna/size.py` accumulates those rows in its evaluation path, with explicit
   volume control.
4. Per-element noise contributions are attached **by reuse** of
   `extract.measure_noise_budget` — never recomputed, never re-implemented, and
   only where a noise deck is already being run.

**Out of scope:** any change to a frozen protocol (NDL@256, ref-v3, snapshots),
any change to what is *gated*, any change to `surrogate.py` / `critic_gnn.py`
(owned by a concurrent agent this session).

## 2. Design

### 2.1 The read-out is print-only

ngspice exposes BSIM4 instance quantities as `@m<dev>[<param>]` vectors. Probed
on this build (`ngspice_con`, 45 nm BSIM4 card): `id, gm, gds, gmbs, vgs, vds,
vbs, vth, vdsat, cgg, cgs, cgd` are available; `cd, ids, is, ig, ib, vth0, rg,
von, beta, gmb` are **not** (`Error: no such parameter`). There is no `region`
parameter — it is derived here from `(vgs, vth, vds, vdsat)`.

Three hard rules, in descending order of how badly violating them would hurt:

* **N1 — never `save`.** `save @m1[id]` before `sp` *restricts* the saved set and
  silently deletes the S-parameters. Single-`op` device parameters need no `save`.
  This WP emits **zero** `save` lines. (Verified on the probe deck: `print
  @m1[gm]` after a bare `op` returns the value.)
* **No extra ngspice invocation.** The read-out lines are appended to the control
  block *between* the existing `print idd` and the existing `sp` line. Same
  process, same analysis, same op point.
* **Default path byte-identical.** `control_block`/`build_deck`/`run_and_extract`
  take the probe as an optional argument defaulting to `None`; with it absent the
  emitted deck text is byte-for-byte what it is today. This is asserted in-process,
  not assumed.

> **Interpretation of "existing deck bytes must be unchanged".** Physically, a
> value cannot leave ngspice without a `print`, so the capture path *does* add
> `print` lines. The constraint is honoured in the two ways that are testable and
> that matter: (a) with capture off — which is every existing call site until this
> WP wires new ones — the deck is byte-identical; (b) with capture on, the added
> lines are **print-only**, add no analysis, no `save`, no `.option`, no `let`,
> and are proven not to move a single metric digit (4.3).

### 2.2 Node voltages

`print all` in the `op` plot dumps every vector without needing to enumerate node
names. Internal model nodes (`m1#body`, `m1#gate`, `m1#dbody`, `m1#sbody` — four
per MOSFET, artefacts of `rgatemod`/`rbodymod`) are **dropped**: they are
model-internal, ~1e-11 V, and would be 4N floats of nothing. Kept: real net
voltages and `*#branch` currents (which is how per-source current, including the
supply, is recovered).

### 2.3 Noise contributions — reuse only

`extract.measure_noise_budget` already computes per-element output-noise power,
per-mechanism MOSFET splits, and the share of the excess noise factor. It runs
its own deck (it must: per-source noise vectors only exist when the `noise` line
carries a `pts_per_summary` argument).

Therefore: an op row carries a noise budget **only when one has already been
computed for that point** — i.e. `size._noise_budget_row`'s existing call in
`log_l2_result`, which is passed through, not repeated. No new noise invocation
is added anywhere. `size._noise_budget_row` is reused verbatim as the compactor.

Additionally, `measure_nf`'s own deck runs an `op` — so on the `log_l2_result`
path (the hub used by `search.py`, `evolve.py`, `d3_campaign.py`,
`nf_campaign.py`, `nf_moves.py`, `g4_search.py`, `relabel_mf.py`) the operating
point is captured from **that already-running deck**, again with no extra
invocation. `build_noise_deck` documents that the noise deck's DC is identical to
the sizing deck's; 4.2 tests that claim numerically rather than trusting it.

### 2.4 Row schema and provenance

`op_points.jsonl` rows are stamped like `sim_points` rows — `wl_hash`, `spec`,
`x`, and (unlike `sim_points`, which stores only `x`) the decoded `params`,
because `x` is meaningless without the `kind_ranges` box that decoded it — **plus**
the Block-6 label-domain stamps, so rows from different harness eras are
distinguishable forever:

```
{"kind":"op", "op_schema":1,
 "wl_hash":..., "spec":..., "stage":"final|zoaf|label", "eval_i":...,
 "x":[...], "params":{...},
 "devices":{"m1":{"id":...,"gm":...,"gds":...,"gmbs":...,"vgs":...,"vds":...,
                  "vbs":...,"vth":...,"vdsat":...,
                  "region":"sat|triode|cutoff|subthreshold"}, ...},
 "nodes":{...}, "branches":{...},
 "metrics":{... the same metric vector the point row carries ...},
 "noise_budget":{...} or null,
 "harness":{"recipe":..., "w_finger":..., "mos_fingers":..., "inductor_q":...,
            "nf_method":..., "nf_gated":..., "bias_rules":..., "deck":"sizing|noise"},
 "provenance":{... the caller's own source_arm/seed/token_file ...},
 "git_sha":..., "ts":...}
```

`op_schema` is the era counter: any future change to which parameters are read or
how a region is derived bumps it, and no consumer may pool across it silently —
the same rule `nf_method`, `w_finger` and `zoaf_cfg.nf_gated` already carry.
`harness.deck` records **which deck the op came from** (the port-driven sizing
deck or the series-Rs noise deck), because that is the one thing about these rows
that is not obvious from the stamps.

### 2.5 Volume control

`sim_points.jsonl` is 26 MB for 66,664 rows — **377 bytes/row**, measured. An op
row is bigger by roughly the device count: predicted **~1.5-2.5 kB** for a
10-16-device LNA (5-7x a point row).

Rules:

* **Always logged, never subsampled:** the final/best point of a sizing run, and
  every repeat-probe evaluation. These are the rows that pair with an L2 label,
  which is the pairing that makes the table trainable at all.
* **Inner ZOAF points:** logged at 1 in `LNA_OP_SUBSAMPLE` evaluations.
  **Default `8`.** (`0` disables inner sampling entirely - final points are still
  logged; `1` logs every evaluation.)
* **Master switch** `LNA_OP_LOG` (default `1`), so a campaign can turn the whole
  mechanism off without a code edit.

**Justification of the default.** Two constraints meet at ~8.

1. *Byte budget.* At 1/8 and ~2 kB/row the op table grows at ~250 bytes per
   ngspice evaluation, against the point table's 377 - i.e. **the new table stays
   smaller than the table it rides along with.** A campaign the size of the one
   that produced the 66k point rows would add ~8.3k op rows, about 17 MB. Logging
   every evaluation would be ~130 MB and would make the table the largest thing
   in the data directory, which is exactly the kind of unforced cost that gets a
   logging feature turned off by the next session.
2. *Information.* The scientific content of an inner point is the **trajectory** -
   how the operating point moves as ZOAF walks. Sizing runs here are ~50-400
   evaluations (`n_evals` in the store), so 1/8 leaves 6-50 samples per run,
   enough to see a trajectory, while the endpoint - the only point that is ever
   quoted as a result - is captured exactly, every time.

Subsampling is **deterministic** (every 8th evaluation in call order), not
random: a stochastic sampler would make two runs of the same seed produce
different tables, and this program's reproducibility rules (snapshots, replay
fences) are worth more than the marginal unbiasedness.

### 2.6 Append-only

`op_points.jsonl` is append-only like every other table, is added to `.gitignore`
next to `sim_points.jsonl` (same reason: bulky, regenerable-ish byproduct), and is
**not** added to any existing snapshot. Nothing already written to any table is
touched.

## 3. Predictions (registered before measurement)

| # | prediction | how it will be judged |
|---|---|---|
| P1 | Runtime overhead of capture-on vs capture-off is **< 2%** (target < 5%) | 20 evaluations of a reference deck, both arms, evals/sec |
| P2 | Logged `id`/`gm` match a direct independent op-only probe of the same deck to **relative 1e-6** | `lna/ref/check_op.py` |
| P3 | Every metric (`s11_db`, `s21_db`, `idd_ma`, `k_min`, ...) is **bit-identical** with capture on and off | full-precision compare on a reference deck |
| P4 | Row size **1.5-2.5 kB** for a 10-16-device LNA | measured on the demo run |
| P5 | The operating point read from the **series-Rs noise deck** equals the one read from the **sizing deck** to relative 1e-6 (`build_noise_deck` asserts this in prose; nobody has ever tested it) | `check_op.py` |

P5 is the prediction most likely to be wrong, and it is registered precisely
because it is currently a documentation claim with no measurement behind it. If
it fails, `harness.deck` is what keeps the two populations separable and the
failure becomes a finding rather than a contamination.

## 4. Validation plan

**4.1 Golden check (`lna/ref/check_op.py`, new, joins the regression set).**
On `ref/ref24_tapped.cir`: run the full sizing deck with capture on; independently
run a bare `op`-only deck built from the same body and params; assert every
device's `id` and `gm` agree to relative 1e-6. A logging instrument nobody
validated is worse than none.

**4.2** Same file: capture from `measure_nf`'s noise deck, compare device-by-device
against the sizing-deck capture (prediction P5).

**4.3 Invariance.** `run_and_extract` with and without capture on the same body +
params, comparing every metric at full `repr` precision.

**4.4 Byte-identity.** Assert `build_deck(...)` with no capture argument produces
exactly the string it produces today.

**4.5 Overhead.** 20 evaluations of the tapped reference, capture off vs capture
on vs capture on + logging to the table; report evals/sec and the percentage.

**4.6 Regression suite green before and after** - vocab guard (analoggenie
python), `screen.py` legacy 59.4%, `pipeline_yield` 40/42, `ref/check_ref.py`,
`ref/check_nf.py`, `ref/check_stab.py`, `ref/check_bjt.py`, `calibrate_specs.py`.
Baseline captured before any edit.

## 5. What would make this WP a failure

* Overhead >= 5% -> the subsample default drops and the inner-loop hook is
  reconsidered; the final-point hook stays either way.
* Any metric moving by any digit with capture on -> the feature is not passive and
  must not ship in that form.
* A golden mismatch on `id`/`gm` -> nothing ships; the read-out is wrong.

## 6. Deliverables

* `lna/plans2/09-WP-OBSERVE.md` (this file), committed **before** the code.
* `lna/extract.py`, `lna/datastore.py`, `lna/size.py`, `.gitignore`.
* `lna/ref/check_op.py` (golden + invariance + overhead harness).
* `FINDINGS.md` 30, `JOURNEY.md` stage 25, `STRUCTURE_LOGIC.md` Blocks 5 and 6.
