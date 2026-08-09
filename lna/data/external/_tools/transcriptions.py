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
}
