## (a) Regression: flags-off byte-identity vs recorded stability-gate rows

Full `json.dumps(result, sort_keys=True)` equality against `../stability-gate/results.json`.

| exp | cell | cand | spec | mode | seed | recorded in | identical full dict |
|---|---|---|---|---|---|---|---|
| anchors | v12-nb-f15-g12 | lna-a2-current-reuse | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g12 | lna-a2-current-reuse | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g12 | lna-a2-current-reuse | stab | gate | 3 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g12 | lna-a4-twostage | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g12 | lna-a4-twostage | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g12 | lna-a4-twostage | stab | gate | 3 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g16 | lna-a2-current-reuse | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g16 | lna-a2-current-reuse | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g16 | lna-a2-current-reuse | stab | gate | 3 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g16 | lna-a4-twostage | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g16 | lna-a4-twostage | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f15-g16 | lna-a4-twostage | stab | gate | 3 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g12 | lna-a2-current-reuse | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g12 | lna-a2-current-reuse | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g12 | lna-a2-current-reuse | stab | gate | 3 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g12 | lna-a4-twostage | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g12 | lna-a4-twostage | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g12 | lna-a4-twostage | stab | gate | 3 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g18 | lna-a2-current-reuse | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g18 | lna-a2-current-reuse | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g18 | lna-a2-current-reuse | stab | gate | 3 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g18 | lna-a4-twostage | stab | gate | 1 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g18 | lna-a4-twostage | stab | gate | 2 | stability-gate/anchors | True |
| anchors | v12-nb-f24-g18 | lna-a4-twostage | stab | gate | 3 | stability-gate/anchors | True |
| edge | v12-nb-f15-g14 | template | stab | gate | 1 | stability-gate/tpl | True |
| edge | v12-nb-f15-g16 | template | stab | gate | 2 | stability-gate/tpl | True |
| edge | v12-nb-f15-g18 | template | stab | gate | 1 | stability-gate/tpl | True |
| edge | v12-nb-f24-g12 | template | stab | gate | 1 | stability-gate/tpl | True |
| edge | v12-nb-f24-g18 | template | stab | gate | 2 | stability-gate/tpl | True |
| edgefail | v12-nb-f15-g12 | lna-a1-inddegen-cascode | stab | gate | 3 | stability-gate/anchors | True |
| edgefail | v12-nb-f15-g12 | template | stab | gate | 1 | stability-gate/tpl | True |
| edgefail | v12-nb-f24-g12 | template | stab | gate | 2 | stability-gate/tpl | True |
| edgefail | v12-nb-f24-g14 | template | stab | gate | 1 | stability-gate/tpl | True |
| regress | v12-wb-s11n10-g10-b0530 | template | lib | gate | 1 | stability-gate/regress | True |
| regress | v12-wb-s11n10-g10-b0530 | template | lib | inloop | 1 | stability-gate/regress | True |
| regress | v12-wb-s11n10-g10-b0530 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g10-b0530 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g10-b0530 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g10-b0530 | template | stab | gate | 3 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g10-b0824 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g10-b0824 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g10-b0824 | template | stab | gate | 3 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g12-b0824 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g12-b0824 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n10-g12-b0824 | template | stab | gate | 3 | stability-gate/tpl | True |
| tpl | v12-wb-s11n11-g10-b0824 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n11-g10-b0824 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n11-g10-b0824 | template | stab | gate | 3 | stability-gate/tpl | True |
| tpl | v12-wb-s11n11-g12-b0824 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n11-g12-b0824 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n11-g12-b0824 | template | stab | gate | 3 | stability-gate/tpl | True |
| tpl | v12-wb-s11n8-g10-b0530 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n8-g10-b0530 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n8-g10-b0530 | template | stab | gate | 3 | stability-gate/tpl | True |
| tpl | v12-wb-s11n8-g12-b0530 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n8-g12-b0530 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n8-g12-b0530 | template | stab | gate | 3 | stability-gate/tpl | True |
| tpl | v12-wb-s11n9-g10-b0530 | template | stab | gate | 1 | stability-gate/tpl | True |
| tpl | v12-wb-s11n9-g10-b0530 | template | stab | gate | 2 | stability-gate/tpl | True |
| tpl | v12-wb-s11n9-g10-b0530 | template | stab | gate | 3 | stability-gate/tpl | True |

**60/60 identical.**

## (b) Per candidate x cell, stability-enabled spec, 2500 evals, seeds 1/2/3

