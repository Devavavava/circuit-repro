#!/usr/bin/env python
"""bench-v2 generation pipeline (pre-registered in kaggle/PREREG-BENCH-V2.md, e5bfd0755).

One detached scheduler process drives everything; each sizing call is one worker
SUBPROCESS running the fixed verifier

    bench_anchor_prep.smoke_run(tokens, spec, seed, 2500, "bptm45", profile="rl-v1")

on an rl-v1-form spec. Stages (see README.md for the full design):

  CAL    anchors a1-a5 x every grid point (probe spec) x seeds {1,2}: the anchor
         design pool used for dominance scoring / pre-kills.
  SEARCH per stream (bench | train), generational guided search over edit scripts
         of 2-4 primitive edits (add R/C/L/NMOS/PMOS between existing or new nets,
         delete, rewire one terminal) applied to an anchor, each followed by the
         deterministic repair pass; sized at seed 1 under the grid point's loose
         probe spec. Parents = tournament over the best-scoring archive
         (mutate-then-repair); plus fresh random scripts and cross-grid transfer.
  PLANT  feasible candidate -> spec = achieved metrics relaxed by the 2% cushion
         (rl-v1 form). Bench: only if no recorded anchor design (or recorded single
         edit of the parent) already satisfies it (else logged PRE-KILL).
  CELL   (bench) A1 witness seeds {1,2,3} >=2 feasible -> F1 anchors a1-a5 x {1,2}
         -> A2 tightened-2% >=1 of {1,2,3} + A3 fresh >=1 of {4,5,6} -> F2 every
         single edit (E-c space) of the parent anchor x {1,2}. Every outcome logged.
  TRAIN  (train stream; disjoint grid points, separate RNG) witness re-size {1,2}
         >=1 feasible, difficulty label (library-solvable / single-edit-solvable /
         witness-only), no F2.
  FINAL  class-capped selection of 20-25 cells -> kaggle/editcap-lib-v2/, training
         pool -> kaggle/train-pool-v2/, fence check.

usage (always via envrun.sh):
  bv2.py run   --mode full|smoke [--run-dir DIR]   # scheduler (resumable)
  bv2.py worker JOB.json OUT.json                  # one sizing call
  bv2.py finalize --mode full|smoke [--run-dir DIR]
  bv2.py status [--run-dir DIR]
"""
import argparse
import copy
import hashlib
import itertools
import json
import math
import os
import random
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter, OrderedDict, defaultdict

REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
CAMP = f"{REPO}/kaggle/campaigns/bench-v2"
for _p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PDK = "bptm45"
BUDGET = 2500
PROFILE = "rl-v1"
DELTA = 0.02                      # cushion (planting) == tightening (acceptance)
WORKER_TIMEOUT_S = 3600

ANCH_DIR = f"{REPO}/kaggle/bench-anchors"
ANCHORS = OrderedDict([
    ("a1", "lna-a1-inddegen-cascode"), ("a2", "lna-a2-current-reuse"),
    ("a3", "lna-a3-shunt-feedback"), ("a4", "lna-a4-twostage"),
    ("a5", "lna-a5-commongate")])
# DEVIATION D1 (README): a1/a4 carry 3 inductors -> topology-rejected (0 evals) by
# every wideband rl-v1 spec (max_inductors 2), so they cannot be a SHOWN wideband
# anchor with sized failure evidence; wideband witnesses derive from a2/a3/a5.
PARENTS = {"wideband": ["a2", "a3", "a5"],
           "narrowband": ["a1", "a2", "a3", "a4", "a5"]}

# declared band grid (pre-reg) x objective flavor = spec grid points
BANDS = OrderedDict([
    ("wb0530", ("wideband", 5e8, 3e9)), ("wb0824", ("wideband", 8e8, 2.4e9)),
    ("wb1020", ("wideband", 1e9, 2e9)),
    ("nb090", ("narrowband", 0.9e9)), ("nb158", ("narrowband", 1.575e9)),
    ("nb240", ("narrowband", 2.4e9)), ("nb350", ("narrowband", 3.5e9))])
FLAVORS = ["noise", "gain", "power"]
GRID = [(b, f) for b in BANDS for f in FLAVORS]


def grid_split(g):
    bi, fi = list(BANDS).index(g[0]), FLAVORS.index(g[1])
    return "bench" if (bi + fi) % 2 == 0 else "train"


def gkey(g):
    return f"{g[0]}-{g[1]}"


# performance constraints per band type: metric -> "max"/"min"
CONS = {"wideband": OrderedDict([("nf_max_db", "max"), ("s11_max_db", "max"),
                                 ("s21_db", "min"), ("s21_ripple_db", "max"),
                                 ("idd_ma", "max")]),
        "narrowband": OrderedDict([("nf_db", "max"), ("s11_max_db", "max"),
                                   ("s21_db", "min"), ("idd_ma", "max")])}
# loose probe spec per band type (quality floor of any planted cell)
PROBE = {"wideband": {"nf_max_db": 4.5, "s11_max_db": -8.0, "s21_db": 8.0,
                      "s21_ripple_db": 3.0, "idd_ma": 12.0},
         "narrowband": {"nf_db": 2.5, "s11_max_db": -8.0, "s21_db": 10.0,
                        "idd_ma": 6.0}}
FLAVOR_W = {"noise": {"nf": 1.0, "s21_db": 0.5, "idd_ma": 0.5},
            "gain": {"s21_db": 1.0, "nf": 0.5, "idd_ma": 0.5},
            "power": {"idd_ma": 1.0, "nf": 0.5, "s21_db": 0.5}}

MOVE_CLASSES = ["cascode", "current-reuse", "added-stage", "feedback",
                "degeneration", "L-match", "input-match", "tank-load", "other"]
_LABEL_PRIO = ["cascode", "current-reuse", "added-stage", "gm-boost", "cg-input",
               "feedback", "degeneration", "L-match", "input-match", "tank-load",
               "other-active", "removal", "other-passive"]
_LABEL_TO_CLASS = {"gm-boost": "added-stage", "cg-input": "other",
                   "other-active": "other", "removal": "other",
                   "other-passive": "other"}

# ------------------------------------------------------------------- configs
CONFIGS = {
    "full": dict(
        run_dir=f"{CAMP}/run", stream_seed={"bench": 20260929_01, "train": 20260929_02},
        cal_seeds=(1, 2), gen_size={"bench": 6, "train": 4},
        max_gens={"bench": 100000, "train": 100000},
        bench_target=25, bench_min=20, cap_frac=0.25, cap_build=6,
        train_target=300, train_quota_per_point=32,
        max_active_val=8, f2_chunk=16, f2_limit=None,
        max_procs=8, throttle_procs=4, load_thresh=22.0,
        search_min_slots=3, train_min_slots=2,
        bench_max_hours=84.0, total_max_hours=118.0, grid_only=None),
    "smoke": dict(
        run_dir=f"{CAMP}/smoke/run", stream_seed={"bench": 777_01, "train": 777_02},
        cal_seeds=(1,), gen_size={"bench": 6, "train": 4},
        max_gens={"bench": 3, "train": 2},
        bench_target=1, bench_min=1, cap_frac=1.0, cap_build=1,
        train_target=2, train_quota_per_point=2,
        max_active_val=3, f2_chunk=8, f2_limit=12,     # SMOKE: F2 SUBSET (first 12)
        smoke_force=True,          # SMOKE: run every stage even after a kill
        max_procs=8, throttle_procs=4, load_thresh=22.0,
        search_min_slots=3, train_min_slots=1,
        bench_max_hours=3.0, total_max_hours=4.0,
        grid_only={"bench": [("nb240", "gain")], "train": [("nb158", "gain")]}),
}


def sha(s, n=16):
    return hashlib.sha1(s.encode() if isinstance(s, str) else s).hexdigest()[:n]


def tokhash(tokens):
    return sha(json.dumps(list(tokens)))         # E-d / R1 key sha1(json(tokens))[:16]


def jdump(o):
    return json.dumps(o, default=repr, sort_keys=False)


def atomic_write(path, text):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


def era_stamp():
    try:
        head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    except Exception:                                            # noqa: BLE001
        head = "unknown"
    md5 = {}
    for f in ("kaggle/bench_anchor_prep.py", "kaggle/campaigns/bench-v2/bv2.py"):
        try:
            md5[f] = hashlib.md5(open(f"{REPO}/{f}", "rb").read()).hexdigest()[:10]
        except OSError:
            md5[f] = None
    return {"git": head, "md5": md5}


def load1():
    try:
        return float(open("/proc/loadavg").read().split()[0])
    except Exception:                                            # noqa: BLE001
        return 0.0


# ------------------------------------------------------------------ netlists
def parse_net(text):
    el = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s[0] in "#*":
            continue
        p = s.split()
        el.append([p[0].upper()] + p[1:])
    return el


def net_text(el):
    return "\n".join(" ".join(e) for e in el) + "\n"


def is_mos(e):
    return e[0] in ("NMOS", "PMOS")


def nets_of(el):
    return sorted({n for e in el for n in e[2:]})


RAILS = {"VDD", "VSS"}
PORTS = {"VDD", "VSS", "VIN1", "VOUT1"}


def anchor_data():
    m = json.load(open(f"{ANCH_DIR}/MANIFEST.json"))["classes"]["lna"]["families"]
    out = OrderedDict()
    for k, fam in ANCHORS.items():
        net = open(f"{REPO}/{m[fam]['net_file']}").read()
        tok = json.load(open(f"{REPO}/{m[fam]['tokens_file']}"))
        out[k] = {"family": fam, "net_file": m[fam]["net_file"],
                  "tokens_file": m[fam]["tokens_file"], "text": net,
                  "elems": parse_net(net), "tokens": tok, "tok": tokhash(tok),
                  "wl": m[fam]["wl_hash"]}
    return out


# --------------------------------------------------------------- edit scripts
class Bad(Exception):
    pass


def apply_script(base, script):
    el = [list(e) for e in base]
    for op in script:
        if op["op"] == "add":
            if any(e[1] == op["name"] for e in el):
                raise Bad("dup name")
            el.append([op["t"], op["name"]] + list(op["nets"]))
        elif op["op"] == "del":
            i = next((i for i, e in enumerate(el) if e[1] == op["name"]), None)
            if i is None:
                raise Bad("del missing")
            el.pop(i)
        elif op["op"] == "rw":
            e = next((e for e in el if e[1] == op["name"]), None)
            if e is None:
                raise Bad("rw missing")
            npin = 3 if is_mos(e) else 2
            if op["pin"] >= npin:
                raise Bad("rw pin")
            if e[2 + op["pin"]] == op["net"]:
                raise Bad("rw noop")
            e[2 + op["pin"]] = op["net"]
        else:
            raise Bad("op")
    if not el:
        raise Bad("empty")
    return el


def _fresh(script, prefix):
    used = set()
    for op in script:
        if "name" in op:
            used.add(op["name"])
        for n in op.get("nets", []) + ([op["net"]] if "net" in op else []):
            used.add(n)
    k = 1
    while f"{prefix}{k}" in used:
        k += 1
    return f"{prefix}{k}"


