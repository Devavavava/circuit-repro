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
| **Windows-side files via `/mnt/c`** don't exist here. | Only the two runtime clones the engineer line needs were fetched into the main checkout: `misc/ZOAF` and `AutoCkt/repo` (for its 45 nm model card), both at their `UPSTREAM.md` SHAs. |
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

## Not done (bigger lifts, not needed for the smoke)

- torch + CUDA env for the lna **generation** side (`generate.py`, `critic_gnn.py`,
  AnalogGenie checkpoint). The RTX A1000 + PyPI CUDA wheels make this easy when wanted.
- The broader 11-paper harness and its per-repo envs.
