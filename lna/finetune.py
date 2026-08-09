"""P1 (class-token) + P2 (plain) LNA fine-tune (WP-GEN, plans/04-GEN.md §2-3).

The prefix trick copies because the conditioning arrives *as content* (a seed the
model continues, and often recites). A fine-tune conditions on the *weights*
instead, and P1 adds an honest conditioning channel -- a `<LNA>` class token --
so we can sample LNAs from bare `<LNA> VSS` with no seed to copy.

  P1  extend the vocab with <LNA>/<OTHER> (ids appended AFTER the 1005 upstream
      tokens, so genie_common's base vocab and test_vocab_matches_upstream are
      untouched), mean-init the two new embedding/lm_head rows, fine-tune on the
      4,023 LNA augmentations as <LNA> + a ~22% replay of general-corpus rows as
      <OTHER>. Sample from <LNA> VSS.
  P2  same data/holdout, no vocab change; sample from bare VSS. The baseline the
      handover demands.

6 of 41 LNA circuits (all their augmentations) are held out for validation only.
Training pads rows to 128 tokens (block 1024 x batch 64 won't fit a 4 GB card for
*training*) and masks the loss after the terminating TRUNCATE so padding doesn't
drown the circuit tokens. lr 3e-5, batch 32.

    # WSL GPU:
    python lna/finetune.py --arm p1 --do train  --device cuda
    python lna/finetune.py --arm p1 --do sample --device cuda --seed 1337 --out lna/out/ft_p1_s1337
    python lna/finetune.py --arm p2 --do both   --device cuda
    # template-free control arm (FINDINGS §16): same recipe, zero archetypes
    python lna/finetune.py --arm p5 --do train --no-templates --tag ctrl
    # curriculum arm (FINDINGS §18): scaffolded phase 1, template-free phase 2
    python lna/finetune.py --arm p5 --do train --no-templates --winners --tag cur \
        --warm-from lna/out/ft_p5.pth --winners-file lna/out/winners_train.pre_dhruva.json
    # then, Windows: python lna/novelty.py --eval lna/out/ft_p1_s1337 --spec wifi24
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch
from torch.nn import functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from genie_common import (BLOCK_SIZE, DEVICES, DROPOUT, N_EMBD, N_HEAD,  # noqa: E402
                          N_LAYER, REPO, STOI, TRUNCATE_ID, VOCAB_SIZE,
                          VSS_ID, decode, generate_batch)
sys.path.insert(0, REPO)
from Models.GPT import GPTLanguageModel  # noqa: E402

LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))
# 6 held-out circuits (spread across both index blocks), validation only.
HOLDOUT = [464, 471, 478, 485, 1083, 1089]
# per-arm class tokens, appended AFTER the 1005 upstream ids (base vocab untouched)
CLASS_TOKENS = {"p1": ["<LNA>", "<OTHER>"],
                "p5": ["<LNA_NB>", "<LNA_WB>", "<OTHER>"]}
PAD_L = 128
IGNORE = -1
PRETRAIN = os.path.join(REPO, "Pretrain.pth")


def ext_vocab(arm):
    devs = DEVICES + CLASS_TOKENS.get(arm, [])
    stoi = {d: i for i, d in enumerate(devs)}
    return devs, stoi, len(devs)


# ------------------------------------------------------------------- data
def _rows_from_npy(path, cls_id):
    """token-name npy -> list of id lists [cls?, content..., TRUNCATE]."""
    arr = np.load(path, allow_pickle=True)
    out = []
    for row in arr:
        toks = [str(t) for t in row]
        if "TRUNCATE" in toks:
            toks = toks[:toks.index("TRUNCATE")]
        if not toks:
            continue
        ids = [STOI[t] for t in toks] + [TRUNCATE_ID]
        if cls_id is not None:
            ids = [cls_id] + ids
        out.append(ids)
    return out


def _rows_from_seqs(seqs, cls_id):
    """token-name sequences -> id lists [cls?, content..., TRUNCATE]."""
    out = []
    for toks in seqs:
        if "TRUNCATE" in toks:
            toks = toks[:toks.index("TRUNCATE")]
        if not toks:
            continue
        ids = [STOI[t] for t in toks] + [TRUNCATE_ID]
        if cls_id is not None:
            ids = [cls_id] + ids
        out.append(ids)
    return out


def _corpus_class(npy_path, nb_id, wb_id):
    """NB (inductor-bearing) vs WB (inductorless) from the circuit's own graph."""
    from topology import Topology
    toks = [str(t) for t in np.load(npy_path, allow_pickle=True)[0]]
    if "TRUNCATE" in toks:
        toks = toks[:toks.index("TRUNCATE")]
    return nb_id if Topology(toks).n_inductors >= 1 else wb_id


