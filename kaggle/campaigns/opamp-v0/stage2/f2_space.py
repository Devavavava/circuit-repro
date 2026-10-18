"""F2' single-edit space per anchor (+ two-edit sample) -> stage2/results/f2_<anchor>.json(l).

Writes, per anchor:
  results/f2_<anchor>_counts.json   counts (raw / unique / after pre-filter, by kind; reasons)
  results/f2_<anchor>.jsonl         one line per pre-filtered unique candidate (Stage 3 screens these)
  results/two_edit_<anchor>_s<seed>.jsonl  `n` seeded two-edit designs (Stage 3 step 4)
plus self-checks: determinism (enumeration twice, identical), canonical form invariant under
renaming internal nets/devices and reordering lines, and isomorphic-variant collapse.
Usage: f2_space.py [n_two_edit=500] [seed=1]
"""
import json
import os
import random
import sys
import time

import s2common as C
from opamp_v0 import edits as E, dialect as DL


def rename_check(text, seed=7):
    """Canonical key must be invariant under internal-net renaming, device renaming that keeps
    the group partition, and line order."""
    devs = DL.parse(text)
    rng = random.Random(seed)
    internal = [n for n in DL.nets_of(devs) if n not in DL.SPECIAL]
    newn = ["q%d" % i for i in range(len(internal))]
    rng.shuffle(newn)
    nm = dict(zip(internal, newn))
    groups = DL.groups(devs)
    gnames = {g: "Z%d" % (i + 1) for i, g in enumerate(rng.sample(list(groups), len(groups)))}
    out = []
    for g, mem in groups.items():
        for j, d in enumerate(mem):
            name = gnames[g] + ("abcdefghijklmnopqrstuvwxyz"[j] if len(mem) > 1 else "")
            out.append(DL.Device(d.type, name, [nm.get(n, n) for n in d.nets]))
    rng.shuffle(out)
    return E.canon_key(devs) == E.canon_key(out)


def main():
    n2 = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    allc = {}
    for a in C.ANCHORS:
        t0 = time.time()
        text = C.circuit_text(a)
        r = E.f2prime(text)
        r2 = E.f2prime(text)
        det = [c["key"] for c in r["candidates"]] == [c["key"] for c in r2["candidates"]]
        checks = {"deterministic": det,
                  "rename_invariant_anchor": all(rename_check(text, s) for s in range(5)),
                  "rename_invariant_sample": all(rename_check(c["netlist"], 11 + i)
                                                 for i, c in enumerate(r["ok"][::50]))}
        ok = r["ok"]
        with open(os.path.join(C.RESULTS, "f2_%s.jsonl" % a), "w") as fh:
            for c in ok:
                fh.write(json.dumps({k: c[k] for k in ("i", "edit", "kind", "key", "netlist")},
                                    sort_keys=True) + "\n")
        two, st = E.two_edit_sample(text, n2, seed, exclude_keys=r["all_keys"])
        two_b, _ = E.two_edit_sample(text, n2, seed, exclude_keys=r["all_keys"])
        checks["two_edit_deterministic"] = [x["key"] for x in two] == [x["key"] for x in two_b]
        with open(os.path.join(C.RESULTS, "two_edit_%s_s%d.jsonl" % (a, seed)), "w") as fh:
            for x in two:
                fh.write(json.dumps(x, sort_keys=True) + "\n")
        kinds2 = {}
        for x in two:
            k = "+".join(sorted((x["edits"][0][0], x["edits"][1][0])))
            kinds2[k] = kinds2.get(k, 0) + 1
        out = {"anchor": a, "anchor_key": r["anchor_key"], "counts": r["counts"], "checks": checks,
               "two_edit": {"n": n2, "seed": seed, "stats": st, "by_kind_pair": kinds2},
               "secs": time.time() - t0}
        with open(os.path.join(C.RESULTS, "f2_%s_counts.json" % a), "w") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
        allc[a] = out
        print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
