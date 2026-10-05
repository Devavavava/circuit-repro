#!/usr/bin/env python
"""LoRA dir -> merged 16-bit HF checkpoint (E-e MERGE_PY, verbatim logic).
usage: sft_merge.py <lora_dir> <out_dir>"""
import os
import sys
import time

lora, outdir = sys.argv[1], sys.argv[2]
t = time.time()
from unsloth import FastLanguageModel  # noqa: E402

model, tok = FastLanguageModel.from_pretrained(model_name=lora, max_seq_length=2048,
                                               load_in_4bit=True, dtype=None)
model.save_pretrained_merged(outdir, tok, save_method="merged_16bit")
sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(outdir) for f in fs)
print("MERGED_OK bytes=%d s=%.1f" % (sz, time.time() - t), flush=True)
