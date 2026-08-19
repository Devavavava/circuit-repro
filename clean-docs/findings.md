# FINDINGS — the measurement log, cleaned up

*Clean version of `lna/FINDINGS.md` (~10,000 lines, 47 numbered findings). That file
is the durable evidence base: every LNA result, measured not asserted, in the order it
happened. This is a plain-language tour of what it establishes. For the story in order,
read [journey.md](journey.md); for exact numbers and methods, go to the cited `§N` in
the original.*

## What this document is

`FINDINGS.md` is a lab notebook, not a report. Its rule is that every claim carries the
number that backs it and the file/section that produced it, and corrections are added
as dated notes rather than silently overwriting the original. The clean version below
groups its findings by theme instead of by date.

## The bottom line (FINDINGS "Bottom line", §1–3)

- The **measurement side was always ready.** ngspice does noise figure, gain, input
  match (S-parameters), and operating point — all confirmed by direct probe.
- **AnalogGenie can represent LNAs** (inductors are in its vocabulary; 41 real LNAs sit
  in its data, ~1.2% of the corpus), and topology reconstruction is **exact**.
- What was missing was **targeting**: no way to *ask* for an LNA, no bias network, no
  device values. Almost everything in the file is about closing that gap.
- Inductors are the signature of an LNA: **20.3%** of devices in the LNA subset vs
  **0.8%** corpus-wide. The structural screen keys on that ratio.
- One tool that looked perfect for scoring LNAs — ZeroSim — has **no inductor and no RF
  port** in its vocabulary. Using it would produce confident nonsense.

## Steering generation without retraining (§5)

- **Prefix conditioning**: seed the generator with the first ~12 tokens of a real LNA
  and the LNA hit rate goes **0% → 40.6%**, no retraining. 94% of candidates simulate;
  16 distinct novel LNAs per run.
- It's a knob with a ceiling: longer prefix → higher hit rate but the output becomes a
  **verbatim copy** of the seed. Yield and novelty trade against each other.
- **P4** (biasing the decoder toward inductors) is a weak lever — the inductor gap is a
  **data** problem, not a decoding one.

## The verified gaps (§4)

1. Generation is unconditional — you get whatever the corpus favors (op-amps, LDOs).
2. Topologies carry **no bias network**, so a reconstructed transistor sits switched
   off. The model can't fix this — the information was never in the training data.
3. Some nodes have no DC path and break the operating-point solve (fixed later by the
   bias rules and finite-Q inductors).
4. No device values — the generator emits topology only.

## The frozen scoreboard — NDL@256 (§5, §14.5, §19.3)

"Novel Distinct LNAs per 256 samples": WL-graph-hashed (so Eulerian reorderings of the
same circuit count once), screen-passing, and absent from a **versioned, digest-pinned
reference set**. The reference was rebaselined twice, and *how* it changed is itself a
finding:

- **ref-v1** (41 corpus circuits) let a generator's copies of its own training
  templates score as "novel" — ~51% of one pool was exactly that.
- **ref-v2** (+148 archetypes) fixed it. The correction was **not uniform** (0 to −50
  depending on how much template data an arm trained on) and **not order-preserving** —
  so it had to be checked that no past adopt/reject decision actually flipped. None did.
- **ref-v3** (+9 real externals) measured **exactly zero** correction on every existing
  checkpoint — proof a reference expansion only perturbs history if something in that
  history could have copied the new content.

## The NF correction — the sharpest single fix (§11, §13)

Every "feasible" design had used an NF measurement that was **silently wrong in one
direction for the whole life of the program** (it even read *negative* NF once a stage
had gain). Building the physically-correct series-Rs measurement and comparing:

- The old NF had flattered every design by a median **+2.3 dB** (up to +12.6 dB).
- Re-judging 14 feasible designs: tier-1 held for all 14; **tier-2 (NF) held for only 2**.
- The lesson written into the record: **a supported-but-missing metric counts as fully
  violated.** Advisory metrics are a debt.

## The critic (§11, §14, §20)

A learned pre-SPICE filter that predicts a topology's post-sizing margins, so search
doesn't waste 5-minute sizing runs on hopeless candidates.

- Simple baselines (nearest-neighbor, ridge) were mandatory before any GNN. The GNN
  **lost** the gate to nearest-neighbor on an early snapshot and only shipped once the
  data justified it.
- Every early failure traced to one root cause: the generator had **memorized ~35
  graphs**, so candidates were near-duplicates a critic can't rank.
- A silent bug had been dropping ~240 broadband rows from every critic. Fixing it
  (not the model) jumped the hard "source-shift" correlation from 0.22 to 0.59.
- **Gate C1 was restated** because its literal "≥2× enrichment" bar was getting
  *harder* as the pipeline improved — backwards. The new "skill" bar is 0 for random
  selection and 1 for a perfect ranker at any base rate.

## The Gate-D3 arc — noise on the dhruva bands (§17, §23, §25)

