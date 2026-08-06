# Handover — executor session 1 → next

**From:** an Opus 4.8 executor session, 2026-08-06 · **Repo:** `C:\Users\Devavrat\circuit-repro`
· **Branch:** `lna-exec` (7 commits, off `main` @ `535104c`, **never pushed**)

You are picking up execution of the LNA plan set in
`.claude/worktrees/lna-plans/lna/plans/` (start at `00-OVERVIEW.md`). That set is
the roadmap; this file is what has actually been *done*, what was *found*, and
exactly where to resume. Read `WORKLOG.md` (entries R1/R2 are mine) and
`FINDINGS.md` (§5 P0 block is mine) for the measured detail.

---

## 1. TL;DR — what shipped this session

| Plan item | Status | Key result |
|---|---|---|
| **WP-SPEC** (01-SPEC, sched. days 1–2) | ✅ done | `spec.py` + 4 specs + spec-driven screen; legacy reproduction **exact**; in-scope union **94.1%** |
| **H-Q3** floating detector (03-BIAS/misc) | ✅ done | detector built; **1081 re-diagnosed** (not floating — ideal-inductor singularity), fixed by finite-Q |
| **P0** novelty metric (04-GEN §1) | ✅ done | WL-hash whole-corpus metric; **NDL@256 = 16 (wifi24) / 26 (legacy)** at prefix 12 — the frozen baseline |
| **WP-REF day 3** (02-REF §2) | ✅ done | device table + **stage-A CG anchor**; S11 −23.3 dB; **H-Q2 closed** (Re(Zin) 0.1%) |
| WP-REF day 4 (stage-B + H-Q1) | ⏳ next | not started |
| WP-BIAS, WP-GEN P1–P5, WP-SIZE | ⏳ later | not started |

Everything below is committed. `main` is untouched; nothing was pushed.

**Commits (newest first):**
```
e65bc7f WP-REF day 3: device table + stage-A CG anchor (closes H-Q2)
cd7c6f6 P0: complete the 256-sample frozen protocol
8926675 P0: WL-hash novelty metric vs the whole corpus (04-GEN §1)
b562540 H-Q3: floating-subcircuit detector + resolve the 1081 mis-diagnosis
74c8820 WP-SPEC day 2: spec-driven screen + calibration
cfa1721 WP-SPEC day 1: spec.py loader/validator + spec targets
9aae632 Import existing LNA pipeline under version control   <- lna/ was untracked before this
```

---

## 2. New / changed files

```
lna/spec.py                 NEW  spec loader/validator + 3 compiled views (screen/objective/seed_filter)
lna/specs/                  NEW  wifi24, gps-l1, wideband-sdr, legacy-lna5 (+ README)
lna/calibrate_specs.py      NEW  WP-SPEC acceptance runner
lna/ref/device_char.py      NEW  device characterization sweep -> device_tables.csv (+ .png)
lna/ref/ref24_cg.cir        NEW  stage-A common-gate reference (the match anchor)
lna/ref/check_ref.py        NEW  reference regression runner (+ ref_baseline.json)
lna/ref/README.md           NEW  reference-LNA writeup incl. the S21 finding
lna/screen.py               MOD  --spec (spec-driven L0 screen); default path byte-unchanged
lna/pipeline_yield.py       MOD  --spec, --inductor-q; made torch-free (local REPO)
lna/to_spice.py             MOD  inductor_q= / --inductor-q (finite-Q, default off = ideal)
lna/topology.py             MOD  floating_devices()/has_floating_subcircuit (H-Q3)
lna/novelty.py              REWRITE  WL-hash whole-corpus metric + frozen-protocol harness
lna/WORKLOG.md              MOD  R1 (1081), R2 (H-Q2) resolution entries
lna/FINDINGS.md             MOD  §5 P0 re-baseline block
```

---

## 3. Environments (this bit up front — it costs an hour if rediscovered)

Three Pythons, used deliberately:

| use | interpreter | has |
|---|---|---|
| **analysis (default)** | `python` → `C:\Python314\python.exe` | py 3.14, numpy, pyyaml, matplotlib — **torch-free** |
| **vocab guard** | `C:\Users\Devavrat\radioconda\envs\analoggenie\python.exe` | py 3.8, **torch** 2.0.1+cpu, networkx |
| **GPU generation** | WSL `/opt/miniconda/envs/gpu/bin/python` | py, **torch 2.13+cu130, CUDA** (RTX 3050) |

