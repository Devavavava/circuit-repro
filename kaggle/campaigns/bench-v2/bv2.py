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
  bv2.py finalize --mode full|smoke|smoke-a1 [--run-dir DIR]
  bv2.py status [--run-dir DIR]
  bv2.py amend-snapshot --mode full                 # AMENDMENT 1: freeze pre-amendment record

AMENDMENT 1 (2026-09-30, PREREG commit 78ccdf0b4): core-fix classes (abl_core),
parent <= 40 % / narrowband >= 25 % selection quotas + search steering
(make_generation_bench), spec floors s11_max_db <= -9 dB & s21_db >= 10 dB
(PROBE_BENCH / floor_violations), fresh 72 h bench budget from the resume,
pre-amendment rows kept and tagged, never selectable. See README "AMENDMENT 1".
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
PROFILE = "rl-v1"                 # verifier of every pre-amendment / amendment-1 row
# PRE-REG AMENDMENT 2 (2026-10-01, PREREG commit 1a0413fb9): bench AND training
# verification switch to rl-v1.1 = rl-v1 + the input-port DC requirement
# (bench_anchor_prep VERIFY_PORT_DC). The active profile of a run is its config's
# `profile`; a Job carries its own profile (part of its cache key).
PROFILE_V11 = "rl-v1.1"
CUR_PROFILE = PROFILE             # set by Pipeline from cfg["profile"]
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
# ---------------------------------------------------------------------------
# PRE-REG AMENDMENT 1 (2026-09-30, commit 78ccdf0b4; user: "go with B, including
# the spec floors"). Everything planted/accepted before it is tagged
# "pre-amendment" and is never selectable; post-amendment rows/cells carry AMEND.
AMEND = "amendment-1"
PRE = "pre-amendment"
AMEND2 = "amendment-2"
POST_ERAS = (AMEND, AMEND2)       # selectable eras (pre-amendment never is)
TAG_PDC = "amend2-port-dc"        # AMENDMENT 2: failed the port-DC requirement
# realistic spec floors, ALL bench cells (wideband and narrowband; narrowband
# uses s11_max_db per rl-v1 W6): planted limit must be at least this strict.
FLOORS = OrderedDict([("s11_max_db", ("max", -9.0)), ("s21_db", ("min", 10.0))])
FLOOR_GUARD = 0.01     # outward guard against the 1e-4 outward rounding of planting


def floor_probe_value(side, F):
    """Achieved value a whose cushion-relaxed planted limit is exactly the floor F.
    Planting: L - DELTA*max(|L|,1) = a (max side) / L + DELTA*max(|L|,1) = a (min
    side). For |L| >= 1 both reduce to L = a/(1+DELTA) (max side with L <= -1:
    L + DELTA*L = a; min side with L >= 1: L + DELTA*L = a), so L within F <=> a
    within F*(1+DELTA): s11 a <= -9.18 dB, s21 a >= 10.20 dB. The probe adds a
    0.01 guard outward (rounding): s11 <= -9.19, s21 >= 10.21."""
    a = F * (1 + DELTA)
    return round(a - FLOOR_GUARD, 6) if side == "max" else round(a + FLOOR_GUARD, 6)


def floor_violations(limits):
    """[(metric, limit, floor)] for every planted limit looser than its floor."""
    out = []
    for m, (side, F) in FLOORS.items():
        v = limits.get(m)
        if not isinstance(v, (int, float)) or (v > F if side == "max" else v < F):
            out.append((m, v, F))
    return out


# bench probe = the loose probe with the floors folded in (at the derived achieved
# threshold), so a seed-1+2 probe-feasible witness plants a spec within the floors.
PROBE_BENCH = copy.deepcopy(PROBE)
for _bt in PROBE_BENCH:
    for _m, (_side, _F) in FLOORS.items():
        _pv = floor_probe_value(_side, _F)
        PROBE_BENCH[_bt][_m] = (min(PROBE_BENCH[_bt][_m], _pv) if _side == "max"
                                else max(PROBE_BENCH[_bt][_m], _pv))
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
        # AMENDMENT 1: quotas on the final selection + their build-time caps
        parent_frac=0.40, nb_frac=0.25, parent_cap_build=10,
        # final-selection class cap rule: AMENDMENT 2 ruled (b) "primary_atom"
        # (was "signature", pre-registered default, pending ruling until then)
        class_rule="primary_atom",
        pre_amend_dir=f"{CAMP}/run/pre-amendment",
        # exact-key reuse of the AMENDMENT-1 smoke's calls (same code, same
        # verifier): its pre-amendment re-classification and floor-probe cal rows;
        # AMENDMENT 2: + the amendment-2 smoke's rl-v1.1 calls (exact key only)
        extra_cache=[f"{CAMP}/smoke/run-amend1/results.jsonl",
                     f"{CAMP}/smoke/run-amend2/results.jsonl"],
        # AMENDMENT 2: verifier rl-v1.1; the amendment-1 state is RESTORED from
        # the frozen record (not replayed), re-evaluated under rl-v1.1, and the
        # search continues from it (bv2.py amend2-snapshot writes the record)
        profile=PROFILE_V11, amend2=True,
        restore_from=f"{CAMP}/run/amendment-1-record",
        abl_strip=True,
        train_target=300, train_quota_per_point=32,
        max_active_val=8, f2_chunk=16, f2_limit=None,
        max_procs=8, throttle_procs=4, load_thresh=22.0,
        search_min_slots=3, train_min_slots=2,
        # AMENDMENT 1: fresh 72 h bench hard stop measured from the resume
        # (start.json t_amend1); total (training) budget unchanged from t_start.
        bench_max_hours=72.0, total_max_hours=118.0, grid_only=None),
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
    # AMENDMENT-1 smoke: separate run dir; reads the full run's pre-amendment
    # snapshot + result cache READ-ONLY (exact-key hits only) so the old cells can
    # be re-classified and pre-amendment topologies can seed the search.
    "smoke-a1": dict(
        run_dir=f"{CAMP}/smoke/run-amend1", stream_seed={"bench": 930_01, "train": 930_02},
        cal_seeds=(1,), gen_size={"bench": 4, "train": 3},
        max_gens={"bench": 2, "train": 1},
        bench_target=1, bench_min=1, cap_frac=1.0, cap_build=1,
        parent_frac=1.0, nb_frac=0.0, parent_cap_build=1,
        pre_amend_dir=f"{CAMP}/run/pre-amendment",
        extra_cache=[f"{CAMP}/run/results.jsonl"],
        abl_strip=True,
        train_target=1, train_quota_per_point=1,
        max_active_val=1, f2_chunk=8, f2_limit=12,     # SMOKE: F2 SUBSET (first 12)
        smoke_force=True,          # SMOKE: run every stage even after a kill
        smoke_force_plant=True,    # SMOKE: plant even after a pre-kill (recorded)
        max_procs=8, throttle_procs=4, load_thresh=22.0,
        search_min_slots=3, train_min_slots=1,
        bench_max_hours=3.0, total_max_hours=4.0,
        grid_only={"bench": [("wb0530", "noise"), ("nb240", "gain")],
                   "train": [("nb158", "gain")]}),
    # AMENDMENT-2 smoke: separate run dir; restores a SUBSET of the full run's
    # frozen amendment-1 record (READ-ONLY) and reads its result cache read-only
    # (exact-key hits + rl-v1 -> rl-v1.1 derivation), then runs every amendment-2
    # path at tiny scale: tag / revalidate / revive / requeue cells, re-check
    # training tasks, one new bench and train generation under rl-v1.1.
    "smoke-a2": dict(
        run_dir=f"{CAMP}/smoke/run-amend2", stream_seed={"bench": 1001_01, "train": 1001_02},
        cal_seeds=(1,), gen_size={"bench": 4, "train": 3},
        max_gens={"bench": 100000, "train": 100000}, new_gens={"bench": 1, "train": 1},
        bench_target=3, bench_min=1, cap_frac=1.0, cap_build=6,
        parent_frac=1.0, nb_frac=0.0, parent_cap_build=10,
        class_rule="primary_atom",
        pre_amend_dir=None,
        extra_cache=[f"{CAMP}/run/results.jsonl"],
        abl_strip=True,
        train_target=300, train_quota_per_point=32,
        max_active_val=8, f2_chunk=8, f2_limit=12,     # SMOKE: F2 SUBSET (first 12)
        smoke_force=False,
        max_procs=8, throttle_procs=4, load_thresh=22.0,
        search_min_slots=2, train_min_slots=1,
        bench_max_hours=3.0, total_max_hours=4.0,
        grid_only={"bench": [("nb090", "gain"), ("wb1020", "noise")],
                   "train": [("nb158", "gain")]},
        profile=PROFILE_V11, amend2=True,
        restore_from=f"{CAMP}/run/amendment-1-record",
        restore_cells=["v2a-nb090-gain-007", "v2a-wb0530-power-000",
                       "v2a-nb158-noise-149", "v2a-nb090-gain-038",
                       "v2a-wb0824-gain-033"],
        # training: pre-filter fail (tag) / pass witness-only / pass single-edit
        restore_train=["t2-nb158-gain-0003", "t2-wb1020-gain-0001", "t2-nb090-noise-0012"],
        # a candidate pre-killed by a single edit that fails the port-DC pre-filter
        restore_replant=["B0010-nb090-gain-2"]),
}
for _k in ("smoke",):          # pre-amendment smoke config kept for the record
    CONFIGS[_k].setdefault("parent_frac", 1.0)
    CONFIGS[_k].setdefault("nb_frac", 0.0)
    CONFIGS[_k].setdefault("parent_cap_build", 99)
    CONFIGS[_k].setdefault("pre_amend_dir", None)
    CONFIGS[_k].setdefault("extra_cache", [])
    CONFIGS[_k].setdefault("abl_strip", True)
for _k in CONFIGS:
    CONFIGS[_k].setdefault("class_rule", "signature")
    # every config before AMENDMENT 2 keeps its historical verifier and code path
    CONFIGS[_k].setdefault("profile", PROFILE)
    CONFIGS[_k].setdefault("amend2", False)
    CONFIGS[_k].setdefault("new_gens", None)
    CONFIGS[_k].setdefault("restore_cells", None)
    CONFIGS[_k].setdefault("restore_train", None)
    CONFIGS[_k].setdefault("restore_replant", None)


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


# ------------------------------------------- AMENDMENT 1: core-fix signatures
# Net class of every net, computed on the PARENT ANCHOR netlist (so a role never
# depends on the other edits of the script). First match wins:
#   IN   = VIN1            OUT = VOUT1          RAIL = VDD / VSS
#   G    = gate of any MOS (a diode net D=G counts as G)
#   D    = drain of any MOS          S = source of any MOS
#   X    = any other parent net (passive-only node)
#   NEW  = a net that does not exist in the parent (introduced by the script)
NET_CLASS_ORDER = ["IN", "OUT", "G", "D", "S", "X", "NEW", "RAIL"]


def net_classes(parent_el):
    mos = [e for e in parent_el if is_mos(e)]
    g, d, s = {e[3] for e in mos}, {e[2] for e in mos}, {e[4] for e in mos}
    out = {}
    for n in nets_of(parent_el):
        out[n] = ("IN" if n == "VIN1" else "OUT" if n == "VOUT1" else
                  "RAIL" if n in RAILS else "G" if n in g else "D" if n in d else
                  "S" if n in s else "X")
    return out


def _dev_role(e, nc):
    """role of a device from its terminal net classes: 2-terminal = sorted pair
    (NET_CLASS_ORDER), MOS = d<cls>.g<cls>.s<cls> (bulk ignored)."""
    if is_mos(e):
        return f"d{nc(e[2])}.g{nc(e[3])}.s{nc(e[4])}"
    return "-".join(sorted((nc(e[2]), nc(e[3])), key=NET_CLASS_ORDER.index))


def group_atoms(parent_el, script):
    """One canonical atom 'op:TYPE:role' per edit group of `script` applied to the
    parent anchor (ops simulated in order so del/rw see the element they touch):
      add   -> add:T:<role of the added device>
      del   -> del:T:<role of the deleted device in the netlist it was deleted from>
      rw    -> rw:T:<pin>:<old net class>><new net class>   (pin D/G/S, 'p' passive)
      ser   (composite: rewire host pin to a new net + passive back to the old net)
            -> ser:<added T>:<host T>.<pin>:<old net class>
      stk   (composite: rewire MOS D/S to a new net + MOS channel old<->new)
            -> stk:<added T>:<host T>.<pin>:<old net class>.g<gate net class>
    Returns OrderedDict gid -> atom."""
    NC = net_classes(parent_el)

    def nc(n):
        return NC.get(n, "NEW")
    el = [list(e) for e in parent_el]
    parts = OrderedDict()
    for op in script:
        cur = {e[1]: e for e in el}
        info = {"op": op["op"], "macro": op.get("macro")}
        if op["op"] == "add":
            dev = [op["t"], op["name"]] + list(op["nets"])
            info.update(T=op["t"], role=_dev_role(dev, nc), nets=list(op["nets"]))
        elif op["op"] == "del":
            e = cur.get(op["name"])
            info.update(T=e[0] if e else "?", role=_dev_role(e, nc) if e else "?")
        else:
            e = cur.get(op["name"])
            T = e[0] if e else "?"
            pin = ("DGS"[op["pin"]] if e and is_mos(e) else "p")
            old = e[2 + op["pin"]] if e else "?"
            info.update(T=T, pin=pin, old=old,
                        role=f"{pin}:{nc(old)}>{nc(op['net'])}")
        parts.setdefault(op["grp"], []).append(info)
        el = apply_script(el, [op])
    atoms = OrderedDict()
    for gid, ps in parts.items():
        mac = ps[0].get("macro")
        if mac in ("ser", "stk") and len(ps) == 2:
            rw, ad = ps
            if mac == "ser":
                atoms[gid] = f"ser:{ad['T']}:{rw['T']}.{rw['pin']}:{nc(rw['old'])}"
            else:
                atoms[gid] = (f"stk:{ad['T']}:{rw['T']}.{rw['pin']}:{nc(rw['old'])}"
                              f".g{nc(ad['nets'][1])}")
        else:
            atoms[gid] = " & ".join(f"{p['op']}:{p['T']}:{p['role']}" for p in ps)
    return atoms


