"""engineer/ext_ldo.py -- the AnalogGym LDO externals adapter (the LDO rung).

The follow-up rung `EXT-CALIBRATION.md` §2.3 / `ext_gym.py` `EXCLUDED_CATEGORIES`
named and deferred: AnalogGym's Low-Dropout-Regulator category ships ngspice
testbenches (unlike Charge Pump / PLL / Sensing / Voltage Reference, which need
Spectre/OCEAN we do not have), so the LDOs ARE runnable here -- amps first, LDOs
second. This module is that second rung: it turns an AnalogGym LDO testbench into
the same env.py *contract* `ext_gym.ExtEnv` exposes, WITHOUT editing env.py,
tasks.py, ext_gym.py, or any driver -- E-1's falsifier applied to the LDO track:
the unedited `score_ext`-shape driver runs against `ExtLdoEnv` exactly as it runs
against `Env`/`ExtEnv`, and `lna/null_sizer.run_cmaes` is imported verbatim as the
cmaes arm (via score_ext_ldo).

WHY A SIBLING MODULE, NOT AN EDIT TO ext_gym.py
-----------------------------------------------
`ext_gym.py` is pinned by its own sha256 in every AMP result's harness stamp and in
`PROTOCOL.md §EXT.9` ("a new ext_gym.py sha256 is an era cutover for this track").
Editing it to add LDOs would re-stamp -- and thus threaten to invalidate -- the
in-flight 280-cell amp scoreboard. So the LDO rung lands as a SIBLING file with its
own sha256 and its own pre-registration appendix (§EXT-LDO), leaving the amp
adapter and its golden byte-for-byte untouched. The two share only pure utilities
(imported from ext_gym): the dep-root walk-up, the SPICE-number parser, the
harness-stamp helpers, the trajectory/plain-JSON writers, BudgetExhausted. Nothing
that measures a number is shared or forked.

WHAT IS PINNED (the LDO "specs" -- curated from AnalogGym, never invented)
-------------------------------------------------------------------------
    netlist (subckt)  AnalogGym/.../Low Dropout Regulator/design_variables/<fam>.txt
                      (yes, design_variables/: for the LDO category THIS file holds
                      the `.subckt <fam> ... .ends` with L_Mx/W_Mx/M_Mx devices --
                      the inverse of the amp category's naming; verified by grep)
    design vars       .../spice_netlist/<fam>_vars.spice  (the `.param` defaults --
                      the ONLY thing an optimizer touches; the golden's fixed point)
    testbench         .../ldo_spice_testbench/<fam>_acdc.cir + <fam>_tran.cir
                      -- each family ships a COMPLETE self-contained deck with its
                      own supply/Vref/Iload, its own node names, and its own wrdata
                      prefixes; we replay it VERBATIM, rewriting only the three
                      `.include ../simulations/*` lines to absolute staged paths and
                      inserting the design-variable override. We do NOT rebuild the
                      deck (unlike the amp adapter): AnalogGym's own testbench is the
                      measurement, faithfully.
    objective (reward) AnalogGym's OWN LDO reward -- the `self.reward` sum of 15
                      directional normalized-margin scores in RGNN_RL/LDO_TB.py
                      (perf_extraction_LDO.py ships only the raw-metric extractor,
                      NO scalar; the scalar lives in the RL env's reward-engineering,
                      which IS AnalogGym's own LDO objective). Reproduced verbatim in
                      LdoSpec.objective; NEGATED so lower-is-better composes with the
                      amp track's convention.
    box               the design-variable KIND ranges (L/W/M/CAP-multiplicity/
                      CURRENT), shared with ext_gym's _KIND_BOX shape.

DETERMINISM / STAMPS / FAILURE  -- identical discipline to ext_gym (see that file).
Two ngspice calls per eval (acdc deck + tran deck), both counted. A family whose
netlist is empty/absent or does not elaborate raises ExtLdoNotSizable BEFORE any
eval; a deck that ran but whose wrdata is missing/short gets AnalogGym's OWN
directional sentinel (score = -1 for that term, per LDO_TB.py) -- finite, one eval.

    python engineer/ext_ldo.py --list
    python engineer/ext_ldo.py --selftest
    python engineer/ext_ldo.py --golden ldo_2          # replay-fence, 3x + note
"""
import math
import os
import re
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ext_gym as X   # noqa: E402  -- pure utilities only (see module docstring)

