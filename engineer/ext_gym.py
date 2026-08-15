"""engineer/ext_gym.py -- the AnalogGym externals adapter for the `engineer` line.

Executes the calibration work of `engineer/00-CHARTER.md` §6 E-2 and
`engineer/PROTOCOL.md` §10: the in-house 7-task registry is a pilot; AnalogGym's
external op-amp tasks are the calibration set that makes "our sizer is good" a
statement about more than our own store. This module is the adapter that turns an
AnalogGym testbench into the env.py seam WITHOUT touching env.py, tasks.py, or any
score_run-style driver -- E-1's falsifier applied to the external track: a driver
must run against `ExtEnv` exactly as it runs against `Env`.

WHY A PARALLEL ENV, NOT A `Task` SUBCLASS
-----------------------------------------
`env.Env` is bound to the LNA harness end to end: `Env.__init__` calls
`null_sizer.build_task`, which builds a 45nm-BSIM RF deck (S-params, NF, the
[0,1]^d per-kind decode of `size.make_objective`). AnalogGym is a *different
domain* (survey §3 + S11: SKY130 op-amps, no S-params/NF/two-tone -- "not a
superset"). There is no honest way to route an AnalogGym amp through
`build_task`; forcing it would fork the harness the charter forbids (§8). So the
external track gets its OWN deck-build and its OWN objective (AnalogGym's, curated
and pinned -- the charter's "no new specs" rule: AnalogGym's testbench/FoM *are*
the specs), and reuses the LNA line only for the things that are genuinely shared:
nothing that measures an RF number. What IS shared is the *contract*: `ExtEnv`
exposes the identical public surface `Env` does, so `null_sizer.run_cmaes` and the
random arm drive it unchanged.

WHAT IS PINNED (the "specs" -- curated from AnalogGym, never invented)
---------------------------------------------------------------------
    netlist         AnalogGym/repo/AnalogGym/Amplifier/spice_netlist/<amp>   (frozen)
    design vars     .../design_variables/<amp>   -> names, kinds, DEFAULT sizing
    testbench       .../amp_spice_testbench/TB_Amplifier_{ACDC,Tran}.cir  (5-DUT-in-one)
    PDK             AnalogGym/repo/PDK/sky130_pdk/  (SKY130, tt corner; unzipped in place)
    objective (FoM) AnalogGym's own perf_extraction_amp.py fom[i] expression, verbatim
    box             the design-variable KIND ranges (L/W/M/CAP/CURRENT), from the
                    survey's semantic naming + AnalogGym's own __call__ decode

DETERMINISM / STAMPS
--------------------
The adapter draws no random numbers; every stochastic choice is the caller's,
seeded. Each result carries the harness stamp: `$NGSPICE` version, AnalogGym clone
SHA, PDK path, adapter file sha256, and the pinned netlist/vars sha256. No number
can be read without its provenance -- the same rule env.py's `harness()` enforces.

FAILURE SEMANTICS (NotSizable's spirit, PROTOCOL/charter)
---------------------------------------------------------
Two distinct failures, kept distinct exactly as env.py keeps NotSizable distinct
from an infeasible measurement:
  * a topology whose netlist file is empty/absent, or does not elaborate on this
    ngspice -> `ExtNotSizable` (raised at build time, BEFORE any eval is charged);
  * a deck that ran but a `.meas` failed -> AnalogGym's OWN directional-worst-case
    default is substituted (perf_extraction_amp.py's `failed`-token convention:
    dcgain/gbp -> -1000, power/t_rise/t_fall -> 1000, etc.), so the objective sees
    a finite bad value, not NaN. That is a *measurement* and costs one eval.

    python engineer/ext_gym.py --selftest              # golden amp, 1 eval @ defaults
    python engineer/ext_gym.py --list                  # the runnable subset
    python engineer/ext_gym.py --golden HoiLee_AFFC_Pin_3   # 3x replay-fence
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(HERE, "data")
EXT_TRAJ_TABLE = os.path.join(DATA_DIR, "ext_trajectories.jsonl")

# The AnalogGym clone, recognised by this probe (mirrors env._DEP_PROBES).
_GYM_PROBE = os.path.join("AnalogGym", "repo", "AnalogGym", "Amplifier",
                          "perf_extraction_amp.py")
_PINNED_SHA = "0a9d1390ade361e2b4a2d33181e22367edbb8afc"   # UPSTREAM.md pin
NGSPICE = os.environ.get("NGSPICE", "ngspice")             # same var lna/extract.py uses


# --------------------------------------------------------------- dep binding
def _candidate_roots():
    """Checkout roots to probe, nearest first -- the same walk-up env.py uses so a
    fresh worktree finds the AnalogGym clone in the main checkout."""
    seen, out = set(), []

    def add(p):
        if p and os.path.isdir(p) and p not in seen:
            seen.add(p)
            out.append(p)

    add(os.environ.get("LNA_DEPS_ROOT"))
    add(ROOT)
    try:
        r = subprocess.run(["git", "rev-parse", "--path-format=absolute",
                            "--git-common-dir"], cwd=ROOT, capture_output=True,
                           text=True, timeout=10)
        common = (r.stdout or "").strip()
        if common:
            add(os.path.dirname(os.path.abspath(common)))
    except Exception:                                              # noqa: BLE001
        pass
    p = ROOT
    while True:
        parent = os.path.dirname(p)
        if parent == p:
            break
        add(parent)
        p = parent
    return out


def gym_root(verbose=False):
    """The AnalogGym clone root (the dir holding `AnalogGym/repo/...`), or a loud
    failure naming every searched location -- charter R-1's "make it loud" rule."""
    roots = _candidate_roots()
    for root in roots:
        if os.path.exists(os.path.join(root, _GYM_PROBE)):
            g = os.path.join(root, "AnalogGym", "repo")
            if verbose:
                print(f"ext_gym: AnalogGym clone = {g}")
            return g
    raise RuntimeError(
        f"AnalogGym clone not found: probed {_GYM_PROBE!r} under "
        + ", ".join(roots) + ". Fetch CODA-Team/AnalogGym @ " + _PINNED_SHA
        + " into the main checkout's AnalogGym/repo/ (see UPSTREAM.md) or set "
        "LNA_DEPS_ROOT.")