def signature(atoms, gids):
    """canonical core-class signature: sorted multiset of the groups' atoms."""
    return " + ".join(sorted(atoms[g] for g in gids)) or "(empty)"


def sig_atoms(sig):
    return [] if sig in (None, "(empty)") else sig.split(" + ")


def contains_atoms(big, small):
    """multiset inclusion small <= big (lists of atoms)."""
    return not (Counter(small) - Counter(big))


def drop_loss(info, spec_path, cache):
    """feasibility loss of removing one group: invalid circuit -> 1e9; otherwise
    -(best over the sized seeds of the worst normalized margin at the cell spec,
    with the wide-mu shortfall mu_min_wide - 1 folded in when wide-unstable);
    an unsized / pre-rejected run counts margin -1e6."""
    if not info.get("valid"):
        return 1e9
    best = None
    for x in info.get("runs") or []:
        res = (cache.get(x["jid"]) or {}).get("res")
        if not res or not res.get("n_evals"):
            m = -1e6
        else:
            _rows, w = worst_margin(spec_path, res.get("metrics") or {})
            m = w[1] if w else -3.0
            mu = res.get("mu_min_wide")
            if res.get("stab_wide_ok") is False and isinstance(mu, (int, float)):
                m = min(m, mu - 1.0)
        best = m if best is None else max(best, m)
    return -(best if best is not None else -1e6)


def primary_atom(atoms, sig_groups, core_drop, spec_path, cache):
    """PRIMARY ATOM of a core = atom of the single core group (inert excluded)
    whose removal from the core causes the largest feasibility loss (drop_loss).
    Tie-break: larger loss, then atom string ascending, then group id. A 1-group
    core's primary atom is that group's atom."""
    if len(sig_groups) == 1 or not core_drop:
        g = sig_groups[0] if sig_groups else None
        return {"atom": atoms.get(g, "(empty)") if g is not None else "(empty)",
                "grp": g, "loss": None, "ranking": []}
    rk = sorted(([round(drop_loss(info, spec_path, cache), 6), atoms[g], g]
                 for g, info in core_drop), key=lambda t: (-t[0], t[1], t[2]))
    return {"atom": rk[0][1], "grp": rk[0][2], "loss": rk[0][0], "ranking": rk}


def inert_groups(script, final_el, inert_tok):
    """edit groups that are pure decoration by the verifier's own W2 test: every
    op of the group is an ADD of an R/C/L (or the rewire half of a series-insert)
    and every added passive is on the witness run's inert list."""
    groups = OrderedDict()
    for op in script:
        groups.setdefault(op["grp"], []).append(op)
    out = set()
    if not inert_tok:
        return out
    for gid, ops in groups.items():
        adds = [o for o in ops if o["op"] == "add"]
        if not adds or any(o["t"] not in ("R", "C", "L") for o in adds):
            continue
        if any(o["op"] != "add" and o.get("macro") != "ser" for o in ops):
            continue
        if all(_tokname(final_el, o["name"]) in inert_tok for o in adds):
            out.add(gid)
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
        if not d["stab_ok"] or not d.get("pdc_ok", True):     # AMENDMENT 2: port DC
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
                           int(job["budget"]), PDK, profile=job.get("profile", PROFILE))
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
def job_id(tokens, spec, seed, budget, profile):
    """cache key = (token hash, spec content, seed, budget, verifier profile)."""
    return sha(f"{tokhash(tokens)}|{spec_sha(spec)}|{seed}|{budget}|{profile}", 20)


class Job:
    __slots__ = ("jid", "kind", "cls", "tokens", "spec", "seed", "budget", "meta",
                 "profile")

    def __init__(self, kind, cls, tokens, spec, seed, budget=BUDGET, meta=None,
                 profile=None):
        self.kind, self.cls, self.tokens, self.spec = kind, cls, list(tokens), spec
        self.seed, self.budget, self.meta = int(seed), int(budget), meta or {}
        self.profile = profile or CUR_PROFILE
        self.jid = job_id(tokens, spec, seed, budget, self.profile)


class Task:
    def __init__(self, name, gen, cls):
        self.name, self.gen, self.cls = name, gen, cls
        self.wait, self.jobs, self.done, self.cancelled = None, None, False, False


