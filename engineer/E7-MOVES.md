# E7-MOVES — a primitive-only move repertoire for output-class reachability (pre-registration)

**Status: DRAFT — PENDING USER RULING. NOTHING EXECUTES UNTIL RULED.**

This document is the **pre-registration** for **rung G2 (E-7)** of
`engineer/ROADMAP.md` §3 (the move-repertoire rung). It is a DRAFT: it is
committed for the user's ruling, and **nothing is built, nothing is scored, no
simulation is run** under it until the user rules. The box is saturated by a
running campaign; the only simulator invocation permitted for this commit is the
mandatory goldens check (`nice -n 19 python lna/ref/check_ref.py`). No move code,
no harness, no arm has been written; the proposed move list below is a *proposal
to be ruled on*, not an implemented set.

Written in the E3-MEMORY / E4-LOOP / E6-BUDGET pre-registration shape: state the
hypothesis, the move-set proposal (with its primitive/macro classification rule
applied and shown), the reachability argument, the test design (arms, budgets,
metrics), the acceptance criterion and the binding falsifier — all fixed **before**
any scoring eval — then, only after a user GO, run and append the outcome
(clearly marked post-hoc). The rule cannot have chosen the protocol.

Per `engineer/ROADMAP.md` §6 and `engineer/G0-FAIRNESS.md` §4 (addendum
2026-08-20), the engineer line's **primary scoreboard metric is SPICE-minutes to
first spec-feasible design**; that is the primary axis this rung is scored on,
with reachability rate reported alongside.

---

## 0. The NUDGE POLICY — binding, recorded verbatim (user directive, 2026-08-20)

> The user has directed that executor-authored topology injections be limited.
> For G2 this means: the extended move repertoire may contain only GENERIC,
> COMPOSABLE graph-edit primitives (examples of the legal kind: add-device-of-type,
> split-net, insert-series/parallel-element, duplicate-branch-with-complement,
> reconnect-terminal). ILLEGAL: any move that encodes a named circuit solution —
> "insert class-AB output stage", "add push-pull pair as a unit", "apply balun
> motif" — because that bakes the D5 answer into the repertoire and the experiment
> would measure our knowledge, not the system's capability. The pre-reg must
> include a review rule: every proposed move is classified primitive/macro, macros
> are rejected, and the final move list is itself part of what the user rules on.
> Every authored component is declared in the G0 contamination ledger.

This section is normative. It governs every move proposed in §2, the review rule
in §2.2, the ledger in §6, and the "what this is NOT" fence in §5. Any move that
fails the primitive test in §2.2 is **rejected before it can be implemented**, and
the reviewer's classification is committed alongside this doc.

---

## 1. Hypothesis (stated before any number is seen)

> **The binding constraint on the diagnosis→intervention loop is the MOVE
> REPERTOIRE, not the diagnosis (FINDINGS §34.8 item 1, §35's cross-reference:
> "the move set is now the bottleneck, not the diagnosis"). With a sufficient
> set of PRIMITIVE (non-macro) graph-edit moves, a guided search — diagnosis
> heads aiming, critic filtering, a trust region — can compose those primitives
> into a topology whose output stage is NOT class-A and that survives the L0/L1
> screens. That capability — reaching a different output class from the diagnosis
> alone — is exactly what the main line's D5 ruling (option 3c, topology-class
> change) now depends on.**

The evidence the hypothesis rests on, cited before the run:

- **The diagnosis is not the bottleneck.** FINDINGS §34 measured the diagnosis
  heads: dominant-noise-device top-1 **0.596** (vs 0.191 base rate), conduction
  AUC **0.949**, weak/strong-inversion AUC **0.858**. Pointing `moves.py` where
  the heads point beat random move selection on the pre-registered metric
  (mean Δ feasibility **−1.049 vs −1.432**) — *"but it wins by removing
  disasters, not by finding wins, and the only feasible child in the entire
  pilot came from a random `rewire`."* (§34 headline.)
- **The moves are.** §34.8 item 1, verbatim: *"The move set is now the
  bottleneck, not the diagnosis. Two of five targeted arms could not be filled
  because the head pointed at a passive whose only prescribed edits were illegal
  on that circuit."* The heads can say *where*; the repertoire cannot always
  *act* there.
