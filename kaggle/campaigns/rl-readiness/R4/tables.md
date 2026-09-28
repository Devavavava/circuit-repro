## (a) spec topology limits over recorded solutions

| source | solutions | cells | violate any spec.topology criterion | by criterion | cells with >=1 compliant solution |
|---|---|---|---|---|---|
| tpl | 16 | 16 | 8 | {'max_inductors': 8} | 8 |
| ec | 208 | 16 | 196 | {'max_inductors': 196} | 8 |
| ec_conf | 208 | 16 | 196 | {'max_inductors': 196} | 8 |
| ed | 20 | 8 | 20 | {'max_inductors': 20} | 0 |
| s1 | 14 | 4 | 14 | {'max_inductors': 14} | 0 |
| sg | 14 | 8 | 0 | - | 8 |

## sizing runs (tag, mode, final feasible, spec feasible): count

- ('dir', 'inloop', False, False): 5
- ('dir', 'lib', True, False): 5
- ('ed', 'inloop', False, False): 31
- ('ed', 'inloop', False, True): 7
- ('ed', 'inloop', True, True): 22
- ('gf', 'gate', False, False): 2
- ('gf', 'gate', False, True): 10
- ('mut', 'inloop', False, False): 3
- ('mut', 'inloop', True, True): 13
- ('nb', 'inloop', False, False): 9
- ('nb', 'inloop', True, True): 63
- ('reg', 'gate', True, True): 1
- ('reg', 'inloop', True, True): 1
- ('reg', 'lib', False, False): 1
- ('reg', 'topo', False, False): 1
- ('reg', 'topo', True, True): 1
- ('reg2', 'all', False, True): 2
- ('reg2', 'gate', True, True): 1
- ('reg2', 'inloop', True, True): 1
- ('reg2', 'lib', False, False): 1
- ('reg2', 'struct', False, False): 1
- ('reg2', 'struct', True, True): 1
- ('reg2', 'win50', True, True): 1
- ('reg3', 'gate', True, True): 1
- ('reg3', 'inloop', True, True): 1
- ('reg3', 'lib', False, False): 1
- ('s1', 'inloop', True, True): 22
- ('win50', 'win50', False, False): 2
- ('win50', 'win50', True, True): 6

| group (inloop) | runs | final feasible | cells | cells with >=1 feasible |
|---|---|---|---|---|
| dir:ec | 5 | 0 | 5 | 0 |
| ed:ed | 60 | 22 | 8 | 4 |
| nb:anchor:lna-a1-inddegen-cascode | 24 | 22 | 8 | 8 |
| nb:ec | 24 | 17 | 8 | 7 |
| nb:template | 24 | 24 | 8 | 8 |
| reg3:template | 1 | 1 | 1 | 1 |
| s1:ec | 14 | 14 | 4 | 4 |
| s1:template | 8 | 8 | 4 | 4 |

Designs analysed: 107 stable-feasible winners, 17 gate-rejected (spec-feasible, wide-unstable) designs (mutation runs excluded).

Winner re-eval through SZ.eval_metrics reproduces the recorded metrics: 107/107 (100%)

## (b) dynamic degeneracy over stable-feasible winners

- MOS with |Id| < 1 uA per design: {0: 107}
- MOS below 50 uA ('off' region) per design: {0: 80, 1: 27}
- Idd (mA): min 1.284, median 3.088, max 9.981
- max total VBGEN (bias-source) current: 0 A
- designs with >=1 INERT passive (opening it keeps the design final-feasible): 33/107 (31%); inert-count histogram {0: 74, 2: 7, 1: 24, 3: 2}

## (c) fragility: 10 draws x (1+U[-5%,+5%]) on every sized value

