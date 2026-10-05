#!/usr/bin/env python
"""pilot-v0 P1 QLoRA SFT (runs in the Kaggle sft kernels, ONE T4).

E-e settings (kaggle/campaigns/bench-v12-audit/E-e): unsloth FastLanguageModel 4-bit
(unsloth/Qwen3-14B-unsloth-bnb-4bit), LoRA r=16 alpha=16 dropout 0 on the 7 projections,
unsloth gradient checkpointing, random_state 3407, trainable params in fp32, fp16 autocast
+ GradScaler, bitsandbytes AdamW8bit lr 2e-4 wd 0, batch 1 (one sequence per micro-step),
prompt tokens masked (-100), the E-e custom loop (no TRL trainer).
P1 additions (identical for the 100/300/1000 subsets): 2 epochs, grad accumulation 4,
linear warmup 10 optimizer steps then linear decay to 0, grad-norm clip 1.0, epoch e
shuffled with random.Random(seed + e), sequences > max-seq (8192) dropped (counted).

Row (sft-<N>.jsonl): {"id", "messages": [system, user], "think": <rationale>,
                      "answer": "```netlist\n...```"}
Sequence = "<|im_start|>system\n{S}<|im_end|>\n<|im_start|>user\n{U}<|im_end|>\n
            <|im_start|>assistant\n"  (masked)
          + "<think>\n{think}\n</think>\n\n{answer}<|im_end|>\n"  (trained)
i.e. Qwen3's own chat format in thinking mode (what llama-server's /apply-template +
the CAP two-phase path produce at eval: the model generates '<think>\n...').
"""
import argparse
import json
import math
import os
import random
import statistics
import sys
import time

TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def prompt_str(row):
    s, u = row["messages"][0], row["messages"][1]
    assert s["role"] == "system" and u["role"] == "user" and len(row["messages"]) == 2
    return ("<|im_start|>system\n%s<|im_end|>\n<|im_start|>user\n%s<|im_end|>\n"
            "<|im_start|>assistant\n" % (s["content"], u["content"]))


def completion_str(row):
    return "<think>\n%s\n</think>\n\n%s<|im_end|>\n" % (row["think"].strip(), row["answer"].strip())


def build(enc, row):
    P = enc(prompt_str(row))
    A = enc(completion_str(row))
    return P + A, [-100] * len(P) + A, len(P), len(A)