- **The D5 wall is a class wall.** FINDINGS §44.4 / `16-WP-LIN.md` §2.2: the D5
  IIP3 failure is an **output-stage class-A current-swing limit** —
  `Iq(MNM6) × |Z_ac| ≈ 1.432 mA × 50.9 Ω ≈ 73 mV`, binding **6.93× (16.8 dB)**
  ahead of the voltage-headroom limit. `20-D5-DECISION.md` §3c (RULED 2026-08-20)
  makes the *only in-envelope* path a **different output-stage class**, and
  sequences main-line D5 behind this rung.

The falsifiable content: can guided primitive-move search *reach* a non-class-A
output that survives L0/L1 — and reach it more often than random primitive-move
search at matched budget? If not, the loop's problem is deeper than the moves.

---

## 2. The move-set proposal (the object the user rules on)

### 2.1 What the current 17 moves are, and what they cannot express

`lna/moves.py` (`MOVES`, 17 entries) is the stratum-M 1-edit set:
`load_swap, cascode_add/remove, buffer_add/remove, degen_add/remove,
stage_add/remove, feedback_add/remove, match_elem_add, input_class_swap,
passive_type_swap, rewire, device_remove, aux_path_add`.

Read as graph edits, the **structural gap** is precise and it is about **device
polarity and complementary conduction**:

- **Every FET-adding move hardcodes `nmos4`.** `m_cascode_add` (line 298),
  `m_buffer_add` (325), `m_stage_add` (394), `m_aux_path_add` (600) all append
  `"nmos4"`. `pmos4` is in `FET_TYPES` (line 42) — the *representation* and the
  L0 screen accept PMOS (archetypes may contain them) — but **no move can
  introduce a PMOS device, nor swap an existing FET's polarity, nor add a
  device positioned to conduct the opposite half-cycle.**
- **Consequence for output class.** A class-A output stage is a single active
  device sinking/sourcing the entire signal current over the whole cycle; its
  swing is capped at `Iq × |Z_ac|`. ANY non-class-A output (class-AB / class-B
  push-pull, complementary current-reuse, a pulled-and-pushed pair) requires a
  **second active device conducting the complementary half-cycle** — a device
  whose current *adds* to the output on the opposite swing so the two share the
  swing and the class-A ceiling is broken. The 17 moves can *stack* same-polarity
  NMOS (cascode), *append* same-polarity NMOS gain/buffer stages, and *rewire*
  passives — none of which changes the number of complementary active devices at
  the output. **The current repertoire cannot change an output stage's class.**
  `m_input_class_swap` swaps CS↔CG on the *input* stage only; there is no output
  analogue, and CS↔CG is a same-device topological reorientation, not a
  complementary-device addition.

This is the abstract, no-simulation reading of the graph: the move set is closed
under {stack NMOS, append NMOS stage, rewire passive, swap passive type}, and the
output-class change lives outside that closure.

### 2.2 The proposed PRIMITIVE extension, with the review rule applied and shown

The review rule (nudge policy §0): **every proposed move is classified
primitive or macro; macros are rejected; the surviving list is what the user
rules on.** A move is a **macro** if it encodes a named circuit solution (a
motif whose identity is a known answer — "class-AB output", "push-pull pair",
"balun"); a move is a **primitive** if it is a generic graph edit whose
definition names no circuit solution and which composes with others.