def sample_group(rng, el, script, room, grp):
    """One primitive edit (or a 2-primitive composite: series insert = rewire to a
    new net + passive back to the old net; stack = rewire a MOS D/S to a new net
    + a MOS channel between old and new net). Returns [op...] or None."""
    nets = nets_of(el)
    kinds = [("addp", 0.30), ("addm", 0.12), ("del", 0.14), ("rw", 0.14)]
    if room >= 2:
        kinds += [("ser", 0.15), ("stk", 0.15)]
    tot = sum(w for _k, w in kinds)
    r, acc, kind = rng.random() * tot, 0.0, kinds[-1][0]
    for k, w in kinds:
        acc += w
        if r <= acc:
            kind = k
            break
    sc = script

    def nm(t):
        return _fresh(sc, "Z" + {"NMOS": "N", "PMOS": "P"}.get(t, t))

    if kind == "addp":
        if len(nets) < 2:
            return None
        t = rng.choice("RCL")
        a, b = rng.sample(nets, 2)
        return [{"op": "add", "t": t, "name": nm(t), "nets": [a, b], "grp": grp}]
    if kind == "addm":
        t = rng.choice(["NMOS", "PMOS"])
        d, g, s = rng.choice(nets), rng.choice(nets), rng.choice(nets)
        if d == s or g == s:
            return None
        return [{"op": "add", "t": t, "name": nm(t),
                 "nets": [d, g, s, "VSS" if t == "NMOS" else "VDD"], "grp": grp}]
    if kind == "del":
        e = rng.choice(el)
        return [{"op": "del", "name": e[1], "grp": grp}]
    if kind == "rw":
        e = rng.choice(el)
        pin = rng.randrange(3 if is_mos(e) else 2)
        cand = [n for n in nets if n != e[2 + pin]]
        return [{"op": "rw", "name": e[1], "pin": pin, "net": rng.choice(cand),
                 "grp": grp}]
    if kind == "ser":
        e = rng.choice(el)
        pin = rng.randrange(3 if is_mos(e) else 2)
        old = e[2 + pin]
        x = _fresh(sc, "x")
        t = rng.choice("RCL")
        return [{"op": "rw", "name": e[1], "pin": pin, "net": x, "grp": grp,
                 "macro": "ser"},
                {"op": "add", "t": t, "name": nm(t), "nets": [x, old], "grp": grp,
                 "macro": "ser"}]
    if kind == "stk":
        mos = [e for e in el if is_mos(e)]
        if not mos:
            return None
        m = rng.choice(mos)
        pin = rng.choice([0, 2])
        old = m[2 + pin]
        x = _fresh(sc, "x")
        t = m[0] if rng.random() < 0.75 else ("PMOS" if m[0] == "NMOS" else "NMOS")
        g = rng.choice(nets)
        nd, ns = (old, x) if pin == 0 else (x, old)
        if m[0] == "PMOS":
            nd, ns = ns, nd
        if t != m[0]:
            nd, ns = ns, nd
        if g == ns:
            return None
        return [{"op": "rw", "name": m[1], "pin": pin, "net": x, "grp": grp,
                 "macro": "stk"},
                {"op": "add", "t": t, "name": nm(t),
                 "nets": [nd, g, ns, "VSS" if t == "NMOS" else "VDD"], "grp": grp,
                 "macro": "stk"}]
    return None


def random_script(rng, base, kmax=4):
    k = rng.choices([2, 3, 4], weights=[0.45, 0.35, 0.20])[0]
    k = min(k, kmax)
    script, grp = [], 0
    for _ in range(40):
        if len(script) >= k:
            break
        try:
            el = apply_script(base, script)
        except Bad:
            return None
        g = sample_group(rng, el, script, k - len(script), grp)
        if not g:
            continue
        try:
            apply_script(base, script + g)
        except Bad:
            continue
        script += g
        grp += 1
    return script if 2 <= len(script) <= 4 else None


def mutate_script(rng, base, parent):
    groups = OrderedDict()
    for op in parent:
        groups.setdefault(op["grp"], []).append(op)
    gids = list(groups)
    n = len(parent)
    moves = []
    if n < 4:
        moves.append("append")
    moves.append("replace")
    if len(gids) > 1:
        moves.append("drop")
    mv = rng.choice(moves)
    nextg = max(gids) + 1
    if mv == "append":
        base_s = [dict(o) for o in parent]
    else:
        drop = rng.choice(gids)
        base_s = [dict(o) for o in parent if o["grp"] != drop]
    try:
        el = apply_script(base, base_s)
    except Bad:
        return None, mv
    if mv == "drop":
        return (base_s if len(base_s) >= 2 else None), mv
    room = 4 - len(base_s)
    if room <= 0:
        return None, mv
    g = sample_group(rng, el, base_s, room, nextg)
    if not g:
        return None, mv
    s = base_s + g
    try:
        apply_script(base, s)
    except Bad:
        return None, mv
    return (s if 2 <= len(s) <= 4 else None), mv


# ------------------------------------------------------------------- repair
def _dc_adj(el):
    adj = defaultdict(set)
    for e in el:
        if e[0] in ("R", "L"):
            a, b = e[2], e[3]
        elif is_mos(e):
            a, b = e[2], e[4]
        else:
            continue
        adj[a].add(b)
        adj[b].add(a)
    return adj


def _reach(adj, s, skip):
    seen, st = {s}, [s]
    while st:
        u = st.pop()
        for w in adj[u]:
            if (u, w) in skip or w in seen:
                continue
            seen.add(w)
            st.append(w)
    return seen


def repair(el):
    """Deterministic repair pass. Returns (elems, repairs) or raises Bad(reason).
      1. prune: a passive with a terminal on a non-port node touched by no other
         pin is dead weight -> removed (iterated);
      2. floating-node completion: a MOS whose channel has no DC path rail-to-rail
         gets a return resistor on the missing side (NMOS: source->VSS, drain->VDD;
         PMOS mirrored), the explicit form of lna/bias.py's v3 R-SOURCE/R-DRAIN
         rules (gate bias itself is left to insert_bias inside smoke_run);
      3. reject incoherent: remaining dangling MOS pin / no DC path / missing port."""
    el = [list(e) for e in el]
    reps = []
    for _ in range(20):
        cnt = Counter(n for e in el for n in (e[2:5] if is_mos(e) else e[2:]))
        dead = [e for e in el if not is_mos(e)
                and any(cnt[n] == 1 and n not in PORTS for n in e[2:])]
        if not dead:
            break
        for e in dead:
            el.remove(e)
            reps.append({"repair": "prune", "name": e[1]})
    cnt = Counter(n for e in el for n in (e[2:5] if is_mos(e) else e[2:]))
    for e in el:
        if is_mos(e) and any(cnt[n] == 1 and n not in PORTS for n in e[2:5]):
            raise Bad("dangling_mos_pin")
    k = 0
    for _ in range(4):
        adj = _dc_adj(el)
        bad = None
        for e in el:
            if not is_mos(e):
                continue
            d, s = e[2], e[4]
            skip = {(d, s), (s, d)}
            ra, rb = _reach(adj, d, skip), _reach(adj, s, skip)
            if (("VDD" in ra and "VSS" in rb) or ("VSS" in ra and "VDD" in rb)):
                continue
            bad = e
            break
        if bad is None:
            break
        d, s = bad[2], bad[4]
        hi, lo = ("VDD", "VSS") if bad[0] == "NMOS" else ("VSS", "VDD")
        skip = {(d, s), (s, d)}
        ra, rb = _reach(adj, d, skip), _reach(adj, s, skip)
        added = False
        if lo not in rb and s not in RAILS:
            k += 1
            el.append(["R", f"Rrep{k}", s, lo])
            reps.append({"repair": "dc_return", "name": f"Rrep{k}", "nets": [s, lo],
                         "for": bad[1]})
            added = True
        if hi not in ra and d not in RAILS:
            k += 1
            el.append(["R", f"Rrep{k}", d, hi])
            reps.append({"repair": "dc_feed", "name": f"Rrep{k}", "nets": [d, hi],
                         "for": bad[1]})
            added = True
        if not added:
            raise Bad("no_dc_path")
    else:
        raise Bad("no_dc_path")
    nets = set(nets_of(el))
    if "VIN1" not in nets or "VOUT1" not in nets:
        raise Bad("missing_port")
    if not any(is_mos(e) for e in el):
        raise Bad("no_mos")
    return el, reps


# ------------------------------------------------------------ move classes
def _roles(el):
    mos = [e for e in el if is_mos(e)]
    diode = {e[2] for e in mos if e[2] == e[3]}         # bias (diode) nets
    drains = {e[2] for e in mos} - RAILS - diode
    gates = {e[3] for e in mos} - RAILS
    sources = {e[4] for e in mos} - RAILS
    padj = defaultdict(set)
    for e in el:
        if not is_mos(e):
            padj[e[2]].add(e[3])
            padj[e[3]].add(e[2])

    def side(start):
        seen, st = {start}, [start]
        while st:
            u = st.pop()
            for w in padj[u]:
                if w in RAILS or w in seen:
                    continue
                seen.add(w)
                st.append(w)
        return seen
    return {"mos": mos, "drains": drains, "gates": gates, "sources": sources,
            "in": side("VIN1"), "out": side("VOUT1")}


def _label_dev(e, R):
    if not is_mos(e):
        a, b = e[2], e[3]
        rails = {a, b} & RAILS
        ins = lambda n: n in R["in"] or n in R["gates"]            # noqa: E731
        outs = lambda n: n in R["out"] or n in R["drains"]         # noqa: E731
        if not rails and ((ins(a) and outs(b)) or (ins(b) and outs(a))) \
                and not ({a, b} <= R["in"]) and not ({a, b} <= R["out"]):
            return "feedback"
        if rails and ({a, b} - RAILS) & R["sources"]:
            return "degeneration"
        if e[0] == "L" and ({a, b} & R["in"]):
            return "L-match"
        if {a, b} & R["in"]:
            return "input-match"
        if {a, b} & (R["drains"] | R["out"]):
            return "tank-load"
        return "other-passive"
    d, g, s = e[2], e[3], e[4]
    same = [m for m in R["mos"] if m is not e and m[0] == e[0]]
    opp = [m for m in R["mos"] if m is not e and m[0] != e[0]]
    series = any(s == m[2] or d == m[4] for m in same if s not in RAILS or d not in RAILS)
    if series and (g in RAILS or g not in (R["in"] | R["drains"] | R["out"])):
        return "cascode"
    if any(d == m[2] and d not in RAILS for m in opp) and (g in R["in"] or g in R["gates"]):
        return "current-reuse"
    if g in (R["drains"] | R["out"]) and g not in R["in"]:
        return "added-stage"
    if g in R["in"] and d in (R["drains"] | R["out"]):
        return "gm-boost"
    if s in R["in"]:
        return "cg-input"
    if series:
        return "cascode"
    return "other-active"


def label_script(base, script, final_el, inert_tok=None):
    """Automatic move-class label (pre-reg Diversity). Per edit: classify the
    added/rewired device by its role in the FINAL netlist (nets on the input side,
    MOS drains/gates/sources, output side); deletions -> removal. Script class =
    highest-priority per-edit label (_LABEL_PRIO), ignoring added passives the
    witness's verifier run found INERT (VERIFY_INERT_COUNT) when known."""
    R = _roles(final_el)
    byname = {e[1]: e for e in final_el}
    labels = []
    for op in script:
        if op["op"] == "del":
            labels.append({"op": "del", "name": op["name"], "label": "removal"})
            continue
        e = byname.get(op["name"])
        if e is None:
            labels.append({"op": op["op"], "name": op["name"], "label": "removal"})
            continue
        lab = _label_dev(e, R)
        tn = _tokname(final_el, op["name"])
        inert = bool(inert_tok and tn and tn in inert_tok)
        labels.append({"op": op["op"], "name": op["name"], "label": lab,
                       "tok": tn, "inert": inert})
    live = [x["label"] for x in labels if not x.get("inert")] or \
        [x["label"] for x in labels]
    top = min(live, key=_LABEL_PRIO.index) if live else "other-passive"
    return _LABEL_TO_CLASS.get(top, top), top, labels


