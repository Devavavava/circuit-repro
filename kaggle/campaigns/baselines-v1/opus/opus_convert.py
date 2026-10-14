#!/usr/bin/env python
"""baselines-v1 part O (kaggle/PREREG-BASELINES-V1.md): convert the Opus subagents' answer files
into the pilot-v0 gen-dir layout so pv1_score.py scores them exactly like sft-r1.

  opus_convert.py <answers_root> <out_gen_dir>

<answers_root>/s<N><A|B>/answers-part<k>.txt hold blocks "==== ANSWER <task> ====\\n<reply>".
Per (sample, task): raw_output.txt = the reply; edit0.net = the FIRST fenced netlist block parsed
with editcap_run._parse_edits_from_raw (the live-LLM parse path); results.jsonl row as p1_gen
(validity via proposal.round_trip). A missing answer is recorded as llm_error="missing answer".
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "kaggle"))
import editcap_run as ER  # noqa: E402

P = ER.P
HDR = re.compile(r"^==== ANSWER (\S+) ====\s*$", re.M)


def parse_answers(text):
    out = {}
    ms = list(HDR.finditer(text))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out.setdefault(m.group(1), text[m.end():end].strip("\n") + "\n")
    return out


def main(root, out):
    plan = json.load(open(os.path.join(root, "plan.json")))
    rows, dup = [], 0
    os.makedirs(out, exist_ok=True)
    for tag, pl in sorted(plan["plan"].items()):
        s = int(tag[1:-1])
        got = {}
        for p in sorted(glob.glob(os.path.join(root, tag, "answers-part*.txt"))):   # incl. re-asks (part5+)
            if os.path.exists(p):
                for t, a in parse_answers(open(p, errors="replace").read()).items():
                    dup += t in got
                    got.setdefault(t, a)
        for t in pl["tasks"]:
            d = os.path.join(out, "s%d" % s, t)
            os.makedirs(d, exist_ok=True)
            row = {"task": t, "sample": s, "model_id": "claude-opus (Claude Code subagent)", "agent": tag,
                   "llm_error": None, "recovered_from_reasoning": False}
            raw = got.get(t)
            if raw is None:
                row.update(llm_error="missing answer", n_edits=0, valid=False, wl_hash=None,
                           rt_error="no answer", tokens=None)
                rows.append(row)
                continue
            open(os.path.join(d, "raw_output.txt"), "w").write(raw)
            edits = ER._parse_edits_from_raw(raw)
            row["n_edits"] = len(edits)
            if edits:
                open(os.path.join(d, "edit0.net"), "w").write(edits[0])
                info = P.round_trip(edits[0])
                row.update(valid=bool(info["ok"]), wl_hash=info.get("wl_hash"), rt_error=info.get("error"),
                           tokens=info.get("tokens"))
            else:
                row.update(valid=False, wl_hash=None, rt_error="no fenced netlist", tokens=None)
            rows.append(row)
    with open(os.path.join(out, "results.jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    n = len(rows)
    print(json.dumps({"rows": n, "answered": sum(1 for r in rows if r["llm_error"] is None),
                      "valid": sum(1 for r in rows if r.get("valid")),
                      "multi_block": sum(1 for r in rows if (r.get("n_edits") or 0) > 1),
                      "duplicate_answer_headers": dup}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