# reuse ext_gym's pins/utilities verbatim so the two adapters cannot drift on the
# things that are genuinely shared (dep root, number parse, stamps, JSON, budget).
gym_root = X.gym_root
_PINNED_SHA = X._PINNED_SHA
NGSPICE = X.NGSPICE
_num = X._num
_now = X._now
_file_sha256 = X._file_sha256
_ngspice_version = X._ngspice_version
_plain = X._plain
_append = X._append
_digest = X._digest
BudgetExhausted = X.BudgetExhausted
DATA_DIR = X.DATA_DIR
EXT_LDO_TRAJ_TABLE = os.path.join(DATA_DIR, "ext_ldo_trajectories.jsonl")

# The LDO category root inside the clone.
_LDO_SUBDIR = os.path.join("AnalogGym", "Low Dropout Regulator")


def _self_sha256():
    return _file_sha256(os.path.abspath(__file__))


# ----------------------------------------------------------------- paths
def _ldo_paths(root=None):
    g = gym_root() if root is None else os.path.join(root, "AnalogGym", "repo")
    if not os.path.isdir(g):
        g = gym_root()
    ldo = os.path.join(g, _LDO_SUBDIR)
    pdk = os.path.join(g, "PDK", "sky130_pdk")
    ng = os.path.join(pdk, "libs.tech", "ngspice")
    return {
        "gym": g, "ldo": ldo, "pdk": pdk,
        "netlist_dir": os.path.join(ldo, "design_variables"),   # subckt lives here
        "vars_dir": os.path.join(ldo, "spice_netlist"),         # .param defaults here
        "tb_dir": os.path.join(ldo, "ldo_spice_testbench"),
        "includes": [
            os.path.join(ng, "corners", "tt.spice"),
            os.path.join(ng, "r+c", "res_typical__cap_typical.spice"),
            os.path.join(ng, "r+c", "res_typical__cap_typical__lin.spice"),
            os.path.join(ng, "corners", "tt", "specialized_cells.spice"),
        ],
    }


# ---------------------------------------------------- design-variable box
# Shared KIND box with ext_gym (imported), extended with the LDO-only multiplicity
# kinds (M_CL / M_Cfb / M_Rfb are integer device multiplicities like M). Fixed,
# testbench-owned bias voltages (Vb / Vb1 / Vb2) are NEVER sized.
_KIND_BOX = dict(X._KIND_BOX)
_FIXED_VARS = {"VB", "VB1", "VB2"}          # gate-bias voltages set by the deck


def _var_kind(name):
    """Kind of an LDO design variable from its name. LDO vars are `W_Mx`, `L_Mx`,
    `M_Mx`, `current_0_bias`, and the multiplicity knobs `M_CL`/`M_Cfb`/`M_Rfb`/
    `M_R0`/`M_C0`.../`M_C4`."""
    up = name.upper()
    if up in _FIXED_VARS:
        return None
    if up.startswith("W_"):
        return "W"
    if up.startswith("L_"):
        return "L"
    if up.startswith("M_"):        # M_Mx, M_CL, M_Cfb, M_Rfb, M_C0, M_R0 ... -> mult
        return "M"
    if up.endswith("_BIAS") or "CURRENT" in up:
        return "CUR"
    return None


def _parse_vars(path):
    """Parse a `_vars.spice` file (`.param NAME=VAL ...`, possibly `NAME=OTHERNAME`
    aliases) into {name: float}. Aliases (`W_M1=W_M0`) are resolved to their base so
    the sized set contains only the FREE parameters -- AnalogGym pins matched pairs
    by aliasing, exactly like the amp netlists bake in `m='4*..'`; we must not size
    an alias independently or we break the intended matching."""
    raw = {}
    alias = {}
    txt = open(path, encoding="utf-8").read()
    for tok in re.sub(r"(?im)^\s*\.param", " ", txt).replace("\n", " ").split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        k, v = k.strip(), v.strip()
        if re.match(r"^[A-Za-z_]", v):        # NAME = OTHERNAME  (an alias)
            alias[k] = v
        else:
            raw[k] = _num(v)
    return raw, alias


# --------------------------------------------------------------- the spec
# AnalogGym's OWN LDO targets + reward, reproduced verbatim from RGNN_RL:
#   ckt_graphs.py GraphLDOtestbench  -> the *_target constants
#   LDO_TB.py    _do_simulation      -> the per-metric directional scores + the sum
# perf_extraction_LDO.py ships only the raw-metric extractor (no scalar); the scalar
# is this reward-engineering. `objective` returns the NEGATED reward (lower better).
_LDO_TARGETS = {
    "LDR": 0.1, "LNR": 0.01,
    "Power_maxload": 9e-5, "Power_minload": 9e-6,
    "vos": 2e-3, "PSRR": -40.0, "GBW": 2e6, "phase_margin": 60.0,
    "v_undershoot": 0.1, "v_overshoot": 0.1,
}
# The raw-metric keys the reward reads (all as read at wrdata row index [1]).
_LDO_METRICS = ("LDR", "LNR_maxload", "LNR_minload", "Power_maxload",
                "Power_minload", "vos_maxload", "vos_minload", "PSRR_maxload",
                "PSRR_minload", "dcgain_maxload", "dcgain_minload", "GBW_maxload",
                "GBW_minload", "phase_margin_maxload", "phase_margin_minload",
                "v_undershoot", "v_overshoot")