- Almost all analysis (spec/screen/pipeline_yield/novelty/calibrate/device_char/check_ref)
  runs under the **default py 3.14** — I deliberately kept the analysis stack torch- and
  networkx-free (the WL hash is hand-rolled) so it needs no conda env.
- Only `test_vocab_matches_upstream.py` needs torch → run it with the **analoggenie** python.
- **GPU generation must go through PowerShell, not Git Bash** — Git Bash mangles
  `/opt/...` into `C:/Program Files/Git/opt/...` (WORKLOG X10). Repo is `/mnt/c/Users/Devavrat/circuit-repro`
  in WSL. Example that worked (a script is cleaner than inline quoting):
  ```
  # PowerShell, background
  wsl -e bash /mnt/c/.../scratchpad/gen.sh   # each line: <gpu_py> lna/generate.py --device cuda ...
  ```
  `generate.py --seed N` seeds **both** the prefix pool and sampling, so a new seed = an
  independent draw. Batch 32 / 256-token cap on the 4 GB card (batch 64×384 OOMs — F3).
- **ngspice:** `C:\msys64\ucrt64\bin\ngspice_con.exe` (the `_con` build writes stdout; plain
  `ngspice.exe` does not).

---

## 4. Regression — now a QUARTET (run before AND after every WP)

00-OVERVIEW says "trio"; I added `check_ref.py`, making it four. All currently green:

```bash
# 1. vocab guard (needs torch -> analoggenie python)
"C:/Users/Devavrat/radioconda/envs/analoggenie/python.exe" lna/test_vocab_matches_upstream.py   # MATCH
# 2. legacy screen unchanged
python lna/screen.py --corpus --indices 461-492,1081-1090 --per-circuit 5                        # 59.4% (114/192)
# 3. pipeline yield
python lna/pipeline_yield.py --indices 461-492,1081-1090                                          # 40/42 (41/42 with --inductor-q 12)
# 4. reference anchor
python lna/ref/check_ref.py                                                                       # GREEN
# + WP-SPEC acceptance
python lna/calibrate_specs.py                                                                     # ALL ACCEPTANCE CRITERIA MET
```

Ground rules from 00-OVERVIEW still hold: **work on `lna-exec` (or a worktree), commit per
task, never push to `main`.**

---

## 5. Findings & decisions that change the plan (read before resuming)

