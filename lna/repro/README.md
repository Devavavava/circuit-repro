# Gate-D1 feasible dhruva-l1 design — reproduction artifacts

Files here pin the WP-DHRUVA Gate-D1 result (blind protocol; see `lna/FINDINGS.md`
§12).

## Files
- `dhruva-l1-rfbcs3.sp` — the full ngspice deck (the schematic, as a netlist) with
  the sized device values substituted. This is the circuit that meets the spec.
- `dhruva-l1-rfbcs3.tokens.txt` — the topology in AnalogGenie arrow-token form.
- `dhruva-l1-rfbcs3.params.json` — the sized device values (W/L, R, C, L, bias).
- `recreate_dhruva_l1.py` — re-run it (`--replay` or `--resize`).

## The result
Archetype `rfbcs3_tank_cc21_bf0` (from `lna/templates.py`), sized vs `dhruva-l1`:
**s11_max −11.2 dB** (≤ −10 over 1.1–2.5 GHz) · **S21 37.8 dB** (≥ 25.4) ·
**Idd 12.93 mA** (≤ 13) → feasible on the tier-1 gated constraints. Stored in
`lna/data/topo_labels.jsonl` as (wl `3ebaf08f99d319d8`, `dhruva-l1`), recipe
`blind-v1`.

## Honest accounting — what produced this
- **Target input:** the `dhruva-l1` spec numbers only (`lna/specs/dhruva-l1.yaml`).
  No paper circuit content was used (blind protocol).
- **Topology:** a **hand-authored generic-textbook archetype** —
  `templates.rfb_cs3_lna` (3 stages: resistive-feedback input for a broadband 50 Ω
  match → two tuned common-source stages for gain). The assistant designed this
  family, guided by the automated sizer's measurements, under blind-protocol rule 2
  (generic textbook blocks chosen without the paper). It is **not** an output of the
  P5 neural generator — the generator's sampled pools (P5-v4/v5) got close
  (best violation 0.318) but did not produce a feasible design.
- **Device sizing:** automated — `size.size_topology` (ZOAF) + `size.polish`
  (min-margin coordinate pattern search), seed 5. This part is the pipeline.
- **NF:** off (tier-1 gates S11/S21/Idd only; noise is tier-2, pending the
  port-noise harness).

So: **assistant-designed topology (blind, generic) + automated sizing/evaluation.**
Not an autonomous generator discovery.

## Recreate
```
# exact logged result (re-evaluate the stored device values):
python lna/repro/recreate_dhruva_l1.py

# re-derive the device values from scratch (size the archetype at seed 5):
python lna/repro/recreate_dhruva_l1.py --resize

# inspect the archetype family:
python lna/templates.py --list | grep rfbcs3
```
Run from the repo root (`.../lna-data`). Uses the torch-free analysis python
(numpy + ngspice on PATH); no GPU needed.
