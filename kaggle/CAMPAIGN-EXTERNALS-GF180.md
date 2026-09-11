# CAMPAIGN externals-gf180-v0 — round-1 external topologies vs the gf180 wall

Commissioned 2026-09-11 (user round-1 approval C1+C3+C4, recorded in
`kaggle/EXTERNALS-GF180-CANDIDATES.md`). Follows gf180-physaudit-v0's verdict
(all 24 specs TOPOLOGY-GAP; device headroom 39–63 dB; wall = joint circuit
design). Box-side leg only; the GPU retrieval leg (E2) is PUSH-GATED and not
part of this pre-reg's scoring.

## Question

Do process-appropriate published topology families — ingested as
structure-only externals and sized by the STANDARD machinery alone (no LLM,
no playbook, no warm start) — close gf180 ladder cells that the corpus-bred
system has never closed in-era?

## Arms (leg E1, box)

Three legs, one per approved family, run with `kaggle/x0v1_run.py` VERBATIM
(the pre-registered fixed-topology sizing engine; rows will carry its
arm="x0v1" label — the campaign directory + `source_record` fields are the
true identity). `LNA_X0_PRIOR` unset (default off = byte-identical null
sizing path), `--pdk gf180mcu`, budgets = engine defaults (base 2 seeds ×
300 evals, one escalation 3 × 600), all 24 ladder specs per leg:

- leg-c1: cells-c1-inddegen-cascode.json (wl 59447359f981d898, 59 tokens)
- leg-c3: cells-c3-current-reuse.json    (wl 776e0dbed858c221, 73 tokens)
- leg-c4: cells-c4-shunt-feedback.json   (wl a6122feb26e8d4dc, 59 tokens)

All three passed the ingestion gates pre-freeze (parse, round-trip,
Topology.valid, L0 vs cap-e01-wifi, gf180 bias sweep — see
`kaggle/externals/MANIFEST.json`) and all three are NOVEL vs novelty ref-v3
(159 hashes, digest 8f25e960cccff34e): the system has never held these
shapes.

**AMENDMENT 1 (2026-09-11, post-v0-legs — logged deviation).** The v0 legs
ran 0/72, but design forensics showed c1's best designs at idd_ma = 0.0
(never conducted) and c3 running PMOS-only: the v0/v0.1 templates omitted
their published BIAS NETWORKS, and under the default (v1) harness bias
rules a cap-isolated gate gets NOTHING inserted (sweep: biased=false;
the opt-in LNA_BIAS_RULES v3 machinery is NOT used — flipping it would
change the recipe vs every comparison arm). The era-binfix gf180 winner
confirms the house idiom: gate bias lives IN the topology (diode-connected
device feeding the gate node). v0.2 templates therefore carry their
published bias networks as structure (C1: mirror ref R→diode-NM3→R to the
input gate, per Shaeffer-Lee; C3: same for the NMOS gate + diode-PM2
reference for the PMOS gate), input DC-blocked — still zero authored
values. New hashes: c1 dcda50191d7c5e73 (103 tokens), c3 226544590d47717b
(157 tokens); both NOVEL vs ref-v3. NEW LAUNCH FENCE (binding, replaces the
vacuous prep bias gate): 40-eval conduction smoke per family on
cap-e01-wifi must show best idd_ma > 0.05 — passed (c1: 4.74 mA, s21 +9.4,
nf 1.6; c3: 14.7 mA). Scoring is UNCHANGED; the v0 c1/c3 legs are archived
as INVALID-PROBE (transcription flaw, not a physics result) and superseded
by v0.2 reruns; the v0 c4 leg is VALID (self-biased via feedback R) and
stands. c4 hash unchanged a6122feb26e8d4dc.

## Pre-set scoring (frozen before results)

- Primary: per-spec feasible-in-any-leg count, vs the in-era gf180 record —
  arch cold control 0/24 (era-5a87ee18 leg1) and selflearn 0/23 (leg2);
  era-binfix 2/24 noted as best-of-run context.
- CREDIT RULE: a cell counts as externals topology credit iff feasible in
  some leg AND never feasible in any in-era gf180 arm. Attribution is clean
  by construction: sizing-only on a fixed shape (no proposal stage at all).
- Secondary (reported, not scored): per-family solve sets; margins on
  unsolved cells vs the selflearn-leg2 margins; noise caveat from physaudit
  Amendment 2 rides along (gf180 NF numbers are within-model only).
- Noise context: gf180 arch variance is large (2→0 across eras). Any credit
  claim here is protected by the fixed-topology determinism (seeded CMA on
  a single shape — no proposal lottery), but single-run margins are still
  read conservatively.

## Contamination ledger (per G0-FAIRNESS §3 schema, inline)

```yaml
contamination_ledger:
  run_id: externals-gf180-v0
  task: gf180 24-spec ladder, box sizing-only legs
  date: 2026-09-11
  status: declared
  intended_generator: none (fixed external topologies, sizing only)
  transferred_in:
    harness_code: {allowed: yes, present: yes, declared: unchanged lna/ + x0v1_run.py verbatim}
    playbook: {allowed: no, present: no}
    seeds: {allowed: engine defaults, present: yes, declared: x0v1 engine seeding}
    selectors: {allowed: no, present: no}
    calibrations: {allowed: no, present: no}
  prefix_seeding: n/a
  hand_edits: none post-freeze; templates are structure-only (no component
    values exist in the token representation; all values sized from the
    standard gf180 boxes incl. sizable pVB)
  new_templates:
    - {id: c1-inddegen-cascode, source: "Shaeffer & Lee, JSSC 1997 (family)",
       author: claude-transcription, approved: round-1 2026-09-11}
    - {id: c3-current-reuse, source: "Karanicolas JSSC 1996 / inverter-LNA lineage",
       author: claude-transcription, approved: round-1 2026-09-11}
    - {id: c4-shunt-feedback, source: "Bruccoleri et al. JSSC 2004 + Mohan et al. JSSC 2000 (family)",
       author: claude-transcription, approved: round-1 2026-09-11}
```

## Label domain / era

Box host, pdk=gf180mcu, era-ext-<freeze-sha> (commit of this pre-reg; label
carried by output dir name). Store writes: NONE (results stay in campaign
archive; ingestion into corpus_manifest/retrieval is a SEPARATE step, only
after results and only for families that earn it — prevents polluting the
novelty reference with untested shapes).

## Outputs

`kaggle/campaigns/externals-gf180-v0/era-ext-<sha>/leg-{c1,c3,c4}/` — the
engine's results.jsonl/.md + designs/; plus README.md verdict at campaign
root. Deviations logged in README.

## Pre-declared consequences

- Credit ≥ 1 cell: externals lever VALIDATED on gf180 → queue user ruling on
  corpus ingestion of winning families + GPU retrieval leg (E2, push-gated,
  own pre-reg addendum).
- Zero credit with healthy sim-health: joint-design wall survives even
  correct shapes under sizing-only → next lever is the loop's edit/refine
  stage on external anchors (needs own pre-reg), not more shapes.
