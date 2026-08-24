"""E-12 P2 -- C2: spec-conditioned regrowth.

Fine-tunes an editor from v7 on store-label sequences with a coarse spec-token
PREFIX prepended, so the generator learns to regrow circuits conditioned on the
target spec class. Each training row is:

    [ <CLASS> , <NF_x> <GAIN_x> <MATCH_x> <IDD_x> , graph.tokens... , TRUNCATE ]

The 4 spec tokens are the row's own achieved-metric bins (fixed public binning of
NF / gain / match / current classes derived from the dhruva-s BASE spec limits;
see e12_train_common.c2_bin -- no per-goal tuning). At proposal time the
evaluation goal's own bin prefix is used (the C2 smoke uses the dhruva-s bin
prefix).

VOCAB EXTENSION: p5 vocab (1008) is extended with 16 new spec tokens
(4 metrics x {A,B,C,D}) appended AFTER the class tokens. The v7 checkpoint loads
via finetune._load_warm, which mean-initializes the 16 new embedding/head rows;
the upstream 1005 ids and the 3 p5 class ids are untouched.

Loss: standard (unweighted) cross-entropy over graph tokens; the spec-prefix
tokens are masked to IGNORE (they are conditioning, not prediction targets).

ANTI-MEMORIZATION: store rows excluded per engineer/data/e12/excluded_rows.json
(dhruva-l1 ban + per-goal answer exclusion, all by wl_hash) NEVER enter training.

ZERO ngspice. CPU. PYTHONHASHSEED=0. Fixed seed. Writes only engineer/out_editor/.

    python e12_train_c2.py [--dry-run] [--epochs N --lr X]
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

CLASS_TOKEN = "<LNA_NB>"     # store base task dhruva-s is narrowband
BATCH = 32
DEFAULT_EPOCHS = 8
DEFAULT_LR = 3e-5


def gather_rows():
    ex = C.load_exclusions()
    banned_wl = ex["banned_wl"]
    excl_wl_goal = ex["excl_wl_goal"]
    all_excl = banned_wl | excl_wl_goal

    kept = []
    exc = {"l1": 0, "goal": 0, "no_tokens": 0}
    total = 0
    with open(C.STORE) as fh:
        for l in fh:
            try:
                r = json.loads(l)
            except Exception:
                continue
            total += 1
            wl = r.get("wl_hash")
            if wl in banned_wl:
                exc["l1"] += 1
                continue
            if wl in excl_wl_goal:
                exc["goal"] += 1
                continue
            toks = (r.get("graph") or {}).get("tokens")
            if not toks:
                exc["no_tokens"] += 1
                continue
            kept.append(r)
    return kept, exc, total, len(all_excl)


def to_row(rec, stoi):
    """[cls, spec-prefix(4), graph tokens, TRUNCATE], n_prefix = spec tokens."""
    toks = [str(t) for t in rec["graph"]["tokens"]]
    if "TRUNCATE" in toks:
        toks = toks[:toks.index("TRUNCATE")]
    if not toks:
        return None
    prefix = C.c2_prefix_tokens(rec.get("metrics", {}))
    try:
        ids = ([stoi[CLASS_TOKEN]] + [stoi[t] for t in prefix]
               + [stoi[t] for t in toks] + [C.TRUNCATE_ID])
    except KeyError:
        return None
    return ids, len(prefix)


def build_dataset(recs, stoi):
    rows, masks = [], []
    for r in recs:
        built = to_row(r, stoi)
        if built is None:
            continue
        ids, npfx = built
        rows.append(ids)
        masks.append(npfx)
    X, Y = C.pad_rows(rows)
    Y = Y.clone()
    for i, npfx in enumerate(masks):
        # mask Y positions predicting the class(0)+spec-prefix tokens:
        # targets at absolute idx 1..npfx -> Y idx 0..npfx-1.
        if npfx > 0:
            Y[i, :npfx] = C.IGNORE
    W = torch.ones(X.size(0), dtype=torch.float32)  # unweighted CE
    return X, Y, W, len(rows)


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

    devs, stoi, vocab = C.ext_vocab_c2()   # 1008 + 16 spec tokens = 1024
    kept, exc, total, n_excl_topos = gather_rows()
    print(f"[c2] store rows={total}  kept={len(kept)}  "
          f"excl l1={exc['l1']} goal={exc['goal']} no_tokens={exc['no_tokens']}",
          flush=True)

    rng = random.Random(C.SEED)
    rng.shuffle(kept)
    k = max(1, int(len(kept) * 0.1))
    va_recs, tr_recs = kept[:k], kept[k:]

    Xtr, Ytr, Wtr, ntr = build_dataset(tr_recs, stoi)
    Xva, Yva, Wva, nva = build_dataset(va_recs, stoi)
    print(f"[c2] vocab={vocab}  train rows={ntr}  val rows={nva}", flush=True)

    tag = "c2"
    out_ckpt = os.path.join(C.OUT, "editor_c2.pth")
    epochs = 1 if a.dry_run else a.epochs
    model = C.build_model(vocab, a.device)
    hist, best, best_ep = C.train_weighted(
        model, Xtr, Ytr, Wtr, Xva, Yva, a.device, epochs, a.lr, BATCH,
        tag + ("-dry" if a.dry_run else ""), out_ckpt, patience=1)

    # example bin prefixes for documentation: the goal-target prefix uses the
    # base-spec limit itself (a design that exactly MEETS every limit => all-B).
    manifest = {
        "checkpoint": "C2", "kind": "spec-conditioned regrowth",
        "dry_run": a.dry_run, "out_ckpt": out_ckpt if not a.dry_run else None,
        "warm_from": C.V7_CKPT, "warm_from_sha1": C.file_sha(C.V7_CKPT),
        "vocab_size": vocab, "class_token": CLASS_TOKEN,
        "vocab_extension": {
            "base_p5_vocab": 1008, "new_spec_tokens": C.C2_TOKENS,
            "how": ("appended AFTER the 3 p5 class tokens; v7 checkpoint loaded "
                    "via finetune._load_warm which mean-initializes the 16 new "
                    "embedding + lm_head rows; upstream 1005 + p5 class ids "
                    "untouched"),
        },
        "store": C.STORE, "store_sha1": C.file_sha(C.STORE),
        "store_rows_total": total,
        "binning_rule": {
            "metrics": {m: {"key": C.BASE_LIMITS[m][0],
                            "sense": C.BASE_LIMITS[m][1],
                            "base_limit": C.BASE_LIMITS[m][2]}
                        for m in C.C2_METRICS},
            "classes": "A strong-pass / B pass / C near-miss / D fail",
            "rule": ("sense=max: A val<=lim-0.5|lim|; B val<=lim; C val<=lim+|lim|; "
                     "D else. sense=min: mirror. |lim| floored at 1.0 when lim==0. "
                     "Derived from dhruva-s BASE spec limits; NO per-goal tuning."),
            "prefix_order": C.C2_METRICS,
            "proposal_time": ("evaluation goal's own bin prefix; the C2 smoke uses "
                              "the dhruva-s bin prefix"),
        },
        "loss": ("unweighted cross-entropy over graph tokens; class + spec-prefix "
                 "tokens masked to IGNORE (conditioning, not targets)"),
        "counts": {"kept": len(kept), "train_rows": ntr, "val_rows": nva},
        "exclusions_applied": {
            "store_rows_excl_l1": exc["l1"], "store_rows_excl_goal": exc["goal"],
            "store_rows_no_tokens": exc["no_tokens"],
            "excluded_topologies_union": n_excl_topos,
        },
        "hyperparams": {"epochs_requested": epochs, "lr": a.lr, "batch": BATCH,
                        "seed": C.SEED, "early_stop": "val rose >=1 epoch past best",
                        "ckpt_policy": "best-val"},
        "history_train_val": hist, "best_val": best, "best_epoch": best_ep,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "ngspice_calls": 0, "ts": C.now(),
    }
    mpath = os.path.join(C.OUT, "manifest_c2_dry.json" if a.dry_run
                         else "manifest_c2.json")
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    print(f"[c2] manifest -> {mpath}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
