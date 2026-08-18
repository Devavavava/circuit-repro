# Phase 1 — The repo survey

**Sources:** `README.md`, `STATUS.md` (the detailed write-up), `UPSTREAM.md`,
`PORTING.md`.

## What this phase did

Fifteen research repos on ML-for-analog-circuit-design were cloned, given working
Python environments, and **smoke-tested** — run just far enough to prove the code
executes and produces sensible output. No paper results were reproduced and no long
training run was launched. The point was to find out what's real and usable.

Work was done first on Windows 11 (RTX 3050, 4 GB), then extended to WSL (Ubuntu
22.04) to unlock the GPU and a couple of Linux-only stacks.

## The headline result

**8 of 8 repos with public code run and pass a smoke test.** Three requested works
(GCN-RL, L2DC, DNN-Opt) have **no public code** and could not be evaluated.

Of the extension repos: ZeroSim passes; CircuitSense passes on Linux but fails on
Windows (a real platform bug, see below); AnalogSAGE is blocked because it ships no
data; RoSE needs Cadence and ships only a stub.

## The eight that run

| Repo | What it does | Smoke result |
|---|---|---|
| **AnalogGenie** | Generates circuit topologies (the LNA project's generator) | 1 topology, 42 devices, validation clean. GPU 77 s vs 400 s CPU |
| **LaMAGIC2** | Generates power-converter topologies | Checkpoint loads clean; GPU and CPU give byte-identical output |
| **CktGNN** | Op-amp topology generation via a graph VAE | 88% valid DAGs, 84% valid circuits |
| **AutoCkt** | RL-based device sizing (was the last blocked item) | Full PPO/RLlib loop runs under WSL with the exact documented Python-3.6 stack |
| **ZOAF** | Zeroth-order (black-box) sizing over ngspice | 73 real simulator calls in 17.6 s |
| **Krylov / Circuit-Synthesis** | Supervised sizing surrogate | 15 sims → trained surrogate, 100 epochs |
| **AnalogGenie-Lite** | Compresses AnalogGenie graphs (no model of its own) | Compression verified device-by-device |
| **AnalogToBi** | Bipartite circuit preprocessing (no checkpoint released) | 2347 circuits processed, 0 errors |

The full table — with the exact smoke command, environment versions, and per-repo
notes — is the top of `STATUS.md`.

## The parts that matter for later

A few survey findings drive the whole LNA project:

- **AnalogGenie is the only real topology *generator* in the set** with inductors in
  its vocabulary and real LNA circuits in its data. That's why it became the LNA
  generator.
- **ngspice (the simulator) can already do everything an LNA needs** — operating
  point, AC, noise, and S-parameters were all confirmed working. Measurement was
  never the bottleneck.
- **ZeroSim looked like the perfect fast scorer but isn't** — its device vocabulary
  has no inductor and no RF port. It's an op-amp model; using it to score LNAs would
  produce confident nonsense. This is a recurring theme: tools that look reusable
  often aren't, and the survey's value was catching that early.

## Environment reality (the useful gotchas)

The docs record a lot of hard-won setup knowledge. The ones worth knowing:

- **One conda environment per repo** — their dependency sets genuinely conflict.
  Nine Windows envs + three WSL envs.
- **The GPU only became usable under WSL.** Windows CUDA PyTorch wheels download at
  ~187 KB/s (≈3.5 h per env); the Linux PyPI wheel is CUDA-enabled and installs in
  ~5 minutes.
- **ngspice on Windows has two traps:** the msys2 GUI build writes *nothing* to
  stdout (use the `_con` console build, or `-o logfile`), and its XSPICE code models
  fail to load until a broken post-install path in `spinit` is fixed by hand.
- **CircuitSense on Windows is a genuine platform bug, not misconfiguration.** Its
  equation stage uses `multiprocessing`; Windows "spawn" must pickle lcapy objects
  that aren't picklable, so 0/5 circuits succeed. Linux "fork" doesn't, so it's 5/5.
  The Windows run even prints "completed successfully" while failing — always read
  the summary block.

## How the upstream code is handled

The 15 upstream repos are **not** vendored into this repository. Instead:

- `UPSTREAM.md` pins each repo by exact commit SHA, with patch notes.
- `scripts/fetch_upstream.sh` re-clones all of them at those commits and applies the
  patches in `patches/` (only **two** real source fixes were needed upstream).
- Smoke tests that must live *inside* an upstream checkout are kept under `smoke/`
  and copied into place after cloning (git can't track a file inside a nested repo).
- Four large artifacts (model checkpoints, a dataset, the WSL rootfs) are excluded
  for size and re-obtained on demand — sources are listed in `README.md`.

`PORTING.md` covers moving the whole setup to a new machine (paths in the smoke
scripts are absolute and machine-specific).
