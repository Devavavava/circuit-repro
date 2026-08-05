"""Compare the model's own greedy token sequence against the dataset reference,
token by token, to locate the divergence behind the high teacher-forced loss."""
import json
import sys

import torch
from transformers import T5Tokenizer

REPO = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\repo"
CKPT = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\ckpt"
DATA = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\data\SFCI_345comp.json"
sys.path.insert(0, REPO)
from analog_LLM.models.T5_transformer import T5ForConditionalGeneration as T5CondGen

tok = T5Tokenizer.from_pretrained(CKPT, model_max_length=512, padding_side="right",
                                  use_fast=False, legacy=True)
tok.add_tokens(['VIN', 'VOUT', 'GND', '<duty_0.1>', '<duty_0.2>', '<duty_0.3>',
                '<duty_0.4>', '<duty_0.5>', '<duty_0.6>', '<duty_0.7>', '<duty_0.8>',
                '<duty_0.9>', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                '10', '11', '12', 'Sa', 'Sb', 'C', 'L'])
tok.add_special_tokens({"sep_token": "<sep>"})
model = T5CondGen.from_pretrained(CKPT).eval()

rec = json.load(open(DATA))[0]
ii = torch.tensor([tok.encode(" ".join(rec["input"].split()))])
dco = torch.tensor([[0.1, 0.3, 0.5, 0.7, 0.9]])
vo = torch.tensor([[rec["vout"]]], dtype=torch.float)
ef = torch.tensor([[rec["eff"]]], dtype=torch.float)

with torch.no_grad():
    g = model.generate(input_ids=ii, attention_mask=torch.ones_like(ii),
                       d_cycle_option=dco, vout=vo, eff=ef,
                       max_length=64, num_beams=1, do_sample=False)
gen_ids = g[0].tolist()
ref_ids = tok.encode(" ".join(rec["output"].split()))

print("GEN ids:", gen_ids)
print("GEN tok:", tok.convert_ids_to_tokens(gen_ids))
print()
print("REF ids:", ref_ids)
print("REF tok:", tok.convert_ids_to_tokens(ref_ids))

# Per-position probability the model assigns to the reference label.
lb = torch.tensor([ref_ids])
with torch.no_grad():
    out = model(input_ids=ii, attention_mask=torch.ones_like(ii), labels=lb,
                d_cycle_option=dco, vout=vo, eff=ef)
lp = torch.log_softmax(out.logits[0], dim=-1)
print("\npos | ref token      | logprob | model's argmax")
for i, t in enumerate(ref_ids):
    am = lp[i].argmax().item()
    print(f"{i:3d} | {tok.convert_ids_to_tokens(t):14s} | {lp[i, t].item():8.3f} | "
          f"{tok.convert_ids_to_tokens(am)}")
    if i > 12:
        break
