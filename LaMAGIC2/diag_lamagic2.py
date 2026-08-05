"""Diagnose the tokenizer/embedding alignment for the LaMAGIC2 SFCI checkpoint.

The checkpoint's embedding has 32128 rows; reproducing the repo's add_device_token
recipe on flan-T5 gives len(tokenizer)=32115, so resizing down to 32115 discards
13 trained rows. This script compares loss with and without that resize, and prints
the ids assigned to the device tokens, to see which alignment the checkpoint expects.
"""
import json
import sys

import torch
from transformers import T5Tokenizer

REPO = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\repo"
CKPT = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\ckpt"
DATA = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\data\SFCI_345comp.json"
sys.path.insert(0, REPO)
from analog_LLM.models.T5_transformer import T5ForConditionalGeneration as T5CondGen


def build_tok():
    tok = T5Tokenizer.from_pretrained(CKPT, model_max_length=512,
                                      padding_side="right", use_fast=False, legacy=True)
    node_tokens = ['VIN', 'VOUT', 'GND',
                   '<duty_0.1>', '<duty_0.2>', '<duty_0.3>', '<duty_0.4>', '<duty_0.5>',
                   '<duty_0.6>', '<duty_0.7>', '<duty_0.8>', '<duty_0.9>',
                   '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
    node_tokens = node_tokens + ['Sa', 'Sb', 'C', 'L']
    n_new = tok.add_tokens(node_tokens)
    n_sp = tok.add_special_tokens({"sep_token": "<sep>"}) if tok.sep_token is None else 0
    return tok, n_new, n_sp


tok, n_new, n_sp = build_tok()
print(f"len(tok)={len(tok)}  new={n_new}  new_special={n_sp}")
probe = ['<sep>', '<duty_0.1>', '<duty_0.5>', '<duty_0.9>', 'Sa', 'Sb', 'C', 'L',
         'VIN', 'VOUT', 'GND', '0', '1', '12']
print("token -> id")
for t in probe:
    print(f"   {t:12s} {tok.convert_tokens_to_ids(t)}")

data = json.load(open(DATA))
recs = data[:5]

for do_resize in (False, True):
    model = T5CondGen.from_pretrained(CKPT)
    if do_resize:
        model.resize_token_embeddings(len(tok))
    model.eval()
    rows = model.get_input_embeddings().weight.shape[0]
    losses = []
    for rec in recs:
        ii = torch.tensor([tok.encode(" ".join(rec["input"].split()))])
        lb = torch.tensor([tok.encode(" ".join(rec["output"].split()))])
        with torch.no_grad():
            out = model(input_ids=ii, attention_mask=torch.ones_like(ii), labels=lb,
                        d_cycle_option=torch.tensor([[0.1, 0.3, 0.5, 0.7, 0.9]]),
                        vout=torch.tensor([[rec["vout"]]], dtype=torch.float),
                        eff=torch.tensor([[rec["eff"]]], dtype=torch.float))
        losses.append(out.loss.item())
    print(f"\nresize={do_resize}  emb_rows={rows}  "
          f"losses={[round(x, 3) for x in losses]}  mean={sum(losses)/len(losses):.3f}")
    del model
