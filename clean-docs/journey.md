# JOURNEY — the LNA project, told as a story

*Clean version of `lna/JOURNEY.md`. That file is the narrative history of the
whole LNA effort: every stage as Context → Decision → Result → Understanding, with
user decisions marked. This is the same story in plain language. For exact numbers,
each stage cites `FINDINGS §N`; see also [findings.md](findings.md).*

## A 30-second glossary

- **Topology** — the circuit's wiring (which devices connect where), with no
  component values yet.
- **Sizing** — choosing the actual device values (transistor widths, resistances…)
  so the circuit hits its targets. Done by a black-box optimizer (ZOAF, later
  CMA-ES) driving the SPICE simulator.
- **Bias** — the DC setup that makes transistors actually switch on. The training
  circuits omit it, so it has to be inserted.
- **The metrics** — NF (noise figure, lower = better), S21 (gain), S11 (input match,
  want ≤ −10 dB), Idd (current draw), IIP3 (linearity), K (stability).
- **Gate** — a named milestone (G4, C1, D3, D5…). "MET" means measured and passed.
- **Tier-1 / tier-2 / tier-3** — S11+S21+Idd / +NF / +IIP3, differential, gain
  programmability. Each tier adds harder constraints.
- **NDL@256** — "Novel Distinct LNAs per 256 samples": the frozen score for how much
  genuinely new (not copied) LNA structure the generator produces.
- **dhruva** — the flagship target: a published GNSS-receiver LNA the pipeline tries
  to match *without being shown the paper's circuit* (the "blind protocol").

## The three phases

- **Phase 1** — build the pipeline: spec → reference → bias → generation → sizing.
- **Phase 2** — add learning: a critic that predicts feasibility, critic-guided
  search, and a self-improvement loop. (Brief from the user, 2026-08-06.)
- **Phase 3** — the dhruva blind campaign: push one real target across every tier.

---

## Phase 1 — building the pipeline (stages 1–3)

**The starting point.** A 15-repo survey (see [survey below is a different doc];
here it's `STATUS.md`) found AnalogGenie was the only real topology generator with
inductors and LNA examples, ngspice could already measure everything an LNA needs,
and tools that *looked* reusable (like ZeroSim) secretly couldn't model LNAs. So the
measurement side was ready; the **targeting** side didn't exist.

**The first win — prefix conditioning.** Seeding the generator with the first ~12
tokens of a real LNA, instead of letting it start blank, moved the LNA hit rate from
**0% to 40.6%** with no retraining. But push the seed longer and the output just
copies the seed circuit — a permanent tension between yield and novelty.

**The honest scoreboard — NDL@256.** To stop "better generation" from meaning "better
at copying," a frozen protocol was declared: count only LNAs that are novel (not a
graph-copy of anything in a reference set) and distinct. The first baseline was
**16**. A "regression quartet" of checks had to stay green before and after every
piece of work.

---

## Phase 2 — adding learning (stages 4–8)

**The reframe.** The user asked to turn "generate then optimize" into "generate,
predict, search, optimize." An unsized topology has no gain yet, so "predict its
metrics" was reframed to "predict its **margins after sizing**," with a cheap→expensive
label economy and a search ladder. The real goal was never "build a GNN" — it was
**stop paying SPICE cost for candidates that were never going to work.**

**The label store (Gate G4, by hand).** Nothing could be learned without labeled
data, and the pipeline had been throwing away every expensive simulation result. An
append-only store was added. A hand-designed reference LNA was sized to full
feasibility so the store even *had* a feasible example to learn from.

**The critic, and the wall behind every failure (Gate C1).** Simple baselines
(nearest-neighbor, ridge regression) were built before any GNN. They worked on a
normal split but collapsed on the "source-shift" split — train on real circuits, test
on generated ones. Every failure pointed at the same root cause: **the generator had
memorized ~35 training graphs.** No critic can rank a pool where every candidate is a
near-duplicate. The lever was the generator's data, not the critic.

**P5 — breaking the memorization ceiling (Gate G4 by generation).** Mixing in ~92
hand-written archetype templates broke the ceiling: novelty jumped, copying dropped,
inductors came back. A generated 8-device LNA sized to full feasibility. Lesson,
repeated many times after: **fixing a bad distribution beats filtering it.**

**The self-improvement loop.** The headline became "SPICE-minutes per feasible novel
design." It went 967 → (a worse turn, recorded honestly) → 367 → 187 as the design
count rose 1 → 3 → 6. The fix was mostly instrumentation and search-landscape work
(curated sizing, replay fences), not raw compute. A regression that made the curve
*worse* is the reason the replay fence exists.

---

## Broadening and the blind campaign (stages 9–10)