1. **device_budget widened `[3,12]→[3,16]`** in the three real specs. Measurement (the
   calibration's stated purpose) showed real single-ended corpus LNAs reach 14 devices.
   Documented in each YAML; reversible.
2. **The corpus is multi-class, which refines H-Q4.** Union-over-41 is 78% *not* because the
   criteria are mis-tuned but because the corpus contains classes the three single-ended-MOS
   specs deliberately don't target: 3 differential LNAs (484/485/1087), 3 with no labeled
   output port (472/480/492), 1 broken (1081), + 2 L0-ambiguous inductorless (477/1088).
   Union over the **in-scope class is 94.1%**, non-LNAs pass 0. `calibrate_specs.py` reports
   both. A `differential:true` spec + screen support (a plan stretch item) would lift the 78%.
3. **Index 1081 was mis-diagnosed by the plan.** It is NOT a floating sub-circuit — it is fully
   connected and fails on an *ideal-inductor branch singularity* (`ll4#branch`: node VB1 reached
   only through ideal inductors + a MOS gate). Fix = finite inductor Q (`to_spice.py --inductor-q 12`,
   default off so existing baselines are unchanged); yield 40/42 → 41/42. See WORKLOG R1. The
   floating detector I built is still correct/useful for *generated* islands.
4. **P0 froze the measuring stick.** Whole-corpus WL-hash novelty; **NDL@256 = 16 (wifi24) /
   26 (legacy)** at prefix 12, collapsing at 24. **Adoption rule for every future GEN arm: beat
   NDL@256 at equal-or-better inductor ratio** (FINDINGS §5). `median NN-sim = 1.000` among
   passing samples = heavy copying pressure. The seed-2338 halves live in `lna/out/sweep{P}_s2338/`
   (seq*.txt gitignored, meta.json kept).
5. **Stage-A CG anchor: the plan's `S21 ≥ 8 dB` is unachievable, and that is a real result.**
   S11 = −23.3 dB (Gate G1 ✓) and Re(Zin) matches 1/(gm+gmb) to 0.1% (**H-Q2 closed**). But a
   resistive-load CG into 50 Ω is gain-limited to ~0 dB (VDD headroom caps RL; the 50 Ω port
   caps a matched CG at gm·50≈1), which also pins NF ~4 dB. **Gain/NF need a tuned load →
   stage B.** Full reasoning in `lna/ref/README.md` + WORKLOG R2.

---

## 6. Where to pick up (in order)

**Immediate: WP-REF day 4 — stage B + H-Q1** (`plans/02-REFERENCE-LNA.md` §3–4).
- Build `lna/ref/ref24_csdeg.cir`: CS + explicit Cex + Ls + Lg, the F1 fix (effective ωT set by
  `gm/(Cgs+Cex)` so Ls ≈ 1.1 nH is realizable). Use `device_tables.csv` for gm/Cgs at the bias.
- H-Q1 (Zin=1122 Ω anomaly) falls out of the build order: the cascode-bypass test (step 2, with/
  without the gate bypass cap) and the tank-detune test (step 3 vs 1). Write the outcome to WORKLOG.
- `check_ref.py` is already structured to take a second deck — add `"ref24_csdeg.cir"` to `DECKS`,
  add its expected metrics + a `check_gates` branch, then `--update`.
- Gate G1 for the week: stage-A already passes S11 ≤ −10 dB, so the gate is met even if stage B stalls.

**Then, per the schedule (`plans/06-SCHEDULE.md`):**
- **WP-BIAS** (`03-BIAS`, week 1 day 5–6): `bias.py` DC-graph + R-GATE/R-CASCODE-BYPASS rules,
  `pipeline_yield --bias`, validation ≥80% conducting on the 40 dataset LNAs (Gate G2). Note the
  DC-connectivity graph there is a close cousin of `topology.floating_devices()` — reuse the shape.
- **WP-GEN P1–P5** (`04-GEN`, week 2): class-token fine-tune (P1) is highest-leverage. The GPU
  path + frozen protocol are ready; **every arm is judged by `novelty.py --eval <dir> --spec …`
  against the NDL@256 baseline** (§5.4 above). Gate G3 = some arm beats the prefix curve on NDL.
- **WP-SIZE** (`05-SIZE`, week 3): needs WP-SPEC objective (done), the anchor (done), and WP-BIAS.
  The anchor re-derivation test (§3.1) is the highest-value first check. Note `spec.objective()`/
  `feasible()` are already implemented and feasibility-first.

---

## 7. ngspice gotchas discovered THIS session (add to your mental X-table)

| # | trap | fix |
|---|---|---|
| N1 | `save @m1[id] …` before `sp` makes S-params/node voltages **disappear** — `save` *restricts* the saved set | don't `save` if you need S-params; single-`op` device params (`@m1[gm]`) are available without `save` (only `.dc` sweeps need pre-`save`, X3) |
| N2 | `wrdata` writes **2N columns** for N vectors — `(xscale, value)` pairs, not N columns | parse odd columns; and give `wrdata` a **Windows** path (ngspice_con is a Windows binary — `/tmp/...` silently fails) |
| N3 | NF came out 92 dB | `inoise_spectrum` is **V/√Hz (amplitude)**, so `NF = 10·log10(inoise²/4kTRs)`; 4kTRs@300K = 8.284e-19 |
| N4 | `meas noise …` → "measure limited to tran/dc/sp/ac" | `meas` can't read a noise plot; index the vector instead (`let nfv=…; nfv[k]` at the f0 grid point) |
| N5 | CG with an ideal source current sink can look under-determined | it solves (device pins Vs through the channel); `.option rshunt=1e12` for safety |

---

## 8. Quick reference — the tools you'll use

```bash
python lna/spec.py --all                                  # validate specs
python lna/spec.py wifi24 --screen-index 461              # screen one corpus circuit
python lna/screen.py --generated "dir/seq*.txt" --spec wifi24
python lna/pipeline_yield.py --generated dir --spec wifi24 [--inductor-q 12]
python lna/novelty.py --eval dir --spec wifi24            # one frozen-protocol row
python lna/novelty.py --rebaseline256 --spec wifi24       # full 256 baseline
python lna/calibrate_specs.py                             # WP-SPEC acceptance
python lna/ref/device_char.py --plot                      # device table
python lna/ref/check_ref.py [--update]                    # reference regression
```

Specs live in `lna/specs/`. Reference decks + device table in `lna/ref/`. Generated runs in
`lna/out/` (seq*.txt ignored, meta.json kept). Plans in `.claude/worktrees/lna-plans/lna/plans/`.
