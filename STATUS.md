# Analog Circuit ML — Clone / Setup / Smoke-Test Status

**Updated:** 2026-08-03 (WSL pass + extension repos). Original Windows pass: 2026-08-02.
**Host:** Windows 11, 16 cores, 16 GB RAM, NVIDIA RTX 3050 Laptop (4 GB), driver 592
**Layout:** `C:\Users\Devavrat\circuit-repro\` — one subfolder per work, `extensions/` for the
follow-up repos, `_wsl/` for the Linux setup scripts, `_logs/` for every run log.
Linux side lives at `\\wsl$\Ubuntu-22.04\root\circuit-repro`.
**Scope:** setup + smoke test only. No paper results reproduced; no long training run launched.

---

## Summary table — the 11 originally requested works

| Work | Official code | Cloned | Env built (Python) | Smoke test command | Result | Notes |
|---|---|---|---|---|---|---|
| **AnalogGenie** (ICLR'25) | [xz-group/AnalogGenie](https://github.com/xz-group/AnalogGenie) | yes | Win `analoggenie` **3.8.20** + WSL `gpu` **3.10.20** | `python Inference_smoke.py` | **PASS** | 1 topology, 1025 tokens, 42 devices / 32 nets, validation clean. **GPU: 77 s vs 400 s CPU.** Repo bug: `torch.load` lacks `map_location`. |
| **LaMAGIC2** (ICML'25) | [turtleben/LaMAGIC](https://github.com/turtleben/LaMAGIC) | yes | Win `lamagic` **3.9.23** + WSL `gpu` **3.10.20** | `python smoke_lamagic2.py` | **PASS** | Checkpoint loads with 0 missing keys; valid SFCI topology. **GPU and CPU produce byte-identical output and identical loss 0.0610.** |
| **CktGNN** (ICLR'23) | [zehao-dong/CktGNN](https://github.com/zehao-dong/CktGNN) | yes | Win `cktgnn` **3.9.23** | `python main.py --model CktGNN --hs 301 --epochs 1 --ng 200 --batch-size 16 --no-cuda --save-appendix _smoke --sample-number 2` | **PASS** | Valid DAG decodings **88.35 %**, valid circuits **84.09 %**, novel **87.50 %**. Fixed a Windows path bug; stray `pdb.set_trace()` forces exit 1 after success. |
| **AutoCkt** (DATE'20) | [ksettaluri6/AutoCkt](https://github.com/ksettaluri6/AutoCkt) | yes | **WSL `autockt` 3.6.15** (+ Win `autockt` 3.7.12 for the engine) | `python autockt/val_autobag_ray_smoke.py` | **PASS** *(was BLOCKED)* | **Full PPO/RLlib loop now runs under WSL** with the exact documented stack. 2 iters, 600 timesteps, reward −32.5. Windows remains blocked. |
| **ZOAF** (2026) | [LiyanTan111/ZOAF](https://github.com/LiyanTan111/ZOAF) | yes | Win `zoaf` **3.10.20** | `python examples/quickstart_10param.py` | **PASS** | 73 real ngspice calls in 17.6 s; ZO-SGD + ZO-CGD both ran. Needs `NGSPICE_LIBRARY_PATH` + `SPICE_LIB_DIR`. |
| **Krylov et al.** (ICML'23) | [indylab/Circuit-Synthesis](https://github.com/indylab/Circuit-Synthesis) | yes | Win `circuitsynth` **3.8.20** | `python main.py --path=./config/smoke_config.yaml` | **PASS** | 15 ngspice sims → `Params (15,2)`, `Performance (15,3)`; 100 supervised epochs. Bundles its own Windows ngspice. |
| **AnalogGenie-Lite** (ICML'25) | [xz-group/AnalogGenie-Lite](https://github.com/xz-group/AnalogGenie-Lite) | yes | reused `analoggenie` | `python graph/SPICE2GRAPH_compress_smoke.py` | **PASS** | Compression verified: device node eliminated, pins linked in an intra-device cycle. No model of its own. |
| **AnalogToBi** (2026) | [Seungmin0825/AnalogToBi](https://github.com/Seungmin0825/AnalogToBi) | yes | reused `analoggenie` | `python PREPROCESSING_Bipartite.py` | **PASS** | 2347 circuits → bipartite matrices, 1003 skipped by its own ERC, 0 errors. No checkpoint released. |
| **GCN-RL** (DAC'20) | **none** | — | — | — | **NO OFFICIAL CODE** | Not in mit-han-lab GitHub. |
| **L2DC** (2018) | **none** | — | — | — | **NO OFFICIAL CODE** | MIT HAN Lab project page 404s. |
| **DNN-Opt** (DAC'21) | **none** | — | — | — | **NO OFFICIAL CODE** | No public repo from the authors. |

**Score: 8 of 8 works with public code now fully verified running. 3 have no public code.**
AutoCkt was the last blocked item and is now unblocked.

## Extension / follow-up repos (added 2026-08-03)

| Work | Code | Env | Smoke test | Result | Notes |
|---|---|---|---|---|---|
| **ZeroSim** (ICCAD'25) | [xz-group/ZeroSim](https://github.com/xz-group/ZeroSim) | Win `zerosim` **3.10.20**, torch 2.4.1 | `python smoke_zerosim.py` | **PASS** | CircuitTransformer builds (2.83 M params), forward `(2, 11)` = num_metrics, grads on all 113 params, loss 0.506 → 0.259 over 5 steps. Needs **torch ≥ 2.1** (`nn.LayerNorm(bias=)`). |
| **CircuitSense** (ICLR'26) | [xz-group/CircuitSense](https://github.com/xz-group/CircuitSense) | Win `circuitsense` + **WSL `circuitsense` 3.10.20** | `PYTHONPATH=. python main.py --note smoke_linux --gen_num 5 --symbolic --derive_equations` | **PASS on Linux / FAIL on Windows** | Linux: **5/5 circuits, 5 transfer functions, 10 MNA equations, 100 % success**. Windows: 0/5 — see note 5. |
| **AnalogSAGE** (arXiv 2512.22435) | [xz-group/AnalogSAGE](https://github.com/xz-group/AnalogSAGE) | not built | n/a | **BLOCKED** | Code-complete (all 11 modules parse) but **ships zero data**: no netlist, config, or index. Needs an OpenAI key, a Pinecone index that is not published and has no build script, and SKY130. See note 6. |
| **RoSE / RoSE-Opt** (DAC'23, TCAD'24) | [xz-group/RoSE](https://github.com/xz-group/RoSE) | Win `rose` **3.10.20** | *not run, per request* | **REFERENCE ONLY** | Installed for browsing: torch 1.12.1, botorch 0.6.6, gpytorch 1.8.1 — imports clean. Blocked anyway: needs Cadence **and** `eval_engines/` contains only a YAML + `__init__.py` (README: "code regarding Cadence simulation will be updated soon"). |

### Surveyed but not set up

* **PowerGenie** (arXiv 2601.21984) — same first author (Jian Gao) and senior author (Xuan Zhang) as AnalogGenie; carries the Eulerian generative approach to reconfigurable power converters with analytical screening + evolutionary finetuning. **Code "released upon publication" — not public yet.**
* **CircuitFlow** (OpenReview `Za1lSj86XG`) — multimodal flow matching that jointly generates topology *and* sizing, **trained on the AnalogGenie dataset**, evaluated on OCB and AnalogGenie. Arguably the most substantive third-party extension; code availability unconfirmed.
* **AnalogXpert** (arXiv 2412.19824) — LLM-based topology synthesis; a competing approach rather than a descendant.

---

## Environments

### Windows (9 conda envs, one per repo)

`analoggenie` 3.8.20 · `lamagic` 3.9.23 · `cktgnn` 3.9.23 · `autockt` 3.7.12 · `zoaf` 3.10.20 ·
`circuitsynth` 3.8.20 · `zerosim` 3.10.20 · `circuitsense` 3.10.20 · `rose` 3.10.20

ngspice **45.2** via msys2. Two fixes were needed: the msys2 post-install script failed
(`cygpath`/`sed` missing), leaving msys2-style paths in `share/ngspice/scripts/spinit` —
rewritten to `C:/msys64/...`, backup at `spinit.bak`; before that all 7 XSPICE code models
failed to load. And the msys2 `ngspice.exe` is a GUI-subsystem binary that writes **nothing**
to stdout, so `-o <logfile>` is mandatory.

### WSL — Ubuntu 22.04.5, WSL2 (added 2026-08-03)

3 conda envs: `autockt` **3.6.15** · `circuitsense` **3.10.20** · `gpu` **3.10.20**.
ngspice **36** from apt. Disk: 7.8 GB miniconda + 195 MB repos.

> **Install note.** `wsl --install -d Ubuntu` failed with `Wsl/InstallDistro/0x80072f7d`
> ("error in the secure channel support") — a WinHTTP TLS fault fetching Microsoft's distro
> list, *not* a permissions problem. WSL 2.6.3.0 itself was already installed and healthy.
> Worked around it by fetching Canonical's rootfs with curl (which reaches the same URL fine),
> verifying the published SHA256, and using `wsl --install --from-file`. Checksum matched:
> `4499c4fe257f2fc83145b429ce211a0a43fd590e70d6261ede616210947d9f8f`.

> **conda channel note.** Miniconda 26.5.3 refuses the Anaconda `defaults` channel without
> accepting a commercial Terms of Service. Rather than accept that on your behalf, every WSL
> env uses `-c conda-forge --override-channels`, which carries Python 3.6 anyway.

---

## What WSL unlocked

### 1. AutoCkt's RL loop — the previously blocked item

The exact documented stack **installed cleanly on Linux**: `tensorflow==1.10.1`, `ray==0.6.3`,
`gym==0.10.5`, `scipy==1.1.0` on Python **3.6.15**. Python 3.6 is the precise target — ray 0.6.3
ships cp36 *and* cp37 wheels, but TF 1.10.1 stops at cp36.

```
PPO_TwoStageAmp_0: TERMINATED, 14 s, 2 iter, 600 ts, -32.5 rew
episode_reward_mean -32.46   max -19.46   min -47.88   episodes_total 20
policy_loss 0.011   vf_loss 303.7   entropy 7.69   kl 5.1e-06
SMOKE TRAINING COMPLETE / RUN EXIT: 0
```

Two iterations is far too few to demonstrate learning — reward went −29.7 → −32.5, which is
noise at this scale. The claim here is only that the loop runs end to end.

**ngspice-in-the-loop verified directly.** One `env.step()` produced
`/tmp/ckt_da/designs_two_stage_opamp/two_stage_opamp_33_34_33_34_34_17_2e-12.../` containing the
rendered `.cir`, `dc.csv`, and a real AC sweep — `v(net6)` = 339.6 V/V, inside the yaml's 200–400
gain target. (An earlier check found `/tmp` empty simply because WSL had restarted the VM and
tmpfs was wiped; re-running proved the artifacts are real.)

Deviations from the README, both forced and both documented in `_wsl/setup_autockt.sh`:
* `environment.yml` pins `numpy==1.16.4`, but TF 1.10.1's own metadata requires `numpy<=1.14.5`.
  Those pins are mutually unsatisfiable under a modern resolver; deferred to TF's constraint.
* `ray.rllib` imports `cv2` unconditionally (atari wrappers), so `opencv-python-headless` is needed.
* The README runs training from ipython at the repo root; invoking the script directly needs
  `PYTHONPATH=<repo>`.
* Capped to 2 iterations with `train_batch_size 256` / `sgd_minibatch_size 64` — the repo's own
  stop condition is convergence (`episode_reward_mean: -0.02`).

### 2. The GPU became usable

Windows CUDA PyTorch wheels exist **only** on `download.pytorch.org`, measured at **187 KB/s**
from this host → ~3.5 h for the 2.3 GB wheel, per environment. On Linux the default **PyPI**
wheel is CUDA-enabled and PyPI runs ~8× faster here. Actual install: **5 min 29 s**.

```
torch 2.13.0+cu130 · cuda available: True · NVIDIA GeForce RTX 3050 Laptop GPU
VRAM free/total 3.46 / 4.29 GB · matmul throughput 0.68 TFLOP/s
```

| Model | Windows CPU | WSL GPU |
|---|---|---|
| AnalogGenie — generate 1 topology (1025 tokens) | 399.6 s | **77 s** (incl. checkpoint copy + CUDA init) |
| LaMAGIC2 — load 944 MB checkpoint + generate | ~30 s | 17.2 s load + **3.40 s** generate, 0.99 GB VRAM |

**Cross-platform validation.** LaMAGIC2's GPU output is *byte-identical* to the Windows CPU run —
`<duty_0.5> <sep> VIN L 3, VOUT L 4, GND Sb 2, Sa 0 Sa 1 Sb 2 L 3, Sa 0 Sa 1 L 4<sep></s>` — and the
self-consistency loss is **0.0610 on both**, across different OS, torch version (2.0.1+cpu vs
2.13.0+cu130) and device. That is a much stronger correctness signal than either run alone.

### 3. CircuitSense's equation derivation started working

See note 5.

---

## Per-work detail (carried forward from the Windows pass)

### AnalogGenie

Checkpoint `Pretrain.pth` (189 MB) from HuggingFace; model builds as **11.81 M parameters,
vocab 1005**. Validation of the generated Eulerian traversal (`_logs/validate_analoggenie.py`),
first circuit = 789 tokens up to `TRUNCATE`:

```
distinct devices : 42        malformed device tokens : 0
distinct pins    : 154       illegal pin names       : 0
named nets       : 15        orphan pins             : 0
electrical nodes : 32        devices w/ incomplete pin sets: 0
```

The reconstructed netlist is electrically sensible: VDD carries only PMOS source/bulk pins, VSS
only NMOS, a current mirror at `n_int_1768` (PM1_G/PM2_G tied to PM4_D), and VOUT1 carries
`C1_P C2_P R2_P` (Miller compensation).

Data pipeline verified on a 25-circuit slice: `SPICE2GRAPH_compress.py` → `Augmentation.py` →
`Stack.py` produced `Training.npy (98, 1025)` and `Validation.npy (3, 1025)` (1025 = block_size
1024 + 1). Spot-checked `Dataset/4`: netlist `M0 (VDD VDD VIN1 VSS) nmos4` → adjacency with
D/G→VDD, S→VIN1, B→VSS. Correct.

> **Repo bug worth reporting upstream:** `Inference.py:187` calls `torch.load(savemodel_name)`
> with no `map_location`. The released checkpoint was saved from CUDA, so on any CPU-only machine
> this raises `RuntimeError: Attempting to deserialize object on a CUDA device`.
> One-line fix: `torch.load(savemodel_name, map_location=device)`.

### LaMAGIC2

The checkpoint is a T5 with exactly **one non-standard parameter, `vout_linear.weight (768,1)`** —
the "float input" projection turning duty-cycle options, voltage conversion ratio and efficiency
into 7 encoder prefix embeddings. The smoke test therefore uses the repo's own model class.

Verified: `from_pretrained` reports **0 missing / 0 unexpected / 0 mismatched keys**, with
`vout_linear` and `shared.weight` byte-identical to the raw file. Conditioning demonstrably
matters — swapping true specs for zeros or extremes changes both loss (15.47 → 15.95 → 16.91)
and the generated topology, with the **true** specs scoring best.

> **Why the teacher-forced number is not meaningful.** Re-encoding the dataset's `output` with
> `" ".join(...split())` yields label ids differing from training by SentencePiece word-boundary
> markers: the reference encodes `L`/`3` as ids 434/519 while the model expects word-initial
> `▁L`/`▁3` (301/220). At every position where tokenization *is* unambiguous (`<sep>`, `VIN`,
> `VOUT`, `,`) the model assigns **logprob exactly 0.000**. The gap is my label reconstruction,
> not the checkpoint. Exact scoring needs the repo's `tokenized(config)` step, which requires the
> config placeholders (`[YOUR_DATA_SAVE_DIR]`, `[YOUR_MODEL_SAVE_DIR]`) filled in.

### CktGNN

OCB ships inside the repo (CktBench101 = 10 000 circuits, CktBench301 = 50 000) — no separate
download. One epoch over the 9000/1000 split took ~4 min on CPU; loss fell 22.02 → 18.31, then
the decoding-validity experiment ran (88.35 % valid DAGs / 84.09 % valid circuits / 87.50 % novel;
recon accuracy 0.0002, expected after 1 epoch of the paper's 300).

`--ng` is metadata only and does **not** slice the dataset. Windows fix applied to
`layers/constants.py`: `path[:path.rindex("/")]` assumes POSIX separators and raises
`ValueError: substring not found`; replaced with `os.path.dirname` + `os.pardir`.

### ZOAF

> **PySpice wiring.** PySpice 1.5 on Windows needs *two* env vars. Setting only
> `NGSPICE_LIBRARY_PATH` fails with `TypeError: expected str... not NoneType` because
> `_load_library` dereferences an unset `NGSPICE_PATH` to build `SPICE_LIB_DIR`. Set both:
> `NGSPICE_LIBRARY_PATH=C:\msys64\ucrt64\bin\libngspice-0.dll` and
> `SPICE_LIB_DIR=C:\msys64\ucrt64\share\ngspice`.

Quickstart ran in 17.6 s with 73 real simulator calls. The objective ran up to the box corners
(params pinned at the 0.1/100 bounds), characteristic of this unconstrained toy gain objective
rather than a framework fault.

### Krylov et al. (Circuit-Synthesis)

Windows-aware by design — `utils.py` selects the **bundled** `ngspice/Spice64/bin/ngspice.exe`
on Windows. The default `nmos` sweep is ~24 000 simulations; narrowed to 5 widths × 3 resistances
= 15 points, run, then **`nmos.yaml` restored**. Four scratch dirs the Dockerfile would create
must exist first: `tmp_out/`, `data/nmos/`, `out_plot/`, `result_out/`.

### AnalogGenie-Lite

`base_dirs` ships **empty** by design (bring your own dataset), so it was pointed at AnalogGenie's
`Dataset/`. On `Dataset/4` the compression is directly visible — device node `NM1` eliminated, its
four pins wired into an intra-device cycle:

```
AnalogGenie      : 8 nodes  [VDD VSS VIN1 NM1 NM1_D NM1_G NM1_S NM1_B]
AnalogGenie-Lite : 7 nodes  [VDD VSS VIN1     NM1_D NM1_G NM1_S NM1_B]
```

Stage 2 (subgraph compression) is hardcoded to the authors' motifs and needs frequent-subgraph
mining on your own data before it generalises.

### AnalogToBi

GitHub link appears only in the arXiv abstract, not in search results. Ships the full
3351-circuit dataset and an 11.3 M-param decoder-only Transformer trained from scratch;
**no checkpoint released**. Bipartite preprocessing: `Success: 2347 / Skipped: 1003 / Errors: 0`
in 15 s. The skips are its own ERC rejecting malformed circuits (e.g. `C1 must connect to exactly
2 different nets, found 1: {'VDD'}`), not failures.

---

## Notes on decisions and findings

**Note 5 — CircuitSense: a genuine platform bug, not a config problem.** On Windows the pipeline
prints "Pipeline completed successfully!" but the summary shows **0/5 successful**, every circuit
failing with `cannot pickle 'module' object` / `Can't pickle <class 'lcapy.mnacpts.Vstep'>`. The
equation-derivation stage wraps lcapy analysis in `multiprocessing` for timeouts; Windows uses
**spawn**, which must pickle those objects, and lcapy objects are not picklable. Linux uses
**fork** and does not. Under WSL the same command gives **5/5, 100 % success, 5 transfer functions,
10 MNA equations, 0 timeouts** — and the maths is right: circuit `1_2` (V1–C1–R1) yields
`s/(s + 1/(C1*R1))`, a textbook high-pass RC. The success message is misleading on Windows;
always check the summary block. (One residual: t-domain MNA hits
`'SuperpositionVoltage' object has no attribute 'sympy'`, an lcapy 1.26 API drift; s-domain and
transfer functions are unaffected.)

