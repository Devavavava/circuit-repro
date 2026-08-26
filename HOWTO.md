# HOWTO — design an LNA from a spec

Three steps, three commands: **write a spec → solve it → view the design.** You do not
need to read anything else in this repo to use it.

An LNA (low-noise amplifier) is the first amplifier in a radio receiver. You describe what
you want with numbers (frequency, noise, gain, match, power); the tool finds a circuit and
picks its device values so it meets those numbers, then verifies it in a SPICE simulator.

## Setup (once per terminal)

```bash
source env.sh          # sets up python + ngspice for this shell
```

---

## Step 1 — Write your spec

A spec is one small YAML file in `lna/specs/`. Copy this template to
`lna/specs/<name>.yaml` and change the numbers. Every field is explained inline.

```yaml
name: myradio                 # MUST match the filename (myradio.yaml)
description: my 2.4 GHz LNA    # free text

process:
  models: AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt
  vdd: 1.1                    # supply voltage (V)
  temp: 27                    # temperature (deg C)

band:
  type: narrowband            # narrowband  (one tuned frequency)  |  wideband
  f0: 2.442e9                 # centre / reporting frequency (Hz)
  f_lo: 2.400e9               # band edges (Hz): S11 is checked across this whole range
  f_hi: 2.4835e9

ports:
  z0: 50                      # reference impedance (ohms) -- almost always 50
  input: VIN1
  output: VOUT1

constraints:                  # HARD gates. A design is "feasible" only if ALL of these pass.
  nf_db:    {max: 2.5}        # noise figure, dB           (lower = better; radio sensitivity)
  s11_db:   {max: -10}        # input match, dB            (<= -10 is well matched)
  s21_db:   {min: 12}         # gain, dB                   (higher = more amplification)
  idd_ma:   {max: 5}          # supply current, mA         (lower = less power)
  iip3_dbm: {min: -5, status: unsupported}   # linearity -- keep 'unsupported' (no in-loop harness)

objectives:                   # SOFT goals: improved only after the design is already feasible
  - {metric: s21_db, direction: max, weight: 1.0}
  - {metric: idd_ma, direction: min, weight: 0.5}
  - {metric: nf_db,  direction: min, weight: 0.5}

topology:
  differential: false
  reject_floating: true       # drop circuits with disconnected islands
  device_budget: [3, 20]      # min / max number of devices allowed
  max_inductors: 3
  l_min: 0.3e-9               # inductor value range (H). Raise l_max for sub-GHz bands.
  l_max: 12e-9
  allow_inductorless: false   # set true for wideband / resistive-feedback designs

sizing:                       # the ranges the sizer is allowed to choose within
  w_um: [1, 200]              # transistor width (um)
  l_fixed: 45e-9              # channel length (m) -- fixed at 45 nm on this process
  r_ohm: [50, 20e3]           # resistor range (ohms)
  c_f: [50e-15, 10e-12]       # capacitor range (F)
  vb_v: [0.2, 0.9]            # bias voltage range (V)
```

**For a wideband spec** change three things: `type: wideband`; gate `s11_max_db` (worst
match across the band) instead of `s11_db`; and set `allow_inductorless: true`. You may
also add `s21_ripple_db: {max: 2}` (flatness of gain across the band).

**Check your spec is valid** before running:

```bash
python lna/spec.py myradio
```

It prints a summary if the file is good, or the exact error if not.

---

## Step 2 — Solve it (get a design)

```bash
python lna/solve_spec.py myradio
```

This generates candidate topologies, inserts biasing, and sizes each one with a black-box
optimizer (CMA-ES driving ngspice) until it meets your spec. It prints whether it found a
**FEASIBLE** design and saves the best one under `designs/myradio/`.

Useful options:

| option | what it does |
|---|---|
| `--corpus` | skip generation; size a few known-good topologies. **Fastest** (~1 min). |
| `--topology <wl_hash>` | size one specific stored topology. |
| `--pool 96` | generate more candidates (default 64). More = slower but better coverage. |
| `--seeds 5` | more optimizer restarts per topology (default 3). |
| `--budget 500` | more ngspice evaluations per sizing (default 300). |