class Pipeline:
    CLS_PRIO = {"cal": 0, "val": 1, "f2": 2, "search": 3, "train": 4}

    def __init__(self, mode, run_dir=None):
        global CUR_PROFILE
        self.mode = mode
        self.cfg = dict(CONFIGS[mode])
        if run_dir:
            self.cfg["run_dir"] = run_dir
        self.rd = self.cfg["run_dir"]
        CUR_PROFILE = self.cfg["profile"]
        self.amend2 = bool(self.cfg.get("amend2"))
        self.phase = AMEND2 if self.amend2 else AMEND
        if self.amend2 and not os.path.isdir(self.cfg["restore_from"]):
            raise SystemExit(f"AMENDMENT 2: frozen amendment-1 record missing: "
                             f"{self.cfg['restore_from']} (run: bv2.py amend2-snapshot)")
        for d in ("specs", "jobs", "logs", "cells", "train"):
            os.makedirs(f"{self.rd}/{d}", exist_ok=True)
        self.era = era_stamp()
        sp_ = f"{self.rd}/start.json"
        if os.path.exists(sp_):
            st0 = json.load(open(sp_))
            self.t_start = st0["t_start"]
        else:
            self.t_start = time.time()
            st0 = {"t_start": self.t_start, "era": self.era, "mode": mode}
        if "t_amend1" not in st0:
            # AMENDMENT 1: the fresh 72 h bench budget runs from this (re)start
            st0["t_amend1"] = time.time()
            st0["era_amend1"] = self.era
            atomic_write(sp_, json.dumps(st0))
        if self.amend2 and "t_amend2" not in st0:
            # AMENDMENT 2: recorded only -- the bench end time is UNCHANGED
            # (t_amend1 + bench_max_hours), so is the total budget (t_start)
            st0["t_amend2"] = time.time()
            st0["era_amend2"] = self.era
            atomic_write(sp_, json.dumps(st0))
        self.t_amend = st0["t_amend1"]
        self.t_amend2 = st0.get("t_amend2")
        self.cache = {}
        self.res_path = f"{self.rd}/results.jsonl"
        # AMENDMENT 1 (5): reuse only on the exact (topology, spec content, seed,
        # budget, profile) key = jid. extra_cache = other run dirs' results read
        # READ-ONLY (smoke-a1 reads the full run's cache); own rows win.
        self.n_extra_cache = 0
        for xp in self.cfg.get("extra_cache") or []:
            if os.path.exists(xp) and os.path.abspath(xp) != os.path.abspath(self.res_path):
                for ln in open(xp):
                    try:
                        r = json.loads(ln)
                    except Exception:                            # noqa: BLE001
                        continue
                    r.setdefault("cache_source", os.path.relpath(xp, REPO))
                    self.cache[r["jid"]] = r
                    self.n_extra_cache += 1
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
            if grid_split(g) == "bench":
                # AMENDMENT 1 (3): bench probe carries the spec floors (new file:
                # the pre-amendment probe files stay as the record)
                self.probe[g] = write_spec(
                    f"{self.rd}/specs/probe-amd1-{gkey(g)}.yaml",
                    make_spec(g, PROBE_BENCH[bt], f"probe-amd1-{gkey(g)}",
                              f"bench-v2 probe spec {gkey(g)} with AMENDMENT-1 floors "
                              f"(s11_max_db <= {FLOORS['s11_max_db'][1]}, s21_db >= "
                              f"{FLOORS['s21_db'][1]} after the 2% cushion)"))
            else:
                self.probe[g] = write_spec(f"{self.rd}/specs/probe-{gkey(g)}.yaml",
                                           make_spec(g, PROBE[bt], f"probe-{gkey(g)}",
                                                     f"bench-v2 loose probe spec {gkey(g)}"))
        # ---- AMENDMENT 1 state
        self.core_accepted = Counter()        # core signature -> accepted (post)
        self.core_atom_count = Counter()      # core atom -> accepted cells containing it
        self.primary_accepted = Counter()     # primary atom -> accepted (post)
        self.parent_accepted = Counter()      # parent anchor -> accepted (post)
        self.floor_rejects = Counter()
        self.steer_last = None
        self.pre_core = OrderedDict()         # pre-amendment accepted -> core class
        self.pre_seed_used = set()
        self.fence_wl, self.fence_tok, self.fence_spec = set(), set(), set()
        self.pre_cells = OrderedDict()
        self.pre_cands = []
        # ---- AMENDMENT 2 state
        self.pdc = Counter()                  # port-DC bookkeeping (progress.json)
        self.search_gen0 = {"bench": 0, "train": 0}
        self.amend1_cells = OrderedDict()     # restored amendment-1 record (name -> cell)
        if self.amend2:
            self.f2space_build()              # pools need the F2 edit tokens (port-DC)
        self.load_pre_amendment()
        self.log(f"=== start mode={mode} run_dir={self.rd} era={self.era} "
                 f"profile={CUR_PROFILE} phase={self.phase} "
                 f"cached_results={len(self.cache)} (extra read-only {self.n_extra_cache}) "
                 f"{AMEND}: t_amend={time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(self.t_amend))} "
                 f"bench end={time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(self.t_amend + 3600 * self.cfg['bench_max_hours']))} "
                 f"pre-amendment cells={len(self.pre_cells)} seeds={len(self.pre_cands)}")

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

    # ----------------------------------------------- AMENDMENT 1: pre-amendment
    def load_pre_amendment(self):
        """Pre-amendment record (snapshot taken at the 26.8 h stop): every cell is
        kept, tagged era_tag=pre-amendment, never selectable. Their recorded
        anchor / single-edit designs stay in the pre-kill pools, their accepted
        witnesses stay fenced, their bench candidates' topologies seed the search,
        their accepted cells are re-classified (core-fix signature) by task_preclass."""
        d = self.cfg.get("pre_amend_dir")
        if not d or not os.path.isdir(d):
            self.log("no pre-amendment snapshot")
            return
        cells = load_jsonl_last(f"{d}/cells.jsonl", "name")
        own = os.path.abspath(d).startswith(os.path.abspath(self.rd) + "/")
        for n, c in cells.items():
            c = dict(c, era_tag=PRE, selectable=False)
            self.pre_cells[n] = c
            if own:            # re-emit so this run's cells.jsonl is the full record
                self.write_cell(c)
            if c["status"] == "accepted":
                self.fence_wl.add(c["wl"])
                self.fence_tok.add(c["tok"])
        n_pool = Counter()
        for r in list(self.cache.values()):
            if r.get("phase") in POST_ERAS:
                continue
            k, m = r.get("kind"), r.get("meta") or {}
            try:
                if k == "cal":
                    b = m["g"].split("-")[0]
                    did = f"pre:cal:{m['g']}:{m['anchor']}:s{r['seed']}"
                    tk = self.anch[m["anchor"]]["tokens"]
                    self.add_pool(self.pool_cal[b], r, did, tokens=tk)
                    self.add_pool(self.pool[b], r, did, tokens=tk)
                elif k == "F1" and m.get("cell") in cells:
                    b = cells[m["cell"]]["band"]
                    self.add_pool(self.pool[b], r, f"pre:F1:{m['cell']}:{m['anchor']}:s{r['seed']}",
                                  tokens=self.anch[m["anchor"]]["tokens"])
                elif k == "F2" and m.get("cell") in cells:
                    c = cells[m["cell"]]
                    self.add_pool(self.pool_se[(c["band"], c["anchor"])], r,
                                  f"pre:F2:{m['cell']}:{m.get('edit')}:s{r['seed']}",
                                  tokens=self.f2_edit_tokens(c["anchor"], m))
                else:
                    continue
                n_pool[k] += 1
            except (KeyError, TypeError):
                continue
        best = OrderedDict()
        if os.path.exists(f"{d}/candidates.jsonl"):
            for ln in open(f"{d}/candidates.jsonl"):
                try:
                    c = json.loads(ln)
                except Exception:                                # noqa: BLE001
                    continue
                if c.get("stream") != "bench" or not c.get("script"):
                    continue
                key = (c["anchor"], json.dumps(c["script"], sort_keys=True))
                sc = c.get("score") if isinstance(c.get("score"), (int, float)) else -9
                if key not in best or sc > best[key][1]:
                    best[key] = (c, sc)
        self.pre_cands = [
            {"cid": c["cid"], "anchor": c["anchor"], "script": c["script"],
             "g": c["g"], "bt": BANDS[c["g"].split("-")[0]][0],
             "feasible": bool(c.get("feasible")), "score": sc}
            for c, sc in best.values()]
        self.pre_cands.sort(key=lambda c: (not c["feasible"], -c["score"], c["cid"]))
        self.log(f"pre-amendment: cells={len(cells)} "
                 f"accepted={sum(1 for c in cells.values() if c['status'] == 'accepted')} "
                 f"pool rows={dict(n_pool)} seed topologies={len(self.pre_cands)}")

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
            miss = [j for j in jobs if j.jid not in self.cache
                    and not (j.jid not in self.running and self.try_derive(j))]
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
                                "seed": j.seed, "budget": j.budget,
                                "profile": j.profile}))
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
                       meta=j.meta, era=self.era, profile=j.profile, phase=self.phase,
                       ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
            self.res_fh.write(jdump(rec) + "\n")
            self.res_fh.flush()
            for f in (of, ef, f"{self.rd}/jobs/{jid}.job.json"):
                try:
                    os.remove(f)
                except OSError:
                    pass
            pd = (rec.get("res") or {}).get("port_dc")
            if isinstance(pd, dict):                # AMENDMENT 2: behavioural checks
                self.pdc["behavioural_checks"] += 1
                if not pd.get("pass"):
                    self.pdc["behavioural_fail"] += 1
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
                           profile=job.profile)
        assert r is not None and r.get("n_evals") == 0, "inproc job was not a pre-reject"
        rec = {"jid": job.jid, "secs": 0.0, "load1": load1(), "sizable": True, "res": r,
               "error": None, "inproc_reject": True, "kind": job.kind, "cls": job.cls,
               "seed": job.seed, "budget": job.budget,
               "spec": os.path.relpath(job.spec, REPO), "tok": tokhash(job.tokens),
               "meta": job.meta, "era": self.era, "profile": job.profile,
               "phase": self.phase, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if (r.get("port_dc_prefilter") or {}).get("pass") is False:
            self.pdc["inproc_prefilter_rejects"] += 1
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
        if PREP.structural_degeneracy(topo):
            return True
        # AMENDMENT 2 (rl-v1.1): the port-DC pre-filter is the third pre-sizing reject
        return bool(self.port_dc_on() and not self.prefilter(tokens)["pass"])

    # -------------------------------------------------------------- main loop
    def run(self):
        signal.signal(signal.SIGTERM, self._sigterm)
        signal.signal(signal.SIGINT, self._sigterm)
        if self.amend2:
            # AMENDMENT 2: restore the frozen amendment-1 state, re-evaluate it
            # under rl-v1.1 and continue (no generator replay: see restore_amend2)
            self.restore_amend2()
        else:
            self.f2space_build()
            self.spawn("calibration", self.task_calibration(), "cal")
            self.spawn("preclass", self.task_preclass(), "val")
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

    def bench_elapsed_h(self):
        """AMENDMENT 1 (4): the bench hard stop is measured from the resume."""
        return (time.time() - self.t_amend) / 3600.0

    # ------------------------------------------------ AMENDMENT 1: steering
    def steer_counts(self):
        """accepted post-amendment cells count 1, cells in validation 0.5 (queued
        plantings 0): per band, band type, parent anchor."""
        nb, nbt, npar = Counter(), Counter(), Counter()
        for c in self.cells.values():
            w = 1.0 if c["status"] == "accepted" else \
                0.5 if c["status"] == "validating" else 0.0
            if w:
                nb[c["band"]] += w
                nbt[c["bt"]] += w
                npar[c["anchor"]] += w
        return nb, nbt, npar

    def capped_cores(self):
        return [sig_atoms(s) for s, k in self.core_accepted.items()
                if k >= self.cfg["cap_build"]]

    def core_penalty(self, atoms):
        """number of accepted cells whose core atoms are contained in `atoms`
        (a candidate carrying an already-accepted core is likely the same fix)."""
        return sum(k for s, k in self.core_accepted.items()
                   if contains_atoms(atoms, sig_atoms(s)))

    def atom_penalty(self, atoms):
        """soft atom-level steering (not a selection criterion): the largest number
        of accepted cells whose core contains any one of `atoms`, in units of the
        class build cap (6): 0 = no overlap, 1 = an atom already in 6 cores."""
        if not atoms:
            return 0.0
        return max(self.core_atom_count.get(a, 0) for a in set(atoms)) / float(
            max(1, self.cfg["cap_build"]))

    def parent_weights(self, bt):
        _nb, _nbt, npar = self.steer_counts()
        pc = self.cfg["parent_cap_build"]
        return OrderedDict((p, 0.0 if self.parent_accepted[p] >= pc else 1.0 / (1.0 + npar[p]))
                           for p in PARENTS[bt])

    def nb_need(self):
        return int(math.ceil(self.cfg["nb_frac"] * self.cfg["bench_target"] - 1e-9))

    def control(self):
        if not self.cal_done:
            return
        # bench stop rule: a quota-compliant selection of bench_target cells exists
        if not self.bench_done:
            sel = select_cells([self.cells[c] for c in self.accepted], self.cfg)
            if len(sel) >= self.cfg["bench_target"]:
                self.bench_done = True
                self.log(f"BENCH TARGET REACHED: {len(sel)} selectable cells")
                self.event("bench_done", n_selectable=len(sel))
            elif self.bench_elapsed_h() > self.cfg["bench_max_hours"]:
                self.bench_done = True
                self.log("BENCH TIME BUDGET EXHAUSTED")
                self.event("bench_time_budget", n_selectable=len(sel))
            if self.bench_done:
                self.bench_search_done = True
                for c in self.val_queue:
                    c["status"] = "not_validated_bench_done"
                    self.write_cell(c)
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
        # AMENDMENT 1 admission (steering): drop cells whose parent anchor is at
        # its build cap or that carry an already-capped core fix; then prefer
        # narrowband while the narrowband quota is unmet, then the least-
        # represented parent, then the fewest accepted cores contained in the
        # witness's live atoms, then larger dominance excess, then plant order.
        pcap = self.cfg["parent_cap_build"]
        while len(self.active_val) < self.cfg["max_active_val"] and self.val_queue:
            acc_wl = {self.cells[n]["wl"] for n in self.accepted}
            act_wl = {self.cells[n]["wl"] for n in self.active_val}
            capped = self.capped_cores()
            keep, best = [], None
            for c in self.val_queue:
                why = ("skipped_dupwl" if c["wl"] in acc_wl else
                       "skipped_parent_cap" if self.parent_accepted[c["anchor"]] >= pcap else
                       "skipped_cap" if any(contains_atoms(c["atoms_live"], k) for k in capped)
                       else None)
                if why:
                    c["status"] = why
                    self.write_cell(c)
                    continue
                keep.append(c)
            self.val_queue = keep
            elig = [c for c in keep if c["wl"] not in act_wl]
            if not elig:
                break
            _nb, nbt, npar = self.steer_counts()
            nb_short = nbt["narrowband"] < self.nb_need()
            best = min(elig, key=lambda c: (
                0 if (nb_short and c["bt"] == "narrowband") else 1,
                npar[c["anchor"]], self.core_penalty(c["atoms_live"]),
                round(self.atom_penalty(c["atoms_live"]), 3), -c["e"], c["seq"]))
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

    def add_pool(self, lst, rec, did, tokens=None):
        r = rec.get("res") or {}
        m = r.get("metrics") or {}
        if not m:
            return
        # a design (sizing call) enters each pool once, whatever path re-adds it
        seen = self.__dict__.setdefault("_pool_seen", defaultdict(set))[id(lst)]
        if rec.get("jid") in seen:
            return
        seen.add(rec.get("jid"))
        d = {"id": did, "metrics": {k: v for k, v in m.items()
                                    if isinstance(v, (int, float))},
             "stab_ok": bool(r.get("stab_wide_ok")),
             "feasible": bool(r.get("feasible"))}
        if self.amend2:
            # AMENDMENT 2: a recorded design is a valid solver (pre-kill / label)
            # only if it meets the port-DC requirement: its own behavioural
            # verdict when it has one (rl-v1.1 feasible winner), else the
            # structural pre-filter of its topology (for a pre-filter-passing
            # topology the behavioural check is a provable no-op: VIN1's DC
            # group holds no MOS terminal / positive rail, so a DC path to ground
            # at VIN1 carries no current -- D23); unknown topology -> not a solver
            pd, pf = r.get("port_dc"), r.get("port_dc_prefilter")
            if isinstance(pd, dict):
                d["pdc_ok"] = bool(pd.get("pass"))
            elif isinstance(pf, dict):
                d["pdc_ok"] = bool(pf.get("pass"))
            elif tokens is not None:
                d["pdc_ok"] = bool(self.prefilter(tokens)["pass"])
            else:
                d["pdc_ok"] = False
            self.pdc["pool_designs_pdc_ok" if d["pdc_ok"] else "pool_designs_pdc_fail"] += 1
        lst.append(d)

    # ------------------------------------------------ AMENDMENT 2: port DC
    def prefilter(self, tokens):
        """bench_anchor_prep.port_dc_prefilter, memoized on the token hash."""
        memo = self.__dict__.setdefault("_pf_memo", {})
        k = tokhash(tokens)
        if k not in memo:
            import bench_anchor_prep as PREP
            memo[k] = PREP.port_dc_prefilter(list(tokens))
        return memo[k]

    def port_dc_on(self):
        import bench_anchor_prep as PREP
        return PREP.VERIFIER_PROFILES.get(CUR_PROFILE, {}).get("VERIFY_PORT_DC") == "1"

    def f2_edit_tokens(self, anchor, meta):
        """tokens of a recorded F2 single edit (f2space entry by idx, desc-checked)."""
        sp = self.f2space.get(anchor) or []
        i = meta.get("idx")
        if isinstance(i, int) and 0 <= i < len(sp) and sp[i]["desc"] == meta.get("edit") \
                and sp[i]["rt_ok"]:
            return sp[i]["tokens"]
        for x in sp:
            if x["desc"] == meta.get("edit") and x["rt_ok"]:
                return x["tokens"]
        return None

    def try_derive(self, j):
        """AMENDMENT 2 cache bridge: an rl-v1.1 job whose rl-v1 twin (same tokens,
        spec content, seed, budget) is cached is answered WITHOUT a re-size when
        the port-DC requirement cannot change it (bench_anchor_prep.derive_port_dc:
        pre-sizing reject in-process, or the rl-v1 winner was infeasible). A
        feasible rl-v1 twin needs the behavioural check on its winner -> None
        (the job is re-sized; the sizing is deterministic, so it is the same
        winner, now checked)."""
        if j.profile != PROFILE_V11:
            return None
        oj = job_id(j.tokens, j.spec, j.seed, j.budget, PROFILE)
        old = self.cache.get(oj)
        if old is None or old.get("error") or old.get("sizable") is None:
            return None
        import bench_anchor_prep as PREP
        try:
            ok, res = PREP.derive_port_dc(old.get("res"), j.tokens, j.spec, j.seed,
                                          j.budget, PDK, profile=j.profile)
        except Exception:                                        # noqa: BLE001
            self.pdc["derive_error"] += 1
            return None
        if not ok:
            self.__dict__.setdefault("_pdc_resize", set()).add(j.jid)
            self.pdc["rl_v1_feasible_resized"] = len(self._pdc_resize)
            return None
        rec = {"jid": j.jid, "secs": 0.0, "load1": load1(), "sizable": res is not None,
               "res": res, "error": None, "derived_from": oj,
               "derived": "rl-v1 -> rl-v1.1 (port-DC cannot change it)",
               "kind": j.kind, "cls": j.cls, "seed": j.seed, "budget": j.budget,
               "spec": os.path.relpath(j.spec, REPO), "tok": tokhash(j.tokens),
               "meta": j.meta, "era": self.era, "profile": j.profile,
               "phase": self.phase, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.res_fh.write(jdump(rec) + "\n")
        self.res_fh.flush()
        self.cache[j.jid] = rec
        self.pdc["derived_rows"] += 1
        if res and (res.get("port_dc_prefilter") or {}).get("pass") is False:
            self.pdc["derived_prefilter_rejects"] += 1
        return rec

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
        if self.port_dc_on() and not self.prefilter(rt["tokens"])["pass"]:
            # AMENDMENT 2: the free port-DC pre-filter at candidate generation
            return None, "port_dc_prefilter"
        if self.pre_reject(rt["tokens"], self.probe[g]):
            return None, "verifier_prescreen"
        cls, top, labels = label_script(base, script, el)
        atoms = group_atoms(base, script)
        return {"stream": stream, "g": gkey(g), "anchor": anchor, "script": script,
                "repairs": reps, "netlist": text, "tokens": rt["tokens"],
                "tok": tokhash(rt["tokens"]), "wl": wl, "cls": cls, "label": top,
                "edit_labels": labels, "origin": origin,
                "atoms": [[gid, a] for gid, a in atoms.items()],
                "atoms_live": sorted(atoms.values()),
                "n_edits": len(script)}, None

    def make_generation_bench(self, gen):
        """AMENDMENT 1 steered bench generation. Weights are recomputed every
        generation from the post-amendment cell counts (accepted 1, validating 0.5)
        and recorded as a `steer` event:
          point weight   w_g = m_bt / (1 + n_band[b]),  m_bt(narrowband) = 1 +
                         2 * max(0, nb_need - n_nb) / nb_need (up to 3x while the
                         >= 25 % narrowband quota is unmet), m_bt(wideband) = 1
          children       N = gen_size * #points split by w_g (largest remainder,
                         >= 1 per point)
          parent weight  w_p = 0 if the parent has parent_cap_build accepted cells
                         (10 = 40 % of 25) else 1 / (1 + n_parent[p]); fresh random
                         children draw their anchor by w_p
          tournament     3 draws (with replacement) from the top-20 archive,
                         weight w_p(anchor) / (1 + #accepted cores contained in the
                         archive member's live atoms) / (1 + atom_penalty); best
                         score wins. atom_penalty = max over the member's atoms of
                         #accepted cores containing that atom / 6 (soft push away
                         from a dominant ingredient, e.g. the pre-amendment
                         series input L, which a whole-signature class misses)
          reject         any child whose atoms contain a capped core class
                         (6 accepted = 25 % of 25) is not generated
        Generation 0 re-sizes pre-amendment bench topologies under the new probe
        (best old score first, rotating over parents by w_p), no random children."""
        cfg, stream = self.cfg, "bench"
        pts = self.grid(stream)
        nb, nbt, npar = self.steer_counts()
        need = self.nb_need()
        m_nb = (1.0 + 2.0 * max(0.0, need - nbt["narrowband"]) / need) if need else 1.0
        w_pt = OrderedDict()
        for g in pts:
            bt = BANDS[g[0]][0]
            w_pt[g] = (m_nb if bt == "narrowband" else 1.0) / (1.0 + nb[g[0]])
            if not any(self.parent_weights(bt).values()):
                w_pt[g] = 0.0
        N = cfg["gen_size"][stream] * len(pts)
        live = [g for g in pts if w_pt[g] > 0]
        alloc = OrderedDict((g, 0) for g in pts)
        if live:
            tot = sum(w_pt[g] for g in live)
            base = {g: max(1.0, N * w_pt[g] / tot) for g in live}
            for g in live:
                alloc[g] = int(base[g])
            rest = N - sum(alloc.values())
            for g in sorted(live, key=lambda g: -(base[g] - int(base[g])))[:max(0, rest)]:
                alloc[g] += 1
        capped = self.capped_cores()
        self.steer_last = {
            "gen": gen, "m_nb": round(m_nb, 3),
            "point_w": {gkey(g): round(w, 4) for g, w in w_pt.items()},
            "alloc": {gkey(g): k for g, k in alloc.items()},
            "parent_w": {bt: {p: round(w, 4) for p, w in self.parent_weights(bt).items()}
                         for bt in ("wideband", "narrowband")},
            "counts": {"band": dict(nb), "band_type": dict(nbt), "parent": dict(npar)},
            "capped_cores": [" + ".join(k) for k in capped]}
        self.event("steer", **self.steer_last)
        out = []
        for g in pts:
            n = alloc[g]
            if n <= 0:
                continue
            bt = BANDS[g[0]][0]
            pw = self.parent_weights(bt)
            rng = random.Random(f"{cfg['stream_seed'][stream]}:{self.phase}:{gkey(g)}:{gen}")
            arch = [c for gg in pts if BANDS[gg[0]][0] == bt
                    for c in self.archive[stream][gg]]
            top = sorted(arch, key=lambda c: (-c["score"], c["cid"]))[:20]
            tw = [pw.get(c["anchor"], 0.0)
                  / (1.0 + self.core_penalty(c.get("atoms_live") or []))
                  / (1.0 + self.atom_penalty(c.get("atoms_live") or []))
                  for c in top]
            if not any(tw):
                top, tw = [], []
            if gen == 0:
                plan = ["seed"] * n
            elif not top:
                plan = ["rand"] * n
            else:
                n_rand = max(1, n // 3)
                plan = ["rand"] * n_rand + ["mut"] * (n - n_rand)
                sib = [c for c in top if c["g"] != gkey(g) and c["feasible"]
                       and c["wl"] not in self.seen_wl[stream][g]
                       and pw.get(c["anchor"], 0.0) > 0]
                if sib and len(plan) > 1:
                    plan[-1] = "xfer"
            seedq = OrderedDict((p, [s for s in self.pre_cands if s["bt"] == bt
                                     and s["anchor"] == p]) for p in pw if pw[p] > 0)
            for slot, kind in enumerate(plan):
                cand, why, tries = None, None, 0
                rej = Counter()
                while cand is None and tries < 150:
                    tries += 1
                    if kind == "seed":
                        # rotate over parents (highest w_p first), best old score
                        par = sorted((p for p in seedq if any(
                            s["cid"] not in self.pre_seed_used for s in seedq[p])),
                            key=lambda p: (-pw[p], list(pw).index(p)))
                        if not par:
                            kind = "rand"
                            continue
                        p = par[(slot + tries - 1) % len(par)]
                        s = next(s for s in seedq[p] if s["cid"] not in self.pre_seed_used)
                        self.pre_seed_used.add(s["cid"])
                        anchor, script = s["anchor"], s["script"]
                        origin = {"kind": "seed_pre_amendment", "from": s["cid"],
                                  "old_score": s["score"]}
                    elif kind == "xfer":
                        if not sib:
                            kind = "mut"
                            continue
                        p = sib.pop(0)
                        anchor, script = p["anchor"], p["script"]
                        origin = {"kind": "xfer", "from": p["cid"]}
                    elif kind == "mut" and top:
                        k = min(3, len(top))
                        pk = min(rng.choices(top, weights=tw, k=k),
                                 key=lambda c: (-c["score"], c["cid"]))
                        script, mv = mutate_script(rng, self.anch[pk["anchor"]]["elems"],
                                                   pk["script"])
                        anchor, origin = pk["anchor"], {"kind": "mut", "move": mv,
                                                        "parent": pk["cid"]}
                    else:
                        ps = [p for p in pw if pw[p] > 0]
                        if not ps:
                            break
                        anchor = rng.choices(ps, weights=[pw[p] for p in ps])[0]
                        script = random_script(rng, self.anch[anchor]["elems"])
                        origin = {"kind": "rand"}
                    if not script:
                        rej["sample"] += 1
                        continue
                    cand, why = self.candidate_from_script(stream, g, anchor, script, origin)
                    if cand is None:
                        rej[why] += 1
                        continue
                    if any(contains_atoms(cand["atoms_live"], k) for k in capped):
                        rej["contains_capped_core"] += 1
                        cand = None
                if cand is None:
                    self.search_stats[stream]["gen_fail"] += 1
                    continue
                cand["gen"] = gen
                cand["cid"] = f"B{gen:04d}-{gkey(g)}-{slot}"
                cand["era_tag"] = self.phase
                cand["rejects_before"] = dict(rej)
                self.seen_wl[stream][g].add(cand["wl"])
                out.append(cand)
                for r_, k_ in rej.items():
                    self.search_stats[stream]["rej_" + r_] += k_
        return out

    def make_generation(self, stream, gen):
        if stream == "bench":
            return self.make_generation_bench(gen)
        cfg = self.cfg
        out = []
        n = cfg["gen_size"][stream]
        for g in self.grid(stream):
            if stream == "train":
                have = self.train_have(g)
                if have >= cfg["train_quota_per_point"]:
                    continue
            bt = BANDS[g[0]][0]
            rng = random.Random(f"{cfg['stream_seed'][stream]}:{gkey(g)}:{gen}" if not self.amend2 else f"{cfg['stream_seed'][stream]}:{AMEND2}:{gkey(g)}:{gen}")
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
        gen = self.search_gen0[stream]
        cfg = self.cfg
        empty = 0
        stop_at = cfg["max_gens"][stream]
        if cfg.get("new_gens"):                    # smoke-a2: N generations past the restore
            stop_at = min(stop_at, gen + cfg["new_gens"][stream])
        while gen < stop_at:
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
                        self.train_have(g)
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
            ig = inert_groups(c["script"], el, inert_toknames(res))
            c["inert_groups"] = sorted(ig)
            c["atoms_live"] = sorted(a for gid, a in c["atoms"] if gid not in ig)
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
        # AMENDMENT 1 (3): a planted spec looser than a floor is NOT planted
        fv = floor_violations(lim)
        if fv:
            for m, _v, _F in fv:
                self.floor_rejects[m] += 1
            self.floor_rejects["specs"] += 1
            self.kill_counts["floor_reject"] += 1
            self.event("floor_reject", cid=c["cid"], limits=lim,
                       violations=[list(x) for x in fv])
            return
        # SMOKE (smoke-a1 only, smoke_force_plant): a pre-kill is recorded as a
        # would-kill and the cell is planted anyway so the post-amendment cell
        # stages run end-to-end at tiny scale; never set in the full run.
        forced = []
        for d in self.pool[g[0]]:
            if d.get("pdc_ok", True) and satisfies(d["metrics"], d["stab_ok"], bt, lim):
                self.kill_counts["prekill_F1_known_anchor_design"] += 1
                self.event("prekill", cid=c["cid"], why="F1: recorded anchor design "
                           "satisfies the planted spec", design=d["id"], limits=lim)
                if not self.cfg.get("smoke_force_plant"):
                    return
                forced.append(f"prekill_F1({d['id']})")
                break
        for d in self.pool_se[(g[0], c["anchor"])]:
            if d.get("pdc_ok", True) and satisfies(d["metrics"], d["stab_ok"], bt, lim):
                self.kill_counts["prekill_F2_known_single_edit_design"] += 1
                self.event("prekill", cid=c["cid"], why="F2: recorded single edit of "
                           "the parent satisfies the planted spec", design=d["id"],
                           limits=lim)
                if not self.cfg.get("smoke_force_plant"):
                    return
                forced.append(f"prekill_F2({d['id']})")
                break
        e, who = excess(c["planted_from"], bt, self.pool[g[0]])
        seq = len(self.cells)
        # AMENDMENT-1 cell namespace v2a-, AMENDMENT-2 v2b- (seq continues)
        name = f"{'v2b' if self.amend2 else 'v2a'}-{g[0]}-{g[1]}-{seq:03d}"
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
                "atoms": c["atoms"], "atoms_live": c["atoms_live"],
                "inert_groups_search": c.get("inert_groups", []),
                "floors": {m: F for m, (_s, F) in FLOORS.items()},
                "era_tag": self.phase, "selectable": True,
                **({"verifier": CUR_PROFILE} if self.amend2 else {}),
                **({"SMOKE_FORCED_would_kill": forced} if forced else {}),
                "status": "queued", "stages": {}, "smoke": self.mode.startswith("smoke")}
        self.cells[name] = cell
        self.write_cell(cell)          # every planted cell is on record (fence)
        # AMENDMENT 1 (4): every post-amendment bench spec / witness is fenced
        # from the training stream as soon as it is planted
        self.fence_wl.add(c["wl"])
        self.fence_tok.add(c["tok"])
        self.fence_spec.add(spec_sha(spec_path))
        self.val_queue.append(cell)
        self.stage_counts["planted"] += 1
        self.event("planted", cell=name, cid=c["cid"], cls=c["cls"], e=e, limits=lim)

    def write_cell(self, c):
        d = {k: v for k, v in c.items() if k != "tokens"}
        if d.get("witness_original"):
            d["witness_original"] = {k: v for k, v in d["witness_original"].items()
                                     if k != "tokens"}
        self.fh["cells.jsonl"].write(jdump(d) + "\n")
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
            if isinstance(c.get("amend2"), dict):
                # AMENDMENT 2 re-evaluation outcome (revalidated / revived / requeued
                # amendment-1 cell); a kill caused by the port-DC requirement is
                # tagged amend2-port-dc (kept on record, not selectable)
                a2 = c["amend2"]
                a2["outcome"] = status if status == "accepted" else f"{status}:{why}"
                port = any("port_dc" in (x.get("infeasible_reason") or "")
                           for stg in c["stages"].values() if isinstance(stg, dict)
                           for x in stg.get("runs", []) or [] if isinstance(x, dict))
                if status != "accepted" and port:
                    a2["tag"] = TAG_PDC
                    c["selectable"] = False
                self.pdc[f"cells_{a2.get('action')}_{'accepted' if status == 'accepted' else ('killed_port_dc' if port else 'killed_other')}"] += 1
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
                self.add_pool(self.pool[c["band"]], r, f"F1:{c['name']}:{j.meta['anchor']}:s{seed}", tokens=j.tokens)
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
                                  f"F2:{c['name']}:{j.meta['edit']}:s{seed}", tokens=j.tokens)
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
        # ---- ABL (AMENDMENT 1): core fix = ablation-essential edits (minimal
        # sufficient subset), class = its canonical signature; non-essential /
        # inert edits stripped from the archived witness when the stripped
        # netlist re-verifies as an accepted witness (else original kept, flagged)
        c["cls_search"], c["label_search"] = c["cls"], c["label"]
        core = yield from self.abl_core(c, J, strip=self.cfg.get("abl_strip", True))
        c["core"] = core
        c["cls"] = core["signature"]
        c["primary_atom"] = core["primary_atom"]
        c["legacy_class"], c["label"] = core["legacy_class"], core["legacy_label"]
        self.accepted.append(c["name"])
        self.core_accepted[c["cls"]] += 1
        self.primary_accepted[c["primary_atom"]] += 1
        self.core_atom_count.update(set(sig_atoms(c["cls"])))
        self.parent_accepted[c["anchor"]] += 1
        if c.get("witness_original"):
            self.fence_wl.add(c["wl"])
            self.fence_tok.add(c["tok"])
        write_cell_dir(c, f"{self.rd}/cells/{c['name']}", self.anch[c["anchor"]], self.cache)
        if c.get("SMOKE_FORCED_would_kill"):
            c["smoke_forced"] = True
            return verdict("accepted", "SMOKE_FORCED(would kill: "
                           + ",".join(c["SMOKE_FORCED_would_kill"]) + ")")
        return verdict("accepted", "all_filters_pass")

    # ------------------------------------------- AMENDMENT 1: core-fix ablation
    def _abl_trials(self, c, J, keys, memo, stage="ABL"):
        """generator: evaluate kept-group sets `keys` (frozensets) at the cell's
        planted spec: invalid (repair / round-trip / equals anchor / verifier
        pre-screen) or sized at seed 1, and seed 2 when seed 1 is infeasible
        (2 seeds, as the F2 null uses). feasible = feasible at seed 1 or 2."""
        base = self.anch[c["anchor"]]["elems"]
        todo = []
        for key in keys:
            if key in memo:
                continue
            s2 = [o for o in c["script"] if o["grp"] in key]
            info = {"kept": sorted(key), "n_prims": len(s2), "runs": [], "valid": False}
            memo[key] = info
            if not s2:
                info["why"] = "empty_script(=anchor)"
                continue
            try:
                el2, reps2 = repair(apply_script(base, s2))
                rt2 = self.round_trip(net_text(el2))
            except Bad as e:
                info["why"] = f"repair:{e}"
                continue
            if not rt2["ok"]:
                info["why"] = "round_trip"
            elif rt2["wl_hash"] in self.anchor_wls:
                info["why"] = "equals_anchor"
            elif self.pre_reject(rt2["tokens"], c["spec"]):
                info["why"] = "verifier_prescreen"
            else:
                info.update(valid=True, tokens=rt2["tokens"], wl=rt2["wl_hash"],
                            netlist=net_text(el2), repairs=reps2, script=s2)
                todo.append(key)
        for seed in (1, 2):
            run = [k for k in todo if not any(x["feasible"] for x in memo[k]["runs"])]
            if not run:
                break
            jobs = [J(stage, memo[k]["tokens"], c["spec"], seed, kept=sorted(k)) for k in run]
            recs = yield jobs
            for k, r in zip(run, recs):
                memo[k]["runs"].append({"seed": seed, "jid": r["jid"], "feasible": feasible(r)})
        for key in keys:
            memo[key]["feasible"] = any(x["feasible"] for x in memo[key]["runs"])
        return [memo[k] for k in keys]

    def abl_core(self, c, J, strip=True):
        """AMENDMENT 1 core fix of an accepted witness.
          inert groups   = pure-decoration groups by the verifier's W2 inert list
                           (first feasible A1 run)
          drop-one       = each group removed in turn; ESSENTIAL iff the reduced
                           circuit is invalid or infeasible at BOTH seeds {1,2}
          core           = greedy backward elimination from the full script, trying
                           inert, then non-essential, then essential groups (in
                           group order); a group is dropped if the circuit without
                           it is still feasible at seed 1 or 2. Every group left
                           in the core is then ablation-essential in the core.
          signature      = sorted multiset of group_atoms() over the core groups,
                           excluding inert groups (decoration never makes a class)
          strip          = if the core is a strict subset: re-verify the core-only
                           netlist as a witness (A1 >= 2 of {1,2,3}, A2 tightened
                           >= 1 of {1,2,3}, A3 >= 1 of {4,5,6}); pass -> archived
                           witness := stripped (original kept alongside); fail or
                           < 2 primitive edits -> original kept, flagged."""
        base = self.anch[c["anchor"]]["elems"]
        script = c["script"]
        groups = OrderedDict()
        for op in script:
            groups.setdefault(op["grp"], []).append(op)
        gids = list(groups)
        allg = frozenset(gids)
        final_el = parse_net(c["netlist"])
        inert_tok = set()
        for x in (c["stages"].get("A1") or {}).get("runs", []):
            if x["feasible"]:
                inert_tok = inert_toknames((self.cache.get(x["jid"]) or {}).get("res"))
                break
        ig = inert_groups(script, final_el, inert_tok)
        atoms = group_atoms(base, script)
        memo = {allg: {"kept": sorted(allg), "n_prims": len(script), "valid": True,
                       "feasible": True, "runs": [], "why": "full witness (A1)"}}
        drop1 = OrderedDict()
        if len(gids) > 1:
            keys = [allg - {g} for g in gids]
            infos = yield from self._abl_trials(c, J, keys, memo)
            for g, info in zip(gids, infos):
                drop1[g] = {"essential": not info["feasible"], "valid": info["valid"],
                            "why": info.get("why"), "runs": info["runs"]}
        else:
            drop1[gids[0]] = {"essential": True, "why": "single_group"}
        cur = allg
        order = ([g for g in gids if g in ig]
                 + [g for g in gids if g not in ig and not drop1[g]["essential"]]
                 + [g for g in gids if g not in ig and drop1[g]["essential"]])
        greedy = []
        changed = True
        while changed:             # passes until a full pass drops nothing
            changed = False
            for g in order:
                if len(cur) <= 1 or g not in cur:
                    continue
                if cur == allg and drop1[g]["essential"]:
                    continue           # already known: removal breaks feasibility
                if (cur - {g}) in memo and not memo[cur - {g}].get("feasible", True):
                    continue           # already tested infeasible in this context
                (info,) = yield from self._abl_trials(c, J, [cur - {g}], memo)
                greedy.append({"drop": g, "from": sorted(cur), "feasible": info["feasible"],
                               "why": info.get("why")})
                if info["feasible"]:
                    cur = cur - {g}
                    changed = True
        core_groups = [g for g in gids if g in cur]
        sig_groups = [g for g in core_groups if g not in ig]
        flags = []
        if not sig_groups:
            sig_groups = core_groups
            flags.append("core_all_inert")
        if any(g in ig for g in core_groups):
            flags.append("inert_group_needed_for_feasibility")
        sig = signature(atoms, sig_groups)
        # primary atom (selection variant (b), pending user ruling): the core
        # group whose removal FROM THE CORE loses the most feasibility
        core_drop = []
        if len(core_groups) > 1:
            miss = [cur - {g} for g in sig_groups if (cur - {g}) not in memo]
            if miss:
                yield from self._abl_trials(c, J, miss, memo)
            for g in sig_groups:
                info = memo[cur - {g}]
                core_drop.append([g, {"valid": info["valid"], "why": info.get("why"),
                                      "feasible": info.get("feasible"),
                                      "runs": info["runs"]}])
        prim = primary_atom(atoms, sig_groups, core_drop, c["spec"], self.cache)
        cls_l, top_l, labels_l = label_script(
            base, [o for o in script if o["grp"] in cur], final_el, inert_tok)
        out = {"inert_groups": sorted(ig), "inert_toknames": sorted(inert_tok),
               "atoms": [[g, a] for g, a in atoms.items()],
               "drop_one": [[g, v] for g, v in drop1.items()], "greedy": greedy,
               "essential_drop_one": [g for g in gids if drop1[g]["essential"]],
               "core_groups": core_groups, "sig_groups": sig_groups,
               "signature": sig, "primary_atom": prim["atom"], "primary": prim,
               "core_drop": core_drop,
               "legacy_class": cls_l, "legacy_label": top_l,
               "legacy_edit_labels": labels_l, "flags": flags}
        # ---- strip the witness to its core
        sinfo = {"attempted": False}
        if cur != allg:
            ci = memo[cur]
            if not strip:
                sinfo["flag"] = "strip_disabled"
            elif ci["n_prims"] < 2:
                sinfo["flag"] = "core_below_2_primitive_edits(original kept)"
            elif ci.get("wl") in self.f2_wls:
                sinfo["flag"] = "core_in_single_edit_space(original kept)"
            else:
                sinfo["attempted"] = True
                tok2 = ci["tokens"]
                a1 = []
                recs = yield [J("S-A1", tok2, c["spec"], 1), J("S-A1", tok2, c["spec"], 2)]
                a1 += [{"seed": s, "jid": r["jid"], "feasible": feasible(r)}
                       for s, r in zip((1, 2), recs)]
                if sum(x["feasible"] for x in a1) == 1:
                    recs = yield [J("S-A1", tok2, c["spec"], 3)]
                    a1.append({"seed": 3, "jid": recs[0]["jid"], "feasible": feasible(recs[0])})
                a2, a3 = [], []
                if sum(x["feasible"] for x in a1) >= 2:
                    ts, fs = [1, 2, 3], [4, 5, 6]
                    while True:
                        need = []
                        if not any(x["feasible"] for x in a2) and ts:
                            need.append(("S-A2", c["tight_spec"], ts.pop(0)))
                        if not any(x["feasible"] for x in a3) and fs:
                            need.append(("S-A3", c["spec"], fs.pop(0)))
                        if not need:
                            break
                        recs = yield [J(k, tok2, sp, s) for k, sp, s in need]
                        for (k, _sp, s), r in zip(need, recs):
                            (a2 if k == "S-A2" else a3).append(
                                {"seed": s, "jid": r["jid"], "feasible": feasible(r)})
                ok = (sum(x["feasible"] for x in a1) >= 2 and any(x["feasible"] for x in a2)
                      and any(x["feasible"] for x in a3))
                sinfo.update(A1=a1, A2=a2, A3=a3, passed=ok, n_prims=ci["n_prims"],
                             wl=ci["wl"], tok=tokhash(tok2))
                if ok:
                    c["witness_original"] = {k: c[k] for k in ("script", "netlist", "tok",
                                                               "wl", "repairs")}
                    c["witness_original"]["tokens"] = c.get("tokens")
                    c["script"], c["netlist"], c["repairs"] = ci["script"], ci["netlist"], ci["repairs"]
                    c["tokens"], c["tok"], c["wl"] = tok2, tokhash(tok2), ci["wl"]
                    sinfo["flag"] = "stripped"
                else:
                    sinfo["flag"] = "strip_failed_reverify(original kept)"
        else:
            sinfo["flag"] = "nothing_to_strip"
        out["strip"] = sinfo
        return out

    def task_preclass(self):
        """AMENDMENT 1 sanity record: core-fix signature of every pre-amendment
        ACCEPTED cell, by the same abl_core() the new cells use (strip included,
        for the record only; pre-amendment cells are never selectable). One
        sub-task per cell so they run in parallel."""
        names = [n for n, c in self.pre_cells.items() if c["status"] == "accepted"]
        if not names:
            return
        self.pre_core_pending = set(names)
        for n in names:
            self.spawn("preclass:" + n, self.task_preclass_one(n), "val")
        return
        yield                                                   # noqa: unreachable

    def task_preclass_one(self, n):
        c = copy.deepcopy(self.pre_cells[n])
        rt = self.round_trip(c["netlist"])
        c["tokens"] = rt["tokens"]

        def J(kind, tokens, sp, seed, cls="val", **meta):
            meta.update(cell=n, stage=kind, pre_amendment=True)
            return Job(kind, cls, tokens, sp, seed, meta=meta)
        core = yield from self.abl_core(c, J, strip=self.cfg.get("abl_strip", True))
        self.pre_core[n] = {"anchor": c["anchor"], "band": c["band"],
                            "old_class": self.pre_cells[n]["cls"],
                            "limits": self.pre_cells[n]["limits"],
                            "floor_violations": floor_violations(self.pre_cells[n]["limits"]),
                            **core}
        self.pre_core_pending.discard(n)
        self.event("preclass", cell=n, signature=core["signature"],
                   primary_atom=core["primary_atom"],
                   core_groups=core["core_groups"], strip=core["strip"].get("flag"))
        atomic_write(f"{self.rd}/pre-amendment-core-classes.json", json.dumps(
            {"note": "AMENDMENT 1 core-fix signatures of the pre-amendment accepted "
                     "cells (never selectable)",
             "done": sorted(self.pre_core), "pending": sorted(self.pre_core_pending),
             "class_hist": dict(Counter(v["signature"] for v in self.pre_core.values())),
             "primary_atom_hist": dict(Counter(v["primary_atom"] for v in self.pre_core.values())),
             "atom_prevalence": atom_prevalence([{"cls": v["signature"]}
                                                 for v in self.pre_core.values()]),
             "cells": self.pre_core}, indent=1, default=repr))

    # ------------------------------------------- AMENDMENT 2: restore + re-check
    REQUEUE_STATUSES = ("queued", "validating", "skipped_parent_cap", "skipped_cap",
                        "skipped_dupwl", "cancelled", "not_validated_bench_done")

    def restore_amend2(self):
        """AMENDMENT 2 (PREREG 1a0413fb9) resume. The amendment-1 state is RESTORED
        from the frozen record (`restore_from`, written by `bv2.py amend2-snapshot`
        at the stop) instead of replaying the generators: a replay re-derives
        steering from wall-clock order (D13) and would diverge early, redoing most
        of 24 h of search. Then everything is re-evaluated under rl-v1.1:
          pools     anchor (cal/F1) and single-edit (F2) designs of the cached
                    amendment-1 rows; a design solves (pre-kill / label) only if
                    it meets the port-DC requirement (add_pool pdc_ok)
          search    candidates + scores + seen WLs restored; an archive member
                    failing the port-DC pre-filter is dropped (it could never be
                    sized under rl-v1.1); new generations continue at the next
                    generation index with an amendment-2 RNG namespace
          cells     accepted / queued / validating / skipped / cancelled:
                    pre-filter fail -> status amend2-port-dc (kept, fenced, never
                    selectable); pass -> accepted cells RE-VALIDATED under rl-v1.1
                    (every stage re-run through the cache bridge try_derive: rows
                    the port-DC requirement cannot change are derived exactly, a
                    feasible rl-v1 row is re-sized and its winner checked), the
                    others re-queued (admission re-applies the caps). A cell
                    KILLED by F2 whose witness passes the pre-filter and whose
                    every solving single edit fails it is REVIVED (that kill is
                    void under rl-v1.1) and re-queued.
          training  ok tasks: pre-filter fail -> amend2-port-dc (out of the
                    pool); pass -> witness re-checked under rl-v1.1 (seed 1, then
                    seed 2 only if needed) and the difficulty label re-checked
                    against the port-DC-filtered pools; unproved stay unproved
          fence     every amendment-1 planted cell (any status), both witnesses
        The bench end time stays t_amend1 + bench_max_hours."""
        rf = self.cfg["restore_from"]
        only_c, only_t = self.cfg.get("restore_cells"), self.cfg.get("restore_train")
        cells = load_jsonl_last(f"{rf}/cells.jsonl", "name")
        tasks = load_jsonl_last(f"{rf}/train.jsonl", "name")
        cands = []
        for ln in open(f"{rf}/candidates.jsonl"):
            try:
                cands.append(json.loads(ln))
            except Exception:                                    # noqa: BLE001
                continue
        a1 = OrderedDict((n, c) for n, c in sorted(cells.items(), key=lambda kv: kv[1]["seq"])
                         if c.get("era_tag") == AMEND and (only_c is None or n in only_c))
        # ---- pools (amendment-1 cached rows; pre-amendment rows: load_pre_amendment)
        n_pool = Counter()
        for r in list(self.cache.values()):
            if r.get("phase") != AMEND:
                continue
            k, m = r.get("kind"), r.get("meta") or {}
            try:
                if k == "cal":
                    b = m["g"].split("-")[0]
                    did = f"a1:cal:{m['g']}:{m['anchor']}:s{r['seed']}"
                    tk = self.anch[m["anchor"]]["tokens"]
                    self.add_pool(self.pool_cal[b], r, did, tokens=tk)
                    self.add_pool(self.pool[b], r, did, tokens=tk)
                elif k == "F1" and m.get("cell") in cells:
                    b = cells[m["cell"]]["band"]
                    self.add_pool(self.pool[b], r, f"F1:{m['cell']}:{m['anchor']}:s{r['seed']}",
                                  tokens=self.anch[m["anchor"]]["tokens"])
                elif k == "F2" and m.get("cell") in cells:
                    c = cells[m["cell"]]
                    self.add_pool(self.pool_se[(c["band"], c["anchor"])], r,
                                  f"F2:{m['cell']}:{m.get('edit')}:s{r['seed']}",
                                  tokens=self.f2_edit_tokens(c["anchor"], m))
                else:
                    continue
                n_pool[k] += 1
            except (KeyError, TypeError):
                continue
        self.cal_done = True
        # ---- search state
        gmax = {"bench": -1, "train": -1}
        for c in cands:
            s = c.get("stream")
            if s not in gmax or not c.get("g"):
                continue
            g = tuple(c["g"].split("-"))
            self.seen_wl[s][g].add(c["wl"])
            gmax[s] = max(gmax[s], int(c.get("gen", 0)))
            self.pdc[f"restored_candidates_{s}"] += 1
            if c.get("score") is None:
                continue
            if not self.prefilter(c["tokens"])["pass"]:
                self.pdc[f"archive_dropped_prefilter_{s}"] += 1
                continue
            self.archive[s][g].append(c)
            self.pdc[f"archive_kept_{s}"] += 1
        for s in gmax:
            self.search_gen0[s] = gmax[s] + 1
        # ---- cells
        revalidate, requeue = [], []
        for n, c0 in a1.items():
            c = copy.deepcopy(c0)
            rt = self.round_trip(c["netlist"])
            c["tokens"] = rt["tokens"]
            for w in [c] + [c[k] for k in ("witness_original",) if c.get(k)]:
                self.fence_wl.add(w["wl"])
                self.fence_tok.add(w["tok"])
            if os.path.exists(c.get("spec", "")):
                self.fence_spec.add(spec_sha(c["spec"]))
            st = c["status"]
            pf = self.prefilter(c["tokens"])
            pfs = {k: pf[k] for k in ("pass", "why", "group")}
            if st == "accepted" or st in self.REQUEUE_STATUSES:
                if not pf["pass"]:
                    c["amend2"] = {"action": "tag", "status_before": st, "prefilter": pfs,
                                   "tag": TAG_PDC, "outcome": TAG_PDC}
                    c["status"], c["selectable"] = TAG_PDC, False
                    self.pdc[f"cells_tagged_prefilter_{st}"] += 1
                elif st == "accepted":
                    c["amend2"] = {"action": "revalidate", "status_before": st,
                                   "prefilter": pfs,
                                   "amend1": {"cls": c.get("cls"),
                                              "primary_atom": c.get("primary_atom"),
                                              "strip": ((c.get("core") or {}).get("strip")
                                                        or {}).get("flag")}}
                    revalidate.append(c)
                else:
                    c["amend2"] = {"action": "requeue", "status_before": st, "prefilter": pfs}
                    requeue.append(c)
            elif st == "killed" and c.get("why") == "F2_single_edit_solves" and pf["pass"]:
                sol = (c["stages"].get("F2") or {}).get("solving_edits") or []
                stoks = [next((x["tokens"] for x in self.f2space[c["anchor"]]
                               if x["desc"] == e and x["rt_ok"]), None) for e in sol]
                void = bool(sol) and all(t is not None and not self.prefilter(t)["pass"]
                                         for t in stoks)
                if void:
                    c["amend2"] = {"action": "revive", "status_before": st,
                                   "why_before": c.get("why"), "prefilter": pfs,
                                   "void_solving_edits": sol}
                    requeue.append(c)
                    self.pdc["cells_revived_f2_kill_void"] += 1
                else:
                    self.pdc["cells_f2_kill_stands"] += 1
            acted = any(x and x[-1] is c for x in (revalidate, requeue))
            if acted:
                # fresh rl-v1.1 validation; the amendment-1 record is kept
                c["amend1_stages"] = c.get("stages") or {}
                c["stages"] = {}
                for k in ("core", "evidence", "f2_progress", "why", "cls_search",
                          "label_search", "f2_space_total", "f2_rt_fail"):
                    if k in c:
                        c[f"amend1_{k}"] = c.pop(k)
                if c.get("witness_original"):
                    c["witness_original_amend1"] = c.pop("witness_original")
                c["selectable"] = True
            self.cells[n] = c
            if not acted:
                self.write_cell(c)
        self.amend1_cells = a1
        for c in revalidate:
            c["status"] = "validating"
            self.write_cell(c)
            self.active_val[c["name"]] = True
            self.pdc["cells_revalidate_started"] += 1
            self.spawn("cell:" + c["name"], self.task_cell(c), "val")
        for c in requeue:
            c["status"] = "queued"
            self.write_cell(c)
            self.val_queue.append(c)
            self.pdc[f"cells_{c['amend2']['action']}_queued"] += 1
        # ---- void F2 pre-kills: a bench candidate pre-killed (never planted) only
        # because a recorded single edit of its parent met its spec, where that
        # edit fails the port-DC pre-filter (so it is no solver under rl-v1.1),
        # and the candidate itself passes: planted now from its recorded seed-1 +
        # seed-2 probe rows (plant_bench re-applies the port-DC-filtered pre-kill
        # pools, the floors and the fence; the cell then validates under rl-v1.1)
        only_r = self.cfg.get("restore_replant")
        cand_by = {c["cid"]: c for c in cands}
        evs = []
        for ln in open(f"{rf}/events.jsonl"):
            try:
                e = json.loads(ln)
            except Exception:                                    # noqa: BLE001
                continue
            if e.get("kind") == "prekill" and str(e.get("why", "")).startswith("F2"):
                evs.append(e)
        done = set()
        for e in evs:
            cid = e["cid"]
            if cid in done or (only_r is not None and cid not in only_r):
                continue
            done.add(cid)
            c = cand_by.get(cid)
            parts = str(e.get("design", "")).split(":")
            if not c or len(parts) < 3 or not c.get("feasible"):
                continue
            cell0 = cells.get(parts[1]) or {}
            etoks = next((x["tokens"] for x in self.f2space.get(cell0.get("anchor"), [])
                          if x["desc"] == parts[2] and x["rt_ok"]), None)
            if etoks is None or self.prefilter(etoks)["pass"] or \
                    not self.prefilter(c["tokens"])["pass"]:
                self.pdc["prekill_f2_stands"] += 1
                continue
            g = tuple(c["g"].split("-"))
            if g not in self.probe:
                continue
            rec2 = self.cache.get(job_id(c["tokens"], self.probe[g], 2, BUDGET, PROFILE))
            if not rec2 or not feasible(rec2):
                continue
            n0 = len(self.cells)
            c = dict(c, origin=dict(c.get("origin") or {}, amend2_replant=e["design"]))
            self.plant("bench", c, rec2)
            if len(self.cells) > n0:
                nc = list(self.cells.values())[-1]
                nc["amend2"] = {"action": "replant", "void_prekill": e["design"],
                                "cid": cid}
                self.write_cell(nc)
                self.pdc["cells_replanted_void_prekill"] += 1
            else:
                self.pdc["replant_rejected_again"] += 1
        # ---- training tasks
        for n, t0 in sorted(tasks.items(), key=lambda kv: kv[1]["seq"]):
            if only_t is not None and n not in only_t:
                continue
            t = copy.deepcopy(t0)
            t["tokens"] = self.round_trip(t["netlist"])["tokens"]
            self.train_tasks[n] = t
            if t["status"] != "ok":
                self.write_train(t)
                continue
            pf = self.prefilter(t["tokens"])
            pfs = {k: pf[k] for k in ("pass", "why", "group")}
            if not pf["pass"]:
                t["amend2"] = {"action": "tag", "status_before": "ok", "prefilter": pfs,
                               "label_before": t.get("difficulty"), "tag": TAG_PDC,
                               "outcome": TAG_PDC}
                t["status"] = TAG_PDC
                self.pdc[f"train_tagged_prefilter_{t.get('difficulty')}"] += 1
                self.write_train(t)
                continue
            t["amend2"] = {"action": "recheck", "status_before": "ok", "prefilter": pfs,
                           "label_before": t.get("difficulty")}
            t["status"] = "running"
            self.spawn("train:" + n, self.task_train_recheck(t), "train")
        self.log(f"AMENDMENT 2 restore from {rf}: cells={len(a1)} revalidate={len(revalidate)} "
                 f"requeue/revive={len(requeue)} tagged={sum(1 for c in self.cells.values() if c['status'] == TAG_PDC)} "
                 f"train={len(self.train_tasks)} recheck={sum(1 for t in self.train_tasks.values() if t['status'] == 'running')} "
                 f"pool rows={dict(n_pool)} next gen={self.search_gen0} pdc={dict(self.pdc)}")
        self.event("amend2_restore", restore_from=os.path.relpath(rf, REPO),
                   cells=len(a1), next_gen=self.search_gen0, pdc=dict(self.pdc),
                   revalidate=[c["name"] for c in revalidate],
                   requeue=[[c["name"], c["amend2"]["action"]] for c in requeue])
        self.spawn("search:bench", self.task_search("bench"), "search")
        self.spawn("search:train", self.task_search("train"), "train")

    def write_train(self, t):
        self.fh["train.jsonl"].write(jdump({k: v for k, v in t.items() if k != "tokens"})
                                     + "\n")
        self.fh["train.jsonl"].flush()

    def task_train_recheck(self, t):
        """AMENDMENT 2: re-check a pre-filter-passing amendment-1 training task under
        rl-v1.1. Witness proof: seed 1, then seed 2 only if seed 1 fails (>= 1 of
        {1, 2} as pre-registered; rows the port-DC requirement cannot change come
        from the cache bridge, a feasible rl-v1 row is re-sized and checked).
        Difficulty: library-solvable stays (anchor designs meet the requirement:
        port-dc-guard tests + pre-filter); otherwise re-derived from the port-DC-
        filtered pools (recorded anchor / single-edit designs), no new sizing."""
        tok, spec, bt = t["tokens"], t["spec"], t["bt"]
        t["amend1_stages"] = t.get("stages") or {}
        t["stages"] = {}
        wit = []
        for s in (1, 2):
            (r,) = yield [Job("T-wit", "train", tok, spec, s,
                              meta={"task": t["name"], "stage": "T-wit", "amend2_recheck": True})]
            res = r.get("res") or {}
            pd = res.get("port_dc") or {}
            wit.append({"seed": s, "jid": r["jid"], "feasible": feasible(r),
                        "derived": bool(r.get("derived_from")),
                        "infeasible_reason": res.get("infeasible_reason"),
                        "port_dc": {k: pd.get(k) for k in ("pass", "dVG_max_V", "dIdd_pct")}
                        if pd else None})
            if wit[-1]["feasible"]:
                break
        t["stages"]["witness"] = wit
        a2 = t["amend2"]
        if not any(x["feasible"] for x in wit):
            port = any("port_dc" in (x["infeasible_reason"] or "") for x in wit)
            t["status"] = TAG_PDC if port else "unproved"
            a2["outcome"] = t["status"]
            if port:
                a2["tag"] = TAG_PDC
            self.pdc[f"train_recheck_{'fail_port_dc' if port else 'fail_other'}"] += 1
            self.write_train(t)
            return
        old = t.get("difficulty")
        label, why = None, None
        if old == "library-solvable":
            label, why = old, t.get("difficulty_why")
        else:
            for d in self.pool[t["band"]]:
                if d.get("pdc_ok", True) and satisfies(d["metrics"], d["stab_ok"], bt, t["limits"]):
                    label, why = "library-solvable", f"recorded anchor design {d['id']}"
                    break
            if label is None:
                for key, lst in self.pool_se.items():
                    if key[0] != t["band"]:
                        continue
                    for d in lst:
                        if d.get("pdc_ok", True) and satisfies(d["metrics"], d["stab_ok"],
                                                               bt, t["limits"]):
                            label, why = "single-edit-solvable", f"recorded single edit {d['id']}"
                            break
                    if label:
                        break
            if label is None:
                label, why = "witness-only", ("no anchor feasible at seed 1; no known "
                                              "single edit meeting the port-DC requirement")
        t["difficulty"], t["difficulty_why"] = label, why
        a2["label_after"] = label
        a2["outcome"] = "ok" + ("" if label == old else f" (relabelled {old} -> {label})")
        self.pdc["train_recheck_ok"] += 1
        if label != old:
            self.pdc[f"train_relabelled_{old}->{label}"] += 1
        t["status"] = "ok"
        self.train_ok.append(t["name"])
        self.write_train(t)

    # --------------------------------------------------------------- training
    def train_have(self, g):
        """tasks counted against a grid point's quota (AMENDMENT 2: a task tagged
        amend2-port-dc no longer holds a slot; its point may be refilled)."""
        return sum(1 for t in self.train_tasks.values()
                   if t["g"] == gkey(g) and t["status"] != TAG_PDC)

    def plant_train(self, c, g, bt):
        if len(self.train_ok) + sum(1 for t in self.train_tasks.values()
                                    if t["status"] == "running") >= self.cfg["train_target"]:
            return
        have = self.train_have(g)
        if have >= self.cfg["train_quota_per_point"]:
            return
        # fence: accepted bench witnesses (both eras) + AMENDMENT 1: every
        # post-amendment planted bench witness (original and stripped) and spec
        bench_wl = {self.cells[n]["wl"] for n in self.accepted} | self.fence_wl
        bench_tok = {self.cells[n]["tok"] for n in self.accepted} | self.fence_tok
        if c["wl"] in bench_wl or c["tok"] in bench_tok:
            self.event("train_fenced", cid=c["cid"])
            return
        lim = planted_limits(bt, c["planted_from"])
        seq = len(self.train_tasks)
        name = f"t2-{g[0]}-{g[1]}-{seq:04d}"
        spec_path = write_spec(f"{self.rd}/specs/{name}.yaml", make_spec(
            g, lim, name, f"train-pool-v2 planted task ({g[0]}, {g[1]} objective) "
            f"from search witness {c['cid']}"))
        if spec_sha(spec_path) in self.fence_spec:
            self.event("train_fenced", cid=c["cid"], why="spec equals a bench spec")
            return
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
            if d.get("pdc_ok", True) and satisfies(d["metrics"], d["stab_ok"], bt, t["limits"]):
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
                    if d.get("pdc_ok", True) and satisfies(d["metrics"], d["stab_ok"], bt, t["limits"]):
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
        beh = self.bench_elapsed_h()
        acc = len(self.accepted)
        srep, sel = selection_report([self.cells[c] for c in self.accepted], self.cfg)
        rate_calls_h = len(self.recent)
        eta = {}
        if acc and beh > 0:
            r = acc / beh
            eta["bench_cells_per_h"] = round(r, 3)
            eta["bench_eta_h_to_target"] = round(max(0, self.cfg["bench_target"] - len(sel)) / r, 1)
        eta["bench_elapsed_h_since_amendment"] = round(beh, 3)
        eta["bench_hard_stop_h"] = round(max(0.0, self.cfg["bench_max_hours"] - beh), 1)
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
                      "extra_readonly_cache": self.n_extra_cache,
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
                      "era": self.phase,
                      "accepted_per_core_class": dict(self.core_accepted),
                      "accepted_per_parent": dict(self.parent_accepted),
                      "accepted_core_atom_hist": dict(self.core_atom_count),
                      "accepted_per_band": srep["accepted"]["per_band"],
                      "accepted_per_band_type": srep["accepted"]["per_band_type"],
                      "class_rule_active": srep["class_rule_active"],
                      "accepted_per_primary_atom": dict(self.primary_accepted),
                      "accepted_atom_prevalence": srep["accepted"]["atom_prevalence"],
                      "selectable_a_signature": {
                          "n": srep["variants"]["a_signature"]["n"],
                          "per_class": srep["variants"]["a_signature"]["per_class"],
                          "per_parent": srep["variants"]["a_signature"]["per_parent"],
                          "per_band_type": srep["variants"]["a_signature"]["per_band_type"]},
                      "selectable_b_primary_atom": {
                          "n": srep["variants"]["b_primary_atom"]["n"],
                          "per_primary_atom": srep["variants"]["b_primary_atom"]["per_primary_atom"],
                          "per_parent": srep["variants"]["b_primary_atom"]["per_parent"],
                          "per_band_type": srep["variants"]["b_primary_atom"]["per_band_type"]},
                      "selectable_per_core_class": srep["selected"]["per_class"],
                      "selectable_per_parent": srep["selected"]["per_parent"],
                      "selectable_per_band": srep["selected"]["per_band"],
                      "selectable_per_band_type": srep["selected"]["per_band_type"],
                      "selection_without_nb_quota": srep["without_nb_quota"]["n"],
                      "nb_quota_binding": srep["nb_quota_binding"],
                      "quotas": srep["quotas"],
                      "planted_per_band_type": dict(Counter(c["bt"] for c in self.cells.values())),
                      "planted_per_parent": dict(Counter(c["anchor"] for c in self.cells.values())),
                      "floor_rejects": dict(self.floor_rejects),
                      "strip": dict(Counter((self.cells[n].get("core") or {}).get(
                          "strip", {}).get("flag") for n in self.accepted)),
                      "steer": self.steer_last,
                      "stage_started": dict(self.stage_counts),
                      "kills": dict(self.kill_counts),
                      "bench_done": self.bench_done,
                      "search_done": self.bench_search_done},
            "pre_amendment": {
                "cells": len(self.pre_cells),
                "status": dict(Counter(c["status"] for c in self.pre_cells.values())),
                "accepted": sum(1 for c in self.pre_cells.values() if c["status"] == "accepted"),
                "selectable": 0,
                "core_classes_done": len(self.pre_core),
                "core_class_hist": dict(Counter(v["signature"] for v in self.pre_core.values())),
                "primary_atom_hist": dict(Counter(v["primary_atom"] for v in self.pre_core.values())),
                "seed_topologies": len(self.pre_cands),
                "seeds_used": len(self.pre_seed_used)},
            "amendment2": None if not self.amend2 else {
                "profile": CUR_PROFILE,
                "t_amend2": (time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.t_amend2))
                             if self.t_amend2 else None),
                "bench_end_unchanged": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(self.t_amend + 3600 * self.cfg["bench_max_hours"])),
                "class_rule": self.cfg.get("class_rule"),
                "port_dc": {
                    **dict(sorted(self.pdc.items())),
                    "gen_rejects_prefilter": {s: self.search_stats[s].get("rej_port_dc_prefilter", 0)
                                              for s in ("bench", "train")},
                    "cells_by_action_outcome": dict(Counter(
                        f"{c['amend2'].get('action')}:{c['amend2'].get('outcome') or c['status']}"
                        for c in self.cells.values() if isinstance(c.get("amend2"), dict))),
                    "cells_tagged": sum(1 for c in self.cells.values()
                                        if (c.get("amend2") or {}).get("tag") == TAG_PDC),
                    "train_by_action_outcome": dict(Counter(
                        f"{t['amend2'].get('action')}:{t['amend2'].get('outcome') or t['status']}"
                        for t in self.train_tasks.values() if isinstance(t.get("amend2"), dict))),
                    "train_tagged": sum(1 for t in self.train_tasks.values()
                                        if t["status"] == TAG_PDC)}},
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
            "verifier": CUR_PROFILE, "seeds": [s for s, _r in parent_recs],
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
    readme = ("EVAL-ONLY. Witness (proof of solvability) of a bench-v2 cell. Never use "
              "in SFT/RL/prompt data (PREREG-BENCH-V2 fence).\n")
    core = c.get("core") or {}
    strip = core.get("strip") or {}
    orig = c.get("witness_original")
    if orig:
        readme += ("AMENDMENT 1: this witness is the ablation CORE of the search-found "
                   "witness (non-essential/inert edit groups stripped) and re-verified "
                   "(A1/A2/A3, results.json). The original search witness is kept in "
                   "original/.\n")
    if c.get("amend2"):
        readme += (f"AMENDMENT 2: this cell was {c['amend2'].get('action')}d under verifier "
                   f"{CUR_PROFILE} (rl-v1 + input-port DC requirement); every stage in "
                   "results.json is an rl-v1.1 run.\n")
        if c.get("witness_original_amend1") and not orig:
            readme += ("original/ (if present) is the AMENDMENT-1 search witness of which "
                       "this witness is the ablation core -- a fenced record, not the "
                       "cell's witness.\n")
    atomic_write(f"{d}/witness/README", readme)

    def put(dd, netlist, tokens, script, repairs, tok, wl, stages, note):
        os.makedirs(dd, exist_ok=True)
        atomic_write(f"{dd}/witness.net", "* bench-v2 witness (EVAL-ONLY). Found by search "
                     f"from anchor {A['family']}; edit script in edit_script.json. {note}\n"
                     + netlist)
        atomic_write(f"{dd}/witness.tokens.json", json.dumps(tokens))
        atomic_write(f"{dd}/edit_script.json", json.dumps(
            {"parent_anchor": A["family"], "script": script, "repairs": repairs,
             "move_class": c["cls"], "core_signature": core.get("signature"),
             "core_groups": core.get("core_groups"), "legacy_class": c.get("legacy_class"),
             "label": c.get("label"), "edit_labels": c.get("edit_labels"),
             "search_cid": c["cid"], "wl_hash": wl, "tok_hash": tok}, indent=1))
        runs = {}
        for stg, lst, sp in stages:
            for x in lst:
                rec = cache.get(x["jid"]) or {}
                runs[f"{stg}_seed{x['seed']}"] = {
                    "seed": x["seed"], "budget": BUDGET, "spec": sp,
                    "result": rec.get("res"), "era": rec.get("era")}
        atomic_write(f"{dd}/results.json", json.dumps(
            {"verifier": CUR_PROFILE, "pdk": PDK, "budget": BUDGET,
             "tight_limits": c["tight_limits"], "limits": c["limits"], "runs": runs},
            indent=1, default=repr))
    tight_note = "tightened (limits in results.json)"
    orig_stages = [(stg, (c["stages"].get(stg) or {}).get("runs", []),
                    "spec.yaml" if stg != "A2" else tight_note) for stg in ("A1", "A2", "A3")]
    if orig:
        put(f"{d}/witness", c["netlist"], c.get("tokens"), c["script"], c["repairs"],
            c["tok"], c["wl"], [("A1", strip.get("A1", []), "spec.yaml"),
                                ("A2", strip.get("A2", []), tight_note),
                                ("A3", strip.get("A3", []), "spec.yaml")],
            "AMENDMENT-1 stripped core witness.")
        put(f"{d}/witness/original", orig["netlist"], orig.get("tokens"), orig["script"],
            orig["repairs"], orig["tok"], orig["wl"], orig_stages,
            "Original (unstripped) search witness.")
    else:
        put(f"{d}/witness", c["netlist"], c.get("tokens"), c["script"], c["repairs"],
            c["tok"], c["wl"], orig_stages,
            f"AMENDMENT-1 strip: {strip.get('flag')}.")
    meta = {k: v for k, v in c.items() if k not in ("tokens", "netlist", "evidence")}
    if meta.get("witness_original"):
        meta["witness_original"] = {k: v for k, v in meta["witness_original"].items()
                                    if k != "tokens"}
    meta["stages"] = {k: {kk: vv for kk, vv in v.items() if kk != "runs"} | {
        "n_runs": len(v.get("runs", []))} for k, v in c["stages"].items()}
    atomic_write(f"{d}/cell.json", json.dumps(meta, indent=1, default=repr))


