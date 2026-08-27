"""driver.py -- bounded LNA reasoning-loop v0 (Kaggle worker + local dry-run).

One spec in, a best sized design + a full trajectory log out. The LLM proposes and
edits topologies as proposal-format netlists (see netlist_format.md / proposal.py);
the deterministic repo funnel screens (L0), biases (L1), sizes (CMA-ES driving
ngspice, L2) and measures. Margins/diagnostics are fed back for ONE edit round.
Every phase appends a trajectory row conforming to
kaggle/schemas/trajectory.schema.json, checkpointed after each candidate so a
Kaggle session timeout loses nothing already measured.

    # on Kaggle, with llama-server up on :8080 :
    python kaggle/loop/driver.py --spec wifi24 --base-url http://127.0.0.1:8080/v1 \
        --k 3 --budget 200 --seeds 2

    # on this box (no GPU): full loop logic, canned LLM text, real sizing:
    source env.sh && export LNA_DEPS_ROOT=$PWD
    python kaggle/loop/driver.py --spec wifi24 --dry-run --budget 60 --seeds 1

    # structure-only (no ngspice): everything but the sizing sim:
    python kaggle/loop/driver.py --spec wifi24 --dry-run --no-sim

Reuse, not reimplementation (house rule): sizing is solve_spec.size_tokens
verbatim (which itself runs prepared_body -> bias.insert_bias -> make_objective ->
CMA-ES); screening is spec.structural_screen; margins are what size_tokens returns
(datastore.margins_for). This file owns ONLY: prompt assembly, the LLM client, the
parse of the model's output contract, the loop control flow, and trajectory I/O.

stdlib only in this file. The repo funnel it calls needs numpy/scipy/pyyaml
always and pandas for the proposal round-trip (build_lna_corpus shims); a missing
pandas is reported as a clear per-candidate error, not a crash.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import proposal as P                                            # noqa: E402

# --- resolve the repo clone (for lna/ imports + subprocess calls) ------------
ROOT = os.environ.get("LNA_DEPS_ROOT")
if not ROOT:
    # fall back to <repo>/ inferred from this file's location (…/kaggle/loop)
    ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LNA = os.path.join(ROOT, "lna")
for _p in (LNA, os.path.join(ROOT, "misc", "ZOAF")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

GATED_METRICS = ("nf_db", "s11_db", "s21_db", "idd_ma")   # the ones we ask about
SCHEMA_PHASES = ("consult", "propose", "roundtrip", "screen", "bias", "size",
                 "diagnose", "edit")


# ======================================================================= LLM
class LLMError(RuntimeError):
    """A live LLM call failed (transport or HTTP). Carries verbatim text."""


class ChatClient(object):
    """Thin OpenAI-compatible /v1/chat/completions client over stdlib urllib.

    base_url is e.g. http://127.0.0.1:8080/v1 (llama-server). `grammar` (a GBNF
    string) is passed through in the request body -- llama.cpp honours a top-level
    "grammar" field on the OpenAI-compatible route; harmless to other servers.
    """

    def __init__(self, base_url, model="local", timeout=600, grammar=None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.grammar = grammar

    def complete(self, messages, temperature=0.7, max_tokens=1024, n=1,
                 grammar=None):
        """Return a raw chat.completions response dict (may hold n choices).

        n>1 fans out as n sequential n=1 requests, choices merged: llama-server
        caps the OpenAI `n` field at its --parallel slot count (observed live:
        HTTP 400 "Field 'n': Value must be between 1 <= value <= 1, but got 2"),
        and sequential singles keep the full context window per request.
        """
        if n > 1:
            base, choices = None, []
            for _ in range(n):
                r = self.complete(messages, temperature=temperature,
                                  max_tokens=max_tokens, n=1, grammar=grammar)
                ch = dict(r["choices"][0])
                ch["index"] = len(choices)
                choices.append(ch)
                if base is None:
                    base = r
                else:
                    for k2 in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        try:
                            base["usage"][k2] += r.get("usage", {}).get(k2, 0)
                        except (KeyError, TypeError):
                            pass
            base["choices"] = choices
            return base
        body = {"model": self.model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens, "n": n}
        g = grammar if grammar is not None else self.grammar
        if g:
            body["grammar"] = g
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:                      # verbatim body
            detail = e.read().decode("utf-8", "replace")
            raise LLMError("HTTP %s from %s: %s"
                           % (e.code, self.base_url, detail))
        except urllib.error.URLError as e:
            raise LLMError("cannot reach %s: %s" % (self.base_url, e))


class DryRunClient(object):
    """Returns canned fixtures so the whole loop runs with no server/GPU.

    Phase is inferred from the last user message: an 'EDIT' marker -> edit.json,
    otherwise propose.json. Responses are popped in order and cycled if exhausted,
    so --k may exceed the fixture count.
    """

    def __init__(self, fixtures_dir):
        self._fix = {}
        for phase in ("propose", "edit"):
            p = os.path.join(fixtures_dir, phase + ".json")
            with open(p, encoding="utf-8") as fh:
                self._fix[phase] = json.load(fh)["responses"]
        self._cursor = {"propose": 0, "edit": 0}

    def complete(self, messages, temperature=0.7, max_tokens=1024, n=1,
                 grammar=None):
        last = messages[-1]["content"] if messages else ""
        phase = "edit" if "REVISE THE CIRCUIT" in last else "propose"
        pool = self._fix[phase]
        choices = []
        for _ in range(max(1, n)):
            resp = pool[self._cursor[phase] % len(pool)]
            self._cursor[phase] += 1
            choices.append(resp["choices"][0])
        for i, c in enumerate(choices):
            c = dict(c)
            c["index"] = i
            choices[i] = c
        base = dict(pool[0])
        base["choices"] = choices
        return base


# ===================================================== output-contract parser
_NETLIST_RE = re.compile(r"```(?:netlist|spice|text)?\s*\n(.*?)```",
                         re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_completion(content):
    """Split one model message into (netlist_text, rationale, predicted_deltas).

    Contract (see the propose prompt): a one-paragraph rationale, a fenced
    ```netlist block, and a fenced ```json block carrying
    {"predicted_deltas": {...}}. Degrades gracefully: if the model omitted a
    fence we still return what we can (netlist=None triggers a recorded parse
    failure downstream; deltas default to {}).
    """
    nl_m = _NETLIST_RE.search(content)
    if nl_m:
        netlist = nl_m.group(1).strip("\n")
    else:
        # last resort: strip any single fenced block that looks like device lines
        m = re.search(r"```\s*\n(.*?)```", content, re.DOTALL)
        netlist = m.group(1).strip("\n") if m else None
    if netlist:
        # observed live (loop-gpu v7): the model opens a BARE fence and puts the
        # language tag on its own first line -- drop it before parsing
        first, _, rest = netlist.partition("\n")
        if first.strip().lower() in ("netlist", "spice", "text"):
            netlist = rest.strip("\n")
    deltas = {}
    j_m = _JSON_RE.search(content)
    if j_m:
        try:
            obj = json.loads(j_m.group(1))
            deltas = obj.get("predicted_deltas", obj) if isinstance(obj, dict) else {}
        except Exception:
            deltas = {}
    # rationale = everything before the first fence, trimmed
    fence = content.find("```")
    rationale = (content[:fence] if fence >= 0 else content).strip()
    return netlist, rationale, deltas


# ============================================================ playbook consult
def consult_playbook(spec):
    """Run `python lna/playbook.py --consult --json` keyed on the spec's band +
    a few derived keywords. Returns (hits_list, argv, error_or_None).

    Never fatal: an empty or failed consult is a recorded gap, not a crash
    (playbook's own doctrine: 'no match is a gap in memory, not a licence to
    guess'). Keys chosen from spec fields only, so the query is reproducible.
    """
    band = spec.band_type
    kws = [band]
    if not spec.allow_inductorless:
        kws.append("inductor")
    else:
        kws.append("inductorless")
    for m in spec.constraints:
        kws.append(m.replace("_db", "").replace("_dbm", "").replace("_ma", ""))
    fam = "lna"
    argv = [sys.executable, os.path.join(LNA, "playbook.py"), "--consult",
            "--json", "--family", fam, "--keywords", ",".join(sorted(set(kws))),
            "--top", "5"]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, cwd=ROOT,
                             timeout=120)
    except Exception as e:
        return [], argv, "consult subprocess failed: %r" % (e,)
    if out.returncode != 0:
        return [], argv, (out.stderr or out.stdout or "").strip()
    try:
        hits = json.loads(out.stdout or "[]")
    except Exception as e:
        return [], argv, "consult JSON parse failed: %s; raw=%s" % (e, out.stdout)
    return hits, argv, None


# ================================================================== prompting
SYSTEM = (
    "You are an analog IC designer proposing low-noise amplifier (LNA) topologies "
    "for a 45nm CMOS process. You output TOPOLOGY ONLY as a small line-oriented "
    "netlist; a downstream deterministic tool inserts biasing and sizes every "
    "device with a SPICE optimizer. Never invent device values, DC sources, or "
    "bias networks -- only the connectivity."
)


def _exemplars():
    """A few committed exemplar netlists (proposal format) for the prompt.

    These are the same archetypes test_proposal.py round-trips WL-hash-exact; we
    read them from the fixtures' propose.json netlists is overkill, so we inline
    the two canonical ones here (CS-degen + CG) as text. Kept tiny on purpose.
    """
    return [
        ("inductively-degenerated common-source, tapped-C load",
         "C Cin VIN1 n1\nL Lg n1 n2\nNMOS M1 n4 n2 n3 VSS\nL Ls n3 VSS\n"
         "L Ld VDD n4\nC Ct1 n4 n5\nC Ct2 n5 VSS\nC Cout n5 VOUT1"),
        ("common-gate, shunt-L source match, resistive load",
         "C Cin VIN1 n1\nL Lin n1 VSS\nNMOS M1 n2 VDD n1 VSS\nR RL VDD n2\n"
         "C Cout n2 VOUT1"),
    ]


def _spec_yaml(spec):
    """The raw spec YAML text, for the prompt (single source of truth)."""
    try:
        with open(spec.source, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return json.dumps(spec.raw, indent=2)


def _consult_block(hits):
    if not hits:
        return "(no playbook rules matched this spec -- rely on fundamentals)"
    lines = []
    for h in hits:
        lines.append("- [%s | %s] %s" % (h.get("id"), h.get("confidence"),
                                         h.get("rule")))
        app = h.get("applicability") or {}
        if app.get("applies"):
            lines.append("    applies: %s" % app["applies"])
    return "\n".join(lines)


OUTPUT_CONTRACT = (
    "OUTPUT CONTRACT (obey exactly):\n"
    "1. One paragraph of rationale (why this topology suits the spec).\n"
    "2. A fenced code block tagged `netlist` with ONE device per line in the "
    "format `TYPE name node1 node2 [node3 node4]` where TYPE in {NMOS,PMOS,R,C,L}; "
    "NMOS/PMOS take 4 nodes D G S B, R/C/L take 2 nodes P N. Use nets VIN1 (input), "
    "VOUT1 (output), VDD, VSS/0 (ground), and any internal node names. Include "
    "both VIN1 and VOUT1 and at least one MOSFET; for a narrowband spec include "
    "at least one inductor. No bias sources or DC networks.\n"
    "3. A fenced code block tagged `json` with "
    "{\"predicted_deltas\": {\"nf_db\": <dB>, \"s11_db\": <dB>, \"s21_db\": <dB>, "
    "\"idd_ma\": <mA>}} -- your predicted absolute value for each gated metric."
)


def build_propose_prompt(spec, hits):
    ex = "\n\n".join("# %s\n%s" % (d, t) for d, t in _exemplars())
    user = (
        "Design an LNA for this spec.\n\n"
        "=== SPEC (%s) ===\n%s\n\n"
        "=== PLAYBOOK CONSULT (retrieved engineering memory) ===\n%s\n\n"
        "=== EXEMPLAR TOPOLOGIES (proposal format) ===\n%s\n\n"
        "%s"
    ) % (spec.name, _spec_yaml(spec), _consult_block(hits), ex, OUTPUT_CONTRACT)
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}]


def _margin_table(margins):
    if not margins:
        return "(no margins -- sizing produced no measured metrics)"
    rows = ["metric        achieved   req_min   req_max   margin(norm)  status"]
    for name, m in margins.items():
        ach = m.get("achieved")
        mar = m.get("margin")
        stat = ("UNSUPPORTED" if not m.get("supported")
                else "MISSING" if ach is None
                else "PASS" if (mar is not None and mar >= 0) else "FAIL")
        rows.append("%-13s %-10s %-9s %-9s %-13s %s" % (
            name,
            "%.4g" % ach if isinstance(ach, (int, float)) else "-",
            m.get("required_min") if m.get("required_min") is not None else "-",
            m.get("required_max") if m.get("required_max") is not None else "-",
            "%.4g" % mar if isinstance(mar, (int, float)) else "-",
            stat))
    return "\n".join(rows)


def build_edit_prompt(spec, hits, prev_netlist, sized, errors):
    margins = (sized or {}).get("margins") or {}
    metrics = (sized or {}).get("metrics") or {}
    err_block = ("\n".join("- %s" % e for e in errors) if errors
                 else "(no simulator/parser errors on the previous candidate)")
    user = (
        "REVISE THE CIRCUIT. Your previous topology was sized and measured; the "
        "margin table below is normalized slack (margin >= 0 means the constraint "
        "is met). Propose ONE edit that improves the binding (most negative "
        "margin) constraint without breaking the others.\n\n"
        "=== SPEC (%s) ===\n%s\n\n"
        "=== PREVIOUS NETLIST ===\n```netlist\n%s\n```\n\n"
        "=== MEASURED MARGINS ===\n%s\n\n"
        "=== RAW METRICS ===\n%s\n\n"
        "=== VERBATIM ERRORS (if any) ===\n%s\n\n"
        "%s\n\nFor predicted_deltas on an edit, give the expected CHANGE vs the "
        "previous candidate for each gated metric (signed)."
    ) % (spec.name, _spec_yaml(spec), prev_netlist, _margin_table(margins),
         json.dumps(metrics, indent=2), err_block, OUTPUT_CONTRACT)
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}]


# =============================================================== trajectory io
class Trajectory(object):
    """Append-only JSONL writer, one row per phase, flushed immediately."""

    def __init__(self, path, run_id, spec_name):
        self.path = path
        self.run_id = run_id
        self.spec = spec_name
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8", buffering=1)

    def row(self, iteration, phase, **fields):
        assert phase in SCHEMA_PHASES, "bad phase %r" % phase
        rec = {"run_id": self.run_id, "spec": self.spec,
               "iteration": int(iteration), "phase": phase, "ts": time.time()}
        rec.update({k: v for k, v in fields.items() if v is not None
                    or k in ("error_verbatim",)})   # keep explicit-None errors
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        return rec

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass


# ================================================================ funnel steps
def _lna_import(mod):
    return __import__(mod)


def screen_topology(spec, tokens):
    """spec.structural_screen on the parsed topology. Returns (passed, criteria)."""
    Topology = _lna_import("topology").Topology
    topo = Topology(list(tokens))
    passed, crit = spec.structural_screen(topo)
    return bool(passed), dict(crit)


def bias_probe(tokens, pdk=None):
    """Report whether the topology biases into a sizable two-port deck.

    A lightweight probe (bias.insert_bias with sweep) so bias_conducting is a
    first-class trajectory field. size_tokens re-derives this internally; the
    small double-cost buys a clean learning signal on biasability. Returns
    (conducting_bool, error_or_None).

    `pdk` (cross-PDK v0): None -> bptm45; a value threads the process rail into
    the probe so `bias_conducting` reflects the SAME rail the sizer will use
    (a 3.3 V gf180 gate biases differently from a 1.1 V bptm45 one)."""
    try:
        bias = _lna_import("bias")
        Topology = _lna_import("topology").Topology
        topo = Topology(list(tokens))
        nl, _ins, rep, _sw = bias.insert_bias(topo, sweep=True, pdk=pdk)
        if rep.get("skipped") or not nl.two_port:
            return False, "bias skipped: %s" % (rep.get("skipped") or "no two-port deck")
        return True, None
    except Exception as e:
        return False, "bias probe raised %s: %s" % (type(e).__name__, e)


def size_candidate(tokens, spec_ref, seeds, budget, pdk=None):
    """Reuse solve_spec.size_tokens across `seeds`, keep the best (feasible-first).

    Returns (best_result_or_None, seconds, total_evals). best_result is exactly
    solve_spec.size_tokens' dict {feasible,best_obj,best_params,metrics,margins,seed}.

    `pdk` (cross-PDK v0): None -> the spec's own pdk; a value is a per-run
    override threaded into size_tokens so the SAME spec sizes on any process."""
    solve = _lna_import("solve_spec")
    t0 = time.time()
    best = None
    for seed in range(1, seeds + 1):
        r = solve.size_tokens(list(tokens), spec_ref, seed, budget, pdk=pdk)
        if r is None:
            continue
        if best is None:
            best = r
        elif r["feasible"] and (not best["feasible"]
                                or r["best_obj"] < best["best_obj"]):
            best = r
        elif not best["feasible"] and r["best_obj"] < best["best_obj"]:
            best = r
    return best, round(time.time() - t0, 3), None


# =================================================================== the loop
def run_candidate(traj, spec, spec_ref, iteration, netlist_text, rationale,
                  deltas, model_id, usage, phase, no_sim, seeds, budget,
                  raw_completion=None, pdk=None):
    """Run one proposed/edited netlist through the full funnel, logging each phase.

    Returns a dict summarizing outcome for ranking:
      {ok, tokens, wl_hash, netlist, sized, errors:[...], objective, stages}
    `phase` is 'propose' or 'edit' (which phase produced the netlist).

    `stages` (cross-PDK v0) is a per-candidate booleans dict tracking the funnel
    each stage the candidate cleared -- parse/roundtrip, L0, bias-conducting,
    sized-at-all, feasible -- so the campaign's cross-PDK funnel-rate table falls
    out of the result rows MECHANICALLY (the overfit-to-bptm45 signal is the
    differential of these rates across processes). It is carried in EVERY return
    so a candidate that dies at any stage still records how far it got.

    `pdk` is a per-run process override threaded into sizing (default: spec's)."""
    errors = []
    # every candidate carries the funnel it walked; each stage flips one field.
    stages = {"parsed": False, "l0": False, "bias": False, "sized": False,
              "feasible": False}
    prop_row = {"netlist": netlist_text if netlist_text is not None else "",
                "rationale": rationale, "predicted_deltas": deltas}
    # completion_verbatim: the model's raw text, untruncated -- the house rule
    # (context-attrition lesson) and the only way to debug a parse failure.
    traj.row(iteration, phase, model_id=model_id, proposal=prop_row,
             completion_verbatim=raw_completion,
             prompt_tokens=(usage or {}).get("prompt_tokens"),
             completion_tokens=(usage or {}).get("completion_tokens"))

    def _ret(ok, tokens, wl, sized, objective):
        return {"ok": ok, "tokens": tokens, "wl_hash": wl,
                "netlist": netlist_text, "sized": sized, "errors": errors,
                "objective": objective, "stages": dict(stages)}

    # ---- roundtrip ---------------------------------------------------------
    t0 = time.time()
    if not netlist_text:
        err = "model emitted no parseable netlist block"
        errors.append(err)
        traj.row(iteration, "roundtrip", roundtrip_ok=False, error_verbatim=err,
                 phase_seconds=round(time.time() - t0, 3))
        return _ret(False, None, None, None, None)
    info = P.round_trip(netlist_text)
    traj.row(iteration, "roundtrip", roundtrip_ok=bool(info["ok"]),
             wl_hash=info["wl_hash"], error_verbatim=info["error"],
             phase_seconds=round(time.time() - t0, 3))
    if not info["ok"]:
        errors.append(info["error"] or "round-trip failed")
        return _ret(False, info.get("tokens"), info["wl_hash"], None, None)
    stages["parsed"] = True
    tokens, wl = info["tokens"], info["wl_hash"]

    # ---- screen (L0) -------------------------------------------------------
    t0 = time.time()
    try:
        passed, crit = screen_topology(spec, tokens)
        traj.row(iteration, "screen", wl_hash=wl, l0_pass=passed,
                 l0_criteria=crit, phase_seconds=round(time.time() - t0, 3))
    except Exception as e:
        err = "structural_screen raised %s: %s" % (type(e).__name__, e)
        errors.append(err)
        traj.row(iteration, "screen", wl_hash=wl, l0_pass=False,
                 error_verbatim=err, phase_seconds=round(time.time() - t0, 3))
        return _ret(False, tokens, wl, None, None)
    if not passed:
        failed = [k for k, v in crit.items() if not v]
        err = "L0 screen rejected: failed %s" % ", ".join(failed)
        errors.append(err)
        traj.row(iteration, "screen", wl_hash=wl, l0_pass=False,
                 l0_criteria=crit, next_action="reject", error_verbatim=err)
        return _ret(False, tokens, wl, None, None)
    stages["l0"] = True

    # ---- bias (L1) ---------------------------------------------------------
    t0 = time.time()
    conducting, bias_err = bias_probe(tokens, pdk=pdk)
    traj.row(iteration, "bias", wl_hash=wl, bias_conducting=conducting,
             error_verbatim=bias_err, phase_seconds=round(time.time() - t0, 3))
    if not conducting:
        errors.append(bias_err or "bias did not conduct")
        return _ret(False, tokens, wl, None, None)
    stages["bias"] = True

    # ---- size (L2) ---------------------------------------------------------
    if no_sim:
        traj.row(iteration, "size", wl_hash=wl,
                 sized={"feasible": None, "metrics": None, "margins": None,
                        "best_objective": None, "n_evals": 0, "seconds": 0.0},
                 next_action="skip_size(no_sim)")
        return _ret(True, tokens, wl, None, None)

    best, secs, _ = size_candidate(tokens, spec_ref, seeds, budget, pdk=pdk)
    if best is None:
        err = "sizing produced no result (topology not sizable for this spec)"
        errors.append(err)
        traj.row(iteration, "size", wl_hash=wl, error_verbatim=err,
                 phase_seconds=secs)
        return _ret(False, tokens, wl, None, None)
    stages["sized"] = True
    stages["feasible"] = bool(best["feasible"])
    sized = {"feasible": best["feasible"], "margins": best["margins"],
             "metrics": best["metrics"], "best_objective": best["best_obj"],
             "seed": best["seed"], "seconds": secs}
    pvo = _prediction_vs_outcome(deltas, best["metrics"])
    traj.row(iteration, "size", wl_hash=wl, sized=sized,
             prediction_vs_outcome=pvo, phase_seconds=secs,
             next_action="accept" if best["feasible"] else "keep_best_effort")
    return _ret(True, tokens, wl, {**sized, "best_params": best["best_params"]},
                best["best_obj"])


def _prediction_vs_outcome(deltas, metrics):
    if not deltas or not metrics:
        return None
    out = {}
    for m, pred in deltas.items():
        meas = metrics.get(m)
        err = None
        if isinstance(pred, (int, float)) and isinstance(meas, (int, float)):
            err = round(meas - pred, 6)
        out[m] = {"predicted": pred, "measured": meas, "error": err}
    return out or None


def rank_key(cand, spec):
    """Feasibility-first ranking: feasible before infeasible, then objective asc."""
    sized = cand.get("sized") or {}
    feasible = bool(sized.get("feasible"))
    obj = cand.get("objective")
    obj = obj if isinstance(obj, (int, float)) else float("inf")
    return (0 if feasible else 1, obj)


def save_best(out_dir, spec_name, cand):
    """Write the best design in solve_spec.py's designs/ layout."""
    solve = _lna_import("solve_spec")
    sized = cand["sized"]
    res = {"feasible": sized["feasible"], "best_obj": cand["objective"],
           "best_params": sized["best_params"], "metrics": sized["metrics"],
           "margins": sized["margins"], "seed": sized.get("seed"),
           "_label": cand["wl_hash"][:12] if cand.get("wl_hash") else spec_name}
    return solve.save_design(out_dir, spec_name, cand["tokens"], res)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="spec name in lna/specs/ or path")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1",
                    help="OpenAI-compatible endpoint (llama-server)")
    ap.add_argument("--model", default="local", help="model id sent to the server")
    ap.add_argument("--dry-run", action="store_true",
                    help="use committed fixtures instead of a live LLM (no GPU)")
    ap.add_argument("--no-sim", action="store_true",
                    help="skip the ngspice sizing step (structure-only smoke)")
    ap.add_argument("--k", type=int, default=2, help="proposals to request")
    ap.add_argument("--edit-rounds", type=int, default=1,
                    help="edit rounds on the best candidate (v0: 0 or 1)")
    ap.add_argument("--seeds", type=int, default=1, help="CMA-ES seeds per sizing")
    ap.add_argument("--budget", type=int, default=200, help="ngspice evals per sizing")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--grammar-file", help="GBNF grammar to constrain decode")
    ap.add_argument("--run-id", help="override run id (default: uuid4 hex)")
    ap.add_argument("--out-dir", help="designs output dir (default depends on mode)")
    ap.add_argument("--traj-dir", help="trajectory dir (default depends on mode)")
    args = ap.parse_args(argv)

    from spec import Spec
    spec = Spec.load(args.spec)
    spec_ref = spec.source                       # path -> stable across procs

    run_id = args.run_id or uuid.uuid4().hex[:16]
    on_kaggle = os.path.isdir("/kaggle/working")
    traj_dir = args.traj_dir or (
        "/kaggle/working/trajectory" if on_kaggle and not args.dry_run
        else os.path.join(os.getcwd(), "trajectory_local"))
    out_dir = args.out_dir or (
        "/kaggle/working/designs" if on_kaggle and not args.dry_run
        else os.path.join(os.getcwd(), "designs_local"))
    traj = Trajectory(os.path.join(traj_dir, run_id + ".jsonl"), run_id, spec.name)

    if args.dry_run:
        client = DryRunClient(os.path.join(HERE, "fixtures"))
        model_id = "dryrun"
    else:
        grammar = None
        if args.grammar_file:
            with open(args.grammar_file, encoding="utf-8") as fh:
                grammar = fh.read()
        client = ChatClient(args.base_url, model=args.model, grammar=grammar)
        model_id = args.model

    print("run %s  spec=%s  mode=%s  traj=%s"
          % (run_id, spec.name, "dry-run" if args.dry_run else "live",
             os.path.join(traj_dir, run_id + ".jsonl")), flush=True)

    # ---- consult -----------------------------------------------------------
    t0 = time.time()
    hits, cargv, cerr = consult_playbook(spec)
    traj.row(0, "consult", consult_hits=hits, error_verbatim=cerr,
             phase_seconds=round(time.time() - t0, 3))
    print("consult: %d hit(s)%s" % (len(hits), "" if not cerr else " (err: %s)" % cerr),
          flush=True)

    # ---- propose (K) -------------------------------------------------------
    candidates = []
    messages = build_propose_prompt(spec, hits)
    try:
        resp = client.complete(messages, temperature=args.temperature,
                               max_tokens=args.max_tokens, n=args.k)
        choices = resp.get("choices", [])
        usage = resp.get("usage")
        rmodel = resp.get("model", model_id)
    except LLMError as e:
        traj.row(0, "propose", error_verbatim=str(e), next_action="give_up")
        print("PROPOSE FAILED: %s" % e, flush=True)
        traj.close()
        _flush_note(traj_dir, run_id, "propose_failed")
        return 1

    for k, ch in enumerate(choices[:args.k]):
        content = (ch.get("message") or {}).get("content", "")
        netlist, rationale, deltas = parse_completion(content)
        print("  proposal %d: %s"
              % (k, "netlist parsed" if netlist else "NO netlist block"), flush=True)
        cand = run_candidate(traj, spec, spec_ref, k, netlist, rationale, deltas,
                             rmodel, usage, "propose", args.no_sim,
                             args.seeds, args.budget, raw_completion=content)
        candidates.append(cand)

    ok = [c for c in candidates if c["ok"]]
    if not ok:
        print("no candidate survived the funnel; see trajectory for verbatim errors",
              flush=True)
        traj.row(len(candidates), "diagnose",
                 diagnosis="all proposals failed before sizing", next_action="give_up")
        traj.close()
        _flush_note(traj_dir, run_id, "no_viable_candidate")
        return 2

    ok.sort(key=lambda c: rank_key(c, spec))
    best = ok[0]

    # ---- diagnose + one edit round ----------------------------------------
    if args.edit_rounds >= 1 and not args.no_sim and best.get("sized"):
        it = len(candidates)
        margins = best["sized"].get("margins") or {}
        binding = _binding_constraint(margins)
        diag = ("binding constraint: %s (margin %s). Editing to improve it."
                % (binding[0], binding[1]) if binding
                else "best candidate feasible; attempting a soft-objective edit.")
        traj.row(it, "diagnose", wl_hash=best.get("wl_hash"), diagnosis=diag,
                 sized={"margins": margins, "metrics": best["sized"].get("metrics"),
                        "feasible": best["sized"].get("feasible")},
                 next_action="edit")
        emsgs = build_edit_prompt(spec, hits, best["netlist"], best["sized"],
                                  best["errors"])
        try:
            eresp = client.complete(emsgs, temperature=args.temperature,
                                    max_tokens=args.max_tokens, n=1)
            ech = eresp.get("choices", [{}])[0]
            content = (ech.get("message") or {}).get("content", "")
            netlist, rationale, deltas = parse_completion(content)
            ecand = run_candidate(traj, spec, spec_ref, it, netlist, rationale,
                                  deltas, eresp.get("model", model_id),
                                  eresp.get("usage"), "edit", args.no_sim,
                                  args.seeds, args.budget, raw_completion=content)
            if ecand["ok"]:
                candidates.append(ecand)
                ok.append(ecand)
                ok.sort(key=lambda c: rank_key(c, spec))
                best = ok[0]
        except LLMError as e:
            traj.row(it, "edit", error_verbatim=str(e), next_action="skip_edit")
            print("EDIT FAILED (kept best proposal): %s" % e, flush=True)

    # ---- write best design -------------------------------------------------
    verdict = "no sizing (no_sim)" if args.no_sim else (
        "FEASIBLE" if (best.get("sized") or {}).get("feasible") else
        "infeasible (closest attempt)")
    if best.get("sized") and best["sized"].get("best_params"):
        ddir = save_best(out_dir, spec.name, best)
        print("best: %s  wl=%s  obj=%s\n  design -> %s"
              % (verdict, (best.get("wl_hash") or "?")[:12], best.get("objective"),
                 ddir), flush=True)
    else:
        print("best: %s  wl=%s  (no design written -- no sized params)"
              % (verdict, (best.get("wl_hash") or "?")[:12]), flush=True)
    traj.close()
    return 0


def _binding_constraint(margins):
    worst = None
    for name, m in (margins or {}).items():
        mar = m.get("margin")
        if isinstance(mar, (int, float)):
            if worst is None or mar < worst[1]:
                worst = (name, mar)
    return worst


def _flush_note(traj_dir, run_id, why):
    """On a failure path, drop a tiny note so the session's outputs record why."""
    try:
        with open(os.path.join(traj_dir, run_id + ".note"), "w",
                  encoding="utf-8") as fh:
            fh.write(why + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
