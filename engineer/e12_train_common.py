"""E-12 P2 shared training helpers (trained editors C1 / C2).

Adapts lna/finetune.py's warm-start + weighted-CE training loop for the two
engineer-owned editor checkpoints. ZERO ngspice; CPU-only; PYTHONHASHSEED=0;
fixed torch seed. Writes ONLY under engineer/out_editor/. Never writes lna/.

The v7 checkpoint (lna/out/ft_p5v7_v2.pth) is a READ-ONLY warm-start input,
loaded through lna.finetune's own vocab-extension surgery (_load_warm).
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENG = HERE
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (ENG, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.nn import functional as F  # noqa: E402

import finetune as FT  # noqa: E402
from genie_common import STOI, TRUNCATE_ID, VOCAB_SIZE  # noqa: E402
from Models.GPT import GPTLanguageModel  # noqa: E402
from genie_common import N_EMBD, N_HEAD, N_LAYER, BLOCK_SIZE, DROPOUT  # noqa: E402

V7_CKPT = "/home/dpatni/circuit-repro/lna/out/ft_p5v7_v2.pth"
EDIT_LOG = os.path.join(HERE, "data", "e11_edit_log", "edits.jsonl")
SEQ_DIR = os.path.join(HERE, "data", "e11_edit_log", "seqs")
STORE = os.path.join(LNA, "data", "topo_labels.jsonl")
EXCL = os.path.join(HERE, "data", "e12", "excluded_rows.json")
OUT = os.path.join(HERE, "out_editor")

PAD_L = 128            # same as finetune.py
IGNORE = -1
SEED = 1337

# ---- fixed public C2 binning tokens: 4 metrics x 4 coarse classes -----------
# class letters: A strong-pass, B pass, C near-miss, D fail (sense-aware,
# derived from the dhruva-s BASE spec limits below; NO per-goal tuning).
C2_METRICS = ["NF", "GAIN", "MATCH", "IDD"]
C2_CLASSES = ["A", "B", "C", "D"]
C2_TOKENS = [f"<{m}_{c}>" for m in C2_METRICS for c in C2_CLASSES]

# dhruva-s BASE spec limits (env.Spec.constraints for dhruva-s-t2-a; the store's
# own base task). (metric_key, sense, limit)
BASE_LIMITS = {
    "NF": ("nf_db", "max", 3.5),
    "GAIN": ("s21_db", "min", 30.0),
    "MATCH": ("s11_max_db", "max", -10.0),
    "IDD": ("idd_ma", "max", 13.0),
}


def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_exclusions():
    d = json.load(open(EXCL))
    banned_log = set(d["l1_ban"]["edit_log_rows"]["line_numbers"])
    banned_wl = set(d["l1_ban"]["store_rows"]["wl_hashes"])
    excl_wl_goal, excl_log_goal, excl_seq = set(), set(), set()
    for g, gd in d["goals"].items():
        excl_wl_goal.update(gd["store_rows_excluded"]["wl_hashes"])
        excl_log_goal.update(gd["edit_log_rows_excluded"]["line_numbers"])
        excl_seq.update(gd["edit_log_rows_excluded"]["seq_shas"])
    return {
        "banned_log": banned_log, "banned_wl": banned_wl,
        "excl_wl_goal": excl_wl_goal, "excl_log_goal": excl_log_goal,
        "excl_seq": excl_seq,
    }


def read_seq(sha):
    """Load a content-addressed token sequence -> list[str] (no TRUNCATE)."""
    p = os.path.join(SEQ_DIR, f"{sha}.txt")
    if not os.path.exists(p):
        return None
    raw = open(p).read().strip()
    toks = [t for t in raw.split("->") if t]
    if toks and toks[-1] == "TRUNCATE":
        toks = toks[:-1]
    return toks


def c2_bin(name, val):
    """Sense-aware coarse class of an achieved metric vs the dhruva-s base limit.
    Fixed public rule (no per-goal tuning):
      sense 'max' (nf/match/idd -- lower is better):
        A: val <= limit - 0.5*|limit|   (>=50% margin band inside the limit)
        B: val <= limit                 (meets)
        C: val <= limit + |limit|       (near-miss, within one limit-width)
        D: otherwise                    (fail)
      sense 'min' (gain -- higher is better): mirror image.
    |limit| uses a floor of 1.0 when the limit is 0 to keep the band finite.
    Returns the class letter, or None if val is missing.
    """
    key, sense, lim = BASE_LIMITS[name]
    if val is None or not isinstance(val, (int, float)):
        return None
    span = abs(lim) if abs(lim) > 1e-9 else 1.0
    if sense == "max":
        if val <= lim - 0.5 * span:
            return "A"
        if val <= lim:
            return "B"
        if val <= lim + span:
            return "C"
        return "D"
    else:  # min
        if val >= lim + 0.5 * span:
            return "A"
        if val >= lim:
            return "B"
        if val >= lim - span:
            return "C"
        return "D"


def c2_prefix_tokens(metrics):
    """Ordered 4 spec tokens (NF,GAIN,MATCH,IDD) for a metrics dict; a metric with
    no class is dropped (kept order stable)."""
    out = []
    for m in C2_METRICS:
        key = BASE_LIMITS[m][0]
        cls = c2_bin(m, metrics.get(key))
        if cls is not None:
            out.append(f"<{m}_{cls}>")
    return out


def ext_vocab_c2():
    """p5 vocab (1008) + the 16 C2 spec tokens, appended AFTER the class tokens so
    the v7 checkpoint (1008 wide) loads via finetune._load_warm mean-init."""
    devs, stoi, _ = FT.ext_vocab("p5")
    devs = list(devs) + C2_TOKENS
    stoi = {d: i for i, d in enumerate(devs)}
    return devs, stoi, len(devs)


def pad_rows(rows):
    """rows: list of id lists. -> (X,Y) tensors, Y=IGNORE after terminator.
    Byte-identical shape convention to finetune._pad."""
    n = len(rows)
    full = np.full((n, PAD_L), TRUNCATE_ID, dtype=np.int64)
    clen = np.empty(n, dtype=np.int64)
    for i, ids in enumerate(rows):
        ids = ids[:PAD_L]
        full[i, :len(ids)] = ids
        clen[i] = len(ids)
    X = full[:, :-1].copy()
    Y = full[:, 1:].copy()
    for i in range(n):
        Y[i, clen[i] - 1:] = IGNORE
    return torch.from_numpy(X), torch.from_numpy(Y)


def build_model(vocab_size, device):
    """Warm-start a GPT of `vocab_size` from the v7 checkpoint (READ-ONLY),
    extending the vocab by mean-init exactly as finetune._load_warm does."""
    model = GPTLanguageModel(vocab_size, N_EMBD, BLOCK_SIZE, N_HEAD, N_LAYER, DROPOUT)
    state = torch.load(V7_CKPT, map_location=device)
    n_add = FT._load_warm(model, state)
    print(f"[warm] loaded v7 ({V7_CKPT}) -> vocab {vocab_size}"
          + (f" (+{n_add} mean-init rows)" if n_add else " (exact)"), flush=True)
    return model.to(device)


def train_weighted(model, Xtr, Ytr, Wtr, Xva, Yva, device, epochs, lr, batch,
                   tag, out_ckpt, patience=1):
    """Per-row-weighted cross-entropy fine-tune with best-val checkpointing and
    early-stop on rising val loss (P5-v8 epoch-1 lesson). Wtr is a per-row scalar
    weight; loss is the weight-averaged token CE over the batch. Returns a
    per-epoch history list of (train, val)."""
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    Xtr, Ytr, Xva, Yva = [t.to(device) for t in (Xtr, Ytr, Xva, Yva)]
    Wtr = Wtr.to(device)
    n = Xtr.size(0)

    def wloss(X, Y, W):
        logits, _ = model(X)
        # token CE without reduction, then per-row mean over non-ignored, then
        # weight-average across rows.
        tok = F.cross_entropy(
            logits.reshape(-1, logits.size(-1)), Y.reshape(-1),
            ignore_index=IGNORE, reduction="none").view(Y.shape)
        mask = (Y != IGNORE).float()
        row_ce = (tok * mask).sum(1) / mask.sum(1).clamp(min=1.0)
        return (row_ce * W).sum() / W.sum().clamp(min=1e-8)

    @torch.no_grad()
    def val_loss():
        model.eval()
        ls = []
        for i in range(0, Xva.size(0), batch):
            logits, _ = model(Xva[i:i + batch])
            Y = Yva[i:i + batch]
            l = F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                                Y.reshape(-1), ignore_index=IGNORE)
            ls.append(l.item())
        model.train()
        return sum(ls) / max(len(ls), 1)

    torch.manual_seed(SEED)
    hist = []
    best, best_ep = float("inf"), -1
    rising = 0
    t0 = time.time()
    for ep in range(epochs):
        perm = torch.randperm(n, device=device)
        model.train()
        tot = 0.0
        nb = 0
        for s in range(0, n, batch):
            ix = perm[s:s + batch]
            loss = wloss(Xtr[ix], Ytr[ix], Wtr[ix])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            tot += loss.item()
            nb += 1
        vl = val_loss()
        tl = tot / max(nb, 1)
        hist.append((tl, vl))
        flag = ""
        if vl < best - 1e-6:
            best, best_ep = vl, ep
            rising = 0
            torch.save(model.state_dict(), out_ckpt)
            flag = "  <- saved (best-val)"
        else:
            rising += 1
        print(f"[{tag}] epoch {ep:2d}  train {tl:.4f}  val {vl:.4f}{flag}",
              flush=True)
        if rising >= patience and ep >= best_ep + patience:
            print(f"[{tag}] early-stop: val rose {rising} epoch(s) past best "
                  f"(best {best:.4f} @ ep {best_ep})", flush=True)
            break
    print(f"[{tag}] done in {time.time()-t0:.0f}s; best val {best:.4f} @ ep "
          f"{best_ep} -> {out_ckpt}", flush=True)
    return hist, best, best_ep
