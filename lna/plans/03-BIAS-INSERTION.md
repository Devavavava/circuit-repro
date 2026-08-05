# WP-BIAS — rule-based bias insertion

**Answers:** HANDOVER §1 item 2, §6 item 4.
**Deliverables:** `lna/bias.py`, `pipeline_yield.py --bias`, before/after
validation table over the 40 simulatable dataset LNAs.
**Cost:** 2–3 days. **Depends on:** nothing. **Blocks:** all of 05-SIZING —
until transistors conduct, every performance number is noise.

---

## 1. Position

Of the three options in FINDINGS §8 Phase 3 — rule-based, template-based,
co-generate — the answer is **rule-based, deliberately minimal, escalated only
by measurement**:

* **Co-generation is rejected.** Extending the vocabulary with bias nets and
  retraining means new sequences the checkpoint has never seen, a larger
  effective corpus requirement, and a coupling between the hardest unsolved
  problem (data scarcity, 04-GENERATION) and a problem that graph rules solve
  deterministically. Wrong trade on this hardware, and it bloats sequences the
  model must learn to emit.
* **Template recognition is the fallback, not the start.** It is strictly more
  code, and we do not yet know it is needed — that is exactly what the
  validation table below measures. If gate-bias rules alone put ≥80% of
  dataset LNAs into a sane operating region, templates stay unbuilt.
* **Rules are cheap to trust** because they operate on the exact graph
  `topology.py` already reconstructs, and their output is *scaffolding marked
  as scaffolding* — never confused with the topology under evaluation.

One principle drives the rule design: **insert the least circuit that makes DC
bias definable, and push all *values* to `.param` so the sizer owns them.**
Bias insertion makes a circuit *biasable*; the sizing loop makes it *biased
well*.

## 2. The rules

All analysis runs on a **DC-connectivity graph**: nodes = electrical nodes,
edges = devices that conduct at DC (R, L, direct wires, voltage sources).
Capacitors are open; MOS channels are *not* DC edges (a channel needs bias
to conduct — that is the thing being established). Driven nets: VDD, 0, any
VB*/VCM*/VREF* already emitted by `to_spice.py`.

* **R-GATE (the load-bearing rule).** For every MOS gate node with no DC path
  to a driven net: attach `RBIASk <gate-node> VBGENk {pRBk}` (default 100 kΩ)
  to a fresh bias net, plus `VBGENk` DC source at `.param pVBGk` (default
  0.5 V) and bypass `CBYPk VBGENk 0 10p`. One *shared* bias net per connected
  gate group, one param each — the sizer sweeps them independently.
* **R-CASCODE-BYPASS.** A gate node that *has* a DC path but through ≥ 100 kΩ
  equivalent and no capacitor to ground gets a bypass cap. (Cheap approximation:
  any inserted VBGEN net gets one automatically; existing VB nets get one too.
  This is also the H-Q1 lesson institutionalized.)
* **R-DIAGNOSE-ONLY for drains/sources.** Do *not* insert drain feeds or
  source references in v1. Textbook LNAs virtually always give drains a DC
  path through their load; measure how many circuits actually fail for
  drain/source reasons before adding rules. `bias.py --report` must classify
  every un-biasable node it finds (gate/drain/source, and why) so v2 rules are
  data-driven rather than speculative.
* **R-FLOAT (H-Q3).** Devices in a connected component containing no driven
  net and no port → flag `floating_subcircuit`, skip the circuit, count it in
  the report. This formalizes the index-1081 failure instead of rediscovering
  it.

Naming contract: every inserted element matches `^(RBIAS|CBYP|VBGEN)` and
`bias.py` records them in a sidecar JSON. `screen.py`, `novelty.py`
fingerprints, and the spec's `device_budget` all exclude them by that contract
— generated-topology identity must not change because scaffolding was added.

## 3. Making inserted bias *useful*, not just present

After insertion, run a **coarse feasibility sweep** per circuit (this is L1 in
the spec's evaluation ladder): grid pVBGk ∈ {0.35, 0.45, 0.55, 0.65} V
(independent grids only if ≤ 2 bias nets; otherwise sweep jointly at 3 points
each), simulate `op` only, and keep the best point by the criterion:

    every MOS has |Id| ≥ 50 µA  and  |Vds| ≥ 1.5×|Vdsat|   (saturation-ish)

Store the winning point in the sidecar as the sizer's starting values. `op`
costs ~0.1 s, so even 4² grids over 128 candidates are ~2 minutes. If no grid
point conducts, classify the failure (usually a drain with no DC path —
feeding the v2 rule decision).

## 4. Validation and acceptance

Run over the **40 dataset LNAs that already simulate** (ground truth — if the
rules can't bias real LNAs, they can't bias generated ones):

| metric | acceptance |
|---|---|
| circuits where all MOS conduct (criterion above) after sweep | **≥ 80%** (32/40) |
| circuits made *worse* (previously conducting, now not) | 0 |
| circuit 461 spot check | Vgs moves from 14 mV to a deliberate 0.35–0.65 V value |
| regression trio + `check_ref.py` | green |

Then over 128 generated candidates at the recommended operating point
(prefix 12, 256-cap): report the new pipeline table with a `biased+conducting`
stage between `simulates` and done. Expect the 48/128 "simulates" number to
split into conducting vs not; **that split is the WP's real output**, because
it is the denominator 05-SIZING starts from.

Failure mode to watch: R-GATE ties a gate that was *intentionally*
signal-only (e.g. the input device gate behind the port DC-block — its bias
now comes from RBIAS, which is correct and is exactly how real LNAs do it) —
but a gate inside a feedback loop may get double-biased. The `--report`
classification catches this: any circuit whose op point degrades after
insertion is a rule bug, and the 0-made-worse acceptance line above is the
tripwire.

## 5. Interface

```bash
python lna/bias.py netlist_in.cir --topology seq0003.txt -o biased.cir --report bias.json
python lna/pipeline_yield.py --generated lna/out/run1 --spec wifi24 --bias
```

Implementation note: operate on the `Topology` object + emit through
`to_spice.py`'s Netlist class (add an `extra_elements` hook) rather than
text-patching netlists — the graph is the source of truth, and text-level
insertion would fight the case-insensitivity traps (X1/X2) all over again.