**Harder specs (gps-l1, wideband-sdr).** New archetype families broke a gain wall,
but input match wouldn't co-close. A later correction (stage 12) found two claimed
"generated discoveries" were actually exact copies of hand templates — the *sizing*
result stood, the *discovery* claim didn't. Lesson: **a "novel" claim is only as good
as the reference it's checked against.**

**The dhruva blind protocol.** New goal: match a published GNSS LNA's numbers without
the pipeline ever seeing its circuit. The paper's PDF was removed; only a
spec-number excerpt was allowed anywhere in the repo; unblinding is the user's call,
never the executor's. A hand-authored generic archetype (`rfb_cs3`) hit the spec on
all four bands — and the record honestly noted **this was assistant-authored, not a
neural-generator discovery.** That honest attribution is the whole point of the
protocol.

---

## The honesty waves (stages 11–12)

**The NF reckoning.** Every "feasible" design so far had NF *advisory only*. When the
physically-correct noise measurement replaced the old broken one, it turned out the
old measurement had **flattered every design** (by up to +12 dB; some had even read
negative NF). Re-judging 14 feasible designs under the real gate: tier-1 held for all
14, but tier-2 (NF) held for only **2**. Lesson: **a supported-but-missing metric
counts as fully violated** — advisory metrics are a debt that comes due.

**The metric-honesty wave.** A broad audit followed. Label noise had been mis-measured
(a pooling bug); a critic bug had been silently dropping ~240 broadband rows; and the
novelty reference had been letting the generator score template *copies* as "novel."
Two fixes touched frozen protocols, so both went to the user for explicit sign-off.
The recurring discipline: **a frozen protocol is a promise; changing it requires
surfacing the change and getting approval, not quietly re-basing a number.**

---

## Search, data, and the critic maturing (stages 13–16)

- **Evolutionary search** over one-edit graph mutations found a novel, stable
  dhruva-s design — but exposed that the critic **collapsed off-distribution** (a
  coverage problem, not a capacity one). The fancy "uncertainty gate" never fired;
  the simple "stay near training data" trust region did the real work.
- **The template question, asked three ways.** Removing templates kept ~half the
  novelty but lost most of the yield. Removing them on a schedule made novelty fall
  monotonically ("copying migrates, it doesn't stop"). The conclusion: templates are
  load-bearing because they **crowd out memorization** — the lever is *more varied
  data*, not clever schedules.
- **Real-data expansion (41 → 50 circuits).** Nine real LNAs (from open silicon
  tapeouts and papers) were ingested through a six-gate vetting ladder.
- **Critic v2** repaired most of the off-distribution collapse and, run live for the
  first time, its edge was largest exactly on **NF** — the constraint dhruva was stuck
  on.

---

## The Gate-D3 arc — the clearest example of the method (stages 17, 20, 22, 23)

Gate D3 = NF low enough on a dhruva band. Its diagnosis deepened, in public, at every
attempt:

