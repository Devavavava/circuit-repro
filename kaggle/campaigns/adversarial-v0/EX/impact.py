"""Guard-impact set (deviation D7): the witness of every bench-v2 ACCEPTED cell and every
`ok` training task (bench-v2/run/cells.jsonl + train.jsonl, READ-ONLY, snapshot sha1
recorded), re-sized under rl-v1.1 at its recorded witness seed (cell: A1 seed 1;
training: the first feasible witness seed) on its own spec, then R-a..R-e exactly like
a seed (ex_drv.py seed). A record already on file with the same (tok, spec file,
seed) -- a strict seed or an extended-record row -- is reused instead of re-run.

usage: impact.py list <out impact_seeds.jsonl> <out reuse.json>
"""
import glob
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402
import seeds as SD  # noqa: E402
import bv2  # noqa: E402
import proposal as P  # noqa: E402

T = os.environ.get("TMPDIR", "/tmp")


def sha1(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()


def main(out, reuse_out):
    tm = SD.tok_map()
    have = {}
    for f in sorted(glob.glob(f"{T}/raw/seeds/S*.json")) + sorted(glob.glob(f"{T}/raw/ext/E*.json")):
        try:
            r = json.load(open(f))
        except Exception:                                        # noqa: BLE001
            continue
        key = (r["tok"], os.path.basename(r.get("src_spec") or r["spec"]), int(r["seed"]))
        have.setdefault(key, r.get("sid"))
    items = []
    for ln in open(f"{SD.RUN}/cells.jsonl"):
        c = json.loads(ln)
        if c.get("status") != "accepted":
            continue
        runs = ((c.get("stages") or {}).get("A1") or {}).get("runs") or []
        seed = next((x["seed"] for x in runs if x.get("feasible")), 1)
        items.append(("cell", c["name"], c["tok"], c["netlist"], c["spec"], seed,
                      c.get("witness_search_metrics") or {}, c.get("era_tag")))
    for ln in open(f"{SD.RUN}/train.jsonl"):
        t = json.loads(ln)
        if t.get("status") != "ok":
            continue
        w = (t.get("stages") or {}).get("witness") or []
        seed = next((x["seed"] for x in w if x.get("feasible")), 1)
        items.append(("train", t["name"], t["tok"], t["netlist"], t["spec"], seed, {}, None))
    rows, reuse, miss = [], {}, 0
    for i, (kind, name, tok, net, spec, seed, recm, era) in enumerate(items):
        key = (tok, os.path.basename(spec), int(seed))
        if key in have:
            reuse[name] = {"kind": kind, "record": have[key], "seed": seed}
            continue
        toks = tm.get(tok)
        if toks is None:
            rt = P.round_trip(net)
            if not rt["ok"]:
                miss += 1
                continue
            toks = rt["tokens"]
            if bv2.tokhash(toks) != tok:
                miss += 1
                continue
        dst = f"{SD.SPECS}/{os.path.basename(spec)}"
        if not os.path.exists(dst):
            shutil.copyfile(spec, dst)
        rows.append({"sid": f"I{len(rows):03d}", "origin": "bench-v2", "tok": tok, "tokens": toks,
                     "spec": os.path.relpath(dst, X.REPO), "src_spec": os.path.relpath(spec, X.REPO),
                     "seed": int(seed), "kinds": [kind], "meta": {kind: name, "era": era},
                     "jid": None, "rec_metrics": recm, "impact": True})
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    snap = {"cells.jsonl_sha1": sha1(f"{SD.RUN}/cells.jsonl"),
            "train.jsonl_sha1": sha1(f"{SD.RUN}/train.jsonl"),
            "n_items": len(items), "n_cells": sum(i[0] == "cell" for i in items),
            "n_train": sum(i[0] == "train" for i in items), "n_run": len(rows),
            "n_reused": len(reuse), "n_token_miss": miss, "reuse": reuse}
    json.dump(snap, open(reuse_out, "w"), indent=1)
    print({k: v for k, v in snap.items() if k != "reuse"})


if __name__ == "__main__":
    main(sys.argv[2], sys.argv[3])