def _tokname(el, name):
    """AnalogGenie tokenizer names devices TYPEPREFIX + index in netlist row order
    per type (verified: 5th R row -> R5)."""
    pre = {"NMOS": "NM", "PMOS": "PM", "R": "R", "C": "C", "L": "L"}
    k = Counter()
    for e in el:
        k[e[0]] += 1
        if e[1] == name:
            return f"{pre[e[0]]}{k[e[0]]}"
    return None


def inert_toknames(res):
    out = set()
    for p in (res or {}).get("inert_devices") or []:
        if isinstance(p, str) and p.startswith("p") and p.endswith("V"):
            out.add(p[1:-1])
    return out


# --------------------------------------------------------------------- specs
def band_dict(b):
    bt = BANDS[b]
    if bt[0] == "wideband":
        lo, hi = bt[1], bt[2]
        return {"type": "wideband", "f0": math.sqrt(lo * hi), "f_lo": lo, "f_hi": hi}
    f0 = bt[1]
    return {"type": "narrowband", "f0": f0, "f_lo": f0 * 0.98, "f_hi": f0 * 1.02}


def make_spec(g, limits, name, description):
    b, fl = g
    bt = BANDS[b][0]
    nfm = "nf_max_db" if bt == "wideband" else "nf_db"
    cons = OrderedDict()
    for m, side in CONS[bt].items():
        cons[m] = {side: float(limits[m])}
    cons["iip3_dbm"] = {"min": 5 if bt == "wideband" else -10, "status": "unsupported"}
    cons["mu_min"] = {"min": 1.0}
    w = FLAVOR_W[fl]
    objs = [{"direction": "min", "metric": nfm, "weight": w["nf"]},
            {"direction": "max", "metric": "s21_db", "weight": w["s21_db"]},
            {"direction": "min", "metric": "idd_ma", "weight": w["idd_ma"]}]
    objs.sort(key=lambda o: -o["weight"])
    topo = {"allow_inductorless": bt == "wideband", "device_budget": [3, 16],
            "differential": False, "l_max": 1e-08 if bt == "wideband" else 1.5e-08,
            "l_min": 3e-10, "max_inductors": 2 if bt == "wideband" else 4,
            "reject_floating": True}
    return OrderedDict([
        ("band", band_dict(b)), ("constraints", dict(cons)),
        ("description", description), ("name", name), ("objectives", objs),
        ("pdk", PDK), ("ports", {"input": "VIN1", "output": "VOUT1", "z0": 50}),
        ("process", {"models": "AutoCkt/repo/eval_engines/ngspice/ngspice_inputs/"
                               "spice_models/45nm_bulk.txt", "temp": 27, "vdd": 1.1}),
        ("sizing", {"c_f": [5e-14, 1e-11], "l_fixed": 4.5e-08,
                    "r_ohm": [50, 20000.0], "vb_v": [0.2, 0.9], "w_um": [1, 200]}),
        ("topology", topo)])


def write_spec(path, d):
    import yaml
    from spec import Spec
    import bench_anchor_prep as PREP
    txt = yaml.safe_dump(json.loads(json.dumps(d)), sort_keys=False)
    if not (os.path.exists(path) and open(path).read() == txt):
        atomic_write(path, txt)
    sp = Spec.load(path)
    iss = PREP.rl_v1_issues(sp)
    assert not iss, (path, iss)
    return path


_SPEC_SHA = {}


def spec_sha(path):
    k = (path, os.path.getmtime(path))
    if k not in _SPEC_SHA:
        import yaml
        d = yaml.safe_load(open(path))
        d.pop("name", None)
        d.pop("description", None)
        _SPEC_SHA[k] = sha(json.dumps(d, sort_keys=True), 16)
    return _SPEC_SHA[k]


_SPEC_OBJ = {}


def sizing_spec(path):
    k = (path, os.path.getmtime(path))
    if k not in _SPEC_OBJ:
        import size as SZ
        _SPEC_OBJ[k] = SZ._spec_for_sizing(path, nf_gate=None, pdk=PDK)
    return _SPEC_OBJ[k]


def _relax(a, side):
    """The limit L whose pre-reg tightening (L -/+ DELTA * max(|L|, 1)) is exactly
    the achieved value a, i.e. the 2% cushion measured on the constraint scale."""
    if side == "max":                       # L - DELTA*max(|L|,1) = a
        for L in (a / (1 - DELTA), a / (1 + DELTA), a + DELTA):
            if (L >= 1 and abs(L - DELTA * L - a) < 1e-12) or \
               (L <= -1 and abs(L + DELTA * L - a) < 1e-12) or \
               (abs(L) < 1 and abs(L - DELTA - a) < 1e-12):
                return L
    else:                                   # L + DELTA*max(|L|,1) = a
        for L in (a / (1 + DELTA), a / (1 - DELTA), a - DELTA):
            if (L >= 1 and abs(L + DELTA * L - a) < 1e-12) or \
               (L <= -1 and abs(L - DELTA * L - a) < 1e-12) or \
               (abs(L) < 1 and abs(L + DELTA - a) < 1e-12):
                return L
    raise ValueError((a, side))


def planted_limits(bt, metrics):
    """limit_k = achieved_k relaxed by the cushion DELTA on the constraint scale
    (Spec._scale = max(|limit|,1)), rounded outward to 1e-4: so the pre-reg
    tightened-2% copy of the planted spec sits at (1e-4 outside) the witness's
    own achieved point."""
    out = {}
    for m, side in CONS[bt].items():
        L = _relax(float(metrics[m]), side)
        out[m] = (math.ceil(L * 1e4 - 1e-9) / 1e4 if side == "max"
                  else math.floor(L * 1e4 + 1e-9) / 1e4)
    return out


def tightened_limits(bt, limits):
    """every performance limit moved inward by DELTA * Spec._scale(limit) (E-a
    convention); mu_min NOT tightened (pre-reg)."""
    out = {}
    for m, side in CONS[bt].items():
        L = float(limits[m])
        sc = max(abs(L), 1.0)
        out[m] = L - DELTA * sc if side == "max" else L + DELTA * sc
    return out


def satisfies(metrics, stab_ok, bt, limits):
    """Does a recorded design (winner metrics of some verifier run) meet `limits`
    + mu_min>=1 in-band + wide stability?"""
    if not metrics or not stab_ok:
        return False
    mu = metrics.get("mu_min")
    if not isinstance(mu, (int, float)) or mu < 1.0:
        return False
    for m, side in CONS[bt].items():
        v = metrics.get(m)
        if not isinstance(v, (int, float)) or not math.isfinite(v):
            return False
        if side == "max" and v > limits[m]:
            return False
        if side == "min" and v < limits[m]:
            return False
    return True


def excess(metrics, bt, pool):
    """Dominance excess of a witness vs recorded designs: min over stable pool
    designs of (max over constraints of normalized improvement of the witness
    over that design) - DELTA. > 0 <=> no pool design satisfies the witness's
    planted spec (up to rounding). Returns (e, id of the closest pool design)."""
    best, who = None, None
    for d in pool:
        if not d["stab_ok"]:
            continue
        gap = -9.0
        for m, side in CONS[bt].items():
            a, v = metrics.get(m), d["metrics"].get(m)
            if not isinstance(v, (int, float)) or not isinstance(a, (int, float)):
                gap = max(gap, 9.0)
                continue
            sc = max(abs(a), 1.0)
            imp = (v - a) / sc if side == "max" else (a - v) / sc
            gap = max(gap, imp)
        if isinstance(d["metrics"].get("mu_min"), (int, float)) and d["metrics"]["mu_min"] < 1:
            gap = max(gap, 9.0)
        gap -= DELTA
        if best is None or gap < best:
            best, who = gap, d["id"]
    return (best if best is not None else 1.0), who


# -------------------------------------------------------------------- worker
def worker(jobfile, outfile):
    job = json.load(open(jobfile))
    import bench_anchor_prep as PREP
    t0 = time.time()
    l0 = load1()
    err, r = None, None
    try:
        r = PREP.smoke_run(list(job["tokens"]), job["spec"], int(job["seed"]),
                           int(job["budget"]), PDK, profile=PROFILE)
    except Exception:                                            # noqa: BLE001
        err = traceback.format_exc()[-3000:]
    rec = {"jid": job["jid"], "secs": round(time.time() - t0, 2), "load1": l0,
           "sizable": r is not None, "res": r, "error": err}
    atomic_write(outfile, jdump(rec))


def feasible(rec):
    r = (rec or {}).get("res")
    return bool(r and r.get("feasible"))


def worst_margin(spec_path, metrics):
    import mysolve as MS
    from spec import Spec
    rows, worst = MS._margins(Spec.load(spec_path), metrics or {})
    return rows, worst


# ================================================================= scheduler
class Job:
    __slots__ = ("jid", "kind", "cls", "tokens", "spec", "seed", "budget", "meta")

    def __init__(self, kind, cls, tokens, spec, seed, budget=BUDGET, meta=None):
        self.kind, self.cls, self.tokens, self.spec = kind, cls, list(tokens), spec
        self.seed, self.budget, self.meta = int(seed), int(budget), meta or {}
        self.jid = sha(f"{tokhash(tokens)}|{spec_sha(spec)}|{seed}|{budget}|{PROFILE}", 20)


class Task:
    def __init__(self, name, gen, cls):
        self.name, self.gen, self.cls = name, gen, cls
        self.wait, self.jobs, self.done, self.cancelled = None, None, False, False


