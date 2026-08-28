# Cross-PDK campaign: requirement vs achieved, per spec

Every best design after full sizing + escalation. "X" = gate missed. Idd=0.0 means microamps (dead circuit).

## sky130 (null, 14/24 run, wall-budget stop)

| spec | NF req/got (dB) | S21 req/got (dB) | S11 req/got (dB) | Idd req/got (mA) | feasible |
|---|---|---|---|---|---|
| cap-e01-wifi | 3.5 / 57.6 **X** | 10 / -51.6 **X** | -8 / -0.1 **X** | 15 / 0.0 | no |
| cap-e02-gpsband | 3.5 / 50.1 **X** | 10 / -44.1 **X** | -8 / -2.6 **X** | 15 / 0.0 | no |
| cap-e03-900mhz | 3.5 / 64.9 **X** | 10 / -58.9 **X** | -8 / -0.1 **X** | 15 / 0.0 | no |
| cap-e04-35ghz | 3.5 / 38.4 **X** | 12 / -32.4 **X** | -8 / -1.4 **X** | 15 / 0.0 | no |
| cap-e05-ism58 | 3.5 / 35.6 **X** | 10 / -29.6 **X** | -8 / -0.6 **X** | 15 / 0.0 | no |
| cap-e06-wifi | 3 / 57.6 **X** | 12 / -51.6 **X** | -10 / -0.1 **X** | 12 / 0.0 | no |
| cap-e07-gpsband | 3 / 50.8 **X** | 12 / -44.7 **X** | -10 / -2.3 **X** | 10 / 0.0 | no |
| cap-e08-wideband | 3.5 / 71.6 **X** | 10 / -65.6 **X** | n/a | 15 / 0.0 | no |
| cap-m01-wifi | 2.5 / 57.7 **X** | 12 / -51.7 **X** | -10 / -0.0 **X** | 5 / 0.0 | no |
| cap-m02-gpsband | 2.2 / 49.9 **X** | 14 / -43.8 **X** | -10 / -2.6 **X** | 5 / 0.0 | no |
| cap-m03-900mhz | 2.5 / 65.2 **X** | 14 / -59.2 **X** | -10 / -0.3 **X** | 6 / 0.0 | no |
| cap-m04-35ghz | 2.8 / 37.9 **X** | 14 / -31.9 **X** | -11 / -1.1 **X** | 6 / 0.0 | no |
| cap-m05-ism58 | 3.5 / 35.5 **X** | 12 / -29.5 **X** | -10 / -0.5 **X** | 10 / 0.0 | no |
| cap-m06-wifi | 2.2 / 57.7 **X** | 15 / -51.7 **X** | -12 / -0.0 **X** | 6 / 0.0 | no |

## gf180mcu (null, complete)

| spec | NF req/got (dB) | S21 req/got (dB) | S11 req/got (dB) | Idd req/got (mA) | feasible |
|---|---|---|---|---|---|
| cap-e01-wifi | 3.5 / 26.6 **X** | 10 / -21.1 **X** | -8 / -0.4 **X** | 15 / 0.0 | no |
| cap-e02-gpsband | 3.5 / 28.3 **X** | 10 / -22.8 **X** | -8 / -0.1 **X** | 15 / 0.0 | no |
| cap-e03-900mhz | 3.5 / 28.1 **X** | 10 / -21.9 **X** | -8 / -0.5 **X** | 15 / 0.0 | no |
| cap-e04-35ghz | 3.5 / 24.6 **X** | 12 / -18.9 **X** | -8 / -0.5 **X** | 15 / 0.0 | no |
| cap-e05-ism58 | 3.5 / 21.7 **X** | 10 / -16.2 **X** | -8 / -1.2 **X** | 15 / 0.0 | no |
| cap-e06-wifi | 3 / 26.5 **X** | 12 / -20.8 **X** | -10 / -0.3 **X** | 12 / 0.0 | no |
| cap-e07-gpsband | 3 / 28.3 **X** | 12 / -22.6 **X** | -10 / -0.1 **X** | 10 / 0.0 | no |
| cap-e08-wideband | 3.5 / 29.7 **X** | 10 / -23.6 **X** | n/a | 15 / 0.0 | no |
| cap-h01-wifi | 1.8 / 26.5 **X** | 16 / -21.0 **X** | -13 / -0.3 **X** | 4 / 0.0 | no |
| cap-h02-gpsband | 1.8 / 28.2 **X** | 16 / -22.9 **X** | -12 / -0.2 **X** | 3 / 0.0 | no |
| cap-h03-900mhz | 1.6 / 29.6 **X** | 17 / -23.6 **X** | -13 / -1.8 **X** | 4 / 4.2 **X** | no |
| cap-h04-35ghz | 1.8 / 24.6 **X** | 17 / -19.0 **X** | -14 / -0.5 **X** | 4 / 0.0 | no |
| cap-h05-ism58 | 2 / 21.6 **X** | 16 / -16.2 **X** | -13 / -1.1 **X** | 5 / 0.0 | no |
| cap-h06-wifi | 1.5 / 26.5 **X** | 18 / -20.9 **X** | -15 / -0.3 **X** | 5 / 0.0 | no |
| cap-h07-gpsband | 1.5 / 28.4 **X** | 20 / -22.9 **X** | -14 / -0.2 **X** | 3 / 0.0 | no |
| cap-h08-wideband | 2.5 / 29.7 **X** | 16 / -24.0 **X** | n/a | 5 / 0.0 | no |
| cap-m01-wifi | 2.5 / 26.6 **X** | 12 / -20.8 **X** | -10 / -0.3 **X** | 5 / 0.0 | no |
| cap-m02-gpsband | 2.2 / 28.3 **X** | 14 / -22.6 **X** | -10 / -0.1 **X** | 5 / 0.0 | no |
| cap-m03-900mhz | 2.5 / 24.0 **X** | 14 / -17.8 **X** | -10 / -1.0 **X** | 6 / 0.0 | no |
| cap-m04-35ghz | 2.8 / 24.5 **X** | 14 / -18.9 **X** | -11 / -0.5 **X** | 6 / 0.0 | no |
| cap-m05-ism58 | 3.5 / 21.7 **X** | 12 / -16.2 **X** | -10 / -1.2 **X** | 10 / 0.0 | no |
| cap-m06-wifi | 2.2 / 26.6 **X** | 15 / -20.7 **X** | -12 / -0.3 **X** | 6 / 0.0 | no |
| cap-m07-gpsband | 2 / 28.5 **X** | 15 / -22.8 **X** | -12 / -0.2 **X** | 4 / 0.0 | no |
| cap-m08-ism58 | 3 / 21.7 **X** | 14 / -16.2 **X** | -11 / -1.2 **X** | 8 / 0.0 | no |