CLASS_RULES = ("signature", "primary_atom")


def class_key(c, rule):
    """class used by the 25 % cap: (a) 'signature' = whole core-fix signature (as
    pre-registered, the default); (b) 'primary_atom' = the core's primary atom
    (pending user ruling). Falls back to the signature if no primary atom."""
    if rule == "primary_atom":
        return c.get("primary_atom") or c["cls"]
    return c["cls"]


def atom_prevalence(cells):
    """(c) fraction of cells whose core signature contains each atom."""
    n = len(cells)
    cnt = Counter(a for c in cells for a in set(sig_atoms(c["cls"])))
    return {a: {"n": k, "frac": round(k / n, 3)} for a, k in
            sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))} if n else {}


def _cfg_eras(cfg):
    """selectable eras of a config: AMENDMENT 2 runs select amendment-1 cells
    re-accepted under rl-v1.1 and amendment-2 cells; earlier configs amendment-1."""
    return POST_ERAS if cfg.get("amend2") else AMEND


def _era_ok(c, era):
    if era is None:
        return True
    if isinstance(era, (tuple, list, set)):
        return c.get("era_tag") in era
    return c.get("era_tag") == era


def select_cells(cells, cfg, nb_quota=True, era="cfg", rule=None):
    """Final selection (AMENDMENT 1). Only ACCEPTED cells of era `era` (post-
    amendment) are selectable; pre-amendment cells never are. The selection of
    size n must satisfy
      <= 1 cell per witness WL hash,
      no class > floor(cap_frac * n)            (25 %; class = class_key(c, rule),
                                                 rule = cfg['class_rule'] unless given),
      no parent anchor > floor(parent_frac * n) (40 %),
      >= ceil(nb_frac * n) narrowband cells     (25 %; skipped if nb_quota=False).
    Largest n <= bench_target wins. Deterministic greedy per n: first take
    narrowband cells in acceptance order until the narrowband quota is met, then
    fill in acceptance order; all caps are checked at every pick."""
    rule = rule or cfg.get("class_rule", "signature")
    assert rule in CLASS_RULES, rule
    era = _cfg_eras(cfg) if era == "cfg" else era
    cells = sorted([c for c in cells if _era_ok(c, era)],
                   key=lambda c: c["seq"])
    for n in range(min(cfg["bench_target"], len(cells)), 0, -1):
        ccap = max(1, int(math.floor(cfg["cap_frac"] * n + 1e-9)))
        pcap = max(1, int(math.floor(cfg.get("parent_frac", 1.0) * n + 1e-9)))
        nbq = int(math.ceil(cfg.get("nb_frac", 0.0) * n - 1e-9)) if nb_quota else 0
        pick, cnt, pc, wls, ids = [], Counter(), Counter(), set(), set()

        def ok(c):
            return (c["wl"] not in wls and cnt[class_key(c, rule)] < ccap
                    and pc[c["anchor"]] < pcap and id(c) not in ids)

        def take(c):
            pick.append(c)
            ids.add(id(c))
            cnt[class_key(c, rule)] += 1
            pc[c["anchor"]] += 1
            wls.add(c["wl"])
        for c in cells:
            if sum(1 for x in pick if x["bt"] == "narrowband") >= nbq:
                break
            if c["bt"] == "narrowband" and ok(c):
                take(c)
        if sum(1 for x in pick if x["bt"] == "narrowband") < nbq:
            continue
        for c in cells:
            if len(pick) >= n:
                break
            if ok(c):
                take(c)
        if len(pick) == n:
            return sorted(pick, key=lambda c: c["seq"])
    return []