| # | proposed move | what it does (graph edit) | classification | verdict |
|---|---|---|---|---|
| P1 | `add_device_of_type(t)` | append one device of a chosen type from `{nmos4, pmos4, resistor, capacitor, inductor}` onto existing nodes (generalizes the NMOS-only adders) | **primitive** — parameterized by type; names no motif | **ACCEPT** |
| P2 | `fet_polarity_swap` | change one existing FET's type `nmos4 ↔ pmos4`, leaving its terminals in place (the L0 screen then judges bias legality) | **primitive** — a device-type substitution, the FET analogue of `passive_type_swap` | **ACCEPT** |
| P3 | `split_net(n)` | split node `n` into `n, n'`, moving a chosen subset of terminals to `n'` (creates the extra node a second device needs to attach to) | **primitive** — a topological refinement; names no motif | **ACCEPT** |
| P4 | `insert_series_element(edge, t)` | break one existing 2-terminal connection and insert a series device of type `t` at a fresh node | **primitive** — generalizes the ad-hoc series inserts inside `match_elem_add`/`stage_add` into one composable edit | **ACCEPT** |
| P5 | `insert_parallel_element(dev, t)` | add a device of type `t` in parallel with an existing device | **primitive** — a generic branch addition | **ACCEPT** |
| P6 | `duplicate_branch_with_complement(dev)` | duplicate a device's connectivity but with the **complementary FET polarity** and its source referred to the opposite rail (nmos4→VSS becomes pmos4→VDD, same signal/drain node) | **primitive — BORDERLINE, see note** | **ACCEPT (as a primitive), see §2.3** |
| P7 | `reconnect_terminal(dev, pin, node)` | move one device terminal to a different existing node (generalizes `rewire` — currently passive-only, line 546 — to FET pins) | **primitive** — the existing rewire, un-restricted | **ACCEPT** |
| X1 | ~~`add_class_ab_output_stage`~~ | insert a complementary output pair pre-wired as a class-AB stage | **MACRO** — names the D5 answer | **REJECT** |
| X2 | ~~`add_push_pull_pair`~~ | add a push-pull pair as one unit | **MACRO** — names the answer | **REJECT** |
| X3 | ~~`apply_balun_motif`~~ | graft the assistant-authored balun (`templates.diff_pair_balun`, FINDINGS §41) | **MACRO** — the named, hand-authored motif this experiment exists to forbid (§5) | **REJECT** |

**Surviving primitive list (what the user rules on): P1–P7.** The three macros
(X1–X3) are rejected by the review rule and named here only so the rejection is a
declaration, not an omission. This list — and specifically the §2.3 borderline
ruling on P6 — is itself part of what the user rules on (nudge policy §0).

### 2.3 The one borderline: P6 `duplicate_branch_with_complement`

P6 is the move that most directly enables a class change, and therefore the one
whose primitive/macro status must be argued, not asserted. The nudge policy's own
examples list **"duplicate-branch-with-complement"** as *a legal kind of
primitive*. The argument for ACCEPT: P6 names no circuit solution — it duplicates
*whatever branch it is pointed at* with the complementary polarity; it is not
"add a push-pull output", it is "mirror this one device to the other rail". It
composes with P3 (split-net) and P7 (reconnect) to build many structures, only
one family of which is a push-pull output. The argument for caution (surfaced for
the user, not decided here): a single P6 applied to the output FET, if the
mirrored device lands exactly complementary at the output node, is *one edit from*
a two-device complementary output — close enough that a reviewer could read it as
a macro-in-primitive-clothing. **We classify P6 primitive** because its definition
is polarity-generic and target-agnostic, but we flag it as **OQ-4** so the user
can downgrade it to "rejected" (leaving the class change to compose from P1+P2+P3+P7
in more edits) if they judge it too close to the answer. The reachability count in
§3 is reported **both with and without P6** for exactly this reason.

---

## 3. Reachability — the edit-path length from class-A to a different output class (computed abstractly, no simulation)

The question: starting from the flagship's class-A output stage (single `nmos4`,
call it M_out, drain on the AC-coupled output load, source on VSS), what is the
**minimum number of primitive edits** that must compose to reach *any* output
class that is not class-A — i.e. a topology with a **second active device
conducting the complementary half-cycle at the output node**?

Reasoning on the graph (the target is: a complementary device — a `pmos4` whose
source is on VDD and whose drain shares the output node — driven in phase-
opposition so it sources current on the half-cycle M_out cannot):

**Path A — with P6 available (the direct route):**

1. `P6 duplicate_branch_with_complement(M_out)` → creates M_out', a `pmos4`
   with source on VDD, drain on the output node (the complementary half is now
   present).

That is **1 primitive edit** to instantiate the complementary device. A minimal
class-AB then also needs the two gates driven so the pair alternates rather than
both following the input identically; if the duplicated branch does not already
share the drive node correctly, **1 more edit** (`P7 reconnect_terminal` on M_out'
gate, or `P3 split_net` to create a separate bias node) makes the pair
push-pull-drivable. **Reachability with P6: 1–2 primitive edits.**

**Path B — without P6 (P6 downgraded to rejected, the conservative repertoire):**

1. `P1 add_device_of_type(pmos4)` → a `pmos4` exists but is unwired (dangling;
   the L0 `sane` screen will reject it until connected).
2. `P7 reconnect_terminal` (source → VDD).
3. `P7 reconnect_terminal` (drain → output node).
4. `P7 reconnect_terminal` (gate → the drive node, possibly after
   `P3 split_net` to separate the two gate biases).