F = final feasible (spec incl. in-band mu_min>=1 AND wide mu>=1), s = spec-feasible but wide-unstable, x = spec-infeasible. mu wide = wide mu_min of the reported winner. jv = joint violation of the inloop winner (sum of normalized in-band shortfalls + max(0, 1 - mu_wide)); min over seeds.

| exp | cell | cand | gate-only 1/2/3 | mu wide gate | gate+inloop 1/2/3 | mu wide inloop | mu in-band inloop | min jv inloop | worst binding inloop (best-jv seed) |
|---|---|---|---|---|---|---|---|---|---|
| anchors | nb-f15-g12 | lna-a2-current-reuse | xxx | 0.78, -0.20, 0.76 | xxx | 0.75, 0.78, 0.90 | 0.78, 0.78, 1.00 | 0.3035 | ['nf_db', -0.17951111111111115] |
| anchors | nb-f15-g12 | lna-a4-twostage | sss | -1.26, -1.55, -1.54 | xxx | 0.92, 0.99, 1.00 | 2.56, 1.51, 1.46 | 0.6696 | ['s11_db', -0.664971] |
| anchors | nb-f15-g16 | lna-a2-current-reuse | xxx | 0.61, 0.63, 0.59 | xxx | 0.80, 0.86, 0.99 | 0.84, 0.86, 1.07 | 0.5986 | ['mu_min', -0.16242900000000005] |
| anchors | nb-f15-g16 | lna-a4-twostage | xss | -2.49, -0.32, -1.59 | xxx | 0.97, 1.00, 0.84 | 1.20, 1.01, 2.71 | 0.7515 | ['s11_db', -0.588713] |
| anchors | nb-f24-g12 | lna-a2-current-reuse | xxx | -0.03, 0.34, -0.10 | xxx | 0.96, 0.93, 0.95 | 1.00, 0.93, 0.96 | 0.3345 | ['s21_db', -0.2413966666666667] |
| anchors | nb-f24-g12 | lna-a4-twostage | sxs | -1.70, 0.64, -2.18 | sxx | 0.95, 1.00, 0.98 | 1.72, 1.08, 1.35 | 0.0489 | ['nf_db', 0.00043777777777778384] |
| anchors | nb-f24-g18 | lna-a2-current-reuse | xxx | 0.65, -0.33, 0.63 | xxx | 0.98, 0.98, 0.96 | 1.00, 0.98, 1.00 | 0.6037 | ['s21_db', -0.5372838888888889] |
| anchors | nb-f24-g18 | lna-a4-twostage | sss | -1.02, -1.11, -1.58 | xss | 0.83, 0.99, 0.99 | 2.70, 1.00, 1.02 | 0.0114 | ['idd_ma', 0.00023399999999995647] |
| ec | wb-s11n10-g10-b0530 | add R n1-n2 | sss | 0.35, 0.91, 0.93 | xxx | 0.90, 0.90, 0.95 | 1.07, 1.05, 1.07 | 0.0469 | ['s11_max_db', -1.8000000000029105e-05] |
| ec | wb-s11n10-g10-b0530 | add R n1-n4 | sxs | -0.69, -0.81, 0.44 | xxs | 1.00, 1.00, 1.00 | 1.13, 1.13, 1.13 | 0.0003 | ['s21_db', 0.0002000000000000668] |
| ec | wb-s11n10-g10-b0530 | add L n4-n5 | sxs | -0.82, 0.17, -0.72 | xxx | 0.99, 0.98, 0.99 | 1.11, 1.12, 1.12 | 0.0203 | ['s11_max_db', -0.013344999999999985] |
| ec | wb-s11n10-g10-b0824 | add R VIN1-n5 | xss | 1.01, 0.37, -0.23 | xxx | 0.79, 1.00, 1.00 | 1.32, 1.38, 1.25 | 0.0045 | ['s11_max_db', -0.004440999999999917] |
| ec | wb-s11n10-g10-b0824 | add R n1-n2 | sss | -0.36, 0.42, 0.82 | FFF | 1.00, 1.00, 1.00 | 1.12, 1.13, 1.13 | 0.0000 | feasible |
| ec | wb-s11n10-g10-b0824 | add L n1-n5 | sss | -0.20, 0.65, -0.30 | FFx | 1.00, 1.00, 1.00 | 1.17, 1.12, 1.47 | 0.0000 | feasible |
| ec | wb-s11n10-g12-b0824 | add L VIN1-n1 | sss | 0.91, 0.89, -0.15 | sxx | 1.00, 0.91, 0.98 | 1.09, 1.00, 1.10 | 0.0030 | ['s21_db', 3.333333333340368e-05] |
| ec | wb-s11n10-g12-b0824 | add R n1-n2 | sss | 0.88, 0.74, 0.89 | xxx | 0.95, 0.95, 0.96 | 1.04, 1.09, 1.13 | 0.0377 | ['s21_db', -0.0006166666666667098] |
| ec | wb-s11n10-g12-b0824 | add R n4-n6 | sss | 0.89, 0.90, 0.20 | xxx | 0.99, 0.98, 1.00 | 1.24, 1.16, 1.21 | 0.0077 | ['s11_max_db', -0.005921999999999983] |
| ec | wb-s11n11-g10-b0824 | add L VIN1-n5 | sss | -0.76, -0.23, -0.08 | FFF | 1.00, 1.00, 1.00 | 1.15, 1.07, 1.06 | 0.0000 | feasible |
| ec | wb-s11n11-g10-b0824 | add R n1-n2 | sss | 0.87, 0.82, 0.58 | FxF | 1.00, 0.95, 1.00 | 1.16, 1.11, 1.12 | 0.0000 | feasible |
| ec | wb-s11n11-g10-b0824 | add L n1-n5 | sss | -0.07, 0.16, 0.82 | xFx | 1.00, 1.00, 1.00 | 1.43, 1.18, 1.41 | 0.0000 | feasible |
| ec | wb-s11n11-g12-b0824 | add L VIN1-n3 | xss | 0.95, 0.46, 0.52 | sxs | 0.99, 0.82, 0.99 | 1.09, 1.27, 1.08 | 0.0069 | ['s11_max_db', 0.00019090909090913044] |
| ec | wb-s11n11-g12-b0824 | add R n1-n2 | sss | 0.64, 0.88, 0.90 | xxs | 0.95, 0.97, 0.93 | 1.09, 1.35, 1.00 | 0.0529 | ['s21_db', -0.00736666666666667] |
| ec | wb-s11n11-g12-b0824 | add R n2-n3 | sxs | 0.44, 0.95, 0.90 | xxx | 0.98, 0.96, 0.95 | 1.23, 1.17, 1.11 | 0.0526 | ['s21_db', -0.012675000000000066] |
| ec | wb-s11n8-g10-b0530 | add R n1-n2 | sss | 0.83, 0.60, 0.82 | xFF | 0.97, 1.00, 1.00 | 1.17, 1.11, 1.13 | 0.0000 | feasible |
| ec | wb-s11n8-g10-b0530 | add R n3-n4 | sxs | 0.46, 0.34, 0.69 | FFF | 1.00, 1.00, 1.00 | 1.11, 1.14, 1.13 | 0.0000 | feasible |
| ec | wb-s11n8-g10-b0530 | add C n4-n5 | sss | -0.52, -0.82, 0.45 | xxx | 1.00, 1.00, 0.98 | 1.15, 1.08, 1.24 | 0.2404 | ['s11_max_db', -0.24033875000000005] |
| ec | wb-s11n8-g12-b0530 | add L VIN1-n0 | sss | 0.81, 0.83, 0.88 | xsx | 0.91, 0.99, 0.94 | 1.06, 1.07, 1.10 | 0.0134 | ['s21_db', 5.8333333333345415e-05] |
| ec | wb-s11n8-g12-b0530 | add R n1-n2 | xxs | -0.36, 0.89, 0.89 | sxx | 0.93, 0.91, 0.93 | 1.00, 1.05, 1.00 | 0.0704 | ['idd_ma', 2.3200000000045406e-05] |
| ec | wb-s11n8-g12-b0530 | add L n4-n6 | ssx | -0.72, 0.16, 0.65 | xxx | 0.99, 0.99, 1.00 | 1.07, 1.17, 1.22 | 0.0730 | ['s21_db', -0.0586583333333334] |
| ec | wb-s11n9-g10-b0530 | add R n1-n2 | sss | 0.61, 0.59, 0.87 | sFs | 0.96, 1.00, 1.00 | 1.11, 1.06, 1.20 | 0.0000 | feasible |
| ec | wb-s11n9-g10-b0530 | add R n1-n4 | sss | 0.01, -0.57, 0.52 | FFF | 1.00, 1.00, 1.00 | 1.11, 1.14, 1.15 | 0.0000 | feasible |
| ec | wb-s11n9-g10-b0530 | add R n4-n5 | sxx | 0.32, -0.51, 0.92 | FxF | 1.00, 0.97, 1.00 | 1.16, 1.19, 1.08 | 0.0000 | feasible |
| tpl | wb-s11n10-g10-b0530 | template | sss | 0.35, 0.91, 0.93 | xxx | 0.90, 0.90, 0.95 | 1.07, 1.05, 1.07 | 0.0469 | ['s11_max_db', -1.8000000000029105e-05] |
| tpl | wb-s11n10-g10-b0824 | template | sss | -0.36, 0.42, 0.82 | FFF | 1.00, 1.00, 1.00 | 1.12, 1.13, 1.13 | 0.0000 | feasible |
| tpl | wb-s11n10-g12-b0824 | template | sss | 0.88, 0.74, 0.89 | xxx | 0.95, 0.95, 0.96 | 1.04, 1.09, 1.13 | 0.0377 | ['s21_db', -0.0006166666666667098] |
| tpl | wb-s11n11-g10-b0824 | template | sss | 0.87, 0.82, 0.58 | FxF | 1.00, 0.95, 1.00 | 1.16, 1.11, 1.12 | 0.0000 | feasible |
| tpl | wb-s11n11-g12-b0824 | template | sss | 0.64, 0.88, 0.90 | xxs | 0.95, 0.97, 0.93 | 1.09, 1.35, 1.00 | 0.0529 | ['s21_db', -0.00736666666666667] |
| tpl | wb-s11n8-g10-b0530 | template | sss | 0.83, 0.60, 0.82 | xFF | 0.97, 1.00, 1.00 | 1.17, 1.11, 1.13 | 0.0000 | feasible |
| tpl | wb-s11n8-g12-b0530 | template | xxs | -0.36, 0.89, 0.89 | sxx | 0.93, 0.91, 0.93 | 1.00, 1.05, 1.00 | 0.0704 | ['idd_ma', 2.3200000000045406e-05] |
| tpl | wb-s11n9-g10-b0530 | template | sss | 0.61, 0.59, 0.87 | sFs | 0.96, 1.00, 1.00 | 1.11, 1.06, 1.20 | 0.0000 | feasible |