def selection_report(cells, cfg, era="cfg"):
    """quota bookkeeping for progress / INDEX. The ACTIVE selection uses
    cfg['class_rule'] (default 'signature', as pre-registered). Both class-cap
    variants are always computed: (a) whole-signature, (b) primary-atom; plus the
    active rule without the narrowband quota (shortfall report) and (c) the
    any-atom prevalence over accepted and selected cells."""
    era = _cfg_eras(cfg) if era == "cfg" else era
    acc = [c for c in cells if _era_ok(c, era)]
    rule = cfg.get("class_rule", "signature")
    var = {r: select_cells(acc, cfg, True, era, r) for r in CLASS_RULES}
    sel = var[rule]
    sel_nonb = select_cells(acc, cfg, False, era, rule)

    def hist(lst):
        return {"n": len(lst), "per_class": dict(Counter(c["cls"] for c in lst)),
                "per_primary_atom": dict(Counter(c.get("primary_atom") for c in lst)),
                "per_parent": dict(Counter(c["anchor"] for c in lst)),
                "per_band": dict(Counter(c["band"] for c in lst)),
                "per_band_type": dict(Counter(c["bt"] for c in lst)),
                "atom_prevalence": atom_prevalence(lst)}
    return {"class_rule_active": rule,
            "selected": hist(sel), "selected_names": [c["name"] for c in sel],
            "variants": {"a_signature": hist(var["signature"]),
                         "b_primary_atom": hist(var["primary_atom"])},
            "variant_names": {r: [c["name"] for c in v] for r, v in var.items()},
            "without_nb_quota": hist(sel_nonb),
            "accepted": hist(acc),
            "quotas": {"class_cap_frac": cfg["cap_frac"], "class_rule": rule,
                       "parent_cap_frac": cfg.get("parent_frac"),
                       "narrowband_min_frac": cfg.get("nb_frac"),
                       "target": cfg["bench_target"], "min": cfg["bench_min"]},
            "shortfall_vs_min": max(0, cfg["bench_min"] - len(sel)),
            "nb_quota_binding": len(sel_nonb) > len(sel)}, sel


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
    # AMENDMENT 1: only post-amendment accepted cells are selectable
    # AMENDMENT 2: + amendment-2 cells; an amendment-1 cell is selectable only if it
    # was re-accepted under rl-v1.1 (status accepted again, never tagged)
    acc_all = [c for c in cells.values() if c["status"] == "accepted"]
    eras = POST_ERAS if cfg.get("amend2") else (AMEND,)
    acc = [c for c in acc_all if c.get("era_tag") in eras and c.get("selectable", True)]
    srep, sel = selection_report(acc, cfg, era=eras)
    sub = {"full": "", "smoke": "smoke/", "smoke-a1": "smoke/amend1-",
           "smoke-a2": "smoke/amend2-"}[mode]
    lib = f"{REPO}/kaggle/editcap-lib-v2" if mode == "full" else f"{CAMP}/{sub}editcap-lib-v2"
    tp = f"{REPO}/kaggle/train-pool-v2" if mode == "full" else f"{CAMP}/{sub}train-pool-v2"
    os.makedirs(lib, exist_ok=True)
    index = {"prereg": "kaggle/PREREG-BENCH-V2.md (+ AMENDMENT 1"
                       + (", AMENDMENT 2)" if cfg.get("amend2") else ")"),
             "verifier": cfg["profile"],
             "pdk": PDK, "budget": BUDGET, "mode": mode, "n_accepted": len(acc),
             "n_accepted_pre_amendment_not_selectable": len(acc_all) - len(acc),
             "n_selected": len(sel), "shortfall": max(0, cfg["bench_min"] - len(sel)),
             "floors": {m: {"side": sd, "limit": F} for m, (sd, F) in FLOORS.items()},
             "selection": srep,
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
                                     "core_signature": c["cls"],
                                     "primary_atom": c.get("primary_atom"),
                                     "legacy_class": c.get("legacy_class"),
                                     "parent_anchor": c["anchor"], "witness_wl": c["wl"],
                                     "witness_tok": c["tok"], "limits": c["limits"],
                                     "strip": ((c.get("core") or {}).get("strip") or {}).get("flag"),
                                     "floor_violations": floor_violations(c["limits"]),
                                     "smoke": c.get("smoke", False)}
    atomic_write(f"{lib}/INDEX.json", json.dumps(index, indent=1))
    # ---- training pool
    tasks = load_jsonl_last(f"{rd}/train.jsonl", "name")
    ok = [t for t in tasks.values() if t["status"] == "ok"]
    # fence: every accepted cell (both eras) + every post-amendment planted cell
    # (original and stripped witness), by WL / token hash and spec
    # AMENDMENT 2: + every amendment-2 planted cell and the amendment-1 original
    # witness of a cell re-validated under rl-v1.1 (witness_original_amend1)
    fcells = acc_all + [c for c in cells.values() if c.get("era_tag") in POST_ERAS
                        and c["status"] != "accepted"]
    wkeys = ("witness_original", "witness_original_amend1")
    bench_wl = {c["wl"] for c in fcells} | {(c.get(k) or {}).get("wl")
                                            for c in fcells for k in wkeys} - {None}
    bench_tok = {c["tok"] for c in fcells} | {(c.get(k) or {}).get("tok")
                                              for c in fcells for k in wkeys} - {None}
    bench_specs = {json.dumps(c["limits"], sort_keys=True) + c["g"] for c in fcells}
    os.makedirs(tp, exist_ok=True)
    tindex = {"prereg": "kaggle/PREREG-BENCH-V2.md", "verifier": cfg["profile"], "mode": mode,
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
    elif a.cmd == "amend2-snapshot":
        # AMENDMENT 2: freeze the amendment-1 record (copies, never moved) at the
        # stop; restore_amend2 rebuilds the state from it. Result cache stays.
        import shutil
        rd = a.run_dir or CONFIGS[a.mode]["run_dir"]
        d = f"{rd}/amendment-1-record"
        if os.path.isdir(d):
            raise SystemExit(f"snapshot exists: {d}")
        pid = f"{rd}/sched.pid"
        if os.path.exists(pid):
            try:
                cmd = open(f"/proc/{int(open(pid).read().strip())}/cmdline").read()
            except (OSError, ValueError):
                cmd = ""
            if "bv2.py" in cmd and " run" in cmd.replace("\0", " "):
                raise SystemExit("scheduler still running: stop it first")
        os.makedirs(d)
        man = {"taken": time.strftime("%Y-%m-%dT%H:%M:%S"), "amendment": AMEND2,
               "prereg_commit": "1a0413fb9", "files": {}}
        for f in ("cells.jsonl", "candidates.jsonl", "events.jsonl", "train.jsonl",
                  "progress.json", "sched.log", "start.json",
                  "pre-amendment-core-classes.json"):
            if os.path.exists(f"{rd}/{f}"):
                shutil.copy2(f"{rd}/{f}", f"{d}/{f}")
                man["files"][f] = hashlib.md5(open(f"{d}/{f}", "rb").read()).hexdigest()
        n = sum(1 for _ in open(f"{rd}/results.jsonl")) if os.path.exists(
            f"{rd}/results.jsonl") else 0
        man["results_jsonl_rows_at_snapshot"] = n
        atomic_write(f"{d}/MANIFEST.json", json.dumps(man, indent=1))
        print(json.dumps(man, indent=1))
    elif a.cmd == "amend-snapshot":
        # AMENDMENT 1: freeze the pre-amendment record (copies, never moved) before
        # the first post-amendment start; the result cache stays in place.
        import shutil
        rd = a.run_dir or CONFIGS[a.mode]["run_dir"]
        d = f"{rd}/pre-amendment"
        if os.path.isdir(d):
            raise SystemExit(f"snapshot exists: {d}")
        os.makedirs(d)
        man = {"taken": time.strftime("%Y-%m-%dT%H:%M:%S"), "amendment": AMEND,
               "prereg_commit": "78ccdf0b4", "files": {}}
        for f in ("cells.jsonl", "candidates.jsonl", "events.jsonl", "train.jsonl",
                  "progress.json", "sched.log", "start.json"):
            if os.path.exists(f"{rd}/{f}"):
                shutil.copy2(f"{rd}/{f}", f"{d}/{f}")
                man["files"][f] = hashlib.md5(open(f"{d}/{f}", "rb").read()).hexdigest()
        n = sum(1 for _ in open(f"{rd}/results.jsonl")) if os.path.exists(
            f"{rd}/results.jsonl") else 0
        man["results_jsonl_rows_at_snapshot"] = n
        atomic_write(f"{d}/MANIFEST.json", json.dumps(man, indent=1))
        print(json.dumps(man, indent=1))
    elif a.cmd == "status":
        rd = a.run_dir or CONFIGS[a.mode]["run_dir"]
        print(open(f"{rd}/progress.json").read())
    else:
        raise SystemExit(f"unknown command {a.cmd}")


if __name__ == "__main__":
    main()
