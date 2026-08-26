# Proposal netlist format

The LLM proposes an LNA topology as a small, line-oriented netlist. This is the
contract the loop parser (`proposal.py`) enforces and the GBNF grammar
(`grammar.gbnf`) constrains generation to. It is a thin, human-legible surface
over the repo's internal `read_netlist` row format
(`[name, net1..netK, type]`) used by `lna/templates.py`, so a valid proposal
round-trips through the same AnalogGenie pipeline the corpus and templates use.

## One device per line

```
TYPE name node1 node2 [node3 node4]
```

- `TYPE` (case-insensitive) is one of:

  | TYPE   | maps to     | pins (in order)     |
  |--------|-------------|---------------------|
  | `NMOS` | `nmos4`     | `D G S B` (4 nodes) |
  | `PMOS` | `pmos4`     | `D G S B` (4 nodes) |
  | `R`    | `resistor`  | `P N` (2 nodes)     |
  | `C`    | `capacitor` | `P N` (2 nodes)     |
  | `L`    | `inductor`  | `P N` (2 nodes)     |

  These are the only device types the 45nm harness sizes. (The vocabulary also
  contains BJTs `NPN`/`PNP` and digital cells, but `to_spice.py`/`size.py` treat
  bipolars as non-sizable and the LNA funnel does not propose them, so they are
  intentionally excluded from this format.)

- `name` is an identifier unique within the netlist: starts with a letter, then
  letters / digits / underscores. It is a **label only** — the AnalogGenie
  `build_connection_matrix` renumbers devices canonically per type in netlist
  order (`NM1, NM2, …`, `R1, R2, …`), so your names never survive into the token
  sequence. Pick readable ones (`M1`, `Cin`, `Ld`).

- Each node is a net name. Node order is significant: `NMOS`/`PMOS` are
  **drain gate source body**, and `R`/`C`/`L` are the two terminals `P N`.

## Reserved nets

| net     | meaning                                                    |
|---------|------------------------------------------------------------|
| `VDD`   | supply rail                                                |
| `VSS`   | negative rail / ground reference                           |
| `0`     | ground — an **alias for `VSS`** (either spelling is fine)  |
| `VIN1`  | RF input  — S-parameter port 1 (50 Ω, AC-coupled)          |
| `VOUT1` | RF output — S-parameter port 2 (50 Ω, AC-coupled)          |

Any other identifier (e.g. `n1`, `gate`, `tap`) is an **internal node**. Internal
nodes are created just by naming them; two device pins on the same internal-node
name are wired together.

## Conventions the funnel expects

- Include both `VIN1` and `VOUT1` — the harness only emits an S-parameter deck
  when both ports exist (`to_spice.Netlist.two_port`). A proposal without both
  ports sizes as "no two-port setup" and cannot report S11/S21.
- Use at least one MOSFET (`structural_screen` requires `has_transistor`).
- For a **narrowband** spec (`allow_inductorless: false`, e.g. `wifi24`) include
  at least one `L` — the L0 screen requires `has_inductor` and caps
  `max_inductors`.
- For a **wideband** spec (`allow_inductorless: true`) the screen instead wants a
  recognizable inductorless RF-input structure: a transistor **source** driven
  from the input (common-gate) or a **resistor bridging input side and output
  side** (shunt feedback).
- Keep the device count inside the spec's `device_budget` (e.g. wifi24 is
  `[3, 16]`).
- Do **not** hand-insert bias networks or DC sources. Biasing is inserted
  deterministically by `lna/bias.py` after the screen; device **values** (W, R,
  C, L, bias voltages) are chosen by the sizer. The proposal is **topology only**.

## Comments and whitespace

- Blank lines are ignored.
- A line whose first non-space character is `#` or `*` is a comment.
- Tokens are whitespace-separated (any run of spaces/tabs).

## Example — inductively-degenerated common-source with a tapped-C load

```
# inductively degenerated CS LNA, tapped-C matched load
C  Cin  VIN1 g_in
L  Lg   g_in g
NMOS M1  d    g   s   VSS
L  Ls   s    VSS
L  Ld   VDD  d
C  Ct1  d    tap
C  Ct2  tap  VSS
C  Cout tap  VOUT1
```

This is the same circuit `templates.cs_lna(gate_ind=True, degen=True, cex=False,
cascode=False, load="tapped", buffer=False)` emits; the parser round-trips it to
the identical WL hash (`test_proposal.py`).

## What happens to a proposal

`proposal.parse(text)` → internal rows → `proposal.to_tokens()` (via the repo's
`build_connection_matrix` + `dfs_all_paths`) → AnalogGenie token sequence →
`topology.Topology`. From there the loop runs the unchanged funnel:
`spec.structural_screen` (L0) → `bias.insert_bias` → `size` (CMA-ES/ZOAF driving
ngspice) → `spec.margins_for`. Any parse or round-trip failure is recorded
verbatim in the trajectory row; it is a first-class outcome, not a crash.
