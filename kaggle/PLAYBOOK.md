# Kaggle worker PLAYBOOK (v0)

How to run the circuit-repro LNA reasoning loop on Kaggle's free tier, driving it
from the box. The box is the **control plane**; every Kaggle session is a
**disposable worker**. Kaggle never pushes to git; it clones read-only and returns
results as notebook-output artifacts, which the box merges.

Anything below marked **UNTESTED** could not be exercised on the box (no Kaggle
account, no GPU, no llama.cpp, no network). Only the parser round-trip
(`test_proposal.py`) and the driver's dry-run/no-sim + real-sizing paths were run
locally.

---

## 0. One-time account + secrets setup  (UNTESTED)

1. **Phone-verify** your Kaggle account (required for GPU + internet in kernels).
2. **Secrets** (Add-ons -> Secrets, per kernel or account-wide):
   - `GH_READ_TOKEN` — a GitHub **read-only** PAT (fine-grained, contents:read on
     this repo). `bootstrap.sh` clones `main` with it. Never a write token.
3. **Datasets** to create (private):
   - **weights** (`<user>/circuit-repro-weights`): the GGUFs from the
     `import-weights` kernel output **plus the two box-side checkpoints**
     `Pretrain.pth` and `ft_p5v7_v2.pth` (each ~190 MB, gitignored, uploaded from
     the box via `kaggle datasets version`). `bootstrap.sh` symlinks the `.pth`
     files into the clone if present. GGUFs are only needed by the GPU loop; the
     `.pth` checkpoints only if the 12M generator is used as a pool filler (the
     LLM loop is torch-free).
   - **ngspice cache** (`<user>/circuit-repro-ngspice47`): the
     `ngspice47.tar.gz` produced by the `setup-cpu` kernel output.
   - **llamacpp cache** (`<user>/circuit-repro-llamacpp`): the
     `llamacpp.tar.gz` produced by `build-llamacpp.sh` (run once in a short GPU
     session).
4. **REPO_SLUG**: set `REPO_SLUG=<youruser>/circuit-repro` for every kernel
   (env or edit the default in `bootstrap.sh`). The default is a placeholder.

---

## 1. Session types

| session      | accel     | internet | what runs                                   | quota |
|--------------|-----------|----------|---------------------------------------------|-------|
| setup-cpu    | none      | on       | `bootstrap.sh` end-to-end + tar ngspice     | free (CPU) |
| import-weights | none    | on       | download GGUFs, print sha256, save dataset  | free (CPU) |
| build-llamacpp | GPU (short) | on   | one-time CUDA build of llama-server         | GPU (~15 min) |
| loop-gpu     | GPU t4x2  | on       | untar caches, launch server, run driver     | GPU (30 h/wk) |

**All setup and debug happens on CPU sessions.** A GPU session runs only
pre-validated code. Re-run `setup-cpu` (CPU) until the acceptance gate is green
*before* ever starting a GPU session.

---

## 2. Quota discipline (30 h/wk GPU)

- **Never idle an interactive GPU session.** Use headless **Save & Run All**
  (batch) so the session exits when the script does.
- Target **3–4 h** batch runs; the driver is bounded (`--k`, `--budget`,
  `--seeds`, one edit round) so a run finishes well inside that.
- Setup, debugging, spec-tweaking, and re-running the acceptance gate are **CPU
  only** — they cost no GPU quota.
- `build-llamacpp` is a one-time short GPU job; cache its output and never rebuild.
- The `loop-gpu` kernel **always flushes** `/kaggle/working/trajectory/` in a
  `finally:` block, so even a killed session returns the rows it already measured.

---

## 3. The acceptance gate (must be green on CPU before any GPU run)

`bootstrap.sh` stage (f) runs, in order (writes `report/gate.log` + `bootstrap.json`):

```
python lna/extract.py --selftest
python lna/ref/check_ref.py
python lna/ref/check_bjt.py
python lna/spec.py --all
python lna/solve_spec.py wifi24 --corpus --budget 100 --seeds 1   # ~1 min smoke
```

