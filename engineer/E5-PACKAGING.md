# E5-PACKAGING — packaging / release inventory (DRAFT for user ruling R-5)

**Status:** DRAFT. Commissioned by the user 2026-08-16, executing **E-5** of
`engineer/00-CHARTER.md` §6. This document is for ruling, not for release.
Nothing is published, prepared for upload, frozen, or committed except this file.
The user's ruling (R-5, charter §7) is what opens any of those paths.

**What this document is.** An inventory of what a release of "RF-grade agentic
analog-design environment + benchmark + dhruva case study" would actually contain,
the license audit of every upstream it depends on, the data manifest, the scrub
list, the protocol-freeze question, and the open decisions — one numbered question
per row — that belong to the user.

**What this document is not.** A plan, a release checklist, or a recommendation
that anything be released. Every sentence in §6 is a question, not a decision.

---

## Table of contents

1. [Inventory](#1-inventory)
   - 1.1 Environment, drivers, and harness
   - 1.2 Benchmark: registry + protocol
   - 1.3 Scoreboards (in-house N=10, external amp + LDO-deferred)
   - 1.4 Memory and loop harnesses with measured-negative results
   - 1.5 The dhruva case study
   - 1.6 Dependency chain: what a stranger needs
   - 1.7 What cannot ship
2. [License audit](#2-license-audit)
3. [Data manifest](#3-data-manifest)
4. [Scrub list](#4-scrub-list)
5. [Freeze interaction](#5-freeze-interaction)
6. [Open questions table](#6-open-questions-table)

---

## 1. Inventory

What a release called "RF-grade agentic analog-design environment + benchmark +
dhruva case study" would actually contain, file by file and artifact by artifact.
The charter defines the product as three artifacts (§1); the inventory maps those
to the files on disk.

### 1.1 Environment, drivers, and harness

These are the **original files** on the `engineer` branch. All are tracked in git.

| File | What it is | Status |
|---|---|---|
| `engineer/env.py` | `Task` / `Env.evaluate` / `Env.observe` / `TrajectoryLogger` / runtime-dep shim | 726 lines, E-1 hardened |
| `engineer/tasks.py` | Benchmark registry v0 — 8 pinned tasks (7 scoring, 1 smoke), `--list`, `--check` | 228 lines |
| `engineer/baseline_run.py` | CMA-ES driver through env.py; the primary in-house null arm | 217 lines |
| `engineer/random_run.py` | Uniform-random driver; the E-1 falsifier and secondary null arm | ~150 lines |
| `engineer/score_run.py` | Parallel runner for the in-house 7×2×10 full scoreboard | part of E-2 |
| `engineer/ext_gym.py` | AnalogGym adapter — `ExtEnv` exposing the same contract as `Env`, without editing `env.py` | E-2 externals |
| `engineer/score_ext.py` | Parallel runner for the external 14×2×10 scoreboard | E-2 externals |
| `engineer/test_env.py` | E-1 API-hardening tests (round-trip, foreign topology, non-sizable contract, loud dep-shim) | E-1 |
| `engineer/mem_playbook.py` | Read-only sidecar; hermetic empty-store injection for cold mode | E-3 |
| `engineer/mem_arm.py` | `pb-cmaes` arm — playbook-informed K-start CMA-ES; K=1 cold is bit-identical to cmaes null | E-3 |
| `engineer/memory_harness.py` | Paired warm/cold runner — `run_pair(task,seed)` | E-3 |
| `engineer/loop_run.py` | `Proposer` / `Verifier` / `Intervener` classes + the unattended loop pilot | E-4 |

These files depend on the **shared core** under `lna/` (charter §3.1), which lives
on `main`. The release would need to include or specify the shared core:

| Shared-core file | What it provides |
|---|---|
| `lna/datastore.py` | Append-only tables, margins, snapshots, diagnosis vocabulary |
| `lna/spec.py` | Spec loading/validation, `feasible` / `objective` / `report` |
| `lna/size.py` | `prepared_body`, `make_objective`, `eval_metrics`, `OpSink`, the box |
| `lna/extract.py` | The ngspice decks and every measurement in them |
| `lna/bias.py` | Bias insertion + `classify_params` |
| `lna/to_spice.py` | Netlist emission, the model card path, `W_FINGER` |
| `lna/topology.py` | The token graph |
| `lna/moves.py` | Topology mutation operators (needed by E-4 escalation) |
| `lna/null_sizer.py` | CMA-ES and random-search arms (imported verbatim by all drivers) |
| `lna/playbook.py` + `lna/playbook/` | Machine-queryable memory store (40 entries at time of E-3/E-4) |
| `lna/ref/` + `lna/ref/check_ref.py` | Golden reference decks and the harness-integrity check |
| `lna/specs/` | Spec YAML files for all tasks |
| `lna/sync_lines.py` | Cross-line data sync tool |

### 1.2 Benchmark: registry + protocol

The benchmark is a table plus a protocol (charter §6 E-2). Both are tracked.

| File | What it is | Freeze state |
|---|---|---|
| `engineer/tasks.py` | The registry: 8 pinned tasks, wl_hash anchors, budget derivation, `--check` | NOT frozen (R-5 reserves the freeze to the user) |
| `engineer/PROTOCOL.md` | Pre-registered scoring protocol v0 (adopted 2026-08-14, amended N=5→10); §EXT appendix (externals, committed alone before any external run) | WORKING, not frozen |
| `engineer/EXT-CALIBRATION.md` | AnalogGym runnable subset table with every exclusion carrying its reason | Informational |

**Pre-registration chain.** The protocol's value as a credibility artifact is its
commit ordering: `PROTOCOL.md` was committed alone before any scoring run;
`PROTOCOL.md §EXT` was committed alone before any external cell ran. Both orderings
are in the git history and are the timestamps that foreclose the E-2 falsifier.
A release preserves this only if it ships the git history, not just a snapshot of
files.

### 1.3 Scoreboards (measured results)

All produced under pre-registered protocols; artifact names carry pre-registration SHAs.

| File | What it is | Cells | Status |
|---|---|---|---|
| `engineer/data/scoreboard_v0.json` | In-house N=5 scoreboard; the §43.2 reproduction artifact | 70 (7×2×5) | Complete; retained permanently |
| `engineer/data/scoreboard_v0.1.json` | In-house N=10 scoreboard (amendment SHA `f9ea7f2`) | 140 (7×2×10) | Complete |
| `engineer/data/ext_golden_v0.json` | External track golden (HoiLee_AFFC default sizing, spread 0.000000) | 1 anchor | Complete |
| `engineer/data/scoreboard_ext_v0.json` | External AnalogGym scoreboard (14 amps × 2 arms × 10 seeds) | 280 | **Placeholder exists; scoring run partially complete at time of draft** — per-cell JSONs present but not yet aggregated |
| `engineer/data/mem_pairs_v0.json` | E-3 warm/cold paired scoreboard (prereg SHA `353f734`) | 70 pairs | Complete; measured negative, all 7 tasks warm < cold |
| `engineer/data/loop_v0.json` | E-4 unattended loop results (prereg SHA `e7937f5`) | 20 loops (10 seeds × warm+cold) | Complete; measured negative, 0/10 feasible |

The **measured-negative results (E-3 and E-4) are a selling point under the
charter's thesis** (charter §8): the field's failure mode is scaffolding without
measurement; this line shipped measurements that came out negative and published
them. The cold/warm harness (E-3) discriminated memory cleanly; the loop (E-4)
ran fully unattended. Those are the deliverables — the headline numbers are results,
not gaps. A release that omits the negative measurements would misrepresent the
program.

### 1.4 Memory and loop harnesses with measured-negative results

Narrative and pre-registration documents for E-3 and E-4:

| File | Content |
|---|---|
| `engineer/E3-MEMORY.md` | Pre-registration + post-hoc outcome for the cold/warm harness. §6 outcome: warm < cold 7/7 tasks, mechanism named (budget-splitting), hermeticity proven |
| `engineer/E4-LOOP.md` | Pre-registration + post-hoc outcome for the unattended loop pilot. §10 outcome: 0/10 feasible, falsified on SPICE cost, mechanism named (staged budget fractures CMA-ES convergence), all invariants held structurally |

The pre-registration sections (above the `POST-HOC` dividers) were committed before
any measurement; the outcome sections were appended after. Both orderings are in
the git history.

### 1.5 The dhruva case study

The dhruva/GNSS balun LNA is the case study the charter calls "the flagship
demonstration that the environment measures something real" (charter §1). Its
evidence is in `lna/`, the shared core, and lives on `main`.

**What the case study consists of (all on `main` / `lna-data`):**

| Source | Content |
|---|---|
| `lna/FINDINGS.md` §43–§46 | The execution wave and WP-LIN results; §43.1 (era re-label: 1,109/1,215 designs era-stale, 10 non-reproducing rows caught); §43.2 (CMA-ES beats ZOAF 4/5 vs 1/5 at matched budget — the benchmark's consistency check); §44 (WP-LIN rung 0, IIP3 measured first time, two-harness cross-check to 0.08 dB); §45 (rungs 1–4, wall named, +0.7 dB of needed ~27); §46 (D-2 test widening, candidate D fails 0/4, candidate N at 5/5 reported not recorded) |
| `lna/JOURNEY.md` | 44 stages of (decision, evidence, outcome) in the LNA program |
| `lna/plans2/15-ENGINEER-PROPOSAL.md` | The proposal that launched the engineer line (the argument from the survey) |
| `lna/plans2/16-WP-LIN.md` + `plans2/17-WP-LIN-D2.md` | Pre-registered WP-LIN work packages |
| `lna/playbook/` | 40 qualitative engineering entries (machine-queryable) |
| `lna/data/trajectories.jsonl` | (state, action, outcome, cost) rows from day one |
| `engineer/data/trajectories.jsonl` | Engineer-line (state, action, outcome, cost) rows (127 MB) |

**What FINDINGS §43–§46 would tell a case-study citation:**
- §43.1 is the era re-label result: the store had 1,109 era-stale designs, 10
  non-reproducing rows (worst |Δ| 38.78 dB), ~30 stored-feasible designs that are
  infeasible under the current harness. Provenance enforcement at scale.
- §43.2 is the benchmark's anchor: CMA-ES beat ZOAF (the field's recent RF sizer)
  at a matched 336-eval budget on wifi24 (4/5 vs 1/5 feasible). The engineer line's
  `scoreboard_v0.json` reproduces this bit-identically.
- §44–§46 carry the two-harness IIP3 measurement (transient + VACASK HB agreeing
  to 0.08 dB), the linearity redesign running out of in-box levers (+0.7 dB of the
  needed ~27), and the D-5 output-swing-wall diagnosis redirecting the program.

### 1.6 Dependency chain: what a stranger needs

A release needs to specify or bundle the following. Items marked **cannot ship**
are addressed in §1.7.

| Dependency | What it is | Must install / fetch? | Size |
|---|---|---|---|
| **ngspice 47** | Simulator; built from source (conda-forge ships 41 which segfaults on `sp` deck) | Must build from source (or provide binary) | ~30 MB installed |
| **VACASK 0.3.4.rc1** | Harmonic-balance simulator for cross-check (HB results in §44.9) | Build from source (OpenVAF + LLVM toolchain) | Build-heavy; binary not redistributed |
| **45nm BSIM4 model card** (`AutoCkt/repo/.../45nm_bulk.txt`) | The process model cards the LNA harness uses | Fetch from `AutoCkt/repo` (MIT via ksettaluri6/AutoCkt) | ~10 KB text; see §2 license audit |
| **ZOAF** (`misc/ZOAF`) | Used by `lna/null_sizer.py` import path resolution; also the source of the ZOAF reference rows pinned in `tasks.py` | Fetch at pinned SHA `62615e91` (MIT) | ~few MB |
| **AnalogGenie/repo** | Used by `lna/moves.py` `realize` path (topology re-tokenisation); partial dep (operators work without it; `realize` needs it + `pandas`) | Fetch at pinned SHA `efc25358` (MIT) | ~200 MB including `Pretrain.pth` (189 MB); `pth` not needed for env use |
| **AnalogGym/repo** | Needed only for the external calibration track (`ext_gym.py`); not needed for the in-house 7-task benchmark | Fetch at pinned SHA `0a9d1390` (BSD-3-Clause) | ~few MB; plus SKY130 PDK (~500 MB unzipped) |
| **SKY130 PDK** | Bundled with AnalogGym (`PDK/sky130_pdk.zip`); Apache-2.0 | Unzip in place | ~500 MB |
| **Python 3.11 + numpy + scipy + pyyaml** | Runtime for all engineer code | Standard install | — |
| **pandas** | Needed only for `AnalogGenie/repo`'s `realize` path | `pip install pandas` | — |

**What the dep-shim provides.** `env._bind_runtime_deps()` walks up the directory
tree (override `LNA_DEPS_ROOT` → this checkout → git common dir's parent →
ancestors) to resolve the model card and ZOAF paths at runtime, stamping what it
resolved into every result's `harness.deps` block. A fresh worktree with none of
the clones will fail loudly (charter R-1 "make it loud"). Whether the shim should
be replaced by a hard precondition is queued as R-1 (still open).

### 1.7 What cannot ship

| Item | Why it cannot ship | What a stranger does instead |
|---|---|---|
| **lna/data/sim_points.jsonl**, **op_points.jsonl** | Bulk, gitignored; not bounded in size | Regenerate by running the scorer; or not needed (only the pinned reference rows matter for the registry) |
| **engineer/data/trajectories.jsonl** (127 MB) | Gittracked but 127 MB; over typical repo size limits | Either a data release (Zenodo / HuggingFace) or regenerated by running the drivers |
| **Per-cell result JSONs** (316 files in `engineer/data/`, ~517 MB total) | Large; gittracked in this worktree but may not be practical in a public repo | Data release or regenerated |
| **AnalogGenie `Pretrain.pth`** (189 MB) | Git LFS on GitHub; not trivially redistributable; not needed for env use | Fetch from HuggingFace at the pinned SHA; only needed for `realize`'s re-tokenisation path |
| **VACASK binary** | AGPL-3.0; see §2; build-heavy | Build from source per PORTING.md; binary would need AGPL compliance |
| **Model binaries / checkpoints** | Charter §3.3: models never ship as binaries | The (data, seed, protocol) triple is what ships; a stranger re-trains |
| **`bsim4v5.out`** | ngspice runtime artefact; gitignored | Generated by ngspice on first run |
| **Machine-specific paths in `harness.deps`** | Each result JSON carries the path where deps were resolved on this box | These are provenance stamps; a re-run on a stranger's box stamps their own paths |
| **`AutoCkt/repo` (the full clone)** | Not vendored; only the model card text is used | Fetch at pinned SHA per UPSTREAM.md; or copy just `45nm_bulk.txt` (see §2 license) |

---

## 2. License audit

Licenses read from files on disk. No license is guessed; unknown means no LICENSE
file was found in the local clone.

| Upstream | Local path | Pinned SHA | License read from file | Redistribution implication |
|---|---|---|---|---|
| **AnalogGym** (CODA-Team) | `AnalogGym/repo/` | `0a9d1390` | **BSD-3-Clause** — `/AnalogGym/repo/LICENSE` | May redistribute; must retain copyright notice and disclaimer; cannot use CODA-Team name for endorsement without permission |
| **ZOAF** (LiyanTan111) | `misc/ZOAF/` | `62615e91` | **MIT** — `/misc/ZOAF/LICENSE` | May redistribute; must retain copyright and permission notice |
| **AnalogGenie** (xz-group) | `AnalogGenie/repo/` | `efc25358` | **MIT** — `/AnalogGenie/repo/LICENSE` | May redistribute; must retain copyright and permission notice. Note: `Pretrain.pth` (189 MB) ships via Git LFS — its own provenance is the checkpoint; the repo's MIT license applies to the code |
| **AutoCkt** (ksettaluri6) | `AutoCkt/repo/` | `a6c8a61d` | **UNKNOWN — no LICENSE file found** in the AutoCkt/repo clone | Cannot redistribute without clarification. The 45nm model card (`45nm_bulk.txt`) is the only file the engineer line actually uses; its header says "BPTM 45nm" (Berkeley Predictive Technology Model), which has its own provenance (see below) |
| **45nm BSIM4 model card** (`45nm_bulk.txt`) | `AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt` | (pinned via AutoCkt repo SHA) | **UNKNOWN — no copyright or license header in the file** (header: `* BPTM 45nm NMOS`). BPTM cards were historically released by the UC Berkeley BSIM Group for open use, but the specific file here carries no license statement | Provenance unclear. The engineer line reads it at runtime via the dep-shim; if a release were to ship a copy, this would need clarification with the BSIM Group or the AutoCkt authors |
| **SKY130 PDK** (in AnalogGym) | `AnalogGym/repo/PDK/sky130_pdk/` | (bundled in AnalogGym) | **Apache-2.0** — `libs.tech/xschem/LICENSE` (representative; the PDK is a joint effort of Google + SkyWater, Apache-2.0 throughout) | May redistribute; must retain license and NOTICE file |
| **VACASK** | `.env/vacask-0.3.4.rc1/` | `0.3.4.rc1` | **GNU AGPL-3.0** — `.env/vacask-0.3.4.rc1/share/doc/vacask/LICENSE` | Copyleft: if VACASK is conveyed (binary or source), the full AGPL-3.0 source disclosure requirement applies. **Critical constraint.** The engineer line calls VACASK only for the `check_hb` cross-check (§44.9); if the release omits the HB cross-check path, VACASK need not be bundled or disclosed. If the release includes VACASK or a build of it, AGPL source obligations apply |
| **ngspice 47** | `.env/ngspice-47/` | built from source | **BSD-like** (UC Berkeley + third-party contributions). The ngspice project is licensed under BSD with some GPL-licensed components (KLU solver). **No LICENSE file present in the installed tree** (only `bin/`, `lib/`, `share/` — source not retained locally). The ngspice project's standard is BSD for the core; the build included KLU via SuiteSparse (LGPL). Distribution of the binary requires retaining the relevant notices | A release that asks users to build ngspice from source (as PORTING.md describes) sidesteps binary redistribution. A pre-built binary would require license review of the build's component tree |

**Summary of redistribution constraints:**

- **Green (permissive, no copyleft):** AnalogGym (BSD-3-Clause), ZOAF (MIT), AnalogGenie (MIT), SKY130 PDK (Apache-2.0).
- **Requires clarification:** AutoCkt (no LICENSE file), 45nm model card (no license header). These are the only two dependencies whose redistribution status is actively unclear. The model card is the only AutoCkt file the engineer line uses.
- **Copyleft constraint:** VACASK (AGPL-3.0). Omitting the HB cross-check path from the release scope avoids this constraint entirely.
- **Binary redistribution complexity:** ngspice (BSD core + LGPL components). A fetch-and-build instruction sidesteps this; a pre-built binary requires license review.

---

## 3. Data manifest

What the charter's §3.2/§3.3 rules imply for a public data snapshot.

### 3.1 Stores that would ship

| Store / file | Location | Size | Era stamps? | Append-only? | Public snapshot implication |
|---|---|---|---|---|---|
| `lna/data/topo_labels.jsonl` | `main` | 14 MB | Yes (era field per row) | Yes | The source of the pinned reference rows in `tasks.py`. A release needs the pinned rows; the full 4,074-row store is the supporting dataset. Era stamps mean old rows are not silently compared to current-era results |
| `lna/data/l1_labels.jsonl` | `main` | 128 KB | Yes | Yes | L1 store (coarser labels) — secondary; may not be needed for the benchmark |
| `engineer/data/scoreboard_v0.json` | `engineer` | small (~100 KB) | Yes (pre-reg SHA) | N/A (a summary artifact, not a JSONL) | Ships as-is; the §43.2 reproduction artifact |
| `engineer/data/scoreboard_v0.1.json` | `engineer` | small | Yes | N/A | Ships as-is; the primary in-house N=10 result |
| `engineer/data/mem_pairs_v0.json` | `engineer` | small | Yes | N/A | Ships as-is; measured negative, should ship |
| `engineer/data/loop_v0.json` | `engineer` | small | Yes | N/A | Ships as-is; measured negative, should ship |
| `engineer/data/ext_golden_v0.json` | `engineer` | small | Yes | N/A | Ships as-is; harness anchor |
| `engineer/data/scoreboard_ext_v0.json` | `engineer` | small (pending) | Yes | N/A | Ships when scoring run completes |
| `engineer/data/trajectories.jsonl` | `engineer` | 127 MB | Yes | Yes | Large; consider data release (Zenodo/HuggingFace) separately from the code repo. Append-only guarantee: every snapshot SHA still verifies |
| Per-cell result JSONs (316 files) | `engineer/data/` | ~517 MB total | Yes (harness block) | N/A | Large; consider data release separately |

### 3.2 Stores that stay private

| Store | Why |
|---|---|
| `lna/data/sim_points.jsonl`, `op_points.jsonl` | Bulk, gitignored; regenerable by running the scorer; not bounded |
| `lna/playbook/` entries | The 40 qualitative engineering entries are the program's own engineering knowledge base; their public release is a separate decision (not needed for the benchmark to run) |

### 3.3 What §3.2/§3.3 rules imply

**§3.2 (prefix-preserving union, append-only law):** A public snapshot of any
JSONL store must be taken as a byte-identical prefix of the live store at a
specific commit, with its sha256 verified. A snapshot that re-orders, edits, or
filters rows breaks the prefix guarantee and invalidates downstream snapshots.
If the JSONL stores are released as a data package, the release must document the
snapshot commit SHA and the sha256 of each file.

**§3.3 (models never ship as binaries):** No `.pth`, no pickled surrogate, no
checkpoint. If any model trained on this data is associated with the release
(e.g. a surrogate trained for a future E-item), it ships as the triple (data
snapshot SHA, seed, protocol description) and is re-trained by the recipient.
AnalogGenie's `Pretrain.pth` is a third-party artifact licensed under MIT; it
is not a model this program trained and §3.3 does not prohibit linking to it.
Surrogates trained by this program using `lna/data/` as training data are
governed by §3.3.

---

## 4. Scrub list

Grep results for machine-specific absolute paths, user names, and identifiers that
would appear in committed files in a public release. All counts and locations are
as of the time of this draft.

### 4.1 Source files (`.py`, `.md`)

| Finding | File | Line | What it is |
|---|---|---|---|
| `/home/dpatni/.claude/jobs/6f62f9fd/tmp/ext_scratch` | `engineer/ext_gym.py` | 865 | Hardcoded fallback scratch directory path from a Claude session; should be replaced with a `tempfile.mkdtemp()` call or a configurable env-var default |

**Total source-file scrub items: 1** (one absolute path in `ext_gym.py` line 865).

### 4.2 Data files (JSON result artifacts)

The `harness.deps` block in every per-cell result JSON carries the absolute paths
resolved on this machine (`/home/dpatni/circuit-repro/...`). These are
**provenance stamps by design** — they record where the harness found its
dependencies on the machine that produced the numbers. They are not bugs.

However, a release that ships these JSONs as data artifacts will expose the
machine username `dpatni` and the absolute path prefix
`/home/dpatni/circuit-repro/` in every single result file.

| Scope | Count | What it is |
|---|---|---|
| JSON files in `engineer/data/` containing `/home/dpatni` | **312** | Per-cell result JSONs; the `harness.deps.models`, `harness.deps.zoaf`, `harness.deps.analoggenie`, `harness.deps.ngspice` fields |
| Source files (`.py`, `.md`) containing `/home/dpatni` | **1** (`ext_gym.py:865`) | See §4.1 above |
| **Total files with machine-specific content** | **313** | |

**Decision this creates (Q-5 in §6):** The provenance stamp is the correct design;
the question is whether the raw per-cell JSONs ship in the release at all, and if
so whether a scrubber replaces the `/home/dpatni/` prefix with a relative or
placeholder path. The alternative is to ship only the aggregated scoreboards (which
contain the same numbers in summary form, without the per-path stamps) and release
the per-cell data separately with a scrubbing note.

### 4.3 Other identifiers

| Pattern searched | Result |
|---|---|
| `devavrat` (any case) in `.py`/`.md` | 0 occurrences in `engineer/` source files |
| Email addresses (`@`) mentioning user identity | 0 in `engineer/*.py` or `engineer/*.md` |
| `C:\Users\Devavrat` Windows paths in committed files | 0 in `engineer/` (present in `lna/FINDINGS.md` in historical documentation, but `lna/` is read-only from this line) |

---

## 5. Freeze interaction

### 5.1 What PROTOCOL v0 currently is

`engineer/PROTOCOL.md` was committed alone before any scoring run; it is the
pre-registration timestamp. It was adopted as the **working protocol** by user
ruling on 2026-08-14 (§43.1 amendment: N=5→10). It is **not frozen**.

"Not frozen" means: the task set, budgets, N, metrics, feasibility definition,
aggregation rule, and the arms can be changed by user ruling before a freeze is
declared, per PROTOCOL §9. Numbers produced under the working protocol are
real measurements; they are not provisional. But the protocol is not yet locked in
the way that would make it a citable immutable benchmark artifact.

### 5.2 What freezing would mean

Freezing PROTOCOL v0 as the benchmark scoring rule (ruling R-5, the user's call)
would:

1. **Lock the protocol permanently at the frozen commit.** The frozen SHA becomes
   the cited version. Any change to the task set, budgets, N, metrics, feasibility,
   or aggregation rule after the freeze would constitute a NEW protocol version (a
   user ruling), and the existing numbers would continue to be cited under the
   frozen version.

2. **Make all current numbers citable.** The in-house scoreboard
   (`scoreboard_v0.1.json`, 7 tasks × 2 arms × 10 seeds, 66,920 evals) and the
   external scoreboard (14 amps × 2 arms × 10 seeds, 280,000 evals at budget 1000)
   become the benchmark's frozen baseline table.

3. **Foreclose future protocol edits without a versioned amendment.** Any future
   agent arm (E-3/E-4 variants, or new arms) must compete against the frozen
   protocol's null baseline at the frozen budget and N. This is the intended
   design (the nulls are the fixed reference the benchmark is built to measure
   improvement over), but it means the null numbers become load-bearing in a way
   they are not today.

4. **Interact with the external track.** The external track (AnalogGym amps, §EXT)
   is pre-registered but its scoreboard is not yet complete. Freezing the protocol
   before the external scoreboard is populated would freeze an incomplete set.
   The alternative is to freeze only the in-house track and treat the external track
   as a separate versioned addition.

### 5.3 The versioned-protocol alternative

Instead of a hard freeze, the protocol could be given an explicit version tag
(`protocol-v0`, `protocol-v1`, etc.) and the benchmark could allow new versions
by user ruling. This is how AnalogGym itself evolved. The cost is that results from
different versions are not directly comparable without a cross-version anchor.

The current pre-registration commits already function as version tags (the
protocol's commit SHA is stamped in every result artifact). The question is whether
to formalize this into a naming convention that a citation can point to.

---

## 6. Open questions table

Every decision that is the user's, one row each. The recommendation column names
the agent's position and the cost/implication of taking it.

| # | Question | Recommendation | Cost / implication if taken |
|---|---|---|---|
| **Q-1** | **Release scope: which of the three charter artifacts (environment, benchmark, case study) ship together, and when?** The benchmark requires the external scoreboard to be complete; the environment can ship without results; the case study requires `lna/` (main-branch content). All three together is a larger lift than any one alone. | Ship the environment and in-house benchmark together as a first release; the case study and external track as a follow-on. This matches the "pilot, not a benchmark" framing (PROTOCOL §10) — ship what is complete. | The external track (AnalogGym amps) becomes a separate release milestone. The case study requires the user to decide how much of `lna/FINDINGS.md` / `JOURNEY.md` is part of the release or merely cited. |
| **Q-2** | **License of the release itself: what license governs the engineer code?** The engineer files (`env.py`, `tasks.py`, drivers, harnesses) have no LICENSE file and no SPDX header. This needs a decision before a public repo is created. | MIT or BSD-3-Clause (consistent with the permissive upstreams); Apache-2.0 is also reasonable. Any permissive license is compatible with the BSD-3-Clause and MIT upstreams. AGPL (matching VACASK) is not recommended because it would impose copyleft on users of the benchmark. | No cost for permissive; picking a license requires a one-line decision from the user. |
| **Q-3** | **AutoCkt / 45nm model card: clarify or replace?** The model card (`45nm_bulk.txt`) has no license header; AutoCkt has no LICENSE file. The engineer line reads the card at runtime (via the dep-shim). Options: (a) contact ksettaluri6/AutoCkt authors for explicit permission; (b) replace with the canonical BPTM distribution from ptm.asu.edu (which carries an explicit open-use statement); (c) document the dep as "fetch separately" and do not ship the file. | Option (b) or (c): either use the canonical BPTM source (same parameters, explicit provenance) or document it as a fetch-separately dependency. | Option (b) costs one engineer day (verify the canonical card produces identical ngspice outputs, update `to_spice.py`'s path pointer). Option (c) is zero cost but increases the stranger's setup friction. |
| **Q-4** | **VACASK: in or out of the release scope?** VACASK is AGPL-3.0. The engineer line uses it only for the HB cross-check (`check_hb`) in §44.9. If VACASK is in scope, AGPL source-disclosure obligations apply. If it is out of scope, the release documents "HB cross-check requires VACASK, build per PORTING.md" and the cross-check results are cited but not reproducible without the user building VACASK themselves. | Out of scope for the release. Document the cross-check result (§44.9 numbers) in the case study, cite the build procedure, and note that `check_hb` is an optional cross-check not required to run the benchmark. | The HB cross-check becomes "trust the paper" rather than "run it yourself." This is the standard position for proprietary-simulator results in the field; the cross-check adds credibility but is not the primary harness. |
| **Q-5** | **Per-cell JSON data: ship with paths, ship scrubbed, or ship aggregates only?** 312 per-cell result JSONs contain the absolute path `/home/dpatni/circuit-repro/...` in their `harness.deps` blocks. The aggregated scoreboards contain the same numbers without the per-path stamps. Options: (a) ship JSONs as-is (exposes username); (b) ship JSONs with a post-processing scrub replacing `/home/dpatni/circuit-repro/` with a placeholder; (c) ship aggregated scoreboards only and release raw JSONs separately (Zenodo/HuggingFace). | Option (c): ship the scoreboards in the code repo; release per-cell JSONs and `trajectories.jsonl` as a separate data package. This is the cleanest separation of code/benchmark from data, and it avoids the scrubbing decision on 312 files. | Zenodo or HuggingFace data deposit is a one-time action; the DOI becomes the citation anchor for the data. Requires a small amount of additional documentation. |
| **Q-6** | **Protocol freeze: freeze v0 now, freeze with external track, or versioned-open?** See §5. Three choices: (a) freeze in-house track now, external track joins later; (b) wait for external track, freeze both together; (c) version-tag rather than hard-freeze. | Option (a): freeze the in-house track (7 tasks, 2 arms, N=10) as `protocol-v0` at a named commit. The external track is pre-registered and its scoreboard is nearly complete; freeze it as `protocol-v0-ext` when the external cells land. Versioned tags are cheap and they let the field cite a stable anchor immediately. | The in-house benchmark is citable before the external track lands. Any future amendment (new arm, budget change, N change) becomes protocol-v1 by user ruling. |
| **Q-7** | **Playbook / case-study depth: what of the engineering knowledge base ships?** The `lna/playbook/` entries (40 qualitative engineering records) are the memory the E-3 arm consumes. They are original content, but they name specific design decisions about the dhruva topology. Options: (a) ship in full; (b) ship a redacted or anonymised form; (c) describe the schema and omit the entries (a stranger can populate their own). | Option (a) if the case study ships; the entries are the evidential basis for the E-3 measured-negative result and omitting them would make the cold/warm story opaque. | If the user prefers not to publish the raw engineering entries, option (c) costs nothing; the benchmark runs identically (the cold control is a hermetic empty store). |
| **Q-8** | **AnalogGym LDO track: in or out of the first release?** `EXT-CALIBRATION.md` notes LDOs as "deferred — a follow-up rung, amps first." The amps track (14 amps) is nearly complete. LDOs would require a separate adapter rung. | Out of scope for the first release; in scope for a follow-on. The amps track is what was pre-registered. | No cost; the "deferred" label in `EXT-CALIBRATION.md` already documents this. |

---

*This document is a draft for user ruling R-5. All eight questions above are
queued; none is decided. The agent's recommendations are advisory; any or all may
be overridden. The document will be updated to reflect the ruling.*
