"""WP-PGAIN: append this work package's blocks to the three shared docs.

Append-only, re-reads each file at write time, inserts exactly one block per
file at a located anchor. Run once; `--check` reports whether the blocks are
already present.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

FIND = """
## 42. Phase 3 - WP-PGAIN: ★★★ Gate **D6** (gain programmability) - MET under a proposed mapping, and the band-match wall that decides *where* gain control is allowed to live (Session 9, 2026-08-13)

Tier-3's second item (`plans2/14-DHRUVA-SIMUL.md` SS1.2: gain range >= 10.6 dB
in >= 3 steps, "NOT ATTEMPTED - no switchable DOFs in the search space") is now
measured. Driver `lna/pgain.py` + `lna/_pgain_mech.py`; artefacts
`lna/out/pgain_*.json`. Nothing in the core design was resized: the shipped
`dhruva-l5.params.json` (and, as a second substrate, the WP-HARDEN
`dhruva-simul.params.json` of SS36) are read verbatim.

### 42.1 The proposed gate mapping - **needs user sign-off before D6 may be called met**

Same class of decision as the program's S21-for-voltage-gain mapping, and
recorded the same way - proposed, not adopted:

> **"Programmable"** = ONE fixed netlist and ONE fixed set of device sizes,
> whose states differ **only** in designated control-voltage parameters
> (`pVSWG*`) on the gates of inserted MOS switch devices. The switches are
> `nmos` instances from the same 45 nm card, emitted multi-finger
> (`w_finger = 2 um`) exactly like every other device in the deck - no
> ideal-switch elements, no per-state re-sizing, no per-state device values.
>
> **Gate D6 is MET iff, on one such netlist:**
> 1. >= 3 gain steps (>= 4 states), gain **monotonic** in the state index at
>    every band f0;
> 2. **span** (max-gain state - min-gain state) **>= 10.6 dB at every band f0**;
> 3. in **every** state: S11 <= -10 dB held over the whole 1.1-2.5 GHz range,
>    and Idd <= 13 mA;
> 4. the **max-gain** state still passes the full D4-SIM gate set on all four
>    bands (S21 >= 30/25.4/22.3/22.3 dB, NF <= 3.5/2.7/2.5/2.5 dB) - a
>    programmable LNA that lost the benchmark in its top state has not gained
>    programmability, it has traded it away;
> 5. NF is gated at the **max-gain state only**; lower-state NF is reported,
>    not gated (the paper's NF is a high-gain number).
>
> K_min is reported per state (advisory, as everywhere in this program).

Clause 4 is the only part that goes beyond the task's framing, and it is the
clause that keeps this honest: without it, any mechanism can "pass" by
degrading the top state until a span appears.

### 42.2 A harness-integrity finding that had to be fixed first: **`prepared_body` node names are not stable across processes**

`size.prepared_body()` -> `to_spice` renumbers internal nodes from a set/dict
walk, so the *same topology* emits **different node names in different Python
processes**. Measured, four consecutive processes, same `tokens.json`:

| process | `CC1 VIN1 ...` | recombine node (MNM2 drain) | MNM6 gate |
|---|---|---|---|
| 1 | `n2` | `n0` | `n8` |
| 2 | `n4` | `n2` | `n6` |
| 3 | `n2` | `n6` | `n7` |
| 4 | `n5` | `n3` | `n9` |

Element names (`CC1..CC8`, `LL1/LL2`, `MNM1..MNM6`, `RR1..RR4`) and the fixed
nets (`VIN1`, `VOUT1`, `p1`, `p2`, `VDD`) **are** stable. Consequence: any
post-processing that inserts elements by literal *node* name attaches to a
random node and its numbers are void - the symptom that exposed it was one
deck text giving 35.94 / 30.26 / 25.24 dB S21 in three different processes
while the untouched design replayed at exactly 35.961 every time. A first
(discarded) WP-PGAIN draft had inserted every mechanism this way.
`_pgain_mech.resolve_nodes()` therefore resolves each circuit role from the
element lines and **cross-checks every role against a second element that must
touch it** (e.g. the recombine node must be MNM2's *and* MNM3's *and* MNM5's
drain *and* RR2's load), raising rather than guessing if the topology contract
ever drifts. This is worth knowing for every future insertion tool, not just
this one.

### 42.3 Where this circuit may be loaded at all - the mechanism-independent map

An **ideal** 10 pF-blocked shunt resistor at each circuit role, R swept, at the
D4-SIM point (`lna/pgain.py --probe`). Cell = gain drop (dB) / S11_max (dB)
over 1.1-2.5 GHz; the gate is that the second number stays <= -10:

| role | R = 1 kOhm | 100 Ohm | 50 Ohm | 20 Ohm | 5 Ohm |
|---|---|---|---|---|---|
| input combiner | 0.32 / **-10.68** | 2.79 / -12.36 | 4.78 / **-9.00** | 8.01 / -4.41 | 10.19 / -1.50 |
| MNM2 gate | 0.30 / -10.61 | 2.58 / -11.76 | 4.31 / **-8.79** | 6.46 / -4.68 | 6.91 / -1.66 |
| CG drain | 0.91 / -10.35 | 2.05 / -10.87 | 2.19 / -10.94 | 2.29 / -10.99 | **2.35** / -11.01 |
| **recombine (n0)** | 0.39 / **-9.64** | 3.78 / -7.54 | 6.64 / -6.50 | 11.15 / -5.65 | 14.52 / -5.47 |
| tank drain | 0.68 / **-9.87** | 5.10 / -8.69 | 8.10 / -8.05 | 12.50 / -7.37 | 15.60 / -6.89 |
| MNM6 gate | 0.66 / **-9.87** | 5.05 / -8.65 | 8.07 / -7.99 | 12.51 / -7.30 | 15.65 / -6.82 |
| **output-stage drain** | 0.30 / -10.01 | 2.65 / -10.11 | 4.65 / -10.17 | 7.98 / -10.27 | **10.35 / -10.36** |
| VOUT1 | 0.28 / -10.01 | 2.53 / -10.10 | 4.42 / -10.16 | 7.57 / -10.24 | 9.74 / -10.32 |

The design's S11 margin is 0.001 dB (SS35.3), so this table is close to a
yes/no map. **Every node from the input combiner through MNM6's gate is
match-forbidden**: loading them moves the input match by more than its entire
margin - in the recombine/tank/gate cases before it has moved the gain by even
1 dB. **Only the output stage's drain and VOUT1 tolerate loading** - and there
the match *improves* monotonically (-10.01 -> -10.36), because the loading
damps a network the match was riding on. The physical reason the forbidden set
is so large is the two 94 um CS devices (MNM2/MNM5), whose C_gd couples the
recombine node straight back to the input node, plus the CC5->CC8 capacitive
chain forward of it.

### 42.4 The mechanism table - five mechanisms, three walls (`lna/pgain.py --wall`)

Authority swept from nothing to the spec's own box limit; the "largest
match-legal span" column is the most gain range obtainable while **every**
state still holds S11 <= -10 dB band-wide and Idd <= 13 mA. Coarse band
`dhruva-l5`; series resistors pinned at the box's 50 Ohm floor, i.e. at their
most favourable value, so a wall here is the mechanism's and not the sweep's:

| mechanism (task label) | where | largest **match-legal** span | what it costs to reach 10.6 dB |
|---|---|---|---|
| `in-att` (a) shunt attenuator bank | input combiner | **0.00 dB** | S11 **-3.23** (breaks by 6.77 dB) |
| `in-degen` (a') source-degeneration ladder | MNM2/MNM5 sources | **2.59 dB** | unreachable - 2.73 dB is the ceiling |
| `n0-bank` (b) load bank, switch-as-element | **recombine n0** | **0.00 dB** | S11 **-5.37** (breaks by 4.63 dB) |
| `n0-bank-r` (b) same, literal series-R bank | recombine n0 | **0.00 dB** | S11 **-5.38** (breaks by 4.62 dB) |
| `out-bank` (b') the same bank, moved | output-stage drain | **18.13 dB** | S11 -10.003 - **holds** |
| `out-bank-r` (b') same, literal series-R bank | output-stage drain | 9.06 dB | unreachable - the 50 Ohm box floor caps it at 9.06 dB |
| `out-bank2` (b'') bank split drain + VOUT1 | both | **25.48 dB** | holds |
| `bypass` (c) switch-bypass of stage MNM6 | around MNM6 | **0.00 dB** on the l5 point | Idd 13.64 mA at the *smallest* switch |
| `bypass` (c) on the **SS36 hardened** point | around MNM6 | **26.34 dB** | holds (Idd 9.02 mA of 13) |

Three separate walls, each a different constraint:

1. **The match wall** (mechanisms a, b). Every gain-control point *inside* the
   amplifier is match-forbidden. For the recombine node - the task's own
   candidate (b) - there is **no setting at all** that is legal: even the
   smallest in-box switch (1 um, R_on ~ 200 Ohm) already sits at S11 =
   -7.90 dB, and 10.6 dB of range costs **4.63 dB of match**. For the input
   combiner it is worse - the *all-off* state alone breaks the gate by
   0.033 dB, from nothing but the off-capacitance of three 1 um switches hung
   on a node whose match margin is 0.001 dB.
2. **The authority wall** (mechanism a', and the literal-resistor readings).
   Source degeneration under the CS pair holds the match comfortably but can
   only move the gain 2.7 dB, because those two 94 um devices carry less of
   this design's gain than their size suggests. And any bank built from a
   *series resistor* is capped by the spec's own 50 Ohm R floor plus the 10 pF
   block's own 13.5 Ohm of reactance at 1.18 GHz - hence `out-bank-r`'s 9.06 dB
   ceiling versus `out-bank`'s 18.13 dB when the triode switch itself is the
   bank element.
3. **The Idd wall** (mechanism c). Stage-bypass is impossible on the D4-SIM
   point for a reason that has nothing to do with gain: that point runs at
   12.963 mA against a 13 mA cap, and the bypass switches' own DC leakage adds
   0.67 mA. On the SS36 hardened point (8.205 mA, 4.8 mA of headroom) the same
   mechanism is legal and enormous. (A first build of it was worse still -
   17 mA - because the bypass switch DC-coupled the output drain onto MNM6's
   gate; the shipped build DC-blocks it. Recorded because the defect was real
   and measured, not because it survived.)

### 42.5 The result - Gate D6 MET (under SS42.1), on the designated D4-SIM point

`out-bank`: three cumulative branches on the **output-stage drain**, each a
10 pF DC block in series with an NMOS switch (W = 8 / 8 / 16 um, L = 45 nm,
multi-finger, all inside the spec's own W box), gates driven by
`pVSWGOB{1,2,3}` at the deck's own rails (0 V / 1.1 V). One netlist, one set of
device sizes, **states differ only in those three control voltages**. Sized for
equal steps by `pgain.descent` (3 starts, 300 coarse evaluations, switch DOFs
only; the core's 20 params are never touched).

**Substrate: `dhruva-l5` (the SS35.3 designated D4-SIM point), unresized.**

| state | controls (V) | S21 @ S | @ L1 | @ L2 | @ L5 | S11_max (1.1-2.5 GHz) | Idd | K_min | NF @ S/L1/L2/L5 |
|---|---|---|---|---|---|---|---|---|---|
| **S0** (max) | 0,0,0 | **33.66** | **35.48** | **35.88** | **35.91** | **-10.004** | 12.963 | 20.1 | **0.867 / 0.995 / 1.196 / 1.253** |
| S1 | 1.1,0,0 | 29.22 | 30.87 | 31.17 | 31.18 | -10.176 | 12.963 | 59.3 | (not gated) |
| S2 | 1.1,1.1,0 | 26.28 | 27.87 | 28.13 | 28.13 | -10.251 | 12.963 | 98.5 | (not gated) |
| S3 (min) | 1.1,1.1,1.1 | 22.44 | 24.09 | 24.43 | 24.45 | -10.317 | 12.963 | 172.7 | (not gated) |
| **span** | | **11.23** | **11.39** | **11.45** | **11.46** | | | | |

All five clauses pass: 3 steps OK - monotonic on all four bands OK - span
11.23-11.46 dB >= 10.6 OK - S11 <= -10 dB band-wide in every state OK - Idd
12.963 mA **identical in every state** (the bank is DC-blocked, so the
operating point is literally untouched) OK - max-gain state passes every D4-SIM
gate with its NF unchanged from SS35.2 to three decimals OK.
**Replay fence: 3/3 repeats, spread 0.0000 on every gated metric across all
4 states x 4 bands.** `out-bank` has 18.13 dB of match-legal authority
available, so the 10.6 dB requirement is met with 6.7 dB of mechanism margin,
not at the edge of what the mechanism can do.

**Second substrate: the SS36 hardened point (`dhruva-simul`), same mechanism,
re-sized switches** - reported because it is strictly more comfortable:

| state | S | L1 | L2 | L5 | S11_max | Idd | K_min | NF @ S/L1/L2/L5 |
|---|---|---|---|---|---|---|---|---|
| **S0** (max) | 31.93 | 32.21 | 31.58 | 31.43 | **-11.011** | 8.205 | 17.6 | 1.331 / 1.459 / 1.667 / 1.726 |
| S1 | 28.82 | 28.99 | 28.27 | 28.10 | -11.027 | 8.205 | 66.7 | |
| S2 | 24.71 | 24.78 | 23.99 | 23.82 | -11.035 | 8.205 | 163.2 | |
| S3 (min) | 19.94 | 20.09 | 19.38 | 19.23 | -11.038 | 8.205 | 345.7 | |
| **span** | **11.99** | **12.13** | **12.19** | **12.21** | | | | |

Same verdict, now with 1.01 dB of S11 margin instead of 0.004 dB and 4.8 mA of
Idd headroom instead of 0.037 mA. Replay 3/3, spread 0.0000. The stage-bypass
mechanism on this substrate reaches a 39.5-42.7 dB span with the match held
(S0 30.39/32.09/31.89/31.80, S3 -12.35/-8.90/-7.80/-7.67, S11 -10.44...-10.93,
Idd <= 9.016 mA, replay 3/3 spread 0.0000) - far more range than the spec asks
for, at the cost of an S-band max-gain margin of only 0.39 dB.

### 42.6 What this does **not** close - read this before quoting the pass

1. **The pass buys gain range, not linearity, and the paper's spec is about
   linearity.** Every mechanism that holds the band-wide match sits *after*
   the last gain stage, so in the low-gain states the front end still sees the
   full input and still compresses identically; an output-side attenuator
   moves OIP3 down with the gain and leaves IIP3 **unchanged**. The paper
   specifies IIP3 *at the minimum-gain setting* (SS1.2), i.e. it expects the
   low-gain state to be the *linear* state. The mechanisms that would deliver
   that - input attenuation, degeneration, recombine-node load (SS42.4 rows
   a/a'/b) - are exactly the ones this design's 0.001 dB match margin forbids.
   **So D6 as mapped is met and the spirit of the paper's programmability is
   not**, and the honest reading of SS42.3 + SS42.4 together is that *this
   topology cannot host front-end gain control at all* at its present match
   margin. That is a topology/margin finding, not a switch-sizing one, and it
   is the real result of this work package.
2. **D5 is untouched.** No IIP3 was measured here; nothing above changes that.
3. **The max-gain S11 margin on the l5 substrate is 0.004 dB** - better than
   the untouched design's 0.001 dB (the off-state bank marginally helps the
   match), but still knife-edge in exactly the SS39 sense. The hardened
   substrate's 1.01 dB is the answer to that, not this work package.
4. **Fidelity caveats carry over verbatim** from SS35.5 / REPORT SS5: 45 nm
   behavioral BSIM4, ideal passives at Q = 12, no corners, no package or layout
   parasitics, S21-into-50-Ohm as the gain mapping. In particular the switch
   devices use the same behavioural card as the signal devices and carry **no
   layout-dependent R_on, no well/substrate coupling and no control-line
   routing** - a real switched bank pays all three.
5. **The state count is the minimum the spec asks for** (4 states / 3 steps).
   Nothing here explores whether a finer ladder stays monotonic.
"""

JOUR = """
## 37. WP-PGAIN - the gain-programmability gate falls, and the map of where this amplifier is allowed to be touched

**The stage.** Tier-3 item two: gain programmability, >= 10.6 dB in >= 3 steps
(`plans2/14-DHRUVA-SIMUL.md` SS1.2, upgrade #6), recorded since stage 30 as
"NOT ATTEMPTED - no switchable DOFs". The task came with its own framing
attached: *propose* what "programmable" means, do not assume it.

**The decision, and who made it.** The mapping in FINDINGS SS42.1 is
**proposed by this executor and awaits user sign-off** - deliberately the same
shape as the program's earlier S21-for-voltage-gain decision, and written down
before any measurement so it could not be shaped by the answer. One netlist,
one set of device sizes, states differing *only* in control voltages on
inserted MOS switch gates. The one clause added beyond the brief is clause 4:
the max-gain state must still pass the whole D4-SIM gate set. Without it every
mechanism can manufacture a span by ruining its own top state, and the gate
would measure nothing.

**What actually happened first was a harness defect.** A prior stopped agent
had left a draft that inserted switches by literal node name. Those names are
not stable: `size.prepared_body` renumbers internal nodes per *process*, so the
same deck text measured 35.94, 30.26 and 25.24 dB of gain in three consecutive
runs while the untouched design replayed at 35.961 exactly. Everything in that
draft was void, and the replacement resolves every circuit role structurally
from element names, cross-checking each one against a second element that must
touch it. The lesson is bigger than this work package: **element names are the
contract, node names are an implementation detail**, and every future
netlist-post-processing tool in this tree needs to know it.

**The result.** Gate **D6 MET** under the proposed mapping, on the designated
D4-SIM point, unresized: four states, spans 11.23-11.46 dB across the four
bands, S11 <= -10 dB held band-wide in every state, Idd 12.963 mA *identical*
in every state, max-gain state unchanged from SS35.2 on every gate including
NF, replay 3/3 spread 0.0000. The mechanism is a three-branch switched bank on
the output stage's drain; the switches are 8/8/16 um NMOS inside the spec's own
sizing box, and the three states are three gate voltages at the rails.

**The understanding - which matters more than the pass.** Five mechanisms were
built and swept, and the interesting output is not the one that worked but the
map of the four that did not. This amplifier has a **0.001 dB** band-wide match
margin, and that margin turns out to be a *spatial* constraint: the input
combiner, the recombine node, the tuned-stage drain and the output stage's gate
are all match-forbidden - loading the recombine node by enough to move the gain
10.6 dB costs 4.63 dB of match, and loading the input combiner costs 6.77 dB.
Only the output stage's drain and VOUT1 tolerate loading at all, and there the
match *improves*. So the gain control had nowhere to go but the very back of
the amplifier - and gain control at the back of an amplifier buys range without
buying linearity, while the paper specifies IIP3 precisely *at* the
minimum-gain setting. The gate as mapped is met; the thing the paper actually
wants from a gain-programmable LNA is, at this match margin, **not available
anywhere in this topology**. That is the finding to carry forward, and it
points the same direction stage 31 already did: margin is the currency, and
this design has almost none to spend.
"""

HAND = """
### ▸ Sub-block: WP-PGAIN - ★★★ Gate **D6** (gain programmability) met under a proposed mapping, and the map of where this amplifier may be loaded (owner: the gain-programmability executor)

**Files owned:** `lna/pgain.py` (new), `lna/_pgain_mech.py` (new),
`lna/_pgain_probe.py` + `lna/_pgain_docs.py` (scratch), `lna/out/pgain_*`,
FINDINGS **SS42**, JOURNEY stage **37**, this sub-block. **No shared file
edited** - switches are inserted by netlist post-processing in this module's
own code; `size.py`, `templates.py` and the specs are read-only here. Inserted
elements are named `MSWG*/RSWG*/CSWG*/VSWG*`, disjoint from the bias scaffold,
so the `^(RBIAS|CBYP|VBGEN)` contract extends to
`^(RBIAS|CBYP|VBGEN|MSWG|RSWG|CSWG|VSWG)` unambiguously when someone needs it.

**Verdict: D6 MET under the mapping proposed in FINDINGS SS42.1 - which needs
user sign-off before the ladder in `plans2/14-DHRUVA-SIMUL.md` SS2 may be
updated.** Four states on one netlist / one sizing / three gate voltages; spans
**11.23-11.46 dB** on the four bands (gate: >= 10.6 in >= 3 steps); S11
<= -10 dB band-wide and Idd 12.963 mA in **every** state; max-gain state
identical to the SS35.2 D4-SIM row on every gate. Replay 3/3, spread 0.0000.

**Read SS42.6 clause 1 before quoting the pass.** Every mechanism that holds
the match sits behind the last gain stage, so the low-gain states buy range and
**no** IIP3 - and the paper specifies IIP3 *at min gain*. The mechanisms that
would buy linearity are precisely the ones the 0.001 dB match margin forbids.

**Two things the next executor should take from this regardless of D6:**

1. **`size.prepared_body` node names are randomised per process** (SS42.2).
   Element names are stable; node names are not. Any tool that post-processes
   an emitted netlist must resolve nodes structurally -
   `_pgain_mech.resolve_nodes()` is a worked example with cross-checks. A prior
   draft of this very work package produced a full set of numbers that were all
   void for this reason.
2. **The loading map (SS42.3) is reusable.** It says, mechanism-independently,
   which nodes of `ace8383c` can be touched at all. Anything that wants to add
   a switch, a tap, a feedback path or a probe to this design should read it
   first.

**Commands**

```bash
export NGSPICE="C:/msys64/ucrt64/bin/ngspice_con.exe"
python lna/pgain.py --probe                                       # the loading map (SS42.3)
python lna/pgain.py --wall                                        # authority-vs-match sweep, all mechanisms (SS42.4)
python lna/pgain.py --mech out-bank --tune --even                 # the shipped state table (SS42.5)
python lna/pgain.py --mech out-bank --tune --even --sizing simul  # same on the WP-HARDEN point
python lna/pgain.py --mech bypass  --tune --sizing simul          # stage-bypass, only legal on the hardened point
python lna/pgain.py --replay --mech out-bank --even --reps 3      # replay fence
python lna/pgain.py --report                                      # every stored mechanism table + verdict
```

`--all` tunes every mechanism; `--sizing {l5,simul}` picks the substrate, and
every emitted row records which one it used.
"""

BLOCKS = [("FINDINGS.md", FIND, None, "## 42. Phase 3 - WP-PGAIN"),
          ("JOURNEY.md", JOUR, "## Current frontier", "## 37. WP-PGAIN"),
          ("HANDOVER-EXEC.md", HAND, "## 1. TL;DR - what shipped this session",
           "Sub-block: WP-PGAIN")]


def run(check=False):
    for name, text, anchor, marker in BLOCKS:
        path = os.path.join(HERE, name)
        t = io.open(path, encoding="utf-8").read()
        if marker in t:
            print(f"{name}: block already present, skipping")
            continue
        if check:
            print(f"{name}: block ABSENT")
            continue
        if anchor:
            i = t.rfind(anchor)
            if i < 0:
                # the em-dash variant of the same heading
                i = t.rfind(anchor.replace(" - ", " \u2014 "))
            if i < 0:
                raise SystemExit(f"{name}: anchor {anchor!r} not found")
            t = t[:i] + text.strip("\n") + "\n\n" + t[i:]
        else:
            t = t.rstrip("\n") + "\n\n" + text.strip("\n") + "\n"
        io.open(path, "w", encoding="utf-8").write(t)
        print(f"{name}: appended {len(text)} chars")


if __name__ == "__main__":
    run(check="--check" in sys.argv)