**Note 6 — AnalogSAGE is blocked on unpublished data, not on code.** All 11 modules compile
cleanly, but a filesystem scan finds **no** `.spice`, `.sp`, `.cir`, `.json`, `.pkl` or `.yaml` —
the repo is Python only. `BO.py` (the one module that imports no OpenAI/Pinecone and could
otherwise run standalone on ngspice + botorch) expects a `test.spice` testbench that is not
shipped. `queryPinecone.py` only *queries* a Pinecone index named `research-papers-pa`; there is
no script to build it, and 8 hardcoded `api_key = ""` placeholders sit across 4 files. The README
asks you to "pre-generate the Design knowledge RAG and Topology vector database" without providing
the means. Even with SKY130 installed this cannot run.

**Note 7 — ZeroSim's dataset was deliberately skipped.** The released `Xun49/Amplifer60` is a
single **4.27 GB** zip (~48 min at this link speed) and no checkpoint is published, so the smoke
test exercises `model/` directly with a synthetic batch shaped per the repo's own docstring. Say
the word if you want the real dataset pulled and a few genuine training steps run.

**Note 8 — CPU vs CUDA on Windows.** All Windows envs use CPU PyTorch for the reason in §2 above.
Every Windows smoke test is small enough that this costs only wall-clock. GPU work now goes
through WSL.

