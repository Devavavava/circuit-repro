# wideband-sdr spec recalibration — raw record (Session 6, 2026-08-09)

Raw run record for FINDINGS §22. Blind protocol: Kanchetla et al. IEEE TMTT
2022 (NavIC/GPS receiver) hard-excluded from all sourcing — not searched, not
cited, not used anywhere below.

## Literature survey (3 parallel agents, 44 sources checked, 12 kept)

See `lna/specs/wideband-sdr.yaml` header comment for the same table inline
with the spec, and FINDINGS §22.1 for the formatted version. Full per-source
notes (secondary-source confidence flags, DOIs, exact search queries) live in
the three agents' transcripts; summarized findings below.

Kept (measured silicon, ~0.1-3 GHz class, S11 / gain / NF-min / power@native-Vdd / inductors / process):

```
Bruccoleri+Klumperink+Nauta   JSSC'04    0.01-1.6GHz   S11<-10   13.7dB  NF<2.4dB  35mW@2.5V   0L  0.25um
Blaakmeer+Klumperink+al       JSSC'08    0.3-3.5GHz    S11<-14   15dB    NF~3.0dB  21mW@1.2V   0L  65nm
Amer+Hegazi+Ragaie*           JSSC'07    0.1-3.85GHz   S11<-10   12.1dB* NF 8.4dB* 9.8mW@1.2V  ?L  90nm
Woo+Kim+Lee+Kim+Laskar        TMTT'12    0.3-0.92GHz   S11<-10   21dB    NF 2.0dB  3.6mW       0L  0.18um
Arshad+Ramzan+Wahab           IntegVLSI'18 50-830MHz   S11-8.9   17dB    NF 2.2dB  n/a         0L  130nm
Chen+Liu+Boos+Niknejad        JSSC'08    0.8-2.1GHz    n/a       >=14.5  NF<2.6dB  17.4mW@1.5V 0L  0.13um
Liu+Boon+Dong                 TCASI'24   0.2-2.85GHz   n/a       20dB    NF 2.9dB  1.74mW@0.6V 0L  28nm
Parvizi+Allidina+El-Gamal     TMTT'16    0.1-2.2GHz    n/a       12.3dB  NF 4.9dB  0.4mW@1V    0L  130nm
De Souza+Mariano+Taris        TCASI'17   ~2.2GHz BW    n/a       21.1dB  NF 2.0dB  7mW(HL)     0L  130nm
Sobhy+Helmy+Hoyos+al          TMTT'11    0.1-1.77GHz   RL>10dB   23dB    NF 1.85dB 2.8mW@2V    0L  90nm
Zhang+Bai+Huang               JSemi'13   0.3-0.9GHz    n/a       12.2-15.2 NF 2.3dB 12.6mW@1.8V 0L  0.18um
Bevilacqua+Niknejad (UWB ctx) JSSC'04    3.1-10.6GHz   S11<-10   9.3dB   NF 4.0dB  9mW         nL  0.18um
```
* Amer is a merged LNA+downconverter chain (gain/NF are chain-level, S11/band only usable).

Explicitly excluded as SIMULATED-only (found, verified as sim-only, not used):
  - Khabbaz/Sobhi/Koozehkanani, AEU 2018 (post-layout sim, 0.18um, claimed 2.8dB NF)
  - unnamed Microelectronics Journal 2024 CSNC+cascode (post-layout sim, 40nm, claimed 1.35-1.72dB NF)
  - Wang/Wang EDSSC 2007 TV-tuner LNA (IEEE Xplore "Notice of Removal")

Not found / not usable despite targeted search (flagged, not guessed):
  - No genuine Belostotski/Haslett resistive-feedback or noise-cancelling wideband LNA located
    (their one verified wideband design, JSSC 2007, is inductively degenerated w/ 4-5 inductors)
  - No "Guan & Nguyen resistive-feedback wideband LNA" paper locatable under that author pair

## Spec diff

```
OLD constraints:
  nf_db:         {max: 3.5}
  s11_db:        {max: -10}      <- gates extract.py's AT-F0 value only
  s21_db:        {min: 12}
  s21_ripple_db: {max: 2}
  idd_ma:        {max: 8}

NEW constraints:
  nf_db:         {max: 3.5}      unchanged
  s11_max_db:    {max: -10}      metric FIXED (was s11_db); value unchanged
  s21_db:        {min: 14}       TIGHTENED from 12
  s21_ripple_db: {max: 2}        unchanged
  idd_ma:        {max: 8}        unchanged
```

