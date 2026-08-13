# WP-DHRUVA "best solution" — four-band Gate-D3 design, reproduction artifacts

Files here pin the program's best answer, so far, to the blind-protocol paper
target (`lna/plans2/08-DHRUVA-GOAL.md`; see `lna/FINDINGS.md` §25/§27 and
`lna/JOURNEY.md` stages 22–23 for the full narrative). Read
`lna/repro/dhruva-best/REPORT.md` for the readable report — this file is the
file index and the recreate commands.

## The result, one line

One topology (`wl_hash ace8383c2fa68d03`, 20 devices / 2 inductors), sized
independently per band, is tier-2 feasible (S11 ≤ −10 dB held over
1.1–2.5 GHz, S21 ≥ target, Idd ≤ 13 mA, **NF ≤ target**) on **all four**
`dhruva-s / dhruva-l1 / dhruva-l2 / dhruva-l5` bands, with roughly 1–2.2 dB of
NF margin to spare on every band. Freshly re-verified for this package — see
REPORT.md §4 for the fresh-vs-claimed table.

## Files

- `tokens.json` — the topology in AnalogGenie arrow-token form (215 tokens),
  shared by all four bands: only device *values* differ per band, not the
  circuit.
- `dhruva-{s,l1,l2,l5}.params.json` — the sized device values (W/L, R, C, L,
  bias) for each band, pulled verbatim from `lna/data/topo_labels.jsonl`
  (recipe `mf2-v1`, the post-multi-finger-cutover NF-descent points that
  match the FINDINGS §27.4 table exactly).
- `dhruva-{s,l1,l2,l5}.meta.json` — each row's `wl_hash`, spec, recipe,
  `provenance` block (move, parent hash, source arm, seed) and the stored
  margins, so the lineage is auditable without re-parsing the label store.
- `dhruva-{s,l1,l2,l5}.sp` — the full, standalone, runnable ngspice deck per
  band (topology + bias + sized values + an S-parameter/stability control
  block). Verified to run directly with `ngspice_con.exe -b <file>.sp`,
  independent of the Python harness.
- `recreate.py` — the runner. See below.

## Recreate

Run from the repo root (`lna-data`). Needs the torch-free analysis Python
(numpy + ngspice on `PATH`, or set `NGSPICE=<path to ngspice_con.exe>`); no
GPU needed.

```
# fresh replay, all four bands, one pass each — S11/S21/Idd/NF/K vs the FINDINGS
# §27.4 claim (prints a delta table):
python lna/repro/dhruva-best/recreate.py

# full audit ladder (5x repeats, in-box check, wide 0.1-20 GHz stability,
# novelty check) -- the same evidence ladder as lna/_nf_gate_d3.py:
python lna/repro/dhruva-best/recreate.py --audit

# per-element noise budget (extract.measure_noise_budget) for one band:
python lna/repro/dhruva-best/recreate.py --band s --noise-budget

# Gate-D4-SIM matrix (FINDINGS §35): every shipped sizing evaluated against
# ALL FOUR band specs -- one fixed sizing, all bands simultaneously. All 16
# cells PASS. Designated single-LNA point since 2026-08-13 (user ruling,
# plans2/14-DHRUVA-SIMUL.md §2.1): the margin-hardened dhruva-simul.params.json
# at pVDD=1.2 V (FINDINGS §36; survives the full corners.py sweep). The
# dhruva-l5 sizing was the first D4-SIM closure and stays archived here
# (⚠ it fails the Idd gate at 1.2 V):
python lna/repro/dhruva-best/recreate.py --cross

# rebuild the dhruva-<band>.sp deck files from tokens.json + params.json:
python lna/repro/dhruva-best/recreate.py --build-decks

# re-derive a band's sizing from scratch via the actual recipe
# (constrained_descent minimizing NF, seeded from this design's own dhruva-s
# point, trust region on S11/Idd) -- demonstrates the method, does not
# overwrite the shipped params:
python lna/repro/dhruva-best/recreate.py --resize l5

# run a deck directly, no Python:
"C:\msys64\ucrt64\bin\ngspice_con.exe" -b lna/repro/dhruva-best/dhruva-s.sp
```

## Honest accounting — what produced this (see REPORT.md for the full version)

- **Topology:** found by **search**, not hand-authored and not a generator
  sample. Lineage: the blind-v1 archetype family `nccgcs_s1_R` (nearest
  reference at WL-feature similarity 0.806, not an exact match — this graph
  is absent from the novelty reference set) → evolutionary/1-edit graph
  moves (`moves.py`: `load_swap` → `stage_add`) → `moves.stage_add` off
  17-device parent `6f0d080f91dfc642`, giving the 20-device design
  `ace8383c2fa68d03`. No generator sample and no paper circuit content
  anywhere (blind protocol, `plans2/08-DHRUVA-GOAL.md` rule 2).
- **Device sizing:** automated per band — `size.constrained_descent`
  (NF-targeted descent inside a hard S11/Idd trust region), recipe chain
  `nf-v3+d21` (original dhruva-s discovery) → `mf2` relabel (multi-finger
  MOS emission cutover, `w_finger=2 µm`, full metric re-measurement) →
  `mf2-v1` (further per-band NF descent under the honest harness). This part
  is the pipeline; see each band's `.meta.json` for its own seed/provenance.
- **NF:** gated (tier-2), series-Rs harness (`extract.measure_nf`,
  golden-validated to 3.0103 dB on an ideal reference). **IIP3, gain
  programmability, output balance are tier-3 and are NOT measured** —
  outside the current harness. See REPORT.md §6 for the full caveat list.

So: **search-found topology (blind, generic 1-edit graph moves) + automated
per-band sizing.** Not a hand-authored archetype (contrast the D1-era
`lna/repro/dhruva-l1-rfbcs3.*` package in this same directory tree), and not
a claim of P5-generator discovery.
