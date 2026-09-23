# gf180mcu + ngspice: run-to-run DC variation demo

## TL;DR

A single gf180 transistor's DC operating point changes on **every ngspice run**
with byte-identical input. The cause is **not an ngspice bug** — the gf180
statistical models default to **Monte-Carlo process/mismatch variation ON**
(`sw_stat_global=1`, `sw_stat_mismatch=1`, set in `design.ngspice`), so each run
draws fresh random Vth/mismatch samples. Turning the switches off (or fixing the
RNG seed) makes it fully deterministic.

**Do not file this as an ngspice bug** — it is intended model behaviour and
ngspice honours a seed correctly (see below).

## What the demo shows

`run_demo.sh` runs the same 1-transistor `.op` deck N times in three configs:

| Config | Deck line | Result |
|---|---|---|
| **MC ON** (default) | *(nothing — gf180 default)* | DC current **differs every run** (~2–3% spread) |
| **MC OFF** | `.param sw_stat_global=0 sw_stat_mismatch=0` | **identical every run** (typical corner) |
| **MC ON + seed** | `.option seed=12345` | **identical every run** (reproducible random corner) |

It prints each run's drain current, the distinct-value count / spread, and a small
ASCII strip plot ("window") so you can *see* the MC-ON points scatter while MC-OFF
and seeded collapse to a single column.

## Why it matters here

Our sizing pipeline included `design.ngspice` (MC on) and never disabled it, so
**every SPICE evaluation ran at a random process corner**. The CMA-ES objective was
therefore noisy, which is what produced the run-to-run margin swings and made
feasibility behave like a rate rather than a verdict.

**Fix for deterministic sizing:** add `.param sw_stat_global=0 sw_stat_mismatch=0`
(typical corner) to the generated decks. If reproducible *variation* is ever wanted
instead (e.g. a fixed non-typical corner), use `.option seed=<N>`.

## Gotcha: which seed knob works

- `.option seed=<N>` (deck body) — **works** (parsed before model setup).
- `set rndseed=<N>` / `setseed <N>` (in `.control`) — **do NOT** make it
  reproducible here (applied too late for the model-parameter agauss draws).

## Prerequisites

- **ngspice** — any recent build (developed against **ngspice-47**).
  Set `$NGSPICE` to the binary, or have `ngspice` on `$PATH`.
- **gf180mcu PDK ngspice models** — the open-source (Apache-2.0) model dir that
  contains `design.ngspice` + `sm141064.ngspice`.
  Set `$GF180_MODELS` to that directory.
  Source: https://github.com/google/gf180mcu-pdk

## Usage

```bash
export NGSPICE=/path/to/ngspice           # or ensure ngspice is on PATH
export GF180_MODELS=/path/to/gf180mcu/models/ngspice
./run_demo.sh 12                           # 12 runs per config (default 12)
```

## Sample output (ngspice-47, this machine)

```
===== MC ON  (gf180 default: sw_stat_global=1, sw_stat_mismatch=1) =====
  distinct values: 12/12   min=6.109236e-04  max=6.272010e-04  spread=2.629%
  ... (points scatter across the ASCII axis) ...

===== MC OFF (sw_stat_global=0, sw_stat_mismatch=0) =====
  distinct values: 1/12    min=6.196781e-04  max=6.196781e-04  spread=0.000%
  ... (all points in one column) ...

===== MC ON + .option seed=12345 (reproducible corner) =====
  distinct values: 1/10    spread=0.000%
```
