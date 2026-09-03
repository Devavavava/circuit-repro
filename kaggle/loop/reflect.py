"""reflect.py -- the self-learning REFLECT stage for capability-v1 (ARM3).

At the start of an ARM3 session the SYSTEM reads its OWN prior campaign output
(the committed capability-v0 arm-B results + trajectories), identifies its OWN
recurring shortcomings, and writes playbook entries it will retrieve later in the
same campaign via the consult overlay. No human- or Claude-authored domain
guidance enters here: this file supplies ONLY structure (what to read, the entry
schema, the mechanical checks) -- never circuit knowledge. The content of every
accepted entry is the model's own words, grounded in verbatim quotes of its own
run rows.

Binding standing principle (user ruling): the prompt is CONTENT-NEUTRAL. It tells
the model the shape of its input and the shape of the output (Trigger / Evidence
/ Rule / Applicability, playbook JSON), and requires that every evidence string
appear VERBATIM in the loaded results/trajectories. It names no circuit family,
no metric target, no design move. The reflect prompt is printed verbatim by
`--print-prompt` so the no-injected-content claim is auditable.

What reflect does, in order:

  1. Load the v0 arm-B corpus: results.jsonl (one row per spec: feasible,
     margins, worst_margin, notes) + every trajectory *.jsonl (proposals,
     rationales, prediction_vs_outcome, verbatim errors, sized margins). Build
     a single flat set of VERBATIM quotable strings (the evidence corpus) so an
     entry whose evidence is a paraphrase is rejected mechanically.
  2. Build the content-neutral prompt from a compact, faithful digest of that
     corpus (the model sees its own numbers, not a summary we editorialized).
  3. Ask the LLM (or, under --dry-run, a canned fixture) for up to CAP entries in
     the playbook schema.
  4. For each proposed entry: stamp author="system", confidence="unverified";
     enforce that EVERY evidence quote appears verbatim in the loaded corpus;
     validate against lna/playbook.py's own validate_entry(); reject on any
     failure and LOG the rejection verbatim to the trajectory.
  5. Write accepted entries (capped) to an OVERLAY store dir (one <id>.json per
     entry, the same on-disk shape playbook.py --consult --extra-dir reads).

    # locally testable end to end, no server, no ngspice:
    python kaggle/loop/reflect.py --dry-run \
        --v0-dir kaggle/campaigns/capability-v0/armb \
        --overlay-dir /tmp/overlay --traj /tmp/reflect.jsonl

CAP (max accepted entries) is pre-registered in CAMPAIGN-CAPABILITY-V1.md.
"""
import argparse
import json
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ROOT = os.environ.get("LNA_DEPS_ROOT") or os.path.abspath(
    os.path.join(HERE, "..", ".."))
LNA = os.path.join(ROOT, "lna")
if os.path.isdir(LNA) and LNA not in sys.path:
    sys.path.insert(0, LNA)

import driver as D                                                # noqa: E402
import playbook as PB                                             # noqa: E402

# Pre-registered cap on accepted overlay entries per reflect pass.
DEFAULT_CAP = 12
# Minimum literal length a quote must have to count as "verbatim evidence" --
# guards against an entry citing a 2-char fragment that trivially appears.
MIN_QUOTE_LEN = 12