The single clearest example of diagnosis deepening in public: "a missing measurement" →
"a search failure" → "a conversion rate" (the noise/gain trade measured as dB-per-dB) →
"a device-budget decision" (widened twice, each time calibrated to the nearest real
silicon device count, never to what closes the gate — and honestly noting the gate
needed 20 devices, not the 21 granted) → **MET on dhruva-s**, with the winning insight
correcting the prior stage: **grow the quietest parent, not the best one.**

## The multi-finger cutover — a device nobody would build (§26, §27-in-JOURNEY)

The harness had emitted each transistor as a **single finger**, loading RF devices with
hundreds of ohms of fake gate resistance. **26–40% of every design's excess noise** was
this artifact.

- Switching to realistic 2 µm-per-finger layout (user-approved) made **one fixed design
  meet tier-2 NF on all four dhruva bands at once.**
- The store-wide relabel put a number on the old error: NF had been **overstated by a
  median of 2.08 dB** across 1,240 rows.
- It also exposed a stability number that had been flattered by the same fake resistor —
  so every stability count taken through the old harness is a **lower bound**.

## The match wall (§29)

With noise solved, generated designs still failed **input match** — they put the signal
on the wrong pin. A structural instrument (pure graph arithmetic — no impedance, no
formula, honoring the blind protocol) found the **source-driven input motif** carries
the whole match/no-match split (58% match vs 13%). Selecting for it produced the first
**generator-authored** Gate-D3-feasible dhruva-l5 design.

## The instruments that were free all along (§30, §33)

- **Operating point (§30).** Every simulation solved a full DC operating point and kept
  one number. Capturing the rest (validated to **0.0 error**) showed the sizer had
  *independently* found textbook RF biasing. Also a correction: "saturated" in this
  program means *conducting with headroom*, not *strong inversion*.
- **The 66k free labels (§33).** Every sizing run logged its interior for free. A
  perfect pre-filter would skip **82.6%** of a cold-start run's simulator calls. The
  waste is in the search, not the simulator. A point-surrogate model captures ~43% of
  that today at zero cost to the answer.

## The null hypotheses (§31, §32)

- **No-learning generator (§31).** Random wiring inside the device budget **beats** the
  trained generator on both headline metrics — because a random graph is never a copy.
  But after biasing, only **3%** of random circuits have all transistors conducting
  (vs **68%** trained), and they produce **zero** feasible designs. So the trained model
  buys **DC viability and gain capability** — invisible to both headline metrics, and
  one of them is *anti-correlated* with it.
- **Outcome conditioning (§32).** Feeding measured results back raised novelty — but so
  did a **shuffled-label control**. The gain was the new training rows, not the labels'
  meaning.

## The linearity wall — Gate D5 (§37, §40, §44–48)

The case study's terminal finding, measured **two independent ways that agree to
0.08 dB** (ngspice two-tone transient vs VACASK harmonic balance, different simulators
and different transistor models):

- **D5 fails by 21–27 dB** on every band.
- It's **not** a sizing problem — output linearity (OIP3 ≈ +3 dBm) is flat across bands
  and sizings. It's set by the output stage's swing budget on 1.1 V / 13 mA.
- Even granting every allowance the paper permits, **more than half the miss survives.**
- **WP-LIN** proved no in-box lever reaches the wall, a device-budget widening didn't
  move it, and it's **stable under perturbation** (worst 2.26 dB vs a 5 dB falsifier).
  Closing D5 needs a different circuit, not a re-size. The null was recorded per the
  user's ruling; the levers that *would* move it (output reference impedance, supply
  envelope, or relaxing the spec) are named as separate open user decisions.

## The other tier-3 gates, on the flagship point (§35, §41, §42)

- **D4-SIM** — one fixed sizing meets all four bands' tier-1+tier-2 at once. It was
  *already* true the day the gate was set; per-band re-sizing had only been buying
  margin.
- **D6** — gain programmability (≥10.6 dB in ≥3 steps) met under a proposed mapping. The
  finding that outlasts the pass: the design's match margin is a *spatial* constraint,
  so gain control could only live at the back of the amplifier — which buys range but
  not linearity.
- **D7** — differential output met via an assistant-authored active balun, costing ~1 mA
  and 1.6 dB of gain on the hardened point.

## The Phase-4 execution wave (§43)

Seven agents ran the cheap levers from the proposal in one afternoon; everything
adoption-shaped was **measured and queued, not adopted**. Three results mattered: the
label store had quietly become a **liability** (it was labeled against a simulator that
no longer exists — fixed by a mechanical re-label); the sizer met its **null** (untuned
CMA-ES beat ZOAF 4/5 vs 1/5 at matched budget on the first task); and the memory was
made **machine-queryable** (a 40-entry playbook, contradictions kept as edges, not
smoothed away).

## The reproducing section (§10)

The file ends with the exact commands to rebuild the corpus, confirm the screen still
separates LNAs, run end-to-end yield on known-good topologies, generate on GPU, screen
the output, and simulate a candidate. See `lna/FINDINGS.md §10` and the tool list in
`lna/HANDOVER-EXEC.md`.