def lr_at(step, total, base, warmup):
    if step < warmup:
        return base * (step + 1) / warmup
    return base * max(0.0, (total - step) / max(1, total - warmup))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out-lora", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--model", default="unsloth/Qwen3-14B-unsloth-bnb-4bit")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=3407)
    ap.add_argument("--max-seq", type=int, default=8192)
    ap.add_argument("--deadline-epoch", type=float, default=0.0)
    ap.add_argument("--dry-tokenizer", default="", help="mock test: a tokenizer stand-in module")
    a = ap.parse_args()

    def emit(**kw):
        kw["t"] = round(time.time(), 1)
        with open(a.log, "a") as f:
            f.write(json.dumps(kw) + "\n")
        print("EMIT", json.dumps(kw)[:600], flush=True)

    rows = [json.loads(l) for l in open(a.rows) if l.strip()]
    hp = {k: getattr(a, k) for k in ("model", "epochs", "lr", "grad_accum", "warmup", "clip",
                                     "seed", "max_seq")}
    hp.update(lora_r=16, lora_alpha=16, lora_dropout=0, targets=TARGETS, optimizer="AdamW8bit",
              weight_decay=0.0, batch=1, autocast="fp16+GradScaler")
    emit(phase="start", n_rows=len(rows), hparams=hp)

    if a.dry_tokenizer:                     # local mock test: no torch/unsloth
        sys.path.insert(0, os.path.dirname(a.dry_tokenizer))
        tokmod = __import__(os.path.basename(a.dry_tokenizer)[:-3])
        enc = tokmod.enc
    else:
        import torch
        from unsloth import FastLanguageModel
        model, tok = FastLanguageModel.from_pretrained(model_name=a.model, max_seq_length=a.max_seq,
                                                       load_in_4bit=True, dtype=None)
        model = FastLanguageModel.get_peft_model(
            model, r=16, lora_alpha=16, lora_dropout=0, bias="none", target_modules=TARGETS,
            use_gradient_checkpointing="unsloth", random_state=a.seed)
        try:
            FastLanguageModel.for_training(model)
        except Exception:
            model.train()
        enc = lambda s: tok(s, add_special_tokens=False)["input_ids"]  # noqa: E731

    data, dropped = [], 0
    for r in rows:
        ids, lab, lp, la = build(enc, r)
        if len(ids) > a.max_seq:
            dropped += 1
            continue
        data.append((r["id"], ids, lab, lp, la))
    lens = [len(d[1]) for d in data]
    emit(phase="tokens", n=len(data), dropped_over_max_seq=dropped,
         seq_mean=round(statistics.mean(lens), 1), seq_max=max(lens), seq_min=min(lens),
         prompt_mean=round(statistics.mean(d[3] for d in data), 1),
         completion_mean=round(statistics.mean(d[4] for d in data), 1),
         completion_max=max(d[4] for d in data))
    total_micro = a.epochs * len(data)
    total_opt = math.ceil(total_micro / a.grad_accum)
    if a.dry_tokenizer:
        order = []
        for e in range(a.epochs):
            idx = list(range(len(data)))
            random.Random(a.seed + e).shuffle(idx)
            order += [data[i][0] for i in idx]
        emit(phase="done", dry=True, total_opt_steps=total_opt, order_head=order[:10])
        return

    params = [p for p in model.parameters() if p.requires_grad]
    for p in params:
        if p.dtype != torch.float32:
            p.data = p.data.float()
    import bitsandbytes as bnb
    opt = bnb.optim.AdamW8bit(params, lr=a.lr, weight_decay=0.0)
    scaler = torch.amp.GradScaler("cuda")
    dev = model.get_input_embeddings().weight.device
    emit(phase="load", trainable=sum(p.numel() for p in params),
         mem_gib=round(torch.cuda.memory_allocated(0) / 2 ** 30, 2), total_opt_steps=total_opt)
    step, micro, t_start = 0, 0, time.time()
    acc_loss, acc_n, times = 0.0, 0, []
    truncated = False
    opt.zero_grad(set_to_none=True)
    for e in range(a.epochs):
        idx = list(range(len(data)))
        random.Random(a.seed + e).shuffle(idx)
        for k, i in enumerate(idx):
            if a.deadline_epoch and time.time() > a.deadline_epoch:
                truncated = True
                break
            _id, ids, lab, _lp, _la = data[i]
            x = torch.tensor([ids], device=dev)
            y = torch.tensor([lab], device=dev)
            t = time.time()
            with torch.autocast("cuda", dtype=torch.float16):
                loss = model(input_ids=x, labels=y).loss
            scaler.scale(loss / a.grad_accum).backward()
            lv = float(loss.detach().float().item())
            acc_loss += lv
            acc_n += 1
            micro += 1
            del x, y, loss
            last = (k == len(idx) - 1) and e == a.epochs - 1
            if micro % a.grad_accum == 0 or last:
                for g in opt.param_groups:
                    g["lr"] = lr_at(step, total_opt, a.lr, a.warmup)
                scaler.unscale_(opt)
                gn = float(torch.nn.utils.clip_grad_norm_(params, a.clip))
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
                torch.cuda.synchronize()
                times.append(time.time() - t)
                emit(phase="step", step=step, epoch=e, micro=micro, loss=round(acc_loss / acc_n, 4),
                     lr=opt.param_groups[0]["lr"], grad_norm=round(gn, 4),
                     scale=float(scaler.get_scale()),
                     peak_gib=round(torch.cuda.max_memory_allocated(0) / 2 ** 30, 2),
                     elapsed_min=round((time.time() - t_start) / 60, 2))
                step += 1
                acc_loss, acc_n = 0.0, 0
        if truncated:
            break
        model.save_pretrained(a.out_lora)
        tok.save_pretrained(a.out_lora)
        emit(phase="epoch_saved", epoch=e, step=step)
    model.save_pretrained(a.out_lora)
    tok.save_pretrained(a.out_lora)
    emit(phase="done", steps=step, micro=micro, truncated=truncated,
         minutes=round((time.time() - t_start) / 60, 2),
         s_per_micro=round((time.time() - t_start) / max(1, micro), 2))


if __name__ == "__main__":
    main()
