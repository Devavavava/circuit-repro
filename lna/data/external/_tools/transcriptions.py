"""Hand-transcribed classic/canonical LNA topology families, authored directly
in AnalogGenie's native device-level format ('Dev (pins) type' + a Port line)
-- the same format the dataset's own Dataset/<i>/<i>.cir files use, so no
spice2genie step is needed (these were never SPICE text to begin with).

Each entry is the CANONICAL circuit for a well-established, widely-cited LNA
topology family, cited to a specific real paper for that family (see
provenance.json per circuit for exact title/authors/DOI/URL). Where the paper
covers a more elaborate variant (differential, multi-mode, reconfigurable) the
transcription simplifies to the core mechanism that defines the family -- the
same "hand-derive from device physics/circuit theory" method already used by
lna/ref/ref24_cg.cir / ref24_csdeg.cir / ref24_tapped.cir in this project, not
an OCR of a specific figure. transcription_confidence in each provenance.json
says exactly what is paper-sourced vs. general canonical-circuit-theory.

None of these derive from, or resemble in any circuit-identifying way, the
Kanchetla et al. TMTT 2022 paper this pipeline is blind-reproducing -- they
are long-predates-2022, independently-published, generically-named topology
families cited across dozens of unrelated papers.
"""

CIRCUITS = {
    "paper_noisecancel": {
        "cir": """M1 (Y VIN1 VSS VSS) nmos4
R1 (VIN1 Y) resistor
R2 (Y VDD) resistor
M2 (VOUT1 VIN1 VSS VSS) nmos4
M3 (VOUT1 Y VSS VSS) nmos4
R3 (VOUT1 VDD) resistor
""",
        "ports": "VDD VSS VIN1 VOUT1",
    },
    "paper_currentreuse": {
        "cir": """L1 (VIN1 G1) inductor
M1 (D1 G1 S1 VSS) nmos4
L2 (S1 VSS) inductor
C1 (D1 G2) capacitor
M2 (VOUT1 G2 D1 VSS) nmos4
L3 (VOUT1 VDD) inductor
R1 (VB1 G2) resistor
""",
        "ports": "VDD VSS VIN1 VOUT1 VB1",
    },
    "paper_gmboostcg": {
        "cir": """M2 (G1 VIN1 VSS VSS) nmos4
R1 (G1 VDD) resistor
M1 (VOUT1 G1 VIN1 VSS) nmos4
L1 (VOUT1 VDD) inductor
""",
        "ports": "VDD VSS VIN1 VOUT1",
    },
    "paper_transformerfb": {
        "cir": """C1 (VIN1 G1) capacitor
R1 (VB1 G1) resistor
M1 (VOUT1 G1 VSS VSS) nmos4
L1 (VOUT1 VDD) inductor
L2 (FB VSS) inductor
C2 (FB G1) capacitor
""",
        "ports": "VDD VSS VIN1 VOUT1 VB1",
    },
    "paper_diffcccg": {
        "cir": """M1 (VOUT1 G1 VIN1 VSS) nmos4
M2 (VOUT2 G2 VIN2 VSS) nmos4
C1 (G1 VIN2) capacitor
C2 (G2 VIN1) capacitor
R1 (VB1 G1) resistor
R2 (VB1 G2) resistor
L1 (VOUT1 VDD) inductor
L2 (VOUT2 VDD) inductor
""",
        "ports": "VDD VSS VIN1 VIN2 VOUT1 VOUT2 VB1",
    },
    # -- round 2 (user-approved 2026-08-20) ------------------------------------
    # paper-sige-hbt-resfb: Wideband SiGe-HBT cascode LNA with resistive+cap
    # feedback and shunt peaking (PMC10422273, CC BY). Q1 common-emitter input,
    # Q2 common-base cascode; series feedback R (RF) || C (CF) from the collector
    # tank back to Q1's base; inductive emitter degeneration (LE); series base
    # inductor (LB); load/peaking inductor LC with a series shunt-peaking damping
    # resistor RSP; Cin input DC-block and Cout output DC-block. Every device the
    # paper's Table 1 lists is present; the (topology-only) token sequence carries
    # no values -- the Table-1 magnitudes live in provenance.json.
    "paper_sige_hbt_resfb": {
        "cir": """Cin (VIN1 B1) capacitor
LB (B1 G1) inductor
Q1 (CASC G1 E1) npn
LE (E1 VSS) inductor
Q2 (CTANK VDD CASC) npn
LC (CTANK VDD) inductor
RSP (CTANK VDD) resistor
RF (CTANK G1) resistor
CF (CTANK G1) capacitor
Cout (CTANK VOUT1) capacitor
""",
        "ports": "VDD VSS VIN1 VOUT1",
    },
    # paper-nc-cc-inductorless: Miniature wide-band noise-canceling CMOS LNA in a
    # current-conveyor arrangement (PMC9318920, CC BY), inductorless. M1 common-
    # gate input (drain and source carry the input device's noise in anti-phase),
    # M2 source-follower completing the current conveyor, two inverting common-
    # source noise-cancel paths (MX sensing the M1 source node, MY sensing the M1
    # drain node) summed at the output through load RY, MF feedback device, and
    # the tail/mirror current sources that bias the branches. The exact node-level
    # wiring of the M3..M13 mirror bank is NOT machine-readable from the source
    # (see provenance.json ambiguous_or_uncertain); this transcription uses the
    # canonical current-conveyor + Bruccoleri-style noise-cancel connectivity and
    # represents the bias bank as diode-referenced NMOS current sources. Every
    # Table-1 device is represented; W/L magnitudes are recorded in provenance.
    "paper_nc_cc_inductorless": {
        "cir": """Cin (VIN1 SN) capacitor
M1 (DN VB1 SN VSS) nmos4
M2 (VDD DN SN VSS) nmos4
MX (VOUT1 SN VSS VSS) nmos4
MY (VOUT1 DN VSS VSS) nmos4
MF (DN VOUT1 SN VSS) nmos4
RY (VOUT1 VDD) resistor
M3 (SN VBX VSS VSS) nmos4
M4 (DN VBX VSS VSS) nmos4
M5 (VOUT1 VBX VSS VSS) nmos4
M6 (VBX VBX VSS VSS) nmos4
M7 (VBF VBF VDD VDD) nmos4
M8 (VB1 VBF VDD VDD) nmos4
M9 (VB1 VB1 VSS VSS) nmos4
M10 (VBX VBF VDD VDD) nmos4
M11 (VBF VBX VSS VSS) nmos4
M12 (SN VB1 VDD VDD) nmos4
M13 (DN VB1 VDD VDD) nmos4
""",
        "ports": "VDD VSS VIN1 VOUT1 VB1",
    },
}
