# era-fixed-0b4b497e: requirement vs achieved, per spec (arm-A nulls)

Post-fix reruns (inductors sized, per-PDK gate bias). "X" = gate missed.

## sky130 (arma-sky130 + resume-tail = full 24) — 0/24 feasible

| spec | NF req/got (dB) | S21 req/got (dB) | S11 req/got (dB) | Idd req/got (mA) | feasible |
|---|---|---|---|---|---|
| cap-e01-wifi | 3.5 / 20.0 **X** | 10 / -14.0 **X** | -8 / -0.1 **X** | 15 / 1.2 | no |
| cap-e02-gpsband | 3.5 / 19.8 **X** | 10 / -13.8 **X** | -8 / -0.1 **X** | 15 / 1.1 | no |
| cap-e03-900mhz | 3.5 / 20.1 **X** | 10 / -13.8 **X** | -8 / -0.1 **X** | 15 / 1.0 | no |
| cap-e04-35ghz | 3.5 / 19.8 **X** | 12 / -13.8 **X** | -8 / -0.1 **X** | 15 / 1.0 | no |
| cap-e05-ism58 | 3.5 / 11.0 **X** | 10 / -2.9 **X** | -8 / -4.4 **X** | 15 / 1.0 | no |
| cap-e06-wifi | 3 / 19.8 **X** | 12 / -13.8 **X** | -10 / -0.0 **X** | 12 / 1.0 | no |
| cap-e07-gpsband | 3 / 20.1 **X** | 12 / -13.9 **X** | -10 / -0.1 **X** | 10 / 1.2 | no |
| cap-e08-wideband | 3.5 / 20.2 **X** | 10 / -14.1 **X** | n/a | 15 / 1.1 | no |
| cap-h01-wifi | 1.8 / 19.9 **X** | 16 / -13.9 **X** | -13 / -0.1 **X** | 4 / 1.2 | no |
| cap-h02-gpsband | 1.8 / 20.1 **X** | 16 / -14.0 **X** | -12 / -0.1 **X** | 3 / 1.1 | no |
| cap-h03-900mhz | 1.6 / 20.2 **X** | 17 / -13.9 **X** | -13 / -0.1 **X** | 4 / 1.1 | no |
| cap-h04-35ghz | 1.8 / 19.7 **X** | 17 / -13.8 **X** | -14 / -0.1 **X** | 4 / 1.1 | no |
| cap-h05-ism58 | 2 / 19.7 **X** | 16 / -13.8 **X** | -13 / -0.1 **X** | 5 / 1.2 | no |
| cap-h06-wifi | 1.5 / 19.8 **X** | 18 / -13.7 **X** | -15 / -0.0 **X** | 5 / 1.2 | no |
| cap-h07-gpsband | 1.5 / 19.8 **X** | 20 / -13.8 **X** | -14 / -0.1 **X** | 3 / 1.3 | no |
| cap-h08-wideband | 2.5 / 20.0 **X** | 16 / -13.9 **X** | n/a | 5 / 1.2 | no |
| cap-m01-wifi | 2.5 / 20.0 **X** | 12 / -13.9 **X** | -10 / -0.0 **X** | 5 / 1.2 | no |
| cap-m02-gpsband | 2.2 / 20.1 **X** | 14 / -13.9 **X** | -10 / -0.1 **X** | 5 / 1.2 | no |
| cap-m03-900mhz | 2.5 / 20.1 **X** | 14 / -13.8 **X** | -10 / -0.1 **X** | 6 / 1.0 | no |
| cap-m04-35ghz | 2.8 / 19.7 **X** | 14 / -13.6 **X** | -11 / -0.0 **X** | 6 / 1.1 | no |
| cap-m05-ism58 | 3.5 / 19.7 **X** | 12 / -13.9 **X** | -10 / -0.1 **X** | 10 / 1.1 | no |
| cap-m06-wifi | 2.2 / 20.0 **X** | 15 / -14.0 **X** | -12 / -0.1 **X** | 6 / 1.3 | no |
| cap-m07-gpsband | 2 / 20.1 **X** | 15 / -14.0 **X** | -12 / -0.1 **X** | 4 / 1.1 | no |
| cap-m08-ism58 | 3 / 19.6 **X** | 14 / -13.8 **X** | -11 / -0.1 **X** | 8 / 1.2 | no |

## gf180mcu — 0/24 feasible

