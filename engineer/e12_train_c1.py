"""E-12 P2 -- C1: contrastive edit priors.

Trains an editor from v7 on (anchor-prefix -> regrown-suffix) sequence pairs
drawn from the edit log. Each training row is:

    [ <CLASS> , anchor_seq[:cut_depth] (KEPT prefix) , regrown_tokens... , TRUNCATE ]

The loss is per-row-weighted cross-entropy (weighted CE): positives up-weighted,
negatives down-weighted. Predictions over the KEPT prefix are masked to IGNORE so
the model is trained only to REGROW the suffix given the anchor prefix -- exactly
the (anchor-prefix -> regrown-suffix) contrastive objective.

POSITIVES  (weight W_POS):
  * the 9 e12-p1b solving edits (gate=='survivor' and stage2.feasible), AND
  * survivors whose stage-2 IMPROVED the L1 objective
    (stage2.best_objective < l1_objective).
NEGATIVES  (weight W_NEG):
  * sampled L0/realize failures (gate=='L0': furthest gate reached was L0, i.e.
    the candidate failed realize() or failed L0 sanity).

Arm-B primitive edits: the edit log stores every arm-B/arm-C proposal uniformly
as (anchor_seq_sha, cut_depth, regrown_tokens_sha) -- i.e. arm-B primitive edits
ARE already representable as the same sequence pairs (an arm-B move regrows a
suffix too). We therefore INCLUDE arm-B positive survivors on identical footing;
there is no separate primitive-edit encoding. Documented in the manifest.

ANTI-MEMORIZATION: rows excluded per engineer/data/e12/excluded_rows.json
(l1 ban by line + realized_wl; per-goal answer exclusion by line, realized_wl,
and seq sha) NEVER enter training. Counts written to the manifest.

ZERO ngspice. CPU. PYTHONHASHSEED=0. Fixed seed. Writes only engineer/out_editor/.

    python e12_train_c1.py [--dry-run] [--epochs N --lr X --wpos P --wneg Q]
"""
import argparse
import json
import os
import random
import sys

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import torch  # noqa: E402
import e12_train_common as C  # noqa: E402

# frozen sampling / conditioning constants (match e11_smoke / main-line p5)
CLASS_TOKEN = "<LNA_NB>"     # dhruva-s family is narrowband; edit log anchors are dhruva-class
NEG_PER_POS = 3             # negatives : positives ratio in the training mix
W_POS = 3.0                # up-weight positives
W_NEG = 0.3                # down-weight negatives
BATCH = 32
DEFAULT_EPOCHS = 8
DEFAULT_LR = 3e-5           # main-line finetune lr


def gather_rows():
    ex = C.load_exclusions()
    banned_log = ex["banned_log"]
    all_wl_ban = ex["banned_wl"] | ex["excl_wl_goal"]
    all_log_ban = ex["banned_log"] | ex["excl_log_goal"]
    excl_seq = ex["excl_seq"]

    lines = open(C.EDIT_LOG).read().splitlines()
    pos_solve, pos_impr, negs = [], [], []
    exc = {"line": 0, "wl": 0, "seq": 0}
    for i, l in enumerate(lines, 1):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if i in all_log_ban:
            exc["line"] += 1
            continue
        rw = r.get("realized_wl")
        if rw and rw in all_wl_ban:
            exc["wl"] += 1
            continue
        if r.get("regrown_tokens_sha") in excl_seq:
            exc["seq"] += 1
            continue
        g = r.get("gate")
        s2 = r.get("stage2")
        if g == "survivor" and s2 and s2.get("feasible"):
            pos_solve.append((i, r))
        elif (g == "survivor" and s2 and s2.get("best_objective") is not None
              and r.get("l1_objective") is not None
              and s2["best_objective"] < r["l1_objective"]):
            pos_impr.append((i, r))
        elif g == "L0":
            negs.append((i, r))
    return pos_solve, pos_impr, negs, exc, len(lines)


def to_row(rec, stoi):
    """Build the id list [cls, kept-prefix, regrown..., TRUNCATE] and the number
    of KEPT-prefix tokens (to mask). Returns (ids, n_prefix) or None."""
    regrown = C.read_seq(rec.get("regrown_tokens_sha"))
    if not regrown:
        return None
    anchor = C.read_seq(rec.get("anchor_seq_sha")) or []
    c = int(rec.get("cut_depth") or 0)
    prefix = anchor[:c]
    # the regrown sequence already begins with the kept prefix (suffix regrowth);
    # to define the (prefix -> suffix) supervision we mask the first n_prefix
    # regrown tokens. Guard: only mask up to len(regrown).
    n_prefix = min(len(prefix), len(regrown))
    toks = regrown
    try:
        ids = [stoi[CLASS_TOKEN]] + [stoi[t] for t in toks] + [C.TRUNCATE_ID]
    except KeyError:
        return None
    return ids, n_prefix


