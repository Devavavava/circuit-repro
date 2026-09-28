"""One-off editor for kernel v4 (vgen-only push): main guard in vgen.py, random LoRA
maker, R3_MODE switch. Run once from the worktree root."""
p = "kaggle/kernels-editcap/rl-readiness-r3-grpo/kernel.py"
s = open(p).read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (old[:80], s.count(old))
    s = s.replace(old, new)


rep('''                emit(phase="natural_validity", status="ERROR", error=repr(e)[:800])
main()
"""''', '''                emit(phase="natural_validity", status="ERROR", error=repr(e)[:800])


if __name__ == "__main__":   # vLLM V1 starts its engine core with spawn -> re-imports this file
    main()
"""

# random-init LoRA adapter (r=16, all 7 projections, every layer) in PEFT format so the
# dedicated-GPU vLLM test exercises the LoRA path without a trainer in the same session.
MAKE_LORA_PY = r"""
import json, os, sys, torch
from safetensors.torch import save_file
out = sys.argv[1]
cfg = json.load(open(sys.argv[2]))
H, I = cfg["hidden_size"], cfg["intermediate_size"]
hd = cfg.get("head_dim") or H // cfg["num_attention_heads"]
q, kv = cfg["num_attention_heads"] * hd, cfg["num_key_value_heads"] * hd
shapes = {"self_attn.q_proj": (H, q), "self_attn.k_proj": (H, kv), "self_attn.v_proj": (H, kv),
          "self_attn.o_proj": (q, H), "mlp.gate_proj": (H, I), "mlp.up_proj": (H, I),
          "mlp.down_proj": (I, H)}
r = 16
g = torch.Generator().manual_seed(0)
t = {}
for i in range(cfg["num_hidden_layers"]):
    for m, (din, dout) in shapes.items():
        k = "base_model.model.model.layers.%d.%s" % (i, m)
        t[k + ".lora_A.weight"] = (torch.randn(r, din, generator=g) / din ** 0.5).half()
        t[k + ".lora_B.weight"] = (torch.randn(dout, r, generator=g) * 1e-3).half()
os.makedirs(out, exist_ok=True)
save_file(t, os.path.join(out, "adapter_model.safetensors"))
json.dump({"peft_type": "LORA", "task_type": "CAUSAL_LM", "r": r, "lora_alpha": 32,
           "lora_dropout": 0.0, "bias": "none", "base_model_name_or_path": "",
           "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj",
                              "down_proj"], "fan_in_fan_out": False, "inference_mode": True,
           "modules_to_save": None}, open(os.path.join(out, "adapter_config.json"), "w"))
print("LORA_OK", len(t), sum(v.numel() for v in t.values()))
"""''')
rep('''BUDGET_MIN = float(os.environ.get("R3_BUDGET_MIN", "75"))''',
    '''# R3_MODE: "full" = pushes 1-3 (trials); "vgen" = push 4 (vLLM on a dedicated T4 only:
# run3's VGEN died on a missing __main__ guard in vgen.py, everything else was measured)
R3_MODE = "vgen"
BUDGET_MIN = float(os.environ.get("R3_BUDGET_MIN", "75" if R3_MODE == "full" else "35"))''')
rep('''    open(os.path.join(TMP, "vgen.py"), "w").write(VGEN_PY)''',
    '''    open(os.path.join(TMP, "vgen.py"), "w").write(VGEN_PY)
    open(os.path.join(TMP, "make_lora.py"), "w").write(MAKE_LORA_PY)''')
rep('''        check_fence(rows)
        spice_bench()''', '''        check_fence(rows)
        if R3_MODE == "vgen":
            return vgen_only(summary)
        spice_bench()''')
rep('''def main():
    os.makedirs(OUT, exist_ok=True)''', '''def vgen_only(summary):
    """Push 4: two concurrent dedicated-GPU vLLM generation tests (with / without LoRA)."""
    cons, pins = constraints()
    vth = threading.Thread(target=install_vllm_venv, args=(cons,), daemon=True)
    vth.start()
    predownload()
    vth.join()
    if VLLM_STATE["status"] != "ok":
        log("vllm venv failed:", VLLM_STATE)
        return
    snap = glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--%s/snapshots/*/config.json"
                                        % MODEL.replace("/", "--")))
    lora = os.path.join(TMP, "lora-rand")
    if snap:
        rc, _ = sh([VLLM_STATE["python"], os.path.join(TMP, "make_lora.py"), lora, snap[0]],
                   timeout=600, logfile=os.path.join(OUT, "make-lora.log"))
        event("make_lora", rc=rc, dir=lora, exists=os.path.isdir(lora))
    th = [threading.Thread(target=run_vgen, args=(0, "VGEN-G8-L1024-lora"), kwargs={"lora": lora}),
          threading.Thread(target=run_vgen, args=(1, "VGEN-G8-L1024-base"), kwargs={"lora": ""})]
    th[0].start()
    time.sleep(20)
    th[1].start()
    for t in th:
        t.join()


def main():
    os.makedirs(OUT, exist_ok=True)''')
open(p, "w").write(s)
print("patched")