**Reachability without P6: 3–4 primitive edits** (P1 + three reconnects, +1 if a
`split_net` is needed for independent gate bias). Note each intermediate state
(a dangling or half-wired PMOS) **fails the L0 `sane` screen** (line 160:
every internal node needs ≥2 signal terminals), so a 1-edit-at-a-time search must
either (a) allow transient L0-illegal intermediates within a single guided
multi-edit step, or (b) compose the reconnects as one atomic "add-and-wire"
primitive. This is a real design finding, surfaced as **OQ-5**.

**Verdict.** A non-class-A output class **IS reachable** in a plausible number of
primitive edits: **1–2 with P6, or 3–4 with P1+P7(+P3) if P6 is rejected**. The
current 17-move set reaches it in **∞ (not reachable)** — no move introduces a
complementary-polarity active device (§2.1). So the extension is *necessary* and,
at 1–4 primitive edits, *sufficient in principle*.

**The minimal additional primitive, if P6 is rejected.** If the user downgrades
P6 (OQ-4), the missing capability is not a new motif but the composition problem
in Path B: the search must be able to add-then-wire a device across ≥3 edits
through L0-illegal intermediates. The minimal PRIMITIVE that repairs this without
reintroducing a macro is an **atomic `add_and_connect_device(type, {pin: node})`**
— still generic (it names a type and a terminal map, never a motif), but it lets
one guided step place a fully-wired device so no intermediate is L0-illegal. That
is the minimal primitive addition; it is offered for the user's ruling (OQ-5),
not adopted here.

---

## 4. Test design

### 4.1 The question the test answers

Given **only** the D5 diagnosis — "output-stage current-swing limit,
`Iq × |Z_ac|`" (no hand-authored output stage anywhere in the pipeline, §5) — can
a guided search (diagnosis heads aiming at the output device, critic filtering
candidates, a trust region bounding edit distance) **reach a topology whose
output stage is not class-A and that survives L0 (structural screen) and L1
(bias-legal / DC-convergent)**? And does it do so more efficiently than chance?

### 4.2 Arms (three, all on the pinned dhruva flagship, no sizing tuning transferred)