## (c) Totals per candidate

| exp | candidate | cells | (cell,cand) units | gate-only F / s / n | cells >=1 F (gate) | gate+inloop F / s / n | cells >=1 F (inloop) | wide mu range gate | wide mu range inloop |
|---|---|---|---|---|---|---|---|---|---|
| anchors | lna-a2-current-reuse | 4 | 4 | 0 / 0 / 12 | 0 | 0 / 0 / 12 | 0 | -0.33..0.78 | 0.75..0.99 |
| anchors | lna-a4-twostage | 4 | 4 | 0 / 10 / 12 | 0 | 0 / 3 / 12 | 0 | -2.49..0.64 | 0.83..1.00 |
| ec | ec:add R n1-n2 | 8 | 8 | 0 / 22 / 24 | 0 | 8 / 4 / 24 | 4 | -0.36..0.93 | 0.90..1.00 |
| ec | ec:other edits | 8 | 16 | 0 / 39 / 48 | 0 | 14 / 5 / 48 | 4 | -0.82..1.01 | 0.79..1.00 |
| tpl | template | 8 | 8 | 0 / 22 / 24 | 0 | 8 / 4 / 24 | 4 | -0.36..0.93 | 0.90..1.00 |

Wideband cells with >=1 stable-feasible seed from ANY tested candidate (template + E-c edits): gate-only 0/8 []; gate+inloop 4/8 ['v12-wb-s11n10-g10-b0824', 'v12-wb-s11n11-g10-b0824', 'v12-wb-s11n8-g10-b0530', 'v12-wb-s11n9-g10-b0530'].

