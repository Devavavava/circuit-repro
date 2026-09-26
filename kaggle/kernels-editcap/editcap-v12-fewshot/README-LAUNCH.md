# editcap-gpu -- launch checklist (READ BEFORE PUSHING)

This kernel runs the GPU leg (arms B + C interleaved) of campaign
**qwen-editcap-v0** (pre-registration `kaggle/CAMPAIGN-QWEN-EDITCAP.md`) over all
13 cells of the frozen failure library `kaggle/editcap-lib/`. It was PREPPED but
**NOT pushed** by the build session (containment: no pushes). A later session
must verify the items below before `kaggle kernels push`.

## What the kernel does

`kernel.py` mirrors the proven `kaggle/kernels/loop-gpu` layout (preflight ->
bootstrap -> untar llamacpp -> launch llama-server -> health-gate), then runs:

```
python kaggle/editcap_run.py --lib kaggle/editcap-lib --out /kaggle/working/editcap \
    --arm both --k 3 --pdk gf180mcu --llm-url http://127.0.0.1:8080/v1 ...
```

It CLONES origin `main` tip at run start (existing convention: a script push
uploads only `kernel.py`; the driver + library + loop code come from the clone).

## HARD PREREQUISITE -- push origin FIRST

Because the kernel clones origin `main`, the driver + library MUST be on origin
`main` before the kernel runs, or the clone will not contain them:

- `kaggle/editcap_run.py` (the driver)
- `kaggle/editcap-lib/` (INDEX.json + 13 cell dirs)

The pre-reg names this the era SHA rule: **"GPU leg clones origin => REQUIRES A
PUSH first"** (`CAMPAIGN-QWEN-EDITCAP.md`, Governance / Execution sequence). A
separate box job runs arm A (the null) from this same worktree; the whole
campaign shares ONE origin SHA across arms. Do NOT push a partial tree.

## Verify BEFORE pushing (all must pass)

1. **Quota.** GPU/internet kernels draw the weekly GPU quota. Confirm remaining
   quota is enough for ~2.5-3.5 h wall (pre-reg cost estimate: 13 cells x 6 edits
   x ~640 evals ~= 50k evals + LLM time). One leg per week fits; check the
   Kaggle account's GPU-hours budget is not already spent by the arm-A/other legs.

2. **Push-verify (origin has the driver + library).** After the origin push,
   confirm the tip actually carries both:
   ```bash
   git ls-tree -r --name-only origin/main | grep -E 'kaggle/editcap_run.py|kaggle/editcap-lib/INDEX.json'
   ```
   Both paths must appear. The kernel's `REPO_SLUG`/`REPO_BRANCH` must match the
   origin you pushed to (default `Devavavava/circuit-repro` `main`).

3. **kernel-metadata id.** Replace the `id` username in
   `kernel-metadata.json` with the launching account's username if it is not
   `devavratpatni` (PLAYBOOK ships `KAGGLE_USERNAME` as the placeholder; here it
   is pre-filled to `devavratpatni` -- confirm it matches YOUR account).

4. **Datasets attached.** `dataset_sources` lists ghtoken, ngspice47,
   llamacpp-cuda, gguf-qwen30, and **pdk-gf180mcu** (the library is gf180mcu --
   evidence.json pdk; sizing is threaded `--pdk gf180mcu`). All five must be
   processed and attachable. The kernel's `preflight()` fails in seconds if any
   is missing -- but a failed preflight still consumes a launch.

5. **RUNNING fence (no double-launch).** Before pushing, confirm no editcap-gpu
   kernel is already RUNNING/QUEUED for this account (a second push while one is
   live wastes quota and can race the output):
   ```bash
   kaggle kernels status <user>/circuit-repro-editcap-gpu
   ```
   Only push when the prior status is COMPLETE/ERROR/CANCELLED (or the kernel has
   never run).

6. **Variant check -- results-B.jsonl presence (adapted).** loop-gpu's variant
   check confirmed the RIGHT arm/variant ran. For editcap the analogue is:
   after the run, `kaggle kernels output` must contain BOTH
   `editcap/results-B.jsonl` AND `editcap/results-C.jsonl` (arm=both), each with
   13 rows, and `editcap/adjudication/<spec>/<arm>/` present per cell (the
   pre-reg's VERBATIM adjudication archive -- prompt.txt, raw_output.txt,
   diagnosis.txt for arm B, edit<i>.net + edit<i>.meta.json). If results-B.jsonl
   is absent or short, arm B did not complete -- do NOT score; investigate the
   kernel log before re-launching.

## Push + monitor (once all six pass)

```bash
kaggle kernels push   -p kaggle/kernels-editcap/editcap-gpu
kaggle kernels status <user>/circuit-repro-editcap-gpu
kaggle kernels output <user>/circuit-repro-editcap-gpu -p ./_out/editcap
```

## Results archive (per pre-reg governance: store writes NONE; archive only)

Archive the kernel output to `kaggle/campaigns/qwen-editcap-v0/` alongside the
arm-A results. The adjudication archive feeds a later stronger-model audit
(grounding vs confabulation) -- keep it VERBATIM, do NOT summarize. No datastore
sync (`sync_lines`) for this campaign: it is a capability MAP, not a topology
harvest.
