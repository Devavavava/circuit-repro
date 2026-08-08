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
CC2 n2 n3 {pC2V}
CC3 VDD n5 {pC3V}
CC4 n5 n6 {pC4V}
CC5 VDD n0 {pC5V}
CC6 n0 VOUT1 {pC6V}
LL1 VDD nqL1 {pL1V}
RQL1 nqL1 n5 {pINDW0*pL1V/pINDQ}
LL2 VDD nqL2 {pL2V}
RQL2 nqL2 n0 {pINDW0*pL2V/pINDQ}
MNM1 n2 n1 0 0 nmos W={pNM1W} L={pNM1L}
MNM2 n4 n3 0 0 nmos W={pNM2W} L={pNM2L}
MNM3 n5 VDD n4 0 nmos W={pNM3W} L={pNM3L}
MNM4 n0 n6 0 0 nmos W={pNM4W} L={pNM4L}
RR1 n2 n1 {pR1V}
RR2 VDD n2 {pR2V}

* Dataset topologies are textbook schematics: they show the signal path
* but omit biasing, so nodes reachable only through capacitors have no
* DC path and the OP solve goes singular. rshunt ties every node to
* ground through 1e12 ohm -- enough for a DC solution, negligible at RF.
* Without it, 9 of 26 dataset LNAs fail to simulate at all.
.option rshunt=1e12
.param pC1V=5.904e-12 pC2V=1.17966e-12 pC3V=5.88376e-13 pC4V=1.27373e-12 pC5V=7.42121e-13 pC6V=3.99511e-12 pINDQ=12 pINDW0=1.25664e+10 pL1V=1.35149e-08 pL2V=1.09428e-08 pNM1L=45n pNM1W=4.51335e-05 pNM2L=45n pNM2W=2.97338e-05 pNM3L=45n pNM3W=1.39629e-05 pNM4L=45n pNM4W=2.85493e-05 pR1V=233.199 pR2V=314.251 pVB=0.5 pVDD=1.1
.control
op
let idd = -i(Vsup)
print idd
sp lin 101 1.1e+09 2.5e+09 1
let s11db = db(mag(S_1_1)+1e-30)
let s21db = db(mag(S_2_1)+1e-30)
meas sp m_s11_f0 find s11db at=1.57542e+09
meas sp m_s11_max max s11db from=1.1e+09 to=2.5e+09
meas sp m_s21_f0 find s21db at=1.57542e+09
meas sp m_s21_min min s21db from=1.1e+09 to=2.5e+09
meas sp m_s21_max max s21db from=1.1e+09 to=2.5e+09
noise v(p2) Vp1 lin 51 1.1e+09 2.5e+09
setplot noise1
let nfv = 10*log10((inoise_spectrum*inoise_spectrum)/8.283894e-19)
let m_nf_f0 = nfv[17]
print m_nf_f0
.endc
.end
