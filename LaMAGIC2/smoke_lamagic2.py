"""LaMAGIC2 smoke test: load the released SFCI checkpoint and generate one topology.

Uses the repo's own model class (analog_LLM/models/T5_transformer.py), which is a
T5 plus a `vout_linear` projection that turns the scalar specs (duty-cycle options,
voltage conversion ratio, efficiency) into encoder prefix embeddings -- this is the
"float input" of the SFCI formulation. Config values follow
run_SFCI_T5tokenizer_dataaug() in experiment/lamagic2/trn_pure_tranformer.py:
typeNidx=True, duty10=False, use_duty_cycle_option_prefix=True, tokenizer='flanT5'.

Reports teacher-forced loss on a real dataset pair (an objective check that the
checkpoint + tokenizer + input format all line up) and then a greedy generation.
"""
import json
import os
import sys

import torch
import transformers
from transformers import T5Tokenizer

REPO = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\repo"
CKPT = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\ckpt"
DATA = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\data\SFCI_345comp.json"
sys.path.insert(0, REPO)

from analog_LLM.models.T5_transformer import T5ForConditionalGeneration as T5CondGen

# --- tokenizer: flan-T5 + the repo's device tokens (typeNidx=True branch) ------
tok = T5Tokenizer.from_pretrained(CKPT, model_max_length=512,
                                  padding_side="right", use_fast=False, legacy=True)
base_len = len(tok)
node_tokens = ['VIN', 'VOUT', 'GND',
               '<duty_0.1>', '<duty_0.2>', '<duty_0.3>', '<duty_0.4>', '<duty_0.5>',
               '<duty_0.6>', '<duty_0.7>', '<duty_0.8>', '<duty_0.9>',
               '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
node_tokens = node_tokens + ['Sa', 'Sb', 'C', 'L']          # typeNidx=True -> append types
n_new = tok.add_tokens(node_tokens)
n_new_special = tok.add_special_tokens({"sep_token": "<sep>"}) if tok.sep_token is None else 0
print(f"tokenizer: base={base_len} +{n_new} tokens +{n_new_special} special -> len={len(tok)}")

# --- model ---------------------------------------------------------------------
model = T5CondGen.from_pretrained(CKPT)
emb = model.get_input_embeddings().weight.shape[0]
print(f"checkpoint embedding rows: {emb}")
print(f"vout_linear present: {hasattr(model, 'vout_linear')}, "
      f"shape={tuple(model.vout_linear.weight.shape)}")
if emb != len(tok):
    print(f"NOTE: resizing embeddings {emb} -> {len(tok)}")
    model.resize_token_embeddings(len(tok))
model.eval()

# --- one real record from the released dataset ---------------------------------
data = json.load(open(DATA))
rec = data[0]
print("\n--- input record ---")
print("vout :", rec["vout"])
print("eff  :", rec["eff"])
print("input:", repr(rec["input"]))
print("ref  :", repr(rec["output"]))

input_ids = torch.tensor([tok.encode(" ".join(rec["input"].split()))])
labels = torch.tensor([tok.encode(" ".join(rec["output"].split()))])
# duty10=False -> the 5-option duty prefix (RawTextDatasetConditionalGen_Transformer)
d_cycle_option = torch.tensor([[0.1, 0.3, 0.5, 0.7, 0.9]])
vout = torch.tensor([[rec["vout"]]], dtype=torch.float)
eff = torch.tensor([[rec["eff"]]], dtype=torch.float)

print(f"\ninput_ids {tuple(input_ids.shape)}  labels {tuple(labels.shape)}")
print("decoded input:", tok.decode(input_ids[0]))

# --- teacher-forced loss: objective check that everything lines up -------------
with torch.no_grad():
    out = model(input_ids=input_ids, attention_mask=torch.ones_like(input_ids),
                labels=labels, d_cycle_option=d_cycle_option, vout=vout, eff=eff)
print(f"\nteacher-forced loss on the true pair: {out.loss.item():.4f}")

# --- generation ----------------------------------------------------------------
with torch.no_grad():
    gen = model.generate(input_ids=input_ids,
                         attention_mask=torch.ones_like(input_ids),
                         d_cycle_option=d_cycle_option, vout=vout, eff=eff,
                         max_length=128, num_beams=1, do_sample=False)
text = tok.decode(gen[0], skip_special_tokens=False)
print("\n--- GENERATED TOPOLOGY ---")
print(text)
print("\n--- REFERENCE ---")
print(" ".join(rec["output"].split()))
