"""Command list for the G-CP1 recoverability re-sizes (D9): every accepted-cell witness and a
deterministic sample (sha1 order of the task name, first N) of the training witnesses
that FAIL the proposed guard G-CP1io strictly (harness_diag P1io not ok), variant `io`.
usage: resize_list.py <summary.json from analyze2> <cmds out> <N train>
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.environ.get("TMPDIR", "/tmp/cr-7cd7ffc3-ex")


def main(summ, out, n):
    s = json.load(open(summ))
    snap = json.load(open(f"{HERE}/impact_snapshot.json"))
    g = "G-CP1io (Cp1,Cp2->1uF), strict"
    cells = s["impact"]["cell"]["guards"][g]["names"]
    train = sorted(s["impact"]["train"]["guards"][g]["names"],
                   key=lambda x: hashlib.sha1(x.encode()).hexdigest())[:n]
    # name -> raw record path
    path = {}
    for ln in open(f"{T}/impact_seeds.jsonl"):
        r = json.loads(ln)
        nm = r["meta"].get("cell") or r["meta"].get("train")
        path[nm] = f"{T}/raw/impact/{r['sid']}.json"
    for nm, v in snap["reuse"].items():
        rid = v["record"]
        path[nm] = f"{T}/raw/seeds/{rid}.json" if rid.startswith("S") else f"{T}/raw/ext/{rid}.json"
    os.makedirs(f"{T}/raw/resize", exist_ok=True)
    with open(out, "w") as fh:
        for nm in cells + train:
            o = f"{T}/raw/resize/{nm}.io.json"
            fh.write(f"{o}\t{HERE}/envrun.sh python {HERE}/resize_cp1.py io {path[nm]} {o}\n")
    print(len(cells), "cells +", len(train), "training witnesses")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