1. **"A missing measurement"** (NF wasn't even trustworthy — stage 11).
2. **"A search failure"** (the sizer never found the noise/gain trade — stage 13).
3. **"A conversion rate"** — the noise/gain trade was measured as a dB-per-dB exchange
   (stage 17). Progress, but the one move that could break it (a second gain stage)
   needed more devices than the budget allowed.
4. **"A device-budget decision"** — the budget was widened twice (16→18→21), each time
   **calibrated to the device count of the nearest real silicon LNA**, never to "what
   closes the gate." Honestly noted: the gate needed 20 devices, not the 21 granted.
5. **MET on dhruva-s** — the first NF-gated feasible dhruva LNAs, independently
   re-audited. The winning insight corrected the previous stage's own prediction:
   **grow the *quietest* parent, not the best one.**

**The multi-finger cutover (stage 23) — the biggest correction.** The harness had been
emitting each transistor as a single finger, which piles hundreds of ohms of fake gate
resistance onto RF devices nobody would ever build that way. 26–40% of the "noise" was
this artifact. Switching to realistic multi-finger layout (2 µm/finger, user-approved)
made **one fixed design meet tier-2 NF on all four bands at once**. It also revealed
the old harness had **overstated every published NF by ~2 dB**, and that a stability
number had been flattered too. A negative result that survives its confound and points
somewhere new is worth more than the positive it replaces.

**The match wall (stage 24).** With noise solved, the generator's designs still failed
on input match — they put the signal on the wrong pin. A structural instrument (pure
graph arithmetic, no formulas — honoring the blind rules) found the "source-driven
input" motif carries the whole match/no-match split. Selecting for it gave a
**generator-authored** dhruva-l5 design that met Gate D3.

---

## Instrumentation the pipeline had been missing (stages 25–26)

- **The operating point (stage 25).** Every simulation had solved a full DC operating
  point and thrown all but one number away. Capturing it (validated to zero error)
  revealed the sizer had *independently* discovered textbook RF biasing — moderate
  inversion for input devices, strong for output — which nothing had told it to do.
- **The 66,000 free labels (stage 26).** Every sizing run had been logging its interior
  for free. Analyzing it showed a perfect pre-filter would skip **82.6% of a sizing
  run's simulator calls** — four of every five minutes are spent on points that never
  beat the incumbent. The waste is in the *search*, not the simulator.

---

## The null hypotheses that bit back (stages 27, 31, 34)

- **The no-learning generator (stage 27).** A generator with *no learning at all* —
  random wiring inside the device budget — **beats** the trained one on both headline
  metrics (spec-screen pass rate and NDL@256), because a random graph is never a copy.
  But once the simulator runs, only **3%** of random circuits have working
  transistors vs **68%** for the trained one, and the random arm produces **zero**
  feasible designs. Lesson: **what the 11.8M-parameter model buys is DC viability and
  gain capability — and neither headline metric can see that.**
- **Outcome conditioning (stage 28).** Telling the generator what its circuits measured
  raised novelty — but a *shuffled-label control* raised it just as much. The novelty
  came from the new training rows, not the labels' meaning.
- **The sensitivity sweep (stage 34).** The flagship design's match and current draw
  are knife-edge (±1% supply flips them) — by construction, because the optimizer pins
  them at their limits. Noise and gain never flip. Real parts hold current over
  temperature with a bias circuit the vocabulary doesn't have.

---

## The linearity wall — D5 (stages 35, 32, 42–46)

This is the case study's terminal finding, and it was measured **two independent ways**.

- A proper two-tone harmonic-balance harness (VACASK) and a separate ngspice
  two-tone transient harness **agree to 0.08 dB** — on two different simulators with
  two different transistor-model implementations.
- The verdict: **Gate D5 fails by 21–27 dB.** And it's not a sizing problem — the
  design's output linearity (OIP3 ≈ +3 dBm) is *flat* across bands and sizings. It's
  set by the output stage's swing budget on a 1.1 V / 13 mA envelope.
- Even granting the design every allowance the paper permits, **more than half the miss
  survives.** Passing would need an output intercept ~33–55× the entire DC power
  budget.
- **WP-LIN** (rungs 0–4, then a budget-widened retest, then a stability check)
  measured that **no in-box lever reaches the wall**, the wall doesn't move under
  perturbation (worst 2.26 dB vs a 5 dB falsifier), and closing D5 **requires changing
  what the circuit is, not re-sizing what it has.** The null was recorded per the
  user's ruling.

Along the way the other tier-3 gates fell on the flagship point: **D4-SIM** (one
fixed sizing meets all four bands' tier-1+tier-2 at once — and it was *already* true
the day the gate was set), **D6** (gain programmability, met under a proposed mapping),
and **D7** (differential output via an assistant-authored active balun).

---

## The pivot — the survey, the proposal, the two lines (stages 38–41)

- **The literature check (stage 38).** Nine external AI-circuit systems were surveyed
  from primary sources (see [survey.md](survey.md)). Key takeaways: the reward function
  is a solved problem; for one-off sizing, RL loses to plain optimization by 10–100×;
  validity must come from construction; and **run the cheap null first** — this
  program's own stage 27 is an example.
- **The proposal (stage 39).** The survey showed two other groups had independently
  built the same shape of system this program already had. Eight of the user's ten
  "autonomous engineer" points already existed here in v0. The real gaps: machine-usable
  memory, diagnosis steering search, and an unattended mode.
- **The re-aim (stage 41).** The user approved reframing the whole effort: **the product
  is the engineer (the environment + benchmark), and dhruva is the flagship case
  study.** The repo split into two lines — `main` (this LNA work) and `engineer` (the
  environment). See the engineer clean doc for what happened there.

---

## Where it stands (the "current frontier")

The flagship dhruva design is tier-1 + tier-2 feasible on all four bands at one fixed
sizing, with gain programmability and a differential output — but D5 (linearity) is a
measured, stable, physical wall that needs a different circuit. Open threads the doc
flags for whoever picks this up:

- A **generated** (not search-plus-sizing) tier-2 feasible dhruva is the next stronger
  claim; the two feasible labels are the seed for it.
- The dhruva-l5 input-stage problem is a **generator/topology** task, not a sizer one.
- More real-data ingestion is a costed, renewable lever (open silicon tapeouts land
  every 1–2 months), not a free assumption.
- IIP3 stays `unsupported` on the benchmark until the two-tone harness is wired in as a
  standard tier-3 rung.
- Stability is measured but advisory and frequency-only (no process corners, no layout
  parasitics).

And the standing honesty mechanisms it expects to keep: the frozen NDL protocol,
adopt-only-if-better (ties to the incumbent, costs reported even on wins), replay
fences and independent re-audits, device-budget widenings calibrated to real silicon,
the blind protocol, the regression quartet, and explicit user sign-off for any change
to a frozen protocol or a spec.
