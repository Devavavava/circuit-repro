"""exit-r1 Kaggle kernel body (kaggle/PREREG-EXIT-R1.md). Imported by the thin kernels in
kaggle/kernels-editcap/exit-r1-*/kernel.py after they clone the repo at a pinned commit.
Every step is pilot-v0's kernel_common.py (kaggle/campaigns/pilot-v0/P1/) or pilot-v1's
kernel_v1.py, unchanged; only the generation driver is new (r1_gen.py).

Kinds (CFG["kind"]):
  gen   step 1. The pilot-v0 LoRA adapter (kernel source devavratpatni/circuit-repro-pilot-v0-
        <tag>, p1/lora-<tag>/) -> pilot-v0 merge -> f16 -> Q4_K_M (pilot-v1 H1 path, D-V4) ->
        llama-server with the R2 flags but --parallel CFG["parallel"] slots of 16384 tokens
        each (-c 16384*parallel) -> r1_gen.py over gen/TASKS.json (training-side prompts,
        CAP-1024, arm B k=1, no few-shot, temperature 0.7), CFG["samples"] per task,
        task-major in the TASKS.json seeded order. Output p1/gen/.
  sft   steps 4+5. pilot-v0's SFT kernel (KC.main_sft: same recipe, merge, GGUF, the SAME
        held-out run) on CFG["rows"], with CFG["samples"] = 8 (sample-major: samples 1-2
        are the pilot-v0 2-sample protocol, 1-8 the pilot-v1 H1 pass@k protocol).
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.join(os.path.dirname(HERE), "pilot-v0", "P1")
PV1 = os.path.join(os.path.dirname(HERE), "pilot-v1")
sys.path.insert(0, P1)
sys.path.insert(0, PV1)
import kernel_common as KC  # noqa: E402
import kernel_v1 as KV1  # noqa: E402  (find_lora)

PREREG = "kaggle/PREREG-EXIT-R1.md (573a21a89)"


def run_gen(clone, model_id, out_dir):
    CFG = KC.CFG
    par = int(CFG.get("parallel", 4))
    env = KC.gen_env(clone)
    env.update(EDITCAP_THINK_BUDGET="1024", EDITCAP_RECOVER_REASONING="1", EDITCAP_GEN_ONLY="1")
    gen = os.path.join(clone, "kaggle", "campaigns", "exit-r1", "r1_gen.py")
    tasks = os.path.join(clone, "kaggle", "campaigns", "exit-r1", "gen", "TASKS.json")
    data = os.path.join(clone, "kaggle", "campaigns", "pilot-v0", "data", "train-all.jsonl")
    deadline = KC.T0 + CFG["start_deadline_min"] * 60
    inner = ("source %s && exec %s %s --tasks %s --data %s --out %s --samples %d --parallel %d "
             "--model-id %s --llm-url http://127.0.0.1:%d/v1 --deadline-epoch %.0f --limit %d"
             % (KC.ENV_SH, KC.PY, gen, tasks, data, out_dir, CFG.get("samples", 2), par, model_id,
                KC.PORT, deadline, CFG.get("task_limit", 0)))
    t = time.time()
    rc = KC.stream(["bash", "-c", inner], os.path.join(KC.OUT, "gen-%s.log" % CFG["tag"]), env=env,
                   timeout=max(60, CFG["hard_wall_min"] * 60 - (time.time() - KC.T0)))
    rows = []
    rp = os.path.join(out_dir, "results.jsonl")
    if os.path.exists(rp):
        rows = [json.loads(l) for l in open(rp) if l.strip()]
    rec = {"step": "gen", "model_id": model_id, "rc": rc, "minutes": round((time.time() - t) / 60, 1),
           "out": out_dir, "n_completions": len(rows), "n_valid": sum(1 for r in rows if r.get("valid")),
           "n_tasks_complete": sum(1 for tk in {r["task"] for r in rows}
                                   if len({r["sample"] for r in rows if r["task"] == tk})
                                   == CFG.get("samples", 2)),
           "gpu_min_sum_requests": round(sum((r.get("gpu_ms") or 0) for r in rows) / 60000, 2)}
    KC.MAN["runs"].append(rec)
    KC.event("gen_done", **rec)
    return rec


def main_gen(tok, clone, head):
    CFG = KC.CFG
    KC.preflight(["gh token", "ngspice cache", "llamacpp cache"])
    os.makedirs(KC.TMP, exist_ok=True)
    KC.env_log()
    bg = KC.start_llamacpp_tools()
    KC.install()
    src = KV1.find_lora(CFG["lora_tag"])
    lora = os.path.join(KC.TMP, "lora-" + CFG["lora_tag"])
    shutil.copytree(src, lora)
    st = os.path.join(lora, "adapter_model.safetensors")
    KC.event("lora", src=src, files=sorted(os.listdir(lora)),
             adapter_sha256=KC._sha256(st) if os.path.isfile(st) else None,
             adapter_bytes=os.path.getsize(st) if os.path.isfile(st) else None)
    gguf = KC.merge_to_q4(lora, bg)
    got = KC.MAN["gguf"].get("q4_sha256")
    KC.event("gguf_vs_pilot_v0", expect=CFG.get("expect_q4_sha256"), got=got,
             identical=(got == CFG.get("expect_q4_sha256")))
    KC.bootstrap(tok, clone, CFG["repo_branch"])
    KC.untar_llamacpp()
    KC.MAN["server_caps"] = KC.log_server_caps()
    par = int(CFG.get("parallel", 4))
    proc = KC.launch_server(gguf, parallel=par, ctx=16384 * par, tag="gen")
    try:
        KC.MAN["probe"] = KC.probe_two_phase()
        run_gen(clone, CFG["model_id"], os.path.join(KC.OUT, "gen"))
    finally:
        KC.stop_server(proc)


def main(cfg, tok, clone, head):
    KC.CFG.update(cfg)
    os.makedirs(KC.OUT, exist_ok=True)
    KC.MAN.update(kernel=cfg["tag"], clone_head=head, prereg=PREREG)
    rc = 0
    try:
        {"gen": main_gen, "sft": KC.main_sft}[cfg["kind"]](tok, clone, head)
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