## ihp_sg13g2 (null, still running)

| spec | NF req/got (dB) | S21 req/got (dB) | S11 req/got (dB) | Idd req/got (mA) | feasible |
|---|---|---|---|---|---|
| cap-e01-wifi | 3.5 / 2.2 | 10 / 23.1 | -8 / -9.9 | 15 / 2.3 | YES |
| cap-e02-gpsband | 3.5 / 2.2 | 10 / 25.9 | -8 / -11.0 | 15 / 9.8 | YES |
| cap-e03-900mhz | 3.5 / 1.9 | 10 / 28.1 | -8 / -9.1 | 15 / 3.5 | YES |
| cap-e04-35ghz | 3.5 / 2.3 | 12 / 15.2 | -8 / -8.1 | 15 / 3.4 | YES |
| cap-e05-ism58 | 3.5 / 2.1 | 10 / 11.1 | -8 / -8.1 | 15 / 4.9 | YES |
| cap-e06-wifi | 3 / 1.6 | 12 / 22.9 | -10 / -10.2 | 12 / 2.5 | YES |
| cap-e07-gpsband | 3 / 2.6 | 12 / 25.7 | -10 / -10.9 | 10 / 2.1 | YES |
| cap-e08-wideband | 3.5 / 2.7 | 10 / 10.2 | n/a | 15 / 2.1 | no |
| cap-m01-wifi | 2.5 / 1.8 | 12 / 25.8 | -10 / -10.5 | 5 / 2.1 | YES |
| cap-m02-gpsband | 2.2 / 1.5 | 14 / 28.7 | -10 / -10.1 | 5 / 3.2 | YES |
| cap-m03-900mhz | 2.5 / 2.4 | 14 / 33.4 | -10 / -10.4 | 6 / 3.2 | YES |
| cap-m04-35ghz | 2.8 / 2.1 | 14 / 15.1 | -11 / -11.0 | 6 / 4.2 | YES |

## sky130 arm-B selflearn GPU (6/24, wall-budget stop)

| spec | NF req/got (dB) | S21 req/got (dB) | S11 req/got (dB) | Idd req/got (mA) | feasible |
|---|---|---|---|---|---|
| cap-e01-wifi | 3.5 / 13.5 **X** | 10 / -8.7 **X** | -8 / -2.7 **X** | 15 / 0.0 | no |
| cap-e02-gpsband | 3.5 / 40.8 **X** | 10 / -35.7 **X** | -8 / -0.0 **X** | 15 / 0.0 | no |
| cap-e03-900mhz | 3.5 / 49.8 **X** | 10 / -44.9 **X** | -8 / -2.5 **X** | 15 / 0.0 | no |
| cap-e04-35ghz | 3.5 / 7.9 **X** | 12 / -3.6 **X** | -8 / -9.3 | 15 / 4.9 | no |
| cap-e05-ism58 | 3.5 / 14.4 **X** | 10 / -6.7 **X** | -8 / -1.1 **X** | 15 / 1.6 | no |
| cap-e06-wifi | 3 / 12.0 **X** | 12 / -7.5 **X** | -10 / -3.3 **X** | 12 / 0.0 | no |

## Reading

sky130 and gf180mcu best designs are not near-misses; they are dead circuits
(zero bias current, negative gain, no input match). Two environment defects
explain the whole matrix; neither is process physics:

1. **Inductor values pinned to the channel-length literal on foreign PDKs.**
   Every foreign-PDK design has every inductor at exactly the PDK's fixed MOS
   channel length read as henries: sky130 150 nH, gf180 280 nH, ihp 130 nH.
   On bptm45 inductors size normally (e.g. 10.4 nH / 6.8 nH). The sizer never
   controlled a single inductor on any foreign PDK.
2. **Gate bias is a fixed 0.5 V literal on every PDK.** pVB=0.5 in every
   design, no sizable bias-voltage params. 0.5 V is above threshold on bptm45
   (45 nm, Vth~0.45) and IHP sg13g2 LV (Vth~0.45) -> circuits conduct; below
   threshold on sky130 1.8V (Vth~0.7) and gf180 3.3V (Vth~0.75) -> subthreshold,
   Idd ~ microamps, S21 negative, NF numbers meaningless.

IHP hit 11/12 *despite* carrying bug 1 (its winning designs worked around
130 nH chokes), which is why it looked like "physics vs setup" split. It is
setup on both counts.
