# Porting circuit-repro to the RHEL 8 EDA box (dpatni)

The repo was built to run half on Windows 11 (native conda) and half in WSL
Ubuntu 22.04, sharing files over `/mnt/c`. This host is a single **RHEL 8.10**
workstation (128 cores, 125 GB RAM, NVIDIA RTX A1000, non-root, NFS home).

**Scope of this port:** the live work only — `lna/` (on `main`) and `engineer/`
(on the `engineer` branch). The reference clones, `smoke/`, and `_wsl/` scripts
were not ported.

## Everything is self-contained under `.env/`

No system state was changed. No `sudo`, no `apt`/`yum`, nothing in `/usr` or
`/opt`. The whole footprint is removable with `rm -rf ~/circuit-repro/.env`:

```
.env/                     Miniconda prefix (installer run with -b -p here)
.env/envs/cr/             python 3.11 + numpy + scipy + pyyaml + ngspice 36 (conda-forge)
.env/ngspice-47/          ngspice 47 built from source (the one the lna decks need)
env.sh                    activation: git-on-PATH + conda activate + $NGSPICE etc.
```

Both `.env/` and `env.sh` are gitignored.

## What had to change, and why

| Blocker on this host | Fix (all contained) |
|---|---|
| **No `git` on PATH.** `engineer/env.py` shells out to `git`. | `env.sh` prepends the git bundled with the Xilinx toolchain (`/tools/xilinx/2025.1/tps/lnx64/git-2.46.0/bin`). Nothing installed. Note: that git build has **no HTTPS helper** — clone upstreams over **SSH** URLs (`git@github.com:...`), not `https://`. |
| **No conda.** `_wsl/*` hardcode `/opt/miniconda` (not writable, non-root). | Miniconda installed into `.env/` under `$HOME`. |
| **No ngspice, and the version matters.** The lna decks use the `sp` S-parameter analysis with `portnum`/`z0` ports (ngspice ≥ 42). conda-forge's newest is **41**, which **segfaults** on that deck; 36 rejects `portnum` outright. | Built **ngspice 47** from source into `.env/ngspice-47`. `env.sh` sets `NGSPICE` to it. (The lna/engineer code reads `$NGSPICE`; the `C:\msys64\...` path in `extract.py`/`bias.py`/… is only the default — no code edit needed.) |
| **System python is 3.6.8**, too old. | conda env `cr` provides 3.11. Its `PYTHONPATH` was being polluted by Xilinx Vitis py-libs; `env.sh` does `unset PYTHONPATH`. |
| **Windows-side files via `/mnt/c`** don't exist here. | Only the two runtime clones the engineer line needs were fetched into the main checkout: `misc/ZOAF` and `AutoCkt/repo` (for its 45 nm model card), both at their `UPSTREAM.md` SHAs. `AnalogGenie/repo` also fetched (see below). |
| **Worktree resolution.** `engineer/` lives on the `engineer` branch. | Checked out as a `git worktree` at `~/circuit-repro-engineer` (keeps `main` intact). `env.py`'s dep-shim finds the clones in the main checkout; `env.sh` also exports `LNA_DEPS_ROOT`. |

## How to run

```bash
source ~/circuit-repro/env.sh          # git + python + ngspice, all contained
cd ~/circuit-repro-engineer            # the engineer-branch worktree
python engineer/baseline_run.py        # the seam smoke: 150 evals, 300 ngspice calls
```

Verified green: 0 sim failures, real S-parameters/NF, CMA-ES converges to a
near-feasible design and finishes infeasible at the reduced 150-eval budget —
exactly what `engineer/README.md` says the smoke should do.

## Reference goldens are green on this host

The three static reference decks (`lna/ref/ref24_{cg,csdeg,tapped}.cir`) baked an
absolute `.include C:/Users/Devavrat/.../45nm_bulk.txt` — the author's Windows
path. On any other host it is dead and ngspice exits with no models, so
`check_ref.py` extracted nothing. Fix: `extract.resolve_models()` /
`extract.rewrite_includes()` rewrite that include at runtime the way
`engineer/env.py`'s dep-shim resolves the card — `$LNA_DEPS_ROOT` override →
this checkout's `AutoCkt/repo/...` path → the baked Windows literal as a last
resort (so Windows keeps working, decks untouched). `body_of()` applies it, which
covers the harness-based checks; `check_ref.py` runs a temp copy of each deck.
`check_hb.py` also became portable: it now respects `$VACASK_HOME`, picks
`vacask` vs `vacask.exe` by platform, and emits the windows-gnu openvaf target
only on Windows.

Golden status verified 2026-08-14 (`source env.sh` + this checkout):

| check | result | note |
|---|---|---|
| `check_ref`  | GREEN | all metrics match `ref_baseline.json` to the digit |
| `check_op`   | GREEN | ref24_tapped OP parity |
| `check_nf`   | GREEN | analytic + real-LNA series-Rs NF |
| `check_iip3` | GREEN | G1–G4 |
| `check_bjt`  | GREEN | Gummel-Poon cards + emission parity |
| `check_diff` | GREEN | ngspice-backed 3-port balun (no VACASK needed) |
| `check_stab` | GREEN (harness) | §1–§3 PASS; §4 now runs (AnalogGenie/repo fetched 2026-08-14). Harness GREEN; dhruva-l2 sizing params produce a CONDITIONAL verdict — a real finding, not an error. |
| `check_hb`   | FAIL | VACASK build present under `.env/vacask-0.3.4.rc1` but its `vacask` binary is missing `libklu.so.2` (SuiteSparse) — a build-wiring issue in the parallel VACASK port, not a path issue |

## AnalogGenie/repo — fetched 2026-08-14

`AnalogGenie/repo` fetched via `curl` codeload tarball (no HTTPS git needed):

- **SHA:** `efc25358939c6bedd247f28d3df61066964f3a90` (pinned in `UPSTREAM.md`)
- **Local path:** `AnalogGenie/repo/` (gitignored upstream clone, main checkout only)
- **Pretrain.pth:** NOT in the codeload tarball (stored via Git LFS on GitHub, not
  trivially curl-able without LFS). Not required for `emit_sequence`/`realize()` or
  `check_stab` §4; deferred with the rest of the torch/GPU env setup.
- **pandas:** `3.0.5` installed via `pip` into the `cr` conda env. numpy `2.4.6`
  and scipy `1.17.1` were IDENTICAL before and after the install (pip did not
  upgrade them). `check_ref.py` GREEN after install.
- The engineer-branch worktree gets a symlink `AnalogGenie/repo ->
  <main>/AnalogGenie/repo` (same pattern as `AutoCkt/repo`).

## Not done (bigger lifts, not needed for the smoke)

- torch + CUDA env for the lna **generation** side (`generate.py`, `critic_gnn.py`,
  AnalogGenie checkpoint + Pretrain.pth). The RTX A1000 + PyPI CUDA wheels make
  this easy when wanted.
- The broader 11-paper harness and its per-repo envs.
