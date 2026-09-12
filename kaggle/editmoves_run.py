"""editmoves_run.py -- the SELECTION-vs-RANDOM driver for campaign editmoves-v0
(user-commissioned 2026-09-12). Modeled on kaggle/editcap_run.py: SAME sizing
recipe, SAME conduction+signal-path fence, SAME verbatim adjudication archive,
SAME fsync-checkpoint discipline. What differs is WHAT the LLM does: the model no
longer authors netlists (qwen-editcap-v0 proved it cannot do so reliably -- see
kaggle/campaigns/qwen-editcap-v0/ADJUDICATION.md). Instead, every candidate edit
is produced by a VALID-BY-CONSTRUCTION move from kaggle/editmoves.py; the model
only SELECTS which (move, site) to apply.

    # arm R (RANDOM null; runs on THIS box, no LLM):
    source env.sh && export LNA_DEPS_ROOT=$PWD
    python kaggle/editmoves_run.py --lib kaggle/editcap-lib --out DIR \
        --arm R --k 3 --seed 12345 --pdk gf180mcu \
        --only cap-e02-gpsband --only cap-m07-gpsband

    # arm M (LLM selects from the menu):
    python kaggle/editmoves_run.py --lib kaggle/editcap-lib --out DIR \
        --arm M --k 3 --seed 12345 --pdk gf180mcu --llm-url http://127.0.0.1:8080/v1
    # arm M dry path on the box (no server): stub picks the first k menu items:
    python kaggle/editmoves_run.py --lib ... --out DIR --arm M --mock-llm ...

TWO ARMS (the experiment's core contrast):
  * Arm R -- RANDOM null. Per cell a SEEDED RNG (seed = --seed XOR cell-index hash;
    NEVER wall-clock) picks k=3 distinct applicable (move, site) pairs uniformly;
    applies them; then the editcap sizing chain VERBATIM (smoke fence -> base size
    -> escalate best). This is the "structural diversity, no reasoning" baseline.
  * Arm M -- LLM SELECTS. The prompt carries the spec constraints, the anchor
    netlist, the editcap ANNOTATION block, the failure evidence (identical content
    to editcap arm B), and a MENU: a numbered list of every applicable (move, site)
    with a one-line NEUTRAL mechanical description (no benefit claims). The model
    must reply DIAGNOSIS FIRST, then exactly k=3 "PICK <n>: <rationale> | predicted
    <metric> <direction ~magnitude>" lines. Invalid picks are logged + skipped.

Reuse (house rule): sizing is `driver.size_candidate`; edit validation is
`proposal.round_trip`; the loop's `campaign.py` supplies `_worst_margin` via the
x0v1_run.py sys.modules trick. Budgets/fence match editcap_run.py byte-for-byte.
This file owns ONLY move sampling / menu assembly / pick parsing and the
adjudication archive; nothing downstream is reimplemented.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(os.path.join(HERE, ".."))
LNA = os.path.join(ROOT, "lna")
LOOP = os.path.join(ROOT, "kaggle", "loop")
for _p in (LOOP, LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# load kaggle/loop/campaign.py as `campaign` BEFORE driver imports it (the
# x0v1_run.py / editcap_run.py trick: lna/campaign.py otherwise shadows it).
import importlib.util as _ilu                                       # noqa: E402
_camp_path = os.path.join(LOOP, "campaign.py")
_spec = _ilu.spec_from_file_location("campaign", _camp_path)
C = _ilu.module_from_spec(_spec)
sys.modules["campaign"] = C
_spec.loader.exec_module(C)
import driver as D                                                  # noqa: E402
import proposal as P                                                # noqa: E402
from spec import Spec                                               # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "kaggle"))
import editcap_annotate as ANN                                      # noqa: E402
import editmoves as EM                                              # noqa: E402

assert hasattr(C, "BASE") and C.__file__ == _camp_path, \
    "wrong campaign module loaded: %r" % getattr(C, "__file__", None)

# ---- budget grid (frozen; byte-identical to editcap_run.py) ----------------
SMOKE = dict(seeds=1, budget=40)      # conduction fence (idd > 0.05 mA)
BASE = dict(seeds=2, budget=300)      # every edit that clears smoke
ESCALATE = dict(seeds=3, budget=600)  # ONLY the single best edit per cell
IDD_FENCE_MA = 0.05                    # externals-v0 conduction lesson
S21_FENCE_DB = -30.0                   # signal-path fence (editcap v1)
K_MOVES = 3                            # pre-reg k=3 selections/cell

LADDER_DIR = os.path.join(ROOT, "kaggle", "specs-ladder")
DEFAULT_PDK = "gf180mcu"


# ================================================================ move sampling
def _cell_seed(base_seed, cell_name):
    """Deterministic per-cell seed derived from --seed + the cell name (NEVER
    wall-clock). A stable 8-byte digest of the name is XORed into the base seed so
    each cell gets an independent-but-reproducible RNG stream."""
    h = hashlib.sha256(cell_name.encode("utf-8")).digest()
    return (int(base_seed) ^ int.from_bytes(h[:8], "big")) & 0xFFFFFFFFFFFFFFFF


def _sample_random_picks(rows, k, rng):
    """Pick k distinct applicable (move, site) entries uniformly from the FULL
    applicable set of the ANCHOR (single-shot selection over the anchor's menu, so
    arm R and arm M draw from the SAME universe). Returns the chosen entries in
    the order sampled. If fewer than k sites exist, returns all of them."""
    entries = EM.enumerate_sites(rows)
    if not entries:
        return []
    idxs = list(range(len(entries)))
    rng.shuffle(idxs)
    chosen = idxs[:k]
    return [entries[i] for i in chosen]


# ================================================================ menu / prompt
SYSTEM = (
    "You are an analog IC designer repairing a low-noise amplifier (LNA) that "
    "FAILED its specification after full SPICE sizing. You do NOT write netlists. "
    "A library of VALID structural edits is offered as a numbered MENU; you SELECT "
    "which edits to apply. A downstream deterministic tool applies the selected "
    "edit, inserts biasing, and sizes every device with a SPICE optimizer."
)


def _spec_constraint_block(spec):
    """Render the spec's gated constraints (min/max) -- identical shape to
    editcap_run._spec_constraint_block (the sizer's own source of truth)."""
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
        if c.get("status") == "unsupported":
            continue
        bits = []
        if c.get("min") is not None:
            bits.append("min %s" % c["min"])
        if c.get("max") is not None:
            bits.append("max %s" % c["max"])
        lines.append("  %-10s %s" % (name, " / ".join(bits) if bits else "(soft)"))
    return "\n".join(lines)


def _evidence_block(ev):
    """Render the failure evidence -- SAME content as editcap arm B (metrics,
    per-constraint margins, binding constraint, Idd headroom, full metrics). NO
    physaudit (frozen evidence-content rule)."""
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
    idd = (ev.get("margins") or {}).get("idd_ma") or {}
    if idd.get("achieved") is not None:
        lines.append("")
        lines.append("Idd: achieved %.6g mA (normalized margin %s vs the idd_ma "
                     "cap; negative == over budget)."
                     % (idd["achieved"], idd.get("margin")))
    lines.append("")
    lines.append("full sized-best metrics (verbatim):")
    lines.append(json.dumps(ev.get("metrics") or {}, indent=2))
    return "\n".join(lines)


def _annotation_block(anchor_net):
    """editcap arm-B/E annotation (deterministic graph facts) rendered from the
    SAME anchor text the model sees."""
    return ("=== STRUCTURAL ANNOTATION (auto-derived from the netlist graph "
            "above; facts only) ===\n" + ANN.annotate(anchor_net))


def build_menu(rows):
    """Enumerate every applicable (move, site) for the anchor and render the
    numbered MENU. Returns (entries, menu_text) where entries[i] corresponds to
    menu number i (1-based in the text). Each line is the move's own NEUTRAL
    mechanical description -- NO benefit claims (the arm-M menu rule)."""
    entries = EM.enumerate_sites(rows)
    lines = ["=== MENU: applicable structural edits (SELECT by number) ==="]
    for i, e in enumerate(entries, 1):
        lines.append("%2d. %s" % (i, e["describe"]))
    return entries, "\n".join(lines)


def _instructions_M(k):
    return (
        "YOUR TASK:\n"
        "1. On the FIRST line, output your diagnosis, starting literally with "
        "\"DIAGNOSIS:\" -- what is physically limiting the binding constraint in "
        "the circuit above?\n"
        "2. Then output EXACTLY %d selections from the MENU, one per line, each in "
        "this exact format:\n"
        "   PICK <number>: <one-line rationale> | predicted <metric> <direction "
        "~magnitude>\n"
        "   (e.g. 'PICK 4: adds a cascode to raise output impedance | predicted "
        "s21_db up ~2 dB'). Choose %d DISTINCT menu numbers." % (k, k))


def build_prompt_M(spec, anchor_net, ev, menu_text, k=K_MOVES):
    """Arm-M prompt: spec constraints + anchor netlist + annotation + failure
    evidence + the MENU + diagnosis-then-k-picks instructions. Returns
    (messages, prompt_text)."""
    user = (
        "%s\n\n"
        "=== ANCHOR NETLIST (the failed circuit, dialect form) ===\n"
        "```netlist\n%s```\n\n"
        "%s\n\n"
        "%s\n\n"
        "%s\n\n"
        "%s"
    ) % (_spec_constraint_block(spec), anchor_net.rstrip("\n") + "\n",
         _annotation_block(anchor_net), _evidence_block(ev), menu_text,
         _instructions_M(k))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user}]
    return messages, SYSTEM + "\n\n" + user