- draws still FINAL-feasible: 182/1070 (17%); spec-feasible 322/1070 (30%); wide-stable 570/1070 (53%)
- designs feasible in 10/10 draws: 0; >=5/10: 7; 0/10: 37 (of 107)
- histogram (#feasible draws: #designs): {0: 37, 1: 19, 2: 19, 3: 13, 4: 12, 5: 4, 6: 3}
- what breaks (count over failing draws): {'WIDE_mu': 500, 's11_db': 300, 's11_max_db': 218, 's21_db': 182, 'mu_min': 170, 'nf_db': 37, 'idd_ma': 18, 's21_ripple_db': 16}

| group | designs | feasible draws | median winner worst margin |
|---|---|---|---|
| nb nb | 63 | 146/630 (23%) | 0.0022 |
| wb ed | 22 | 19/220 (9%) | 0.0018 |
| wb s1 | 22 | 17/220 (8%) | 0.0032 |

## (d) stability-window sensitivity (pass = mu_min >= 1)

| window | stable winners pass | gate-rejected designs pass |
|---|---|---|
| w0p1_10 | 106/107 (99%) | 0/17 (0%) |
| w0p1_20 | 107/107 (100%) | 0/17 (0%) |
| w0p1_20_fine | 104/107 (97%) | 0/17 (0%) |
| w0p01_50 | 99/107 (93%) | 0/17 (0%) |
| w0p01_50_dec | 100/107 (93%) | 0/17 (0%) |
| 0.01-50 lin AND dec | 99/107 (93%) | |

Gate-rejected designs, where the 0.01-50 GHz mu<1 span starts: {'0.1-10GHz': 14, '<0.1GHz': 3}
Gate-rejected designs, gate-window mu_min: -1.705, -1.260, -1.018, -0.359, 0.347, 0.612, 0.637, 0.826, 0.866, 0.879, 0.930, 0.931, 0.966, 0.977, 0.978, 0.983, 0.989

## (e) transient with real terminations (80 ns, 1 mA x 10 ps kick at VIN1+VOUT1)

| population | designs | r50/r50 oscillates | r50/r50 dc_shift | oscillates under >=1 of 25 terminations | median # oscillating terminations |
|---|---|---|---|---|---|
| gate-rejected | 17 | 0 | 0 | 5 | 0 |

gate-rejected: verdicts over all termination pairs: {'decays': 397, 'ringing': 9, 'oscillates': 19}

| stable winners | 107 | 0 | 0 | 7 | 0 |

stable winners: verdicts over all termination pairs: {'decays': 2307, 'ringing': 361, 'oscillates': 7}

Gate-rejected designs, oscillating termination pairs (source/load): {'l3n/open': 3, 'l3n/l3n': 3, 'l3n/c1p': 2, 'c1p/open': 2, 'c1p/l3n': 2, 'short/c1p': 1, 'r50/l3n': 1, 'open/open': 1, 'open/l3n': 1, 'l3n/r50': 1, 'l3n/short': 1, 'c1p/c1p': 1}

## (f) other loopholes

- NF checked at f0 only: wideband winners whose NF over the band exceeds the spec max: 35/44 (80%); narrowband 5/63
- narrowband (spec checks s21/s11 at f0 only): winners whose in-band (f0 +/-2%) s21_min < spec: 4/63; s11_max > spec: 61/63
- out-of-band |S21| peak above in-band s21 by > 3 dB: 0/107 winners (max excess 0.41 dB)
- sized values pinned at a range limit: 78/107 (73%) winners; by kind/side {'C-hi': 44, 'R-lo': 7, 'W-lo': 2, 'L-hi': 28, 'R-hi': 39, 'C-lo': 3, 'W-hi': 2, 'L-lo': 1}

### adversarial mutations of the reference templates (inloop verifier, seed 1)

| mutation | cell | seed | parent final feasible | mutant final feasible | mutant worst margin (parent) | inert passives in mutant winner (parent) |
|---|---|---|---|---|---|---|
| nb_bleeder | nb-f15-g16 | 1 | True | True | +0.0060 mu_min (+0.0008 mu_min) | ['pC4V', 'pR3V'] ([]) |
| nb_cap_in | nb-f15-g16 | 1 | True | True | +0.0004 s11_db (+0.0008 mu_min) | ['pC4V', 'pC5V'] ([]) |
| nb_dangling | nb-f15-g16 | 1 | True | True | +0.0077 mu_min (+0.0008 mu_min) | ['pC4V', 'pC5V', 'pR3V'] ([]) |
| nb_dead_mos | nb-f15-g16 | 1 | True | True | +0.0037 mu_min (+0.0008 mu_min) | ['pC4V'] ([]) |
| nb_dup_out | nb-f15-g16 | 1 | True | True | +0.0002 s11_db (+0.0008 mu_min) | ['pC5V'] ([]) |
| nb_rin_out | nb-f15-g16 | 1 | True | False | -3.4124 nf_db (+0.0008 mu_min) | None ([]) |
| nb_tank_out | nb-f15-g16 | 1 | True | True | +0.0216 s11_db (+0.0008 mu_min) | ['pC4V', 'pC5V'] ([]) |
| nb_vbnet | nb-f15-g16 | 1 | True | False | -0.2661 s11_db (+0.0008 mu_min) | None ([]) |
| wb_bleeder | wb-s11n10-g10-b0824 | 1 | True | True | +0.0059 s21_db (+0.0040 s21_db) | ['pR1V', 'pR6V'] ([]) |
| wb_cap_in | wb-s11n10-g10-b0824 | 1 | True | True | +0.0095 s11_max_db (+0.0040 s21_db) | ['pC5V', 'pR1V'] ([]) |
| wb_dangling | wb-s11n10-g10-b0824 | 1 | True | False | -1.7710 nf_db (+0.0040 s21_db) | None ([]) |
| wb_dead_mos | wb-s11n10-g10-b0824 | 1 | True | True | +0.0024 s11_max_db (+0.0040 s21_db) | [] ([]) |
| wb_dup_out | wb-s11n10-g10-b0824 | 1 | True | True | +0.0069 s21_db (+0.0040 s21_db) | ['pC5V'] ([]) |
| wb_rin_out | wb-s11n10-g10-b0824 | 1 | True | True | +0.0038 s21_db (+0.0040 s21_db) | [] ([]) |
| wb_tank_out | wb-s11n10-g10-b0824 | 1 | True | True | +0.0028 s11_max_db (+0.0040 s21_db) | [] ([]) |
| wb_vbnet | wb-s11n10-g10-b0824 | 1 | True | True | +0.0007 s21_db (+0.0040 s21_db) | [] ([]) |
