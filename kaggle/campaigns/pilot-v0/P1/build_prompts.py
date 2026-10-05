#!/usr/bin/env python
"""pilot-v0 P1 step 1: held-out eval prompts NOW, from the frozen split.

Uses pv0.py's own prompt path read-only (import; no pv0 run dir touched):
  shown anchor  = pv0.shown_anchor(task, seed-1 E-TF1 rows)       (README D-P2)
  evidence      = pv0.evidence_for(R, task, anchor, [(1, seed-1 row)])  (D-P3)
  prompt        = pv0.prompt_for(R, spec, anchor, evidence)  = editcap_run.build_prompt_B(k=1),
                  EDITCAP_FEWSHOT / EDITCAP_NO_THINK unset
The seed-1 E-TF1 rows are exact-key cache hits (AMENDMENT-3 T-F1 rows, plus any row
already in pilot-v0 run/ or smoke/ results, read-only). The 2 strict cells use the
AMENDMENT-3 record's F1 seed-1 row of their anchor, exactly as pv0.build_eval.

Each prompts/<task>.json is written in pv0.build_eval's exact JSON layout, so it can be
compared byte-for-byte with eval/prompts/<task>.json once P0 writes it (`compare`).

usage (through an env wrapper with the crenv vars):
  build_prompts.py build      -> P1/prompts/*.json, P1/specs/*.yaml, P1/prompts/INDEX.json
  build_prompts.py compare    -> P1/prompts/COMPARE-<src>.json (byte equality vs
                                 pilot-v0/eval/prompts or a given dir)
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
PV0 = os.path.dirname(HERE)
sys.path.insert(0, PV0)
import pv0  # noqa: E402

B = pv0.B
SCRATCH = os.environ.get("P1_SCRATCH", "/tmp/crp1/pv0-shadow")


def runner():
    os.makedirs(SCRATCH, exist_ok=True)
    src = f"{PV0}/run/f2space.json"
    if os.path.exists(src) and not os.path.exists(f"{SCRATCH}/f2space.json"):
        shutil.copy(src, f"{SCRATCH}/f2space.json")     # read-only copy (avoids a rebuild)
    a = argparse.Namespace(cmd="build-eval", run_dir=SCRATCH, eval_limit=None, f2_limit=None,
                           train_limit=None, no_gen=True, gen_max_new=None, max_procs=1,
                           extra_cache=[f"{PV0}/run/results.jsonl", f"{PV0}/smoke/results.jsonl"],
                           partial=True)
    R = pv0.Runner(a)
    R.load_inputs()
    return R


def build():
    R = runner()
    out = f"{HERE}/prompts"
    os.makedirs(out, exist_ok=True)
    os.makedirs(f"{HERE}/specs", exist_ok=True)
    index = OrderedDict()
    for t in R.eval_tasks:
        n, spec = t["name"], t["spec"]
        jobs = R.tf1_jobs("E-TF1", t, 1)
        s1 = []
        for j in jobs:
            r = R.cache.get(j.jid)
            if r is None and j.meta.get("inproc"):
                r = R.inproc(j)                 # 0-eval pre-reject, written to SCRATCH only
            assert r is not None, f"{n} {j.meta['anchor']}: seed-1 E-TF1 row not cached"
            s1.append(R.summ(r, 1, spec, anchor=j.meta["anchor"]))
        an = pv0.shown_anchor(t, s1)
        if an is None:
            index[n] = {"excluded": "no anchor fails at seed 1 (no shown anchor)"}
            continue
        row = [R.cache[x["jid"]] for x in s1 if x["anchor"] == an][0]
        ev = pv0.evidence_for(R, t, an, [(1, row)])
        assert not ev["feasible"]
        msgs, text = pv0.prompt_for(R, spec, an, ev)
        shutil.copy(spec, f"{HERE}/specs/{n}.yaml")
        body = json.dumps(OrderedDict(
            task=n, kind="held-out training-pool task", family=t["g"], band_type=t["bt"],
            spec_file=f"specs/{n}.yaml", spec_sha=B.spec_sha(spec), shown_anchor=an,
            shown_anchor_family=R.anch[an]["family"], arm="B", k=1, fewshot=False,
            messages=msgs, prompt_text=text, evidence=ev), indent=1, default=float)
        B.atomic_write(f"{out}/{n}.json", body)
        index[n] = {"family": t["g"], "band_type": t["bt"], "shown_anchor": an,
                    "parent_anchor": t["anchor"], "spec": os.path.relpath(spec, pv0.REPO),
                    "spec_sha": B.spec_sha(spec),
                    "seed1_feasible_anchors": [x["anchor"] for x in s1 if x["feasible"]],
                    "sha256": hashlib.sha256(body.encode()).hexdigest()}
    # strict cells: pv0.build_eval's prompt path verbatim
    a3cache = {r["jid"]: r for r in B.read_jsonl(f"{pv0.A3}/run/results.jsonl")}
    cells3 = B.load_jsonl_last(f"{pv0.A3}/run/cells_amend3.jsonl", "name")
    for cn in pv0.STRICT:
        o, c = cells3[cn], R.cells[cn]
        st = o["stages"]
        spec = c["spec"] if os.path.exists(c["spec"]) else f"{pv0.SRC}/specs/{os.path.basename(c['spec'])}"
        row = [a3cache[x["jid"]] for x in st["F1"]["runs"] if x["anchor"] == c["anchor"] and x["seed"] == 1][0]
        ev = pv0.evidence_for(R, {"name": cn, "spec": spec}, c["anchor"], [(1, row)])
        msgs, text = pv0.prompt_for(R, spec, c["anchor"], ev)
        shutil.copy(spec, f"{HERE}/specs/{cn}.yaml")
        body = json.dumps(OrderedDict(
            task=cn, kind="bench-v2 strict cell (AMENDMENT 3 pass)", family=c["g"],
            band_type=c["bt"], spec_file=f"specs/{cn}.yaml", spec_sha=B.spec_sha(spec),
            shown_anchor=c["anchor"], shown_anchor_family=R.anch[c["anchor"]]["family"], arm="B",
            k=1, fewshot=False, messages=msgs, prompt_text=text, evidence=ev),
            indent=1, default=float)
        B.atomic_write(f"{out}/{cn}.json", body)
        index[cn] = {"family": c["g"], "band_type": c["bt"], "shown_anchor": c["anchor"],
                     "parent_anchor": c["anchor"], "spec": os.path.relpath(spec, pv0.REPO),
                     "spec_sha": B.spec_sha(spec), "strict_cell": True,
                     "sha256": hashlib.sha256(body.encode()).hexdigest()}
    meta = OrderedDict(
        what="pilot-v0 P1 held-out eval prompts, generated before P0 tiering finished, "
             "via pv0.py's own prompt path (read-only import)",
        prereg="kaggle/PREREG-PILOT-V0.md (137ea060a)",
        split_sha256=open(f"{pv0.EVAL}/split.json.sha256").read().split()[0],
        pv0_md5=hashlib.md5(open(pv0.__file__, "rb").read()).hexdigest()[:10],
        n_items=sum(1 for v in index.values() if not v.get("excluded")),
        n_excluded=sum(1 for v in index.values() if v.get("excluded")), items=index)
    B.atomic_write(f"{out}/INDEX.json", json.dumps(meta, indent=1))
    print(f"prompts: {meta['n_items']} written, {meta['n_excluded']} excluded -> {out}")


def compare(src):
    out = f"{HERE}/prompts"
    idx = json.load(open(f"{out}/INDEX.json"))["items"]
    res = OrderedDict()
    for n, v in idx.items():
        if v.get("excluded"):
            continue
        theirs = f"{src}/{n}.json"
        if not os.path.exists(theirs):
            res[n] = "absent"
            continue
        res[n] = "identical" if open(theirs, "rb").read() == open(f"{out}/{n}.json", "rb").read() \
            else "DIFFERENT"
    extra = sorted(set(f[:-5] for f in os.listdir(src) if f.endswith(".json")) - set(idx))
    summ = {k: sum(1 for x in res.values() if x == k) for k in ("identical", "DIFFERENT", "absent")}
    rec = OrderedDict(src=os.path.relpath(src, pv0.REPO), summary=summ,
                      only_in_src=extra, items=res)
    tag = os.path.relpath(src, PV0).replace("/", "_")
    B.atomic_write(f"{out}/COMPARE-{tag}.json", json.dumps(rec, indent=1))
    print(json.dumps({"src": rec["src"], "summary": summ, "only_in_src": extra}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "compare"])
    ap.add_argument("--src", default=f"{pv0.EVAL}/prompts")
    a = ap.parse_args()
    build() if a.cmd == "build" else compare(os.path.abspath(a.src))
