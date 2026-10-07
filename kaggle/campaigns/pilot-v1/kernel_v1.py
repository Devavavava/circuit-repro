"""pilot-v1 Kaggle kernel body (kaggle/PREREG-PILOT-V1.md). Imported by the thin kernels in
kaggle/kernels-editcap/pilot-v1-*/kernel.py after they clone the repo at a pinned commit.
Every step reuses pilot-v0's kernel_common.py (kaggle/campaigns/pilot-v0/P1/) unchanged.

Kinds (CFG["kind"]):
  lora_heldout  H1. The pilot-v0 LoRA adapter (attached as a kernel source: the output of
                devavratpatni/circuit-repro-pilot-v0-<tag>, p1/lora-<tag>/) -> pilot-v0's own
                merge (unsloth merged_16bit) -> llama.cpp b10636 convert f16 -> llama-quantize
                Q4_K_M (sha256 compared with the pilot-v0 GGUF) -> the pilot-v0 held-out run
                (same llama-server flags, same p1_gen.py heldout driver, CAP-1024, arm B k=1,
                temperature 0.7) with CFG["samples"] = 8 (sample-major order).
  rat           pilot-v0's rationalize kernel (official Qwen3-14B Q4_K_M, --parallel 4).
  sft           pilot-v0's SFT kernel (same recipe) on CFG["rows"] + the same held-out run.
"""
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.join(os.path.dirname(HERE), "pilot-v0", "P1")
sys.path.insert(0, P1)
import kernel_common as KC  # noqa: E402

PREREG = "kaggle/PREREG-PILOT-V1.md (e46157ccf)"


def find_lora(tag):
    hits = sorted(glob.glob("/kaggle/input/**/lora-%s/adapter_config.json" % tag, recursive=True))
    if not hits:
        KC.log("/kaggle/input:", glob.glob("/kaggle/input/*") + glob.glob("/kaggle/input/*/*")
               + glob.glob("/kaggle/input/*/*/*"))
        sys.exit("no lora-%s/adapter_config.json under /kaggle/input (kernel source missing)" % tag)
    return os.path.dirname(hits[0])


def main_lora_heldout(tok, clone, head):
    CFG = KC.CFG
    KC.preflight(["gh token", "ngspice cache", "llamacpp cache"])
    os.makedirs(KC.TMP, exist_ok=True)
    KC.env_log()
    bg = KC.start_llamacpp_tools()
    KC.install()
    src = find_lora(CFG["lora_tag"])
    lora = os.path.join(KC.TMP, "lora-" + CFG["lora_tag"])
    shutil.copytree(src, lora)
    files = sorted(os.listdir(lora))
    st = os.path.join(lora, "adapter_model.safetensors")
    KC.event("lora", src=src, files=files,
             adapter_sha256=KC._sha256(st) if os.path.isfile(st) else None,
             adapter_bytes=os.path.getsize(st) if os.path.isfile(st) else None)
    gguf = KC.merge_to_q4(lora, bg)
    got = KC.MAN["gguf"].get("q4_sha256")
    KC.event("gguf_vs_pilot_v0", expect=CFG.get("expect_q4_sha256"), got=got,
             identical=(got == CFG.get("expect_q4_sha256")))
    KC.bootstrap(tok, clone, CFG["repo_branch"])
    KC.untar_llamacpp()
    KC.MAN["server_caps"] = KC.log_server_caps()
    proc = KC.launch_server(gguf, parallel=1, tag="eval")
    try:
        KC.MAN["probe"] = KC.probe_two_phase()
        KC.run_eval(clone, CFG["model_id"], os.path.join(KC.OUT, "gen"), CFG["start_deadline_min"],
                    CFG["hard_wall_min"])
    finally:
        KC.stop_server(proc)


def main(cfg, tok, clone, head):
    KC.CFG.update(cfg)
    os.makedirs(KC.OUT, exist_ok=True)
    KC.MAN.update(kernel=cfg["tag"], clone_head=head, prereg=PREREG)
    rc = 0
    try:
        {"lora_heldout": main_lora_heldout, "rat": KC.main_rat,
         "sft": KC.main_sft}[cfg["kind"]](tok, clone, head)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
        KC.event("exit", code=str(e.code))
    except Exception as e:                                           # noqa: BLE001
        import traceback
        rc = 1
        KC.event("crash", error=repr(e)[:800], tb=traceback.format_exc()[-3000:])
    finally:
        KC.save_manifest()
    return rc
