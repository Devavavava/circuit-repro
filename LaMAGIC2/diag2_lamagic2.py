"""Check whether from_pretrained actually loaded every weight, and whether the
float conditioning (vout/eff) has any effect on the model's output."""
import json
import sys

import torch
from transformers import T5Tokenizer

REPO = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\repo"
CKPT = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\ckpt"
DATA = r"C:\Users\Devavrat\circuit-repro\LaMAGIC2\data\SFCI_345comp.json"
sys.path.insert(0, REPO)
from analog_LLM.models.T5_transformer import T5ForConditionalGeneration as T5CondGen

model, info = T5CondGen.from_pretrained(CKPT, output_loading_info=True)
for k, v in info.items():
    print(f"{k}: {len(v)}")
    for x in list(v)[:12]:
        print("    ", x)
model.eval()

raw = torch.load(f"{CKPT}/pytorch_model.bin", map_location="cpu")
print("\nvout_linear loaded correctly:",
      torch.allclose(model.vout_linear.weight, raw["vout_linear.weight"]))
print("shared.weight loaded correctly:",
      torch.allclose(model.get_input_embeddings().weight, raw["shared.weight"]))

tok = T5Tokenizer.from_pretrained(CKPT, model_max_length=512, padding_side="right",
                                  use_fast=False, legacy=True)
nt = ['VIN', 'VOUT', 'GND', '<duty_0.1>', '<duty_0.2>', '<duty_0.3>', '<duty_0.4>',
      '<duty_0.5>', '<duty_0.6>', '<duty_0.7>', '<duty_0.8>', '<duty_0.9>',
      '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12',
      'Sa', 'Sb', 'C', 'L']
tok.add_tokens(nt)
tok.add_special_tokens({"sep_token": "<sep>"})

rec = json.load(open(DATA))[0]
ii = torch.tensor([tok.encode(" ".join(rec["input"].split()))])
lb = torch.tensor([tok.encode(" ".join(rec["output"].split()))])
dco = torch.tensor([[0.1, 0.3, 0.5, 0.7, 0.9]])

print("\nlabel tokens:", tok.convert_ids_to_tokens(lb[0].tolist()))

# Does the conditioning change anything at all?
for tag, vo, ef in [("true", rec["vout"], rec["eff"]),
                    ("zeros", 0.0, 0.0),
                    ("extreme", 5.0, 5.0)]:
    with torch.no_grad():
        out = model(input_ids=ii, attention_mask=torch.ones_like(ii), labels=lb,
                    d_cycle_option=dco,
                    vout=torch.tensor([[vo]], dtype=torch.float),
                    eff=torch.tensor([[ef]], dtype=torch.float))
        g = model.generate(input_ids=ii, attention_mask=torch.ones_like(ii),
                           d_cycle_option=dco,
                           vout=torch.tensor([[vo]], dtype=torch.float),
                           eff=torch.tensor([[ef]], dtype=torch.float),
                           max_length=64, num_beams=1, do_sample=False)
    print(f"\n[{tag}] loss={out.loss.item():.3f}")
    print("   gen:", tok.decode(g[0], skip_special_tokens=False))

# Self-consistency: loss of the model's own greedy output as labels.
with torch.no_grad():
    g = model.generate(input_ids=ii, attention_mask=torch.ones_like(ii),
                       d_cycle_option=dco,
                       vout=torch.tensor([[rec["vout"]]], dtype=torch.float),
                       eff=torch.tensor([[rec["eff"]]], dtype=torch.float),
                       max_length=64, num_beams=1, do_sample=False)
    self_lb = g[:, 1:]  # drop decoder_start pad
    out = model(input_ids=ii, attention_mask=torch.ones_like(ii), labels=self_lb,
                d_cycle_option=dco,
                vout=torch.tensor([[rec["vout"]]], dtype=torch.float),
                eff=torch.tensor([[rec["eff"]]], dtype=torch.float))
print(f"\nloss on model's OWN greedy output: {out.loss.item():.4f}")