# ================================================================ pick parsing
_PICK_RE = re.compile(r"^\s*PICK\s+(\d+)\s*:\s*(.*)$", re.IGNORECASE)
_DIAG_RE = re.compile(r"DIAGNOSIS\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)


def parse_picks(raw_text, n_menu, k):
    """Robustly parse the model reply -> (diagnosis, picks).

    diagnosis: the text after the first 'DIAGNOSIS:' up to the first PICK line
      (None if absent -- schema violation, logged).
    picks: list of {menu_index (0-based), menu_number (1-based), rationale,
      raw_line, valid, reason}. A pick is INVALID (logged + skipped downstream) if
      its number is out of [1, n_menu] or duplicates an earlier accepted pick. At
      most k valid picks are kept (extras beyond k are marked valid=False,
      reason='beyond_k')."""
    lines = raw_text.splitlines()
    # diagnosis: from the first DIAGNOSIS: marker to the first PICK line
    diagnosis = None
    diag_start = None
    for i, ln in enumerate(lines):
        if re.match(r"\s*DIAGNOSIS\s*:", ln, re.IGNORECASE):
            diag_start = i
            break
    if diag_start is not None:
        collected = []
        for ln in lines[diag_start:]:
            if _PICK_RE.match(ln):
                break
            collected.append(ln)
        diagnosis = "\n".join(collected).strip() or None   # kept verbatim

    picks = []
    seen_nums = set()
    n_valid = 0
    for ln in lines:
        m = _PICK_RE.match(ln)
        if not m:
            continue
        num = int(m.group(1))
        rationale = m.group(2).strip()
        pk = {"menu_number": num, "menu_index": num - 1, "rationale": rationale,
              "raw_line": ln.strip(), "valid": False, "reason": None}
        if num < 1 or num > n_menu:
            pk["reason"] = "out_of_range(1..%d)" % n_menu
        elif num in seen_nums:
            pk["reason"] = "duplicate"
        elif n_valid >= k:
            pk["reason"] = "beyond_k"
        else:
            pk["valid"] = True
            seen_nums.add(num)
            n_valid += 1
        picks.append(pk)
    return diagnosis, picks


# ================================================================ LLM clients
class _MockLLM(object):
    """Deterministic stub (no server): picks the FIRST k menu items with a canned
    diagnosis + canned rationale, so the FULL arm-M path (menu -> parse -> apply ->
    round_trip -> smoke -> base size -> escalate -> archive) runs on the box."""

    def __init__(self, k=K_MOVES):
        self.k = k

    def complete_select(self, prompt_messages, n_menu):
        k = min(self.k, n_menu)
        parts = ["DIAGNOSIS: (mock stub) the binding constraint is the input "
                 "match; the anchor presents a poor real part at the source, so "
                 "the reflection sits above target. The first few structural "
                 "edits below perturb the loading to probe the match."]
        for i in range(1, k + 1):
            parts.append("PICK %d: mock rationale for menu item %d | predicted "
                         "s11_db down ~2 dB" % (i, i))
        return "\n".join(parts)


class _LiveLLM(object):
    """Wraps the loop's ChatClient for ONE selection completion per cell."""

    def __init__(self, base_url, model="local", temperature=0.7, max_tokens=2048):
        self.client = D.ChatClient(base_url, model=model)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete_select(self, prompt_messages, n_menu):
        resp = self.client.complete(prompt_messages, temperature=self.temperature,
                                    max_tokens=self.max_tokens, n=1)
        ch = (resp.get("choices") or [{}])[0]
        return (ch.get("message") or {}).get("content", "") or ""


# ================================================================ sizing steps
def _smoke_idd(tokens, spec_ref, pdk):
    best, _secs, _ = D.size_candidate(tokens, spec_ref, SMOKE["seeds"],
                                      SMOKE["budget"], pdk=pdk)
    if best is None:
        return None, None
    idd = (best.get("metrics") or {}).get("idd_ma")
    return (idd if isinstance(idd, (int, float)) else None), best


def _fence_eval(idd, smoke_best, fence_s21):
    """Conduction + signal-path fence (byte-identical to editcap_run)."""
    metrics = (smoke_best or {}).get("metrics") or {}
    s21 = metrics.get("s21_db")
    s21 = s21 if isinstance(s21, (int, float)) else None
    idd_ok = isinstance(idd, (int, float)) and idd > IDD_FENCE_MA
    s21_ok = True
    s21_applied = bool(fence_s21) and s21 is not None
    if s21_applied:
        s21_ok = s21 > S21_FENCE_DB
    passed = bool(idd_ok and s21_ok)
    detail = {"passed": passed, "idd_ma": idd if isinstance(idd, (int, float))
              else None, "idd_ok": idd_ok, "idd_floor_ma": IDD_FENCE_MA,
              "s21_db": s21, "s21_ok": s21_ok, "s21_applied": s21_applied,
              "s21_floor_db": S21_FENCE_DB if s21_applied else None,
              "fence_s21_flag": bool(fence_s21)}
    return passed, detail


def _size_at(tokens, spec_ref, cfg, pdk):
    best, secs, _ = D.size_candidate(tokens, spec_ref, cfg["seeds"], cfg["budget"],
                                     pdk=pdk)
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
    return {k: {kk: m.get(kk) for kk in ("achieved", "margin", "supported")}
            for k, m in (margins or {}).items()}


def _binding_delta(anchor_worst, best_sized):
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


# ================================================================ per-edit apply+size
def _apply_and_size(entry, anchor_rows, anchor_wl, seen_wl, spec_ref, pdk,
                    fence_s21):
    """Apply ONE move entry to the anchor rows, validate, fence, base-size.

    Returns a compact edit dict (archived + summarized). The move is
    valid-by-construction, but we STILL run the four editmoves invariants + the
    round_trip as a hard gate (defence in depth), then the editcap smoke/fence/
    base-size chain. `seen_wl` is mutated for dedup vs anchor + prior edits."""
    edit = {"move_name": entry["name"], "site": entry["site"],
            "menu_desc": entry["describe"], "wl_hash": None, "valid": False,
            "dup": False, "invariants_ok": None, "invariant_detail": None,
            "fence_outcome": None, "fence_detail": None, "smoke_idd_ma": None,
            "sized": None, "netlist": None, "error": None}

    new_rows, moved_gates = EM.apply_move(anchor_rows, entry)
    net_text = P.rows_to_text(new_rows)
    edit["netlist"] = net_text

    # hard invariant gate (valid-by-construction, but verified) --------------
    inv_ok, inv_detail = EM.check_invariants(anchor_rows, new_rows, moved_gates)
    edit["invariants_ok"] = inv_ok
    edit["invariant_detail"] = inv_detail

    info = P.round_trip(net_text)
    edit["wl_hash"] = info.get("wl_hash")
    if not info["ok"]:
        edit["error"] = info.get("error") or "round-trip failed"
        edit["fence_outcome"] = "parse_fail"
        return edit
    edit["valid"] = True
    wl = info["wl_hash"]
    if wl in seen_wl:
        edit["dup"] = True
        edit["fence_outcome"] = "dup_skip"
        return edit
    seen_wl.add(wl)
    tokens = info["tokens"]

    idd, smoke_best = _smoke_idd(tokens, spec_ref, pdk)
    edit["smoke_idd_ma"] = idd
    passed, fence_detail = _fence_eval(idd, smoke_best, fence_s21)
    edit["fence_detail"] = fence_detail
    if not passed:
        edit["fence_outcome"] = "fence_fail"
        return edit

    sized = _size_at(tokens, spec_ref, BASE, pdk)
    edit["fence_outcome"] = "smoke_pass"
    edit["sized"] = sized
    edit["_tokens"] = tokens         # kept for escalation; stripped before archive
    return edit


# ================================================================ per-cell run
def run_cell(cell_name, cell_dir, arm, llm, out_dir, pdk, base_seed, k=K_MOVES,
             fence_s21=True):
    """Run ONE cell for ONE arm (R or M) end to end. Returns (row, n_valid)."""
    anchor_net = open(os.path.join(cell_dir, "anchor.net"), encoding="utf-8").read()
    ev = json.load(open(os.path.join(cell_dir, "evidence.json"), encoding="utf-8"))
    anchor_rows, _ports = P.parse(anchor_net)

    spec_path = os.path.join(LADDER_DIR, cell_name + ".yaml")
    spec = Spec.load(spec_path)
    spec_ref = spec_path

    anchor_wl = ev.get("wl_hash")
    anchor_worst = ev.get("worst_margin")
    adj = _adj_dir(out_dir, cell_name, arm)

    entries, menu_text = build_menu(anchor_rows)

    # ---- select the k (move, site) entries for this arm --------------------
    diagnosis = None
    picks = None
    raw_output = None
    prompt_text = None
    llm_error = None
    chosen = []

    if arm == "R":
        rng = random.Random(_cell_seed(base_seed, cell_name))
        chosen = _sample_random_picks(anchor_rows, k, rng)
        # archive the RNG-selection record verbatim (the "prompt" analogue)
        sel_lines = ["=== ARM R (RANDOM null) selection ===",
                     "base_seed=%s  cell_seed=%d  k=%d  n_applicable=%d"
                     % (base_seed, _cell_seed(base_seed, cell_name), k,
                        len(entries))]
        for e in chosen:
            sel_lines.append("chose: %s  site=%s" % (e["name"], e["site"]))
        _write_verbatim(os.path.join(adj, "selection.txt"),
                        "\n".join(sel_lines) + "\n\n" + menu_text)
    else:  # arm M
        messages, prompt_text = build_prompt_M(spec, anchor_net, ev, menu_text, k)
        _write_verbatim(os.path.join(adj, "prompt.txt"), prompt_text)
        try:
            raw_output = llm.complete_select(messages, len(entries))
        except D.LLMError as e:
            llm_error = str(e)
            raw_output = "LLM ERROR: %s" % llm_error
        _write_verbatim(os.path.join(adj, "raw_output.txt"), raw_output)
        diagnosis, picks = parse_picks(raw_output, len(entries), k)
        _write_verbatim(os.path.join(adj, "diagnosis.txt"), diagnosis or "")
        _write_verbatim(os.path.join(adj, "picks.json"),
                        json.dumps(picks, indent=2, default=float))
        # map the VALID picks to menu entries (invalid picks logged, skipped)
        for pk in picks:
            if pk["valid"]:
                chosen.append(entries[pk["menu_index"]])

    # ---- apply + fence + base-size each chosen edit ------------------------
    seen_wl = {anchor_wl} if anchor_wl else set()
    edits = []
    sized_edits = []
    for j, entry in enumerate(chosen):
        edit = _apply_and_size(entry, anchor_rows, anchor_wl, seen_wl, spec_ref,
                               pdk, fence_s21)
        edit["index"] = j
        # archive the edit netlist + meta VERBATIM
        _write_verbatim(os.path.join(adj, "edit%d.net" % j), edit.get("netlist") or "")
        meta = {kk: vv for kk, vv in edit.items() if kk != "_tokens"}
        _write_verbatim(os.path.join(adj, "edit%d.meta.json" % j),
                        json.dumps(meta, indent=2, default=float))
        if edit.get("_tokens") is not None and edit.get("sized") is not None:
            sized_edits.append((j, edit["_tokens"], edit))
        edits.append(edit)

    # ---- escalate ONLY the overall best base-sized edit (3x600) ------------
    best_entry = None
    best_sized = None
    if sized_edits:
        def _key(t):
            s = t[2]["sized"]
            wm = s.get("worst_margin")
            wm_v = wm[1] if (wm and isinstance(wm[1], (int, float))) else -1e9
            obj = s.get("best_obj")
            obj = obj if isinstance(obj, (int, float)) else float("inf")
            return (0 if s.get("feasible") else 1, -wm_v, obj)
        sized_edits.sort(key=_key)
        best_entry = sized_edits[0]
        bi, btokens, bedit = best_entry
        esc = _size_at(btokens, spec_ref, ESCALATE, pdk)
        bedit["escalated"] = True
        bedit["sized_escalated"] = esc
        meta = {kk: vv for kk, vv in bedit.items() if kk != "_tokens"}
        _write_verbatim(os.path.join(adj, "edit%d.meta.json" % bi),
                        json.dumps(meta, indent=2, default=float))
        best_sized = esc if esc is not None else bedit["sized"]

    # ---- strip the transient tokens before the results row ------------------
    for e in edits:
        e.pop("_tokens", None)
        e.pop("netlist", None)     # netlist archived to edit<i>.net; keep row small

    best_feasible = bool((best_sized or {}).get("feasible"))
    best_worst = (best_sized or {}).get("worst_margin")
    binding_delta = _binding_delta(anchor_worst, best_sized)
    n_valid = sum(1 for e in edits if e.get("valid") and not e.get("dup"))
    n_smoke_pass = sum(1 for e in edits if e.get("fence_outcome") == "smoke_pass")
    n_invalid_picks = (sum(1 for p in (picks or []) if not p["valid"])
                       if arm == "M" else 0)

    row = {
        "spec": cell_name,
        "arm": arm,
        "pdk": pdk,
        "anchor_wl": anchor_wl,
        "anchor_wl12": (anchor_wl or "")[:12] or None,
        "anchor_worst_margin": anchor_worst,
        "bucket": ev.get("bucket") or _bucket_of(cell_name),
        "base_seed": base_seed,
        "cell_seed": _cell_seed(base_seed, cell_name) if arm == "R" else None,
        "n_applicable_sites": len(entries),
        "llm_error": llm_error,
        "diagnosis_present": bool(diagnosis) if arm == "M" else None,
        "n_picks_parsed": (len(picks) if picks is not None else None),
        "n_picks_invalid": n_invalid_picks,
        "k": k,
        "fence_s21": bool(fence_s21),
        "fence_config": {"idd_floor_ma": IDD_FENCE_MA,
                         "s21_floor_db": S21_FENCE_DB, "s21_gate": bool(fence_s21)},
        "n_edits_applied": len(edits),
        "n_edits_valid": n_valid,
        "n_edits_smoke_pass": n_smoke_pass,
        "edits": edits,
        "best_edit_index": (best_entry[0] if best_entry else None),
        "best_edit_move": (best_entry[2].get("move_name") if best_entry else None),
        "best_edit_wl": (best_entry[2].get("wl_hash") if best_entry else None),
        "best_edit_feasible": best_feasible,
        "best_edit_worst_margin": best_worst,
        "best_edit_metrics": (best_sized or {}).get("metrics"),
        "best_edit_margins": _margins_compact((best_sized or {}).get("margins")),
        "best_edit_escalated": bool(best_entry),
        "feasible": best_feasible,
        "binding_margin_delta_vs_anchor": binding_delta,
        "budgets": {"smoke": SMOKE, "base": BASE, "escalate": ESCALATE, "k": k},
        "ts": time.time(),
    }
    return row, n_valid


# --------- bucket lookup (INDEX.json, falls back to evidence) ----------------
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
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", default=os.path.join(ROOT, "kaggle", "editcap-lib"),
                    help="the failure library dir (kaggle/editcap-lib)")
    ap.add_argument("--out", required=True, help="output dir for this run")
    ap.add_argument("--arm", default="both",
                    help="R (random null, box), M (LLM selects), or 'both'. "
                         "Comma lists accepted (e.g. R,M).")
    ap.add_argument("--only", action="append",
                    help="restrict to these cell/spec names (repeatable)")
    ap.add_argument("--k", type=int, default=K_MOVES,
                    help="selections per cell (pre-reg k=3)")
    ap.add_argument("--seed", type=int, default=12345,
                    help="base seed for arm R's per-cell RNG (NEVER wall-clock)")
    _fence = ap.add_mutually_exclusive_group()
    _fence.add_argument("--fence-s21", dest="fence_s21", action="store_true",
                        default=True, help="signal-path fence (default ON): smoke "
                        "must ALSO show s21_db > -30 dB when measurable.")
    _fence.add_argument("--no-fence-s21", dest="fence_s21", action="store_false",
                        help="disable the s21 signal-path fence (idd-only).")
    ap.add_argument("--mock-llm", action="store_true",
                    help="arm M without a server: stub picks the first k menu items")
    ap.add_argument("--llm-url", default="http://127.0.0.1:8080/v1",
                    help="OpenAI-compatible endpoint (llama-server), loop convention")
    ap.add_argument("--model", default="local", help="model id sent to the server")
    ap.add_argument("--pdk", default=DEFAULT_PDK,
                    help="process override threaded into sizing (library is gf180mcu)")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2048)
    args = ap.parse_args(argv)

    lib_dir = os.path.abspath(args.lib)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isdir(lib_dir):
        sys.exit("editmoves: FATAL -- library dir missing: %s" % lib_dir)
    names = _cells_in_lib(lib_dir, args.only)
    if not names:
        sys.exit("editmoves: FATAL -- no cells found in %s%s"
                 % (lib_dir, (" matching --only %s" % args.only) if args.only
                    else ""))

    if args.arm == "both":
        arms = ["R", "M"]
    else:
        arms = [a.strip().upper() for a in args.arm.split(",") if a.strip()]
    bad = [a for a in arms if a not in ("R", "M")]
    if bad:
        sys.exit("editmoves: FATAL -- unknown arm(s) %s (choose R, M, or 'both')"
                 % bad)

    # arm M needs an LLM client; arm R runs on the box with no LLM.
    llm = None
    if "M" in arms:
        llm = (_MockLLM(k=args.k) if args.mock_llm
               else _LiveLLM(args.llm_url, model=args.model,
                             temperature=args.temperature,
                             max_tokens=args.max_tokens))

    print("editmoves: lib=%s out=%s arms=%s cells=%d pdk=%s k=%d seed=%d "
          "fence_s21=%s M-mode=%s"
          % (lib_dir, out_dir, arms, len(names), args.pdk, args.k, args.seed,
             args.fence_s21,
             ("n/a" if "M" not in arms else
              ("mock" if args.mock_llm else "live %s" % args.llm_url))),
          flush=True)

    globals()["K_MOVES"] = args.k

    total_valid = 0
    for arm in arms:
        rows = []
        for i, name in enumerate(names):
            cell_dir = os.path.join(lib_dir, name)
            if not os.path.isdir(cell_dir):
                sys.exit("editmoves: FATAL -- cell dir missing: %s" % cell_dir)
            print("\n[arm %s] [%d/%d] %s  pdk=%s" % (arm, i + 1, len(names), name,
                                                     args.pdk), flush=True)
            t0 = time.time()
            row, n_valid = run_cell(name, cell_dir, arm, llm, out_dir, args.pdk,
                                    args.seed, k=args.k, fence_s21=args.fence_s21)
            total_valid += n_valid
            rows.append(row)
            _checkpoint(out_dir, arm, rows)
            dt = time.time() - t0
            bd = row.get("binding_margin_delta_vs_anchor") or {}
            print("    -> applied=%d valid=%d smoke_pass=%d best_move=%s "
                  "best_feasible=%s binding_delta=%s  (%.1f min)"
                  % (row["n_edits_applied"], row["n_edits_valid"],
                     row["n_edits_smoke_pass"], row.get("best_edit_move"),
                     row["feasible"],
                     (("%.4g" % bd["delta_same_metric"])
                      if isinstance(bd.get("delta_same_metric"), (int, float))
                      else "-"), dt / 60), flush=True)

    if total_valid == 0:
        sys.exit("editmoves: STRUCTURAL FAILURE -- zero valid/non-dup edits across "
                 "ALL cells and arms (nonzero exit)")

    print("\neditmoves done: arms=%s cells=%d total_valid_edits=%d  out=%s"
          % (arms, len(names), total_valid, out_dir), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
