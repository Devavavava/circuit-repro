# WP-HB — harmonic-balance IIP3 harness (VACASK)

The linearity harness for **Gate D5**. Measures IIP3 of the designated
Gate-D4-SIM design by true **two-tone harmonic balance** — a frequency-domain
steady-state solve for the complex phasor at every intermodulation line — in
[VACASK](https://codeberg.org/arpadbuermen/VACASK), an open-source circuit
simulator with an HB engine that ngspice does not have.

This is upgrade **#4** of `lna/plans2/14-DHRUVA-SIMUL.md` §4, taken in its
"proper IIP3 harness" half only. **The IHP SG13G2 PDK migration — the other
half of that upgrade — was deliberately NOT started** (user decision,
2026-08-13): this harness targets the program's *existing* 45 nm behavioral
BSIM4 models so every number stays comparable with everything measured so
far.

## Install

| | |
|---|---|
| version | `vacask 0.3.4.rc1`, Windows x86_64 prebuilt |
| location | `C:\Users\Devavrat\tools\vacask_0.3.4.rc1\vacask_0.3.4.rc1_windows-x86_64` |
| binary | `bin\vacask.exe` (`bin\openvaf-r.exe` compiles Verilog-A to OSDI) |
| raw reader | `lib\python\rawfile.py` (shipped; used as-is, unmodified) |
| MOS model | `lib\mod\spice\bsim4v8.osdi` — the shipped SPICE-compatible BSIM4.8 |
| docs | `doc\docs\*.md` (`cmd-analysis-hb.md`, `python-rawfile.md`, `dev-spice.md`) |

Override the location with `VACASK_HOME`. Nothing is installed into the repo;
no PDK is vendored.

**`.vacaskrc.toml` gotcha (written automatically by the harness).** Compiling
embedded Verilog-A needs a linker. There is no MSVC linker on this machine and
the `link` on `PATH` is GNU coreutils' `link`, which openvaf silently picks up
and fails on. The harness writes

```toml
[Binaries]
openvaf_args = [ "--target", "x86_64-pc-windows-gnu" ]
```

into every working directory so openvaf targets the MSYS2 GNU toolchain.
Only the golden needs this (the design decks use the prebuilt `.osdi`
models), but it is written for both.

## Files

| file | role |
|---|---|
| `lna/ref/check_hb.py` | **the golden** — closed-form validation of HB + the IIP3 extraction. Run first; it must print `GREEN`. |
| `lna/hb/port45.py` | ngspice `.sp` deck → VACASK netlist, for exactly the grammar `lna/to_spice.py` emits |
| `lna/hb/hb_iip3.py` | the driver: `--op`, `--gain`, `--iip3`, `--fence` |
| `lna/hb/hb_iip3_d4sim.json` | measured results for the designated D4-SIM point |

## Golden (`lna/ref/check_hb.py`)

Four checks, all closed-form — no BSIM anywhere:

- **G0 — negative control on the solver tolerance.** The same circuit at
  VACASK's *default* reltol must **fail** to resolve the IM3 line. It does:
  the IM3 phasor comes back `6.0e-16` instead of `9.375e-5` (Newton residual
  noise) and IIP3 reads **+133.18 dBm instead of +21.25 dBm, a +111.9 dB
  error**. This is why `options reltol=1e-6` is in every deck, and G0 is
  what stops that line from being deleted as cargo cult by a later reader.
- **G1 — memoryless cubic transconductor**, `i = -(a1·v + a3·v³)`,
  `a1 = 10, a3 = -1` into 1 Ω. Analytic `A_IP3 = sqrt(4/3·|a1/a3|) = 3.65148 V`
  → **+21.2494 dBm** in the program's dBm-at-50-Ω convention. VACASK
  reproduces the closed form to 6 significant figures (fundamental
  `0.499719` vs `a1A + (9/4)a3A³`; IM3 `9.375e-5` vs `(3/4)|a3|A³`); extracted
  IIP3 error **−0.002 / −0.010 / −0.039 dB** at A = 0.05 / 0.1 / 0.2 V, IM3
  slope **3.0000**. Also pins the phasor convention: HB phasors are **peak**
  amplitudes (convention factor 0.9994).
- **G2 (×2) — cross-method reference.** The *exact* closed-form references the
  sibling ngspice two-tone transient golden uses (`lna/ref/check_iip3.py`):
  voltage-form `y = a1x + a3x³` behind the same Thevenin-50 Ω/50 Ω port
  network, the same `(a1,a3)` pairs `(10,−200)` and `(4,−50)`, the same
  available-power sweeps. Max |error| **0.200 / 0.198 dB** against that
  harness's own 0.25 dB bar, slope 3.000, gain error −0.039 dB. The residual
  is physical compression from the `(9/4)a3A³` term, not numerics — it is
  shared by both methods, which is the point: the two harnesses are now
  anchored to identical ground.

```bash
python lna/ref/check_hb.py        # ~30 s, must print "check_hb: GREEN"
```

## Conventions (identical to `lna/iip3.py`, by construction)

```
P_in   = available power per tone from a 50-Ω source = A_emf² / (8·50)
P_out  = peak² / (2·50) at the 50-Ω load
P_im3  = the WORSE of the two IM3 sidebands (2f1−f2, 2f2−f1)
IIP3   = P_in + (P_fund − P_im3)/2,  median over uncompressed points
```
"Uncompressed" = gain within 0.5 dB of the small-signal value; the IM3-vs-Pin
slope over the retained points must be 3:1. Default tone spacing **2 MHz**
= the sibling harness's `DF`, so the two are directly comparable.

The S-parameter ports of the shipped deck become a *physical* testbench:
port 1 → series EMF stack + 50 Ω into the deck's DC-block cap; port 2 → the
deck's DC-block cap into a 50 Ω load. For a 2-port in a Z0 system
`S21 = 2·V(p2)/V_emf` exactly, which is what `--gain` checks.
ngspice's `.option rshunt=1e12` becomes explicit 1 TΩ resistors on every node
— load-bearing, not hygiene: six gates in this design have no other DC path.

## Model compatibility — measured, not assumed

`--op` and `--gain` run **live ngspice** on the same shipped deck and compare.
Note the two simulators do not even run the same BSIM4: ngspice reports
`BSIM 4.5`, and VACASK's OSDI model warns `unknown BSIM4 version, working now
with BSIM4.8.3` (the card's `version=4.0` is not honored). They agree anyway:

| quantity | VACASK | ngspice | delta |
|---|---|---|---|
| Idd | 12.96322 mA | 12.96318 mA | **+36 nA (+0.0003%)** |
| DC solution, 19 nodes | — | — | **worst 2.05 µV** (at `n7`) |
| S21 @ 1176.45 MHz | 35.9608 dB | 35.9610 dB | −0.0002 dB |
| S21 @ 1227.60 MHz | 35.9307 dB | 35.9310 dB | −0.0003 dB |
| S21 @ 1575.42 MHz | 35.5346 dB | 35.5349 dB | −0.0003 dB |
| S21 @ 2492.03 MHz | 33.7267 dB | 33.7269 dB | −0.0002 dB |

## Numerical fences (`--fence`)

Measured on the designated point, Pin = −70 dBm/tone:

- **reltol** 1e-4 … 1e-9: IIP3 constant to **0.000 dB** (the guard matters at
  the golden's much smaller IM3, not here — G0 is where it bites).
- **nharm = immax** 4 … 8: constant to **≤0.001 dB**, on every band. This is
  what licenses the `NHARM_LADDER` workaround below.
- **tone spacing**: a real but mild memory effect, monotone in spacing —
  **0.43 dB** total from 1 → 10 MHz. The reported 2 MHz setting is near the
  pessimistic end, and it is the sibling harness's spacing.

  | band | 1 MHz | **2 MHz** | 5 MHz | 10 MHz |
  |---|---|---|---|---|
  | dhruva-l5 | −33.074 | **−32.780** | −32.665 | −32.641 |
  | dhruva-l2 | −33.014 | **−32.716** | −32.601 | −32.577 |
  | dhruva-l1 | −32.531 | **−32.160** | −32.044 | −32.021 |
  | dhruva-s  | −30.683 | **−30.301** | −30.145 | −30.115 |

- Upper and lower IM3 sidebands agree to **0.02 dB** at 10 MHz spacing,
  0.15 dB at 1 MHz.

## Known VACASK edge case (worked around, recorded)

VACASK 0.3.4.rc1 **aborts** on a few specific *(f0, tone spacing, nharm)*
spectrum combinations — e.g. `dhruva-l2` (1227.6 MHz) at 2 MHz spacing with
`nharm=4` or `5`. It is a **spectrum-construction** failure, not a
convergence one: it reproduces identically at every drive level *including
zero amplitude*, and clears at `nharm=3, 6, 7, 8`. The abort surfaces only as

```
terminate called after throwing an instance of 'std::filesystem::filesystem_error'
  what(): cannot remove: The process cannot access the file because it is
          being used by another process [hb1.raw]
```

with **empty stdout** and a **zero-length** `hb1.raw` — VACASK unlinking its
own still-open output file on an error path, which destroys the real message.
Do not read that text as a file-locking problem; it is a masked crash.

`two_tone()` therefore walks `NHARM_LADDER = (5, 6, 7)` and records the
`nharm` each row actually used. This is safe **because it provably does not
move the answer**: the fence above shows IIP3 constant to ≤0.001 dB over
nharm 4…8. Each VACASK invocation also gets its own private working directory
(the repo's `moves.private_tmp()` convention) with a short retry, since
VACASK removes a pre-existing `<analysis>.raw` before writing.

## Results (FINDINGS §40)

**Gate D5 FAILS on all four bands.** Designated D4-SIM point (`dhruva-l5`
sizing of `ace8383c`), one fixed sizing, 8 drive levels per band, 2 MHz
spacing — `hb_iip3_d4sim.json`:

| band | f0 (MHz) | IIP3 (dBm) | target | margin | OIP3 | gain |
|---|---|---|---|---|---|---|
| dhruva-l5 | 1176.45 | **−32.76** | ≥ −7.4 | **−25.36** | +3.20 | 35.96 |
| dhruva-l2 | 1227.60 | **−32.70** | ≥ −7.4 | **−25.30** | +3.23 | 35.93 |
| dhruva-l1 | 1575.42 | **−32.14** | ≥ −7.6 | **−24.54** | +3.39 | 35.53 |
| dhruva-s  | 2492.03 | **−30.28** | ≥ −8.7 | **−21.58** | +3.44 | 33.73 |

IM3 slope 2.96–2.97 over 6 uncompressed points, spread ≤0.43 dB, and a second
full run reproduces every digit. OIP3 is flat to 0.24 dB across bands while
gain varies 2.2 dB — linearity is set by the output stage's swing budget, so
even granting the full ≥10.6 dB programmability range at unchanged OIP3 leaves
the design ~14.8 dB short. See §40.4.

**Cross-method agreement (`--own`, `hb_iip3_ownsizing.json`).** The sibling
ngspice two-tone *transient* harness (`lna/iip3.py`) measures each band on its
**own** per-band deck; on those same four decks:

| band | transient (ngspice, FFT) | HB (VACASK) | delta |
|---|---|---|---|
| dhruva-l1 | −33.31 | **−33.31** | 0.00 |
| dhruva-l2 | −31.58 | **−31.58** | 0.01 |
| dhruva-l5 | −32.78 | **−32.76** | 0.02 |
| dhruva-s  | −34.03 | **−33.99** | 0.04 |

Two simulators, two BSIM4 implementations, two entirely different numerical
methods, worst disagreement **0.04 dB**.

## Repro

```bash
python lna/ref/check_hb.py                        # golden — GREEN first
python lna/hb/hb_iip3.py --op                     # Idd + DC vs live ngspice
python lna/hb/hb_iip3.py --gain                   # HB gain vs live ngspice S21
python lna/hb/hb_iip3.py --iip3 --json out.json   # the D5 number, 4 bands
python lna/hb/hb_iip3.py --iip3 --own             # each band on its OWN
                                                  #   per-band deck (what the
                                                  #   sibling transient harness
                                                  #   measures) — method x-check
python lna/hb/hb_iip3.py --fence                  # convergence fences
```

`--iip3` without `--own` measures the **one fixed `dhruva-l5` sizing** at all
four band f0s — the Gate-D4-SIM designated point, which is the claim under
test.
