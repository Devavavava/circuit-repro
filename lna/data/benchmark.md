# Cross-spec feasibility benchmark

6 candidate topologies (feasible + closest near-feasible), sized against each spec (curated on wifi24, all-free multi-seed else).

> **★★ WP-DHRUVA Gate D0 (2026-08-08, blind protocol — plans2/08-DHRUVA-GOAL.md):**
> the scoreboard now carries the four paper-target tier-1 rows
> `dhruva-{l5,l2,l1,s}` (S21 22.3 / 22.3 / 25.4 / 30 dB at f0; **S11 ≤ −10 dB held
> over 1.1–2.5 GHz**; Idd ≤ 13 mA). **Result: 0/6 on every dhruva band**, binding
> almost entirely on **`s11_max`** (worst-case S11 over the band) — the current
> single-stage candidates match at *no* frequency across 1.1–2.5 GHz. The sharpest
> point: `seq0046` reaches **S21 23.7 dB on dhruva-l1** and 24.1 on dhruva-s (near
> the gain targets) yet its f0 S11 is ≈ −0.5 — **gain alone gets close; the
> broadband match is the wall**, exactly the hard match+gain pair 08 §5 flags. This
> is the blind baseline; closing it is a generator job (WP-D2 → Gate D1).
>
> **Read caveats:** (1) this run used a *lean* budget (`seeds=1, budget=5,5,1`) to
> produce the D0 rows quickly — **wifi24 shows 4/6 here vs 6/6 at full budget**
> (a budget artifact; wifi24 remains the solved class). The dhruva 0/6 verdict is
> budget-robust (candidates are far off). (2) The **S11** detail column is the f0
> value; feasibility gates on **`s11_max`** (the worst point over the band), which
> is why an f0-matched cell can still bind `s11_max`. (3) NF is advisory (gated off,
> port-noise harness gap); dhruva NF is tier-2 (WP-D1).

## Per-spec yield (feasible / total)

- **wifi24**: 4/6 feasible; binding when not: {'s21': 2}
- **gps-l1**: 0/6 feasible; binding when not: {'s11': 4, 's21': 2}
- **wideband-sdr**: 0/6 feasible; binding when not: {'s11': 4, 's21': 2}
- **dhruva-l5**: 0/6 feasible; binding when not: {'s11_max': 5, 's21': 1}
- **dhruva-l2**: 0/6 feasible; binding when not: {'s11_max': 6}
- **dhruva-l1**: 0/6 feasible; binding when not: {'s11_max': 6}
- **dhruva-s**: 0/6 feasible; binding when not: {'s11_max': 4, 's21': 2}

## Matrix (F = feasible, else binding constraint)

| candidate | dev | wifi24 | gps-l1 | wideband-sdr | dhruva-l5 | dhruva-l2 | dhruva-l1 | dhruva-s |
|---|---|---|---|---|---|---|---|---|
| seq0240.txt | 8 | **F** | s11 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0009.txt | 10 | **F** | s21 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0220.txt | 9 | **F** | s21 | s21 | s21 | s11_max | s11_max | s21 |
| seq0079.txt | 10 | s21 | s11 | s11 | s11_max | s11_max | s11_max | s21 |
| seq0086.txt | 10 | **F** | s11 | s11 | s11_max | s11_max | s11_max | s11_max |
| seq0046.txt | 12 | s21 | s11 | s21 | s11_max | s11_max | s11_max | s11_max |

## Detail (best sized metrics per cell)