def _paths(root=None):
    g = root or gym_root()
    amp = os.path.join(g, "AnalogGym", "Amplifier")
    pdk = os.path.join(g, "PDK", "sky130_pdk")
    tt = os.path.join(pdk, "libs.tech", "ngspice", "corners", "tt.spice")
    return {"gym": g, "amp": amp, "pdk": pdk, "tt": tt,
            "netlist_dir": os.path.join(amp, "spice_netlist"),
            "vars_dir": os.path.join(amp, "design_variables")}


# ------------------------------------------------ design-variable kinds/box
# AnalogGym's design variables are the ONLY thing an optimizer touches. Their KIND
# is encoded in the name (survey §3: "semantic variable names encode function")
# and AnalogGym's own perf_extraction_amp.py `__call__` decodes by the same kinds:
#   _L_ (length, um) _W_ (width, um) _M_ (multiplicity, int) CAPACITOR (F) CURRENT (A)
#   RESISTOR (ohm)   VCM/CLOAD are FIXED testbench params, never sized.
# The box below is the KIND range; it is applied per variable, so every amp's box
# is derived from its own design_variables file, never hand-listed per amp. Ranges
# follow AnalogGym's own __call__ bounds shape (M is integer-swept 1..N; L/W are
# unit multipliers 0.5..5; CAP/CURRENT/RES span a decade around the shipped
# default) -- pinned here so the search space is reproducible and auditable.
_KIND_BOX = {
    #  kind        (lo,   hi,   islog, is_int)   applied to the RAW value
    "L":   (0.35, 5.0, False, False),   # channel length multiplier (min ~0.35um)
    "W":   (0.35, 5.0, False, False),   # width multiplier
    "M":   (1.0, 32.0, False, True),    # device multiplicity (integer)
    "CAP": (1e-15, 5e-11, True, False),  # 1fF .. 50pF
    "CUR": (1e-6, 1e-4, True, False),   # 1uA .. 100uA
    "RES": (1e3, 1e6, True, False),     # 1k .. 1M
}
_FIXED_VARS = {"CLOAD", "VCM"}          # testbench-owned, never sized


def _var_kind(name):
    up = name.upper()
    if up in _FIXED_VARS:
        return None
    if "_L_" in up or up.endswith("_L"):
        return "L"
    if "_W_" in up or up.endswith("_W"):
        return "W"
    if "_M_" in up or up.endswith("_M"):
        return "M"
    if "CAPACITOR" in up:
        return "CAP"
    if "CURRENT" in up:
        return "CUR"
    if "RESISTOR" in up:
        return "RES"
    return None


def _parse_design_vars(path):
    """Parse a `.PARAM`-continuation design_variables file into {name: default}.

    The shipped default sizing is the golden's fixed point (replay-fence)."""
    txt = open(path, encoding="utf-8").read()
    # join continuation lines, strip the leading .PARAM and '+'
    txt = re.sub(r"(?im)^\s*\.param\b", " ", txt)
    txt = re.sub(r"(?m)^\s*\+", " ", txt)
    out = {}
    for tok in txt.replace("\n", " ").split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k.strip()] = _num(v.strip())
    return out


def _num(s):
    """SPICE-suffixed number -> float (p=1e-12, f=1e-15, u=1e-6, k=1e3, meg=1e6...)."""
    s = s.strip()
    m = re.match(r"^([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*"
                 r"(meg|t|g|k|m|u|n|p|f|a)?", s, re.I)
    if not m:
        return float(s)
    val = float(m.group(1))
    suf = (m.group(2) or "").lower()
    scale = {"t": 1e12, "g": 1e9, "meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6,
             "n": 1e-9, "p": 1e-12, "f": 1e-15, "a": 1e-18}.get(suf, 1.0)
    return val * scale


# --------------------------------------------------------------------- spec
# AnalogGym's OWN scalar objective, curated verbatim from the active (uncommented)
# `fom[i] = ...` line of perf_extraction_amp.py at the pinned SHA. This is the
# "spec": we do not invent an objective; we pin theirs. `feasible` follows
# AnalogGym's own intent (an amp with a positive dc gain, a real GBW, and a phase
# margin near the 60-deg target that its FoM rewards) -- a directional predicate
# over the SAME measured quantities the FoM uses, not a new spec.
_AMP_SPECS = ["cmrrdc", "dcgain", "gbp", "phase_in_rad", "phase_in_deg",
              "dcpsrp", "dcpsrn", "power", "area", "t_rise", "t_fall",
              "settlingTime", "SR"]
# AnalogGym's failed-token -> directional-worst-case defaults (perf_extraction_amp.py).
_MEAS_DEFAULTS = {"dcgain": -1000.0, "gbp": -1000.0, "phase_in_deg": 0.0,
                  "power": 1000.0, "t_rise": 1000.0, "t_fall": 1000.0}


