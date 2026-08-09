"""Flip-check every adopt/reject decision under ref-v3, and re-freeze the baselines.

Reads the table `lna/_ndl_refv3.py` wrote and replays the adopt-only-if-better
rule the program actually used at each point in its history: a candidate is
adopted iff its NDL@256 beats **the then-current baseline** (not the best-ever),
at equal-or-better inductor ratio. Then prints the ref-v2 -> ref-v3 old/new table
and the re-frozen baselines.

Note the direction of the guarantee, which is what makes the missing P2 pool
survivable: ref-v3 is a strict superset of ref-v2 (nine hashes added, nothing
removed), and adding hashes can only ever *remove* items from the novel set, so
`NDL_v3(X) <= NDL_v2(X)` for every X. A bound is often enough to settle a
comparison outright.

    python lna/_ndl_flipcheck.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

JSON = os.path.join(HERE, "out", "_ingest", "ndl_refv3.json")

# (label, candidate, baseline-at-the-time, historical verdict). P2's pool is lost
# (`ft_p2.pth` is gone and its seq files were gitignored), so decisions 1 and 2
# are settled by the monotonicity bound rather than by measurement -- exactly as
# in FINDINGS §14.5, and stated as such.
DECISIONS = [
    ("prefix-12 baseline -> P2", "P2", "P0 prefix-12", "ADOPT"),
    ("P2 -> P5-v1", "P5-v1", "P2", "ADOPT"),
    ("P5-v1 -> P5-v2", "P5-v2", "P5-v1", "ADOPT"),
    ("P5-v2 -> P5-v3", "P5-v3 (adopted)", "P5-v2", "ADOPT"),
    ("P5-v3 vs P5-v4", "P5-v4", "P5-v3 (adopted)", "reject"),
    ("P5-v3 vs P5-v5", "P5-v5", "P5-v3 (adopted)", "reject"),
    ("P5-v3 vs P5-v6", "P5-v6", "P5-v3 (adopted)", "reject"),
]
# P2's ref-v1 number, the only thing that survives of it.
P2_NDL_V1 = 24


def main():
    blob = json.load(open(JSON, encoding="utf-8"))
    refs = blob["refs"]
    by = {r["label"]: r for r in blob["rows"]}

    def ndl(label, ref):
        if label == "P2":
            return None
        r = by.get(label)
        return r["by_ref"][ref]["ndl"] if r else None

    def indr(label, ref):
        r = by.get(label)
        return r["by_ref"][ref]["ind_ratio"] if r else None

    print("== old -> new (frozen NDL@256 protocol, same pools, ref moves only) ==")
    print(f"  {'checkpoint':<20} {'ref-v1':>7} {'ref-v2':>7} {'ref-v3':>7} "
          f"{'d(v3-v2)':>9} {'indR':>7}")
    for r in blob["rows"]:
        lab = r["label"]
        v1, v2, v3 = (ndl(lab, x) for x in ("ref-v1", "ref-v2", "ref-v3"))
        print(f"  {lab:<20} {v1:>7} {v2:>7} {v3:>7} {v3 - v2:>+9} "
              f"{indr(lab, 'ref-v3'):>7.3f}")

    print("\n== flip check: every adopt/reject decision, re-scored ==")
    print(f"  {'#':>2} {'decision':<26} {'ref-v2':>12} {'ref-v3':>12} "
          f"{'verdict':>8}  flips?")
    flips = 0
    for i, (name, cand, base, hist) in enumerate(DECISIONS, 1):
        c2, b2 = ndl(cand, "ref-v2"), ndl(base, "ref-v2")
        c3, b3 = ndl(cand, "ref-v3"), ndl(base, "ref-v3")
        if cand == "P2" or base == "P2":
            # bound only: NDL_v3(P2) <= NDL_v1(P2) = 24
            if base == "P2":
                ok3 = c3 > P2_NDL_V1 or c3 >= P2_NDL_V1
                shown3 = f"{c3} vs <={P2_NDL_V1}"
                proved = c3 > P2_NDL_V1
            else:
                ok3 = True
                shown3 = f"<={P2_NDL_V1} vs {b3}"
                proved = False
            new = "ADOPT" if ok3 else "reject"
            flip = new.lower() != hist.lower()
            print(f"  {i:>2} {name:<26} {'(pool lost)':>12} {shown3:>12} "
                  f"{new:>8}  {'YES' if flip else 'no'}"
                  f"{'  (proved by the bound)' if proved else '  (inferred)'}")
        else:
            new = "ADOPT" if c3 > b3 else "reject"
            old = "ADOPT" if c2 > b2 else "reject"
            flip = new != old
            flips += flip
            print(f"  {i:>2} {name:<26} {f'{c2} vs {b2}':>12} "
                  f"{f'{c3} vs {b3}':>12} {new:>8}  {'YES' if flip else 'no'}")

    print(f"\n  decisions that flip under ref-v3: {flips}")

    print("\n== ordering (the thing §14.5 warned is NOT guaranteed) ==")
    for ref in refs:
        order = sorted(((ndl(r["label"], ref), r["label"]) for r in blob["rows"]
                        if r["spec"] == "wifi24" and r["label"] != "P0 prefix-12"),
                       reverse=True)
        print(f"  {ref}: " + "  >  ".join(f"{lab.split(' ')[0]} {n}"
                                          for n, lab in order))

    print("\n== RE-FROZEN BASELINES (adopt-only-if-better, ref-v3) ==")
    nb = by["P5-v3 (adopted)"]["by_ref"]["ref-v3"]
    wb = by["P5-v3 wb (adopted)"]["by_ref"]["ref-v3"]
    nb2 = by["P5-v3 (adopted)"]["by_ref"]["ref-v2"]
    wb2 = by["P5-v3 wb (adopted)"]["by_ref"]["ref-v2"]
    print(f"  nb  NDL@256 = {nb['ndl']} (was {nb2['ndl']} under ref-v2) "
          f"at inductor ratio {nb['ind_ratio']:.3f}   {nb['ref_tag']}")
    print(f"  wb  NDL@256 = {wb['ndl']} (was {wb2['ndl']} under ref-v2) "
          f"at inductor ratio {wb['ind_ratio']:.3f}   {wb['ref_tag']}")


if __name__ == "__main__":
    main()