def build_dataset_p5(stoi, winners=False, templates=True, templates_file=None,
                     winners_file=None):
    """Corpus LNAs (tagged NB/WB by inductor) + Eulerian-augmented templates.py
    archetypes (tagged by class) + <OTHER> replay. This is the P5 lever: template
    diversity breaks the 35-graph memorization ceiling, and the class tokens make
    narrowband vs wideband a sampled channel (04-GEN §6). With `winners=True` the
    store's own feasible/near-feasible winners are mixed in -- Stage-3 Loop B
    expert iteration (templates.py --emit-winners -> out/winners_train.json).

    `templates=False` is the **template-free control arm** (FINDINGS §16): the
    identical recipe with zero archetype sequences, which measures how much of the
    generator's capability is the template scaffolding rather than the model. It
    also removes the archetype half of the validation set, so val is the 6 held-out
    corpus circuits alone -- stated because the best-val checkpoint policy then
    early-stops on a different (corpus-only) criterion.
    `templates_file` / `winners_file` pin *which* emission a run trained on; the
    archetype set has grown 92 -> 118 -> 135 -> 148, so reproducing a historical
    arm means naming its file, not just its flags."""
    nb, wb, oth = stoi["<LNA_NB>"], stoi["<LNA_WB>"], stoi["<OTHER>"]
    train, val = [], []
    for i in LNA_INDICES:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        rows = _rows_from_npy(p, _corpus_class(p, nb, wb))
        (val if i in HOLDOUT else train).extend(rows)
    n_corpus = len(train)
    # pre-generated augmented template rows (templates.py --emit-train), so the
    # GPU env needs no pandas; hold out every 8th archetype for val.
    n_arch, n_tmpl_tr = 0, 0
    if templates:
        tf = templates_file or os.path.join(HERE, "out", "templates_train.json")
        tdata = json.load(open(tf, encoding="utf-8"))
        n_arch = tdata["n_archetypes"]
        for r in tdata["rows"]:
            rows = _rows_from_seqs([r["seq"]], nb if r["cls"] == "nb" else wb)
            if r["arch"] % 8 == 0:            # hold out every 8th archetype
                val.extend(rows)
            else:
                train.extend(rows)
                n_tmpl_tr += len(rows)
    n_win = 0
    if winners:
        wf = winners_file or os.path.join(HERE, "out", "winners_train.json")
        for r in json.load(open(wf, encoding="utf-8"))["rows"]:
            train.extend(_rows_from_seqs([r["seq"]], nb if r["cls"] == "nb" else wb))
            n_win += 1
    gen = _rows_from_npy(os.path.join(REPO, "Training.npy"), oth)
    target = int(0.15 * len(train))
    replay = [gen[j % len(gen)] for j in range(target)] if gen else []
    train += replay
    print(f"[p5] train: {n_corpus} corpus + {n_tmpl_tr} template ({n_arch} arch"
          f"{'' if templates else ', TEMPLATE-FREE control arm'}) "
          f"+ {n_win} winner + {len(replay)} replay = {len(train)}; val: {len(val)}",
          flush=True)
    return _pad(train), _pad(val)