def _score_toward(target, val):
    """AnalogGym's smaller-is-better score np.min([(target-val)/(target+val),0])
    (LDO_TB.py, for LDR/LNR/Power/vos/undershoot/overshoot: metric should be BELOW
    target). <=0; 0 iff val <= target."""
    d = target + val
    if d == 0:
        return -1.0
    return float(min((target - val) / d, 0.0))


def _neg_margin(val, target):
    """AnalogGym's larger-is-better score np.min([(val-target)/(val+target),0])
    (LDO_TB.py, for PSRR/GBW/phase-margin: metric should EXCEED target). <=0; 0 iff
    val >= target. Note the numerator is (val-target), the mirror of _score_toward."""
    d = val + target
    if d == 0:
        return -1.0
    return float(min((val - target) / d, 0.0))


class LdoSpec(object):
    """AnalogGym's LDO reward as a spec-shaped object (objective/feasible/report),
    API-compatible with lna/spec.Spec and ext_gym.ExtSpec so the same
    trajectory/observe code reads it. `objective` = -reward (lower better)."""

    name = "analoggym-ldo-reward"

    def _scores(self, m):
        """The 15 directional scores, LDO_TB.py verbatim (missing metric -> the same
        sentinel LDO_TB.py assigns: a failed AC gives score -1, etc.)."""
        g = dict(m or {})
        T = _LDO_TARGETS
        s = {}
        # LDR / LNR: negative raw value is a sim failure -> -1 (LDO_TB.py)
        s["LDR"] = -1.0 if g.get("LDR", -1) < 0 else _score_toward(T["LDR"], g["LDR"])
        s["LNR_maxload"] = (-1.0 if g.get("LNR_maxload", -1) < 0
                            else _score_toward(T["LNR"], g["LNR_maxload"]))
        s["LNR_minload"] = (-1.0 if g.get("LNR_minload", -1) < 0
                            else _score_toward(T["LNR"], g["LNR_minload"]))
        s["Power_maxload"] = _score_toward(T["Power_maxload"],
                                           g.get("Power_maxload", 1.0))
        s["Power_minload"] = _score_toward(T["Power_minload"],
                                           g.get("Power_minload", 1.0))
        s["vos_maxload"] = _score_toward(T["vos"], abs(g.get("vos_maxload", 1.0)))
        s["vos_minload"] = _score_toward(T["vos"], abs(g.get("vos_minload", 1.0)))
        # PSRR (LDO_TB.py verbatim): >0 (or missing) is a failure -> -1; else
        # score = min((PSRR-target)/(PSRR+target),0), then forced to 0 if the PSRR is
        # already deeper than target (PSRR < target, both negative). Note the
        # numerator is (val-target), NOT _score_toward's (target-val).
        for tag in ("maxload", "minload"):
            p = g.get(f"PSRR_{tag}")
            if p is None or p > 0:
                s[f"PSRR_{tag}"] = -1.0
            else:
                sc = _neg_margin(p, T["PSRR"])
                s[f"PSRR_{tag}"] = 0.0 if p < T["PSRR"] else sc
        # GBW + PM (LDO_TB.py verbatim): gated on positive dcgain; failure -> -1;
        # else score = min((val-target)/(val+target),0).
        for tag in ("maxload", "minload"):
            dcg = g.get(f"dcgain_{tag}")
            gbw = g.get(f"GBW_{tag}")
            pm = g.get(f"phase_margin_{tag}")
            if dcg is None or dcg <= 0 or gbw is None or pm is None:
                s[f"GBW_{tag}"] = -1.0
                s[f"PM_{tag}"] = -1.0
            else:
                s[f"GBW_{tag}"] = _neg_margin(gbw, T["GBW"])
                s[f"PM_{tag}"] = _neg_margin(pm, T["phase_margin"])
        s["v_undershoot"] = _score_toward(T["v_undershoot"],
                                          g.get("v_undershoot", 1.0))
        s["v_overshoot"] = _score_toward(T["v_overshoot"],
                                         abs(g.get("v_overshoot", 1.0)))
        return s

    def _reward(self, m):
        s = self._scores(m)
        r = (s["LDR"] + s["LNR_maxload"] + s["LNR_minload"]
             + s["Power_maxload"] + s["Power_minload"]
             + s["vos_maxload"] + s["vos_minload"]
             + s["PSRR_maxload"] + s["PSRR_minload"]
             + s["GBW_maxload"] + s["GBW_minload"]
             + s["PM_maxload"] + s["PM_minload"]
             + s["v_overshoot"] + s["v_undershoot"])
        # LDO_TB.py adds CL_area_score + 10 iff reward>=0; CL_area_score needs an OP
        # decap read our replay does not compute, so the bonus (a constant +10 plus a
        # bounded [-1,1] decap term) is applied as +10 only when all 15 terms are 0
        # (reward==0). This is the SAME threshold LDO_TB.py uses; we omit only the
        # <=|1| decap nudge, which cannot change the sign or the arm ordering at the
        # feasibility boundary. Recorded as a deviation in the appendix.
        if r >= 0:
            r = r + 10.0
        return float(r)

    def objective(self, m):
        return -self._reward(m)      # lower is better (composes with amp track)

    def feasible(self, m):
        """An LDO is feasible iff AnalogGym's reward hits its all-targets-met plateau
        (every one of the 15 directional scores == 0, i.e. reward >= 0 before bonus).
        Directional over AnalogGym's OWN scored quantities -- not a new spec."""
        s = self._scores(m)
        viol = {k: round(-v, 6) for k, v in s.items() if v < 0}
        return (len(viol) == 0), viol

    def report(self, m):
        g = dict(m or {})
        return ("  ldo: dcgain(max)=%s PSRR(max)=%s GBW(max)=%s PM(max)=%s "
                "LDR=%s under=%s over=%s reward=%.3f"
                % (_fmt(g.get("dcgain_maxload")), _fmt(g.get("PSRR_maxload")),
                   _fmt(g.get("GBW_maxload")), _fmt(g.get("phase_margin_maxload")),
                   _fmt(g.get("LDR")), _fmt(g.get("v_undershoot")),
                   _fmt(g.get("v_overshoot")), self._reward(m)))