# ============================================================ corpus loading
def _iter_strings(obj):
    """Yield every string reachable in a nested json object (keys skipped:
    only VALUES are quotable evidence). Numbers are yielded as their repr AND
    their %.6g form so a quote like '17.81288' or '-10.13' matches either the
    stored float or a rounded rendering the model might copy."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, bool):
        yield str(obj)
    elif isinstance(obj, (int, float)):
        yield repr(obj)
        try:
            yield "%.6g" % obj
            yield "%.5g" % obj
            yield "%.4g" % obj
            yield "%.3g" % obj
        except Exception:
            pass
    elif isinstance(obj, dict):
        for v in obj.values():
            for s in _iter_strings(v):
                yield s
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            for s in _iter_strings(v):
                yield s


def load_corpus(v0_dir):
    """Load results.jsonl + all trajectory/*.jsonl under v0_dir.

    v0_dir may be a single dir or a list of dirs (repeated --v0-dir); corpora
    concatenate additively in the order given. Each dir must hold a
    results.jsonl; trajectory/ is optional per dir.

    Returns (results_rows, traj_rows, corpus_blob) where corpus_blob is one big
    string of every value in every row -- the substring haystack the verbatim
    evidence check runs against. Raising here is a hard error: reflect cannot
    run without its own prior output to reflect on.
    """
    dirs = [v0_dir] if isinstance(v0_dir, str) else list(v0_dir)
    results = []
    traj_rows = []
    for d in dirs:
        results_path = os.path.join(d, "results.jsonl")
        if not os.path.isfile(results_path):
            raise SystemExit("[reflect] no results.jsonl under %s" % d)
        with open(results_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    results.append(json.loads(line))

        traj_dir = os.path.join(d, "trajectory")
        if os.path.isdir(traj_dir):
            for fn in sorted(os.listdir(traj_dir)):
                if not fn.endswith(".jsonl"):
                    continue
                with open(os.path.join(traj_dir, fn), encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            try:
                                traj_rows.append(json.loads(line))
                            except Exception:
                                pass

    # the verbatim haystack: every reachable string value + the raw file text.
    parts = []
    for row in results:
        parts.extend(_iter_strings(row))
    for row in traj_rows:
        parts.extend(_iter_strings(row))
    corpus_blob = "\n".join(parts)
    return results, traj_rows, corpus_blob


# ============================================================ prompt assembly
def _results_digest(results):
    """A compact, faithful line per spec: the model's own outcome + numbers.

    Content-neutral: it copies fields straight out of the row, editorializing
    nothing. Every number here also lives in the corpus_blob, so the model can
    quote it verbatim.
    """
    lines = []
    for r in results:
        wm = r.get("worst_margin")
        wm_s = ("%s=%.5g" % (wm[0], wm[1])
                if wm and isinstance(wm[1], (int, float)) else "-")
        margin_bits = []
        for name, m in (r.get("margins") or {}).items():
            mar = m.get("margin")
            ach = m.get("achieved")
            if isinstance(mar, (int, float)):
                margin_bits.append("%s(achieved=%s,margin=%.5g)"
                                   % (name,
                                      ("%.6g" % ach if isinstance(ach, (int, float))
                                       else ach), mar))
        sh = (r.get("stage_rates") or {}).get("sim_health") or {}
        sh_s = ("n_evals=%s,n_sim_fail=%s,sim_success_rate=%s"
                % (sh.get("n_evals"), sh.get("n_sim_fail"),
                   sh.get("sim_success_rate")) if sh else "-")
        lines.append(
            "- spec=%s tier=%s feasible=%s first_feasible_phase=%s "
            "escalated=%s best_obj=%s worst_margin=%s | margins: %s | "
            "sim_health: %s | notes=%r"
            % (r.get("spec"), r.get("tier"), r.get("feasible"),
               r.get("first_feasible_phase"), r.get("escalated"),
               r.get("best_obj"), wm_s, "; ".join(margin_bits), sh_s,
               (r.get("notes") or "")))
    return "\n".join(lines)


def _pvo_digest(traj_rows, cap=40):
    """Prediction-vs-outcome rows: the model's own predicted_deltas vs measured,
    with the signed error. This is where 'my predictions were wrong by X' is
    grounded. Capped so the prompt stays bounded."""
    lines = []
    for r in traj_rows:
        pvo = r.get("prediction_vs_outcome")
        if not pvo:
            continue
        bits = []
        for m, d in pvo.items():
            if isinstance(d, dict):
                bits.append("%s(predicted=%s,measured=%s,error=%s)"
                            % (m, d.get("predicted"), d.get("measured"),
                               d.get("error")))
        if bits:
            lines.append("- spec=%s wl=%s: %s"
                         % (r.get("spec"), r.get("wl_hash"), "; ".join(bits)))
        if len(lines) >= cap:
            lines.append("- (... prediction-vs-outcome rows truncated ...)")
            break
    return "\n".join(lines) if lines else "(no prediction-vs-outcome rows)"


def _error_digest(traj_rows, cap=40):
    """Verbatim per-candidate errors: parse failures, screen rejects, sizing
    failures -- the failure-first signal. Copied verbatim, deduped, capped."""
    seen = []
    for r in traj_rows:
        ev = r.get("error_verbatim")
        if ev and isinstance(ev, str):
            tag = "%s/%s" % (r.get("spec"), r.get("phase"))
            item = "- [%s] %s" % (tag, ev)
            if item not in seen:
                seen.append(item)
        sh = r.get("sim_health") or {}
        sv = sh.get("sim_error")
        if sv and isinstance(sv, str):
            tag = "%s/%s" % (r.get("spec"), r.get("phase"))
            item = ("- [%s] sim_health n_sim_fail=%s n_evals=%s error: %s"
                    % (tag, sh.get("n_sim_fail"), sh.get("n_evals"), sv))
            if item not in seen:
                seen.append(item)
        if len(seen) >= cap:
            seen.append("- (... error rows truncated ...)")
            break
    return "\n".join(seen) if seen else "(no verbatim error rows)"


# The reflect prompt. CONTENT-NEUTRAL by construction: it describes the shape of
# the input and the required output schema and the verbatim-evidence rule. It
# names no circuit family, metric target, topology, or design move. Auditable
# via --print-prompt. {digest}/{pvo}/{errors}/{cap}/{signatures} are filled from
# the model's OWN loaded corpus and the playbook's own controlled vocabulary.
SYSTEM = (
    "You are reviewing the recorded output of your own prior run. You will "
    "identify recurring shortcomings in YOUR OWN output and write reusable rules "
    "you will retrieve later. You reason only from the rows shown; you invent no "
    "facts and quote your own rows verbatim as evidence."
)

REFLECT_PROMPT = """\
Below is the complete recorded output of a prior run of yours: for each task, \
whether you reached a feasible result, the measured margins on every gated \
constraint, your predicted-vs-measured errors, and the verbatim errors your \
candidates produced. Read your own record and identify RECURRING shortcomings in \
YOUR output -- patterns that cost you feasible results or that show your \
predictions were systematically off. For each distinct recurring shortcoming, \
write ONE atomic rule you could retrieve on a future task to avoid repeating it.

=== YOUR PER-TASK OUTCOMES ===
{digest}

=== YOUR PREDICTION-VS-OUTCOME RECORDS (predicted value vs measured, signed error) ===
{pvo}

=== YOUR VERBATIM CANDIDATE ERRORS ===
{errors}

=== OUTPUT CONTRACT (obey exactly) ===
Return a single fenced ```json block containing a JSON list of AT MOST {cap} \
entries. Each entry is an object with EXACTLY these fields:

  "id":            a short kebab-case slug, lowercase letters/digits/dashes only
  "type":          one of {types}
  "trigger":       an object with:
                     "family":            list of strings (the task family)
                     "analysis":          list of strings (the analysis kind)
                     "failure_signature": list of strings, each chosen from: {signatures}
                     "keywords":          non-empty list of retrieval keywords
  "evidence":      a NON-EMPTY list of objects, each {{"quote": <string>, "source": <string>}}.
                   Every "quote" MUST be a substring that appears VERBATIM in the \
rows above (a measured number, a margin, a verbatim error message, or an exact \
field value). An entry whose evidence is a paraphrase, a rounding you did not see, \
or invented text WILL BE REJECTED. Quote your own rows exactly.
  "rule":          one imperative sentence -- the reusable lesson.
  "applicability": an object with "applies" (string) and "not" (string), both non-empty.

Do NOT set author, confidence, sources, or created -- those are stamped for you. \
Write only rules your OWN rows above support. If a shortcoming is not evidenced in \
the rows, do not write a rule for it. Fewer well-grounded entries beat many weak \
ones.
"""


def build_reflect_prompt(results, traj_rows, cap):
    digest = _results_digest(results)
    pvo = _pvo_digest(traj_rows)
    errors = _error_digest(traj_rows)
    user = REFLECT_PROMPT.format(
        digest=digest, pvo=pvo, errors=errors, cap=cap,
        types=", ".join(PB.TYPES),
        signatures=", ".join(PB.FAILURE_SIGNATURES))
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}]


# The first live ARM3 run failed with the full 24-spec prompt at 11,282 tokens
# against an 8,192 context (HTTP 400, zero entries). Reflection is therefore
# CHUNKED: specs are split into contiguous groups whose prompt fits a token
# budget; one LLM call per chunk; validation always runs against the FULL
# corpus_blob; ids dedupe across chunks; the entry cap is global.
REFLECT_TOKEN_BUDGET = int(os.environ.get("REFLECT_PROMPT_TOKEN_BUDGET", "5200"))


def _est_tokens(text):
    """Conservative token estimate (~3 chars/token for this mixed prose/data)."""
    return len(text) // 3


def chunk_reflect_prompts(results, traj_rows, cap, budget=None):
    """Yield (messages, spec_names) per chunk, each chunk's USER message under
    the token budget. Bisects the spec count; a single over-budget spec is sent
    anyway (its digests are internally capped) rather than dropped."""
    budget = budget or REFLECT_TOKEN_BUDGET
    n = len(results)
    start = 0
    while start < n:
        take = n - start
        while take > 1:
            sub = results[start:start + take]
            specs = set(r.get("spec") for r in sub)
            straj = [t for t in traj_rows if t.get("spec") in specs]
            msgs = build_reflect_prompt(sub, straj, cap)
            if _est_tokens(msgs[1]["content"]) <= budget:
                break
            take //= 2
        sub = results[start:start + take]
        specs = set(r.get("spec") for r in sub)
        straj = [t for t in traj_rows if t.get("spec") in specs]
        yield build_reflect_prompt(sub, straj, cap), sorted(specs)
        start += take


# ============================================================ entry validation
def _extract_entries(content):
    """Pull the JSON list of entries from a model completion.

    Accepts a fenced ```json block (preferred) or a bare JSON array/object. On
    any parse failure returns ([], error_string) so the caller logs it verbatim.
    """
    import re
    m = re.search(r"```json\s*\n(.*?)```", content, re.DOTALL | re.IGNORECASE)
    raw = m.group(1) if m else content
    try:
        obj = json.loads(raw)
    except Exception as e:
        # last resort: first [...] span
        m2 = re.search(r"(\[.*\])", raw, re.DOTALL)
        if not m2:
            return [], "reflect: no parseable JSON entries (%s)" % e
        try:
            obj = json.loads(m2.group(1))
        except Exception as e2:
            return [], "reflect: JSON parse failed (%s)" % e2
    if isinstance(obj, dict):
        obj = obj.get("entries", [obj])
    if not isinstance(obj, list):
        return [], "reflect: expected a JSON list of entries, got %s" % type(obj).__name__
    return obj, None


def _quotes_verbatim(entry, corpus_blob):
    """Every evidence quote must appear verbatim (as a substring) in the loaded
    corpus and be at least MIN_QUOTE_LEN chars. Returns (ok, reason_or_None)."""
    ev = entry.get("evidence")
    if not isinstance(ev, list) or not ev:
        return False, "evidence missing or empty"
    for i, item in enumerate(ev):
        if not isinstance(item, dict):
            return False, "evidence[%d] not an object" % i
        q = str(item.get("quote", ""))
        if len(q.strip()) < MIN_QUOTE_LEN:
            return False, ("evidence[%d].quote too short to be verbatim proof "
                           "(<%d chars): %r" % (i, MIN_QUOTE_LEN, q))
        if q not in corpus_blob:
            return False, ("evidence[%d].quote does NOT appear verbatim in the "
                           "loaded results/trajectories: %r" % (i, q))
    return True, None


def stamp_and_validate(entry, corpus_blob, created, seen_ids):
    """Stamp system provenance, enforce verbatim evidence, run playbook schema
    validation. Returns (accepted_entry_or_None, reason_or_None)."""
    if not isinstance(entry, dict):
        return None, "entry is not an object: %r" % (entry,)
    e = dict(entry)
    # SYSTEM stamps: author=system, confidence=unverified, sources + created.
    # The model is forbidden from setting these; overwrite unconditionally.
    e["author"] = "system"
    e["confidence"] = "unverified"
    e["created"] = created
    e["sources"] = ["system reflect on capability-v0 arm-B (%s)" % created]

    eid = e.get("id")
    if eid in seen_ids:
        return None, "duplicate id within this reflect pass: %r" % eid

    ok, why = _quotes_verbatim(e, corpus_blob)
    if not ok:
        return None, "verbatim-evidence check failed: %s" % why

    errs = PB.validate_entry(e)
    if errs:
        return None, "playbook schema errors: %s" % "; ".join(errs)
    return e, None


# ============================================================ overlay writing
def write_overlay(entry, overlay_dir):
    """Write one accepted entry as <id>.json into the overlay store, in the same
    on-disk shape playbook.py reads. Returns the path."""
    os.makedirs(overlay_dir, exist_ok=True)
    path = os.path.join(overlay_dir, entry["id"] + ".json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(entry, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return path


# ============================================================ the reflect pass
def reflect(v0_dir, overlay_dir, client, model_id, traj_path, cap=DEFAULT_CAP,
            temperature=0.4, max_tokens=4096, created=None):
    """Run one reflect pass. Returns a summary dict.

    Logs every phase (load, reflect call, per-entry accept/reject) to traj_path
    as JSONL, one row per event, with rejected entries recorded VERBATIM.
    """
    created = created or time.strftime("%Y-%m-%d")
    run_id = uuid.uuid4().hex[:16]
    os.makedirs(os.path.dirname(os.path.abspath(traj_path)), exist_ok=True)
    tfh = open(traj_path, "a", encoding="utf-8", buffering=1)

    def log(event, **fields):
        rec = {"run_id": run_id, "stage": "reflect", "event": event,
               "ts": time.time()}
        rec.update(fields)
        tfh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        tfh.flush()
        os.fsync(tfh.fileno())
        return rec

    results, traj_rows, corpus_blob = load_corpus(v0_dir)
    log("load_corpus", v0_dir=v0_dir, n_results=len(results),
        n_traj_rows=len(traj_rows), corpus_chars=len(corpus_blob), cap=cap)

    proposed = []
    errors_seen = []
    n_chunks = 0
    shown_texts = []   # the exact prompts shown to the model: the r2 run rejected
    # ALL 17 live entries because the digests round numbers (%.5g) while the gate
    # checked the raw corpus serialization -- the model quoted what it SAW,
    # faithfully. The verbatim reference is therefore corpus + shown prompts
    # (both mechanically derived from its own rows; anti-hallucination intact).
    for messages, chunk_specs in chunk_reflect_prompts(results, traj_rows, cap):
        n_chunks += 1
        shown_texts.append(messages[1]["content"])
        log("reflect_chunk", chunk=n_chunks, specs=chunk_specs,
            est_prompt_tokens=_est_tokens(messages[1]["content"]))
        try:
            resp = client.complete(messages, temperature=temperature,
                                   max_tokens=max_tokens, n=1)
        except Exception as e:                                    # noqa: BLE001
            log("reflect_call_failed", chunk=n_chunks, error_verbatim=str(e))
            errors_seen.append(str(e))
            continue                       # a failed chunk never kills the rest
        content = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        log("reflect_completion", chunk=n_chunks, completion_verbatim=content,
            model=resp.get("model", model_id))
        chunk_entries, perr = _extract_entries(content)
        if perr:
            log("extract_failed", chunk=n_chunks, error_verbatim=perr,
                completion_verbatim=content)
            errors_seen.append(perr)
            continue
        proposed.extend(chunk_entries)
    log("proposed", n_proposed=len(proposed), n_chunks=n_chunks,
        chunk_errors=errors_seen)
    if not proposed and errors_seen:
        tfh.close()
        return {"accepted": 0, "rejected": 0, "entries_written": [],
                "error": "; ".join(errors_seen)[:2000], "run_id": run_id}

    accepted, rejected = [], []
    seen_ids = set()
    evidence_reference = corpus_blob + "\n" + "\n".join(shown_texts)
    for idx, raw_entry in enumerate(proposed):
        if len(accepted) >= cap:
            log("cap_reached", cap=cap, dropped_index=idx,
                entry_verbatim=raw_entry)
            rejected.append({"reason": "cap reached", "entry": raw_entry})
            continue
        e, reason = stamp_and_validate(raw_entry, evidence_reference, created, seen_ids)
        if e is None:
            log("entry_rejected", index=idx, reason=reason,
                entry_verbatim=raw_entry)
            rejected.append({"reason": reason, "entry": raw_entry})
            continue
        seen_ids.add(e["id"])
        path = write_overlay(e, overlay_dir)
        log("entry_accepted", index=idx, id=e["id"], path=path,
            rule=e.get("rule"))
        accepted.append(e["id"])

    log("reflect_done", accepted=len(accepted), rejected=len(rejected),
        overlay_dir=overlay_dir)
    tfh.close()
    return {"accepted": len(accepted), "rejected": len(rejected),
            "entries_written": accepted, "rejected_detail": rejected,
            "overlay_dir": overlay_dir, "run_id": run_id}


# =================================================================== main / cli
def _make_client(args):
    if args.dry_run:
        return D.DryRunClient(os.path.join(HERE, "fixtures")), "dryrun"
    grammar = None
    if args.grammar_file:
        with open(args.grammar_file, encoding="utf-8") as fh:
            grammar = fh.read()
    return D.ChatClient(args.base_url, model=args.model, grammar=grammar), args.model


class _ReflectDryRunClient(object):
    """DryRunClient serves propose/edit fixtures keyed on loop phrasing; reflect
    is a different phase, so it reads its own fixtures/reflect.json instead.
    Falls back to an empty list if the fixture is absent (still a valid path)."""

    def __init__(self, fixtures_dir):
        self._resp = None
        p = os.path.join(fixtures_dir, "reflect.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                self._resp = json.load(fh)["responses"]

    def complete(self, messages, temperature=0.4, max_tokens=4096, n=1,
                 grammar=None):
        if not self._resp:
            return {"model": "dryrun", "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "```json\n[]\n```"}}]}
        base = dict(self._resp[0])
        base["choices"] = [dict(self._resp[0]["choices"][0])]
        return base


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--v0-dir", action="append", dest="v0_dir",
                    help="dir holding results.jsonl (+ optional trajectory/); "
                         "may be repeated -- corpora concatenate additively "
                         "in the order given (default: capability-v0 armb)")
    ap.add_argument("--overlay-dir", required=True,
                    help="output dir for accepted system-authored entries")
    ap.add_argument("--traj", required=True,
                    help="reflect trajectory JSONL (accept/reject log)")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP,
                    help="max accepted overlay entries (pre-registered)")
    ap.add_argument("--dry-run", action="store_true",
                    help="use fixtures/reflect.json instead of a live LLM")
    ap.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model", default="local")
    ap.add_argument("--grammar-file")
    ap.add_argument("--temperature", type=float, default=0.4)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--print-prompt", action="store_true",
                    help="print the reflect prompt (audit) and exit -- no LLM call")
    args = ap.parse_args(argv)
    if not args.v0_dir:
        args.v0_dir = [os.path.join(ROOT, "kaggle", "campaigns",
                                    "capability-v0", "armb")]

    if args.print_prompt:
        results, traj_rows, _ = load_corpus(args.v0_dir)
        msgs = build_reflect_prompt(results, traj_rows, args.cap)
        print("=== SYSTEM ===\n%s\n\n=== USER ===\n%s"
              % (msgs[0]["content"], msgs[1]["content"]))
        return 0

    if args.dry_run:
        client, model_id = _ReflectDryRunClient(os.path.join(HERE, "fixtures")), "dryrun"
    else:
        client, model_id = _make_client(args)

    summary = reflect(args.v0_dir, args.overlay_dir, client, model_id,
                      args.traj, cap=args.cap, temperature=args.temperature,
                      max_tokens=args.max_tokens)
    print("[reflect] accepted=%d rejected=%d -> %s"
          % (summary["accepted"], summary["rejected"], args.overlay_dir),
          flush=True)
    if summary.get("entries_written"):
        print("[reflect] entries: " + ", ".join(summary["entries_written"]),
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
