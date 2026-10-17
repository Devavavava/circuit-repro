# bench-v3 A0 yield probe -- tables

Pre-reg: kaggle/PREREG-BENCH-V3.md (f56d45e11) sections 2 + 8. Verifier rl-v1.2, seed 1, budget 2500, bptm45. Built 2026-10-18T00:57:28 by `a0.py summarize`.

**Verdict: STOP (< 8 accepted: the stretch form fails here; stop and report)** -- eligible 35, nominated (headroom) 0, accepted 0.

| | eligible | nominated | accepted |
|---|---|---|---|
| tier T2 | 32 | 0 | 0 |
| tier T3 | 3 | 0 | 0 |
| family nb090-noise | 16 | 0 | 0 |
| family wb0824-gain | 1 | 0 | 0 |
| family wb1020-gain | 17 | 0 | 0 |
| family wb1020-noise | 1 | 0 | 0 |

Confirmation calls: 0 rows (0 newly sized, 0 reused), new CPU 0.00 CPU-h.

No-headroom reasons: a_w < 0.02 6, a_w < 0.02 & b_w - 0.02 <= delta_min 28, b_w - 0.02 <= delta_min 1

## Per task

a = min non-flavor margin (incl. mu_wide-1), b = flavor margin, at the ORIGINAL spec (cached seed-1 rows). delta_min = 0.05 + max{b(d): a(d) > -0.05} over library + single edits. Confirmation = new seed-1 sizing at the stretched spec: worst normalized margin incl. mu_wide-1 (witness, ref1-3).