def build_dataset(arm, stoi, winners=False, **kw):
    if arm == "p5":
        return build_dataset_p5(stoi, winners=winners, **kw)
    lna_cls = stoi.get("<LNA>") if arm == "p1" else None
    oth_cls = stoi.get("<OTHER>") if arm == "p1" else None
    train, val = [], []
    for i in LNA_INDICES:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        rows = _rows_from_npy(p, lna_cls)
        (val if i in HOLDOUT else train).extend(rows)
    n_lna = len(train)
    # general-corpus replay (~22%), oversampled from Training.npy
    gen = _rows_from_npy(os.path.join(REPO, "Training.npy"), oth_cls)
    target = int(0.22 * n_lna)
    replay = [gen[k % len(gen)] for k in range(target)] if gen else []
    train += replay
    print(f"[{arm}] train rows: {n_lna} LNA + {len(replay)} replay = {len(train)}; "
          f"val (holdout {HOLDOUT}): {len(val)}")
    return _pad(train), _pad(val)


def _pad(rows):
    """-> (X [N,L-1], Y [N,L-1]) with Y=IGNORE after the terminating TRUNCATE."""
    n = len(rows)
    full = np.full((n, PAD_L), TRUNCATE_ID, dtype=np.int64)
    clen = np.empty(n, dtype=np.int64)
    for i, ids in enumerate(rows):
        ids = ids[:PAD_L]
        full[i, :len(ids)] = ids
        clen[i] = len(ids)                 # content+terminator length (<= L)
    X = full[:, :-1].copy()
    Y = full[:, 1:].copy()
    for i in range(n):
        Y[i, clen[i] - 1:] = IGNORE        # ignore predictions of padding
    return torch.from_numpy(X), torch.from_numpy(Y)


# -------------------------------------------------------- checkpoint surgery
def build_model(arm, vocab_size, device, warm=None):
    model = GPTLanguageModel(vocab_size, N_EMBD, BLOCK_SIZE, N_HEAD, N_LAYER, DROPOUT)
    if warm and os.path.exists(warm):                # Stage-3 expert iteration:
        model.load_state_dict(torch.load(warm, map_location=device))  # warm-start
        print(f"[{arm}] warm-started from {warm}", flush=True)
        return model.to(device)
    state = torch.load(PRETRAIN, map_location=device)
    if arm == "p2":
        model.load_state_dict(state, strict=False)
    else:
        # copy everything but the two vocab-sized tensors; mean-init new rows
        own = model.state_dict()
        for k, v in state.items():
            if k in own and own[k].shape == v.shape:
                own[k].copy_(v)
        tok = state["token_embedding_table.weight"]           # (1005, 384)
        model.token_embedding_table.weight.data[:VOCAB_SIZE] = tok
        model.token_embedding_table.weight.data[VOCAB_SIZE:] = tok.mean(0, keepdim=True)
        hw, hb = state["lm_head.weight"], state["lm_head.bias"]
        model.lm_head.weight.data[:VOCAB_SIZE] = hw
        model.lm_head.weight.data[VOCAB_SIZE:] = hw.mean(0, keepdim=True)
        model.lm_head.bias.data[:VOCAB_SIZE] = hb
        model.lm_head.bias.data[VOCAB_SIZE:] = hb.mean()
    return model.to(device)


# ------------------------------------------------------------------ train
def ckpt_path(arm, winners=False, tag=None):
    # expert-iteration writes a distinct version so the base checkpoint is kept
    # (revertability is a Stage-3 tripwire requirement, 04-SELF-IMPROVE §2).
    # `tag` renames ONLY the checkpoint file, never the architecture: a side arm
    # (e.g. the template-free control) must never overwrite a shared 198 MB
    # checkpoint other agents are sampling from.
    return os.path.join(HERE, "out", f"ft_{tag or arm}{'_v2' if winners else ''}.pth")


