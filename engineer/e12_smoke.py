"""E-12 P2 zero-sim smoke for a trained editor (C1 or C2).

Same mechanism as e11_smoke.py (E-11 §10.3): from the standard dhruva-s reached
anchor, cut uniformly over {0} U device-token positions, keep the prefix, regrow
the suffix with the trained editor by temperature sampling. Gate with L0 sane()
+ realize() only -- ZERO ngspice, NO env.evaluate. Sample until 50 distinct
L0-passing candidates OR 500 attempts.

For C2 the goal's bin prefix (dhruva-s bins) is prepended after the class token,
exactly as the C2 training conditioned the model.

Every proposal is appended to engineer/data/e11_edit_log/edits.jsonl in the E-11
schema with campaign "e12-p2smoke". PYTHONHASHSEED=0, frozen sampling constants
(temp 0.7 / max_new 256 / seed 1337) identical to the v7 baseline smoke.

    python e12_smoke.py --arm c1 --ckpt out_editor/editor_c1.pth
    python e12_smoke.py --arm c2 --ckpt out_editor/editor_c2.pth
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
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import torch  # noqa: E402
import e12_train_common as C  # noqa: E402

ANCHOR_TASK = "dhruva-s-t2-a"
CLASS = "nb"
TEMPERATURE = 0.7
MAX_NEW_TOKENS = 256
SEED = 1337
TARGET_DISTINCT = 50
MAX_ATTEMPTS = 500

EDIT_DIR = os.path.join(HERE, "data", "e11_edit_log")
SEQ_DIR = os.path.join(EDIT_DIR, "seqs")
EDITS_JSONL = os.path.join(EDIT_DIR, "edits.jsonl")


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(tokens):
    return hashlib.sha1("->".join(tokens).encode()).hexdigest()


def _store_seq(tokens):
    sha = _sha(tokens)
    p = os.path.join(SEQ_DIR, f"{sha}.txt")
    if not os.path.exists(p):
        tmp = p + ".tmp"
        with open(tmp, "w") as fh:
            fh.write("->".join(tokens) + "->")
        os.replace(tmp, p)
    return sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["c1", "c2"])
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    os.makedirs(SEQ_DIR, exist_ok=True)

    import finetune as FT
    import genie_common as GC
    from genie_common import VOCAB_SIZE, TRUNCATE_ID
    from Models.GPT import GPTLanguageModel
    from genie_common import N_EMBD, N_HEAD, N_LAYER, BLOCK_SIZE, DROPOUT
    import templates as T
    import moves as M
    from topology import Topology
    from tasks import get
    from env import Env

    # guarantee zero ngspice
    import extract as EX
    ng = {"n": 0}
    if hasattr(EX, "run_and_extract"):
        _orig = EX.run_and_extract

        def _wrapped(*args, **kw):
            ng["n"] += 1
            return _orig(*args, **kw)
        EX.run_and_extract = _wrapped

    # ---- vocab + model: C1 uses p5 (1008); C2 uses p5+16 spec tokens (1024) ---
    if a.arm == "c1":
        devs, stoi, vocab = FT.ext_vocab("p5")
        stoi = {d: i for i, d in enumerate(devs)}
        spec_prefix_toks = []
    else:
        devs, stoi, vocab = C.ext_vocab_c2()
        spec_prefix_toks = None  # filled after we know the dhruva-s bin prefix

    if not os.path.exists(a.ckpt):
        raise SystemExit(f"missing checkpoint: {a.ckpt}")
    torch.manual_seed(SEED)
    model = GPTLanguageModel(vocab, N_EMBD, BLOCK_SIZE, N_HEAD, N_LAYER, DROPOUT)
    model.load_state_dict(torch.load(a.ckpt, map_location=a.device))
    model = model.to(a.device).eval()

    cls_tok = "<LNA_NB>" if CLASS == "nb" else "<LNA_WB>"
    cls_id = stoi[cls_tok]

    # ---- the standard dhruva-s reached anchor -----------------------------
    env = Env(get(ANCHOR_TASK), budget=1, seed=1, logger=None)
    base_spec = env.spec
    anchor_nl, _ = T.topo_to_netlist(env.topo)
    anchor_seq = [str(t) for t in T.emit_sequence(anchor_nl)]
    if not anchor_seq:
        raise SystemExit("anchor topology did not emit a token sequence")
    anchor_seq_sha = _store_seq(anchor_seq)
    max_dev = base_spec.topology.get("device_budget", [3, 16])[1]
    min_dev = base_spec.topology.get("device_budget", [3, 16])[0]

    # ---- C2 dhruva-s bin prefix: the goal-target bins (design that MEETS every
    #      base limit -> all 'B'); this is the goal's own bin prefix per §5. -----
    if a.arm == "c2":
        # dhruva-s base spec: a target design MEETS every limit exactly => class B
        spec_prefix_toks = [f"<{m}_B>" for m in C.C2_METRICS]
        spec_prefix_ids = [stoi[t] for t in spec_prefix_toks]
    else:
        spec_prefix_ids = []

    def is_dev_tok(tk):
        return ("_" not in tk) and tk not in ("VSS", "VDD", "TRUNCATE")
    dev_positions = [i for i, tk in enumerate(anchor_seq) if is_dev_tok(tk)]
    cut_choices = [0] + dev_positions

    anchor_wl = None
    try:
        from novelty import wl_features
        anchor_wl = wl_features(env.topo)[0]
    except Exception:
        pass

    print(f"[smoke-{a.arm}] anchor={ANCHOR_TASK} wl={anchor_wl} "
          f"seq_len={len(anchor_seq)} vocab={vocab} "
          f"spec_prefix={spec_prefix_toks} class={cls_tok} "
          f"temp={TEMPERATURE} max_new={MAX_NEW_TOKENS}", flush=True)

    rng = __import__("random").Random(SEED)
    log_fh = open(EDITS_JSONL, "a", buffering=1)

    attempts = 0
    l0_pass = 0
    realize_pass = 0
    distinct_l0 = set()
    cut_hist = Counter()
    gate_counts = Counter()
    t0 = time.time()

    while len(distinct_l0) < TARGET_DISTINCT and attempts < MAX_ATTEMPTS:
        attempts += 1
        c = rng.choice(cut_choices)
        prefix_toks = anchor_seq[:c]
        prefix_ids = [cls_id] + spec_prefix_ids + [stoi[t] for t in prefix_toks]

        try:
            rows, _steps = GC.generate_batch(
                model, [prefix_ids], max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE, device=a.device)
        except Exception as e:
            gate_counts["sample_error"] += 1
            _log(log_fh, a.arm, anchor_wl, anchor_seq_sha, c, None, None,
                 "sample_error", detail=repr(e))
            continue

        ids = [int(x) for x in rows[0].tolist()]
        ids = [x for x in ids if x < VOCAB_SIZE]      # drop class + spec tokens
        circ_ids = ids[:ids.index(TRUNCATE_ID)] if TRUNCATE_ID in ids else ids
        regrown_toks = [GC.ITOS[i] for i in circ_ids]
        regrown_len = len(regrown_toks) - c
        regrown_sha = _store_seq(regrown_toks)

        l0_ok = False
        nl = None
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
            _log(log_fh, a.arm, anchor_wl, anchor_seq_sha, c, regrown_sha,
                 regrown_len, "L0")
            continue

        l0_pass += 1
        distinct_l0.add(regrown_sha)
        cut_hist[c] += 1

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
            gate = "L0"
            gate_counts["realize_fail"] += 1
        wl = r[2] if r is not None else None
        _log(log_fh, a.arm, anchor_wl, anchor_seq_sha, c, regrown_sha,
             regrown_len, gate, realized_wl=wl)

    log_fh.close()
    wall = time.time() - t0

    report = {
        "campaign": "e12-p2smoke", "arm": a.arm, "checkpoint": a.ckpt,
        "anchor_task": ANCHOR_TASK, "anchor_wl": anchor_wl,
        "spec_prefix": spec_prefix_toks, "vocab": vocab,
        "frozen_constants": {
            "class_token": cls_tok, "temperature": TEMPERATURE,
            "max_new_tokens": MAX_NEW_TOKENS, "seed": SEED,
            "cut_rule": "uniform over {0} U device-token positions",
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
        "gate_counts": dict(gate_counts),
        "ngspice_calls": ng["n"],
        "wall_s": round(wall, 1),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "ts": _now(),
    }
    rpath = os.path.join(C.OUT, f"smoke_{a.arm}_report.json")
    with open(rpath, "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    print(json.dumps(report, indent=1))
    if ng["n"] != 0:
        print(f"!! WARNING: ngspice_calls={ng['n']} (MUST be 0)", flush=True)
    return 0


def _log(fh, arm, anchor_wl, anchor_seq_sha, cut_depth, regrown_sha,
         regrown_len, gate, realized_wl=None, detail=None):
    rec = {"campaign": "e12-p2smoke", "goal": "smoke", "arm": arm, "seed": SEED,
           "anchor_wl": anchor_wl, "anchor_seq_sha": anchor_seq_sha,
           "cut_depth": cut_depth, "regrown_tokens_sha": regrown_sha,
           "regrown_len": regrown_len, "gate": gate, "realized_wl": realized_wl,
           "l1_objective": None, "stage2": None, "era": "e12-p2smoke",
           "ts": _now()}
    if detail:
        rec["detail"] = detail
    fh.write(json.dumps(rec, default=str) + "\n")


if __name__ == "__main__":
    sys.exit(main())