Any failure -> non-zero exit, no GPU session, no label claim. `bootstrap.json`
records python/git/ngspice versions + per-stage timings for provenance.

ngspice **must be >= 42** (the `sp` portnum/z0 syntax); the bootstrap pins **47**.
conda-forge 41 segfaults; older silently fails. The build prefix is FIXED at
`/kaggle/working/ngspice47` because spinit bakes absolute codemodel paths.

---

## 4. Driving from the box with the kaggle CLI  (UNTESTED — CLI install pending approval)

Once the `kaggle` CLI install is approved on the box:

```bash
# push a kernel (edit kernel-metadata.json: replace KAGGLE_USERNAME first)
kaggle kernels push -p kaggle/kernels/setup-cpu
kaggle kernels status  <user>/circuit-repro-setup-cpu
kaggle kernels output  <user>/circuit-repro-setup-cpu -p ./_out/setup

# turn a kernel output into / update a dataset
kaggle datasets create  -p ./_out/setup            # first time (add dataset-metadata.json)
kaggle datasets version -p ./_out/setup -m "ngspice47 rebuild"

# add the box-side checkpoints to the weights dataset
kaggle datasets version -p ./_out/weights -m "add Pretrain.pth + ft_p5v7_v2.pth"

# run the loop (headless batch)
kaggle kernels push   -p kaggle/kernels/loop-gpu
kaggle kernels status <user>/circuit-repro-loop-gpu
kaggle kernels output <user>/circuit-repro-loop-gpu -p ./_out/loop
```

Every `kernel-metadata.json` ships with `KAGGLE_USERNAME` as the id placeholder —
replace it before pushing. `dataset_sources` are left empty; attach the ngspice /
llamacpp / weights datasets in the Kaggle UI or add their slugs to
`dataset_sources` before pushing.

---

## 5. Results merge procedure

Kaggle emits `trajectory/<run_id>.jsonl` (schema: `kaggle/schemas/trajectory.schema.json`)
and `designs/<spec>/` (solve_spec layout). Download the kernel output, then:

```bash
# ALWAYS dry-run first — inspect what would merge
python lna/sync_lines.py --source ./_out/loop/trajectory --dry-run
# then, only if the dry-run is clean:
python lna/sync_lines.py --source ./_out/loop/trajectory
```

Each row carries its `run_id`, and (via `bootstrap.json`) the ngspice version and
layout config that produced it, so provenance is never lost on merge.

---

## 6. Label-domain rule (do not skip)

**Kaggle-produced rows are a SEPARATE label domain from the box's golden store**
until a goldens-parity pooling ruling. The ngspice build, checkpoint set, and
sizing budget may differ from the box's golden geometry
(`to_spice.layout_cfg` stamps geometry precisely because different geometry =
different domain). Do not pool Kaggle margins into the golden store; keep them
tagged as Kaggle-domain until a ruling says a parity check passed. See
`kaggle/schemas/README.md` §"Label-domain rule".

---

## 7. Loop knobs (driver.py)

| flag            | meaning                                         | typical |
|-----------------|-------------------------------------------------|---------|
| `--spec`        | spec name in `lna/specs/` or a path             | wifi24  |
| `--k`           | proposals requested from the LLM                | 3       |
| `--edit-rounds` | edit rounds on the best candidate (v0: 0 or 1)  | 1       |
| `--seeds`       | CMA-ES seeds per sizing                          | 2       |
| `--budget`      | ngspice evals per sizing                         | 200     |
| `--base-url`    | llama-server OpenAI endpoint                     | :8080/v1|
| `--grammar-file`| GBNF to constrain decode                         | grammar.gbnf |
| `--dry-run`     | canned fixtures, no GPU/server (box only)        | —       |
| `--no-sim`      | skip ngspice sizing (structure-only smoke)       | —       |

Verified on the box: `--dry-run --no-sim` (full structural path, no ngspice) and
`--dry-run` with real tiny sizing (`--budget 50 --seeds 1`) both run green
end-to-end and emit schema-valid trajectory rows through all eight phases. The
**live** LLM path (`--base-url` to a real llama-server) is **UNTESTED** here.