| candidate | spec | feas | S11 | S21 | Idd | NF | binding |
|---|---|---|---|---|---|---|---|
| seq0240.txt | wifi24 | yes | -10.0 | 13.4 | 1.74 | -0.4 | - |
| seq0240.txt | gps-l1 | no | -0.5 | 8.5 | 0.47 | 6.5 | s11 |
| seq0240.txt | wideband-sdr | no | -0.0 | 7.2 | 2.01 | 11.0 | s11 |
| seq0240.txt | dhruva-l5 | no | -0.6 | 8.3 | 0.66 | 7.7 | s11_max |
| seq0240.txt | dhruva-l2 | no | -0.7 | 8.8 | 0.7 | 7.4 | s11_max |
| seq0240.txt | dhruva-l1 | no | -0.3 | 12.3 | 2.82 | 5.1 | s11_max |
| seq0240.txt | dhruva-s | no | -4.8 | 14.8 | 0.91 | -0.7 | s11_max |
| seq0009.txt | wifi24 | yes | -10.1 | 12.2 | 2.67 | -1.6 | - |
| seq0009.txt | gps-l1 | no | -13.2 | -2.4 | 1.41 | 6.4 | s21 |
| seq0009.txt | wideband-sdr | no | -0.3 | 1.2 | 3.54 | 4.8 | s11 |
| seq0009.txt | dhruva-l5 | no | -1.3 | 13.2 | 7.75 | 6.8 | s11_max |
| seq0009.txt | dhruva-l2 | no | -1.4 | 13.2 | 7.44 | 6.4 | s11_max |
| seq0009.txt | dhruva-l1 | no | -1.9 | 10.7 | 7.58 | 6.1 | s11_max |
| seq0009.txt | dhruva-s | no | -4.2 | 9.9 | 4.86 | 2.2 | s11_max |
| seq0220.txt | wifi24 | yes | -13.6 | 15.4 | 4.89 | -1.7 | - |
| seq0220.txt | gps-l1 | no | -12.7 | -7.1 | 1.59 | 11.0 | s21 |
| seq0220.txt | wideband-sdr | no | -10.7 | -0.6 | 12.34 | 10.6 | s21 |
| seq0220.txt | dhruva-l5 | no | -6.5 | -1.8 | 3.11 | 13.2 | s21 |
| seq0220.txt | dhruva-l2 | no | -1.1 | 8.1 | 12.48 | 11.2 | s11_max |
| seq0220.txt | dhruva-l1 | no | -1.2 | 8.5 | 9.57 | 9.5 | s11_max |
| seq0220.txt | dhruva-s | no | -11.6 | 3.7 | 4.59 | 7.0 | s21 |
| seq0079.txt | wifi24 | no | -11.8 | 11.5 | 2.02 | -0.9 | s21 |
| seq0079.txt | gps-l1 | no | -0.3 | 2.8 | 0.98 | 5.3 | s11 |
| seq0079.txt | wideband-sdr | no | -1.0 | 5.2 | 8.16 | 8.3 | s11 |
| seq0079.txt | dhruva-l5 | no | -0.2 | 6.8 | 3.25 | 4.8 | s11_max |
| seq0079.txt | dhruva-l2 | no | -0.2 | 6.7 | 3.23 | 4.7 | s11_max |
| seq0079.txt | dhruva-l1 | no | -0.6 | 5.2 | 2.95 | 6.6 | s11_max |
| seq0079.txt | dhruva-s | no | -6.1 | 4.0 | 4.1 | 3.8 | s21 |
| seq0086.txt | wifi24 | yes | -11.2 | 16.6 | 2.26 | -1.2 | - |
| seq0086.txt | gps-l1 | no | -0.2 | 10.3 | 1.55 | 8.2 | s11 |
| seq0086.txt | wideband-sdr | no | -0.1 | 6.4 | 0.73 | 8.4 | s11 |
| seq0086.txt | dhruva-l5 | no | -0.4 | 13.4 | 2.47 | 6.6 | s11_max |
| seq0086.txt | dhruva-l2 | no | -0.4 | 13.4 | 2.54 | 6.4 | s11_max |
| seq0086.txt | dhruva-l1 | no | -0.6 | 13.9 | 2.26 | 4.8 | s11_max |
| seq0086.txt | dhruva-s | no | -1.8 | 15.4 | 2.2 | 1.2 | s11_max |
| seq0046.txt | wifi24 | no | -9.8 | 0.7 | 2.45 | 6.0 | s21 |
| seq0046.txt | gps-l1 | no | -0.9 | 18.8 | 2.72 | 6.2 | s11 |
| seq0046.txt | wideband-sdr | no | -1.0 | -22.4 | 7.55 | 27.6 | s21 |
| seq0046.txt | dhruva-l5 | no | -0.5 | 18.7 | 11.67 | 8.7 | s11_max |
| seq0046.txt | dhruva-l2 | no | -0.4 | 18.3 | 11.52 | 8.4 | s11_max |
| seq0046.txt | dhruva-l1 | no | -0.5 | 23.7 | 3.86 | 6.9 | s11_max |
| seq0046.txt | dhruva-s | no | -1.8 | 24.1 | 8.51 | 4.9 | s11_max |
