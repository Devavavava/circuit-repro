"""ZeroSim smoke test: build CircuitTransformer from the repo's own config and
run a forward + backward pass on a synthetic circuit batch.

The released dataset (Xun49/Amplifer60) is a single 4.27 GB zip, which is a heavy
download for a smoke test, and no checkpoint is published -- so this exercises the
model/ code path directly with a tiny synthetic batch shaped per the repo's own
docstring: nodes [B, N], params [B, N, P], attn_mask [B, N, N] adjacency.
"""
import json
import os
import sys

import torch
from omegaconf import OmegaConf

REPO = r"C:\Users\Devavrat\circuit-repro\extensions\ZeroSim"
sys.path.insert(0, REPO)
from model.circuitformer import CircuitTransformer

cfg = OmegaConf.load(os.path.join(REPO, "configs", "config.yaml"))
vocab = json.load(open(os.path.join(REPO, "configs", "device_vocab.json")))
num_device_types = len(vocab)
print(f"device vocab entries : {num_device_types}")
print(f"model config         : {OmegaConf.to_container(cfg.model)}")

m = cfg.model
model = CircuitTransformer(
    num_encoder_layers=m.num_encoder_layers,
    num_decoder_layers=m.num_decoder_layers,
    num_device_types=num_device_types,
    num_metrics=m.num_metrics,
    num_cross_layers=m.num_cross_layers,
    node_emb_dim=m.node_emb_dim,
    out_dim=m.out_dim,
    num_heads=m.num_heads,
    decoder_type=m.decoder_type,
    dropout=m.dropout,
    ffn_embedding_dim=m.ffn_embedding_dim,
    degree_embed=m.degree_embed,
    max_degree=m.max_degree,
    activation=m.activation,
    norm_type=m.norm_type,
    max_nodes=cfg.dataset.max_nodes,
    pos_encoding_type=m.pos_encoding_type,
    lap_dim=m.lap_dim,
)
n_par = sum(p.numel() for p in model.parameters())
print(f"parameters           : {n_par/1e6:.2f} M")

# Synthetic batch: 2 circuits, 12 device-pin nodes each, 4 params per node.
torch.manual_seed(0)
B, N, P = 2, 12, 4
nodes = torch.randint(1, num_device_types, (B, N))
params = torch.randn(B, N, P)

# Plain [B, N, N] binary adjacency (1 = connected). The model prepends the graph
# token row/column itself and converts 1 -> 0.0 / else -> -inf internally.
adj = (torch.rand(B, N, N) < 0.3).float()
adj = ((adj + adj.transpose(1, 2)) > 0).float()
adj = ((adj + torch.eye(N).unsqueeze(0)) > 0).float()
attn_mask = adj

model.train()
out = model(nodes=nodes, params=params, attn_mask=attn_mask)
print(f"\nforward output shape : {tuple(out.shape)}  (expect [B={B}, num_metrics={m.num_metrics}])")
print(f"output finite        : {bool(torch.isfinite(out).all())}")

target = torch.randn_like(out)
loss = torch.nn.functional.mse_loss(out, target)
loss.backward()
grads = [p.grad for p in model.parameters() if p.grad is not None]
gnorm = sum(float(g.pow(2).sum()) for g in grads) ** 0.5
print(f"loss                 : {loss.item():.4f}")
print(f"params with grads    : {len(grads)}/{len(list(model.parameters()))}")
print(f"global grad norm     : {gnorm:.4f}")

# A few optimiser steps to show the loss actually moves.
opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
losses = []
for _ in range(5):
    opt.zero_grad()
    out = model(nodes=nodes, params=params, attn_mask=attn_mask)
    l = torch.nn.functional.mse_loss(out, target)
    l.backward()
    opt.step()
    losses.append(round(l.item(), 4))
print(f"5 training steps     : {losses}")

ok = out.shape == (B, m.num_metrics) and gnorm > 0 and losses[-1] < losses[0]
print("\nSMOKE TEST:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
