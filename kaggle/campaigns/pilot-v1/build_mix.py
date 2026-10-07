#!/usr/bin/env python
"""pilot-v1 M1 data mix (kaggle/PREREG-PILOT-V1.md § M1). Local; reads pilot-v0 data read-only.

  build_mix.py rat-input
        the phase-A (non-library) training examples of pilot-v0/data/train-all.jsonl
        that pilot-v0 never rationalized (= not in its nested-1000 subset) ->
        rat/rat-input-mix.jsonl. These are the only mix candidates that can be "new"
        (the new library-solvable ones are all positive rank 3, beyond the library
        quota; `build` asserts every selected example has a trace); they are
        rationalized with pilot-v0's exact rationalize kernel (same filters, <= 3 attempts).
  build_mix.py build [--rat DIR]
        selection (below) with every example that has no kept trace treated as
        unavailable (pilot-v0's 6 examples that failed 3 attempts; new examples that
        fail in the pilot-v1 rat kernel), then pilot-v0's build_sft.py `sft` on that id
        list (first kept trace per example, local re-verification of the round-trip
        token hash, reasoning length and leak filter; fence re-check) -> sft-data/
        sft-<N>.jsonl + MIX.json (composition, caps, reuse/new counts, fence).

Selection (pre-reg M1; seed 20261005 = pilot-v0 SUBSET_SEED, so the per-stratum order is
pilot-v0's own):
  - strata = band type x difficulty; within a stratum tasks are shuffled (seed) and
    examples ordered by (positive rank within task, task rank) -- pv0.py's exact code;
  - target-topology cap: at most 3 examples per canonical target WL (global);
  - phase A: ALL available non-library-solvable examples (difficulty witness-only and
    single-edit-solvable), strata in sorted order, subject to the WL cap;
  - phase B: library-solvable examples up to the 40 % cap, i.e. L = floor(2 |A| / 3)
    (L / (|A| + L) <= 0.40), allocated over band types proportionally to the
    library-solvable pool (largest remainder, as pilot-v0's allocation), filled in each
    band's stratum order subject to the WL cap (an unfillable share moves to the other
    band).
"""
import argparse
import hashlib
import json
import math
import os
import random
import sys
from collections import Counter, OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PV0 = os.path.join(REPO, "kaggle", "campaigns", "pilot-v0")
P1 = os.path.join(PV0, "P1")
DATA = os.path.join(PV0, "data")
SEED = 20261005                  # == pv0.SUBSET_SEED
WL_CAP = 3
LIB_FRAC = 0.40
LIB = "library-solvable"
PV0_RAT = [os.path.join(P1, "kernels", "rat-a", "rat"), os.path.join(P1, "kernels", "rat-b", "rat")]
PV1_RAT = os.path.join(HERE, "kernels", "rat-mix", "rat")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rj(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def load():
    exs = OrderedDict()
    for e in rj(os.path.join(DATA, "train-all.jsonl")):
        exs[e["id"]] = e
    sub = json.load(open(os.path.join(DATA, "subsets.json")))
    assert sub["seed"] == SEED
    return exs, sub["subsets"]


def stratum_order(exs):
    """pv0.py build-data's per-stratum order, verbatim (same rng sequence)."""
    rng = random.Random(SEED)
    strata = defaultdict(list)
    for e in exs.values():
        strata[(e["band_type"], e["difficulty"])].append(e)
    order = {}
    for key in sorted(strata):
        es = strata[key]
        tnames = sorted({e["task"] for e in es})
        rng.shuffle(tnames)
        rank = {tn: i for i, tn in enumerate(tnames)}
        es.sort(key=lambda e: (int(e["id"].rsplit(":", 1)[1]), rank[e["task"]]))
        order[key] = es
    return order


def check_order_matches_pv0(order, sub):
    """pilot-v0's nested-1000 must be a per-stratum prefix of this order (sanity)."""
    s1000 = set(sub["1000"])
    for key, es in order.items():
        flags = [e["id"] in s1000 for e in es]
        n = sum(flags)
        assert all(flags[:n]) and not any(flags[n:]), ("order mismatch", key)


def rat_status(rat_dirs):
    """id -> 'kept' | 'failed' over the given rationalize.jsonl dirs."""
    st = {}
    for d in rat_dirs:
        for r in rj(os.path.join(d, "rationalize.jsonl")):
            if r.get("ok"):
                st[r["id"]] = "kept"
            else:
                st.setdefault(r["id"], "failed")
    return st


def select(exs, order, unavailable):
    wl = Counter()
    A = []
    for key in sorted(order):
        if key[1] == LIB:
            continue
        for e in order[key]:
            if e["id"] in unavailable or wl[e["target_wl"]] >= WL_CAP:
                continue
            wl[e["target_wl"]] += 1
            A.append(e["id"])
    L = int(math.floor((LIB_FRAC / (1 - LIB_FRAC)) * len(A) + 1e-9))
    bands = sorted({k[0] for k in order if k[1] == LIB})
    pool = {b: len(order[(b, LIB)]) for b in bands}
    N = sum(pool.values())
    q = {b: L * pool[b] / N for b in bands}
    al = {b: int(math.floor(q[b])) for b in bands}
    for b in sorted(bands, key=lambda b: (-(q[b] - al[b]), b))[: L - sum(al.values())]:
        al[b] += 1
    alloc0 = dict(al)
    Bsel = {b: [] for b in bands}
    ptr = {b: 0 for b in bands}

    def fill(b, want):
        es = order[(b, LIB)]
        while len(Bsel[b]) < want and ptr[b] < len(es):
            e = es[ptr[b]]
            ptr[b] += 1
            if e["id"] in unavailable or wl[e["target_wl"]] >= WL_CAP:
                continue
            wl[e["target_wl"]] += 1
            Bsel[b].append(e["id"])
    for b in bands:
        fill(b, al[b])
    short = sum(al[b] - len(Bsel[b]) for b in bands)
    moved = {}
    if short:                             # an unfillable share moves to the other band
        for b in bands:
            extra = short
            before = len(Bsel[b])
            fill(b, len(Bsel[b]) + extra)
            moved[b] = len(Bsel[b]) - before
            short -= moved[b]
    Bids = [i for b in bands for i in Bsel[b]]
    meta = OrderedDict(n_A=len(A), L_cap=L, lib_alloc=alloc0, lib_got={b: len(Bsel[b]) for b in bands},
                       lib_moved=moved, n_B=len(Bids))
    return A, Bids, meta, wl


def cmd_rat_input(a):
    exs, sub = load()
    s1000 = set(sub["1000"])
    # library-solvable new examples (all positive rank 3) sit far past the library quota
    # in every band's order, so only the non-library new ones can enter the mix
    new = [e for e in exs.values() if e["id"] not in s1000 and e["difficulty"] != LIB]
    os.makedirs(os.path.join(HERE, "rat"), exist_ok=True)
    p = os.path.join(HERE, "rat", "rat-input-mix.jsonl")
    with open(p, "w") as fh:
        for e in new:
            fh.write(json.dumps({k: e[k] for k in ("id", "task", "family", "band_type", "difficulty",
                                                   "source", "messages", "target_netlist",
                                                   "completion", "target_tok", "target_wl")}) + "\n")
    # preview: which of them a selection would use if every new example were kept
    order = stratum_order(exs)
    check_order_matches_pv0(order, sub)
    st = rat_status(PV0_RAT)
    unavail = {i for i in s1000 if st.get(i) != "kept"}
    A, Bids, meta, _ = select(exs, order, unavail)
    sel = set(A) | set(Bids)
    rec = OrderedDict(train_all_sha256=sha256_file(os.path.join(DATA, "train-all.jsonl")),
                      n_new=len(new), ids=[e["id"] for e in new],
                      by_difficulty=dict(Counter(e["difficulty"] for e in new)),
                      selected_if_all_kept=sorted(i for i in sel if i not in s1000),
                      preview_selection=meta, preview_n=len(sel),
                      note="non-library examples never rationalized by pilot-v0 (not in its nested-1000)")
    json.dump(rec, open(os.path.join(HERE, "rat", "INPUT.json"), "w"), indent=1)
    print(json.dumps(rec, indent=1))


def cmd_build(a):
    exs, sub = load()
    s1000 = set(sub["1000"])
    order = stratum_order(exs)
    check_order_matches_pv0(order, sub)
    rat_dirs = PV0_RAT + [a.rat]
    st = rat_status(rat_dirs)
    unavail = {i for i in exs if st.get(i) != "kept"}
    A, Bids, meta, wl = select(exs, order, unavail)
    ids = A + Bids
    n = len(ids)
    assert len(Bids) <= LIB_FRAC * n + 1e-9, (len(Bids), n)
    assert max(wl.values()) <= WL_CAP
    os.makedirs(a.out, exist_ok=True)
    subf = os.path.join(a.out, "subset-mix.json")
    json.dump(OrderedDict(seed=SEED, method=__doc__.split("Selection")[1].strip(),
                          subsets={str(n): ids}), open(subf, "w"), indent=1)
    # pilot-v0's own trace assembly / local re-verification / fence (build_sft.py sft)
    sys.path.insert(0, P1)
    sys.path.insert(0, PV0)
    import build_sft as BS
    ns = argparse.Namespace(data=DATA, subsets=subf, rat=",".join(rat_dirs), out=a.out,
                            no_runner_fence=False)
    BS.cmd_sft(ns)
    rows = rj(os.path.join(a.out, "sft-%d.jsonl" % n))
    assert [r["id"] for r in rows] == ids, "an example lost its trace in local re-verification"
    sft1000 = {r["id"] for r in rj(os.path.join(P1, "sft-data", "sft-1000.jsonl"))}
    pv0_wl = Counter(exs[i]["target_wl"] for i in sft1000)
    E = [exs[i] for i in ids]
    tw = Counter(e["target_wl"] for e in E)
    mix = OrderedDict(
        prereg="kaggle/PREREG-PILOT-V1.md (e46157ccf) M1",
        n=n, n_tasks=len({e["task"] for e in E}), selection=meta,
        library_solvable_share=round(len(Bids) / n, 4),
        by_difficulty=dict(Counter(e["difficulty"] for e in E)),
        by_band_type=dict(Counter(e["band_type"] for e in E)),
        by_stratum=dict(Counter("%s/%s" % (e["band_type"], e["difficulty"]) for e in E)),
        by_source=dict(Counter(e["source"].split(":")[0] for e in E)),
        by_family=dict(Counter(e["family"] for e in E)),
        distinct_target_wl=len(tw), max_per_target_wl=max(tw.values()),
        per_wl_hist=dict(Counter(tw.values())),
        anchor_target_examples=sum(1 for e in E if e["source"].startswith("library")),
        reuse_rationale=sum(1 for i in ids if i in sft1000),
        new_rationalized=sum(1 for i in ids if i not in s1000),
        overlap_with_sft1000=len(set(ids) & sft1000),
        sft1000_ref=OrderedDict(n=len(sft1000), distinct_target_wl=len(pv0_wl),
                                max_per_target_wl=max(pv0_wl.values()),
                                library_solvable_share=round(sum(1 for i in sft1000 if exs[i]["difficulty"] == LIB)
                                                             / len(sft1000), 4)),
        unavailable_no_trace=sorted(i for i in unavail if i in set(ids) | s1000 or i in st),
        rat_dirs=[os.path.relpath(d, REPO) for d in rat_dirs],
        sft_file=os.path.relpath(os.path.join(a.out, "sft-%d.jsonl" % n), REPO),
        sft_sha256=sha256_file(os.path.join(a.out, "sft-%d.jsonl" % n)),
        fence="build_sft.py sft asserts: no held-out family/task/strict cell; target WL / token hash "
              "not in pv0's fence set (bench-v2 planted cells any status + held-out witnesses)",
        feasible_size_note=("WL cap alone bounds any mix from train-all at %d examples"
                            % sum(min(WL_CAP, c) for c in Counter(e["target_wl"] for e in exs.values()).values())))
    json.dump(mix, open(os.path.join(a.out, "MIX.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in mix.items() if k != "unavailable_no_trace"}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["rat-input", "build"])
    ap.add_argument("--rat", default=PV1_RAT)
    ap.add_argument("--out", default=os.path.join(HERE, "sft-data"))
    a = ap.parse_args()
    {"rat-input": cmd_rat_input, "build": cmd_build}[a.cmd](a)