def train(arm, device, epochs=40, batch=32, lr=3e-5, seed=1337, winners=False,
          tag=None, warm_from=None, ckpt_policy="best", **kw):
    """`warm_from` pins the warm-start checkpoint explicitly, overriding the
    `ft_<tag>.pth` convention -- a **curriculum** phase warm-starts from another
    arm's shipped checkpoint (e.g. the scaffolded P5-v3) and must not have to copy
    a 198 MB file over a shared path to do it (FINDINGS §18).
    `ckpt_policy="final"` ships the last epoch instead of the best-val one, which
    is the only way to run a *fixed-length* curriculum tail in a program whose
    fine-tunes all take their best val at epoch 0-1; `"best"` (the default) is the
    unchanged §16/P5 policy."""
    torch.manual_seed(seed)
    _, stoi, vocab_size = ext_vocab(arm)
    (Xtr, Ytr), (Xva, Yva) = build_dataset(arm, stoi, winners=winners, **kw)
    base = ckpt_path(arm, tag=tag)
    warm = warm_from or (base if (winners and os.path.exists(base)) else None)
    if warm_from and not os.path.exists(warm_from):
        raise SystemExit(f"--warm-from: no such checkpoint: {warm_from}")
    model = build_model(arm, vocab_size, device, warm=warm)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    Xtr, Ytr, Xva, Yva = [t.to(device) for t in (Xtr, Ytr, Xva, Yva)]
    n = Xtr.size(0)

    def loss_on(X, Y):
        logits, _ = model(X)
        return F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                               Y.reshape(-1), ignore_index=IGNORE)

    @torch.no_grad()
    def val_loss():
        model.eval()
        losses = [loss_on(Xva[i:i + batch], Yva[i:i + batch]).item()
                  for i in range(0, Xva.size(0), batch)]
        model.train()
        return sum(losses) / max(len(losses), 1)

    out_ckpt = ckpt_path(arm, winners, tag=tag)
    os.makedirs(os.path.dirname(out_ckpt), exist_ok=True)
    best, best_ep = float("inf"), -1
    t0 = time.time()
    for ep in range(epochs):
        perm = torch.randperm(n, device=device)
        model.train()
        tot = 0.0
        for s in range(0, n, batch):
            ix = perm[s:s + batch]
            loss = loss_on(Xtr[ix], Ytr[ix])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            tot += loss.item()
        vl = val_loss()
        flag = ""
        if vl < best:
            best = vl
            best_ep = ep
            if ckpt_policy == "best":
                torch.save(model.state_dict(), out_ckpt)
                flag = "  <- saved"
        if ckpt_policy == "final" and ep == epochs - 1:
            torch.save(model.state_dict(), out_ckpt)
            flag += "  <- saved (final)"
        print(f"[{arm}] epoch {ep:3d}  train {tot/(n//batch+1):.4f}  "
              f"val {vl:.4f}{flag}", flush=True)
    print(f"[{arm}] done in {time.time()-t0:.0f}s; best val {best:.4f} "
          f"@ epoch {best_ep}; policy={ckpt_policy} -> {out_ckpt}")


# ------------------------------------------------------------------ sample
def load_ft(arm, device, winners=False, tag=None):
    _, _, vocab_size = ext_vocab(arm)
    model = GPTLanguageModel(vocab_size, N_EMBD, BLOCK_SIZE, N_HEAD, N_LAYER, DROPOUT)
    model.load_state_dict(torch.load(ckpt_path(arm, winners, tag=tag),
                                     map_location=device))
    return model.to(device).eval()