## Re-judging script + output (recompute from stored `metrics`, no re-simulation)

```python
import sys, json, yaml
sys.path.insert(0, 'lna')
from spec import Spec
import datastore as ds

new = Spec.load('lna/specs/wideband-sdr.yaml')
old = Spec(yaml.safe_load('''
name: wideband-sdr
constraints:
  nf_db: {max: 3.5}
  s11_db: {max: -10}
  s21_db: {min: 12}
  s21_ripple_db: {max: 2}
  idd_ma: {max: 8}
  iip3_dbm: {min: 0, status: unsupported}
objectives: []
topology: {differential: false, allow_inductorless: true}
'''), source='<old-inmem-HEAD>')

rows = [json.loads(l) for l in open('lna/data/topo_labels.jsonl', encoding='utf-8')
        if l.strip() and json.loads(l).get('spec') == 'wideband-sdr']
# (134 L2 rows as of this session)
```

Output (verbatim):

```
=== OLD spec (git HEAD, as literally implemented) ===
OLD: feasible 0/134  best_total_violation=1.3745  wl=eb6c31c8dc22
   viol breakdown: {'nf_db': 0.5722, 's21_ripple_db': 0.8024}

=== NEW spec (recalibrated) ===
NEW: feasible 0/134  best_total_violation=2.0554  wl=f2f10647ec88
   viol breakdown: {'nf_db': 0.8321, 's11_max_db': 0.9899, 's21_db': 0.0322, 's21_ripple_db': 0.2012}
```

`eb6c31c8dc22` (the old record-holder) metrics: `s11_db=-17.71 s11_max_db=-3.61
s21_db=12.02 ripple=3.60 nf=5.50 idd=3.07` — passes the old spot-S11 check by
7.7 dB of margin while missing the true worst-case-over-band value by 6.4 dB.

`f2f10647ec88` (the new record-holder; evolve gen-20, move `stage_remove` per
`nf_moves.py`/`evolve.py` provenance) metrics: `s11_db=-1.37 s11_max_db=-0.10
s21_db=13.55 ripple=2.40 nf=6.41 idd=1.55` — essentially unmatched even in the
old spot sense, but wins on the new total because it's cheapest on the other
three axes combined.

## Per-constraint pass rate over 134 rows (old value vs new)

```
s11_db <= -10        : 29/134  (22%)   <- old, wrong gate
s11_max_db <= -10     :  0/134  ( 0%)   <- new, correct gate -- NEVER once cleared
nf_db <= 3.5           :  0/134  ( 0%)   unchanged (best-ever 4.04 dB)
s21_db >= 12  (old)    : 21/134  (16%)
s21_db >= 14  (new)    :  6/134  ( 4%)
s21_ripple_db <= 2      : 27/134  (20%)  unchanged
idd_ma <= 8             :109/134  (81%)  unchanged, never the binding constraint
```

Top 5 closest designs under the NEW spec (by total normalized violation):

```
wl=f2f10647ec tv=2.055 arch=evolve-evolve       s11max=-0.10 s21=13.55 ripple=2.40 nf=6.41 idd=1.55
wl=b98fc16139 tv=2.105 arch=evolve-random       s11max=-1.31 s21= 7.36 ripple=2.07 nf=6.04 idd=7.76
wl=eb6c31c8dc tv=2.155 arch=nf-campaign          s11max=-3.61 s21=12.02 ripple=3.60 nf=5.50 idd=3.07
wl=3868a99288 tv=2.218 arch=rfb_shunt_peak_bf0_cc0 s11max=-0.83 s21= 8.56 ripple=0.76 nf=6.69 idd=4.66
wl=eb6c31c8dc tv=2.257 arch=nccgcs_wb_s0         s11max=-3.55 s21=14.17 ripple=3.69 nf=6.19 idd=2.70
```

## Regression (before/after edit, identical both times)

```
python lna/calibrate_specs.py            -> ALL ACCEPTANCE CRITERIA MET (114/192, 32/41, 94.1%, 0/4)
python lna/pipeline_yield.py --indices 461-492,1081-1090  -> 40/42 (95.2%), only 1081 singular matrix
"<analoggenie python>" lna/test_vocab_matches_upstream.py -> MATCH
python lna/ref/check_ref.py    -> GREEN
python lna/ref/check_nf.py     -> GREEN
python lna/ref/check_stab.py   -> GREEN
python lna/ref/check_bjt.py    -> GREEN
python lna/spec.py --all       -> all 8 specs OK
```
