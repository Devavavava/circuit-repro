"""Shared AnalogGenie plumbing: vocabulary, model loading, batched sampling.

Upstream's Inference.py rebuilds the vocabulary inline and samples one sequence
at a time for a fixed 1024 steps with no early stop. That is very slow: the model
has no KV cache, so step t re-attends over the whole prefix and total cost grows
as O(T^2). Sequences that finish at TRUNCATE after ~200 tokens still pay for all
1024 steps.

This module keeps the vocabulary byte-identical to upstream (the checkpoint
depends on the exact token ordering) but adds:
  * batched sampling  -- B sequences per forward pass
  * early stop        -- halt once every row has emitted TRUNCATE
  * prefix condition  -- seed with an arbitrary token list instead of bare VSS
"""
import os
import sys

import torch
from torch.nn import functional as F

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "AnalogGenie", "repo"))

# Upstream hyperparameters -- these must match Pretrain.pth
BLOCK_SIZE = 1024
N_EMBD = 384
N_HEAD = 6
N_LAYER = 6
DROPOUT = 0.2


def build_vocab():
    """Reproduce upstream's device list exactly. Order defines token ids."""
    nm_np_bases = ["{}_D", "{}_G", "{}_S", "{}_B"]
    npn_pnp_bases = ["{}_C", "{}_B", "{}_E"]
    c_r_l_i_bases = ["{}_P", "{}_N"]
    xor_bases = ["{}_A", "{}_B", "{}_VDD", "{}_VSS", "{}_Y"]
    pfd_bases = ["{}_A", "{}_B", "{}_QA", "{}_QB", "{}_VDD", "{}_VSS"]
    inverter_bases = ["{}_A", "{}_Q", "{}_VDD", "{}_VSS"]
    tg_bases = ["{}_A", "{}_B", "{}_C", "{}_VDD", "{}_VSS"]

    devices = []
    for prefix in ["NM", "PM"]:
        for i in range(1, 35):
            devices.append(f"{prefix}{i}")
            devices.extend(b.format(f"{prefix}{i}") for b in nm_np_bases)
    for prefix in ["NPN", "PNP"]:
        for i in range(1, 27):
            devices.append(f"{prefix}{i}")
            devices.extend(b.format(f"{prefix}{i}") for b in npn_pnp_bases)
    for tag, hi in (("R", 28), ("C", 16), ("L", 24), ("DIO", 8)):
        for i in range(1, hi):
            devices.append(f"{tag}{i}")
            devices.extend(b.format(f"{tag}{i}") for b in c_r_l_i_bases)
    for i in range(1, 2):
        devices.append(f"XOR{i}")
        devices.extend(b.format(f"XOR{i}") for b in xor_bases)
    for i in range(1, 2):
        devices.append(f"PFD{i}")
        devices.extend(b.format(f"PFD{i}") for b in pfd_bases)
    for i in range(1, 11):
        devices.append(f"INVERTER{i}")
        devices.extend(b.format(f"INVERTER{i}") for b in inverter_bases)
    for i in range(1, 13):
        devices.append(f"TRANSMISSION_GATE{i}")
        devices.extend(b.format(f"TRANSMISSION_GATE{i}") for b in tg_bases)

    singles = [("VIN", 11), ("IIN", 3), ("VOUT", 7), ("IOUT", 5), ("VB", 11),
               ("IB", 7), ("VCONT", 21), ("VCLK", 9), ("VCM", 3), ("VREF", 3),
               ("IREF", 3), ("VRF", 3), ("VLO", 5), ("VIF", 3), ("VBB", 5),
               ("LOGICA", 3), ("LOGICB", 3), ("LOGICD", 3), ("LOGICF", 3),
               ("LOGICG", 3), ("LOGICQ", 3), ("LOGICQA", 2), ("LOGICQB", 2),
               ("VLATCH", 3), ("VHOLD", 2), ("VTRACK", 3)]
    for tag, hi in singles:
        devices.extend(f"{tag}{i}" for i in range(1, hi))

    devices.extend(["VDD", "VSS", "TRUNCATE"])
    return devices


DEVICES = build_vocab()
STOI = {d: i for i, d in enumerate(DEVICES)}
ITOS = {i: d for i, d in enumerate(DEVICES)}
VOCAB_SIZE = len(DEVICES)
VSS_ID = STOI["VSS"]
TRUNCATE_ID = STOI["TRUNCATE"]


def load_model(device="cpu", ckpt=None):
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from Models.GPT import GPTLanguageModel

    model = GPTLanguageModel(VOCAB_SIZE, N_EMBD, BLOCK_SIZE, N_HEAD, N_LAYER, DROPOUT)
    ckpt = ckpt or os.path.join(REPO, "Pretrain.pth")
    state = torch.load(ckpt, map_location=device)   # upstream omits map_location
    model.load_state_dict(state, strict=False)
    model.to(device)
    model.eval()
    return model


@torch.no_grad()
def generate_batch(model, prefix_ids, batch=None, max_new_tokens=1024,
                   temperature=0.7, device="cpu", progress=None):
    """Sample sequences, stopping early once every row has emitted TRUNCATE.

    `prefix_ids` is either a single prefix (repeated `batch` times) or a list of
    per-row prefixes. Rows only need to share a *length*, not contents -- they
    are different rows of one tensor, so a batch of 64 distinct LNA seeds runs
    as one forward pass. Grouping by identical prefix instead would collapse to
    batch-1, which on GPU is ~150x slower per sequence than batch-64.

    Returns (tensor [batch, T], steps_taken).
    """
    if prefix_ids and isinstance(prefix_ids[0], (list, tuple)):
        lens = {len(p) for p in prefix_ids}
        if len(lens) != 1:
            raise ValueError(f"prefixes must share a length, got {sorted(lens)}")
        idx = torch.tensor(list(prefix_ids), dtype=torch.long, device=device)
        batch = idx.size(0)
    else:
        if batch is None:
            raise ValueError("batch is required when passing a single prefix")
        idx = torch.tensor(prefix_ids, dtype=torch.long, device=device)
        idx = idx.unsqueeze(0).repeat(batch, 1)
    done = torch.zeros(batch, dtype=torch.bool, device=device)

    for step in range(max_new_tokens):
        idx_cond = idx[:, -model.block_size:]
        logits, _ = model(idx_cond)
        logits = logits[:, -1, :] / temperature
        probs = F.softmax(logits, dim=-1)
        nxt = torch.multinomial(probs, num_samples=1)
        nxt[done] = TRUNCATE_ID           # freeze finished rows
        idx = torch.cat((idx, nxt), dim=1)
        done |= nxt.squeeze(1) == TRUNCATE_ID
        if progress and step % progress == 0:
            print(f"    step {step:4d}  finished {int(done.sum())}/{batch}", flush=True)
        if bool(done.all()):
            return idx, step + 1
    return idx, max_new_tokens


def decode(ids):
    """Upstream's on-disk format: tokens joined by '->' with a trailing '->'."""
    return "->".join(ITOS[int(i)] for i in ids) + "->"


def first_circuit(ids):
    """Tokens up to the first TRUNCATE (one complete Eulerian circuit)."""
    out = []
    for i in ids:
        if int(i) == TRUNCATE_ID:
            break
        out.append(int(i))
    return out