## (d) 100 MHz edge: wide mu(f) of FINAL winners

Stable winners (final feasible): 30. With argmin at the 100 MHz edge: 0.

Rows `edge` = 5 nb-template runs the stability-gate campaign recorded final-feasible (re-run gate-only, deterministic); `edgefail` = the 4 recorded spec-feasible nb runs that fail the wide gate with mu_wide >= 0.99; then the first 8 S-1 stable winners (all wideband, gate+inloop).

| exp | cell | cand | mode | seed | argmin (GHz) | mu min | mu@100MHz | interior argmin (GHz) | interior mu min | pts mu<1.001 |
|---|---|---|---|---|---|---|---|---|---|---|
| edge | nb-f15-g14 | template | gate | 1 | 0.1000 | 1.000133 | 1.000133 | 0.150 | 1.0003 | 4 |
| edge | nb-f15-g16 | template | gate | 2 | 0.1000 | 1.000113 | 1.000113 | 0.150 | 1.0003 | 4 |
| edge | nb-f15-g18 | template | gate | 1 | 0.1000 | 1.000118 | 1.000118 | 0.150 | 1.0003 | 4 |
| edge | nb-f24-g12 | template | gate | 1 | 0.1000 | 1.000018 | 1.000018 | 0.150 | 1.0000 | 17 |
| edge | nb-f24-g18 | template | gate | 2 | 0.1000 | 1.000031 | 1.000031 | 0.150 | 1.0001 | 14 |
| edgefail | nb-f15-g12 | template | gate | 1 | 1.4930 | 0.998120 | 1.000134 | 1.493 | 0.9981 | 6 |
| edgefail | nb-f15-g12 | lna-a1-inddegen-cascode | gate | 3 | 1.4432 | 0.996057 | 1.000166 | 1.443 | 0.9961 | 7 |
| edgefail | nb-f24-g12 | template | gate | 2 | 2.2393 | 0.991249 | 1.000020 | 2.239 | 0.9912 | 23 |
| edgefail | nb-f24-g14 | template | gate | 1 | 2.5875 | 0.996510 | 1.000022 | 2.587 | 0.9965 | 26 |
| ec | wb-s11n10-g10-b0824 | add R n1-n2 | inloop | 1 | 8.5077 | 1.000451 | 1.018570 | 8.508 | 1.0005 | 13 |
| ec | wb-s11n10-g10-b0824 | add R n1-n2 | inloop | 2 | 6.1197 | 1.000225 | 1.014163 | 6.120 | 1.0002 | 18 |
| ec | wb-s11n10-g10-b0824 | add R n1-n2 | inloop | 3 | 5.8213 | 1.001770 | 1.009307 | 5.821 | 1.0018 | 0 |
| ec | wb-s11n10-g10-b0824 | add L n1-n5 | inloop | 1 | 8.5575 | 1.001068 | 1.068607 | 8.557 | 1.0011 | 0 |
| ec | wb-s11n10-g10-b0824 | add L n1-n5 | inloop | 2 | 5.4730 | 1.000471 | 1.045227 | 5.473 | 1.0005 | 15 |
| ec | wb-s11n11-g10-b0824 | add L VIN1-n5 | inloop | 1 | 5.5228 | 1.000321 | 1.039551 | 5.523 | 1.0003 | 17 |
| ec | wb-s11n11-g10-b0824 | add L VIN1-n5 | inloop | 2 | 3.7815 | 1.001537 | 1.066990 | 3.781 | 1.0015 | 0 |
| ec | wb-s11n11-g10-b0824 | add L VIN1-n5 | inloop | 3 | 3.3835 | 1.001008 | 1.056445 | 3.384 | 1.0010 | 0 |