Notes:
- The default (generation) path takes ~2–4 minutes on this CPU box; `--corpus` is much
  faster and a good first try.
- If nothing meets the spec, it still saves the **closest attempt** so you can see which
  metric failed and by how much — then loosen that constraint, raise `--pool`/`--budget`,
  or try `--corpus`.

---

## Step 3 — View the design

The solve step prints the exact command. It looks like:

```bash
python lna/render_design.py --design designs/myradio/design
```

You get a human-readable report with three parts:

- **TOPOLOGY** — every device and what each pin connects to (`VIN1` = input, `VOUT1` =
  output, `0` = ground, `VDD` = supply, `iN` = internal nodes).
- **SIZING** — each device's value in normal units (µm, nm, Ω, F, H).
- **SPECS ACHIEVED** — each metric: what it hit, the limit, the margin, and PASS/FAIL.

Add `--deck` to also print the actual SPICE netlist:

```bash
python lna/render_design.py --design designs/myradio/design --deck
```

---

## A complete worked example (copy-paste)

```bash
source env.sh

# 1) write a spec
cat > lna/specs/demo24.yaml <<'YAML'
name: demo24
description: 2.4 GHz demo LNA
process: {models: AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt, vdd: 1.1, temp: 27}
band: {type: narrowband, f0: 2.442e9, f_lo: 2.40e9, f_hi: 2.4835e9}
ports: {z0: 50, input: VIN1, output: VOUT1}
constraints:
  nf_db:    {max: 3.0}
  s11_db:   {max: -10}
  s21_db:   {min: 12}
  idd_ma:   {max: 8}
  iip3_dbm: {min: -5, status: unsupported}
objectives:
  - {metric: s21_db, direction: max, weight: 1.0}
  - {metric: idd_ma, direction: min, weight: 0.5}
  - {metric: nf_db,  direction: min, weight: 0.5}
topology: {differential: false, reject_floating: true, device_budget: [3, 20], max_inductors: 3, l_min: 0.3e-9, l_max: 12e-9, allow_inductorless: false}
sizing: {w_um: [1, 200], l_fixed: 45e-9, r_ohm: [50, 20e3], c_f: [50e-15, 10e-12], vb_v: [0.2, 0.9]}
YAML

# 2) check + solve (use --corpus for a fast first result)
python lna/spec.py demo24
python lna/solve_spec.py demo24 --corpus

# 3) view whatever it saved
python lna/render_design.py --design designs/demo24/design
```

---

## Troubleshooting

- **`ModuleNotFoundError` / `ngspice not found`** — you forgot `source env.sh` in this
  terminal.
- **"infeasible — closest attempt saved"** — no circuit met every gate. Read the render's
  FAIL rows, loosen that constraint, or try `--corpus`, `--pool 96`, `--budget 500`.
- **Very slow** — the default generates topologies on CPU. Use `--corpus` to skip that.
- **Sub-GHz band won't match** — raise `l_max` in the spec (e.g. `30e-9`); low frequencies
  need bigger inductors.
- **Linearity (`iip3_dbm`)** — leave it `unsupported`. The two-tone harness exists but is
  not wired into the sizing loop, so gating it would just fail everything.

## What each tool is

| file | role |
|---|---|
| `lna/specs/<name>.yaml` | your spec — the single source of truth for the target |
| `python lna/spec.py <name>` | validate a spec |
| `python lna/solve_spec.py <name>` | spec → sized design (generate + size + verify) |
| `python lna/render_design.py --design <dir>` | view a design (topology + sizing + specs) |
| `designs/<name>/` | where your solved designs are saved (git-ignored) |

## Under the hood (optional)

The flow is `generate (an 11.8M-param GPT) → structural screen → bias insertion → CMA-ES
sizing → ngspice verify`. The sizer is deterministic per seed, so a feasible result
reproduces exactly. For the "what was built and what it can do" story, see
[`V0-RETROSPECTIVE.md`](V0-RETROSPECTIVE.md); for the verification tests and more example
designs, see [`capacity_tests/README.md`](capacity_tests/README.md).