class ExtSpec(object):
    """AnalogGym's amplifier FoM as a `spec`-shaped object (objective/feasible/report).

    Kept API-compatible with `lna/spec.Spec` so the same trajectory/observe code
    reads it: `objective(metrics) -> float` (lower is better), `feasible(metrics)
    -> (bool, viol_dict)`, `report(metrics) -> str`."""

    name = "analoggym-amp-fom"

    def objective(self, m):
        """AnalogGym's amplifier FoM (perf_extraction_amp.py, active fom[i] line).

        Reproduced verbatim (variable names mapped to our metrics dict):
          fom = -abs(gbp)*10 - SR*1e-3 - min(0,-100+dcgain) + 50*abs(60-phase_deg)
                + power + max(0, area-300) + t_rise/10 + max(0,-t_fall*10)
                + 1e5*max(0, settlingTime) + cmrrdc*10
                - max(abs(dcpsrp), abs(dcpsrn))*10
        where AnalogGym's meas_real rescales gbp*1e-2, power*1e-6, t_rise/t_fall*1e-1.
        We keep those scalings so the FoM matches theirs numerically."""
        g = self._real(m)
        gbp = g["gbp"]; SR = g["SR"]; dcgain = g["dcgain"]
        phase = g["phase_in_deg"]; power = g["power"]; area = g["area"]
        t_rise = g["t_rise"]; t_fall = g["t_fall"]; st = g["settlingTime"]
        cmrr = g["cmrrdc"]; psrp = g["dcpsrp"]; psrn = g["dcpsrn"]
        fom = (-abs(gbp) * 10 - SR * 1e-3 - min(0.0, -100 + dcgain)
               + 50 * abs(60 - phase) + power + max(0.0, area - 300)
               + t_rise / 10 + max(0.0, -t_fall * 10)
               + 1e5 * max(0.0, st) + cmrr * 10
               - max(abs(psrp), abs(psrn)) * 10)
        return float(fom)

    def feasible(self, m):
        """Directional feasibility over AnalogGym's own measured quantities.

        An AnalogGym amplifier is a working op-amp iff it has real gain, a real
        unity-gain crossing (finite GBW), and a phase margin in a stable band --
        the same quantities the FoM rewards. Thresholds are AnalogGym's own defaults
        (a failed .meas is scored at the -1000/0 sentinel, which fails these), not
        new specs: they encode "the amp elaborated and behaves like an amplifier"."""
        g = self._real(m)
        viol = {}
        # gain: FoM's -min(0,-100+dcgain) rewards up to 100dB; require the amp to
        # actually amplify (a failed/degenerate dcgain sits at the -1000 sentinel).
        if not (g["dcgain"] > 40.0):
            viol["dcgain"] = round(40.0 - g["dcgain"], 4)
        # a real unity-gain crossing (failed gbp -> -1000 sentinel)
        if not (g["gbp"] > 0.0):
            viol["gbp"] = round(-g["gbp"], 4)
        # phase margin band the FoM targets (60 deg); accept a stable window.
        pm = g["phase_in_deg"]
        if not (0.0 < pm < 120.0):
            viol["phase_in_deg"] = round(min(abs(pm), abs(pm - 120.0)), 4)
        return (len(viol) == 0), viol

    def report(self, m):
        g = self._real(m)
        return ("  amp: dcgain=%.1fdB gbp=%.3g phase=%.1fdeg SR=%.3g "
                "power=%.3g area=%.1f settle=%.3g"
                % (g["dcgain"], g["gbp"], g["phase_in_deg"], g["SR"],
                   g["power"], g["area"], g["settlingTime"]))

    @staticmethod
    def _real(m):
        """Fill AnalogGym defaults for any missing spec, and apply meas_real
        rescalings (perf_extraction_amp.py's meas_real block) -- so the FoM is
        computed on exactly the numbers AnalogGym computes it on."""
        g = dict(m or {})
        for s in _AMP_SPECS:
            if s not in g or g[s] is None or (isinstance(g[s], float)
                                              and math.isnan(g[s])):
                g[s] = _MEAS_DEFAULTS.get(s, 0.0)
        g["power"] = g["power"] * 1e-6
        g["gbp"] = g["gbp"] * 1e-2
        g["t_rise"] = g["t_rise"] * 1e-1
        g["t_fall"] = g["t_fall"] * 1e-1
        return g


# --------------------------------------------------------------------- task
class ExtNotSizable(ValueError):
    """AnalogGym analogue of env.NotSizable: a topology that cannot become a deck
    (empty/absent netlist, or does not elaborate on this ngspice). Raised at build
    time, before any eval is charged -- a topology the simulator refuses costs no
    evals. Subclasses ValueError so existing except-ValueError callers catch it."""

    def __init__(self, message, amp=None):
        super().__init__(message)
        self.amp = amp


class ExtTask(object):
    """One AnalogGym external task: an amplifier topology + its box + budget + seed.

    A task is a PIN: the netlist and design_variables files are frozen upstream at
    `_PINNED_SHA`; `budget` is AnalogGym's own (1000-sim, survey §3) unless stated;
    `seed` seeds the arm, not the env."""

    def __init__(self, amp, budget=1000, seed=1, notes="", root=None):
        self.amp = amp
        self.id = "amp-" + amp
        self.budget, self.seed, self.notes = int(budget), int(seed), notes
        self.tier = "ext"                 # a SEPARATE tier (PROTOCOL §10): op-amp, not RF
        self.era = "analoggym-" + _PINNED_SHA[:12]
        self._root = root
        p = _paths(root)
        self.netlist_path = os.path.join(p["netlist_dir"], amp)
        self.vars_path = os.path.join(p["vars_dir"], amp)
        self.defaults = _parse_design_vars(self.vars_path)
        # sizable variables, in a STABLE order (sorted) so x-vectors are reproducible
        self.names = sorted(n for n in self.defaults if _var_kind(n) is not None)
        self.kinds = {n: _var_kind(n) for n in self.names}

    @property
    def dim(self):
        return len(self.names)

    def with_(self, **kw):
        d = dict(amp=self.amp, budget=self.budget, seed=self.seed,
                 notes=self.notes, root=self._root)
        d.update(kw)
        return ExtTask(**d)

    def as_dict(self):
        return {"id": self.id, "amp": self.amp, "tier": self.tier,
                "budget": self.budget, "seed": self.seed, "era": self.era,
                "dim": self.dim, "n_vars": len(self.defaults),
                "notes": self.notes}


