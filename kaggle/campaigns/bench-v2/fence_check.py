#!/usr/bin/env python
"""bench-v2 fence check (PREREG-BENCH-V2.md, "Training-task pool"):

  no bench spec, and no bench witness netlist (canonical token hash), appears in
  the training pool; bench-v2 cells are EVAL-ONLY.

Checks, for every training task under --train against every bench cell under
--bench (plus every ACCEPTED bench witness in --cells-jsonl, selected or not):
  1. witness token hash (sha1(json(tokens))[:16], recomputed by round-tripping
     witness.net when the repo env is available) not in the bench witness set;
  2. witness WL hash (isomorphism-level) not in the bench witness set;
  3. spec content (band + constraints + objectives + topology) not equal to any
     bench spec;
  4. no training task's witness.net body text equals a bench witness body.
AMENDMENT 1: the bench side also includes every post-amendment PLANTED cell in
--cells-jsonl (any status; its spec and both the stripped and the original
witness), not only accepted ones.
Exit 1 on any violation. Usage:
  fence_check.py --bench kaggle/editcap-lib-v2 --train kaggle/train-pool-v2 \
                 [--cells-jsonl kaggle/campaigns/bench-v2/run/cells.jsonl]
"""
import argparse
import hashlib
import json
import os
import sys

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)


def body(path):
    return "\n".join(ln.strip() for ln in open(path).read().splitlines()
                     if ln.strip() and not ln.lstrip().startswith(("*", "#")))


def spec_key(path):
    import yaml
    d = yaml.safe_load(open(path))
    return hashlib.sha1(json.dumps({k: d.get(k) for k in
                                    ("band", "constraints", "objectives", "topology")},
                                   sort_keys=True).encode()).hexdigest()[:16]


def rt_hashes(net_path):
    try:
        import proposal as P
        rt = P.round_trip(open(net_path).read())
        if rt.get("ok"):
            return (hashlib.sha1(json.dumps(rt["tokens"]).encode()).hexdigest()[:16],
                    rt["wl_hash"])
    except Exception:                                            # noqa: BLE001
        pass
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--train", required=True)
    ap.add_argument("--cells-jsonl", default=None)
    a = ap.parse_args()
    b_tok, b_wl, b_spec, b_body = {}, {}, {}, {}
    for c in sorted(os.listdir(a.bench)) if os.path.isdir(a.bench) else []:
        d = f"{a.bench}/{c}"
        if not os.path.isdir(d):
            continue
        es = json.load(open(f"{d}/witness/edit_script.json"))
        b_tok[es["tok_hash"]] = c
        b_wl[es["wl_hash"]] = c
        t2, w2 = rt_hashes(f"{d}/witness/witness.net")
        if t2:
            b_tok[t2] = c
            b_wl[w2] = c
        b_spec[spec_key(f"{d}/spec.yaml")] = c
        b_body[body(f"{d}/witness/witness.net")] = c
    n_acc = n_post = 0
    if a.cells_jsonl and os.path.exists(a.cells_jsonl):
        last = {}
        for ln in open(a.cells_jsonl):
            r = json.loads(ln)
            last[r["name"]] = r
        for r in last.values():
            # every ACCEPTED cell (both eras) and, AMENDMENT 1, every post-amendment
            # PLANTED cell whatever its status (spec + witness, original and stripped)
            post = r.get("era_tag") == "amendment-1"
            if r.get("status") != "accepted" and not post:
                continue
            n_acc += r.get("status") == "accepted"
            n_post += post
            wits = [r] + ([r["witness_original"]] if r.get("witness_original") else [])
            for w in wits:
                b_tok.setdefault(w["tok"], r["name"])
                b_wl.setdefault(w["wl"], r["name"])
                b_body.setdefault("\n".join(x.strip() for x in w["netlist"].splitlines()
                                            if x.strip()), r["name"])
            if os.path.exists(r.get("spec", "")):
                b_spec.setdefault(spec_key(r["spec"]), r["name"])
    viol = []
    n = 0
    for t in sorted(os.listdir(a.train)) if os.path.isdir(a.train) else []:
        d = f"{a.train}/{t}"
        if not os.path.isdir(d):
            continue
        n += 1
        es = json.load(open(f"{d}/witness/edit_script.json"))
        t2, w2 = rt_hashes(f"{d}/witness/witness.net")
        for h in {es["tok_hash"], t2} - {None}:
            if h in b_tok:
                viol.append((t, "witness token hash", b_tok[h]))
        for h in {es["wl_hash"], w2} - {None}:
            if h in b_wl:
                viol.append((t, "witness WL hash", b_wl[h]))
        k = spec_key(f"{d}/spec.yaml")
        if k in b_spec:
            viol.append((t, "spec content", b_spec[k]))
        bb = body(f"{d}/witness/witness.net")
        if bb in b_body:
            viol.append((t, "witness netlist body", b_body[bb]))
    print(f"fence_check: bench specs={len(b_spec)} (accepted in jsonl={n_acc}, "
          f"post-amendment planted={n_post}) "
          f"bench witness tok={len(b_tok)} wl={len(b_wl)}; training tasks={n}; "
          f"violations={len(viol)}")
    for v in viol:
        print("VIOLATION", *v)
    sys.exit(1 if viol else 0)


if __name__ == "__main__":
    main()
