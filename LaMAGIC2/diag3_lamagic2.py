"""Confirm the teacher-forced-loss gap is a label whitespace/tokenization artifact.

Naively re-encoding the dataset's `output` string with " ".join(split()) puts a space
before each comma, which SentencePiece turns into a standalone '_' token the model
never emits. Collapsing " ," -> "," should drop the loss sharply if that is the cause.
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

tok = T5Tokenizer.from_pretrained(CKPT, model_max_length=512, padding_side="right",
                                  use_fast=False, legacy=True)
tok.add_tokens(['VIN', 'VOUT', 'GND', '<duty_0.1>', '<duty_0.2>', '<duty_0.3>',
                '<duty_0.4>', '<duty_0.5>', '<duty_0.6>', '<duty_0.7>', '<duty_0.8>',
                '<duty_0.9>', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                '10', '11', '12', 'Sa', 'Sb', 'C', 'L'])
tok.add_special_tokens({"sep_token": "<sep>"})
model = T5CondGen.from_pretrained(CKPT).eval()

data = json.load(open(DATA))
dco = torch.tensor([[0.1, 0.3, 0.5, 0.7, 0.9]])


def loss_for(rec, norm):
    ii = torch.tensor([tok.encode(" ".join(rec["input"].split()))])
    lb = torch.tensor([tok.encode(norm(rec["output"]))])
    with torch.no_grad():
        o = model(input_ids=ii, attention_mask=torch.ones_like(ii), labels=lb,
                  d_cycle_option=dco,
                  vout=torch.tensor([[rec["vout"]]], dtype=torch.float),
                  eff=torch.tensor([[rec["eff"]]], dtype=torch.float))
    return o.loss.item(), lb.shape[1]


naive = lambda s: " ".join(s.split())
nospace = lambda s: " ".join(s.split()).replace(" ,", ",")

print("record |  naive ' ,'  |  collapsed ','")
for i, rec in enumerate(data[:6]):
    a, la = loss_for(rec, naive)
    b, lb_ = loss_for(rec, nospace)
    print(f"  {i}    |  {a:7.3f} (n={la:2d}) |  {b:7.3f} (n={lb_:2d})")

rec = data[0]
print("\nnaive     tokens:", tok.convert_ids_to_tokens(tok.encode(naive(rec["output"]))))
print("\ncollapsed tokens:", tok.convert_ids_to_tokens(tok.encode(nospace(rec["output"]))))