| spec | NF req/got (dB) | S21 req/got (dB) | S11 req/got (dB) | Idd req/got (mA) | feasible |
|---|---|---|---|---|---|
| cap-e01-wifi | 3.5 / 6.9 **X** | 10 / -1.7 **X** | -8 / -0.2 **X** | 15 / 14.3 | no |
| cap-e02-gpsband | 3.5 / 6.9 **X** | 10 / -1.5 **X** | -8 / -0.1 **X** | 15 / 15.0 **X** | no |
| cap-e03-900mhz | 3.5 / 7.2 **X** | 10 / -1.6 **X** | -8 / -0.0 **X** | 15 / 14.5 | no |
| cap-e04-35ghz | 3.5 / 7.0 **X** | 12 / -1.8 **X** | -8 / -0.4 **X** | 15 / 15.0 | no |
| cap-e05-ism58 | 3.5 / 7.4 **X** | 10 / -2.4 **X** | -8 / -1.0 **X** | 15 / 14.7 | no |
| cap-e06-wifi | 3 / 6.9 **X** | 12 / -1.6 **X** | -10 / -0.2 **X** | 12 / 12.0 | no |
| cap-e07-gpsband | 3 / 7.0 **X** | 12 / -1.6 **X** | -10 / -0.1 **X** | 10 / 10.0 | no |
| cap-e08-wideband | 3.5 / 6.9 **X** | 10 / -1.5 **X** | n/a | 15 / 14.8 | no |
| cap-h01-wifi | 1.8 / 7.8 **X** | 16 / -2.6 **X** | -13 / -0.3 **X** | 4 / 4.0 **X** | no |
| cap-h02-gpsband | 1.8 / 8.1 **X** | 16 / -2.9 **X** | -12 / -0.1 **X** | 3 / 3.0 **X** | no |
| cap-h03-900mhz | 1.6 / 7.9 **X** | 17 / -2.6 **X** | -13 / -0.0 **X** | 4 / 4.1 **X** | no |
| cap-h04-35ghz | 1.8 / 7.9 **X** | 17 / -2.7 **X** | -14 / -0.4 **X** | 4 / 4.0 **X** | no |
| cap-h05-ism58 | 2 / 8.1 **X** | 16 / -3.0 **X** | -13 / -0.9 **X** | 5 / 5.1 **X** | no |
| cap-h06-wifi | 1.5 / 7.5 **X** | 18 / -2.3 **X** | -15 / -0.2 **X** | 5 / 5.0 **X** | no |
| cap-h07-gpsband | 1.5 / 8.0 **X** | 20 / -2.8 **X** | -14 / -0.1 **X** | 3 / 3.2 **X** | no |
| cap-h08-wideband | 2.5 / 7.5 **X** | 16 / -2.3 **X** | n/a | 5 / 5.0 **X** | no |
| cap-m01-wifi | 2.5 / 7.5 **X** | 12 / -2.3 **X** | -10 / -0.2 **X** | 5 / 5.0 **X** | no |
| cap-m02-gpsband | 2.2 / 7.5 **X** | 14 / -2.2 **X** | -10 / -0.1 **X** | 5 / 5.0 **X** | no |
| cap-m03-900mhz | 2.5 / 7.6 **X** | 14 / -2.1 **X** | -10 / -0.0 **X** | 6 / 6.0 | no |
| cap-m04-35ghz | 2.8 / 7.4 **X** | 14 / -2.2 **X** | -11 / -0.4 **X** | 6 / 5.9 | no |
| cap-m05-ism58 | 3.5 / 7.5 **X** | 12 / -2.4 **X** | -10 / -0.9 **X** | 10 / 10.0 **X** | no |
| cap-m06-wifi | 2.2 / 7.4 **X** | 15 / -2.1 **X** | -12 / -0.2 **X** | 6 / 6.0 **X** | no |
| cap-m07-gpsband | 2 / 7.7 **X** | 15 / -2.4 **X** | -12 / -0.1 **X** | 4 / 4.1 **X** | no |
| cap-m08-ism58 | 3 / 7.7 **X** | 14 / -2.7 **X** | -11 / -0.9 **X** | 8 / 7.8 | no |

## ihp_sg13g2 — 23/24 feasible

