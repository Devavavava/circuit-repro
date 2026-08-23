"""E-11 §10.3 REGROWTH SMOKE -- ZERO counted evals, no L1 probes.

Pre-reg: engineer/E11-GENEDIT.md §10.3 + §2 (cut-and-regrow with the v7
checkpoint) + §3 (durable edit logging). Confirms the adopted main-line v7
generator (`ft_p5v7_v2.pth`) emits realizable sequences under prefix-conditioned
continuation BEFORE the scored campaign is committed.

Mechanism (§2), from ONE anchor = E-9's dhruva-s reached anchor topology:
  * Emit the anchor's AnalogGenie token sequence (templates.emit_sequence
    round-trip; WL-hash-exact).
  * Cut depth c sampled UNIFORMLY over device-token positions (c=0 permitted =
    full regeneration). Keep the prefix; regenerate the remainder with the v7
    checkpoint by temperature sampling (suffix regrowth -- the model is
    autoregressive). Sampling constants are FROZEN (recorded below), taken from
    the main line's OWN v7 p5 sampling path (finetune.sample defaults):
        temperature   = 0.7
        max_new_tokens = 256
    and narrowband class-token conditioning `<LNA_NB>` (the dhruva-s anchor is a
    3-inductor narrowband design), exactly as finetune.sample builds the p5
    prefix `[<LNA_NB>, VSS]`. No per-goal tuning (G0-FAIRNESS).

Gates -- FREE only, NO env.evaluate, NO counted evals (ngspice count MUST be 0):
  L0      sane() structural sanity (on the token-round-trip netlist)
  realize M.realize (token round-trip + Topology.valid + structural_screen +
          topo_to_netlist)  -- all 0 sims.

Sample until 50 DISTINCT L0-passing candidates OR 500 attempts. Every proposal
(incl. L0/realize rejects) is appended to engineer/data/e11_edit_log/edits.jsonl
in the §3 schema; token sequences are content-addressed under .../seqs/<sha>.txt.

CONTAINMENT: read-only toward lna/ and engineer/; the v7 checkpoint is read from
the main checkout (read-only). Writes ONLY under engineer/data/e11_edit_log/ and
engineer/data/e11_null/../e11_smoke_report.json. PYTHONHASHSEED=0.

    python e11_smoke.py
"""
import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

