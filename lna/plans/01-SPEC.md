# WP-SPEC — the LNA specification format

**Answers:** HANDOVER-FABLE §4, all five questions, plus H-Q4.
**Deliverables:** `lna/spec.py`, three spec files in `lna/plans/specs/`
(move to `lna/specs/` when implemented), spec-driven `screen.py`.
**Cost:** ~2 days. **Depends on:** nothing — this can start immediately.

---

## 1. Design decisions and why

**Format: YAML, one file per target.** Boring is correct here. The interesting
decisions are semantic, not syntactic:

**D1 — the spec compiles; nothing reads it ad hoc.** `spec.py` loads and
validates a spec and exposes exactly three views of it:

| View | Consumer | Works on |
|---|---|---|
| `spec.structural_screen()` | `screen.py` | unsized topology |
| `spec.objective()` | sizing loop (05-SIZING) | sized, simulated circuit |
| `spec.seed_filter()` | `generate.py` | corpus circuits used as prefix seeds |

If a consumer needs something the spec doesn't express, the spec grows — no
side channels. This is what makes question §4-Q3 ("constrain generation, not
just evaluation") answerable at all: generation, screening and sizing read the
*same* object.

**D2 — hard constraints and soft objectives are structurally separate**
(§4-Q2). `constraints:` is a dict of pass/fail limits; `objectives:` is an
ordered list of quantities to improve *after* all constraints pass. They are
never blended into one scalar except at the ZOAF boundary, and there only
feasibility-first (05-SIZING §3): infeasible points are ranked by total
normalized violation, feasible points by objective value. NF and S11 are
constraints; gain beyond its floor and power below its budget are objectives.
This matches how an RF engineer actually reads a datasheet requirement.

**D3 — every metric declares its evaluation level.** The central problem of
§4-Q1 is that most spec numbers are meaningless before sizing. The resolution
is to tag each requirement with the earliest pipeline stage that can check it:

* **L0 — structural** (unsized topology): checkable from the graph alone.
* **L1 — default-valued simulation**: checkable after bias insertion with
  placeholder values; only sanity, never pass/fail on performance.
* **L2 — sized simulation**: the real requirement, checked after ZOAF.

`screen.py` evaluates L0 only. The sizing loop evaluates L2. L1 exists to
discard candidates that cannot even produce a DC operating point — it is a
yield gate, not a performance gate. A spec never claims a topology "meets NF"
at L0; it claims the topology is *not structurally disqualified* from meeting
it. That is the honest limit of pre-sizing screening.

**D4 — the spec's structural screen is derived, not hand-written.** H-Q4
showed the fixed 5-criterion screen caps real LNAs at 59.4% because 40% of
them are inductorless. The screen was never wrong — it encoded exactly one
target (narrowband, inductor-matched) for all time. Under this WP the L0
criteria are *generated from the spec*:

| Spec property | Derived L0 criteria |
|---|---|
| `band.type: narrowband` | ≥1 inductor OR ≥1 C in a resonant-capable position; tuned-load plausible |
| `band.type: wideband` | inductors optional; feedback path or 1/gm-match stage plausible |
| `topology.max_inductors: N` | inductor count ≤ N |
| `topology.differential: false` | exactly one VIN net |
| ports required | VIN present; VOUT present |
| any spec | ≥1 transistor; device count in `topology.device_budget`; bias-insertable (03-BIAS R-checks pass); no floating sub-circuit (H-Q3 detector) |

Under `wideband-sdr`, a resistive-feedback LNA scores full marks with zero
inductors. The 59.4% ceiling disappears because the question "what fraction of
all real LNAs pass" stops being meaningful — the right calibration question
becomes "what fraction of real LNAs *of this spec's class* pass," and that
should be ≈100%. Calibration task below re-runs the ground-truth split per
spec.

**D5 — unsupported metrics are declared, not silently dropped.** Linearity
(IIP3/P1dB) needs a two-tone transient or `.disto` harness that does not exist.
A spec may state `iip3_dbm: {min: -5, status: unsupported}`; `spec.py` loads
it, reports it as *declared but unmeasured* in every output, and the objective
ignores it. This keeps specs honest against real standards without blocking on
harness work. Building the two-tone harness is a stretch WP (06-SCHEDULE).

---

## 2. Schema

```yaml
# lna/specs/wifi24.yaml — annotated schema reference
name: wifi24
description: 2.4 GHz ISM-band WiFi front-end LNA (802.11b/g/n)

process:
  models: AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/spice_models/45nm_bulk.txt
  vdd: 1.1                  # V — fixed by process assumption
  temp: 27

band:
  type: narrowband          # narrowband | wideband
  f0: 2.442e9               # Hz — centre (ch. 7); evaluation frequency
  f_lo: 2.400e9             # Hz — band edges; constraints hold across the band
  f_hi: 2.4835e9

ports:
  z0: 50                    # ohm, both ports
  input: VIN1               # dataset net-name conventions
  output: VOUT1

constraints:                # hard: all must hold at L2, across [f_lo, f_hi]
  nf_db:      {max: 2.5}
  s11_db:     {max: -10}
  s21_db:     {min: 12}
  idd_ma:     {max: 5}      # from VDD, excludes bias-gen scaffolding current
  iip3_dbm:   {min: -5, status: unsupported}   # declared; harness cannot measure yet

objectives:                 # soft: improve after constraints pass, in priority order
  - {metric: s21_db,  direction: max, weight: 1.0}
  - {metric: idd_ma,  direction: min, weight: 0.5}
  - {metric: nf_db,   direction: min, weight: 0.5}

topology:                   # L0-checkable structural facts
  differential: false
  device_budget: [3, 12]    # devices, excluding inserted bias scaffolding
  max_inductors: 3          # area proxy
  l_min: 0.3e-9             # H — smallest realizable on-chip inductor
  l_max: 12e-9              # H — largest acceptable spiral
  allow_inductorless: false # narrowband tuned target wants a matched/tuned path

sizing:                     # bounds handed to the sizer (05-SIZING)
  w_um:  [1, 200]           # MOS width, log-scale
  l_fixed: 45e-9            # keep channel length at minimum for RF
  r_ohm: [50, 20e3]         # log
  c_f:   [50e-15, 10e-12]   # log
  vb_v:  [0.2, 0.9]
  # inductors take [l_min, l_max] from topology
```

`spec.py` requirements:

* Load + schema-validate (fail loudly on unknown keys — silent typo tolerance
  in a spec file is how wrong constraints ship).
* `structural_screen(topology) -> (passed: bool, criteria: dict)` per D4.
* `objective(metrics: dict) -> float` per D2/05-SIZING §3, plus
  `feasible(metrics) -> (bool, violations: dict)`.
* `seed_filter(corpus_index) -> bool` per §5 below.
* `report(metrics)` → human-readable pass/fail table, including
  `unsupported`-status constraints listed as UNMEASURED.
* No pandas/pydantic dependency needed; PyYAML + a hand validator is fine and
  keeps the WSL/Windows envs identical.

---

## 3. The three reference targets (§4-Q4)

Numbers are pulled from published-standard context, not invented; each is
deliberately a *different design problem* so the spec machinery is exercised,
and each carries a rationale comment in its YAML.

**`wifi24` — 2.4 GHz ISM narrowband** (file above). Typical published 45–65nm
CMOS WiFi LNAs sit at NF 2–3 dB, gain 12–20 dB, 2–6 mW. NF ≤ 2.5 dB,
S21 ≥ 12 dB, S11 ≤ −10 dB, Idd ≤ 5 mA @ 1.1 V. Narrowband tuned; inductors
expected. This is the primary bring-up target and the one the reference LNA
(02-REFERENCE-LNA) anchors.

**`gps-l1` — 1.57542 GHz, noise-first.** GPS signals arrive at ≈ −130 dBm;
the LNA NF dominates receiver sensitivity, and the L1 C/A band is only ~2 MHz
wide (20 MHz including P(Y)). NF ≤ 1.8 dB (constraint that actually binds),
S21 ≥ 15 dB, S11 ≤ −10 dB, Idd ≤ 3 mA. Narrowband; this spec is the one that
justifies inductive degeneration and will stress the l_min analysis (§6).

**`wideband-sdr` — 0.5–3 GHz general-purpose front end.** SDR/TV-tuner class:
NF ≤ 3.5 dB across the band, S21 ≥ 12 dB with ≤ 2 dB ripple (ripple is L2-only,
computed from the sweep), S11 ≤ −10 dB across the band, Idd ≤ 8 mA.
`allow_inductorless: true`, `max_inductors: 1`. This target legitimizes
resistive-feedback and common-gate topologies — the H-Q4 population — and is
the spec under which the screen's old 59.4% "ceiling" becomes the *point*.

A fourth target was considered and **explicitly excluded: 28 GHz mmWave.** The
BPTM 45nm predictive model has no layout parasitics, no NQS, no substrate
network; at mmWave those dominate. Numbers produced there would be fiction.
Revisit only with a better model, and say so in the spec directory README.

---

## 4. Calibration tasks (acceptance criteria for this WP)

1. **Ground-truth split per spec.** Run the spec-driven L0 screen over the 41
   real LNAs. Expect: `wifi24`/`gps-l1` pass the inductor-bearing majority
   (~60%), `wideband-sdr` passes most of the inductorless remainder. Overall
   union coverage of real LNAs across the three specs should be ≳90% — if it
   is not, the derived criteria are mis-tuned. Non-LNA circuits (indices
   14, 17, 20, 22 as before) must still pass 0 specs.
2. **Screen replacement is lossless.** With a `legacy-lna5` spec written to
   mimic the old 5-criterion screen, `screen.py --spec legacy-lna5` must
   reproduce the historical numbers (59.4% corpus, 40.6% at the recommended
   operating point) exactly. This pins the refactor.
3. **`pipeline_yield.py --spec wifi24`** runs end to end and reports per-stage
   attrition with the spec name in the header.
4. Regression trio still green.

---

## 5. Spec-constrained generation (§4-Q3)

Cheap and immediate (this WP): `spec.seed_filter()` — conditioned generation
draws prefix seeds only from corpus LNAs matching the spec's structural class.
For `wifi24`/`gps-l1`: the inductor-bearing LNAs. For `wideband-sdr`: the
inductorless feedback/common-gate ones. The prefix trick stays the same; the
seed pool becomes spec-aware. Expected effect: inductor ratio of conditioned
samples rises for narrowband specs without any decoding change, because the
current seed pool mixes both classes.

Deeper coupling belongs to 04-GENERATION: class-token fine-tuning can carry a
*per-spec-class* token (`<LNA_NB>` / `<LNA_WB>`) if the template corpus (P5)
provides labels, and the inductor logit bias (P4) takes its target ratio from
the spec class. The spec file is the single source of truth for both.

---

## 6. The minimum-inductor constraint (§4-Q5)

Short version: **the constraint binds only at peak-fT bias, and peak-fT bias
is the wrong operating point anyway.** `Ls = Z0/ωT` with fT = 300–600 GHz gives
12–27 pH — unbuildable, F1 was right. But ωT here is the *effective* ωT of the
input device, gm/(Cgs+Cex), and both terms are design variables:

* The power budgets in all three specs (3–8 mA) force bias well below peak-fT
  current density.
* An explicit gate–source capacitor Cex raises the capacitance term at will:
  Ls = Z0·(Cgs+Cex)/gm. With gm = 20 mS and Cgs+Cex ≈ 450 fF, Ls ≈ 1.1 nH and
  the gate resonance inductor lands ≤ 10 nH — both inside [l_min, l_max].

So the canonical topology is **not** ruled out on this process; it is ruled
out *at the bias point F1 probed*. The full worked design and the measurement
that verifies this is 02-REFERENCE-LNA §3. The spec encodes the constraint as
`topology.l_min/l_max`, and the L2 check is simple: any sized inductor value
outside the range fails feasibility. An L0 version is impossible (values don't
exist yet), which is fine — l_min binds at sizing, and the sizer's bounds
enforce it by construction.