| spec | NF req/got (dB) | S21 req/got (dB) | S11 req/got (dB) | Idd req/got (mA) | feasible |
|---|---|---|---|---|---|
| cap-e01-wifi | 3.5 / 1.7 | 10 / 26.0 | -8 / -14.3 | 15 / 2.7 | YES |
| cap-e02-gpsband | 3.5 / 2.2 | 10 / 23.9 | -8 / -12.7 | 15 / 2.5 | YES |
| cap-e03-900mhz | 3.5 / 3.2 | 10 / 27.4 | -8 / -21.8 | 15 / 3.2 | YES |
| cap-e04-35ghz | 3.5 / 1.1 | 12 / 32.3 | -8 / -14.4 | 15 / 2.8 | YES |
| cap-e05-ism58 | 3.5 / 1.5 | 10 / 27.4 | -8 / -22.6 | 15 / 4.7 | YES |
| cap-e06-wifi | 3 / 1.3 | 12 / 26.0 | -10 / -10.8 | 12 / 2.8 | YES |
| cap-e07-gpsband | 3 / 1.9 | 12 / 21.6 | -10 / -17.9 | 10 / 3.8 | YES |
| cap-e08-wideband | 3.5 / 2.0 | 10 / 15.8 | n/a | 15 / 4.4 | YES |
| cap-h01-wifi | 1.8 / 1.1 | 16 / 29.4 | -13 / -16.1 | 4 / 2.8 | YES |
| cap-h02-gpsband | 1.8 / 1.4 | 16 / 26.1 | -12 / -12.6 | 3 / 2.4 | YES |
| cap-h03-900mhz | 1.6 / 1.5 | 17 / 26.0 | -13 / -14.5 | 4 / 2.8 | YES |
| cap-h04-35ghz | 1.8 / 1.2 | 17 / 23.7 | -14 / -21.1 | 4 / 1.9 | YES |
| cap-h05-ism58 | 2 / 1.2 | 16 / 25.2 | -13 / -28.8 | 5 / 2.1 | YES |
| cap-h06-wifi | 1.5 / 1.2 | 18 / 31.3 | -15 / -15.8 | 5 / 3.8 | YES |
| cap-h07-gpsband | 1.5 / 1.5 | 20 / 24.0 | -14 / -14.1 | 3 / 2.5 | YES |
| cap-h08-wideband | 2.5 / 3.0 **X** | 16 / 12.4 **X** | n/a | 5 / 4.6 | no |
| cap-m01-wifi | 2.5 / 1.5 | 12 / 23.9 | -10 / -16.1 | 5 / 4.2 | YES |
| cap-m02-gpsband | 2.2 / 2.2 | 14 / 17.3 | -10 / -10.7 | 5 / 2.3 | YES |
| cap-m03-900mhz | 2.5 / 2.3 | 14 / 19.6 | -10 / -11.8 | 6 / 4.2 | YES |
| cap-m04-35ghz | 2.8 / 1.9 | 14 / 23.8 | -11 / -12.9 | 6 / 3.5 | YES |
| cap-m05-ism58 | 3.5 / 1.7 | 12 / 25.9 | -10 / -17.0 | 10 / 4.3 | YES |
| cap-m06-wifi | 2.2 / 1.5 | 15 / 33.5 | -12 / -13.2 | 6 / 2.7 | YES |
| cap-m07-gpsband | 2 / 1.4 | 15 / 30.2 | -12 / -14.9 | 4 / 3.7 | YES |
| cap-m08-ism58 | 3 / 1.7 | 14 / 27.5 | -11 / -15.2 | 8 / 5.1 | YES |

## Reading (2026-08-29)

Three different verdicts, one per process:

- **ihp_sg13g2 23/24** -- beats the bptm45 null itself (20/24). Only
  cap-h08-wideband stands (NF 3.0 vs 2.5, S21 12.4 vs 16): the same
  multi-path-feedback wideband wall as on bptm45. Transfer SUCCESS.
- **gf180mcu 0/24 but ALIVE**: designs ride the Idd cap exactly (4.0/4,
  5.0/5, 15/15), NF ~7-8 dB vs gates 1.5-3.5, S21 ~ -2 dB vs gates 10-20.
  Conducting, current-saturated, cannot buy gain at these budgets: consistent
  with 180 nm 3.3 V physics and/or 45nm-bred corpus topologies being wrong for
  this process. THIS is where an arm-B (LLM proposing gf180-native topologies)
  comparison is now meaningful.
- **sky130 0/24 STILL SETUP-LIMITED**: uniform starved signature (Idd ~1.1 mA
  on every spec regardless of budget, NF ~20, S21 ~ -14) and a directly
  measured ~2/3 ngspice-failure rate at random sizing points (8/12 fail;
  gf180: 0/12; funnel golden: fails=48/50). The sizer is starved by sim
  failures -- suspect the sky130 fd_pr subcircuit W/L binning rejecting most
  of the W box. A sky130-specific bring-up fix (own pre-reg) before any
  capability claim about that process.

Provenance notes: arma-sky130 here stopped at 14/24 (wall budget, shared with
a concurrent leftover process -- see below); arma-sky130-resume-tail carries
the other 10 specs, run with the SAME fixed code (process started ~18:52,
merge 0b4b497e landed 18:49; ts-verified) by a leftover gated resume job from
the prior session that wrote into the old buggy-era output dir. Together they
cover the full 24-spec ladder on fixed code. The buggy-era arma-sky130
archive (14 rows) predates that write and is uncontaminated.