| arm | what it is |
|---|---|
| **(G) guided** | Diagnosis-head-aimed primitive-move search: heads point at the output device (§34's conduction/dominant-device outputs), the critic filters proposed mutants, a trust region caps edit distance per step; the primitive repertoire is P1–P7 (§2.2). |
| **(R) random** | The **same** primitive repertoire P1–P7, moves chosen uniformly at random (no head aiming, no critic filter), matched total budget. This is the null the §1 hypothesis must beat — it isolates *guidance* from *repertoire*. |
| **(N) no-move** | No structural edits at all: sizing-only on the pinned class-A topology (the D5 record, candidate N). Establishes that the wall is not reachable by sizing — the §3d/§44.4 result restated as a live baseline, so a G/R success is unambiguously structural. |

All three declare the G0 contamination ledger (§6); none consults the playbook
(that is G3); seeds are generic 1..N.

### 4.3 Budgets and tiers

- **Primary metric:** **SPICE-minutes to first spec-feasible design** (ROADMAP §6,
  G0-FAIRNESS §4 addendum). Derived from the per-eval `cost.wall_s`/`sim_s` stamps
  already recorded by `Env.evaluate`; no extra simulations.
- **Reachability rate** (reported alongside): the fraction of runs that reach a
  non-class-A output class surviving L0/L1 within budget, and the median SPICE-
  minutes and median primitive-edit-count to first such topology.
- **Smoke tier (mechanics check only, per R-4):** **150 evals/arm** (the R-4 smoke
  convention, same as E-6 §4.1). Seeds 1–3. Purpose: verify the primitive moves
  realize through the token round-trip, the trust region and head-aiming plumbing
  run deterministically, every eval goes through the env counter, and no write
  touches `lna/`. **Smoke can refute the harness, never confirm the hypothesis**
  (E-6 §7 discipline, binding here too).
- **Full tier (TO BE RUN ONLY AFTER HUMAN GO):** the matched-budget configuration
  and N=10, budgets from the pinned reference rows; the tier at which §4.4's
  acceptance/falsifier can be reached.

### 4.4 Acceptance criterion and the binding falsifier (pre-stated)

**Acceptance:** guided primitive-move search (arm G) reaches a non-class-A output
class that survives L0/L1 at a **higher reachability rate** than random primitive-
move search (arm R) at matched budget, **and** reaches first feasibility in
**fewer SPICE-minutes** (primary metric) than R; the no-move arm (N) reaches the
non-class-A class **never** (confirming the change is structural, not a sizing
artifact).

**Binding falsifier (pre-stated):**

> **If guided move search reaches a non-class-A output class no more often than
> random move search at matched budget, diagnosis-aimed structural editing is
> refuted for this wall** — the heads' aim carries no usable signal for
> output-class change, and the D5 path (option 3c) needs a user re-ruling because
> the machine-found-output-class premise it rests on is unsupported for this wall.

A secondary, weaker negative: if **both** G and R reach the class *never* at the
full budget, the primitive repertoire (P1–P7) is itself insufficient — the finding
then points to the §3 minimal-additional-primitive (OQ-5), not to a re-ruling of D5.

---

## 5. What this is NOT (the fence, per the nudge policy)

- **No hand-authored output stage anywhere in the pipeline for this test.** The
  point is to measure whether the *system* composes a non-class-A output from
  primitives under diagnosis guidance. Any macro that pre-bakes the answer voids
  the measurement (nudge policy §0).
- **The assistant-authored D7 balun is the named precedent this experiment
  forbids.** FINDINGS §41 grafted an *assistant-authored active balun*
  (`templates.diff_pair_balun`, `cs_cg_balun`, `balun_stage`), each hand-written
  with its engineering argument, to meet Gate D7. That is exactly the shortcut G2
  must not take: it is the human injecting the topology, so the result measured
  *our* knowledge, not the loop's capability. X3 (`apply_balun_motif`) is rejected
  in §2.2 precisely to keep this precedent out of the repertoire. If the loop
  reaches a differential/complementary output here, it must have *composed it from
  P1–P7*, not retrieved a named motif.
- **Not a sizing rung.** Sizing the reached topology to actually clear D5 IIP3 is
  downstream (OQ-7); G2's claim is reachability + L0/L1 survival, not a met D5 gate.

---

## 6. Contamination ledger (declared here, per PROTOCOL v1.1 / G0-FAIRNESS §3)

The dhruva flagship is a **regression floor**, NOT fresh (G0-FAIRNESS §1) — so a
transfer-tier ledger is informational here, but every **authored component** of
this rung is declared per the nudge policy §0. Authored components: the primitive
move functions P1–P7 (generic graph edits, no task-specific motif) and the
G2 arm/runner harness. No named-solution motif is authored (X1–X3 rejected).

```yaml
contamination_ledger:
  run_id: "E7-moves-<arm>_<task>_s<seed>"
  scope: "dhruva flagship — NOT fresh (G0-FAIRNESS §1) regression floor; ledger informational + nudge-policy authored-component declaration"
  date: "2026-08-20"
  transferred_in:
    harness_code:
      allowed: always
      description: "env.py, tasks.py, moves.py primitives P1-P7 (generic graph edits), critic_gnn diagnosis heads (read-only aim), realize() token round-trip"
    playbook:
      allowed: declared
      present: false      # G2 consults NO store; warm-vs-cold is G3
      declared: false
    seeds:
      allowed: never
      present: false      # generic seeds 1..N; no task-specific seed selection
    selectors:
      allowed: never
      present: false      # diagnosis heads AIM but are the experimental variable, not a tuned selector baked to this task; guidance is the arm under test, disclosed as such
      note: "no motif/archetype selector tuned to dhruva; the primitive move list is task-generic and reviewed primitive-only (§2.2)"
    calibrations:
      allowed: never
      present: false      # budgets from pinned reference rows / R-4 smoke convention; trust-region radius is a fixed constant, not tuned on this task's curve
  authored_components:      # nudge-policy §0 declaration
    primitives: [P1_add_device_of_type, P2_fet_polarity_swap, P3_split_net, P4_insert_series_element, P5_insert_parallel_element, P6_duplicate_branch_with_complement, P7_reconnect_terminal]
    macros_rejected: [X1_add_class_ab_output_stage, X2_add_push_pull_pair, X3_apply_balun_motif]
    review_rule: "every move classified primitive/macro (§2.2); macros rejected; list is user-ruled"
```

The **diagnosis-head aim** (arm G) is the experimental variable, disclosed as
such — it is not a hidden tuned selector; arm R runs the identical repertoire
without it precisely to isolate the aim's contribution.

---

## 7. Open questions for the user (E-6-style, queued not guessed — recorded before any run)

| # | question | why it is queued, not decided here |
|---|---|---|
| **OQ-1** | Is the **smoke worth running before the E-6 verdict frees the box**, or should G2 wait until the running E-6 campaign completes and the shared box is idle? | The box is saturated (E-6 campaign). The G2 smoke is a mechanics check (150 evals, refutes only the harness); the user may prefer to spend no simulator time until E-6's full-tier lands. Pre-registered so the timing is the user's call, not a default. |
| **OQ-2** | Does a **G2 success on L0/L1 justify immediate L2 sizing spend** on the reached topology (to test whether it actually clears D5 IIP3), or is L2 a separate ruling after the reachability verdict? | G2's claim is reachability + L0/L1 survival, not a met D5 gate (§5). Sizing spend is a larger commitment; whether a reachability win auto-authorizes it, or needs its own pre-reg, is the user's call. |
| **OQ-3** | If **reachability requires the one new primitive** of §3 (atomic `add_and_connect_device`, needed only if P6 is rejected), does adding it need a **separate ruling**, or is it pre-authorized as within the primitive class? | It is a primitive by the §2.2 test (names a type + terminal map, no motif), but it is an addition beyond the P1–P7 list the user is ruling on now. Pre-registered so its adoption is explicit, not smuggled in mid-run. |
| **OQ-4** | Is **P6 `duplicate_branch_with_complement`** a primitive (accept) or too close to the D5 answer (downgrade to reject)? | The nudge policy lists it as a legal kind, but a single P6 on the output FET is 1 edit from a complementary pair (§2.3). §3 reports reachability *both with and without P6* so the user can rule either way; the reachability count is 1–2 edits with P6, 3–4 without. |
| **OQ-5** | If P6 is rejected, is the **atomic add-and-wire primitive** (§3) accepted so multi-edit device placement need not pass through L0-illegal intermediates — or should the search be allowed transient L0-illegal states within one guided multi-edit step instead? | Two legal ways to solve the same composition problem (§3 Path B); both avoid a macro. Which one is preferred is a design ruling. |
| **OQ-6** | Is the **falsifier reading** (§4.4: guided-no-better-than-random ⇒ diagnosis-aimed structural editing refuted for this wall ⇒ D5 re-ruling) the one the user wants, or should a guided≈random result instead trigger a *stronger-guidance* follow-up before touching D5's ruling? | The §4.4 falsifier sends a null straight back to a D5 re-ruling; the user may prefer one intervening guidance-strengthening rung first. This is the same "how strong a negative binds the cross-line ruling" question OQ-3 posed for E-6. |

The harness resolves none of these inside a run; it records the trace and they
stay queued for the user.

---

## 8. Cross-line note (per `lna/plans2/20-D5-DECISION.md` §6)

Main-line D5 is **paused behind this rung** by the user's 2026-08-20 ruling
(option 3c, topology-class change): *"Main-line D5 work pauses pending engineer
rung G2 (move repertoire; its registered test case is this wall)"* (§6(a)).
Candidate N remains the standing D5 record for the current topology family until a
G2-derived output class produces a new measurable candidate (§6(b)).

A **G2 verdict therefore reopens or re-rules D5**:
- **G2 acceptance** (§4.4: guided reaches a machine-found non-class-A output class
  surviving L0/L1, beating random) → D5 **reopens** with that machine-found output
  class as the new candidate to size (subject to OQ-2's L2 ruling), fulfilling 3c's
  "the only in-envelope path" with a class the loop found, not one we authored.
- **G2 falsification** (§4.4: guided no better than random, or the class is
  unreachable even at full budget) → the 3c premise ("a G2-derived output class")
  is unsupported for this wall, and **D5 goes back to the user for a re-ruling**
  among the options `20-D5-DECISION.md` §4 priced (envelope relief 3a, spec relief
  3b, or record-and-close 3d).

---

<!-- POST-HOC OUTCOME SECTION APPENDED BELOW ONLY AFTER A USER GO AND THE RUN —
     NOT PART OF THE PRE-REGISTRATION. Everything above this line is the DRAFT
     committed for the user's ruling; nothing above was informed by any G2 eval. -->
