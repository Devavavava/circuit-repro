"""Inductor logit bias for constrained decoding (WP-GEN P4, plans/04-GEN.md §5).

The fine-tuned arms under-produce inductors (ratio ~0.10 vs 0.188 real), because
inductors are rare in the corpus and rarer still in what the model recites. A
decoding-time nudge fixes this without touching the weights: at every step where
a sequence's *running* inductor ratio is below the spec-class target, add +lambda
to the logits of the L-family device tokens it hasn't used yet, and let it lapse
once the ratio is met. Pure sampling-side, composes on any model.

Risk (called out in the plan): a biased-in inductor can be structurally valid but
electrically pointless. Validity and the L1 feasibility gate are the honest judges
-- this module reports the inductor ratio it achieves; novelty.py / bias.py judge
whether it is junk.
"""
import torch
from torch.nn import functional as F

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genie_common import ITOS, TRUNCATE_ID, VSS_ID  # noqa: E402
from topology import base_of, is_device  # noqa: E402


def _masks(vocab_size):
    """(device_mask, l_mask): bool[vocab] over device tokens and L-device tokens."""
    dev = torch.zeros(vocab_size, dtype=torch.bool)
    ldev = torch.zeros(vocab_size, dtype=torch.bool)
    for i in range(vocab_size):
        tok = ITOS.get(i)                     # base vocab; extended ids (>=1005) -> None
        if tok is None:
            continue
        if is_device(tok):
            dev[i] = True
            if base_of(tok) == "L":
                ldev[i] = True
    return dev, ldev


@torch.no_grad()
def generate_inductor_biased(model, prefix_ids, lambda_L, target_ratio=0.188,
                             max_new_tokens=256, temperature=0.7, device="cpu"):
    """Batched sampling with the inductor logit bias. `prefix_ids` is a list of
    per-row prefixes sharing a length. Returns (idx [B,T], steps)."""
    vocab_size = model.lm_head.weight.size(0)
    dev_mask, l_mask = _masks(vocab_size)
    dev_mask, l_mask = dev_mask.to(device), l_mask.to(device)
    l_ids = torch.nonzero(l_mask, as_tuple=False).squeeze(1)      # [nL]

    idx = torch.tensor(list(prefix_ids), dtype=torch.long, device=device)
    B = idx.size(0)
    ar = torch.arange(B, device=device)
    done = torch.zeros(B, dtype=torch.bool, device=device)
    n_dev = torch.zeros(B, device=device)
    n_ind = torch.zeros(B, device=device)
    used = torch.zeros(B, vocab_size, dtype=torch.bool, device=device)
    for row in range(B):                                          # seed counts from prefix
        for t in idx[row].tolist():
            if not used[row, t] and dev_mask[t]:
                n_dev[row] += 1
                n_ind[row] += float(l_mask[t])
            used[row, t] = True

    for step in range(max_new_tokens):
        logits = model(idx[:, -model.block_size:])[0][:, -1, :] / temperature
        if lambda_L:
            ratio = n_ind / n_dev.clamp(min=1.0)
            # Only nudge where the model ITSELF is about to introduce a device
            # (its argmax is a device token). Biasing L-tokens everywhere just
            # jams them into pin/net positions and destroys validity (measured);
            # gating on the model's own grammar keeps the sequence legal and only
            # swaps a device choice toward an inductor.
            at_dev = dev_mask[logits.argmax(dim=-1)]              # [B]
            need = (ratio < target_ratio) & ~done & at_dev       # [B]
            if need.any():
                add = need.unsqueeze(1) & ~used[:, l_ids]         # [B, nL]
                logits[:, l_ids] += lambda_L * add.float()
        probs = F.softmax(logits, dim=-1)
        nxt = torch.multinomial(probs, num_samples=1).squeeze(1)  # [B]
        nxt[done] = TRUNCATE_ID
        new = ~used[ar, nxt]
        n_dev += (new & dev_mask[nxt]).float()
        n_ind += (new & l_mask[nxt]).float()
        used[ar, nxt] = True
        idx = torch.cat((idx, nxt.unsqueeze(1)), dim=1)
        done |= nxt == TRUNCATE_ID
        if bool(done.all()):
            return idx, step + 1
    return idx, max_new_tokens
