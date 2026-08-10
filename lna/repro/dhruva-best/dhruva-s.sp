* Auto-generated from an AnalogGenie topology by lna/to_spice.py
* Device values are placeholders exposed as .param for a sizing loop.

.include C:/Users/Devavrat/circuit-repro/.claude/worktrees/lna-data/AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt


Vsup VDD 0 dc {pVDD}

* port 1: RF input, DC-blocked so bias is not shorted to 50 ohm
Vp1 p1 0 dc 0 ac 1 portnum 1 z0 50
Cp1 p1 VIN1 10p
* port 2: RF output
Cp2 VOUT1 p2 10p
Vp2 p2 0 dc 0 ac 0 portnum 2 z0 50

CC1 VIN1 n1 {pC1V}
CC2 n11 0 {pC2V}
CC3 n1 n8 {pC3V}
CC4 n7 n10 {pC4V}
CC5 n0 n4 {pC5V}
CC6 n5 VOUT1 {pC6V}
CC7 n1 n9 {pC7V}
CC8 n6 n3 {pC8V}
LL1 n1 nqL1 {pL1V}
RQL1 nqL1 0 {pINDW0*pL1V/pINDQ}
LL2 n2 nqL2 {pL2V}
RQL2 nqL2 n6 {pINDW0*pL2V/pINDQ}
MNM1 n7 n11 n1 0 nmos W={pNM1W} L={pNM1L} NF={max(1,ceil(pNM1W/2e-06))}
MNM2 n0 n8 0 0 nmos W={pNM2W} L={pNM2L} NF={max(1,ceil(pNM2W/2e-06))}
MNM3 n0 n10 0 0 nmos W={pNM3W} L={pNM3L} NF={max(1,ceil(pNM3W/2e-06))}
MNM4 n6 n4 0 0 nmos W={pNM4W} L={pNM4L} NF={max(1,ceil(pNM4W/2e-06))}
MNM5 n0 n9 0 0 nmos W={pNM5W} L={pNM5L} NF={max(1,ceil(pNM5W/2e-06))}
MNM6 n5 n3 0 0 nmos W={pNM6W} L={pNM6L} NF={max(1,ceil(pNM6W/2e-06))}
RR1 VDD n7 {pR1V}
RR2 VDD n0 {pR2V}
RR3 VDD n2 {pR3V}
RR4 VDD n5 {pR4V}

* Dataset topologies are textbook schematics: they show the signal path
* but omit biasing, so nodes reachable only through capacitors have no
* DC path and the OP solve goes singular. rshunt ties every node to
* ground through 1e12 ohm -- enough for a DC solution, negligible at RF.
* Without it, 9 of 26 dataset LNAs fail to simulate at all.
.option rshunt=1e12
.param pC1V=3.56177e-12 pC2V=3.05182e-12 pC3V=1e-11 pC4V=1e-11 pC5V=1e-11 pC6V=1e-11 pC7V=1e-11 pC8V=1e-11 pINDQ=12 pINDW0=1.25664e+10 pL1V=8.45196e-09 pL2V=1.5e-08 pNM1L=45n pNM1W=1.48113e-05 pNM2L=45n pNM2W=5.30586e-05 pNM3L=45n pNM3W=6.60048e-06 pNM4L=45n pNM4W=3.66014e-05 pNM5L=45n pNM5W=2.32071e-05 pNM6L=45n pNM6W=2.90982e-05 pR1V=830.29 pR2V=157.161 pR3V=50 pR4V=74.1868 pVB=0.5 pVDD=1.1
.control
op
let idd = -i(Vsup)
print idd
sp lin 101 1.1e+09 2.5e+09 1
let s11db = db(mag(S_1_1)+1e-30)
let s21db = db(mag(S_2_1)+1e-30)
meas sp m_s11_f0 find s11db at=2.49203e+09
meas sp m_s11_max max s11db from=1.1e+09 to=2.5e+09
meas sp m_s21_f0 find s21db at=2.49203e+09
meas sp m_s21_min min s21db from=1.1e+09 to=2.5e+09
meas sp m_s21_max max s21db from=1.1e+09 to=2.5e+09
let s11m = mag(S_1_1)
let s22m = mag(S_2_2)
let s12s21 = mag(S_1_2*S_2_1)
let dlt = S_1_1*S_2_2 - S_1_2*S_2_1
let dltm = mag(dlt)
let kk = (1 - s11m*s11m - s22m*s22m + dltm*dltm)/(2*s12s21 + 1e-30)
let mul = (1 - s11m*s11m)/(mag(S_2_2 - dlt*conj(S_1_1)) + s12s21 + 1e-30)
let mus = (1 - s22m*s22m)/(mag(S_1_1 - dlt*conj(S_2_2)) + s12s21 + 1e-30)
let s22db = db(s22m+1e-30)
let s12db = db(mag(S_1_2)+1e-30)
meas sp m_k_f0 find kk at=2.49203e+09
meas sp m_k_min min kk from=1.1e+09 to=2.5e+09
meas sp m_mu_f0 find mul at=2.49203e+09
meas sp m_mu_min min mul from=1.1e+09 to=2.5e+09
meas sp m_mus_f0 find mus at=2.49203e+09
meas sp m_mus_min min mus from=1.1e+09 to=2.5e+09
meas sp m_delta_f0 find dltm at=2.49203e+09
meas sp m_delta_max max dltm from=1.1e+09 to=2.5e+09
meas sp m_s22_f0 find s22db at=2.49203e+09
meas sp m_s12_f0 find s12db at=2.49203e+09
.endc
.end
