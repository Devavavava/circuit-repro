# circuit-repro `engineer` -- environment + benchmark release

**Scope of this package (E-5 ruling, 2026-08-16): the environment and the
in-house benchmark only.** The dhruva/GNSS-balun LNA case study and the external
AnalogGym scoreboards are staged for a later release. Nothing here is frozen as
"v1.0" until the protocol freeze lands (see PROVENANCE).

## What this is

An **RF-grade agentic analog-design environment + benchmark + measured
baselines**, framed as in the founding charter (§1):

- **Environment** (`engineer/env.py`) -- a *budgeted, counted, observable,
  deterministic* interface onto a golden-validated ngspice harness. Searches,
  agents, and unattended loops run and are compared over it.
- **Benchmark** (`engineer/tasks.py`) -- a registry of 8 pinned tasks (7 scoring
  + 1 smoke), each pinned to the exact stored reference row its budget and
  numbers come from, with a compute-matched scoring protocol
  (`engineer/PROTOCOL.md`).
- **Measured baselines, including honest negatives.** The scoreboards ship the
  CMA-ES and random null arms; the memory (E-3) and unattended-loop (E-4)
  harnesses ship results that came out **negative** (memory: warm < cold on 7/7
  tasks; loop: 0/10 feasible) -- these are deliverables, not gaps. The field's
  failure mode is scaffolding without measurement; this line measured, and
  published the negatives.

## Dependencies (the version cliffs are real)

- **Python 3.11 + numpy** (scipy + pyyaml for the shared core). No installs
  beyond these for the in-house benchmark.
- **ngspice >= 42** -- **VERSION CLIFF**: the RF decks use the `sp` S-parameter
  analysis with `portnum`/`z0` ports. conda-forge's ngspice **41 segfaults** on
  that deck; **36 rejects `portnum` outright**. Build ngspice **47** from source
  (this line's reference), or provide a >= 42 binary. See `PORTING.md`.
- **The shared core `lna/`** (datastore, spec, size, extract, to_spice,
  topology, moves, null_sizer, playbook, ref/, specs/) -- lives on the
  circuit-repro **main** branch. The environment imports it at runtime. Fetch
  the main branch alongside this release; the env dep-shim walks up to find it,
  or set `$LNA_DEPS_ROOT`.
- **ZOAF** (MIT) at pinned SHA `62615e91` -- imported by `null_sizer`; fetch per
  `UPSTREAM.md`.

### Manual fetch: the 45 nm BSIM4 model card (license status UNKNOWN)

> The 45 nm BSIM4 process model card (`45nm_bulk.txt`) is **NOT bundled with
> this release and is NOT auto-fetched.** Its redistribution status is
> **unknown**: the file carries no license header (header line: `* BPTM 45nm
> NMOS`), and the AutoCkt repository it lives in has no LICENSE file. To run any
> evaluation you must fetch it yourself, manually, from the AutoCkt repo:
>
> - Repo: `ksettaluri6/AutoCkt` at pinned SHA `a6c8a61d`
> - Path in that repo:
>   `eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt`
> - Place the clone so the env dep-shim finds it (at `<repo>/AutoCkt/repo/...`),
>   or point `$LNA_DEPS_ROOT` at a tree that contains it.
>
> **License status: unknown.** BPTM cards were historically released by the UC
> Berkeley BSIM Group for open use, but this specific file states no license.
> Do not redistribute it without clarifying its provenance. The environment
> reads it at runtime only; nothing in this package copies it.

### Optional: VACASK (harmonic-balance cross-check) -- out of scope

VACASK is **AGPL-3.0** and is **not bundled**. It is used only for the `check_hb`
IIP3 cross-check (case-study material, a later release). To reproduce that
cross-check, build VACASK from source per `PORTING.md`; it is **not required** to
run the benchmark.

## Benchmark protocol

The scoring protocol is pre-registered in `engineer/PROTOCOL.md` (committed alone
before any scoring run; the `§EXT` appendix committed alone before any external
cell ran -- the commit ordering is the pre-registration timestamp). The registry
pins are in `engineer/tasks.py` and mirrored, for offline listing, in
`engineer/tasks_registry_v0.json`.

## Reproduction commands

```bash
# 0) list the benchmark registry -- works WITHOUT lna/ or the model card:
python engineer/tasks.py --list
python engineer/tasks.py --list --long

# --- everything below needs the shared core (lna/) AND the manual 45 nm card ---

# 1) re-derive the registry pins against the live store (needs lna/data):
python engineer/tasks.py --check

# 2) the end-to-end smoke (150 evals, ~300 ngspice calls, lands infeasible):
python engineer/baseline_run.py

# 3) the in-house scoreboard (7 tasks x 2 arms x N seeds):
python engineer/score_run.py

# 4) the memory paired harness (E-3, warm vs cold):
python engineer/memory_harness.py

# 5) the unattended loop pilot (E-4):
python engineer/loop_run.py

# 6) API-hardening tests:
python engineer/test_env.py
```

## What a stranger can do WITHOUT the manual fetches

- `python engineer/tasks.py --list[/--long]` -- the full benchmark registry,
  from the shipped `tasks_registry_v0.json`.
- Read every shipped scoreboard/golden JSON and every doc (PROTOCOL, E3/E4,
  EXT-CALIBRATION, E5-PACKAGING, MANIFEST).
- Inspect all source.

## What a stranger canNOT do WITHOUT the manual fetches

- Run ANY evaluation (`baseline_run`, `random_run`, `score_run`,
  `memory_harness`, `loop_run`, `test_env`, `ext_*`). All route through
  `env._bind_runtime_deps()`, which requires `lna/` + ZOAF + the 45 nm card. The
  shim **fails loudly** when a dep is missing (by design).
- `tasks.py --check` (needs the live `lna/data/topo_labels.jsonl`).

## PROVENANCE

- **Era stamps.** Every benchmark reference row carries an `era` field.
  `current` means the row was produced after the 2026-08-10 multi-finger cutover
  (`w_finger == 2e-6`). FINDINGS §43.1 measured 1,109/1,215 stored designs
  era-stale on >= 1 metric -- an era stamp is the difference between a reference
  number and a number from a simulator that no longer exists.
- **Replay fences.** Goldens (`ext_golden_v0.json`, `ext_ldo_golden_v0.json`)
  record in-process AND separate-process replay reps so a stranger can confirm
  determinism (spread 0.000000 on the anchor).
- **Pre-registration.** PROTOCOL.md and its §EXT appendix were each committed
  ALONE before the runs they govern; scoreboard artifacts stamp the
  pre-registration SHA. This ordering is in git history -- ship the history, not
  just a snapshot, to preserve it.
- **"Frozen v1.0"** means: once the user rules the protocol freeze, the frozen
  commit SHA becomes the cited benchmark version; the null scoreboards at that
  commit become the fixed reference future arms compete against. **As of this
  package the protocol is NOT frozen** -- these are real measurements under the
  working protocol, citable by their pre-registration SHAs, not yet locked.

## License

See `LICENSE` -- a **placeholder**: the license is **TBD at publish time** per
the E-5 ruling. No rights are granted by this package yet.

## The honest boundary

`MANIFEST.md` lists every shipped file with its sha256 and the exclusions (raw
per-cell JSONs, trajectories, VACASK, the 45 nm model card, `lna/` internals,
the case study) with the reason each is out.