def _fmt(v):
    return "-" if v is None else (f"{v:.3g}" if isinstance(v, float) else str(v))


# --------------------------------------------------------------- the task
class ExtLdoNotSizable(ValueError):
    """LDO analogue of ext_gym.ExtNotSizable / env.NotSizable: an LDO family that
    cannot become a deck (empty/absent netlist, no .subckt, or does not elaborate).
    Raised at build time, before any eval is charged."""

    def __init__(self, message, fam=None):
        super().__init__(message)
        self.fam = fam


class LdoTask(object):
    """One AnalogGym LDO task: a family + its box + budget + seed. A PIN: the netlist
    (design_variables/<fam>.txt), the vars (spice_netlist/<fam>_vars.spice) and the
    two testbenches are frozen upstream at `_PINNED_SHA`."""

    def __init__(self, fam, budget=1000, seed=1, notes="", root=None):
        self.fam = fam
        self.id = "ldo-" + fam
        self.budget, self.seed, self.notes = int(budget), int(seed), notes
        self.tier = "ext-ldo"
        self.era = "analoggym-" + _PINNED_SHA[:12]
        self._root = root
        p = _ldo_paths(root)
        self.netlist_path = os.path.join(p["netlist_dir"], fam + ".txt")
        self.vars_path = os.path.join(p["vars_dir"], fam + "_vars.spice")
        self.acdc_tb = os.path.join(p["tb_dir"], fam + "_acdc.cir")
        self.tran_tb = os.path.join(p["tb_dir"], fam + "_tran.cir")
        self.raw, self.alias = _parse_vars(self.vars_path)
        self.defaults = dict(self.raw)
        self.names = sorted(n for n in self.raw if _var_kind(n) is not None)
        self.kinds = {n: _var_kind(n) for n in self.names}

    @property
    def dim(self):
        return len(self.names)

    def with_(self, **kw):
        d = dict(fam=self.fam, budget=self.budget, seed=self.seed,
                 notes=self.notes, root=self._root)
        d.update(kw)
        return LdoTask(**d)

    def as_dict(self):
        return {"id": self.id, "fam": self.fam, "tier": self.tier,
                "budget": self.budget, "seed": self.seed, "era": self.era,
                "dim": self.dim, "n_vars": len(self.raw), "notes": self.notes}