- Gated runs: 240. Spec-feasible but wide-failing with mu_wide in [0.999, 1): **1** (would flip fail->pass with tolerance 1e-3: ec/v12-wb-s11n10-g10-b0530/add R n1-n4/inloop/s3 mu=0.99969 at 8.159 GHz).
- Final-feasible runs with mu_wide < 1.001 (would flip pass->fail if the threshold were raised by 1e-3): **23/30**; of these 0 have the argmin at 100 MHz.
- Spec-feasible, wide-failing runs whose argmin is the 100 MHz edge point: 0.
- stability-gate campaign (171 gated rows): tolerance 1e-3 flips fail->pass: **0**; within 1e-2 (mu_wide in [0.99,1)): 5 (the `edgefail` rows above + negctl s1, min at 1.29-1.34 GHz). Final-feasible with mu_wide < 1.001 (flip pass->fail at +1e-3): **32/32**.
- `edge` rows: argmin at 100 MHz in 5/5 (mu there 1.00002..1.00013); `edgefail` rows: argmin at 100 MHz in 0/4 (interior dips at 1.49, 1.44, 2.24, 2.59 GHz).
- Any final winner (all 240 curves) with argmin at 100 MHz: 1; their mu@100MHz range 1.000130..1.000130.

## (e) Wall-time overhead of the in-loop term

- Paired runs: 120 (same cell/cand/seed, gate-only vs gate+inloop, 8 parallel processes, shared box).
- Median wall: gate-only 57.1 s, gate+inloop 95.2 s; median ratio 1.66x.
- In-loop wide sims: 300000 total, 4335 s, 14.4 ms/sim (~36.1 s per 2500-eval run).