def sample(arm, device, n=256, batch=32, max_tokens=256, temperature=0.7,
           seed=1337, out=None, inductor_bias=0.0, cls="nb", winners=False,
           tag=None):
    torch.manual_seed(seed)
    devs, stoi, _ = ext_vocab(arm)
    itos = {i: d for i, d in enumerate(devs)}
    model = load_ft(arm, device, winners=winners, tag=tag)
    if arm == "p1":
        prefix = [stoi["<LNA>"], VSS_ID]
    elif arm == "p5":
        prefix = [stoi["<LNA_NB>" if cls == "nb" else "<LNA_WB>"], VSS_ID]
    else:
        prefix = [VSS_ID]
    otag = f"{tag or arm}{'v2' if winners else ''}"
    out = out or os.path.join(HERE, "out", f"ft_{otag}_{cls}_s{seed}"
                              if arm == "p5" else f"ft_{otag}_s{seed}")
    os.makedirs(out, exist_ok=True)
    if inductor_bias:
        from decode import generate_inductor_biased

    meta, produced = [], 0
    t0 = time.time()
    for start in range(0, n, batch):
        b = min(batch, n - start)
        if inductor_bias:
            rows, steps = generate_inductor_biased(
                model, [list(prefix)] * b, lambda_L=inductor_bias,
                max_new_tokens=max_tokens, temperature=temperature, device=device)
        else:
            rows, steps = generate_batch(model, [list(prefix)] * b,
                                         max_new_tokens=max_tokens,
                                         temperature=temperature, device=device)
        for row in rows:
            ids = [int(x) for x in row.tolist()]
            ids = [x for x in ids if x < VOCAB_SIZE]      # drop class token(s)
            circ = ids[:ids.index(TRUNCATE_ID)] if TRUNCATE_ID in ids else ids
            path = os.path.join(out, f"seq{produced:04d}.txt")
            open(path, "w").write(decode(circ))
            meta.append({"file": os.path.basename(path),
                         "terminated": TRUNCATE_ID in ids,
                         "circuit_tokens": len(circ)})
            produced += 1
        print(f"  [{produced}/{n}] {steps} steps", flush=True)
    json.dump({"arm": arm, "prefix": prefix, "seed": seed, "meta": meta},
              open(os.path.join(out, "meta.json"), "w"), indent=2)
    term = sum(m["terminated"] for m in meta)
    print(f"[{arm}] sampled {produced} -> {out} in {time.time()-t0:.0f}s; "
          f"terminated {term}/{produced}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["p1", "p2", "p5"], required=True)
    ap.add_argument("--do", choices=["train", "sample", "both"], default="both")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--out", default=None)
    ap.add_argument("--class", dest="cls", choices=["nb", "wb"], default="nb",
                    help="p5 sampling class token (<LNA_NB> / <LNA_WB>)")
    ap.add_argument("--winners", action="store_true",
                    help="p5 Stage-3 expert iteration: mix store winners, warm-start "
                         "from ft_p5.pth, write ft_p5_v2.pth (04-SELF-IMPROVE §2)")
    ap.add_argument("--inductor-bias", type=float, default=0.0,
                    help="P4: add this logit bias to unused L-device tokens while "
                         "the running inductor ratio is below target")
    ap.add_argument("--no-templates", action="store_true",
                    help="p5 TEMPLATE-FREE control arm: train on corpus (+winners) "
                         "only, zero templates.py archetype sequences (FINDINGS §16)")
    ap.add_argument("--templates-file", default=None,
                    help="pin which templates.py emission to train on "
                         "(default out/templates_train.json)")
    ap.add_argument("--winners-file", default=None,
                    help="pin which emit-winners emission to train on "
                         "(default out/winners_train.json)")
    ap.add_argument("--tag", default=None,
                    help="rename the checkpoint/out-dir stem (ft_<tag>[_v2].pth) so "
                         "a side arm never overwrites a shared checkpoint")
    ap.add_argument("--warm-from", default=None,
                    help="explicit warm-start checkpoint, overriding the "
                         "ft_<tag>.pth convention (curriculum phase 2, FINDINGS §18)")
    ap.add_argument("--ckpt-policy", choices=["best", "final"], default="best",
                    help="ship the best-val epoch (default, = P5/§16 policy) or the "
                         "final epoch (fixed-length curriculum tail)")
    args = ap.parse_args()
    dkw = {}
    if args.arm == "p5":
        dkw = {"templates": not args.no_templates,
               "templates_file": args.templates_file,
               "winners_file": args.winners_file}

    if args.do in ("train", "both"):
        train(args.arm, args.device, epochs=args.epochs, seed=args.seed,
              winners=args.winners, tag=args.tag, warm_from=args.warm_from,
              ckpt_policy=args.ckpt_policy, **dkw)
    if args.do in ("sample", "both"):
        sample(args.arm, args.device, n=args.n, seed=args.seed, out=args.out,
               inductor_bias=args.inductor_bias, cls=args.cls,
               winners=args.winners, tag=args.tag)


if __name__ == "__main__":
    main()