**Environment isolation.** 9 Windows envs + 3 WSL envs, one per repo, as requested. AnalogGenie-Lite
and AnalogToBi reuse `analoggenie` deliberately — both are pure pandas/tqdm preprocessing with no
conflicting pins, and AnalogGenie-Lite is by design a plug-in to AnalogGenie.

**AnalogGenie's and LaMAGIC's `environment.yml` cannot be used as shipped on Windows** — both are
full `conda env export`s carrying Linux build strings (`h5eee18b`, `_libgcc_mutex`). Rebuilt from
their real pins. Under WSL they would work verbatim, if you ever want the exact upstream envs.

**Files added, and what was modified.** Smoke drivers and reduced-scope copies are new files
alongside the originals (`Inference_smoke.py`, `SPICE2GRAPH_compress_smoke.py`,
`Augmentation_smoke.py`, `Stack_smoke.py`, `smoke_lamagic2.py`, `smoke_engine.py`,
`smoke_zerosim.py`, `config/smoke_config.yaml`, `autockt/val_autobag_ray_smoke.py`, and the
`_wsl/*.sh` scripts). Only two repo files were edited: `CktGNN/layers/constants.py` (Windows path
bug) and the msys2 `spinit` (backed up). `Circuit-Synthesis/config/circuits/nmos/nmos.yaml` was
narrowed and then restored.