# --------------------------------------------------------------- the arena
class _LdoArena(object):
    """Deck-replay + box decode + one-eval objective for ONE AnalogGym LDO family.

    Owns the free `points` hook (list of (x, metrics) per eval)."""

    def __init__(self, task, spec, workdir, root=None):
        self.task, self.spec, self.workdir = task, spec, workdir
        self.paths = _ldo_paths(root)
        self.points = []
        self.names, self.kinds, self.dim = task.names, task.kinds, task.dim
        self._verify_sizable()

    def _verify_sizable(self):
        for pth, what in ((self.task.netlist_path, "netlist"),
                          (self.task.acdc_tb, "acdc testbench"),
                          (self.task.tran_tb, "tran testbench")):
            if not os.path.exists(pth) or os.path.getsize(pth) == 0:
                raise ExtLdoNotSizable(
                    f"AnalogGym LDO {self.task.fam!r}: {what} empty or absent "
                    f"({pth})", fam=self.task.fam)
        self.subckt = self._subckt_name()
        if self.subckt is None:
            raise ExtLdoNotSizable(
                f"AnalogGym LDO {self.task.fam!r}: no .subckt line in netlist",
                fam=self.task.fam)

    def _subckt_name(self):
        for line in open(self.task.netlist_path, encoding="utf-8"):
            if line.strip().lower().startswith(".subckt"):
                return line.split()[1]
        return None

    # ---- box: [0,1]^d <-> raw values (shared decode shape with ext_gym) ----
    def decode(self, x):
        out = {}
        for name, t in zip(self.names, x):
            lo, hi, islog, isint = _KIND_BOX[self.kinds[name]]
            t = min(max(float(t), 0.0), 1.0)
            if islog:
                v = 10 ** (math.log10(lo) + t * (math.log10(hi) - math.log10(lo)))
            else:
                v = lo + t * (hi - lo)
            out[name] = int(round(v)) if isint else v
        return out

    def encode(self, params):
        x = []
        for name in self.names:
            lo, hi, islog, _ = _KIND_BOX[self.kinds[name]]
            v = float(params[name])
            if islog:
                v = max(v, lo)
                t = (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
            else:
                t = (v - lo) / (hi - lo)
            x.append(min(max(t, 0.0), 1.0))
        return x

    # ---- the objective: replay 2 shipped decks, parse wrdata, reward ------
    def objective_func(self, x):
        params = self.decode(np.asarray(x, dtype=float).tolist())
        metrics = self._simulate(params)
        self.points.append((list(np.asarray(x, dtype=float)), metrics))
        return self.spec.objective(metrics)

    def _override_block(self, params):
        lines = []
        for name, v in params.items():
            if self.kinds[name] == "M":
                lines.append(f".param {name}={int(v)}")
            else:
                lines.append(f".param {name}={v:.10g}")
        # re-assert the aliases AnalogGym pinned (matched pairs) against the new base
        for a, base in self.task.alias.items():
            lines.append(f".param {a}={base}")
        return "\n".join(lines)

    def _stage_deck(self, tb_path, override_path, tag):
        """Read the shipped testbench, rewrite the three `.include ../simulations/*`
        lines to absolute (space-free staged) paths, drop the trailing
        `_dev_params.spice` OP include (needs .op vectors we do not use), inject the
        override right after the vars include, and point wrdata into the workdir.
        Everything else (nodes, sweeps, meas, wrdata prefixes) is AnalogGym's own."""
        src = open(tb_path, encoding="utf-8").read()
        out = []
        for line in src.splitlines():
            s = line.strip()
            low = s.lower()
            if low.startswith(".include") and "../simulations/" in s:
                base = s.split("../simulations/")[1].strip()
                if base.endswith("_dev_params.spice"):
                    continue                     # OP extraction -- not needed
                if base.endswith("_vars.spice"):
                    out.append(f".include {self._staged['vars']}")
                    out.append(f".include {override_path}")   # override AFTER default
                else:                            # the subckt netlist include
                    out.append(f".include {self._staged['netlist']}")
                continue
            if low.startswith(".include") and "mosfet_model/" in s:
                # map the four PDK includes onto our absolute paths, in order
                idx = len([o for o in out if o.startswith(".include")
                           and o.split("/")[-1] in
                           {os.path.basename(p) for p in self.paths["includes"]}])
                out.append(f".include {self.paths['includes'][idx]}")
                continue
            out.append(line)
        text = "\n".join(out)
        deck = os.path.join(self.workdir, f"deck_{tag}.cir")
        with open(deck, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        return deck

    def _simulate(self, params):
        wd = self.workdir
        os.makedirs(wd, exist_ok=True)
        # stage netlist+vars once (space-free names so ngspice .include is happy)
        self._staged = {
            "netlist": os.path.join(wd, self.task.fam + "_netlist.txt"),
            "vars": os.path.join(wd, self.task.fam + "_vars.spice"),
        }
        if not os.path.exists(self._staged["netlist"]):
            _copy(self.task.netlist_path, self._staged["netlist"])
        if not os.path.exists(self._staged["vars"]):
            _copy(self.task.vars_path, self._staged["vars"])
        ov = os.path.join(wd, "override.spice")
        with open(ov, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self._override_block(params) + "\n")
        # clean prior wrdata so a failed re-run cannot read a stale file
        for fn in os.listdir(wd):
            if fn.startswith(self.task.fam) and ("_ACDC_" in fn or "_LNR_" in fn
                                                 or "_LR_" in fn or "_PSRR_" in fn
                                                 or "_GBW_" in fn or "_tran_" in fn
                                                 or "_Vdrop_" in fn):
                try:
                    os.remove(os.path.join(wd, fn))
                except OSError:
                    pass
        ac_deck = self._stage_deck(self.task.acdc_tb, ov, "acdc")
        tr_deck = self._stage_deck(self.task.tran_tb, ov, "tran")
        self._run(ac_deck, "acdc")
        self._run(tr_deck, "tran")
        return self._read_metrics()

    def _run(self, deck, tag):
        log = os.path.join(self.workdir, f"log_{tag}.txt")
        try:
            subprocess.run([NGSPICE, "-b", "-o", log, deck], cwd=self.workdir,
                           capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return

    # ---- read AnalogGym's wrdata files (row index [1], the perf_extraction_LDO
    #      column layout), family-prefixed -----------------------------------
    def _read_row1(self, prefix, ncol):
        """Return the columns of data-row index 1 (the 2nd row) of a wrdata file, or
        None if the file is missing/short -- exactly perf_extraction_LDO.py's `[1]`
        access, but tolerant (it raises; we sentinel)."""
        path = os.path.join(self.workdir, prefix)
        if not os.path.exists(path):
            return None
        rows = []
        for line in open(path, encoding="utf-8", errors="replace"):
            parts = line.split()
            if len(parts) < ncol:
                continue
            try:
                rows.append([float(p) for p in parts[:ncol]])
            except ValueError:
                continue
            if len(rows) >= 2:
                break
        return rows[1] if len(rows) >= 2 else None

    def _read_metrics(self):
        f = self.task.fam
        # ldo_1/ldo_2 use the LDO_TB_ACDC_* prefixes? No -- their per-family decks use
        # `<fam>_ACDC_*`; ldo_simple/folded use `<fam>_*` (no _ACDC_). Detect by which
        # files the shipped deck actually wrote (grep of the deck's own wrdata lines).
        pre = self._wrdata_prefixes()
        m = {}
        # LNR (col layout: freq/sweep, value)  -> value at [1][1]
        r = self._read_row1(pre["LNR_maxload"], 2)
        if r is not None:
            m["LNR_maxload"] = r[1]
        r = self._read_row1(pre["LNR_minload"], 2)
        if r is not None:
            m["LNR_minload"] = r[1]
        # LR_Power_vos: cols = idx,LR, idx,Power1, idx,Power2, idx,vos1, idx,vos2
        # perf_extraction reads [1]=LR, [3]=Power_max, [5]=Power_min, [7]=vos_max,
        # [9]=vos_min from the split, i.e. columns 1,3,5,7,9 of the wrdata row.
        r = self._read_row1(pre["LR_Power_vos"], 10)
        if r is not None:
            m["LDR"] = r[1]
            m["Power_maxload"] = r[3]
            m["Power_minload"] = r[5]
            m["vos_maxload"] = r[7]
            m["vos_minload"] = r[9]
        # PSRR_dcgain: cols = freq,DCPSRp, freq,dcgain  -> PSRR=[1], dcgain=[3]
        for tag in ("maxload", "minload"):
            r = self._read_row1(pre[f"PSRR_dcgain_{tag}"], 4)
            if r is not None:
                m[f"PSRR_{tag}"] = r[1]
                m[f"dcgain_{tag}"] = r[3]
            r = self._read_row1(pre[f"GBW_PM_{tag}"], 4)
            if r is not None:
                m[f"GBW_{tag}"] = r[1]
                m[f"phase_margin_{tag}"] = r[3]
        # tran: cols = time,v_undershoot, time,v_overshoot -> [1], [3]
        r = self._read_row1(pre["tran_meas"], 4)
        if r is not None:
            m["v_undershoot"] = r[1]
            m["v_overshoot"] = r[3]
        return m

    def _wrdata_prefixes(self):
        """Map logical metric -> the exact wrdata filename the SHIPPED deck writes,
        parsed from the deck's own `wrdata <name> ...` lines so we never guess the
        family's naming convention (ldo_1/2 use `<fam>_ACDC_*`, simple/fc use
        `<fam>_*`)."""
        want = {
            "LNR_maxload": "LNR_maxload", "LNR_minload": "LNR_minload",
            "LR_Power_vos": "LR_Power_vos",
            "PSRR_dcgain_maxload": "PSRR_dcgain_maxload",
            "PSRR_dcgain_minload": "PSRR_dcgain_minload",
            "GBW_PM_maxload": "GBW_PM_maxload", "GBW_PM_minload": "GBW_PM_minload",
            "tran_meas": "tran_meas",
        }
        found = {}
        for tb, keys in ((self.task.acdc_tb, [k for k in want if k != "tran_meas"]),
                         (self.task.tran_tb, ["tran_meas"])):
            for line in open(tb, encoding="utf-8"):
                s = line.strip()
                if not s.lower().startswith("wrdata"):
                    continue
                fn = s.split()[1]
                for k in keys:
                    if fn.endswith(want[k]):
                        found[k] = fn
        # fall back to the canonical names if a wrdata line was not matched
        for k, suf in want.items():
            found.setdefault(k, f"{self.task.fam}_{suf}")
        return found


def _copy(src, dst):
    with open(src, "rb") as a, open(dst, "wb") as b:
        b.write(a.read())


# ------------------------------------------------------------------ the env
class ExtLdoEnv(object):
    """The AnalogGym LDO sizing environment -- env.Env / ext_gym.ExtEnv public
    surface, LDO domain. Exposes objective_fn/dim/evaluate/best/observe/harness/
    n_evals/best_f/spec. Deterministic; budget-counted; harness-stamped."""

    def __init__(self, task, budget=None, seed=None, logger=None, workdir=None,
                 run_id=None, verbose=False, root=None):
        self.task = task.with_(budget=budget if budget is not None else task.budget,
                               seed=seed if seed is not None else task.seed)
        self.spec = LdoSpec()
        self._root = root
        self.run_id = run_id or _run_id(self.task)
        self.workdir = workdir or os.path.join(
            _scratch(), f"ldo_{self.task.fam}_s{self.task.seed}_{os.getpid()}")
        self.arena = _LdoArena(self.task, self.spec, self.workdir, root=root)
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
        return self.n_evals * 2

    @property
    def remaining(self):
        return max(0, self.task.budget - self.n_evals)

    def evaluate(self, params=None, action=None):
        if params is None:
            raise ValueError("evaluate() needs params: an x vector or a dict")
        x = (self.arena.encode(params) if isinstance(params, dict)
             else [float(v) for v in params])
        if len(x) != self.arena.dim:
            raise ValueError(f"x has {len(x)} entries, {self.task.fam} has "
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
        if not m or m.get("dcgain_maxload") is None:
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
            print(f"  [{self.n_evals:>4}/{self.task.budget}] obj={f:>12.4f}"
                  + ("  BEST" if out["is_best"] else "")
                  + ("  FEASIBLE" if feas else ""))
        return out

    def objective_fn(self):
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
            "task": self.task.as_dict(), "harness": self.harness(),
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
                "eval_entry": "ext_ldo.LdoSpec.objective(RGNN_RL LDO reward)",
                "ngspice_calls_per_eval": 2, "era": self.task.era,
                "analoggym_sha": _PINNED_SHA,
                "adapter_sha256": _self_sha256(),
                "ext_gym_sha256": X._self_sha256(),
                "netlist_sha256": _file_sha256(self.task.netlist_path),
                "vars_sha256": _file_sha256(self.task.vars_path),
                "acdc_tb_sha256": _file_sha256(self.task.acdc_tb),
                "tran_tb_sha256": _file_sha256(self.task.tran_tb),
                "pdk": os.path.relpath(self.arena.paths["pdk"],
                                       self.arena.paths["gym"]),
                "domain": "LDO (SKY130); NOT RF -- ext-ldo tier"}


# ---------------------------------------------------------- the trajectory
class ExtLdoTrajectoryLogger(object):
    """Append-only (state, action, outcome, cost) rows for the LDO track, to
    `engineer/data/ext_ldo_trajectories.jsonl` and NOWHERE ELSE."""

    def __init__(self, path=EXT_LDO_TRAJ_TABLE, run_id=None, meta=None, enabled=True):
        self.path, self.run_id = path, run_id
        self.meta, self.enabled, self.n = dict(meta or {}), enabled, 0

    def log(self, env, out, action=None):
        if not self.enabled:
            return None
        row = {
            "kind": "ext_ldo_trajectory", "schema": "engineer-ext-ldo-traj-v0",
            "run_id": self.run_id or env.run_id, "task": env.task.id,
            "fam": env.task.fam, "tier": env.task.tier, "seed": env.task.seed,
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


# --------------------------------------------------------------- registry
# The four shipped LDO families. Runnability is established by simulation at default
# sizing (see --list / EXT-CALIBRATION.md LDO section); a family is IN iff its
# testbenches elaborate and produce parseable wrdata. The golden anchors on the
# cleanest-at-default family.
FAMILIES = ["ldo_1", "ldo_2", "ldo_simple", "ldo_folded_cascode"]
RUNNABLE = None      # filled by probe_runnable(); see --list
EXCLUDED = {}


def registry(budget=1000, seeds=(1,), fams=None, root=None):
    out = {}
    for fam in (fams or FAMILIES):
        for s in seeds:
            t = LdoTask(fam, budget=budget, seed=s, root=root)
            out[t.id + f"-s{s}"] = t
    return out


# --------------------------------------------------------------------- utils
def _scratch():
    return os.environ.get("EXT_LDO_SCRATCH",
                          "/home/dpatni/.claude/jobs/6f62f9fd/tmp/ext_ldo_scratch")


def _run_id(task):
    return f"{task.id}-s{task.seed}-b{task.budget}-{_now().replace(':', '')}"


# ----------------------------------------------------------------------- CLI
def _golden(fam, reps=3):
    task = LdoTask(fam, budget=reps + 1, seed=0)
    env = ExtLdoEnv(task)
    defaults = {n: task.defaults[n] for n in task.names}
    x0 = env.arena.encode(defaults)
    objs, metricss = [], []
    for _ in range(reps):
        out = env.evaluate(params=x0)
        objs.append(out["objective"])
        metricss.append(out["metrics"])
    spread = max(objs) - min(objs)
    print(f"golden {fam}: {reps} reps @ shipped-default sizing (d={env.dim})")
    for i, (o, m) in enumerate(zip(objs, metricss)):
        print(f"  rep {i}: obj={o:.6f}  " + env.spec.report(m).strip())
    print(f"  spread(obj) = {spread:.6g}   (deterministic harness -> 0.0)")
    return {"fam": fam, "reps": reps, "objs": objs, "spread": spread,
            "metrics": metricss[0], "x0": x0, "defaults": defaults,
            "harness": env.harness(), "feasible": env.spec.feasible(metricss[0])[0]}


def _probe_one(fam):
    try:
        r = _golden(fam, reps=1)
        m = r["metrics"]
        ok = m.get("dcgain_maxload") is not None
        return {"fam": fam, "elaborated": True, "obj": r["objs"][0],
                "dcgain_maxload": m.get("dcgain_maxload"),
                "feasible_default": r["feasible"], "runnable": ok}
    except ExtLdoNotSizable as e:
        return {"fam": fam, "elaborated": False, "reason": str(e), "runnable": False}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="AnalogGym LDO externals adapter")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--golden", metavar="FAM")
    ap.add_argument("--fam", default="ldo_2")
    ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    if a.list:
        gym_root(verbose=True)
        print(f"\nLDO families ({len(FAMILIES)}): probing at default sizing...")
        for fam in FAMILIES:
            p = _probe_one(fam)
            if p["elaborated"]:
                t = LdoTask(fam)
                print(f"  {fam:<22} d={t.dim:>2}  runnable={p['runnable']}  "
                      f"dcgain_max={_fmt(p.get('dcgain_maxload'))}  "
                      f"obj={p['obj']:.3f}  feasible@default={p['feasible_default']}")
            else:
                print(f"  {fam:<22} NOT SIZABLE: {p['reason']}")
        return 0
    if a.golden:
        _golden(a.golden, reps=a.reps)
        return 0
    if a.selftest:
        gym_root(verbose=True)
        task = LdoTask(a.fam, budget=3, seed=1)
        env = ExtLdoEnv(task, verbose=True)
        print(f"ldo {task.fam}: d={env.dim} sizable vars, tier={task.tier}")
        print(f"  harness: {env.harness()['ngspice_version']}, "
              f"sha={_PINNED_SHA[:12]}")
        x0 = env.arena.encode({n: task.defaults[n] for n in task.names})
        out = env.evaluate(params=x0)
        print(f"  default-sizing eval: obj={out['objective']:.4f} "
              f"feasible={out['feasible']}")
        print("  " + env.spec.report(out["metrics"]))
        try:
            for _ in range(3):
                env.evaluate(params=x0)
            print("  BUDGET NOT ENFORCED -- bug")
            return 1
        except BudgetExhausted as e:
            print(f"  budget enforced: {e}")
        return 0
    ap.error("give --list, --selftest, or --golden FAM")


if __name__ == "__main__":
    sys.exit(main())