class Pipeline:
    CLS_PRIO = {"cal": 0, "val": 1, "f2": 2, "search": 3, "train": 4}

    def __init__(self, mode, run_dir=None):
        self.mode = mode
        self.cfg = dict(CONFIGS[mode])
        if run_dir:
            self.cfg["run_dir"] = run_dir
        self.rd = self.cfg["run_dir"]
        for d in ("specs", "jobs", "logs", "cells", "train"):
            os.makedirs(f"{self.rd}/{d}", exist_ok=True)
        self.era = era_stamp()
        sp_ = f"{self.rd}/start.json"
        if os.path.exists(sp_):
            self.t_start = json.load(open(sp_))["t_start"]
        else:
            self.t_start = time.time()
            atomic_write(sp_, json.dumps({"t_start": self.t_start, "era": self.era,
                                          "mode": mode}))
        self.cache = {}
        self.res_path = f"{self.rd}/results.jsonl"
        if os.path.exists(self.res_path):
            for ln in open(self.res_path):
                try:
                    r = json.loads(ln)
                except Exception:                                # noqa: BLE001
                    continue
                self.cache[r["jid"]] = r
        # event logs are regenerated on every (re)start: the replay through the
        # result cache re-emits them; old copies are rotated, never deleted.
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for f in ("candidates.jsonl", "events.jsonl", "cells.jsonl", "train.jsonl",
                  "sched.log"):
            p = f"{self.rd}/{f}"
            if os.path.exists(p) and os.path.getsize(p):
                os.makedirs(f"{self.rd}/logs/prev-{stamp}", exist_ok=True)
                os.replace(p, f"{self.rd}/logs/prev-{stamp}/{f}")
        self.fh = {f: open(f"{self.rd}/{f}", "a") for f in
                   ("candidates.jsonl", "events.jsonl", "cells.jsonl", "train.jsonl")}
        self.logfh = open(f"{self.rd}/sched.log", "a")
        self.res_fh = open(self.res_path, "a")
        self.rtcache_path = f"{self.rd}/rtcache.jsonl"
        self.rtcache = {}
        if os.path.exists(self.rtcache_path):
            for ln in open(self.rtcache_path):
                try:
                    r = json.loads(ln)
                    self.rtcache[r["k"]] = r["v"]
                except Exception:                                # noqa: BLE001
                    pass
        self.rt_fh = open(self.rtcache_path, "a")
        self.pending = []                 # [Job]
        self.running = {}                 # jid -> (Popen, Job, t0)
        self.waiters = defaultdict(list)  # jid -> [Task]
        self.tasks = []
        self.stop = False
        self.n_done_new = 0
        self.cpu_new = 0.0
        self.recent = []                  # (t_end, secs) of new calls
        self.anch = anchor_data()
        self.anchor_wls = {a["wl"] for a in self.anch.values()}
        # shared state
        self.pool = defaultdict(list)        # band -> anchor designs (cal + F1)
        self.pool_cal = defaultdict(list)    # band -> calibration anchor designs
        self.pool_se = defaultdict(list)     # (band, anchor) -> single-edit designs
        self.cal_done = False
        self.archive = {"bench": defaultdict(list), "train": defaultdict(list)}
        self.seen_wl = {"bench": defaultdict(set), "train": defaultdict(set)}
        self.search_stats = {s: Counter() for s in ("bench", "train")}
        self.search_gen = {"bench": 0, "train": 0}
        self.val_queue = []
        self.cells = OrderedDict()           # name -> cell dict
        self.active_val = {}
        self.accepted = []                   # cell names in acceptance order
        self.cls_accepted = Counter()
        self.bench_done = False
        self.bench_search_done = False
        self.train_tasks = OrderedDict()
        self.train_ok = []
        self.train_search_done = False
        self.n_cand = Counter()
        self.stage_counts = Counter()
        self.kill_counts = Counter()
        self.f2space = {}
        self.last_progress = 0.0
        self.probe = {}
        for g in GRID:
            bt = BANDS[g[0]][0]
            self.probe[g] = write_spec(f"{self.rd}/specs/probe-{gkey(g)}.yaml",
                                       make_spec(g, PROBE[bt], f"probe-{gkey(g)}",
                                                 f"bench-v2 loose probe spec {gkey(g)}"))
        self.log(f"=== start mode={mode} run_dir={self.rd} era={self.era} "
                 f"cached_results={len(self.cache)}")

    # ------------------------------------------------------------ utilities
    def log(self, msg):
        line = time.strftime("%Y-%m-%dT%H:%M:%S ") + msg
        self.logfh.write(line + "\n")
        self.logfh.flush()

    def event(self, kind, **kw):
        kw = dict(kind=kind, ts=time.strftime("%Y-%m-%dT%H:%M:%S"), **kw)
        self.fh["events.jsonl"].write(jdump(kw) + "\n")
        self.fh["events.jsonl"].flush()

    def grid(self, stream):
        go = self.cfg.get("grid_only")
        if go:
            return [tuple(x) for x in go[stream]]
        return [g for g in GRID if grid_split(g) == stream]

    def round_trip(self, text):
        k = sha(text, 24)
        if k in self.rtcache:
            return self.rtcache[k]
        import proposal as P
        rt = P.round_trip(text)
        v = {"ok": bool(rt.get("ok")), "error": rt.get("error"),
             "tokens": rt.get("tokens"), "wl_hash": rt.get("wl_hash"),
             "n_devices": rt.get("n_devices")}
        self.rtcache[k] = v
        self.rt_fh.write(json.dumps({"k": k, "v": v}) + "\n")
        self.rt_fh.flush()
        return v

    # ------------------------------------------------------------ job engine
    def spawn(self, name, gen, cls):
        t = Task(name, gen, cls)
        self.tasks.append(t)
        self._advance(t, None)
        return t

    def _advance(self, t, results):
        while True:
            try:
                jobs = t.gen.send(results) if results is not None or t.jobs is not None \
                    else next(t.gen)
            except StopIteration:
                t.done = True
                return
            except Exception:                                    # noqa: BLE001
                self.log(f"TASK {t.name} CRASHED:\n{traceback.format_exc()}")
                t.done = True
                return
            t.jobs = jobs
            miss = [j for j in jobs if j.jid not in self.cache]
            if not miss:
                results = [self.cache[j.jid] for j in jobs]
                continue
            t.wait = set(j.jid for j in miss)
            for j in miss:
                self.waiters[j.jid].append(t)
                if j.jid not in self.running and not any(p.jid == j.jid for p in self.pending):
                    self.pending.append(j)
            return

    def cancel(self, t):
        t.cancelled = True
        t.done = True
        try:
            t.gen.close()
        except Exception:                                        # noqa: BLE001
            pass
        if t.wait:
            for jid in t.wait:
                ws = self.waiters.get(jid, [])
                if t in ws:
                    ws.remove(t)
                if not ws:
                    self.pending = [p for p in self.pending if p.jid != jid]

    def _finish(self, jid, rec):
        self.cache[jid] = rec
        for t in self.waiters.pop(jid, []):
            if t.done:
                continue
            t.wait.discard(jid)
            if not t.wait:
                self._advance(t, [self.cache[j.jid] for j in t.jobs])

    def _pick(self):
        if not self.pending:
            return None
        run_cls = Counter(j.cls for _p, j, _t in self.running.values())
        pend_cls = {j.cls for j in self.pending}
        order = None
        if "search" in pend_cls and run_cls["search"] < self.cfg["search_min_slots"]:
            order = "search"
        elif "train" in pend_cls and run_cls["train"] < self.cfg["train_min_slots"]:
            order = "train"
        if order is None:
            order = min(pend_cls, key=lambda c: self.CLS_PRIO[c])
        for i, j in enumerate(self.pending):
            if j.cls == order:
                return self.pending.pop(i)
        return self.pending.pop(0)

    def _launch(self, j):
        jf = f"{self.rd}/jobs/{j.jid}.job.json"
        of = f"{self.rd}/jobs/{j.jid}.out.json"
        ef = f"{self.rd}/jobs/{j.jid}.err"
        atomic_write(jf, jdump({"jid": j.jid, "tokens": j.tokens, "spec": j.spec,
                                "seed": j.seed, "budget": j.budget}))
        with open(ef, "w") as efh:
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "worker", jf,
                                  of], stdout=subprocess.DEVNULL, stderr=efh,
                                 start_new_session=True)
        self.running[j.jid] = (p, j, time.time())

    def _reap(self):
        for jid, (p, j, t0) in list(self.running.items()):
            rc = p.poll()
            if rc is None and time.time() - t0 < WORKER_TIMEOUT_S:
                continue
            if rc is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:                                # noqa: BLE001
                    pass
                p.wait()
            del self.running[jid]
            of = f"{self.rd}/jobs/{jid}.out.json"
            ef = f"{self.rd}/jobs/{jid}.err"
            if os.path.exists(of):
                rec = json.load(open(of))
            else:
                err = open(ef).read()[-2000:] if os.path.exists(ef) else ""
                rec = {"jid": jid, "secs": round(time.time() - t0, 2), "sizable": None,
                       "res": None, "error": f"worker rc={rc}: {err}"}
            rec.update(kind=j.kind, cls=j.cls, seed=j.seed, budget=j.budget,
                       spec=os.path.relpath(j.spec, REPO), tok=tokhash(j.tokens),
                       meta=j.meta, era=self.era, profile=PROFILE,
                       ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
            self.res_fh.write(jdump(rec) + "\n")
            self.res_fh.flush()
            for f in (of, ef, f"{self.rd}/jobs/{jid}.job.json"):
                try:
                    os.remove(f)
                except OSError:
                    pass
            self.n_done_new += 1
            self.cpu_new += rec.get("secs") or 0
            self.recent.append((time.time(), rec.get("secs") or 0))
            self._finish(jid, rec)

    def inproc(self, job):
        """Pre-sizing verifier reject run in-process (0 evals, instant): used only
        when the SAME topo/struct guards smoke_run applies first already fail."""
        if job.jid in self.cache:
            return self.cache[job.jid]
        import bench_anchor_prep as PREP
        r = PREP.smoke_run(job.tokens, job.spec, job.seed, job.budget, PDK,
                           profile=PROFILE)
        assert r is not None and r.get("n_evals") == 0, "inproc job was not a pre-reject"
        rec = {"jid": job.jid, "secs": 0.0, "load1": load1(), "sizable": True, "res": r,
               "error": None, "inproc_reject": True, "kind": job.kind, "cls": job.cls,
               "seed": job.seed, "budget": job.budget,
               "spec": os.path.relpath(job.spec, REPO), "tok": tokhash(job.tokens),
               "meta": job.meta, "era": self.era, "profile": PROFILE,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.res_fh.write(jdump(rec) + "\n")
        self.res_fh.flush()
        self.cache[job.jid] = rec
        return rec

    def pre_reject(self, tokens, spec_path):
        """Would smoke_run reject this topology before sizing (topo limits /
        structural degeneracy under rl-v1)? Same functions smoke_run calls."""
        import bench_anchor_prep as PREP
        from topology import Topology
        sp = sizing_spec(spec_path)
        topo = Topology(list(tokens))
        if not PREP.topo_limits(sp, topo)["ok"]:
            return True
        return bool(PREP.structural_degeneracy(topo))

    # -------------------------------------------------------------- main loop
    def run(self):
        signal.signal(signal.SIGTERM, self._sigterm)
        signal.signal(signal.SIGINT, self._sigterm)
        self.f2space_build()
        self.spawn("calibration", self.task_calibration(), "cal")
        while not self.stop:
            self._reap()
            self.control()
            limit = self.cfg["max_procs"]
            if load1() > self.cfg["load_thresh"]:
                limit = self.cfg["throttle_procs"]
            self.cur_limit = limit
            while len(self.running) < limit and self.pending:
                j = self._pick()
                if j is None:
                    break
                self._launch(j)
            if time.time() - self.last_progress > 30:
                self.progress()
            if not self.running and not self.pending and all(t.done for t in self.tasks):
                if self.finish_check():
                    break
            time.sleep(0.5)
        self.progress()
        if not self.stop:
            self.log("pipeline complete -> finalize")
            finalize(self.mode, self.rd)
            self.progress(final=True)
        self.log("scheduler exit")

    def _sigterm(self, *_a):
        self.log("SIGTERM: stopping (running workers killed; resume re-runs them)")
        self.stop = True
        for jid, (p, _j, _t) in list(self.running.items()):
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except Exception:                                    # noqa: BLE001
                pass

    def finish_check(self):
        return True

    # --------------------------------------------------------------- control
    def elapsed_h(self):
        return (time.time() - self.t_start) / 3600.0

    def control(self):
        if not self.cal_done:
            return
        # bench stop rule: a cap-respecting selection of bench_target cells exists
        if not self.bench_done:
            sel = select_cells([self.cells[c] for c in self.accepted], self.cfg)
            if len(sel) >= self.cfg["bench_target"]:
                self.bench_done = True
                self.log(f"BENCH TARGET REACHED: {len(sel)} selectable cells")
                self.event("bench_done", n_selectable=len(sel))
            elif self.elapsed_h() > self.cfg["bench_max_hours"]:
                self.bench_done = True
                self.log("BENCH TIME BUDGET EXHAUSTED")
                self.event("bench_time_budget", n_selectable=len(sel))
            if self.bench_done:
                self.bench_search_done = True
                self.val_queue = []
                for t in self.tasks:
                    if t.name.startswith("cell:") and not t.done:
                        self.cancel(t)
                        c = self.cells[t.name[5:]]
                        c["status"] = "cancelled"
                        self.write_cell(c)
                        self.active_val.pop(c["name"], None)
        if self.elapsed_h() > self.cfg["total_max_hours"] and not self.train_search_done:
            self.train_search_done = True
            self.log("TOTAL TIME BUDGET EXHAUSTED: stopping training")
            for t in self.tasks:
                if (t.name.startswith("train:") or t.name == "search:train") and not t.done:
                    self.cancel(t)
        # admission of cell validations
        if self.bench_done:
            return
        cap = self.cfg["cap_build"]
        while len(self.active_val) < self.cfg["max_active_val"] and self.val_queue:
            act_cls = Counter(self.cells[n]["cls"] for n in self.active_val)
            acc_wl = {self.cells[n]["wl"] for n in self.accepted}
            act_wl = {self.cells[n]["wl"] for n in self.active_val}
            keep, best = [], None
            for c in self.val_queue:
                if self.cls_accepted[c["cls"]] >= cap or c["wl"] in acc_wl:
                    c["status"] = "skipped_cap" if c["wl"] not in acc_wl else "skipped_dupwl"
                    self.write_cell(c)
                    continue
                keep.append(c)
            self.val_queue = keep
            elig = [c for c in keep if self.cls_accepted[c["cls"]] + act_cls[c["cls"]] < cap + 2
                    and c["wl"] not in act_wl]
            if not elig:
                break
            best = min(elig, key=lambda c: (self.cls_accepted[c["cls"]] + act_cls[c["cls"]],
                                            -c["e"], c["seq"]))
            self.val_queue.remove(best)
            self.active_val[best["name"]] = True
            best["status"] = "validating"
            self.spawn("cell:" + best["name"], self.task_cell(best), "val")

    # ---------------------------------------------------------- calibration
    def task_calibration(self):
        jobs = []
        go = self.cfg.get("grid_only")
        cal_grid = GRID if not go else [tuple(x) for s in go for x in go[s]]
        for g in cal_grid:
            for a, A in self.anch.items():
                for s in self.cfg["cal_seeds"]:
                    j = Job("cal", "cal", A["tokens"], self.probe[g], s,
                            meta={"g": gkey(g), "anchor": a})
                    if self.pre_reject(A["tokens"], self.probe[g]):
                        self.inproc(j)
                    jobs.append(j)
        recs = yield jobs
        for j, r in zip(jobs, recs):
            b = j.meta["g"].split("-")[0]
            self.add_pool(self.pool_cal[b], r, f"cal:{j.meta['g']}:{j.meta['anchor']}:s{j.seed}")
            self.add_pool(self.pool[b], r, f"cal:{j.meta['g']}:{j.meta['anchor']}:s{j.seed}")
        self.cal_done = True
        feas = Counter(j.meta["g"] for j, r in zip(jobs, recs) if feasible(r))
        self.log(f"calibration done: {len(jobs)} runs, probe-feasible per grid {dict(feas)}")
        self.event("calibration_done", n=len(jobs), feasible_per_grid=dict(feas))
        self.spawn("search:bench", self.task_search("bench"), "search")
        self.spawn("search:train", self.task_search("train"), "train")

    def add_pool(self, lst, rec, did):
        r = rec.get("res") or {}
        m = r.get("metrics") or {}
        if not m:
            return
        lst.append({"id": did, "metrics": {k: v for k, v in m.items()
                                          if isinstance(v, (int, float))},
                    "stab_ok": bool(r.get("stab_wide_ok")),
                    "feasible": bool(r.get("feasible"))})

    # --------------------------------------------------------------- F2 space
    def f2space_build(self):
        """E-c single-edit space of every anchor (add R/C/L between every
        unordered net pair, delete any element), round-tripped once."""
        import itertools as IT
        for a, A in self.anch.items():
            lines = A["text"].splitlines()
            elems = []
            for i, raw in enumerate(lines):
                s = raw.strip()
                if not s or s[0] in "#*":
                    continue
                p = s.split()
                elems.append((i, p[0].upper(), p[1], p[2:]))
            nets = sorted({n for _i, _t, _n, ns in elems for n in ns})
            body = "\n".join(lines)
            cands = []
            for x, y in IT.combinations(nets, 2):
                for typ in ("R", "C", "L"):
                    cands.append({"kind": "add", "desc": f"add {typ} {x}-{y}",
                                  "netlist": body.rstrip("\n") + f"\n{typ} {typ}x {x} {y}\n"})
            for i, typ, name, ns in elems:
                kept = [ln for k, ln in enumerate(lines) if k != i]
                cands.append({"kind": "del", "desc": f"del {typ} {name} ({' '.join(ns)})",
                              "netlist": "\n".join(kept) + "\n"})
            out = []
            for idx, c in enumerate(cands):
                rt = self.round_trip(c["netlist"])
                out.append({"idx": idx, "kind": c["kind"], "desc": c["desc"],
                            "rt_ok": rt["ok"], "tokens": rt["tokens"],
                            "wl": rt["wl_hash"], "rt_error": rt["error"]})
            self.f2space[a] = out
        self.f2_wls = {c["wl"] for a in self.f2space for c in self.f2space[a] if c["rt_ok"]}
        self.log("f2space: " + ", ".join(f"{a}={len(v)}({sum(c['rt_ok'] for c in v)} ok)"
                                         for a, v in self.f2space.items()))

    # ----------------------------------------------------------------- search
    def candidate_from_script(self, stream, g, anchor, script, origin):
        """apply -> repair -> coherence checks -> round-trip -> verifier-identical
        pre-screens -> dedupe. Returns (cand, None) or (None, reason)."""
        bt = BANDS[g[0]][0]
        base = self.anch[anchor]["elems"]
        try:
            el0 = apply_script(base, script)
            el, reps = repair(el0)
        except Bad as e:
            return None, f"repair:{e}"
        nL = sum(1 for e in el if e[0] == "L")
        if not (3 <= len(el) <= 16):
            return None, "device_budget"
        if bt == "wideband" and nL > 2:
            return None, "max_inductors"
        if bt == "narrowband" and nL < 1:
            return None, "has_inductor"
        text = net_text(el)
        rt = self.round_trip(text)
        if not rt["ok"]:
            return None, "round_trip"
        wl = rt["wl_hash"]
        if wl in self.anchor_wls:
            return None, "equals_anchor"
        if wl in self.f2_wls:
            return None, "in_single_edit_space"
        if wl in self.seen_wl[stream][g]:
            return None, "dup"
        if self.pre_reject(rt["tokens"], self.probe[g]):
            return None, "verifier_prescreen"
        cls, top, labels = label_script(base, script, el)
        return {"stream": stream, "g": gkey(g), "anchor": anchor, "script": script,
                "repairs": reps, "netlist": text, "tokens": rt["tokens"],
                "tok": tokhash(rt["tokens"]), "wl": wl, "cls": cls, "label": top,
                "edit_labels": labels, "origin": origin,
                "n_edits": len(script)}, None

    def make_generation(self, stream, gen):
        cfg = self.cfg
        out = []
        n = cfg["gen_size"][stream]
        for g in self.grid(stream):
            if stream == "train":
                have = sum(1 for t in self.train_tasks.values() if t["g"] == gkey(g))
                if have >= cfg["train_quota_per_point"]:
                    continue
            bt = BANDS[g[0]][0]
            rng = random.Random(f"{cfg['stream_seed'][stream]}:{gkey(g)}:{gen}")
            arch = [c for gg in self.grid(stream) if BANDS[gg[0]][0] == bt
                    for c in self.archive[stream][gg]]
            here = self.archive[stream][g]
            top = sorted(arch, key=lambda c: -c["score"])[:20]
            plan = []
            if gen == 0 or not top:
                plan = ["rand"] * n
            else:
                n_rand = max(1, n // 3)
                plan = ["rand"] * n_rand + ["mut"] * (n - n_rand)
                sib = [c for c in top if c["g"] != gkey(g) and c["feasible"]
                       and c["wl"] not in self.seen_wl[stream][g]]
                if sib:
                    plan[-1] = "xfer"
            for slot, kind in enumerate(plan):
                cand, why, tries = None, None, 0
                rej = Counter()
                while cand is None and tries < 150:
                    tries += 1
                    if kind == "xfer":
                        p = sib[0]
                        sib = sib[1:]
                        cand, why = self.candidate_from_script(
                            stream, g, p["anchor"], p["script"],
                            {"kind": "xfer", "from": p["cid"]})
                        if cand is None:
                            rej[why] += 1
                            if not sib:
                                kind = "mut"
                        continue
                    if kind == "mut" and top:
                        k = min(3, len(top))
                        p = min(rng.sample(top, k), key=lambda c: -c["score"])
                        script, mv = mutate_script(rng, self.anch[p["anchor"]]["elems"],
                                                   p["script"])
                        anchor, origin = p["anchor"], {"kind": "mut", "move": mv,
                                                       "parent": p["cid"]}
                    else:
                        anchor = rng.choice(PARENTS[bt])
                        script = random_script(rng, self.anch[anchor]["elems"])
                        origin = {"kind": "rand"}
                    if not script:
                        rej["sample"] += 1
                        continue
                    cand, why = self.candidate_from_script(stream, g, anchor, script, origin)
                    if cand is None:
                        rej[why] += 1
                        continue
                    if stream == "bench" and self.cls_accepted[cand["cls"]] >= cfg["cap_build"]:
                        rej["class_capped"] += 1
                        cand = None
                if cand is None:
                    self.search_stats[stream]["gen_fail"] += 1
                    continue
                cand["gen"] = gen
                cand["cid"] = f"{stream[0]}{gen:04d}-{gkey(g)}-{slot}"
                cand["rejects_before"] = dict(rej)
                self.seen_wl[stream][g].add(cand["wl"])
                out.append(cand)
                for r_, k_ in rej.items():
                    self.search_stats[stream]["rej_" + r_] += k_
        return out

    def task_search(self, stream):
        gen = 0
        cfg = self.cfg
        empty = 0
        while gen < cfg["max_gens"][stream]:
            if stream == "bench" and self.bench_search_done:
                break
            if stream == "train" and (self.train_search_done
                                      or len(self.train_ok) >= cfg["train_target"]):
                break
            cands = self.make_generation(stream, gen)
            self.search_gen[stream] = gen
            if not cands:
                empty += 1
                if empty >= 3 or (stream == "train" and all(
                        sum(1 for t in self.train_tasks.values() if t["g"] == gkey(g))
                        >= cfg["train_quota_per_point"] for g in self.grid(stream))):
                    self.log(f"search:{stream} exhausted (no admissible candidates) "
                             f"at gen {gen}")
                    break
                gen += 1
                continue
            empty = 0
            jobs = [Job("search", "search" if stream == "bench" else "train",
                        c["tokens"], self.probe[tuple(c["g"].split("-"))], 1,
                        meta={"cid": c["cid"], "stream": stream}) for c in cands]
            recs = yield jobs
            for c, j, r in zip(cands, jobs, recs):
                self.process_candidate(stream, c, j, r)
            # planting confirmation (DEVIATION D2): a seed-1 probe-feasible
            # candidate is re-sized at probe seed 2; only if that is feasible too
            # is it planted, from the componentwise-WORST of the two stable
            # winners (both real designs satisfy the planted spec).
            feas = [c for c in cands if c["feasible"]]
            if feas:
                cj = [Job("confirm", j.cls, c["tokens"], self.probe[tuple(c["g"].split("-"))],
                          2, meta={"cid": c["cid"], "stream": stream})
                      for c, j in zip(cands, jobs) if c["feasible"]]
                crecs = yield cj
                for c, r in zip(feas, crecs):
                    self.plant(stream, c, r)
            gen += 1
        if stream == "bench":
            self.bench_search_done = True
        else:
            self.train_search_done = True
        self.log(f"search:{stream} finished at gen {gen}")

    def process_candidate(self, stream, c, job, rec):
        g = tuple(c["g"].split("-"))
        bt = BANDS[g[0]][0]
        res = rec.get("res") or {}
        st = self.search_stats[stream]
        st["sized"] += 1
        c["jid"] = job.jid
        c["result"] = {k: res.get(k) for k in (
            "feasible", "spec_feasible", "stab_wide_ok", "mu_min_wide", "n_evals",
            "infeasible_reason", "inert_devices", "n_inert_devices")} if res else None
        c["metrics"] = {k: v for k, v in (res.get("metrics") or {}).items()
                        if isinstance(v, (int, float))} if res else None
        c["secs"] = rec.get("secs")
        c["feasible"] = feasible(rec)
        score = None
        if rec.get("sizable") and res:
            if c["feasible"]:
                e, who = excess(c["metrics"], bt, self.pool_cal[g[0]])
                c["e_cal"], c["e_cal_vs"] = e, who
                score = 1.0 + max(-0.5, min(1.0, e))
                st["feasible"] += 1
            else:
                _rows, worst = worst_margin(self.probe[g], c["metrics"] or {})
                w = worst[1] if worst else -3.0
                mu = res.get("mu_min_wide")
                if res.get("stab_wide_ok") is False and isinstance(mu, (int, float)):
                    w = min(w, mu - 1.0)
                score = max(-3.0, min(-1e-6, w))
        c["score"] = score
        if score is not None:
            self.archive[stream][g].append(c)
        # re-label with the verifier's inert list (W2) when the run was feasible
        if c["feasible"]:
            base = self.anch[c["anchor"]]["elems"]
            el = parse_net(c["netlist"])
            cls, top, labels = label_script(base, c["script"], el,
                                            inert_toknames(res))
            c["cls"], c["label"], c["edit_labels"] = cls, top, labels
        self.fh["candidates.jsonl"].write(jdump(c) + "\n")
        self.fh["candidates.jsonl"].flush()
        self.n_cand[stream] += 1

    def plant(self, stream, c, rec2):
        g = tuple(c["g"].split("-"))
        bt = BANDS[g[0]][0]
        st = self.search_stats[stream]
        res2 = rec2.get("res") or {}
        c2 = {"cid": c["cid"], "jid2": rec2["jid"], "feasible2": feasible(rec2),
              "metrics2": {k: v for k, v in (res2.get("metrics") or {}).items()
                           if isinstance(v, (int, float))}}
        if not c2["feasible2"]:
            st["confirm_fail"] += 1
            self.event("confirm_fail", cid=c["cid"], stream=stream,
                       reason=res2.get("infeasible_reason"),
                       stab_wide_ok=res2.get("stab_wide_ok"))
            return
        st["confirmed"] += 1
        worst = {}
        for m, side in CONS[bt].items():
            a, b = c["metrics"][m], c2["metrics2"][m]
            worst[m] = max(a, b) if side == "max" else min(a, b)
        worst["mu_min"] = min(c["metrics"].get("mu_min", 1), c2["metrics2"].get("mu_min", 1))
        c = dict(c, planted_from=worst, confirm_jid=rec2["jid"],
                 metrics_seed2=c2["metrics2"])
        if stream == "bench":
            self.plant_bench(c, g, bt)
        else:
            self.plant_train(c, g, bt)

    # ---------------------------------------------------------------- planting
    def plant_bench(self, c, g, bt):
        lim = planted_limits(bt, c["planted_from"])
        for d in self.pool[g[0]]:
            if satisfies(d["metrics"], d["stab_ok"], bt, lim):
                self.kill_counts["prekill_F1_known_anchor_design"] += 1
                self.event("prekill", cid=c["cid"], why="F1: recorded anchor design "
                           "satisfies the planted spec", design=d["id"], limits=lim)
                return
        for d in self.pool_se[(g[0], c["anchor"])]:
            if satisfies(d["metrics"], d["stab_ok"], bt, lim):
                self.kill_counts["prekill_F2_known_single_edit_design"] += 1
                self.event("prekill", cid=c["cid"], why="F2: recorded single edit of "
                           "the parent satisfies the planted spec", design=d["id"],
                           limits=lim)
                return
        e, who = excess(c["planted_from"], bt, self.pool[g[0]])
        seq = len(self.cells)
        name = f"v2-{g[0]}-{g[1]}-{seq:03d}"
        spec_path = write_spec(f"{self.rd}/specs/{name}.yaml", make_spec(
            g, lim, name, f"bench-v2 planted cell ({BANDS[g[0]][0]} {g[0]}, "
            f"{g[1]} objective) from search witness {c['cid']}"))
        tlim = tightened_limits(bt, lim)
        tight_path = write_spec(f"{self.rd}/specs/{name}__tight.yaml", make_spec(
            g, tlim, name + "__tight", "tightened-2% acceptance copy"))
        cell = {"name": name, "seq": seq, "g": gkey(g), "band": g[0], "flavor": g[1],
                "bt": bt, "cid": c["cid"], "anchor": c["anchor"], "wl": c["wl"],
                "tok": c["tok"], "tokens": c["tokens"], "netlist": c["netlist"],
                "script": c["script"], "repairs": c["repairs"], "cls": c["cls"],
                "label": c["label"], "edit_labels": c["edit_labels"], "e": e,
                "e_vs": who, "limits": lim, "tight_limits": tlim, "spec": spec_path,
                "tight_spec": tight_path, "witness_search_metrics": c["metrics"], "planted_from": c["planted_from"], "metrics_seed2": c["metrics_seed2"],
                "status": "queued", "stages": {}, "smoke": self.mode == "smoke"}
        self.cells[name] = cell
        self.val_queue.append(cell)
        self.stage_counts["planted"] += 1
        self.event("planted", cell=name, cid=c["cid"], cls=c["cls"], e=e, limits=lim)

    def write_cell(self, c):
        self.fh["cells.jsonl"].write(jdump({k: v for k, v in c.items() if k != "tokens"})
                                     + "\n")
        self.fh["cells.jsonl"].flush()

    # ------------------------------------------------------------ cell pipeline
    def task_cell(self, c):
        tok = c["tokens"]
        spec, tight = c["spec"], c["tight_spec"]
        st = c["stages"]
        bt = c["bt"]

        def J(kind, tokens, sp, seed, cls="val", **meta):
            meta.update(cell=c["name"], stage=kind)
            return Job(kind, cls, tokens, sp, seed, meta=meta)

        def verdict(status, why):
            c["status"] = status
            c["why"] = why
            self.active_val.pop(c["name"], None)
            self.kill_counts[f"{status}:{why}" if status != "accepted" else "accepted"] += 1
            self.write_cell(c)
            self.event("cell_verdict", cell=c["name"], status=status, why=why,
                       cls=c["cls"])

        force = bool(self.cfg.get("smoke_force"))

        def killed(why):
            """SMOKE force mode: record the would-be kill and keep going so every
            stage is exercised; never set in the full run."""
            if force:
                lst = c.setdefault("SMOKE_FORCED_would_kill", [])
                if why not in lst:
                    lst.append(why)
                return False
            verdict("killed", why)
            return True

        def summ(r, seed, extra=None):
            res = r.get("res") or {}
            d = {"seed": seed, "jid": r["jid"], "feasible": feasible(r),
                 "sizable": r.get("sizable"), "secs": r.get("secs"),
                 "mu_min_wide": res.get("mu_min_wide"),
                 "infeasible_reason": res.get("infeasible_reason"),
                 "n_evals": res.get("n_evals")}
            if extra:
                d.update(extra)
            return d

        # ---- A1: witness >= 2 of seeds {1,2,3}
        self.stage_counts["A1_started"] += 1
        a1 = []
        recs = yield [J("A1", tok, spec, 1), J("A1", tok, spec, 2)]
        a1 += [summ(r, s) for r, s in zip(recs, (1, 2))]
        nf = sum(x["feasible"] for x in a1)
        if nf == 1:
            recs = yield [J("A1", tok, spec, 3)]
            a1 += [summ(recs[0], 3)]
            nf += a1[-1]["feasible"]
        st["A1"] = {"runs": a1, "n_feasible": nf, "pass": nf >= 2}
        if nf < 2:
            if killed("A1_witness_not_2of3"):
                return
        # ---- F1: library null, a1-a5 x {1,2}
        self.stage_counts["F1_started"] += 1
        f1 = []
        parent_recs = []
        for seed in (1, 2):
            jobs = []
            for a, A in self.anch.items():
                j = J("F1", A["tokens"], spec, seed, anchor=a)
                if self.pre_reject(A["tokens"], spec):
                    self.inproc(j)
                jobs.append(j)
            recs = yield jobs
            for j, r in zip(jobs, recs):
                f1.append(summ(r, seed, {"anchor": j.meta["anchor"],
                                         "inproc_reject": bool(r.get("inproc_reject"))}))
                self.add_pool(self.pool[c["band"]], r, f"F1:{c['name']}:{j.meta['anchor']}:s{seed}")
                if j.meta["anchor"] == c["anchor"]:
                    parent_recs.append((seed, r))
            if any(x["feasible"] for x in f1):
                st["F1"] = {"runs": f1, "pass": False}
                if killed("F1_library_solves"):
                    return
        st["F1"] = {"runs": f1, "pass": not any(x["feasible"] for x in f1)}
        c["evidence"] = make_evidence(c, spec, parent_recs, self.anch[c["anchor"]])
        # ---- A2 tightened >=1 of {1,2,3}; A3 fresh >=1 of {4,5,6}
        self.stage_counts["A23_started"] += 1
        a2, a3 = [], []
        t_seeds, f_seeds = [1, 2, 3], [4, 5, 6]
        while True:
            need = []
            if not any(x["feasible"] for x in a2) and t_seeds:
                need.append(("A2", tight, t_seeds.pop(0)))
            if not any(x["feasible"] for x in a3) and f_seeds:
                need.append(("A3", spec, f_seeds.pop(0)))
            if not need:
                break
            recs = yield [J(k, tok, sp, s) for k, sp, s in need]
            for (k, _sp, s), r in zip(need, recs):
                (a2 if k == "A2" else a3).append(summ(r, s))
        p2, p3 = any(x["feasible"] for x in a2), any(x["feasible"] for x in a3)
        st["A2"] = {"runs": a2, "pass": p2}
        st["A3"] = {"runs": a3, "pass": p3}
        if not p2:
            if killed("A2_tightened_fails"):
                return
        if not p3:
            if killed("A3_fresh_seeds_fail"):
                return
        # ---- F2: every single edit of the SHOWN (parent) anchor x {1,2}
        self.stage_counts["F2_started"] += 1
        space = [x for x in self.f2space[c["anchor"]] if x["rt_ok"]]
        c["f2_space_total"] = len(self.f2space[c["anchor"]])
        c["f2_rt_fail"] = [x["desc"] for x in self.f2space[c["anchor"]] if not x["rt_ok"]]
        if self.cfg["f2_limit"]:
            space = space[: self.cfg["f2_limit"]]
            c["f2_SMOKE_SUBSET"] = self.cfg["f2_limit"]
        f2 = []
        for seed in (1, 2):
            live = []
            for x in space:
                j = J("F2", x["tokens"], spec, seed, cls="f2", edit=x["desc"], idx=x["idx"])
                if self.pre_reject(x["tokens"], spec):
                    r = self.inproc(j)
                    f2.append(summ(r, seed, {"edit": x["desc"], "inproc_reject": True}))
                else:
                    live.append(j)
            for k in range(0, len(live), self.cfg["f2_chunk"]):
                chunk = live[k:k + self.cfg["f2_chunk"]]
                recs = yield chunk
                for j, r in zip(chunk, recs):
                    f2.append(summ(r, seed, {"edit": j.meta["edit"]}))
                    self.add_pool(self.pool_se[(c["band"], c["anchor"])], r,
                                  f"F2:{c['name']}:{j.meta['edit']}:s{seed}")
                c["f2_progress"] = len(f2)
                if any(x["feasible"] for x in f2):
                    st["F2"] = {"runs": f2, "pass": False,
                                "solving_edits": [x["edit"] for x in f2 if x["feasible"]]}
                    if killed("F2_single_edit_solves"):
                        return
        st["F2"] = {"runs": f2, "pass": not any(x["feasible"] for x in f2),
                    "solving_edits": [x["edit"] for x in f2 if x["feasible"]], "n_sized": sum(
            1 for x in f2 if not x.get("inproc_reject")),
            "n_prereject": sum(1 for x in f2 if x.get("inproc_reject"))}
        # ---- ABL: automatic move-class label from the ESSENTIAL edit groups
        # (drop one group -> re-size seed 1 at the planted spec; still feasible
        # => that group is not needed). Label = _LABEL_PRIO-top over the
        # essential groups' per-edit labels in the witness netlist.
        base = self.anch[c["anchor"]]["elems"]
        groups = OrderedDict()
        for op in c["script"]:
            groups.setdefault(op["grp"], []).append(op)
        abl, jobs, gids = [], [], []
        if len(groups) > 1:
            for gid in groups:
                s2 = [o for o in c["script"] if o["grp"] != gid]
                try:
                    el2, _r = repair(apply_script(base, s2))
                    rt2 = self.round_trip(net_text(el2))
                except Bad:
                    rt2 = None
                if not rt2 or not rt2["ok"] or self.pre_reject(rt2["tokens"], spec):
                    abl.append({"grp": gid, "essential": True, "why": "invalid_without"})
                    continue
                jobs.append(J("ABL", rt2["tokens"], spec, 1, grp=gid))
                gids.append(gid)
            if jobs:
                recs = yield jobs
                for gid, r in zip(gids, recs):
                    abl.append({"grp": gid, "essential": not feasible(r), "jid": r["jid"]})
        ess = {x["grp"] for x in abl if x["essential"]} or set(groups)
        inert = set()
        for x in st["A1"]["runs"]:
            if x["feasible"]:
                inert = inert_toknames((self.cache.get(x["jid"]) or {}).get("res"))
                break
        cls, top, labels = label_script(base, [o for o in c["script"] if o["grp"] in ess],
                                        parse_net(c["netlist"]), inert)
        st["ABL"] = {"runs": abl, "essential_groups": sorted(ess)}
        c["cls_search"], c["label_search"] = c["cls"], c["label"]
        c["cls"], c["label"], c["edit_labels_essential"] = cls, top, labels
        self.accepted.append(c["name"])
        self.cls_accepted[c["cls"]] += 1
        write_cell_dir(c, f"{self.rd}/cells/{c['name']}", self.anch[c["anchor"]], self.cache)
        if c.get("SMOKE_FORCED_would_kill"):
            c["smoke_forced"] = True
            return verdict("accepted", "SMOKE_FORCED(would kill: "
                           + ",".join(c["SMOKE_FORCED_would_kill"]) + ")")
        return verdict("accepted", "all_filters_pass")

    # --------------------------------------------------------------- training
    def plant_train(self, c, g, bt):
        if len(self.train_ok) + sum(1 for t in self.train_tasks.values()
                                    if t["status"] == "running") >= self.cfg["train_target"]:
            return
        have = sum(1 for t in self.train_tasks.values() if t["g"] == gkey(g))
        if have >= self.cfg["train_quota_per_point"]:
            return
        bench_wl = {self.cells[n]["wl"] for n in self.accepted}
        bench_tok = {self.cells[n]["tok"] for n in self.accepted}
        if c["wl"] in bench_wl or c["tok"] in bench_tok:
            self.event("train_fenced", cid=c["cid"])
            return
        lim = planted_limits(bt, c["planted_from"])
        seq = len(self.train_tasks)
        name = f"t2-{g[0]}-{g[1]}-{seq:04d}"
        spec_path = write_spec(f"{self.rd}/specs/{name}.yaml", make_spec(
            g, lim, name, f"train-pool-v2 planted task ({g[0]}, {g[1]} objective) "
            f"from search witness {c['cid']}"))
        t = {"name": name, "seq": seq, "g": gkey(g), "band": g[0], "flavor": g[1],
             "bt": bt, "cid": c["cid"], "anchor": c["anchor"], "wl": c["wl"],
             "tok": c["tok"], "tokens": c["tokens"], "netlist": c["netlist"],
             "script": c["script"], "repairs": c["repairs"], "cls": c["cls"],
             "label": c["label"], "limits": lim, "spec": spec_path, "status": "running",
             "stages": {}, "smoke": self.mode == "smoke"}
        self.train_tasks[name] = t
        self.spawn("train:" + name, self.task_train(t), "train")

    def task_train(self, t):
        tok, spec, bt = t["tokens"], t["spec"], t["bt"]

        def J(kind, tokens, seed, **meta):
            meta.update(task=t["name"], stage=kind)
            return Job(kind, "train", tokens, spec, seed, meta=meta)

        recs = yield [J("T-wit", tok, 1), J("T-wit", tok, 2)]
        wit = [{"seed": s, "jid": r["jid"], "feasible": feasible(r)}
               for s, r in zip((1, 2), recs)]
        t["stages"]["witness"] = wit
        if not any(x["feasible"] for x in wit):
            t["status"] = "unproved"
            self.fh["train.jsonl"].write(jdump({k: v for k, v in t.items()
                                                if k != "tokens"}) + "\n")
            self.fh["train.jsonl"].flush()
            return
        label, why = None, None
        for d in self.pool[t["band"]]:
            if satisfies(d["metrics"], d["stab_ok"], bt, t["limits"]):
                label, why = "library-solvable", f"recorded anchor design {d['id']}"
                break
        parent_recs = []
        if label is None:
            jobs = []
            for a, A in self.anch.items():
                j = J("T-F1", A["tokens"], 1, anchor=a)
                if self.pre_reject(A["tokens"], spec):
                    self.inproc(j)
                jobs.append(j)
            recs = yield jobs
            f1 = []
            for j, r in zip(jobs, recs):
                f1.append({"anchor": j.meta["anchor"], "seed": 1, "jid": r["jid"],
                           "feasible": feasible(r)})
                if j.meta["anchor"] == t["anchor"]:
                    parent_recs.append((1, r))
            t["stages"]["F1_seed1"] = f1
            sol = [x["anchor"] for x in f1 if x["feasible"]]
            if sol:
                label, why = "library-solvable", f"anchor(s) {sol} feasible at seed 1"
        if label is None:
            for key, lst in self.pool_se.items():
                if key[0] != t["band"]:
                    continue
                for d in lst:
                    if satisfies(d["metrics"], d["stab_ok"], bt, t["limits"]):
                        label, why = "single-edit-solvable", f"recorded single edit {d['id']}"
                        break
                if label:
                    break
        if label is None:
            label, why = "witness-only", "no anchor feasible at seed 1; no known single edit"
        t["difficulty"], t["difficulty_why"] = label, why
        if parent_recs:
            t["evidence"] = make_evidence(t, spec, parent_recs, self.anch[t["anchor"]])
        t["status"] = "ok"
        self.train_ok.append(t["name"])
        self.fh["train.jsonl"].write(jdump({k: v for k, v in t.items() if k != "tokens"})
                                     + "\n")
        self.fh["train.jsonl"].flush()

    # --------------------------------------------------------------- progress
    def progress(self, final=False):
        self.last_progress = time.time()
        now = time.time()
        self.recent = [(t, s) for t, s in self.recent if now - t < 3600]
        cls_run = Counter(j.cls for _p, j, _t in self.running.values())
        cls_pend = Counter(j.cls for j in self.pending)
        stat = Counter(c["status"] for c in self.cells.values())
        stage_active = Counter()
        for n in self.active_val:
            stg = self.cells[n]["stages"]
            stage_active[("F2" if "A3" in stg else "A2/A3" if "F1" in stg and stg["F1"]["pass"]
                          else "F1" if "A1" in stg else "A1")] += 1
        eh = self.elapsed_h()
        acc = len(self.accepted)
        sel = select_cells([self.cells[c] for c in self.accepted], self.cfg)
        rate_calls_h = len(self.recent)
        eta = {}
        if acc and eh > 0:
            r = acc / eh
            eta["bench_cells_per_h"] = round(r, 3)
            eta["bench_eta_h_to_target"] = round(max(0, self.cfg["bench_target"] - len(sel)) / r, 1)
        eta["bench_hard_stop_h"] = round(max(0.0, self.cfg["bench_max_hours"] - eh), 1)
        if self.train_ok and eh > 0:
            r = len(self.train_ok) / eh
            eta["train_tasks_per_h"] = round(r, 2)
            eta["train_eta_h_to_target"] = round(max(0, self.cfg["train_target"]
                                                     - len(self.train_ok)) / r, 1)
        eta["total_hard_stop_h"] = round(max(0.0, self.cfg["total_max_hours"] - eh), 1)
        pr = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": self.mode,
            "final": final, "pid": os.getpid(), "run_dir": self.rd, "era": self.era,
            "elapsed_h": round(eh, 3), "load1": load1(),
            "proc_limit": getattr(self, "cur_limit", None),
            "running": dict(cls_run), "pending": dict(cls_pend),
            "calls": {"new_this_session": self.n_done_new,
                      "cached_total": len(self.cache),
                      "cpu_h_this_session": round(self.cpu_new / 3600, 2),
                      "last_hour": rate_calls_h,
                      "median_secs_last_hour": (sorted(s for _t, s in self.recent)[
                          len(self.recent) // 2] if self.recent else None)},
            "calibration_done": self.cal_done,
            "search": {s: {"generation": self.search_gen[s], "candidates": self.n_cand[s],
                           **dict(self.search_stats[s])} for s in ("bench", "train")},
            "bench": {"planted": len(self.cells), "queued": len(self.val_queue),
                      "validating": dict(stage_active), "status": dict(stat),
                      "accepted": acc, "selectable": len(sel),
                      "accepted_class_hist": dict(self.cls_accepted),
                      "selected_class_hist": dict(Counter(c["cls"] for c in sel)),
                      "stage_started": dict(self.stage_counts),
                      "kills": dict(self.kill_counts),
                      "bench_done": self.bench_done,
                      "search_done": self.bench_search_done},
            "train": {"tasks": len(self.train_tasks), "ok": len(self.train_ok),
                      "labels": dict(Counter(self.train_tasks[n].get("difficulty")
                                             for n in self.train_ok)),
                      "per_grid": dict(Counter(self.train_tasks[n]["g"] for n in self.train_ok)),
                      "search_done": self.train_search_done},
            "eta": eta,
        }
        atomic_write(f"{self.rd}/progress.json", json.dumps(pr, indent=1, default=repr))


# ================================================================ artifacts
def make_evidence(c, spec_path, parent_recs, A):
    """Shown-anchor failure evidence, editcap-lib-v12-45nm evidence.json format:
    best (max worst-margin) of the parent anchor's F1 runs at this spec."""
    best = None
    tot = 0
    for seed, r in parent_recs:
        res = r.get("res") or {}
        tot += res.get("n_evals") or 0
        m = {k: v for k, v in (res.get("metrics") or {}).items()}
        rows, worst = worst_margin(spec_path, m)
        rows = list(rows)
        mw = res.get("mu_min_wide")
        if isinstance(mw, (int, float)):
            # rl-v1 wide stability (0.01-50 GHz) as one more evidence row, so a
            # shown anchor that is in-band compliant but wide-unstable reports
            # its real binding constraint
            rows.append(("mu_min_wide_0.01-50GHz", mw, {"min": 1.0}, mw - 1.0, True))
            if worst is None or mw - 1.0 < worst[1]:
                worst = ["mu_min_wide_0.01-50GHz", mw - 1.0]
        elif res.get("n_evals") and res.get("stab_wide_ok") is False:
            rows.append(("mu_min_wide_0.01-50GHz", None, {"min": 1.0}, None, False))
        wm = worst[1] if worst else -9e9
        if best is None or wm > best[0]:
            best = (wm, m, rows, worst, bool(res.get("feasible")), seed, res)
    wm, m, rows, worst, feas, seed, res = best
    import yaml
    sp = yaml.safe_load(open(spec_path))
    return {"spec": c["name"], "band": sp["band"], "pdk": PDK,
            "anchor_family": A["family"].split("-", 2)[-1],
            "feasible": feas, "worst_margin": worst,
            "margins": {n: {"achieved": a, "margin": mg, "supported": sup}
                        for n, a, _c, mg, sup in rows},
            "metrics": m, "total_evals": tot,
            "verifier": "rl-v1", "seeds": [s for s, _r in parent_recs],
            "best_seed": seed, "stab_wide_ok": res.get("stab_wide_ok"),
            "mu_min_wide": res.get("mu_min_wide"),
            "infeasible_reason": res.get("infeasible_reason")}


def write_cell_dir(c, d, A, cache):
    os.makedirs(f"{d}/witness", exist_ok=True)
    import shutil
    shutil.copy(c["spec"], f"{d}/spec.yaml")
    shutil.copy(f"{REPO}/{A['net_file']}", f"{d}/anchor.net")
    shutil.copy(f"{REPO}/{A['tokens_file']}", f"{d}/anchor.tokens.json")
    if c.get("evidence"):
        atomic_write(f"{d}/evidence.json", json.dumps(c["evidence"], indent=1, default=float))
    atomic_write(f"{d}/witness/README", "EVAL-ONLY. Witness (proof of solvability) of a "
                 "bench-v2 cell. Never use in SFT/RL/prompt data (PREREG-BENCH-V2 fence).\n")
    atomic_write(f"{d}/witness/witness.net",
                 "* bench-v2 witness (EVAL-ONLY). Found by search from anchor "
                 f"{A['family']}; edit script in edit_script.json.\n" + c["netlist"])
    atomic_write(f"{d}/witness/witness.tokens.json", json.dumps(c.get("tokens")))
    atomic_write(f"{d}/witness/edit_script.json", json.dumps(
        {"parent_anchor": A["family"], "script": c["script"], "repairs": c["repairs"],
         "move_class": c["cls"], "label": c["label"], "edit_labels": c["edit_labels"],
         "search_cid": c["cid"], "wl_hash": c["wl"], "tok_hash": c["tok"]}, indent=1))
    runs = {}
    for stg in ("A1", "A2", "A3"):
        for x in (c["stages"].get(stg) or {}).get("runs", []):
            rec = cache.get(x["jid"]) or {}
            runs[f"{stg}_seed{x['seed']}"] = {"seed": x["seed"], "budget": BUDGET,
                                             "spec": "spec.yaml" if stg != "A2" else
                                             "tightened (limits in results.json)",
                                             "result": rec.get("res"), "era": rec.get("era")}
    atomic_write(f"{d}/witness/results.json", json.dumps(
        {"verifier": PROFILE, "pdk": PDK, "budget": BUDGET,
         "tight_limits": c["tight_limits"], "limits": c["limits"], "runs": runs},
        indent=1, default=repr))
    meta = {k: v for k, v in c.items() if k not in ("tokens", "netlist", "evidence")}
    meta["stages"] = {k: {kk: vv for kk, vv in v.items() if kk != "runs"} | {
        "n_runs": len(v.get("runs", []))} for k, v in c["stages"].items()}
    atomic_write(f"{d}/cell.json", json.dumps(meta, indent=1, default=repr))


def select_cells(cells, cfg):
    """Final selection: acceptance order, <= 1 cell per witness WL hash, no move
    class > cap_frac of the selected set, at most bench_target cells. Returns the
    largest such list."""
    cells = sorted(cells, key=lambda c: c["seq"])
    best = []
    for n in range(min(cfg["bench_target"], len(cells)), 0, -1):
        cap = max(1, int(math.floor(cfg["cap_frac"] * n + 1e-9)))
        pick, cnt, wls = [], Counter(), set()
        for c in cells:
            if c["wl"] in wls or cnt[c["cls"]] >= cap:
                continue
            pick.append(c)
            cnt[c["cls"]] += 1
            wls.add(c["wl"])
            if len(pick) == n:
                break
        if len(pick) == n:
            best = pick
            break
    return best


def load_jsonl_last(path, key):
    d = OrderedDict()
    if os.path.exists(path):
        for ln in open(path):
            try:
                r = json.loads(ln)
            except Exception:                                    # noqa: BLE001
                continue
            d[r[key]] = r
    return d


def finalize(mode, rd=None):
    """Write the selected bench cells to kaggle/editcap-lib-v2 (smoke: under the
    smoke dir) and the training pool to kaggle/train-pool-v2, then fence-check."""
    import shutil
    cfg = dict(CONFIGS[mode])
    rd = rd or cfg["run_dir"]
    cells = load_jsonl_last(f"{rd}/cells.jsonl", "name")
    acc = [c for c in cells.values() if c["status"] == "accepted"]
    sel = select_cells(acc, cfg)
    lib = f"{REPO}/kaggle/editcap-lib-v2" if mode == "full" else f"{CAMP}/smoke/editcap-lib-v2"
    tp = f"{REPO}/kaggle/train-pool-v2" if mode == "full" else f"{CAMP}/smoke/train-pool-v2"
    os.makedirs(lib, exist_ok=True)
    index = {"prereg": "kaggle/PREREG-BENCH-V2.md", "verifier": PROFILE, "pdk": PDK,
             "budget": BUDGET, "mode": mode, "n_accepted": len(acc),
             "n_selected": len(sel), "shortfall": max(0, cfg["bench_min"] - len(sel)),
             "class_hist_selected": dict(Counter(c["cls"] for c in sel)),
             "class_hist_accepted": dict(Counter(c["cls"] for c in acc)),
             "cells": OrderedDict()}
    for c in sel:
        src = f"{rd}/cells/{c['name']}"
        dst = f"{lib}/{c['name']}"
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        index["cells"][c["name"]] = {"band": c["band"], "flavor": c["flavor"],
                                     "band_type": c["bt"], "move_class": c["cls"],
                                     "parent_anchor": c["anchor"], "witness_wl": c["wl"],
                                     "witness_tok": c["tok"], "limits": c["limits"],
                                     "smoke": c.get("smoke", False)}
    atomic_write(f"{lib}/INDEX.json", json.dumps(index, indent=1))
    # ---- training pool
    tasks = load_jsonl_last(f"{rd}/train.jsonl", "name")
    ok = [t for t in tasks.values() if t["status"] == "ok"]
    bench_wl = {c["wl"] for c in acc}
    bench_tok = {c["tok"] for c in acc}
    bench_specs = {json.dumps(c["limits"], sort_keys=True) + c["g"] for c in acc}
    os.makedirs(tp, exist_ok=True)
    tindex = {"prereg": "kaggle/PREREG-BENCH-V2.md", "verifier": PROFILE, "mode": mode,
              "fence": "no bench-v2 spec, witness WL hash or witness token hash",
              "tasks": OrderedDict(), "fenced_out": []}
    for t in ok:
        if t["wl"] in bench_wl or t["tok"] in bench_tok or \
                (json.dumps(t["limits"], sort_keys=True) + t["g"]) in bench_specs:
            tindex["fenced_out"].append(t["name"])
            continue
        d = f"{tp}/{t['name']}"
        os.makedirs(f"{d}/witness", exist_ok=True)
        shutil.copy(t["spec"], f"{d}/spec.yaml")
        A = anchor_data()[t["anchor"]]
        shutil.copy(f"{REPO}/{A['net_file']}", f"{d}/anchor.net")
        shutil.copy(f"{REPO}/{A['tokens_file']}", f"{d}/anchor.tokens.json")
        if t.get("evidence"):
            atomic_write(f"{d}/evidence.json", json.dumps(t["evidence"], indent=1, default=float))
        atomic_write(f"{d}/witness/witness.net", "* train-pool-v2 witness (search-found)\n"
                     + t["netlist"])
        atomic_write(f"{d}/witness/edit_script.json", json.dumps(
            {"parent_anchor": A["family"], "script": t["script"], "repairs": t["repairs"],
             "move_class": t["cls"], "wl_hash": t["wl"], "tok_hash": t["tok"]}, indent=1))
        atomic_write(f"{d}/task.json", json.dumps({k: v for k, v in t.items()
                                                   if k not in ("netlist", "evidence")},
                                                  indent=1, default=repr))
        tindex["tasks"][t["name"]] = {"band": t["band"], "flavor": t["flavor"],
                                      "difficulty": t.get("difficulty"),
                                      "move_class": t["cls"], "parent_anchor": t["anchor"],
                                      "witness_wl": t["wl"], "witness_tok": t["tok"]}
    tindex["difficulty_hist"] = dict(Counter(v["difficulty"] for v in tindex["tasks"].values()))
    atomic_write(f"{tp}/INDEX.json", json.dumps(tindex, indent=1))
    rc = subprocess.run([sys.executable, f"{CAMP}/fence_check.py", "--bench", lib,
                         "--train", tp, "--cells-jsonl", f"{rd}/cells.jsonl"],
                        capture_output=True, text=True)
    atomic_write(f"{rd}/fence_check.txt", rc.stdout + rc.stderr)
    print(f"finalize: {len(sel)} bench cells -> {lib}; {len(tindex['tasks'])} training "
          f"tasks -> {tp} (fenced out {len(tindex['fenced_out'])}); fence rc={rc.returncode}")
    return len(sel), len(tindex["tasks"]), rc.returncode


# ====================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--mode", default="full")
    ap.add_argument("--run-dir", default=None)
    a = ap.parse_args()
    if a.cmd == "worker":
        worker(*a.args[:2])
    elif a.cmd == "run":
        rd = a.run_dir or CONFIGS[a.mode]["run_dir"]
        os.makedirs(rd, exist_ok=True)
        atomic_write(f"{rd}/sched.pid", str(os.getpid()))
        Pipeline(a.mode, rd).run()
    elif a.cmd == "finalize":
        finalize(a.mode, a.run_dir)
    elif a.cmd == "status":
        rd = a.run_dir or CONFIGS[a.mode]["run_dir"]
        print(open(f"{rd}/progress.json").read())
    else:
        raise SystemExit(f"unknown command {a.cmd}")


if __name__ == "__main__":
    main()