HERE = os.path.dirname(os.path.abspath(__file__))
ENG = HERE
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (ENG, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import torch  # noqa: E402

# ---------------------------------------------------------- FROZEN constants
CKPT = "/home/dpatni/circuit-repro/lna/out/ft_p5v7_v2.pth"   # main-adopted P5-v7
ARM = "p5"
ANCHOR_TASK = "dhruva-s-t2-a"          # E-9's dhruva-s reached anchor
CLASS = "nb"                            # dhruva-s is narrowband (3 inductors)
TEMPERATURE = 0.7                       # finetune.sample default (main line)
MAX_NEW_TOKENS = 256                   # finetune.sample default (main line)
SEED = 1337                            # main line's sampling seed
TARGET_DISTINCT = 50
MAX_ATTEMPTS = 500

EDIT_DIR = os.path.join(HERE, "data", "e11_edit_log")
SEQ_DIR = os.path.join(EDIT_DIR, "seqs")
EDITS_JSONL = os.path.join(EDIT_DIR, "edits.jsonl")
REPORT = os.path.join(HERE, "data", "e11_null", "e11_smoke_report.json")


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git_sha():
    try:
        import datastore as ds
        return ds.git_sha()
    except Exception:
        return None


def _sha(tokens):
    return hashlib.sha1("->".join(tokens).encode()).hexdigest()


def _store_seq(tokens):
    """Content-address a token sequence under seqs/<sha>.txt; return the sha."""
    sha = _sha(tokens)
    p = os.path.join(SEQ_DIR, f"{sha}.txt")
    if not os.path.exists(p):
        tmp = p + ".tmp"
        with open(tmp, "w") as fh:
            fh.write("->".join(tokens) + "->")
        os.replace(tmp, p)
    return sha


def main():
    ap = argparse.ArgumentParser(description="E-11 regrowth smoke")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    os.makedirs(SEQ_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)

    import finetune as FT
    import genie_common as GC
    from genie_common import VOCAB_SIZE, TRUNCATE_ID
    import templates as T
    import moves as M
    from topology import Topology
    from tasks import get
    from env import Env

    # ---- confirm ngspice is never invoked in this task -------------------
    import extract as EX
    ng = {"n": 0}
    if hasattr(EX, "run_and_extract"):
        _orig = EX.run_and_extract

        def _wrapped(*args, **kw):
            ng["n"] += 1
            return _orig(*args, **kw)
        EX.run_and_extract = _wrapped

    # ---- load the v7 checkpoint (extended p5 vocab, 1008) -----------------
    if not os.path.exists(CKPT):
        raise SystemExit(f"missing checkpoint: {CKPT}")
    FT.ckpt_path = lambda arm, winners=False, tag=None: CKPT
    _devs, stoi, _vsz = FT.ext_vocab(ARM)          # 1005 + [<LNA_NB>,<LNA_WB>,<OTHER>]
    torch.manual_seed(SEED)
    model = FT.load_ft(ARM, a.device, winners=True)
    cls_tok = "<LNA_NB>" if CLASS == "nb" else "<LNA_WB>"
    cls_id = stoi[cls_tok]

    # ---- the anchor: E-9's dhruva-s reached anchor topology ---------------
    env = Env(get(ANCHOR_TASK), budget=1, seed=1, logger=None)
    base_spec = env.spec
    anchor_nl, _ = T.topo_to_netlist(env.topo)
    anchor_seq = T.emit_sequence(anchor_nl)
    if not anchor_seq:
        raise SystemExit("anchor topology did not emit a token sequence")
    anchor_seq = [str(t) for t in anchor_seq]
    anchor_seq_sha = _store_seq(anchor_seq)
    # anchor spec device-budget for sane()'s bounds (structural screen bounds)
    max_dev = base_spec.topology.get("device_budget", [3, 16])[1]
    min_dev = base_spec.topology.get("device_budget", [3, 16])[0]

    # device-token positions: bare device names (no pin underscore, not a rail).
    def is_dev_tok(tk):
        return ("_" not in tk) and tk not in ("VSS", "VDD", "TRUNCATE")
    dev_positions = [i for i, tk in enumerate(anchor_seq) if is_dev_tok(tk)]
    # c=0 allowed -> full regeneration (prefix = class token only). The cut set is
    # {0} U device-token positions; c is the number of anchor tokens KEPT.
    cut_choices = [0] + dev_positions

    anchor_wl = None
    try:
        from novelty import wl_features
        anchor_wl = wl_features(env.topo)[0]
    except Exception:
        pass

    print(f"[smoke] anchor={ANCHOR_TASK} wl={anchor_wl} seq_len={len(anchor_seq)} "
          f"sha={anchor_seq_sha[:12]} device_positions={len(dev_positions)} "
          f"class={cls_tok} temp={TEMPERATURE} max_new={MAX_NEW_TOKENS}", flush=True)

    rng = __import__("random").Random(SEED)
    log_fh = open(EDITS_JSONL, "a", buffering=1)   # append-only, line-buffered

    attempts = 0
    l0_pass = 0
    realize_pass = 0
    distinct_l0 = set()            # distinct L0-passing candidate WL/seq hashes
    cut_hist = Counter()
    regrown_lens = []
    gate_counts = Counter()
    t0 = time.time()

    while len(distinct_l0) < TARGET_DISTINCT and attempts < MAX_ATTEMPTS:
        attempts += 1
        c = rng.choice(cut_choices)             # tokens KEPT from the anchor
        prefix_toks = anchor_seq[:c]
        prefix_ids = [cls_id] + [stoi[t] for t in prefix_toks]

        try:
            rows, _steps = GC.generate_batch(
                model, [prefix_ids], max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE, device=a.device)
        except Exception as e:
            gate_counts["sample_error"] += 1
            _log(log_fh, anchor_wl, anchor_seq_sha, c, None, None,
                 "sample_error", detail=repr(e))
            continue

        ids = [int(x) for x in rows[0].tolist()]
        ids = [x for x in ids if x < VOCAB_SIZE]        # drop class token(s)
        circ_ids = ids[:ids.index(TRUNCATE_ID)] if TRUNCATE_ID in ids else ids
        regrown_toks = [GC.ITOS[i] for i in circ_ids]
        regrown_len = len(regrown_toks) - c             # tokens the model added
        regrown_sha = _store_seq(regrown_toks)

        # ---- L0: parse + topo_to_netlist + sane() (0 sims) ---------------
        gate = "L0"                                     # furthest gate FAILED-at
        l0_ok = False
        try:
            topo = Topology(regrown_toks)
            if topo.valid:
                nl, _ = T.topo_to_netlist(topo)
                if nl is not None and M.sane(nl, max_dev=max_dev, min_dev=min_dev):
                    l0_ok = True
        except Exception:
            l0_ok = False

        if not l0_ok:
            gate_counts["L0_fail"] += 1
            _log(log_fh, anchor_wl, anchor_seq_sha, c, regrown_sha, regrown_len,
                 "L0")
            continue

        l0_pass += 1
        # distinctness keyed on the regrown token sha (content-addressed)
        distinct_l0.add(regrown_sha)
        cut_hist[c] += 1
        regrown_lens.append(regrown_len)

        # ---- realize: token round-trip + structural_screen (0 sims) ------
        r = None
        try:
            r = M.realize(nl, base_spec)
        except Exception:
            r = None
        if r is not None:
            realize_pass += 1
            gate = "realize"
            gate_counts["realize_pass"] += 1
        else:
            gate = "L0"      # passed L0, failed realize -> furthest = L0
            gate_counts["realize_fail"] += 1

        wl = r[2] if r is not None else None
        _log(log_fh, anchor_wl, anchor_seq_sha, c, regrown_sha, regrown_len,
             gate, realized_wl=wl)

    log_fh.close()
    wall = time.time() - t0

    lens = regrown_lens
    report = {
        "campaign": "E-11", "phase": "regrowth-smoke",
        "anchor_task": ANCHOR_TASK, "anchor_wl": anchor_wl,
        "anchor_seq_sha": anchor_seq_sha, "anchor_seq_len": len(anchor_seq),
        "n_device_positions": len(dev_positions),
        "frozen_constants": {
            "generator_checkpoint": "ft_p5v7_v2.pth (cross-line import, main-adopted)",
            "arm": ARM, "class_token": cls_tok, "temperature": TEMPERATURE,
            "max_new_tokens": MAX_NEW_TOKENS, "seed": SEED,
            "cut_rule": "uniform over {0} U device-token positions (c=tokens kept)",
            "target_distinct": TARGET_DISTINCT, "max_attempts": MAX_ATTEMPTS,
        },
        "attempts": attempts,
        "distinct_l0_candidates": len(distinct_l0),
        "l0_pass_count": l0_pass,
        "l0_pass_rate": round(l0_pass / attempts, 4) if attempts else 0.0,
        "realize_pass_count": realize_pass,
        "realize_pass_rate": round(realize_pass / attempts, 4) if attempts else 0.0,
        "realize_rate_of_l0": round(realize_pass / l0_pass, 4) if l0_pass else 0.0,
        "cut_depth_histogram": dict(sorted(cut_hist.items())),
        "regrown_len_stats": {
            "n": len(lens),
            "min": min(lens) if lens else None,
            "max": max(lens) if lens else None,
            "mean": round(sum(lens) / len(lens), 2) if lens else None,
        },
        "gate_counts": dict(gate_counts),
        "ngspice_calls": ng["n"],
        "wall_s": round(wall, 1),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "git_sha": _git_sha(), "ts": _now(),
    }
    tmp = REPORT + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    os.replace(tmp, REPORT)

    print(json.dumps(report, indent=1))
    if ng["n"] != 0:
        print(f"!! WARNING: ngspice_calls = {ng['n']} (MUST be 0)", flush=True)
    return 0


def _log(fh, anchor_wl, anchor_seq_sha, cut_depth, regrown_sha, regrown_len,
         gate, realized_wl=None, detail=None, era="E-11"):
    rec = {"campaign": "E-11", "goal": "smoke", "arm": "c", "seed": SEED,
           "anchor_wl": anchor_wl, "anchor_seq_sha": anchor_seq_sha,
           "cut_depth": cut_depth, "regrown_tokens_sha": regrown_sha,
           "regrown_len": regrown_len, "gate": gate,
           "realized_wl": realized_wl,
           "l1_objective": None, "stage2": None,
           "era": era, "ts": _now()}
    if detail:
        rec["detail"] = detail
    fh.write(json.dumps(rec, default=str) + "\n")


if __name__ == "__main__":
    sys.exit(main())
