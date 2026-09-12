# CAMPAIGN reflect-positives-v0 — can the self-learning channel derive lessons now that positives exist? (GO 2026-09-13)

User GO ("setup and run reflect with positives"). First reflect pass over a
gf180 corpus CONTAINING SUCCESSES (the externals wins) — every prior gf180
reflect ran on all-failure records and produced only mechanics lessons
(selflearn-gf180-v0 leg2: channel worked, zero capability content).

## Question

Given its own record with 16 feasible gf180 results (and matched failures),
does the sanctioned reflection channel — reflect.py VERBATIM, no prompt
changes, no human hints — write admitted entries that capture (a)
topology-family → outcome facts, and/or (b) structural conventions
(input DC-blocking / bias-network presence) visible in its own record?

## Frozen corpus (all standard results.jsonl form, all on origin 1ee92a34)

- kaggle/campaigns/externals-gf180-v0/era-ext-9167fd46/leg-c1-v02 (10 wins)
- .../leg-c3-v02 (6 wins) and .../leg-c4 (0/24 valid null, contrast)
- kaggle/campaigns/selflearn-gf180-v0/era-5a87ee18/leg1-arch (0/24, contrast)

EXCLUDED and logged: editcap adjudication records (per-arm results-<X>.jsonl
format; the reflect corpus loader takes results.jsonl dirs — a loader
extension is a separate change, deferred). Consequence: the fence-death
(L-to-VIN1) lesson is NOT derivable in this v0; only what the four dirs
support. Corpus loading validated pre-launch via `reflect.py
--print-prompt` on the box (feasible rows render with margins).

## Run

Standalone reflect (NOT a campaign leg): Kaggle GPU kernel, loop-gpu copy
with an added RUN_MODE=reflect branch that execs
`kaggle/loop/reflect.py --v0-dir <4 dirs> --cap 12 --overlay-dir
<out>/system-playbook --traj <out>/reflect.jsonl`. Era = origin tip at
launch (1ee92a34 expected). Wall ≈ bootstrap + minutes.

## Pre-set evaluation (frozen; QUALITATIVE — no capability claim from this run)

- E1: does ≥1 ADMITTED entry state a family→outcome fact grounded in the
  feasible rows (quoting its own record)?
- E2: does any admitted entry reference input-path/bias structure?
- E3: admission stats (accepted/rejected + reasons) vs the leg2 baseline
  (12 accepted / 63 rejected, all-mechanics).
- The CAPABILITY measurement (consult-on vs consult-off arm) is explicitly
  OUT of scope — separate pre-reg if these entries warrant it.

Archive: kaggle/campaigns/reflect-positives-v0/ (overlay entries verbatim +
reflect.jsonl + kernel log). Store writes: none; overlay stays in archive.
