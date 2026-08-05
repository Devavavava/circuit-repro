# WP-SIZE — closing the loop with ZOAF

**Answers:** HANDOVER §1 item 3 (no device values → sized, scored circuits).
**Deliverables:** `lna/extract.py` (metrics from ngspice output),
`lna/size.py` (ZOAF driver), a sized-candidate scoreboard.
**Cost:** 3–4 days + compute. **Depends on:** 01-SPEC (objective), 02-REF
(trust anchor), 03-BIAS (conducting circuits). Start only after those gates.

---

## 1. Shape of the loop

Per candidate topology (post-bias, L1-conducting):

```
.param surface (to_spice.py) ──> x ∈ R^d  (d ≈ 6–14)
        │                              │
biased .cir template          ZOAF (misc/ZOAF, generic f: R^d → R API)
        │                              │
        └── substitute x → run ngspice_con → extract.py → spec.objective() ──┘
```

* **Parameter vector.** From the emitted `.param`s, per 01-SPEC `sizing:`
  bounds: MOS widths (log-scale), R (log), C (log), L in [l_min, l_max] (log),
  inserted pVBG voltages (linear). Channel length pinned at `l_fixed` — RF
  devices at minimum L; halves the MOS dimensions for free. All variables
  normalized to [0,1]^d inside the optimizer (ZOAF clips to the box natively).
* **Evaluation.** One ngspice_con run per point: `op` + `sp` + `noise` over
  the spec band (reuse the to_spice control block; write params via a
  one-line `.include params.inc` rather than regenerating the netlist).
  `extract.py` parses S11/S21 across the band, NF at f0 (and band edges for
  wideband), Idd from the op point — returns the metrics dict `spec.report()`
  and `spec.objective()` consume. ~1 s/eval measured.
* **Objective (feasibility-first, per 01-SPEC D2).**

  ```
  if any hard constraint violated:  f = 1 + Σ_i  v_i / s_i      (normalized violations)
  else:                             f = − Σ_j w_j · (m_j − floor_j)/s_j   (weighted objectives)
  ```

  The `1 +` offset guarantees every feasible point beats every infeasible one
  — ZOAF minimizes a single float, and this encoding keeps D2's hard/soft
  separation intact through the scalar boundary. Report feasibility separately
  in all output; never let a scalar hide a constraint miss.

## 2. Budget and parallelism

~1 s/eval ⇒ 600–1200 evals ≈ 10–20 min per candidate on one core. ngspice is
single-threaded and the box has 8 threads: run **4–6 candidates in parallel**
as processes (`size.py --jobs 5 --candidates dir/`). Sizing 30 candidates
overnight is comfortable; a screened batch of ~50 conducting candidates from
128 samples costs roughly one night. ZOAF settings to start: hybrid init
sampling, `n_starts=4`, `sgd_iterations≈8`, then CGD refinement — mirror the
10-param example's recipe (`misc/ZOAF/examples/quickstart_10param.py`) and
tune only if convergence stalls.

## 3. Trust ladder (do not skip rungs)

1. **Anchor re-derivation.** Strip the stage-B reference LNA (02-REF) to
   `.param` defaults, hand `size.py` its topology + the `wifi24` spec.
   Acceptance: sizer reaches feasibility and lands within ~1 dB of the
   hand-tuned reference on every constrained metric. This is the single most
   informative test in the whole plan — it validates extract.py, the
   objective encoding, the bias params, and ZOAF's budget at once, on a
   circuit whose answer is known.
2. **CG anchor under `wideband-sdr`** (cheap second point, inductorless path).
3. **Generated candidates.** Top ~30 by L0+L1 from the best 04-GEN arm,
   sized against `wifi24` and `wideband-sdr`. Output: scoreboard CSV + a
   FINDINGS-style table — per candidate: spec, feasible?, metrics, eval count,
   novel-vs-corpus (P0 metric). Even a handful of feasible novel topologies
   is the program's first end-to-end result: **spec in, novel sized LNA out.**

## 4. Known holes, called now

* **IIP3 stays unmeasured** (spec `status: unsupported`). Two-tone `tran` +
  FFT harness is a stretch WP (06-SCHEDULE); do not bolt it on mid-sizing.
* **Idealized passives.** No inductor Q, no pad/package parasitics. Sized
  NF/S11 will be optimistic — fine for ranking topologies, wrong for absolute
  claims; say so in every scoreboard header. Adding series-R to inductors
  (Q ≈ 10–15 at band) is a one-line netlist upgrade worth doing in v1.1.
* **Local optima.** ZO methods on multimodal RF surfaces stall; the mitigation
  is ZOAF's multi-start (already built in) plus the L1 sweep's bias starting
  point. If > half of anchor-test runs miss feasibility, raise `n_samples`
  before inventing anything cleverer.
