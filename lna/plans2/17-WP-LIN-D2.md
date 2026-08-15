# 17 — WP-LIN D-2: the one bounded test-widening that carries candidate D and the isolating input to real two-tone

**Status:** **PRE-REGISTRATION — committed before any run.** One measurement,
not a program. Mirrors the house pre-registration form (`16-WP-LIN.md`,
`13-WP-DIAGHEADS.md`), kept short by mandate.
**Branch:** `main`. **Owner:** WP-LIN executor (Session 10, D-2 test-widening).
**Authorized by:** the user's ruling 2026-08-15 — *"Widen the device budget
just enough (justified, corpus-anchored per §23's precedent) to carry candidate
D (current-reuse) and the isolating input architecture to real two-tone — one
bounded incremental measurement — so candidate N is judged on a full 5/5 or
refuted."*
**Documentation slots:** FINDINGS §46, JOURNEY next stage, `16-WP-LIN.md` §11
row appended after execution.

---

## 0. Why this exists — the missing half of candidate N's clause 4

Rungs 0–4 are complete (FINDINGS §44/§44.9/§45; JOURNEY 42–43). Candidate N
(the null — the wall is physical at ≤1.2 V) stands at **4½ of 5** clauses
(§45.5). The missing half is inside **clause 4** ("the best candidate from each
of B, C, D carried to real two-tone"):

* **B ✓** (real two-tone, +0.72 dB OIP3, S11-capped at NM6×2 — §45.3/§45.4).
* **C ✓** (real two-tone, −2.7 dB OIP3, proxy validated — §45.4).
* **D ✗** — **in-box-impossible at the 21-device budget** (§45.2): current-
  reuse needs a stacked device the 20/21 topology does not have to spare once
  the front-side path also wants one. Recorded as blocked, **not measured.**

And the front-side gain-control path — the only route to the ~12 dB half of
§2.3's decomposition — was refuted (P4, §45.1) **as an in-box mechanism**: every
front-side node is match-forbidden because the C_gd-coupled input-match
architecture (not the S11 margin) forbids loading. §45.5(i) named the escape:
*an isolating front-end — a topology change beyond the 1-spare-device budget.*
That structure has never been built or measured either.

Both gaps are the **same** gap: **devices.** The user has ruled one bounded
widening to close them, so N is judged on a full 5/5 or refuted, not left at 4½.

---

## 1. The device allowance — smallest sufficient, each device named with its role

Standing topology: **20 of 21** active devices (`device_budget: [3, 21]`,
`dhruva-*.yaml`, widened 18→21 on 2026-08-10 against calibrated corpus counts).
The two structures this test must carry require, minimally:

| structure | device added | role | why one is necessary and sufficient |
|---|---|---|---|
| **candidate D** (current-reuse) | **MNMD1** — reuse/stacking NMOS | folds a second transconductance onto one DC branch so MNM6's *effective* output current rises without new supply draw (§3 row D; §45.5(iii)'s "8 mA in the output device" funded by reuse, not by taking MNM4's current, which B proved S11 forbids) | current-reuse of a single stage is one added active device by construction — the stack IS the reuse |
| **isolating input** | **MNMI1** — cascode/isolation NMOS on the combiner's CS pair | breaks the C_gd feed-through that makes every front-side node match-forbidden (§45.1; §3 row F note: "cascoding MNM2/MNM5 could buy S11 margin that candidate A then spends"), presenting a high-Z, C_gd-shielded tap point | isolation between the match node and the gain-control tap is one series device (a cascode) |
| **isolating input** | **MNMI2** — front-side variable-attenuation device on the *isolated* tap | the actual gain-control element P4 needs — now attaching to a node that tolerates loading because MNMI1 shields it from the input match | the gain control needs its own conductance device once the isolation node exists; the DC-blocked switches of the D6 bank act on a match-legal node only after MNMI1 makes one |

**Allowance chosen: +3 devices → a D-2 *test allowance* of `device_budget`
[3, 24].** Smaller allowances were considered and rejected:

* **+1** carries D **or** the isolating input, not both — but the mandate is to
  carry both (D's clause-4 leg *and* the isolating input's span question).
* **+2** carries D (MNMD1) + one input device, but a single added device on the
  input either isolates (MNMI1) or controls gain (MNMI2), not both; a bare
  cascode with no tap measures no span, and a bare tap with no isolation
  reproduces §45.1's refutation. The isolating input is irreducibly 2 devices.

**+3 is therefore the smallest allowance that makes the pre-registered
measurement well-posed.** Inductors and `kind_ranges` are **untouched** (2 of 6
inductors stand; all params in-box).

**This is a TEST allowance, not a spec edit.** `lna/specs/*.yaml`
`device_budget: [3, 21]` is **not** touched (frozen-protocol, §7 D-3). The
three devices are built in **sidecar space** (`_pgain_mech`-style structural
inserts, §42.2 discipline) with the widening pre-registered here as a
user-authorized D-2 allowance. **If a widened candidate passes**, adopting the
widening into the spec is a **separate user ruling** requiring a justifying
corpus circuit (§23 precedent — the way 18→21 was justified). **If none
passes**, N's clause 4 is complete and **N is REPORTED as fully met (5/5) but
still NOT recorded** — recording N remains the user's call (§7 D-1).

---

## 2. The candidate definitions (sidecar builds)

**Common substrate:** the designated `dhruva-simul` params at pVDD = 1.2 V, the
§45-measured constraints respected — three input devices (MNM2/3/5) in
sub-threshold, 1.2 V rail, all sources structurally resolved (§42.2), never by
literal node name.

**D — current-reuse.** MNMD1 stacked to re-fund the output stage per §3 row D's
mechanism: one DC branch's current serves MNM6's output transconductance in
addition to its original stage, raising `Iq(MNM6)_eff × |Z_ac|` without adding
supply current (the resource B could not free without breaking S11). Built on
the output side, where §45.1's probe map says loading is legal (S11 *improves*
at outd/VOUT1). Structural role resolution reused verbatim from
`_pgain_mech.resolve_nodes`; MNMD1 inserted between resolved roles, cross-checked
by a second element that must touch it, never by literal node.

**Isolating input architecture.** MNMI1 (cascode) inserted in series above the
combiner CS pair so the gain-control tap sees a C_gd-shielded, high-Z node;
MNMI2 provides the variable front-side attenuation on that isolated node, driven
by a `pVSWG*`-style DC control (the pgain probe machinery, §42.1 mapping-legal).
The **match-legal span** of this architecture is measured by the same
`pgain.py --probe/--wall` span machinery that measured the in-att/in-degen walls
in §45.1 — the number the user asked to be closed.

---

## 3. Screen — rung-1 form, kill rules pre-stated

`size.eval_metrics(nf_gated=True)` + one `op` at 1.2 V nominal, plus swing
proxies (`Iq(MNM6)_eff`, `|Z_ac|`, `Vq−Vdsat`, per-device region/gm-Id), plus —
for the isolating input — the match-legal span measurement.

* **Kill (D):** any device off or in triode (`extract.mos_region`), any
  `Vds < Vdsat`, S11 off band-wide legality, Idd > 13 mA, S21 below D4-SIM
  floors, or `Iq(MNM6)_eff × |Z_ac|` failing to improve on the 72.9 mV baseline.
* **Kill (isolating input):** band-wide S11 > −10 dB in any state, **or
  match-legal span < 10.6 dB** (the §6.2 D6 span requirement — the same bar the
  §45.1 walls failed). This is the span question the mandate closes.

---

## 4. Two-tone acceptance — §6.1 gates at the D6 min-gain state, full fences

Survivors of §3 → real two-tone at the **D6 out-bank S3 min-gain state**,
pVDD = 1.2 V, four bands, 5-drive min-gain window (§44.3), the full §37.3 fence
set intact (IM3 slope 3 ± 0.3, ≥10 dB SNR over floor, ≤0.5 dB compression,
per-point spread reported, re-pointed §37.4 S21 cross-check never disabled),
replay-fenced ×3 in-process (spread target 0.0000). §6.1 pass = IIP3 ≥
−7.4/−7.4/−7.6/−8.7 dBm at l5/l2/l1/s. **HB cross-check (VACASK) on any claimed
pass** — 3 MHz tone spacing on switch decks (§40.5 2 MHz pathology convention).

---

## 5. Predictions, with falsifiers (§45's arithmetic gives the priors — stated honestly)

* **PD1 (D).** Current-reuse **raises** `Iq(MNM6)_eff × |Z_ac|` more than B's
  +1.13× — B was capped by S11 at NM6×2 (+1.1 dB); reuse funds current without
  widening MNM6, so it should clear the S11 cap. **Falsifier:** if the stack
  costs the 1.2 V rail its headroom (three input devices already sub-threshold),
  MNMD1 or a stacked device drops out of saturation → killed at screen, D
  **measured-impossible even widened**, mechanism named (headroom, not count).
  *Prior: I expect the headroom to bind — §45.5 already priced the honest
  requirement at OIP3 ≈ 33–55× P_dc; +1 device of reuse buys a few dB at most,
  far short of the ~27 dB gap. I expect D to be screened or to reach two-tone
  and fail by ~20+ dB.*

* **PD2 (isolating input span).** The cascode **lifts** the front-side
  match-legal span above §45.1's 4.8 dB by shielding C_gd — but I predict it
  **still falls short of 10.6 dB**, because the forbidden zone is the
  *input-match architecture itself* (§45.1's conclusion: "architecture, not
  margin"), and one cascode shifts the C_gd feed-through node without removing
  the match constraint that the CS pair's g_m sets. **Falsifier:** span ≥ 10.6
  dB at any front-side node with S11 band-wide legal → P4's escape is real, the
  ~12 dB half of §2.3 is back on the table, and this becomes a **candidate for
  §6 acceptance** (queuing a spec-widening ruling).

* **PN (candidate N).** I expect **neither** widened candidate to reach §6
  acceptance; the honest outcome is N's clause 4 completed with D
  *measured* (pass or the mechanism of its failure named, no longer "in-box
  impossible") and the span *closed* with a number — **N reported 5/5, not
  recorded.** **Falsifier:** any band passing §6.1 two-tone on a widened
  candidate → N is NOT met, and a spec-widening ruling is queued for the user.

---

## 6. Caps (stop at cap, publish shortfall)

* ≤ **600** screen evaluations.
* ≤ **6** candidates carried to two-tone.
* ≤ **3 h** wall on the loaded box (≤32 workers, ~2× §45 per-run times).
* Stop at any cap and publish the shortfall (§34 precedent).

---

## 7. Law (unchanged from WP-LIN)

Goldens GREEN before/after every landing (`check_ref`, `check_iip3`,
`check_hb`, `check_diff`). Sidecars + module-attribute overrides only; no shared
harness edit (§7 D-9); no spec/frozen-protocol touch (§7 D-3); `device_budget`
line NOT edited. §42.2 node-name discipline on every insert (structural role
resolution + second-element cross-check). Append-only store, `recipe=wplin-v1`,
`source_arm=wplin-d2`. N is **not** recorded (§7 D-1 is the user's).

---

## 8. Outcome (appended after execution — 2026-08-15, FINDINGS §46)

| pre-registered claim | verdict |
|---|---|
| **PD1** — the 1.2 V rail's headroom binds candidate D | **CONFIRMED, and sharpened.** The 20-point headroom map (§46.2): every saturated MNMD1 build lands *below* the baseline swing product (best 54.97 vs 72.91 mV); every swing-seeking build collapses to triode — and even in triode the product asymptotes at 72.56, **never exceeding baseline**, because the output branch current is resistor-set (RR4) and a stack adds gm, not current. Carried to the ruled condition anyway (best saturated tier-legal build): **D5 FAILS 0/4, −20.7…−22.1 dB**, fences intact, replay 0.0000. One surprise, reported as measured: the stack source-degenerates MNM6 and buys +5.5…+6.1 dB of S3 IIP3 — the WP's only IIP3-positive candidate, still 20+ dB short. |
| **PD2** — the cascode lifts the span but not to 10.6 dB | **CONFIRMED in verdict, wrong in detail — the span did not lift at all.** Match-legal span = **0.00 dB** (all-off legal at S11 −10.62; every conducting-attenuator state breaks to −7.13…−7.20). Worse than the un-isolated combiner's 4.84 dB (§45.1): the shunt's loading reaches the input match *through* the cascode. The forbidden zone is the input match architecture itself; isolation hardware does not shield it. Screen also killed the build on NF (2.70/2.64 > 2.5). |
| **PN** — neither reaches §6; N reported 5/5, not recorded | **CONFIRMED.** No band passed on any widened candidate; the mechanism check (l5, match-illegal state, evidence-only) measured front-side attenuation buying IIP3 as §2.3 assumed (−9.32 dB of G → **+10.07 dB of IIP3**, replay 0.0000) — confirming the premise the span kills. **Candidate N: 5 of 5, REPORTED — NOT recorded (D-1). The D-2 spec-adoption ruling is moot; `device_budget: [3, 21]` stands untouched.** |

Caps: ~85 screen evals (of 600); 1 full two-tone candidate + 1 mechanism
check (of 6); ≈1.7 h wall (of 3). Deviations in FINDINGS §46.7.