| task | tier | flavor metric | limit | a_w | b_w | R (id, b) | delta_min | headroom | delta* | stretched limit | witness worst | ref1 | ref2 | ref3 | accepted |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t2-nb090-noise-0012 | T3 | nf_db max | 1.7879 | 0.0002 | 0.3202 | lib:a1, -0.0736 | -0.0236 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0254 | T2 | nf_db max | 1.3486 | 0.0000 | 0.0041 | edit:a4:69:add R VOUT1-n7, 0.1897 | 0.2397 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0269 | T2 | nf_db max | 1.7183 | -0.0411 | 0.0227 | edit:a4:13:add C VDD-n2, 0.4088 | 0.4588 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0286 | T2 | nf_db max | 1.5001 | 0.0007 | 0.2550 | edit:a4:69:add R VOUT1-n7, 0.2457 | 0.2957 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0291 | T2 | nf_db max | 1.4763 | -0.0238 | 0.0013 | edit:a4:16:add C VDD-n4, 0.2784 | 0.3284 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0300 | T2 | nf_db max | 1.3717 | 0.0000 | 0.2610 | edit:a4:69:add R VOUT1-n7, 0.2027 | 0.2527 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0312 | T2 | nf_db max | 1.357 | 0.0001 | 0.2471 | edit:a4:69:add R VOUT1-n7, 0.1763 | 0.2263 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0322 | T2 | nf_db max | 1.3425 | 0.0017 | 0.1167 | edit:a4:115:add C n2-n7, 0.1544 | 0.2044 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0323 | T2 | nf_db max | 1.8517 | 0.0413 | 0.3824 | edit:a4:16:add C VDD-n4, 0.4534 | 0.5034 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0349 | T2 | nf_db max | 1.2682 | 0.0189 | 0.2610 | edit:a4:16:add C VDD-n4, 0.2212 | 0.2712 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0350 | T2 | nf_db max | 1.1457 | -0.3754 | 0.0121 | edit:a4:133:add C n6-n7, 0.4113 | 0.4613 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0351 | T2 | nf_db max | 1.4335 | 0.0055 | 0.4281 | edit:a4:69:add R VOUT1-n7, 0.2156 | 0.2656 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0363 | T2 | nf_db max | 1.6719 | 0.0026 | 0.5120 | edit:a4:16:add C VDD-n4, 0.3239 | 0.3739 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0375 | T2 | nf_db max | 1.2427 | -0.3482 | 0.1060 | edit:a4:133:add C n6-n7, 0.4658 | 0.5158 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0397 | T2 | nf_db max | 1.2984 | 0.0031 | 0.4731 | edit:a4:133:add C n6-n7, 0.4915 | 0.5415 | no | - | - | - | - | - | - | no |
| t2-nb090-noise-0411 | T2 | nf_db max | 1.1308 | 0.0023 | 0.1843 | edit:a4:133:add C n6-n7, 0.4331 | 0.4831 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0010 | T2 | s21_db min | 11.0472 | 0.0004 | 0.0003 | edit:a2:52:add C VIN1-n5, 0.0893 | 0.1393 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0027 | T2 | s21_db min | 11.3954 | 0.0002 | 0.0814 | edit:a2:52:add C VIN1-n5, 0.0564 | 0.1064 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0028 | T2 | s21_db min | 10.2985 | 0.0006 | 0.1517 | edit:a2:159:add R n4-n6, 0.0423 | 0.0923 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0045 | T2 | s21_db min | 13.0745 | 0.0004 | 0.0157 | edit:a2:151:add C n3-n5, 0.0205 | 0.0705 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0046 | T2 | s21_db min | 11.1855 | 0.0006 | 0.1733 | edit:a2:73:add C VOUT1-n4, 0.2298 | 0.2798 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0065 | T2 | s21_db min | 10.5476 | 0.0002 | 0.0925 | edit:a2:102:add R n0-n1, 0.1603 | 0.2103 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0067 | T2 | s21_db min | 12.2162 | 0.0003 | 0.0580 | edit:a2:19:add C VDD-n3, 0.0957 | 0.1457 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0089 | T2 | s21_db min | 12.1881 | 0.0002 | 0.0209 | edit:a2:73:add C VOUT1-n4, 0.0773 | 0.1273 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0108 | T2 | s21_db min | 12.1891 | 0.0001 | 0.0018 | edit:a2:13:add C VDD-n1, 0.0381 | 0.0881 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0109 | T2 | s21_db min | 12.8023 | 0.0000 | -0.0030 | edit:a2:25:add C VDD-n5, 0.0060 | 0.0560 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0128 | T2 | s21_db min | 12.6523 | 0.0003 | 0.0037 | edit:a2:75:add R VOUT1-n5, 0.0037 | 0.0537 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0142 | T2 | s21_db min | 13.6274 | 0.0004 | 0.0001 | edit:a2:19:add C VDD-n3, 0.0014 | 0.0514 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0159 | T2 | s21_db min | 12.38 | 0.0001 | 0.0002 | edit:a2:118:add C n0-n6, 0.0063 | 0.0563 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0160 | T2 | s21_db min | 12.5845 | -0.0010 | -0.0435 | edit:a2:117:add R n0-n6, 0.0075 | 0.0575 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0161 | T2 | s21_db min | 12.978 | 0.0000 | 0.0003 | edit:a2:73:add C VOUT1-n4, 0.0636 | 0.1136 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0184 | T2 | s21_db min | 12.6056 | 0.0010 | 0.0017 | edit:a2:73:add C VOUT1-n4, 0.0093 | 0.0593 | no | - | - | - | - | - | - | no |
| t2-wb1020-gain-0207 | T2 | s21_db min | 11.1542 | 0.0003 | 0.0026 | edit:a2:102:add R n0-n1, 0.0784 | 0.1284 | no | - | - | - | - | - | - | no |
| v2b-wb0824-gain-188 | T3 | s21_db min | 11.3706 | 0.0000 | 0.0301 | edit:a2:78:add R VOUT1-n6, 0.0016 | 0.0516 | no | - | - | - | - | - | - | no |
| v2b-wb1020-noise-217 | T3 | nf_max_db max | 1.7022 | 0.0003 | 0.1085 | edit:a2:156:add R n4-n5, 0.0009 | 0.0509 | no | - | - | - | - | - | - | no |

## Nominated tasks: references and confirmation detail