def build_dataset(pos, neg, stoi, seed):
    rng = random.Random(seed)
    rows, weights, masks = [], [], []

    def add(recs, w):
        n = 0
        for _, r in recs:
            built = to_row(r, stoi)
            if built is None:
                continue
            ids, n_prefix = built
            rows.append(ids)
            weights.append(w)
            masks.append(n_prefix)
            n += 1
        return n

    n_pos = add(pos, W_POS)
    # sample negatives to NEG_PER_POS * (#positive rows actually built)
    n_neg_target = max(1, NEG_PER_POS * n_pos)
    neg_sample = neg if len(neg) <= n_neg_target else rng.sample(neg, n_neg_target)
    n_neg = add(neg_sample, W_NEG)

    # build padded tensors, then apply prefix masks (IGNORE over kept prefix in Y)
    X, Y = C.pad_rows(rows)
    Y = Y.clone()
    for i, npfx in enumerate(masks):
        # Y[i,j] predicts rows[i][j+1]; the class token is index 0, kept prefix
        # occupies indices 1..npfx. Mask Y positions that PREDICT a prefix token
        # (targets at absolute indices 1..npfx) -> Y indices 0..npfx-1.
        if npfx > 0:
            Y[i, :npfx] = C.IGNORE
    W = torch.tensor(weights, dtype=torch.float32)
    return X, Y, W, n_pos, n_neg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    ap.add_argument("--lr", type=float, default=DEFAULT_LR)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()

    torch.manual_seed(C.SEED)
    random.seed(C.SEED)
    os.makedirs(C.OUT, exist_ok=True)

    # C1 needs no new tokens: plain p5 vocab (1008), same width as the v7 ckpt.
    import finetune as _FT
    devs, stoi, vocab = _FT.ext_vocab("p5")
    stoi = {d: i for i, d in enumerate(devs)}

    pos_solve, pos_impr, negs, exc, n_log = gather_rows()
    pos = pos_solve + pos_impr
    print(f"[c1] log rows={n_log}  positives: solves={len(pos_solve)} "
          f"improved={len(pos_impr)}  negatives(pool)={len(negs)}", flush=True)
    print(f"[c1] exclusions: by_line={exc['line']} by_wl={exc['wl']} "
          f"by_seq={exc['seq']}", flush=True)

    # 90/10 split for train/val, stratified by class, deterministic
    rng = random.Random(C.SEED)
    def split(recs):
        recs = list(recs)
        rng.shuffle(recs)
        k = max(1, int(len(recs) * 0.1)) if len(recs) >= 10 else 0
        return recs[k:], recs[:k]
    pos_tr, pos_va = split(pos)
    neg_tr, neg_va = split(negs)

    Xtr, Ytr, Wtr, ntr_pos, ntr_neg = build_dataset(pos_tr, neg_tr, stoi, C.SEED)
    Xva, Yva, Wva, nva_pos, nva_neg = build_dataset(pos_va, neg_va, stoi, C.SEED + 1)
    print(f"[c1] train rows={Xtr.size(0)} (pos {ntr_pos}/neg {ntr_neg})  "
          f"val rows={Xva.size(0)} (pos {nva_pos}/neg {nva_neg})", flush=True)

    tag = "c1"
    out_ckpt = os.path.join(C.OUT, "editor_c1.pth")

    epochs = 1 if a.dry_run else a.epochs
    model = C.build_model(vocab, a.device)
    hist, best, best_ep = C.train_weighted(
        model, Xtr, Ytr, Wtr, Xva, Yva, a.device, epochs, a.lr, BATCH,
        tag + ("-dry" if a.dry_run else ""), out_ckpt, patience=1)

    manifest = {
        "checkpoint": "C1", "kind": "contrastive edit priors",
        "dry_run": a.dry_run, "out_ckpt": out_ckpt if not a.dry_run else None,
        "warm_from": C.V7_CKPT, "warm_from_sha1": C.file_sha(C.V7_CKPT),
        "vocab_size": vocab, "class_token": CLASS_TOKEN,
        "edit_log": C.EDIT_LOG, "edit_log_sha1": C.file_sha(C.EDIT_LOG),
        "edit_log_rows_total": n_log,
        "positive_def": ("gate==survivor & stage2.feasible (9 e12-p1b solves) "
                         "OR gate==survivor & stage2.best_objective < l1_objective"),
        "negative_def": "gate==L0 (L0/realize failures), sampled",
        "armB_primitive_edits": ("included as positives -- arm-B moves are stored "
                                 "as the same (anchor_seq_sha,cut_depth,"
                                 "regrown_tokens_sha) sequence pairs, no separate "
                                 "primitive encoding needed"),
        "loss": ("per-row weighted cross-entropy; row loss = mean token CE over "
                 "non-prefix tokens; batch loss = sum(w_i*row_ce_i)/sum(w_i). "
                 "Prefix (kept anchor) tokens masked to IGNORE => train only the "
                 "regrown suffix given the anchor prefix."),
        "weights": {"W_POS": W_POS, "W_NEG": W_NEG, "neg_per_pos": NEG_PER_POS},
        "counts": {
            "positives_total": len(pos), "solves": len(pos_solve),
            "improved_survivors": len(pos_impr),
            "negatives_pool": len(negs),
            "train_rows": int(Xtr.size(0)), "train_pos": ntr_pos, "train_neg": ntr_neg,
            "val_rows": int(Xva.size(0)), "val_pos": nva_pos, "val_neg": nva_neg,
        },
        "exclusions_applied": {
            "by_line": exc["line"], "by_realized_wl": exc["wl"], "by_seq_sha": exc["seq"],
            "l1_ban_log_lines": len(C.load_exclusions()["banned_log"]),
            "l1_ban_store_topos": len(C.load_exclusions()["banned_wl"]),
        },
        "hyperparams": {"epochs_requested": epochs, "lr": a.lr, "batch": BATCH,
                        "seed": C.SEED, "early_stop": "val rose >=1 epoch past best",
                        "ckpt_policy": "best-val"},
        "history_train_val": hist, "best_val": best, "best_epoch": best_ep,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "ngspice_calls": 0, "ts": C.now(),
    }
    mpath = os.path.join(C.OUT, "manifest_c1_dry.json" if a.dry_run
                         else "manifest_c1.json")
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    print(f"[c1] manifest -> {mpath}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
