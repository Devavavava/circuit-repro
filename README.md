# circuit-repro

Setup and smoke-test harness for 11 analog-circuit ML papers, plus 4 follow-up repos.

**[STATUS.md](STATUS.md) is the main document** — per-work results, environment versions,
every bug hit and how it was worked around, and Windows-vs-WSL-GPU timings.

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
smoke/                     smoke tests that must live inside an upstream checkout
_wsl/                      Ubuntu 22.04 setup + run scripts (WSL side)
_logs/                     stdout from every smoke run
<Work>/smoke_*.py          per-work smoke tests
LaMAGIC2/diag*_lamagic2.py the four LaMAGIC2 diagnostic passes
```

Some smoke tests have to sit *inside* an upstream checkout to import it — for example
`AnalogGenie/repo/Inference_smoke.py`. Git will not track a file inside a directory that is
itself a git repository, so those live under `smoke/` mirroring their destination path, and
`fetch_upstream.sh` copies each one into place after cloning.

## Reproducing

```bash
bash scripts/fetch_upstream.sh
```

This clones all 12 repos at their pinned commits and applies `patches/`. Then build the conda
environments listed in the *Environments* section of STATUS.md — one per repo, because their
dependency sets genuinely conflict — and run the smoke command from the summary table.

**Paths are absolute and machine-specific.** The smoke scripts were written against
`C:\Users\Devavrat\circuit-repro\...` and the `_wsl/` scripts against
`/root/circuit-repro`. Adjust the constants at the top of each script for your own layout.

## Files not tracked

Four things are excluded for size. None are original work; each is re-obtainable.

| Path | Size | Where it comes from |
|---|---|---|
| `LaMAGIC2/ckpt/` | 944 MB | [turtleben/LaMAGIC2-345comp-SFCI-dataaug](https://huggingface.co/turtleben/LaMAGIC2-345comp-SFCI-dataaug) on Hugging Face |
| `LaMAGIC2/data/SFCI_345comp.json` | 29 MB | [turtleben/LaMAGIC-dataset](https://huggingface.co/datasets/turtleben/LaMAGIC-dataset), `transformed/` split |
| `AnalogGenie/repo/Pretrain.pth` | 189 MB | ships inside the AnalogGenie clone — `fetch_upstream.sh` retrieves it |
| `_wsl/ubuntu-22.04.5-wsl-amd64.wsl` | 344 MB | Canonical's rootfs, SHA256 `4499c4fe257f2fc83145b429ce211a0a43fd590e70d6261ede616210947d9f8f` (see the install note in STATUS.md) |

## Results at a glance

8 of 8 works with public code run and pass a smoke test. GCN-RL, L2DC, and DNN-Opt have no
public code. Of the extensions, ZeroSim passes, CircuitSense passes on Linux but fails on
Windows, AnalogSAGE is blocked on unpublished data, and RoSE needs Cadence. Full detail,
including the exact failure modes, is in STATUS.md.
