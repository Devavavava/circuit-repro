# Trajectory rows → training data

`trajectory.schema.json` defines one row of the reasoning loop's log. The driver
appends a row **per phase, per candidate**, to
`/kaggle/working/trajectory/<run_id>.jsonl`, and checkpoints after every candidate
so a Kaggle session timeout loses nothing already measured.

## What a run looks like

For one spec, the loop emits, in order:

- one `consult` row (the playbook hits it retrieved),
- then per proposal `k` in `0..K-1`: a `propose` row, a `roundtrip` row, a
  `screen` row, a `bias` row, a `size` row,
- one `diagnose` row (the margin table the model reads),
- per edit: an `edit` row + its own `roundtrip/screen/bias/size` rows,
- the loop ranks by `spec.objective` and writes the best design in
  `solve_spec.py`'s `designs/` format.

Every row shares `run_id` + `spec`; `iteration` orders candidates; `phase` orders
stages within a candidate.

## Why these fields become training data

The program's stated learning target (00-OVERVIEW R1, mirrored in
`datastore.margins_for`) is **post-sizing margins, not raw metrics**. A
trajectory row already carries every field a future fine-tune needs, keyed on a
stable graph identity:

| field                         | trains …                                              |
|-------------------------------|-------------------------------------------------------|
| `consult_hits` + `spec`       | retrieval-conditioned proposing (what to recall)      |
| `proposal.netlist` + `wl_hash`| topology proposals; `wl_hash` dedups + joins to labels|
| `proposal.predicted_deltas` vs `sized.margins` (`prediction_vs_outcome`) | metric-prediction calibration (predict-then-measure) |
| `l0_pass` / `bias_conducting` | cheap structural rejection before any sim             |
| `sized.margins` / `feasible`  | the margin-regression target itself                   |
| `diagnosis` → `edit` → new `sized` | credit-assigned edits (did the edit help?)        |
| `error_verbatim`              | failure-mode classification (parser/sim faults)       |

Prediction-vs-outcome is deliberately first-class: a model that predicts its own
metric deltas and is scored against the simulator is self-calibrating, and the
gap is a direct supervised signal.

## Label-domain rule (do not skip)

Kaggle-produced rows are a **separate label domain** from the box's golden store
until a goldens-parity pooling ruling (see `kaggle/PLAYBOOK.md`). Reasons: the
ngspice build, the checkpoint set, and the sizing budget may differ from the
box's golden geometry (`to_spice.layout_cfg` stamps geometry precisely because
different geometry = different domain). Merge back is via
`lna/sync_lines.py --dry-run` first; a row's `run_id`, ngspice version, and
layout config travel with it so provenance is never lost.
