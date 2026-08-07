# Cross-spec feasibility benchmark

6 candidate topologies (feasible + closest near-feasible), sized against each spec (curated on wifi24, all-free multi-seed else).

## Per-spec yield (feasible / total)

- **wifi24**: 6/6 feasible; binding when not: -
- **gps-l1**: 0/6 feasible; binding when not: {'s21': 5, 'idd': 1}
- **wideband-sdr**: 0/6 feasible; binding when not: {'s11': 4, 's21': 1, 's21_ripple': 1}

## Matrix (F = feasible, else binding constraint)

| candidate | dev | wifi24 | gps-l1 | wideband-sdr |
|---|---|---|---|---|
| seq0240.txt | 8 | **F** | s21 | s11 |
| seq0009.txt | 10 | **F** | s21 | s11 |
| seq0220.txt | 9 | **F** | s21 | s11 |
| seq0009.txt | 12 | **F** | s21 | s21 |
| seq0001.txt | 10 | **F** | s21 | s11 |
| seq0008.txt | 9 | **F** | idd | s21_ripple |

## Detail (best sized metrics per cell)

| candidate | spec | feas | S11 | S21 | Idd | NF | binding |
|---|---|---|---|---|---|---|---|
| seq0240.txt | wifi24 | yes | -14.9 | 14.5 | 2.17 | -0.4 | - |
| seq0240.txt | gps-l1 | no | -7.7 | 9.6 | 3.48 | 5.5 | s21 |
| seq0240.txt | wideband-sdr | no | -0.3 | 12.0 | 4.32 | 5.1 | s11 |
| seq0009.txt | wifi24 | yes | -10.9 | 12.8 | 4.0 | -1.4 | - |
| seq0009.txt | gps-l1 | no | -11.0 | 5.3 | 2.75 | 4.3 | s21 |
| seq0009.txt | wideband-sdr | no | -0.4 | 6.4 | 6.68 | 5.2 | s11 |
| seq0220.txt | wifi24 | yes | -13.8 | 12.6 | 2.46 | -2.6 | - |
| seq0220.txt | gps-l1 | no | -12.4 | 5.3 | 3.01 | 4.3 | s21 |
| seq0220.txt | wideband-sdr | no | -0.8 | 8.4 | 7.78 | 9.0 | s11 |
| seq0009.txt | wifi24 | yes | -11.5 | 17.1 | 3.72 | 3.0 | - |
| seq0009.txt | gps-l1 | no | -8.1 | 9.2 | 3.05 | 3.7 | s21 |
| seq0009.txt | wideband-sdr | no | -0.1 | -12.4 | 6.04 | 16.0 | s21 |
| seq0001.txt | wifi24 | yes | -12.0 | 13.0 | 3.09 | 1.3 | - |
| seq0001.txt | gps-l1 | no | -12.2 | 13.8 | 2.84 | 0.2 | s21 |
| seq0001.txt | wideband-sdr | no | -0.3 | 7.8 | 0.96 | 5.8 | s11 |
| seq0008.txt | wifi24 | yes | -10.4 | 15.0 | 4.07 | 3.4 | - |
| seq0008.txt | gps-l1 | no | -12.9 | 18.3 | 4.56 | -0.3 | idd |
| seq0008.txt | wideband-sdr | no | -1.2 | 13.1 | 6.44 | 7.0 | s21_ripple |

## What this says about next steps

- **wifi24** (S21>=12, Idd<=5): **SOLVED** -- curated sizing makes every candidate
  feasible. The pipeline reliably designs wifi24-class LNAs.
- **gps-l1** (S21>=15, Idd<=3, NF<=1.8): **GAIN-LIMITED** -- 5/6 bind on S21. The
  cascode+tapped topologies top out ~12-14 dB; 15 dB at 3 mA needs *higher-gain
  archetypes* (two-stage / gm-boosted / higher-ratio transformer). A TOPOLOGY lever
  (templates.py + P5 generator), not a sizer lever.
- **wideband-sdr** (broadband S11, ripple<=2): **MATCH-LIMITED** -- 4/6 bind on S11.
  A narrowband LC match cannot hold 50 ohm across the band; needs *wideband-match
  archetypes* (resistive shunt-feedback, which templates.py has but the generator
  underuses; the candidates here are all narrowband-matched).

Net: the pipeline is tuned for wifi24-class specs. Broadening it = add (1) gain-
boosted and (2) wideband-match archetype families to templates.py + the P5
generator, then re-run this benchmark. Sizing (curated) is not the bottleneck for
the harder specs -- topology diversity is.
