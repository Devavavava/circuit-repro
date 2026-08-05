"""LaMAGIC2 SFCI checkpoint inference on the GPU (WSL).

Same test as the Windows CPU run, with Linux paths and the model on CUDA.
Checkpoint/dataset are read from the Windows side via /mnt/c (not re-downloaded).
"""
import json
import sys
import time

import torch
from transformers import T5Tokenizer

WIN = "/mnt/c/Users/Devavrat/circuit-repro/LaMAGIC2"
REPO = "/root/circuit-repro/gpu/LaMAGIC2/repo"
CKPT = f"{WIN}/ckpt"
DATA = f"{WIN}/data/SFCI_345comp.json"
sys.path.insert(0, REPO)
from analog_LLM.models.T5_transformer import T5ForConditionalGeneration as T5CondGen

dev = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", dev)
if dev == "cuda":
    print("gpu   :", torch.cuda.get_device_name(0))

tok = T5Tokenizer.from_pretrained(CKPT, model_max_length=512,
                                  padding_side="right", use_fast=False, legacy=True)
tok.add_tokens(['VIN', 'VOUT', 'GND', '<duty_0.1>', '<duty_0.2>', '<duty_0.3>',
                '<duty_0.4>', '<duty_0.5>', '<duty_0.6>', '<duty_0.7>', '<duty_0.8>',
                '<duty_0.9>', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                '10', '11', '12', 'Sa', 'Sb', 'C', 'L'])
tok.add_special_tokens({"sep_token": "<sep>"})

t0 = time.time()
model = T5CondGen.from_pretrained(CKPT).to(dev).eval()
print(f"checkpoint load: {time.time()-t0:.1f}s")
print("vout_linear    :", tuple(model.vout_linear.weight.shape))
if dev == "cuda":
    print(f"VRAM allocated : {torch.cuda.memory_allocated()/1e9:.2f} GB")

rec = json.load(open(DATA))[0]
ii = torch.tensor([tok.encode(" ".join(rec["input"].split()))]).to(dev)
dco = torch.tensor([[0.1, 0.3, 0.5, 0.7, 0.9]]).to(dev)
vo = torch.tensor([[rec["vout"]]], dtype=torch.float).to(dev)
ef = torch.tensor([[rec["eff"]]], dtype=torch.float).to(dev)

print("\ninput :", repr(rec["input"]))
print("vout  :", rec["vout"], " eff:", rec["eff"])

if dev == "cuda":
    torch.cuda.synchronize()
t0 = time.time()
with torch.no_grad():
    g = model.generate(input_ids=ii, attention_mask=torch.ones_like(ii),
                       d_cycle_option=dco, vout=vo, eff=ef,
                       max_length=128, num_beams=1, do_sample=False)
if dev == "cuda":
    torch.cuda.synchronize()
print(f"generation time: {time.time()-t0:.2f}s")
print("\n--- GENERATED TOPOLOGY ---")
print(tok.decode(g[0], skip_special_tokens=False))
print("\n--- REFERENCE ---")
print(" ".join(rec["output"].split()))

# Self-consistency, same objective check as the CPU run.
with torch.no_grad():
    out = model(input_ids=ii, attention_mask=torch.ones_like(ii), labels=g[:, 1:],
                d_cycle_option=dco, vout=vo, eff=ef)
print(f"\nloss on own greedy output: {out.loss.item():.4f}  (CPU run gave 0.0610)")
