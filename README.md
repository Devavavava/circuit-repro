# circuit-repro

> **Want to design an LNA? → [HOWTO.md](HOWTO.md)** — write a spec, run one command, view
> the result. Three steps, no need to read the rest of the repo.

Setup and smoke-test harness for 11 analog-circuit ML papers, plus 4 follow-up repos.

**[STATUS.md](STATUS.md) is the main document** — per-work results, environment versions,
every bug hit and how it was worked around, and Windows-vs-WSL-GPU timings.

**`lna/`** goes deeper on one target: generating low-noise-amplifier topologies.

* **[lna/FINDINGS.md](lna/FINDINGS.md)** — capability assessment, measured gaps,
  profiling, and a phased plan. Prefix conditioning takes the LNA hit rate from
  0% to 40.6% with no retraining.
* **[lna/WORKLOG.md](lna/WORKLOG.md)** — what was tried, what failed, and the
  ngspice traps worth not rediscovering.
* **[lna/HANDOVER-FABLE.md](lna/HANDOVER-FABLE.md)** — open brief: improving
  generation, and defining what LNA is actually being designed.

Scope is deliberately narrow: get each published implementation to *run* and prove it with a
smoke test. No paper results are reproduced and no long training run was launched.

## What is in this repository

Only original work — smoke tests, diagnostics, setup scripts, run logs, and the write-up.
The 12 upstream repositories are **not** vendored here; they are pinned by commit SHA in
[UPSTREAM.md](UPSTREAM.md) and re-created on demand.

```
STATUS.md                  the write-up: results, environments, bugs, timings
UPSTREAM.md                12 upstream repos, pinned SHAs, patch notes
patches/                   the 2 real source fixes needed upstream
scripts/fetch_upstream.sh  re-clone all 12 at their pinned commits + apply patches
<Work>/smoke_*.py          per-work smoke tests
```

Some smoke tests had to sit *inside* an upstream checkout to import it — for example
`AnalogGenie/repo/Inference_smoke.py`. They lived under `smoke/` mirroring their destination
path (preserved at git tag `phase1-survey`); `fetch_upstream.sh` copied each one into place
after cloning. `LaMAGIC2/` diagnostics, `_wsl/` setup scripts, and `_logs/` run logs are
likewise preserved at that tag but removed from the working tree.

## Reproducing

```bash
bash scripts/fetch_upstream.sh
```

This clones all 12 repos at their pinned commits and applies `patches/`. Then build the conda
environments listed in the *Environments* section of STATUS.md — one per repo, because their
dependency sets genuinely conflict — and run the smoke command from the summary table.

**Paths are absolute and machine-specific.** The smoke scripts were written against
`C:\Users\Devavrat\circuit-repro\...` (preserved at git tag `phase1-survey`).
The project now runs on a RHEL 8 workstation via `source env.sh`; see `PORTING.md`.

## Files not tracked

Four things are excluded for size. None are original work; each is re-obtainable.

| Path | Size | Where it comes from |
|---|---|---|
| `AnalogGenie/repo/Pretrain.pth` | 189 MB | ships inside the AnalogGenie clone — `fetch_upstream.sh` retrieves it |

Phase-1 large assets (`LaMAGIC2/ckpt/`, `LaMAGIC2/data/`, `_wsl/ubuntu-22.04.5-wsl-amd64.wsl`)
are documented in STATUS.md and preserved at git tag `phase1-survey`.

## Results at a glance

8 of 8 works with public code run and pass a smoke test. GCN-RL, L2DC, and DNN-Opt have no
public code. Of the extensions, ZeroSim passes, CircuitSense passes on Linux but fails on
Windows, AnalogSAGE is blocked on unpublished data, and RoSE needs Cadence. Full detail,
including the exact failure modes, is in STATUS.md.
