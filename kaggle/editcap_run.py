"""editcap_run.py -- the GPU-leg driver for campaign qwen-editcap-v0
(pre-registration `kaggle/CAMPAIGN-QWEN-EDITCAP.md`).

Runs arm B (evidence edit) and/or arm C (blind-edit ablation) over the frozen
failure library `kaggle/editcap-lib/` (one cell per unsolved gf180 cell). The
SUBJECT is the MODEL: shown a failed sized circuit + its failure evidence, does
Qwen produce a STRUCTURAL fix that succeeds, and is looking at the failure
causally involved?  The sizer is the known-good tool, reused verbatim; this file
owns ONLY prompt assembly, the edit parse/validate/dedup, the smoke+size control
flow, and the verbatim adjudication archive.

    # on Kaggle, llama-server up on :8080 :
    python kaggle/editcap_run.py --lib kaggle/editcap-lib --out <dir> --arm both

    # on this box (no GPU): full downstream path, deterministic stub LLM:
    source env.sh && export LNA_DEPS_ROOT=$PWD
    python kaggle/editcap_run.py --lib kaggle/editcap-lib --out <dir> \
        --arm both --only cap-e02-gpsband --only cap-h02-gpsband --mock-llm

Reuse, not reimplementation (house rule): sizing is `driver.size_candidate`
(which loops `solve_spec.size_tokens` across seeds -- the SAME call arm B makes);
the netlist fence extraction is `driver.parse_completion`; edit validation is
`proposal.round_trip`. The sys.modules['campaign'] loader trick is lifted from
`kaggle/x0v1_run.py` so the loop's `campaign.py` (not lna/campaign.py) is used
for its `_worst_margin` helper. Nothing downstream is reimplemented.

BUDGETS (pre-reg, arm B/C per-edit grid, frozen):
  * conduction SMOKE : seeds=1 x budget=40  -- idd_ma must exceed 0.05 mA
  * base SIZE        : seeds=2 x budget=300  -- every edit that clears smoke
  * best-edit ESCAL  : seeds=3 x budget=600  -- ONLY the single best edit/cell

Outputs (checkpointed after EVERY cell -- a crash loses nothing already sized):
  <out>/results-<arm>.jsonl          one row per cell (rewritten each cell)
  <out>/adjudication/<spec>/<arm>/    VERBATIM archive (pre-reg hard requirement):
      prompt.txt          the exact rendered prompt shown to the model
      raw_output.txt      the raw model output, untruncated
      diagnosis.txt       the parsed diagnosis text (ARM B ONLY)
      edit<i>.net         the i-th proposed edit netlist (verbatim as parsed)
      edit<i>.meta.json   {wl_hash, predicted_delta_text, fence_outcome,
                           sized metrics/margins/feasible}
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# Bind $LNA_DEPS_ROOT on sys.path so the driver runs the WORKTREE's modules.
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(os.path.join(HERE, ".."))
LNA = os.path.join(ROOT, "lna")
LOOP = os.path.join(ROOT, "kaggle", "loop")
for _p in (LOOP, LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse the loop's campaign.py (for _worst_margin) + driver + proposal + Spec
# VERBATIM. `lna/campaign.py` shadows `kaggle/loop/campaign.py` by name on
# sys.path, so load THE LATTER by explicit file path and register it as
# `campaign` BEFORE driver.py's own `import` runs -- the x0v1_run.py trick.
import importlib.util as _ilu                                       # noqa: E402
_camp_path = os.path.join(LOOP, "campaign.py")
_spec = _ilu.spec_from_file_location("campaign", _camp_path)
C = _ilu.module_from_spec(_spec)
sys.modules["campaign"] = C
_spec.loader.exec_module(C)
import driver as D                                                  # noqa: E402
import proposal as P                                                # noqa: E402
from spec import Spec                                               # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "kaggle"))                   # editcap_annotate
import editcap_annotate as A                                        # noqa: E402

assert hasattr(C, "BASE") and C.__file__ == _camp_path, \
    "wrong campaign module loaded: %r" % getattr(C, "__file__", None)

# ---- pre-registered budget grid (frozen) -----------------------------------
SMOKE = dict(seeds=1, budget=40)      # conduction fence (idd > 0.05 mA)
BASE = dict(seeds=2, budget=300)      # every edit that clears smoke
ESCALATE = dict(seeds=3, budget=600)  # ONLY the single best edit per cell
IDD_FENCE_MA = 0.05                    # externals-v0 conduction lesson
S21_FENCE_DB = -30.0                   # v1 signal-path fence: any measurable
                                       # forward path (bias-branch idd alone let a
                                       # dead-signal edit clear the v0 fence --
                                       # ADJUDICATION.md "conduction fence passes
                                       # on TOTAL supply current"). Applied only
                                       # when the smoke best exposes s21_db.
K_EDITS = 3                            # pre-reg k=3 structural edits/cell

LADDER_DIR = os.path.join(ROOT, "kaggle", "specs-ladder")
# The library is a gf180 campaign (evidence.json pdk=gf180mcu); the ladder YAMLs
# carry a 45nm model path, so the process is a per-run OVERRIDE threaded into
# sizing, exactly as the loop-gpu kernel passes --pdk gf180mcu to campaign.py.
DEFAULT_PDK = "gf180mcu"


# ================================================================ LLM clients
class _MockLLM(object):
    """Deterministic stub (no server): returns a canned diagnosis + k VALID
    netlist edits DERIVED from the anchor, each adding one legal device (an R or
    C on a legal existing net) so the FULL downstream path (parse -> round_trip
    -> WL-dedup -> smoke -> base size -> escalate -> archive) is exercised end to
    end. No GPU, no network; byte-reproducible per (anchor, arm, k).

    The edits are the anchor with one device appended:
      edit0: + C Cadd VOUT1 VSS   (output shunt cap -- changes WL, conducts)
      edit1: + R Radd VOUT1 VSS   (output shunt resistor)
      edit2: + C Cadd2 VIN1 VSS   (input shunt cap)
    These are legal proposal-dialect lines on reserved nets, guaranteed distinct
    from the anchor WL hash and from each other, and size on real ngspice.

    For round r>1 (arm F/EF verify-refine), a STRUCTURALLY distinct set is used
    (shunts to VDD / a series R into the output) so the round-2 edits survive the
    WL-dedup-vs-all-prior-edits and exercise the round-2 base-size path too. (WL
    hashes are graph-structural, so merely renaming a device does not dedup-clear;
    the nets themselves must differ round to round.)"""

    _ADDS = [
        "C Cadd VOUT1 VSS",
        "R Radd VOUT1 VSS",
        "C Cadd2 VIN1 VSS",
    ]
    # round 2+: distinct nets (VDD-side shunts + a series R) so the graphs differ.
    _ADDS_R2 = [
        "C Cadd VOUT1 VDD",
        "R Radd VIN1 VDD",
        "C Cadd2 VIN1 VOUT1",
    ]

    def __init__(self, k=K_EDITS):
        self.k = k

    def _diagnosis(self):
        return ("DIAGNOSIS (mock stub): the binding constraint is the input "
                "match; the anchor presents a poor real part at the source, so "
                "s11 sits well above target. Each variant below perturbs the "
                "loading to probe whether added structure moves the match.")

    def complete_edit(self, anchor_net, arm, round_no=1):
        """Return (raw_output_text, diagnosis_or_None, [edit_texts]).

        Evidence arms (B/E/F/EF) include a worded diagnosis; the blind control C
        omits it (matches the prompts). `round_no` perturbs the appended devices
        so round-2 mock edits DIFFER from round-1 (WL-dedup vs prior rounds is
        then exercised end to end).

        The raw text places each edit's prediction AFTER its fence (the observed
        live format -- see the archived raw_output.txt), so the predicted-text
        association fix is exercised on realistic layout."""
        edits = []
        adds = self._ADDS_R2 if round_no > 1 else self._ADDS
        for i in range(self.k):
            add = adds[i % len(adds)]
            edits.append(anchor_net.rstrip("\n") + "\n" + add + "\n")
        diag = self._diagnosis() if arm != "C" else None
        # Render a raw output that LOOKS like a real model reply, so the archived
        # raw_output.txt exercises the SAME parse path a live reply would.
        parts = []
        if diag:
            parts.append(diag + "\n")
        for i, e in enumerate(edits):
            pred = ("PREDICTED for the binding metric: s11_db improves "
                    "(more negative) by ~2 dB." if arm != "C"
                    else "variant %d." % i)
            # fence FIRST, prediction AFTER (matches observed live layout).
            parts.append("```netlist\n%s```\n\n%s\n" % (e, pred))
        return "\n".join(parts), diag, edits


def _parse_edits_from_raw(raw_text):
    """Extract up to many fenced netlist edits from a raw model reply, reusing
    the loop's fence regex. `driver.parse_completion` returns only the FIRST
    fenced block; an editcap reply carries k of them, so we iterate the loop's
    own `_NETLIST_RE` over the text and clean each block the same way
    parse_completion cleans the single one (drop a bare language-tag first line).
    Returns a list of netlist strings in document order."""
    out = []
    for m in D._NETLIST_RE.finditer(raw_text):
        nl = m.group(1).strip("\n")
        first, _, rest = nl.partition("\n")
        if first.strip().lower() in ("netlist", "spice", "text"):
            nl = rest.strip("\n")
        if nl.strip():
            out.append(nl)
    return out


class _LiveLLM(object):
    """Wraps the loop's ChatClient for ONE editcap completion per cell per arm.

    One request, k edits parsed from the single reply (the pre-reg asks the model
    to emit exactly k=3 edits in one turn). Diagnosis (arm B) is the prose before
    the first fence, captured verbatim."""

    def __init__(self, base_url, model="local", k=K_EDITS,
                 temperature=0.7, max_tokens=3072):
        self.client = D.ChatClient(base_url, model=model)
        self.model = model
        self.k = k
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete_edit(self, prompt_messages, arm):
        """Return (raw_output_text, diagnosis_or_None, [edit_texts]).

        Raises driver.LLMError on transport/HTTP failure (the caller turns it
        into a recorded structural failure for the cell)."""
        resp = self.client.complete(prompt_messages, temperature=self.temperature,
                                    max_tokens=self.max_tokens, n=1)
        ch = (resp.get("choices") or [{}])[0]
        content = (ch.get("message") or {}).get("content", "") or ""
        edits = _parse_edits_from_raw(content)[:self.k]
        # diagnosis (evidence arms B/E/F/EF) = everything before the first fence,
        # trimmed. The blind control C requests no diagnosis, so none is parsed.
        diag = None
        if arm != "C":
            fence = content.find("```")
            diag = (content[:fence] if fence >= 0 else content).strip() or None
        return content, diag, edits


# ================================================================ prompting
SYSTEM = (
    "You are an analog IC designer repairing a low-noise amplifier (LNA) that "
    "FAILED its specification after full SPICE sizing. You reason about the "
    "failure and propose STRUCTURAL (topology) changes. You output TOPOLOGY ONLY "
    "as a small line-oriented netlist; a downstream deterministic tool inserts "
    "biasing and sizes every device with a SPICE optimizer. Never invent device "
    "values, DC sources, or bias networks -- only the connectivity."
)

DIALECT = (
    "NETLIST DIALECT (obey exactly, one device per line):\n"
    "  TYPE name node1 node2 [node3 node4]\n"
    "  TYPE in {NMOS, PMOS, R, C, L}.\n"
    "  NMOS/PMOS take 4 nodes in order D G S B; R/C/L take 2 nodes P N.\n"
    "  Nets: VIN1 (input), VOUT1 (output), VDD, VSS (ground); any internal node "
    "name otherwise. NO device values. NO V sources. NO bias networks."
)


def _spec_constraint_block(spec):
    """Render the spec's gated constraints (min/max) from the lna Spec object --
    the single source of truth the sizer itself uses. No physaudit data."""
    lines = ["=== SPEC (%s) ===" % spec.name]
    desc = getattr(spec, "description", None) or (spec.raw or {}).get("description")
    if desc:
        lines.append("description: %s" % desc)
    band = getattr(spec, "band_type", None)
    f0 = (spec.raw or {}).get("band", {}).get("f0")
    if f0:
        lines.append("band: %s, f0=%s Hz" % (band, f0))
    lines.append("gated constraints:")
    for name, c in (spec.constraints or {}).items():
        status = c.get("status")
        if status == "unsupported":
            continue  # iip3 is declared unsupported -- not a gate, omit
        bits = []
        if c.get("min") is not None:
            bits.append("min %s" % c["min"])
        if c.get("max") is not None:
            bits.append("max %s" % c["max"])
        lines.append("  %-10s %s" % (name, " / ".join(bits) if bits else "(soft)"))
    return "\n".join(lines)


def _evidence_block(ev):
    """Render the failure evidence (arm B ONLY) from evidence.json VERBATIM in
    content: sized-best metrics, per-constraint margins, the binding constraint,
    Idd headroom vs cap, total evals. NO physaudit (frozen evidence-content
    rule)."""
    lines = ["=== FAILURE EVIDENCE (this circuit was sized and MISSED) ==="]
    wm = ev.get("worst_margin")
    if wm:
        lines.append("binding (worst) constraint: %s  margin=%.6g (normalized; "
                     "negative == failing)" % (wm[0], wm[1]))
    lines.append("feasible: %s   total sizing evals spent: %s"
                 % (ev.get("feasible"), ev.get("total_evals")))
    lines.append("")
    lines.append("per-constraint margins (achieved vs gate, normalized margin):")
    lines.append("  %-10s %-14s %-14s %s" % ("metric", "achieved", "margin",
                                             "supported"))
    for name, m in (ev.get("margins") or {}).items():
        ach = m.get("achieved")
        mar = m.get("margin")
        lines.append("  %-10s %-14s %-14s %s" % (
            name,
            ("%.6g" % ach) if isinstance(ach, (int, float)) else "-",
            ("%.6g" % mar) if isinstance(mar, (int, float)) else "-",
            m.get("supported")))
    # Idd headroom vs cap -- derived from the margin (margin>=0 == within cap).
    idd = (ev.get("margins") or {}).get("idd_ma") or {}
    if idd.get("achieved") is not None:
        lines.append("")
        lines.append("Idd: achieved %.6g mA (normalized margin %s vs the "
                     "idd_ma cap; negative == over budget)."
                     % (idd["achieved"], idd.get("margin")))
    lines.append("")
    lines.append("full sized-best metrics (verbatim):")
    lines.append(json.dumps(ev.get("metrics") or {}, indent=2))
    return "\n".join(lines)


def _instructions_B(k):
    return (
        "YOUR TASK (arm B):\n"
        "1. DIAGNOSE the failure in words: what is physically limiting the "
        "binding constraint in the circuit above?\n"
        "2. Propose EXACTLY %d STRUCTURAL edits as FULL netlists in the dialect "
        "below. Each edit is a complete netlist (not a diff), each structurally "
        "DIFFERENT from the anchor and from the other edits.\n"
        "3. After EACH edit, state a PREDICTED direction AND magnitude for the "
        "binding metric (e.g. 's11_db improves by ~3 dB').\n\n"
        "Emit each edit in its OWN fenced ```netlist block.\n\n%s"
        % (k, DIALECT))


def _instructions_C(k):
    return (
        "YOUR TASK:\n"
        "Propose EXACTLY %d STRUCTURAL variants of the circuit above as FULL "
        "netlists in the dialect below. Each variant is a complete netlist (not "
        "a diff), each structurally DIFFERENT from the starting circuit and from "
        "the other variants.\n\n"
        "Emit each variant in its OWN fenced ```netlist block.\n\n%s"
        % (k, DIALECT))


# ---- arm taxonomy (v1): B,C,E,F,EF ----------------------------------------
# E = B + annotation; F = B + rounds 2; EF = both. C stays the blind control
# (no annotation, no rounds -- enforced in main()). All non-C arms are
# "evidence" arms (same evidence package as B); the arm string only toggles the
# annotate/rounds capabilities layered on top of B's prompt.
def _arm_has_evidence(arm):
    return arm != "C"


def _arm_annotates(arm):
    return arm in ("E", "EF")


def _arm_rounds(arm):
    """True if the arm letter implies a verify-refine second round (F / EF)."""
    return arm in ("F", "EF")


def _annotation_block(anchor_net):
    """The arm-E annotation, rendered from the SAME anchor text the model sees.

    Wrapped in neutral section headers by editcap_annotate itself. A leading
    banner labels it as machine-derived so the model does not mistake it for
    additional spec content."""
    body = A.annotate(anchor_net)
    return ("=== STRUCTURAL ANNOTATION (auto-derived from the netlist graph "
            "above; facts only) ===\n" + body)


def build_prompt_B(spec, anchor_net, ev, k=K_EDITS, annotate=False):
    """Arm B (and E/F/EF) prompt: spec constraints + anchor netlist VERBATIM +
    (optional) structural annotation + failure evidence + diagnose-then-k-edits
    instructions. Returns (messages, prompt_text).

    `annotate=False` reproduces v0 byte-for-byte; `annotate=True` (arm E/EF)
    inserts the auto-derived GRAPH FACTS block between the anchor and the
    evidence (targets the measured comprehension failures)."""
    anno = ("%s\n\n" % _annotation_block(anchor_net)) if annotate else ""
    user = (
        "%s\n\n"
        "=== ANCHOR NETLIST (the failed circuit, dialect form) ===\n"
        "```netlist\n%s```\n\n"
        "%s"
        "%s\n\n"
        "%s"
    ) % (_spec_constraint_block(spec), anchor_net.rstrip("\n") + "\n",
         anno, _evidence_block(ev), _instructions_B(k))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user}]
    return messages, SYSTEM + "\n\n" + user


def build_prompt_C(spec, anchor_net, k=K_EDITS):
    """Arm C prompt: IDENTICAL to B minus ALL evidence (no metrics/margins, no
    diagnosis request -- just spec + anchor + 'propose k structural variants').
    The blind control stays blind: no annotation, no rounds (arm C never sets
    them). Returns (messages, prompt_text)."""
    user = (
        "%s\n\n"
        "=== ANCHOR NETLIST (starting circuit, dialect form) ===\n"
        "```netlist\n%s```\n\n"
        "%s"
    ) % (_spec_constraint_block(spec), anchor_net.rstrip("\n") + "\n",
         _instructions_C(k))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user}]
    return messages, SYSTEM + "\n\n" + user


# ================================================================ sizing steps
def _smoke_idd(tokens, spec_ref, pdk):
    """40-eval conduction smoke (seeds=1 x budget=40). Returns (best_idd_ma_or_None,
    best_result_or_None). A dead edit (idd <= 0.05 mA or unsizable) is a failed
    proposal per the externals-v0 fence."""
    best, _secs, _ = D.size_candidate(tokens, spec_ref, SMOKE["seeds"],
                                      SMOKE["budget"], pdk=pdk)
    if best is None:
        return None, None
    idd = (best.get("metrics") or {}).get("idd_ma")
    return (idd if isinstance(idd, (int, float)) else None), best


def _fence_eval(idd, smoke_best, fence_s21):
    """Decide the conduction fence from the smoke best. Returns (passed, detail).

    v0 fence: idd > IDD_FENCE_MA (bias-branch current). v1 signal-path fence
    (`fence_s21`, default ON): ALSO require the smoke best's s21_db > S21_FENCE_DB
    -- any measurable forward path -- to reject dead-signal edits that the bias
    branch alone floated past the v0 fence (ADJUDICATION.md). If the smoke metrics
    lack s21_db, the s21 gate is skipped (fence falls back to idd-only), recorded
    as s21=None. `detail` is archived into the edit meta + result row."""
    metrics = (smoke_best or {}).get("metrics") or {}
    s21 = metrics.get("s21_db")
    s21 = s21 if isinstance(s21, (int, float)) else None
    idd_ok = isinstance(idd, (int, float)) and idd > IDD_FENCE_MA
    s21_ok = True
    s21_applied = bool(fence_s21) and s21 is not None
    if s21_applied:
        s21_ok = s21 > S21_FENCE_DB
    passed = bool(idd_ok and s21_ok)
    detail = {
        "passed": passed,
        "idd_ma": idd if isinstance(idd, (int, float)) else None,
        "idd_ok": idd_ok,
        "idd_floor_ma": IDD_FENCE_MA,
        "s21_db": s21,
        "s21_ok": s21_ok,
        "s21_applied": s21_applied,
        "s21_floor_db": S21_FENCE_DB if s21_applied else None,
        "fence_s21_flag": bool(fence_s21),
    }
    return passed, detail


def _size_at(tokens, spec_ref, cfg, pdk):
    """Size one edit at cfg (seeds x budget) via the loop's size_candidate.
    Returns a compact sized dict (or None if unsizable)."""
    best, secs, _ = D.size_candidate(tokens, spec_ref, cfg["seeds"],
                                     cfg["budget"], pdk=pdk)
    if best is None:
        return None
    margins = best.get("margins") or {}
    return {
        "feasible": bool(best["feasible"]),
        "best_obj": best.get("best_obj"),
        "metrics": best.get("metrics"),
        "margins": margins,
        "worst_margin": C._worst_margin(margins),
        "seed": best.get("seed"),
        "seconds": secs,
        "evals": cfg["seeds"] * cfg["budget"],
        "sim_health": {"n_evals": best.get("sh_n_evals"),
                       "n_sim_fail": best.get("sh_n_sim_fail"),
                       "sim_error": best.get("sh_sim_error")},
    }


# ================================================================ adjudication io
def _adj_dir(out_dir, spec_name, arm):
    d = os.path.join(out_dir, "adjudication", spec_name, arm)
    os.makedirs(d, exist_ok=True)
    return d


def _write_verbatim(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text if text is not None else "")
        fh.flush()
        os.fsync(fh.fileno())


def _margins_compact(margins):
    """Campaign-shaped compact margins (achieved/margin/supported only)."""
    return {k: {kk: m.get(kk) for kk in ("achieved", "margin", "supported")}
            for k, m in (margins or {}).items()}


# ---- round-2 prompt (arm F/EF verify-refine) -------------------------------
def _measured_results_block(round_no, edit_summaries):
    """Render the VERBATIM measured results for one round's edits, for the next
    round's prompt: per edit, its WL hash, fence outcome, and (if sized) the
    sized metrics, per-constraint margins, and worst margin. This is the model's
    own round-1 attempts + what the deterministic sizer actually measured -- the
    feedback the verify-refine loop is built to consume."""
    lines = ["=== MEASURED RESULTS OF YOUR ROUND %d EDITS ===" % round_no]
    for s in edit_summaries:
        i = s.get("index")
        lines.append("")
        lines.append("--- your edit %d ---" % i)
        lines.append("WL hash: %s" % (s.get("wl_hash") or "(unparseable)"))
        lines.append("outcome: %s" % s.get("fence_outcome"))
        if s.get("error"):
            lines.append("parse/round-trip error: %s" % s["error"])
        if s.get("fence_detail"):
            fd = s["fence_detail"]
            lines.append("conduction fence: idd=%s mA (floor %s), s21=%s dB%s -> %s"
                         % (fd.get("idd_ma"), fd.get("idd_floor_ma"),
                            fd.get("s21_db"),
                            (" (floor %s)" % fd.get("s21_floor_db"))
                            if fd.get("s21_applied") else " (s21 gate off)",
                            "PASS" if fd.get("passed") else "FAIL"))
        sm = s.get("sized_metrics")
        if sm is not None:
            lines.append("sized: feasible=%s  worst_margin=%s"
                         % (s.get("sized_feasible"), s.get("worst_margin")))
            lines.append("sized metrics (verbatim): %s"
                         % json.dumps(sm, default=float))
            if s.get("sized_margins"):
                lines.append("per-constraint margins: %s"
                             % json.dumps(s["sized_margins"], default=float))
    return "\n".join(lines)


def _instructions_round2(k):
    return (
        "YOUR TASK (round 2 -- verify and refine):\n"
        "Above are your round-1 edits and EXACTLY what the deterministic sizer "
        "measured for each. Using ONLY those measured outcomes, propose EXACTLY "
        "%d NEW structural edits: you may iterate on whichever round-1 edit did "
        "best, or change course entirely. Each edit is a complete netlist (not a "
        "diff), structurally DIFFERENT from the anchor, from every round-1 edit, "
        "and from the other round-2 edits.\n"
        "After EACH edit, state a PREDICTED direction AND magnitude for the "
        "binding metric.\n\n"
        "Emit each edit in its OWN fenced ```netlist block.\n\n%s"
        % (k, DIALECT))


def build_prompt_round2(base_prompt_text, round_no, prev_edit_summaries, k=K_EDITS):
    """Round-r prompt = the ORIGINAL round-1 prompt content (spec + anchor +
    [annotation] + evidence) with the round-1 instruction block replaced by the
    VERBATIM measured results + the verify-refine instruction. Returns
    (messages, prompt_text). The original content is reused verbatim by prefixing
    it (minus its trailing task block would over-engineer; instead we append the
    measured-results feedback and a fresh task -- the model re-reads its own prior
    task above and now sees the outcomes)."""
    results = _measured_results_block(round_no - 1, prev_edit_summaries)
    user = "%s\n\n%s\n\n%s" % (base_prompt_text, results, _instructions_round2(k))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user}]
    return messages, user


# ================================================================ per-cell run
def _process_round(adj_round, edit_texts, raw_output, seen_wl, spec_ref, pdk,
                   fence_s21, round_no=1):
    """Parse/validate/dedup/fence/base-size one round of edit texts.

    Archives edit<i>.net + edit<i>.meta.json into `adj_round` (VERBATIM). Mutates
    `seen_wl` (dedup vs anchor + ALL prior rounds' edits). Returns
    (edit_summaries, sized_edits) where sized_edits carries (index, tokens, meta,
    sized, adj_round) for each edit that cleared the fence and base-sized -- the
    escalation candidates. The predicted-delta text is associated with each edit's
    FOLLOWING prose (the v0 off-by-one fix)."""
    edit_summaries = []
    sized_edits = []
    pred_texts = _predicted_texts(raw_output, len(edit_texts))

    for i, etext in enumerate(edit_texts):
        meta = {"index": i, "round": round_no,
                "predicted_delta_text": pred_texts[i],
                "wl_hash": None, "valid": False, "dup": False,
                "fence_outcome": None, "fence_detail": None, "sized": None,
                "error": None}
        _write_verbatim(os.path.join(adj_round, "edit%d.net" % i), etext)

        info = P.round_trip(etext)
        meta["wl_hash"] = info.get("wl_hash")
        if not info["ok"]:
            meta["error"] = info.get("error") or "round-trip failed"
            meta["fence_outcome"] = "parse_fail"
            _write_verbatim(os.path.join(adj_round, "edit%d.meta.json" % i),
                            json.dumps(meta, indent=2, default=float))
            edit_summaries.append(_edit_summary(meta))
            continue
        meta["valid"] = True
        wl = info["wl_hash"]
        if wl in seen_wl:
            meta["dup"] = True
            meta["fence_outcome"] = "dup_skip"
            _write_verbatim(os.path.join(adj_round, "edit%d.meta.json" % i),
                            json.dumps(meta, indent=2, default=float))
            edit_summaries.append(_edit_summary(meta))
            continue
        seen_wl.add(wl)
        tokens = info["tokens"]

        # -- 40-eval conduction smoke + signal-path fence --
        idd, smoke_best = _smoke_idd(tokens, spec_ref, pdk)
        meta["smoke_idd_ma"] = idd
        passed, fence_detail = _fence_eval(idd, smoke_best, fence_s21)
        meta["fence_detail"] = fence_detail
        if not passed:
            meta["fence_outcome"] = "fence_fail"   # dead / no-signal -- not resized
            _write_verbatim(os.path.join(adj_round, "edit%d.meta.json" % i),
                            json.dumps(meta, indent=2, default=float))
            edit_summaries.append(_edit_summary(meta))
            continue

        # -- base size (2 x 300) --
        sized = _size_at(tokens, spec_ref, BASE, pdk)
        meta["fence_outcome"] = "smoke_pass"
        meta["sized"] = sized
        _write_verbatim(os.path.join(adj_round, "edit%d.meta.json" % i),
                        json.dumps(meta, indent=2, default=float))
        edit_summaries.append(_edit_summary(meta))
        if sized is not None:
            sized_edits.append((i, tokens, meta, sized, adj_round))
    return edit_summaries, sized_edits


def run_cell(cell_name, cell_dir, arm, llm, out_dir, pdk, rounds=1,
             fence_s21=True, annotate=None):
    """Run ONE cell for ONE arm end to end. Returns (row_dict, n_valid_edits).

    Control flow (pre-reg, v1):
      build prompt -> one LLM completion -> parse k edits (loop fence regex)
      -> validate each via proposal.round_trip -> WL-dedup vs anchor and ALL
      prior-round edits -> per VALID edit: 40-eval smoke + signal-path fence
      (idd>0.05 AND s21>-30 when measurable, `fence_s21`); fail -> not resized;
      pass -> base-size (2x300). With --rounds N>1 (arm F/EF), a verify-refine
      round embeds the VERBATIM measured round-1 results and asks for k NEW edits
      (same parse/dedup/fence/base-size path). After the FINAL round, escalate
      ONLY the overall best base-sized edit (3x600), as v0. Archives VERBATIM.

    Archive layout: rounds==1 keeps the FLAT v0 layout
    (adjudication/<spec>/<arm>/{prompt,raw_output,diagnosis,edit<i>.*}); rounds>1
    uses per-round subdirs adjudication/<spec>/<arm>/round<r>/{...}."""
    anchor_net = open(os.path.join(cell_dir, "anchor.net"), encoding="utf-8").read()
    ev = json.load(open(os.path.join(cell_dir, "evidence.json"), encoding="utf-8"))

    spec_path = os.path.join(LADDER_DIR, cell_name + ".yaml")
    spec = Spec.load(spec_path)
    spec_ref = spec_path

    anchor_wl = ev.get("wl_hash")
    anchor_worst = ev.get("worst_margin")
    has_evidence = _arm_has_evidence(arm)
    # annotate: explicit override (main derives it from arm + --annotate); when
    # None, fall back to the arm letter. The blind control C is NEVER annotated
    # and NEVER runs extra rounds, whatever the flags say.
    if annotate is None:
        annotate = _arm_annotates(arm)
    if arm == "C":
        annotate = False
        rounds = 1

    adj = _adj_dir(out_dir, cell_name, arm)
    # rounds==1 -> flat v0 layout (byte-identical archive paths); rounds>1 ->
    # per-round subdirs. round_dir(r) picks the right directory for round r.
    def round_dir(r):
        if rounds <= 1:
            return adj
        d = os.path.join(adj, "round%d" % r)
        os.makedirs(d, exist_ok=True)
        return d

    # ---- round 1 prompt (v0 path when annotate off) --------------------------
    if has_evidence:
        messages, prompt_text = build_prompt_B(spec, anchor_net, ev, K_EDITS,
                                               annotate=annotate)
    else:
        messages, prompt_text = build_prompt_C(spec, anchor_net, K_EDITS)

    seen_wl = {anchor_wl} if anchor_wl else set()
    all_summaries = []       # every proposed edit across rounds (with round tag)
    all_sized = []           # escalation candidates across ALL rounds
    llm_error = None
    diagnosis_r1 = None
    base_prompt_text = prompt_text   # reused verbatim for the round-2 prompt

    for r in range(1, rounds + 1):
        rdir = round_dir(r)
        if r == 1:
            msgs, ptext = messages, prompt_text
        else:
            msgs, ptext = build_prompt_round2(base_prompt_text, r,
                                              prev_summaries, K_EDITS)
        _write_verbatim(os.path.join(rdir, "prompt.txt"), ptext)

        diagnosis = None
        raw_output = ""
        edit_texts = []
        try:
            if isinstance(llm, _MockLLM):
                raw_output, diagnosis, edit_texts = llm.complete_edit(
                    anchor_net, arm, round_no=r)
            else:
                raw_output, diagnosis, edit_texts = llm.complete_edit(msgs, arm)
        except D.LLMError as e:                                     # transport/HTTP
            llm_error = str(e)
            raw_output = "LLM ERROR: %s" % llm_error

        _write_verbatim(os.path.join(rdir, "raw_output.txt"), raw_output)
        if has_evidence:
            _write_verbatim(os.path.join(rdir, "diagnosis.txt"), diagnosis or "")
        if r == 1:
            diagnosis_r1 = diagnosis

        summaries, sized = _process_round(rdir, edit_texts, raw_output, seen_wl,
                                          spec_ref, pdk, fence_s21, round_no=r)
        all_summaries.extend(summaries)     # each already tagged with its round
        all_sized.extend(sized)
        prev_summaries = summaries

    # ---- escalate ONLY the overall best base-sized edit across rounds (3x600) -
    best_entry = None
    if all_sized:
        def _key(entry):
            s = entry[3]
            wm = s.get("worst_margin")
            wm_v = wm[1] if (wm and isinstance(wm[1], (int, float))) else -1e9
            obj = s.get("best_obj")
            obj = obj if isinstance(obj, (int, float)) else float("inf")
            return (0 if s.get("feasible") else 1, -wm_v, obj)
        all_sized.sort(key=_key)
        best_entry = all_sized[0]
        bi, btokens, bmeta, bbase, bdir = best_entry
        esc = _size_at(btokens, spec_ref, ESCALATE, pdk)
        bmeta["escalated"] = True
        bmeta["sized_escalated"] = esc
        # re-archive the best edit's meta with the escalation result folded in.
        _write_verbatim(os.path.join(bdir, "edit%d.meta.json" % bi),
                        json.dumps(bmeta, indent=2, default=float))
        best_sized = esc if esc is not None else bbase
    else:
        best_sized = None

    # ---- build the results row -----------------------------------------------
    best_feasible = bool((best_sized or {}).get("feasible"))
    best_worst = (best_sized or {}).get("worst_margin")
    binding_delta = _binding_delta(anchor_worst, best_sized)

    n_valid = sum(1 for m in all_summaries if m.get("valid") and not m.get("dup"))
    n_smoke_pass = sum(1 for m in all_summaries
                       if m.get("fence_outcome") == "smoke_pass")
    row = {
        "spec": cell_name,
        "arm": arm,
        "pdk": pdk,
        "anchor_wl": anchor_wl,
        "anchor_wl12": (anchor_wl or "")[:12] or None,
        "anchor_worst_margin": anchor_worst,
        "bucket": ev.get("bucket") or _bucket_of(cell_name),
        "llm_error": llm_error,
        "rounds": rounds,
        "annotate": annotate,
        "fence_s21": bool(fence_s21),
        "fence_config": {"idd_floor_ma": IDD_FENCE_MA,
                         "s21_floor_db": S21_FENCE_DB, "s21_gate": bool(fence_s21)},
        "n_edits_proposed": len(all_summaries),
        "n_edits_valid": n_valid,
        "n_edits_smoke_pass": n_smoke_pass,
        "edits": all_summaries,
        "best_edit_index": (best_entry[0] if best_entry else None),
        "best_edit_wl": (best_entry[2].get("wl_hash") if best_entry else None),
        "best_edit_round": (best_entry[2].get("round") if best_entry else None),
        "best_edit_feasible": best_feasible,
        "best_edit_worst_margin": best_worst,
        "best_edit_metrics": (best_sized or {}).get("metrics"),
        "best_edit_margins": _margins_compact((best_sized or {}).get("margins")),
        "best_edit_escalated": bool(best_entry),
        "feasible": best_feasible,
        "binding_margin_delta_vs_anchor": binding_delta,
        "budgets": {"smoke": SMOKE, "base": BASE, "escalate": ESCALATE,
                    "k": K_EDITS},
        "ts": time.time(),
    }
    return row, n_valid


def _predicted_texts(raw_output, n):
    """Associate each edit with the prose that FOLLOWS its fenced netlist block --
    the model's predicted-delta text is stated AFTER each edit (observed live
    format: fence, then "Prediction: ...").

    v0 BUGFIX (logged in ADJUDICATION.md "predicted_delta_text is misaligned by
    one block; holds the PREVIOUS edit's prediction; last prediction dropped"):
    v0 used segs[i] (the prose BEFORE fence i), which for the fence-then-prediction
    layout shifted every prediction back by one and dropped the last. The split
    yields segs of length (#fences + 1) where segs[j] is the prose after fence
    j-1 / before fence j; edit i's FOLLOWING prose is therefore segs[i+1]. Any
    leading diagnosis prose lands in segs[0] and is correctly NOT assigned to an
    edit. Falls back to None where a segment is absent."""
    import re as _re
    segs = _re.split(r"```(?:netlist|spice|text)?\s*\n.*?```", raw_output,
                     flags=_re.DOTALL | _re.IGNORECASE)
    out = []
    for i in range(n):
        j = i + 1                       # the segment AFTER edit i's fence
        out.append((segs[j].strip() if j < len(segs) else "") or None)
    return out


def _edit_summary(meta):
    """Compact per-edit row for results.jsonl + round-2 feedback (mirrors the
    archived meta). Carries the round tag, the fence detail (idd + s21 gate), and
    the sized metrics/margins the verify-refine prompt shows back to the model."""
    s = meta.get("sized") or {}
    return {
        "index": meta.get("index"),
        "round": meta.get("round"),
        "wl_hash": meta.get("wl_hash"),
        "wl12": (meta.get("wl_hash") or "")[:12] or None,
        "valid": meta.get("valid"),
        "dup": meta.get("dup"),
        "fence_outcome": meta.get("fence_outcome"),
        "fence_detail": meta.get("fence_detail"),
        "smoke_idd_ma": meta.get("smoke_idd_ma"),
        "feasible": s.get("feasible"),
        "sized_feasible": s.get("feasible"),
        "worst_margin": s.get("worst_margin"),
        "sized_metrics": s.get("metrics"),
        "sized_margins": _margins_compact(s.get("margins")) if s else None,
        "predicted_delta_text": meta.get("predicted_delta_text"),
        "error": meta.get("error"),
    }


def _binding_delta(anchor_worst, best_sized):
    """Binding-margin delta vs the anchor's worst_margin (from evidence.json).

    Pre-reg scoring wants the improvement on the binding constraint. Prefer the
    SAME metric the anchor bound on (look it up in the edit's margins); fall back
    to the edit's own worst-margin value. Returns a dict for auditability."""
    if not (anchor_worst and isinstance(anchor_worst[1], (int, float))):
        return None
    a_metric, a_val = anchor_worst[0], anchor_worst[1]
    out = {"anchor_metric": a_metric, "anchor_margin": a_val,
           "edit_margin_same_metric": None, "edit_worst_margin": None,
           "delta_same_metric": None}
    if best_sized:
        m = (best_sized.get("margins") or {}).get(a_metric) or {}
        em = m.get("margin")
        if isinstance(em, (int, float)):
            out["edit_margin_same_metric"] = em
            out["delta_same_metric"] = em - a_val
        wm = best_sized.get("worst_margin")
        if wm and isinstance(wm[1], (int, float)):
            out["edit_worst_margin"] = {"metric": wm[0], "margin": wm[1]}
    return out


# --------- bucket lookup (from INDEX.json, falls back to evidence) -----------
_INDEX = None


def _load_index(lib_dir):
    global _INDEX
    if _INDEX is None:
        p = os.path.join(lib_dir, "INDEX.json")
        _INDEX = json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else {}
    return _INDEX


def _bucket_of(cell_name):
    idx = _INDEX or {}
    cells = (idx.get("cells") or {})
    return (cells.get(cell_name) or {}).get("bucket")


# ================================================================ checkpoint io
def _checkpoint(out_dir, arm, rows):
    """Rewrite results-<arm>.jsonl after EVERY cell (fsync -- a crash loses
    nothing already sized), mirroring the house fsync-checkpoint discipline."""
    os.makedirs(out_dir, exist_ok=True)
    jl = os.path.join(out_dir, "results-%s.jsonl" % arm)
    with open(jl, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


# ================================================================ main
def _cells_in_lib(lib_dir, only):
    idx = _load_index(lib_dir)
    names = list((idx.get("cells") or {}).keys())
    if not names:
        # fall back to scanning for cell dirs that hold the 3 library files.
        for n in sorted(os.listdir(lib_dir)):
            d = os.path.join(lib_dir, n)
            if (os.path.isdir(d)
                    and os.path.isfile(os.path.join(d, "anchor.net"))
                    and os.path.isfile(os.path.join(d, "evidence.json"))):
                names.append(n)
    if only:
        want = set(only)
        names = [n for n in names if n in want]
    return names


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", default=os.path.join(ROOT, "kaggle", "editcap-lib"),
                    help="the failure library dir (kaggle/editcap-lib)")
    ap.add_argument("--out", required=True, help="output dir for this run")
    ap.add_argument("--arm", default="both",
                    help="which arm(s) to run: B, C, E (=B+annotate), "
                         "F (=B+rounds2), EF (=both), or 'both' (=B,C, v0 "
                         "default). Comma-separated lists accepted (e.g. B,C,E).")
    ap.add_argument("--only", action="append",
                    help="restrict to these cell/spec names (repeatable)")
    ap.add_argument("--annotate", action="store_true",
                    help="arm E: prepend a deterministic, purely-structural "
                         "annotation block (graph facts) after the anchor "
                         "netlist. Forced ON for arms E/EF; never for C.")
    ap.add_argument("--rounds", type=int, default=1,
                    help="arm F: number of verify-refine rounds (>=1). Forced to "
                         "at least 2 for arms F/EF; never >1 for C. Default 1 "
                         "(=v0 single completion).")
    _fence = ap.add_mutually_exclusive_group()
    _fence.add_argument("--fence-s21", dest="fence_s21", action="store_true",
                        default=True,
                        help="signal-path fence (default ON for v1): the "
                             "conduction smoke must ALSO show s21_db > -30 dB "
                             "when measurable, not just idd > 0.05 mA.")
    _fence.add_argument("--no-fence-s21", dest="fence_s21", action="store_false",
                        help="disable the s21 signal-path fence (idd-only, v0 "
                             "conduction behaviour).")
    ap.add_argument("--mock-llm", action="store_true",
                    help="no server: deterministic stub returns a canned "
                         "diagnosis + k valid netlist edits derived from the "
                         "anchor (exercises the FULL downstream path)")
    ap.add_argument("--llm-url", default="http://127.0.0.1:8080/v1",
                    help="OpenAI-compatible endpoint (llama-server), loop convention")
    ap.add_argument("--model", default="local", help="model id sent to the server")
    ap.add_argument("--pdk", default=DEFAULT_PDK,
                    help="process override threaded into sizing (library is "
                         "gf180mcu; the ladder YAMLs carry a 45nm model path)")
    ap.add_argument("--k", type=int, default=K_EDITS,
                    help="structural edits per cell (pre-reg k=3)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=3072)
    args = ap.parse_args(argv)

    lib_dir = os.path.abspath(args.lib)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isdir(lib_dir):
        sys.exit("editcap: FATAL -- library dir missing: %s" % lib_dir)
    names = _cells_in_lib(lib_dir, args.only)
    if not names:
        sys.exit("editcap: FATAL -- no cells found in %s%s"
                 % (lib_dir, (" matching --only %s" % args.only) if args.only
                    else ""))

    # arm taxonomy (v1): 'both' == B,C (v0 default preserved byte-for-byte).
    # Accept a single arm or a comma-separated list; validate against B/C/E/F/EF.
    _VALID_ARMS = ("B", "C", "E", "F", "EF")
    if args.arm == "both":
        arms = ["B", "C"]
    else:
        arms = [a.strip() for a in args.arm.split(",") if a.strip()]
    bad = [a for a in arms if a not in _VALID_ARMS]
    if bad:
        sys.exit("editcap: FATAL -- unknown arm(s) %s (choose from %s or 'both')"
                 % (bad, ", ".join(_VALID_ARMS)))

    # per-arm effective capabilities: arm letter forces the capability on; the
    # explicit --annotate / --rounds flags can ALSO turn them on for arm B; C
    # stays blind always (enforced again in run_cell).
    def _eff_annotate(arm):
        return arm != "C" and (_arm_annotates(arm) or args.annotate)

    def _eff_rounds(arm):
        if arm == "C":
            return 1
        want = 2 if _arm_rounds(arm) else 1
        return max(want, args.rounds)

    # one LLM client reused across cells/arms; mock is per-cell deterministic.
    if args.mock_llm:
        llm = _MockLLM(k=args.k)
    else:
        llm = _LiveLLM(args.llm_url, model=args.model, k=args.k,
                       temperature=args.temperature, max_tokens=args.max_tokens)

    print("editcap: lib=%s out=%s arms=%s cells=%d pdk=%s fence_s21=%s mode=%s"
          % (lib_dir, out_dir, arms, len(names), args.pdk, args.fence_s21,
             "mock" if args.mock_llm else ("live %s" % args.llm_url)),
          flush=True)

    # k is per-run (pre-reg default 3); thread it through the module global so
    # the prompt builders and run_cell (which read K_EDITS) use the chosen k.
    globals()["K_EDITS"] = args.k

    total_valid = 0          # parseable+non-dup edits across ALL cells/arms
    for arm in arms:
        rows = []
        eff_annotate = _eff_annotate(arm)
        eff_rounds = _eff_rounds(arm)
        for i, name in enumerate(names):
            cell_dir = os.path.join(lib_dir, name)
            if not os.path.isdir(cell_dir):
                sys.exit("editcap: FATAL -- cell dir missing: %s" % cell_dir)
            print("\n[arm %s] [%d/%d] %s  pdk=%s annotate=%s rounds=%d"
                  % (arm, i + 1, len(names), name, args.pdk, eff_annotate,
                     eff_rounds), flush=True)
            t0 = time.time()
            row, n_valid = run_cell(name, cell_dir, arm, llm, out_dir, args.pdk,
                                    rounds=eff_rounds, fence_s21=args.fence_s21,
                                    annotate=eff_annotate)
            total_valid += n_valid
            rows.append(row)
            _checkpoint(out_dir, arm, rows)          # durable after EVERY cell
            dt = time.time() - t0
            bd = row.get("binding_margin_delta_vs_anchor") or {}
            print("    -> proposed=%d valid=%d smoke_pass=%d best_feasible=%s "
                  "binding_delta=%s  (%.1f min)"
                  % (row["n_edits_proposed"], row["n_edits_valid"],
                     row["n_edits_smoke_pass"], row["feasible"],
                     (("%.4g" % bd["delta_same_metric"])
                      if isinstance(bd.get("delta_same_metric"), (int, float))
                      else "-"), dt / 60), flush=True)

    if total_valid == 0:
        sys.exit("editcap: STRUCTURAL FAILURE -- zero parseable/non-dup edits "
                 "across ALL cells and arms (nonzero exit per pre-reg)")

    print("\neditcap done: arms=%s cells=%d total_valid_edits=%d  out=%s"
          % (arms, len(names), total_valid, out_dir), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
