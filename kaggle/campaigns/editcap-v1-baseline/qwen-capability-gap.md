# Can Qwen reach Claude's solutions? (topology-repertoire analysis)

Compared Claude's working topologies (kaggle/claude-solutions/templates/) against
Qwen's actual arm-B edits (structural scan, analyze_qwen_vs_claude_topo.py).

## Narrowband (Claude soln = cascode-CS + LC tank)
- Qwen edits (bnl-1575/bnl-09, n=29): cascode+tank present in **6/29**.
- => Qwen CAN reach this structure (it's in its repertoire, ~20%). Gap =
  RELIABILITY + clean netlist execution (Exp2: G-S shorts, drain->wrong node).

## Wideband (Claude soln = resistive shunt-feedback, Rf drain->input-gate)
- Qwen edits (bnl-wb, n=64): shunt-feedback present in **0/64**. Never.
- Qwen stays reactive-only (shunt/series L, LC tanks; tank in 64/64) e.g.
  "L4 n0 VSS ; shunt inductor for input matching". A 6:1-band match cannot be
  flattened with reactance alone.
- => Qwen CANNOT currently reach this; it lacks the CONCEPT of resistive
  broadband feedback. A genuine capability gap, not reliability.

## Fine-tuning implication
- Narrowband: make Qwen apply cascode+tank consistently and emit valid netlists.
- Wideband: TEACH the missing topology class (resistive shunt-feedback LNAs) --
  the highest-value data to inject.
Caveat: analyzed Qwen edits from the gf180 baseline (its repertoire is process-
independent); a direct Qwen-on-bench-v1.2 run would confirm, pending.

## AUDIT CAVEATS (2026-09-26)
- Every count here comes from the **gf180 3072-token baseline edits**, not bench-v1.2.
- The shunt-fb detector requires the resistor to land on a MOS drain; an R from a
  tank node to the input gate (seen in the few-shot n10-g10 solve) is missed, so it
  can undercount. On the gf180 set a broader scan found only 1 extra R touching a gate.
- A direct measurement on bench-v1.2 (ZS vs FS, 32B + 14B) = E-d,
  `kaggle/PREREG-BENCH-V12-AUDIT.md`.