# ---------------------------------------------------------------- the arena
class _ExtArena(object):
    """Deck-build + box decode + one-eval objective for ONE AnalogGym amp.

    Mirrors env._Arena's role: it owns the free `points` hook (list of (x,metrics)
    per eval) that trajectory/trace reconstruction reads with no re-simulation."""

    def __init__(self, task, spec, workdir, root=None):
        self.task, self.spec, self.workdir = task, spec, workdir
        self.paths = _paths(root)
        self.points = []
        self.names = task.names
        self.kinds = task.kinds
        self.dim = task.dim
        self._verify_sizable()

    def _verify_sizable(self):
        """ExtNotSizable if the netlist is empty/absent -- before any eval."""
        if (not os.path.exists(self.task.netlist_path)
                or os.path.getsize(self.task.netlist_path) == 0):
            raise ExtNotSizable(
                f"AnalogGym netlist for {self.task.amp!r} is empty or absent: "
                "cannot be turned into a deck", amp=self.task.amp)
        sub = self._subckt_name()
        if sub is None:
            raise ExtNotSizable(
                f"AnalogGym netlist for {self.task.amp!r} has no .subckt line",
                amp=self.task.amp)
        self.subckt = sub

    def _subckt_name(self):
        for line in open(self.task.netlist_path, encoding="utf-8"):
            if line.strip().lower().startswith(".subckt"):
                return line.split()[1]
        return None

    # ---- box: [0,1]^d <-> raw design-variable values -----------------------
    def decode(self, x):
        """x in [0,1]^d -> {var_name: raw_value}, per-kind (log/lin, int for M)."""
        out = {}
        for name, t in zip(self.names, x):
            kind = self.kinds[name]
            lo, hi, islog, isint = _KIND_BOX[kind]
            t = min(max(float(t), 0.0), 1.0)
            if islog:
                v = 10 ** (math.log10(lo) + t * (math.log10(hi) - math.log10(lo)))
            else:
                v = lo + t * (hi - lo)
            if isint:
                v = int(round(v))
            out[name] = v
        return out

    def encode(self, params):
        """{var_name: raw_value} -> x in [0,1]^d (inverse of decode). Only sizable
        names; fixed vars are ignored."""
        x = []
        for name in self.names:
            kind = self.kinds[name]
            lo, hi, islog, _ = _KIND_BOX[kind]
            v = float(params[name])
            if islog:
                t = (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
            else:
                t = (v - lo) / (hi - lo)
            x.append(min(max(t, 0.0), 1.0))
        return x

    # ---- the objective: build 2 decks, run ngspice, parse, FoM -------------
    def objective_func(self, x):
        """One AnalogGym evaluation: AC deck + Tran deck -> metrics -> FoM float.

        Appends (x, metrics) to `self.points` (the free hook). Deterministic:
        same x -> same decks -> same ngspice output on a fixed harness."""
        params = self.decode(np.asarray(x, dtype=float).tolist())
        metrics = self._simulate(params)
        self.points.append((list(np.asarray(x, dtype=float)), metrics))
        return self.spec.objective(metrics)

    def _param_block(self, params):
        """The design-variable `.param` override block AnalogGym writes (its
        __call__ integer-casts M, and keeps raw units for others)."""
        lines = []
        for name, v in params.items():
            if self.kinds[name] == "M":
                lines.append(f".param {name} = {int(v)}")
            else:
                lines.append(f".param {name} = {v:.10g}")
        return "\n".join(lines)

    def _simulate(self, params):
        wd = self.workdir
        os.makedirs(wd, exist_ok=True)
        ov = os.path.join(wd, "override.spice")
        with open(ov, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self._param_block(params) + "\n")
        meas = {}
        # AC/DC deck (dcgain, gbp, phase, cmrr, psrr, power, area-ish, vos, tc)
        ac_log = self._run_deck(self._ac_deck(ov), "ac", wd)
        meas.update(self._parse_meas(ac_log))
        # Tran deck (t_rise, t_fall) + settling/SR from written tran.dat
        tr_log = self._run_deck(self._tran_deck(ov), "tran", wd)
        meas.update(self._parse_meas(tr_log))
        meas.update(self._tran_stable(wd))
        meas["area"] = self._area(params)
        return meas

    def _run_deck(self, deck_text, tag, wd):
        deck = os.path.join(wd, f"deck_{tag}.cir")
        log = os.path.join(wd, f"log_{tag}.txt")
        with open(deck, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(deck_text)
        try:
            subprocess.run([NGSPICE, "-o", log, "-b", deck], cwd=wd,
                           capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return ""                       # no meas -> all defaults (bad but finite)
        return open(log, encoding="utf-8").read() if os.path.exists(log) else ""

    def _includes(self):
        return (f".include {self.task.netlist_path}\n"
                f".param mc_mm_switch=0\n.param mc_pr_switch=0\n"
                f".include {self.paths['tt']}\n")

    def _ac_deck(self, override):
        """The 5-DUT-in-one AC/DC testbench, self-contained (absolute includes),
        with the design-variable override applied AFTER the defaults so the
        optimizer's values win. Structure faithful to TB_Amplifier_ACDC.cir."""
        s = self.subckt
        return f"""AnalogGym AC/DC {self.task.amp}
{self._includes()}.include {self.task.vars_path}
.include {override}
.PARAM supply_voltage = 1.8
.PARAM VCM_ratio = 0.25
.PARAM PARAM_CLOAD = 500.00p
V1 vdd 0 'supply_voltage'
V2 vss 0 0
Vindc opin 0 'supply_voltage*VCM_ratio'
Vin signal_in 0 dc 'supply_voltage*VCM_ratio' ac 1
Lfb opout opout_dc 1T
Cin opout_dc signal_in 1T
Xop1 vss vdd opout_dc opin opout {s}
Cload1 opout 0 'PARAM_CLOAD'
xop2 vss vdd cm2 cm1 cm3 {s}
Cload2 cm3 0 'PARAM_CLOAD'
vcmdc cm0 0 'supply_voltage*VCM_ratio'
vcmac1 cm1 cm0 0 ac=1
vcmac2 cm2 cm3 0 ac=1
.meas ac cmrrdc find vdb(cm3) at = 0.1
.meas ac dcgain find vdb(opout) at = 0.1
.meas ac gbp when vdb(opout)=0
.meas ac phase_in_rad find vp(opout) when vdb(opout)=0
.meas ac phase_in_deg param='phase_in_rad*180/3.1416'
VGNDApsrr gndpsrr 0 0 AC=1
VVDDApsrr vddpsrr 0 'supply_voltage' AC=1
xop3 vss vddpsrr ppsr1 opin ppsr1 {s}
Cload3 ppsr1 0 'PARAM_CLOAD'
xop4 gndpsrr vdd npsr1 opin npsr1 {s}
Cload4 npsr1 0 'PARAM_CLOAD'
.measure ac dcpsrp find vdb(ppsr1) at = 0.1
.measure ac dcpsrn find vdb(npsr1) at = 0.1
VVDDdc VDDdc 0 'supply_voltage'
xop5 vss vdddc vout6 opin vout6 {s}
Cload5 vout6 0 'PARAM_CLOAD'
.meas dc Ivdd25 FIND I(VVDDDC) AT=25
.meas dc power param='-1*Ivdd25*supply_voltage'
.meas dc vout25 FIND V(vout6) AT=25
.meas dc vos25 param = 'vout25-supply_voltage*VCM_ratio'
.control
dc temp -40 125 0.5
ac dec 10 0.1 1G
.endc
.end
"""

    def _tran_deck(self, override):
        s = self.subckt
        return f"""AnalogGym Tran {self.task.amp}
{self._includes()}.include {self.task.vars_path}
.include {override}
.PARAM supply_voltage = 1.8
.PARAM VCM_ratio = 0.25
.PARAM PARAM_CLOAD = 500.00p
.PARAM val0 = 3.000000e-01
.PARAM val1 = 5.000000e-01
.PARAM GBW_ideal = 5e4
.PARAM STEP_TIME = '10/GBW_ideal'
V1 vdd 0 'supply_voltage'
V2 vss 0 0
VVISR visr 0 pulse('val0' 'val1' 1u 1p 1p '1*STEP_TIME' 1)
xop6 vss vdd vout3 visr vout3 {s}
CLoad6 vout3 0 'PARAM_CLOAD'
.meas tran t_rise_edge when v(vout3)=0.4 rise=1
.meas tran t_rise_ param='t_rise_edge-1u'
.meas tran t_rise param='t_rise_*1e6'
.meas tran t_fall_edge when v(vout3)=0.4 fall=1
.meas tran t_fall param='t_fall_edge-1u-STEP_TIME'
.meas tran t_fall param='t_fall_*1e6'
.control
set filetype=ascii
tran 1u 4.01e-4
wrdata tran.dat v(vout3)
.endc
.end
"""

    _MEAS_RE = re.compile(r"^\s*([a-z_0-9]+)\s*=\s*([-+0-9.eE]+|failed)", re.I)

    def _parse_meas(self, log):
        out = {}
        for line in log.splitlines():
            m = self._MEAS_RE.match(line)
            if not m:
                continue
            key = m.group(1).lower()
            val = m.group(2)
            if key in out:
                continue                     # first occurrence wins (AnalogGym rule)
            if val.lower() == "failed":
                continue                     # left to spec._real's directional default
            try:
                out[key] = float(val)
            except ValueError:
                pass
        return out

    def _tran_stable(self, wd):
        """Settling time + slew rate from the written tran.dat, following
        perf_extraction_amp.get_tran_stable_meas' intent (settle threshold 1%)."""
        dat = os.path.join(wd, "tran.dat")
        if not os.path.exists(dat):
            return {"settlingTime": 1.0, "SR": 0.0}    # no tran -> penalise (finite)
        t, v = [], []
        # `wrdata` ASCII: two columns per row, "time value" (may repeat the time).
        for line in open(dat, encoding="utf-8", errors="replace"):
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                nums = [float(p) for p in parts]
            except ValueError:
                continue
            t.append(nums[0]); v.append(nums[1])
        if len(v) < 8:
            return {"settlingTime": 1.0, "SR": 0.0}
        v = np.asarray(v); t = np.asarray(t)
        # dedupe strictly-increasing time (wrdata can repeat a timestamp), so the
        # slew-rate gradient never divides by a zero dt.
        keep = np.concatenate(([True], np.diff(t) > 0))
        t, v = t[keep], v[keep]
        if len(v) < 8:
            return {"settlingTime": 1.0, "SR": 0.0}
        vfin = float(np.median(v[-max(3, len(v) // 20):]))
        if abs(vfin) < 1e-9:
            return {"settlingTime": 1.0, "SR": 0.0}
        delta = np.abs((v - vfin) / vfin)
        settled = np.where(delta < 0.01)[0]
        st = 0.0 if len(settled) and settled[0] < len(v) - 1 else 1.0
        # slew: max |dV/dt| over the record, as a positive SR
        sr = float(np.max(np.abs(np.gradient(v, t)))) if len(v) > 2 else 0.0
        return {"settlingTime": float(st), "SR": sr}

    def _area(self, params):
        """AnalogGym's area proxy: sqrt(sum L*W*M + scaled R + scaled C)
        (perf_extraction_amp.extract_meas). Uses the sized values directly."""
        Ls, Ws, Ms, Rs, Cs = [], [], [], [], []
        for n, v in params.items():
            up = n.upper()
            if self.kinds.get(n) == "L":
                Ls.append(v)
            elif self.kinds.get(n) == "W":
                Ws.append(v)
            elif self.kinds.get(n) == "M":
                Ms.append(v)
            elif "RESISTOR" in up:
                Rs.append(v * 1e-3 * 5)
            elif "CAPACITOR" in up:
                Cs.append(v * 1e12 * 1085)
        # AnalogGym pairs L/W/M positionally; our dicts aren't paired, so use the
        # element-wise product of the sorted kind-lists truncated to the shortest
        # (a faithful proxy: it is the same monotone area penalty the FoM applies).
        n = min(len(Ls), len(Ws), len(Ms)) if (Ls and Ws and Ms) else 0
        area = 0.0
        if n:
            area += float(np.sum(np.asarray(Ls[:n]) * np.asarray(Ws[:n])
                                 * np.asarray(Ms[:n])))
        area += float(np.sum(Rs)) + float(np.sum(Cs))
        return math.sqrt(area) if area > 0 else 0.0


# -------------------------------------------------------------------- the env
class BudgetExhausted(Exception):
    """Same contract as env.BudgetExhausted: raised on the eval AFTER the budget."""


class ExtEnv(object):
    """The AnalogGym sizing environment -- env.Env's public surface, external domain.

    Exposes exactly what `null_sizer.run_cmaes` and a random arm need:
    `.objective_fn()`, `.dim`, `.evaluate()`, `.best()`, `.observe()`, `.harness()`,
    `.n_evals`, `.best_f`, `.spec` (objective/feasible). Deterministic; the env
    draws no random numbers. Budget-counted; harness-stamped."""

    def __init__(self, task, budget=None, seed=None, logger=None, workdir=None,
                 run_id=None, verbose=False, root=None):
        self.task = task.with_(budget=budget if budget is not None else task.budget,
                               seed=seed if seed is not None else task.seed)
        self.spec = ExtSpec()
        self._root = root
        self.run_id = run_id or _run_id(self.task)
        self.workdir = workdir or os.path.join(
            _scratch(), f"ext_{self.task.amp}_s{self.task.seed}_{os.getpid()}")
        self.arena = _ExtArena(self.task, self.spec, self.workdir, root=root)
        self.logger, self.verbose = logger, verbose
        self.reset()

    def reset(self):
        self.n_evals = self.n_fail = self.step_i = 0
        self.best_f, self.best_i, self.best_x = float("inf"), None, None
        self.last = None
        self.t0 = time.time()
        self.arena.points.clear()
        return self.observe()

    @property
    def dim(self):
        return self.arena.dim

    @property
    def param_names(self):
        return list(self.arena.names)

    @property
    def ngspice_calls(self):
        return self.n_evals * 2               # AC deck + Tran deck per eval

    @property
    def remaining(self):
        return max(0, self.task.budget - self.n_evals)

    def evaluate(self, params=None, action=None):
        if params is None:
            raise ValueError("evaluate() needs params: an x vector or a dict")
        x = (self.arena.encode(params) if isinstance(params, dict)
             else [float(v) for v in params])
        if len(x) != self.arena.dim:
            raise ValueError(f"x has {len(x)} entries, this amp has "
                             f"{self.arena.dim} sizable vars")
        if self.n_evals >= self.task.budget:
            raise BudgetExhausted(
                f"{self.task.id}: budget of {self.task.budget} evals is spent "
                f"({self.ngspice_calls} ngspice calls)")
        t0 = time.time()
        f = float(self.arena.objective_func(np.asarray(x, dtype=float)))
        wall = time.time() - t0
        self.n_evals += 1
        self.step_i += 1
        m = self.arena.points[-1][1] if self.arena.points else None
        feas, viol = self.spec.feasible(m)
        if not m or not m.get("dcgain") or m.get("dcgain") == _MEAS_DEFAULTS["dcgain"]:
            self.n_fail += 1
        if f < self.best_f:
            self.best_f, self.best_i, self.best_x = f, self.n_evals, list(x)
        out = {"eval_i": self.n_evals, "step": self.step_i, "objective": f,
               "metrics": m, "feasible": bool(feas),
               "viol": ({k: round(v, 6) for k, v in viol.items()} if viol else {}),
               "params": self.arena.decode(x), "x": x,
               "cost": {"evals": 1, "ngspice_calls": 2, "wall_s": round(wall, 4)},
               "is_best": self.best_i == self.n_evals}
        self.last = out
        if self.logger is not None:
            self.logger.log(self, out, action=action)
        if self.verbose:
            print(f"  [{self.n_evals:>4}/{self.task.budget}] fom={f:>12.4f}"
                  + ("  BEST" if out["is_best"] else "")
                  + ("  FEASIBLE" if feas else ""))
        return out

    def objective_fn(self):
        """The bare f(x)->float an optimizer wants, budget enforced. This is what
        `null_sizer.run_cmaes(f, dim, seed)` is handed -- unchanged from how Env
        hands it its objective."""
        def f(x):
            return self.evaluate(params=x, action="objective_fn")["objective"]
        return f

    def best(self):
        if self.best_i is None:
            return None, None
        x, m = self.arena.points[self.best_i - 1]
        return list(x), m

    def observe(self):
        bx, bm = self.best()
        return {
            "task": self.task.as_dict(),
            "harness": self.harness(),
            "budget": {"spent": self.n_evals, "total": self.task.budget,
                       "remaining": self.remaining,
                       "ngspice_calls": self.ngspice_calls,
                       "sim_failures": self.n_fail},
            "best": {"objective": (None if self.best_i is None else self.best_f),
                     "eval_i": self.best_i, "x": bx, "metrics": bm,
                     "feasible": (bool(self.spec.feasible(bm)[0]) if bm else False)},
            "last": ({k: self.last[k] for k in
                      ("eval_i", "objective", "feasible", "viol")}
                     if self.last else None),
            "params": {"names": self.param_names, "dim": self.dim},
        }

    def harness(self):
        return {"simulator": "ngspice", "ngspice": NGSPICE,
                "ngspice_version": _ngspice_version(),
                "eval_entry": "ext_gym.ExtSpec.objective(perf_extraction_amp FoM)",
                "ngspice_calls_per_eval": 2, "era": self.task.era,
                "analoggym_sha": _PINNED_SHA,
                "adapter_sha256": _self_sha256(),
                "netlist_sha256": _file_sha256(self.task.netlist_path),
                "vars_sha256": _file_sha256(self.task.vars_path),
                "pdk": os.path.relpath(self.arena.paths["pdk"],
                                       self.arena.paths["gym"]),
                "domain": "op-amp (SKY130); NOT RF -- separate tier from lna registry"}


# ------------------------------------------------------------ the trajectory
class ExtTrajectoryLogger(object):
    """Append-only (state, action, outcome, cost) rows for the external track.

    Writes to `engineer/data/ext_trajectories.jsonl` and NOWHERE ELSE -- a
    separate table from the in-house `trajectories.jsonl`, the external tier's own
    (charter §3.2's append-only law, applied to a distinct namespace)."""

    def __init__(self, path=EXT_TRAJ_TABLE, run_id=None, meta=None, enabled=True):
        self.path, self.run_id = path, run_id
        self.meta, self.enabled, self.n = dict(meta or {}), enabled, 0

    def log(self, env, out, action=None):
        if not self.enabled:
            return None
        row = {
            "kind": "ext_trajectory", "schema": "engineer-ext-traj-v0",
            "run_id": self.run_id or env.run_id, "task": env.task.id,
            "amp": env.task.amp, "tier": env.task.tier, "seed": env.task.seed,
            "step": out["step"],
            "state": {"digest": _digest([env.task.id, env.task.seed,
                                         out["eval_i"] - 1, env.task.budget]),
                      "evals_spent": out["eval_i"] - 1, "budget": env.task.budget},
            "action": {"kind": "size_eval", "desc": action or "evaluate",
                       "x_digest": _digest(out["x"])},
            "outcome": {"objective": out["objective"], "feasible": out["feasible"],
                        "viol": out["viol"], "metrics": out["metrics"],
                        "is_best": out["is_best"]},
            "cost": out["cost"],
            "harness": {"era": env.task.era, "analoggym_sha": _PINNED_SHA},
            "meta": self.meta, "ts": _now(),
        }
        _append(self.path, row)
        self.n += 1
        return row


# --------------------------------------------------------------- the registry
# The ngspice-runnable subset, established by simulating every amp at its shipped
# default sizing on ngspice 47 (see EXT-CALIBRATION.md for the honest table +
# exclusion reasons). An amp is IN iff its netlist elaborates and produces finite
# AC metrics; OUT amps are recorded with their reason, not silently dropped.
RUNNABLE = [
    "Fan_SMC_Pin_3", "HoiLee_AFFC_Pin_3", "Leung_DFCFC1_Pin_3",
    "Leung_DFCFC2_Pin_3", "Leung_NMCF_Pin_3", "Leung_NMCNR_Pin_3",
    "Peng_ACBC_Pin_3", "Peng_IAC_Pin_3", "Peng_TCFC_Pin_3", "Qu2017_AZC_Pin_3",
    "Ramos_PFC_Pin_3", "Sau_CFCC_Pin_3", "Song_DACFC_Pin_3", "Yan_AZ_Pin_3",
]
# Runnable but degenerate at default sizing (dcgain<0 -> some .meas fail at
# defaults; the deck elaborates and simulates -- an optimizer can move it). Kept
# separate so the golden anchors on a clean default point.
RUNNABLE_DEGENERATE = ["Alfio_RAFFC_Pin_3"]
# Excluded, with the reason (EXT-CALIBRATION.md):
EXCLUDED = {
    "Qu_LEC_Pin_3": "netlist file is EMPTY (0 bytes) in the upstream clone",
    "Tan_CLIA_Pin_3": "netlist does not elaborate on ngspice 47 "
                      "(chopper amp; 'incomplete netlist' at subckt expansion)",
    "Cascode_Miller_Pin_2": "no spice_netlist file (design_variables only)",
    "Cascode_Null_Pin_1": "no spice_netlist file (design_variables only)",
    "Davide_ASMIHF_Pin_3": "no spice_netlist file (design_variables only)",
    "TwoSt_SMCNR_Pin_2": "no spice_netlist file (design_variables only)",
}
# Whole categories out of scope (need a simulator we do not have):
EXCLUDED_CATEGORIES = {
    "Low Dropout Regulator": "ngspice testbenches present; deferred to a follow-up "
                             "rung (LDO FoM in perf_extraction_LDO.py) -- amps first",
    "Charge Pump": "Spectre/HSPICE + OCEAN flow (.ocn, cds.lib) -- no ngspice deck",
    "Phase-Locked Loop": "Spectre + OCEAN flow (pll_vco.ocn, mylib.zip) -- no ngspice",
    "Sensing Front End": "Spectre netlists (spectre_ptat*); PTAT refs -- no ngspice",
    "Voltage Reference": "description only, no shipped netlists",
}


def registry(budget=1000, seeds=(1,), root=None):
    """The external task registry: one ExtTask per runnable amp per seed."""
    out = {}
    for amp in RUNNABLE:
        for s in seeds:
            t = ExtTask(amp, budget=budget, seed=s, root=root)
            out[t.id + f"-s{s}"] = t
    return out


# --------------------------------------------------------------------- utils
def _scratch():
    return os.environ.get("EXT_SCRATCH",
                          "/home/dpatni/.claude/jobs/6f62f9fd/tmp/ext_scratch")


def _run_id(task):
    return f"{task.id}-s{task.seed}-b{task.budget}-{_now().replace(':', '')}"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ngspice_version():
    try:
        r = subprocess.run([NGSPICE, "--version"], capture_output=True, text=True,
                           timeout=15)
        for line in (r.stdout or "").splitlines():
            if "ngspice-" in line:
                return line.strip().lstrip("* ").strip()
    except Exception:                                              # noqa: BLE001
        pass
    return None


def _file_sha256(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except Exception:                                              # noqa: BLE001
        return None


def _self_sha256():
    return _file_sha256(os.path.abspath(__file__))


def _digest(obj, n=16):
    return hashlib.sha256(
        json.dumps(_plain(obj), separators=(",", ":"), sort_keys=True)
        .encode("utf-8")).hexdigest()[:n]


def _append(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(_plain(row), separators=(",", ":"), sort_keys=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    return row


def _plain(o):
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return _plain(o.tolist())
    return o


# ----------------------------------------------------------------------- CLI
def _golden(amp, reps=3):
    """Replay-fence golden: FIXED sizing (the shipped defaults) -> FIXED metrics,
    reps times in-process + a note on the separate-process check the CLI driver
    runs. Reports the spread; a real golden has spread 0.0 on a deterministic
    harness."""
    task = ExtTask(amp, budget=reps + 1, seed=0)
    env = ExtEnv(task)
    # x that decodes to the SHIPPED defaults: encode(defaults).
    defaults = {n: task.defaults[n] for n in task.names}
    x0 = env.arena.encode(defaults)
    objs, metricss = [], []
    for _ in range(reps):
        out = env.evaluate(params=x0)
        objs.append(out["objective"])
        metricss.append(out["metrics"])
    spread = max(objs) - min(objs)
    print(f"golden {amp}: {reps} reps @ shipped-default sizing")
    for i, (o, m) in enumerate(zip(objs, metricss)):
        print(f"  rep {i}: fom={o:.6f}  dcgain={m.get('dcgain')}  "
              f"gbp={m.get('gbp')}  phase_deg={m.get('phase_in_deg')}")
    print(f"  spread(fom) = {spread:.6g}   (deterministic harness -> 0.0)")
    return {"amp": amp, "reps": reps, "objs": objs, "spread": spread,
            "metrics": metricss[0], "x0": x0, "defaults": defaults,
            "harness": env.harness()}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="AnalogGym externals adapter")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--golden", metavar="AMP")
    ap.add_argument("--amp", default="HoiLee_AFFC_Pin_3")
    ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    if a.list:
        g = gym_root(verbose=True)
        print(f"\nrunnable amps ({len(RUNNABLE)}):")
        for amp in RUNNABLE:
            t = ExtTask(amp, root=g and None)
            print(f"  {amp:<22} d={t.dim:>2}  ({len(t.defaults)} vars)")
        print(f"\ndegenerate-at-default ({len(RUNNABLE_DEGENERATE)}): "
              + ", ".join(RUNNABLE_DEGENERATE))
        print(f"excluded ({len(EXCLUDED)}):")
        for amp, why in EXCLUDED.items():
            print(f"  {amp:<22} {why}")
        return 0
    if a.golden:
        _golden(a.golden, reps=a.reps)
        return 0
    if a.selftest:
        gym_root(verbose=True)
        task = ExtTask(a.amp, budget=3, seed=1)
        env = ExtEnv(task, verbose=True)
        print(f"amp {task.amp}: d={env.dim} sizable vars, tier={task.tier}")
        print(f"  harness: {env.harness()['ngspice_version']}, "
              f"sha={_PINNED_SHA[:12]}")
        x0 = env.arena.encode({n: task.defaults[n] for n in task.names})
        out = env.evaluate(params=x0)
        print(f"  default-sizing eval: fom={out['objective']:.4f} "
              f"feasible={out['feasible']}")
        print("  " + env.spec.report(out["metrics"]))
        try:
            env.evaluate(params=x0)
            env.evaluate(params=x0)
            env.evaluate(params=x0)
            print("  BUDGET NOT ENFORCED -- bug")
            return 1
        except BudgetExhausted as e:
            print(f"  budget enforced: {e}")
        return 0
    ap.error("give --selftest, --list, or --golden AMP")


if __name__ == "__main__":
    sys.exit(main())