---

## Log index — `C:\Users\Devavrat\circuit-repro\_logs\`

| File | Contents |
|---|---|
| `analoggenie_smoke.log` + `analoggenie_{preprocess,augment,stack}.log` | checkpoint generation and data pipeline |
| `validate_analoggenie.py` | topology structural validator + netlist reconstructor |
| `lamagic2_smoke.log`, `lamagic2_diag{,2,3,4}.log` | checkpoint inference and the four diagnostic passes |
| `cktgnn_smoke.log` | full VAE epoch + decoding-validity experiment |
| `autockt_engine.log` | Windows ngspice two-stage op-amp evaluation |
| `zoaf_smoke.log` | 73-call optimizer run |
| `circuitsynth_smoke.log` | dataset generation + 100 training epochs |
| `analoggenie_lite.log`, `analogtobi_smoke.log` | compression / bipartite preprocessing |
| `zerosim_smoke.log`, `circuitsense_smoke.log` | extension smoke tests (Windows) |
| `rc.cir`, `rc3.log` | ngspice install verification |

WSL scripts live in `_wsl/`: `setup_wsl.sh`, `setup_autockt.sh`, `run_autockt.sh`,
`verify_autockt_sim.sh`, `setup_gpu.sh`, `run_gpu_models.sh`, `smoke_lamagic2_gpu.py`,
`run_circuitsense.sh`, `inventory.sh`.
