"""pilot-v0 P1 Kaggle kernel body (imported by the thin kernels in
kaggle/kernels-editcap/pilot-v0-*/kernel.py AFTER they clone this repo at a pinned
commit, so everything that runs here is pinned).

Kinds (CFG["kind"]):
  eval   official Qwen3-14B Q4_K_M GGUF (official HF repo, sha256-verified, as R2/E-d),
         llama-server flags == rl-readiness R2 (-c 16384 --parallel 1 --split-mode layer
         --n-gpu-layers 999, no grammar, no seed), two-phase probe, then
         p1_gen.py eval (CAP-1024, arm B k=1, no few-shot, 2 samples, gen-only).
  rat    same model/server but --parallel 4 (-c 16384 -> 4096 per slot), then
         p1_gen.py rationalize on CFG["examples"] (a shard of the training examples).
  sft    QLoRA (E-e stack + settings: unsloth/Qwen3-14B-unsloth-bnb-4bit on ONE T4,
         r16/a16/dropout 0, 7 projections, unsloth GC, AdamW8bit lr 2e-4 wd 0, fp16
         autocast + GradScaler, batch 1, prompt tokens masked, seed 3407; P1 adds
         2 epochs, grad-accum 4, 10-step warmup + linear decay, clip 1.0, seq <= 8192)
         on CFG["rows"] -> LoRA (kernel output) -> unsloth merged_16bit -> llama.cpp
         b10636 convert_hf_to_gguf f16 -> llama-quantize Q4_K_M -> the SAME eval as
         kind=eval (same server flags, same driver) on that GGUF.
Outputs: /kaggle/working/p1/ (small files only; the GGUFs and merged weights live in /tmp).
"""
import glob
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

WORK = "/kaggle/working"
OUT = os.path.join(WORK, "p1")
TMP = "/tmp/p1"
LLAMACPP_PREFIX = os.path.join(WORK, "llamacpp")   # == R2 (untar target)
ENV_SH = os.path.join(WORK, "env-kaggle.sh")
PORT = 8080
PY = sys.executable
LLAMACPP_TAG = "b10636"   # == the llama-server in devavratpatni/circuit-repro-llamacpp-cuda
GGUF_OFFICIAL = {
    "url": "https://huggingface.co/Qwen/Qwen3-14B-GGUF/resolve/main/Qwen3-14B-Q4_K_M.gguf",
    "bytes": 9001752960,
    "sha256": "500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0",
}
SFT_BASE = "unsloth/Qwen3-14B-unsloth-bnb-4bit"     # E-e 14B (dynamic 4-bit), 1xT4
PINS = [   # E-e pinned stack (kaggle/campaigns/bench-v12-audit/E-e/README.md)
    "unsloth==2026.9.11", "unsloth_zoo==2026.9.7", "transformers==5.5.0", "trl==0.24.0",
    "peft==0.21.0", "bitsandbytes==0.50.2", "accelerate==1.15.0", "datasets==4.3.0",
]
NODEPS_EXTRA = ["cut_cross_entropy", "torchao", "tyro", "msgspec", "hf_transfer",
                "sentencepiece", "protobuf", "diffusers", "structlog", "typer", "click",
                "rich", "pydantic", "nest-asyncio", "regex", "pillow", "huggingface_hub",
                "safetensors", "psutil", "wheel", "packaging"]
HERE = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()
CFG = {}
MAN = {"runs": [], "events": []}


# ================================================================ helpers
def el_min():
    return (time.time() - T0) / 60.0


def log(*a):
    msg = "[p1 %s %6.1fm] %s" % (CFG.get("tag", "?"), el_min(), " ".join(str(x) for x in a))
    print(msg, flush=True)
    try:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "kernel.log"), "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def event(kind, **kw):
    kw.update(kind=kind, t_min=round(el_min(), 2))
    MAN["events"].append(kw)
    log("EVENT", json.dumps(kw, default=str)[:1500])
    save_manifest()


def save_manifest():
    try:
        MAN["wall_minutes"] = round(el_min(), 1)
        MAN["cfg"] = CFG
        with open(os.path.join(OUT, "KERNEL-MANIFEST.json"), "w") as fh:
            json.dump(MAN, fh, indent=2, default=str)
    except Exception:
        pass


def sh(cmd, timeout=None, logfile=None, env=None, shell=False, check=False):
    """run; output to logfile (or captured); return (rc, tail). rc 'TIMEOUT' on timeout."""
    shown = cmd if isinstance(cmd, str) else " ".join(cmd)
    shown = re.sub(r"://[^@/\s]+@", "://REDACTED@", shown)
    log("$", shown[:400])
    lf = open(logfile, "a") if logfile else None
    try:
        p = subprocess.run(cmd, shell=shell, env=env, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else ""
        rc = "TIMEOUT"
    if lf:
        lf.write(out)
        lf.close()
    if check and rc != 0:
        raise RuntimeError("command failed rc=%s: %s\n%s" % (rc, shown[:300], out[-2000:]))
    return rc, out[-4000:]


def stream(cmd, logfile, env=None, timeout=None):
    """run with live output to logfile + stdout (long jobs). returns rc or 'TIMEOUT'."""
    log("$ (stream)", (cmd if isinstance(cmd, str) else " ".join(cmd))[:400])
    with open(logfile, "a") as lf:
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=isinstance(cmd, str), start_new_session=True)
        t0 = time.time()
        for raw in iter(p.stdout.readline, b""):
            line = raw.decode("utf-8", "replace")
            lf.write(line)
            lf.flush()
            print(line, end="", flush=True)
            if timeout and time.time() - t0 > timeout:
                break
        if timeout and time.time() - t0 > timeout and p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            return "TIMEOUT"
        return p.wait()


def find_one(pattern):
    hits = sorted(glob.glob(pattern, recursive=True))
    return hits[0] if hits else None


def preflight(need):
    pats = {
        "gh token": ["/kaggle/input/**/gh_token*"],
        "ngspice cache": ["/kaggle/input/**/ngspice47.tar.gz", "/kaggle/input/**/ngspice47/bin/ngspice"],
        "llamacpp cache": ["/kaggle/input/**/llamacpp.tar.gz", "/kaggle/input/**/llamacpp/bin/llama-server"],
    }
    missing = [k for k in need if not any(glob.glob(p, recursive=True) for p in pats[k])]
    if missing:
        log("/kaggle/input:", glob.glob("/kaggle/input/*") + glob.glob("/kaggle/input/*/*"))
        sys.exit("PREFLIGHT FAILED -- missing inputs: %s" % ", ".join(missing))
    log("preflight OK:", need)


def bootstrap(tok, clone, branch):
    bs = os.path.join(clone, "kaggle", "bootstrap.sh")
    env = dict(os.environ, WITH_PANDAS="1", GH_READ_TOKEN=tok, REPO_SLUG=CFG["repo_slug"],
               REPO_BRANCH=branch, CLONE_DIR=clone)
    rc = stream(["bash", bs], os.path.join(OUT, "bootstrap.log"), env=env, timeout=1800)
    if rc != 0:
        sys.exit("bootstrap failed rc=%s" % rc)


def untar_llamacpp():
    if os.path.isdir(os.path.join(LLAMACPP_PREFIX, "bin")):
        return
    tar = find_one("/kaggle/input/**/llamacpp.tar.gz")
    if tar:
        sh(["tar", "-xzf", tar, "-C", WORK], check=True)
    else:
        hit = find_one("/kaggle/input/**/llamacpp/bin/llama-server")
        if not hit:
            sys.exit("no llamacpp cache")
        sh(["cp", "-r", os.path.dirname(os.path.dirname(hit)), WORK], check=True)
    sh("chmod +x %s/bin/* || true" % LLAMACPP_PREFIX, shell=True)


def server_bin():
    s = os.path.join(LLAMACPP_PREFIX, "bin", "llama-server")
    if not os.path.isfile(s):
        c = glob.glob(os.path.join(LLAMACPP_PREFIX, "**", "llama-server"), recursive=True)
        s = c[0] if c else s
    return s


def _sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def fetch_official_gguf():
    url, size, sha = GGUF_OFFICIAL["url"], GGUF_OFFICIAL["bytes"], GGUF_OFFICIAL["sha256"]
    os.makedirs(TMP, exist_ok=True)
    dest = os.path.join(TMP, os.path.basename(url))
    if shutil.disk_usage(TMP).free < size + (1 << 30):
        sys.exit("not enough scratch disk for the GGUF")
    t = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "circuit-repro-kernel"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
        shutil.copyfileobj(r, out, 1 << 22)
    got = os.path.getsize(dest)
    digest = _sha256(dest)
    log("GGUF %d bytes in %.0fs sha256 %s" % (got, time.time() - t, digest))
    if got != size or digest != sha:
        sys.exit("GGUF size/sha256 mismatch (%d, %s)" % (got, digest))
    return dest, {"source": "download", "url": url, "bytes": got, "sha256": digest, "verified": True}


def wait_health(proc, timeout=1200):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            log("llama-server exited rc=%s during load" % proc.returncode)
            return False
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % PORT, timeout=5) as r:
                if r.status == 200:
                    log("llama-server healthy after %.1fs" % (time.time() - t0))
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def launch_server(gguf, parallel=1, ctx=16384, tag="eval"):
    """R2 flags; parallel only differs for the rationalize kernel."""
    cmd = [server_bin(), "-m", gguf, "--host", "127.0.0.1", "--port", str(PORT),
           "--n-gpu-layers", "999", "--split-mode", "layer", "-c", str(ctx),
           "--parallel", str(parallel)]
    env = dict(os.environ)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    logf = open(os.path.join(OUT, "llama-server-%s.log" % tag), "w")
    log("launching:", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, env=env)
    if not wait_health(proc):
        try:
            print(open(os.path.join(OUT, "llama-server-%s.log" % tag)).read()[-4000:], flush=True)
        except Exception:
            pass
        stop_server(proc)
        sys.exit("llama-server never became healthy")
    MAN.setdefault("server", []).append({"tag": tag, "cmd": cmd[1:]})
    return proc


def stop_server(proc):
    if proc is not None and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()


def _post(path, body, timeout=300):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path),
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def log_server_caps():
    info = {}
    for flag in ("--version", "--help"):
        try:
            r = subprocess.run([server_bin(), flag], capture_output=True, text=True, timeout=60)
            info[flag] = (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            info[flag] = "ERROR %r" % (e,)
    with open(os.path.join(OUT, "llama-server-help.txt"), "w") as fh:
        fh.write(info["--version"] + "\n\n" + info["--help"])
    return {"version": info["--version"].strip()[-300:]}


def probe_two_phase():
    """R2's 64-token probe of the CAP path; abort if phase 1 is not a Qwen3 think."""
    msgs = [{"role": "user", "content": "What is 17*23? Think step by step."}]
    prompt = _post("/apply-template", {"messages": msgs})["prompt"]
    p1 = _post("/completion", {"prompt": prompt, "n_predict": 64, "temperature": 0.7,
                               "stop": ["</think>"], "cache_prompt": True})
    t1 = p1.get("content") or ""
    p2 = _post("/completion", {"prompt": prompt + t1 + "\n</think>\n\n", "n_predict": 128,
                               "temperature": 0.7, "cache_prompt": True})
    rec = {"template_tail": prompt[-60:], "p1_head": t1[:120],
           "p1_tokens": p1.get("tokens_predicted"), "p1_stop": p1.get("stop_type"),
           "p2_head": (p2.get("content") or "")[:200], "p2_tokens": p2.get("tokens_predicted")}
    log("two-phase probe:", json.dumps(rec))
    if not (("<think>" in t1) or prompt.rstrip().endswith("<think>")):
        sys.exit("PROBE FAILED: phase-1 text has no <think> (CAP path invalid)")
    return rec


def gen_env(clone):
    env = dict(os.environ, LNA_DEPS_ROOT=clone)
    env.pop("CUDA_VISIBLE_DEVICES", None)
    for k in ("EDITCAP_FEWSHOT", "EDITCAP_NO_THINK", "EDITCAP_THINK_BUDGET",
              "EDITCAP_RECOVER_REASONING", "EDITCAP_GEN_ONLY"):
        env.pop(k, None)
    return env


def run_eval(clone, model_id, out_dir, deadline_min, hard_min):
    env = gen_env(clone)
    env.update(EDITCAP_THINK_BUDGET="1024", EDITCAP_RECOVER_REASONING="1", EDITCAP_GEN_ONLY="1")
    gen = os.path.join(clone, "kaggle", "campaigns", "pilot-v0", "P1", "p1_gen.py")
    prompts = os.path.join(clone, "kaggle", "campaigns", "pilot-v0", "P1", "prompts")
    deadline = T0 + deadline_min * 60
    inner = ("source %s && exec %s %s heldout --prompts %s --out %s --samples %d --model-id %s "
             "--llm-url http://127.0.0.1:%d/v1 --deadline-epoch %.0f --limit %d"
             % (ENV_SH, PY, gen, prompts, out_dir, CFG.get("samples", 2), model_id, PORT, deadline,
                CFG.get("prompt_limit", 0)))
    t = time.time()
    rc = stream(["bash", "-c", inner], os.path.join(OUT, "gen-%s.log" % CFG["tag"]), env=env,
                timeout=max(60, hard_min * 60 - (time.time() - T0)))
    rec = {"step": "eval", "model_id": model_id, "rc": rc, "minutes": round((time.time() - t) / 60, 1),
           "out": out_dir}
    rows = []
    rp = os.path.join(out_dir, "results.jsonl")
    if os.path.exists(rp):
        rows = [json.loads(l) for l in open(rp) if l.strip()]
    rec.update(n_completions=len(rows), n_valid=sum(1 for r in rows if r.get("valid")),
               gpu_min=round(sum((r.get("gpu_ms") or 0) for r in rows) / 60000, 2))
    MAN["runs"].append(rec)
    event("eval_done", **rec)
    return rec


# ============================================================ kinds
def main_eval(tok, clone, head):
    preflight(["gh token", "ngspice cache", "llamacpp cache"])
    bootstrap(tok, clone, CFG["repo_branch"])
    untar_llamacpp()
    MAN["server_caps"] = log_server_caps()
    gguf, prov = fetch_official_gguf()
    MAN["gguf"] = prov
    proc = launch_server(gguf, parallel=1, tag="eval")
    try:
        MAN["probe"] = probe_two_phase()
        run_eval(clone, CFG["model_id"], os.path.join(OUT, "gen"), CFG["start_deadline_min"],
                 CFG["hard_wall_min"])
    finally:
        stop_server(proc)


def main_rat(tok, clone, head):
    preflight(["gh token", "ngspice cache", "llamacpp cache"])
    bootstrap(tok, clone, CFG["repo_branch"])
    untar_llamacpp()
    MAN["server_caps"] = log_server_caps()
    gguf, prov = fetch_official_gguf()
    MAN["gguf"] = prov
    par = CFG.get("parallel", 4)
    proc = launch_server(gguf, parallel=par, ctx=4096 * par, tag="rat")
    try:
        run_rat(clone)
    finally:
        stop_server(proc)


def run_rat(clone):
    par = CFG.get("parallel", 4)
    env = gen_env(clone)
    gen = os.path.join(clone, "kaggle", "campaigns", "pilot-v0", "P1", "p1_gen.py")
    exs = os.path.join(clone, CFG["examples"])
    deadline = T0 + CFG["start_deadline_min"] * 60
    inner = ("source %s && exec %s %s rationalize --examples %s --out %s --attempts %d "
             "--parallel %d --model-id %s --llm-url http://127.0.0.1:%d/v1 --deadline-epoch %.0f"
             % (ENV_SH, PY, gen, exs, os.path.join(OUT, "rat"), CFG.get("attempts", 3), par,
                CFG["model_id"], PORT, deadline))
    t = time.time()
    rc = stream(["bash", "-c", inner], os.path.join(OUT, "rat.log"), env=env,
                timeout=max(60, CFG["hard_wall_min"] * 60 - (time.time() - T0)))
    rows = []
    rp = os.path.join(OUT, "rat", "rationalize.jsonl")
    if os.path.exists(rp):
        rows = [json.loads(l) for l in open(rp) if l.strip()]
    n_in = sum(1 for l in open(exs) if l.strip())
    rec = {"step": "rationalize", "rc": rc, "minutes": round((time.time() - t) / 60, 1),
           "n_examples": n_in, "n_calls": len(rows), "n_kept": len({r["id"] for r in rows if r.get("ok")}),
           "gpu_min_sum_requests": round(sum(((r.get("timings") or {}).get("prompt_ms") or 0)
                                             + ((r.get("timings") or {}).get("predicted_ms") or 0)
                                             for r in rows) / 60000, 2)}
    MAN["runs"].append(rec)
    event("rat_done", **rec)
    return rec


# ---------------------------------------------------------------- sft
def env_log():
    sh("nvidia-smi; free -g; nproc; df -h / /tmp /kaggle/working", shell=True,
       logfile=os.path.join(OUT, "env.log"))


def start_llamacpp_tools():
    script = r"""
set -x
cd /tmp && rm -rf llama.cpp
git clone --depth 1 --branch %s https://github.com/ggml-org/llama.cpp /tmp/llama.cpp || exit 11
cd /tmp/llama.cpp
cmake -B build -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=OFF \
      -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON || exit 12
cmake --build build --config Release --target llama-quantize -j2 || exit 13
ls -la build/bin/llama-quantize && echo QUANTIZE_OK
""" % LLAMACPP_TAG
    lf = open(os.path.join(OUT, "llamacpp-tools.log"), "w")
    return subprocess.Popen(["bash", "-c", script], stdout=lf, stderr=subprocess.STDOUT)


def install():
    """E-e install route A (torch pinned via a constraints file), B fallback."""
    os.makedirs(TMP, exist_ok=True)
    rc, tv = sh([PY, "-c", "import importlib.metadata as m\n"
                 "for p in ('torch','torchvision','torchaudio'):\n"
                 "  try: print(p+'=='+m.version(p))\n"
                 "  except Exception: pass"])
    cons = os.path.join(TMP, "constraints.txt")
    pins = [l.strip() for l in tv.splitlines() if "==" in l and l.strip().split("==")[0]
            in ("torch", "torchvision", "torchaudio")]
    open(cons, "w").write("\n".join(pins) + "\n")
    plog = os.path.join(OUT, "pip-install.log")
    rc, _ = sh([PY, "-m", "pip", "install", "-q", "-c", cons, "--only-binary=xformers"] + PINS,
               timeout=1800, logfile=plog)
    route = "A"
    if rc != 0:
        route = "B"
        sh([PY, "-m", "pip", "install", "-q", "--no-deps", PINS[0], PINS[1]], timeout=900, logfile=plog)
        sh([PY, "-m", "pip", "install", "-q", "-c", cons] + PINS[2:] + NODEPS_EXTRA,
           timeout=1800, logfile=plog)
    chk = ("import torch, transformers, peft, trl, bitsandbytes, accelerate, unsloth, unsloth_zoo\n"
           "import importlib.metadata as m, json\n"
           "v={p:m.version(p) for p in ['unsloth','unsloth_zoo','torch','transformers','peft',"
           "'trl','bitsandbytes','accelerate','datasets']}\n"
           "print('VERSIONS_JSON='+json.dumps(v))\n")
    tail = ""
    for _ in range(3):
        rc, tail = sh([PY, "-c", chk], timeout=900, logfile=plog)
        if rc == 0:
            break
        miss = re.findall(r"No module named '([A-Za-z0-9_\.]+)'", tail)
        if not miss:
            break
        sh([PY, "-m", "pip", "install", "-q", "-c", cons, miss[-1].split(".")[0].replace("_", "-")],
           timeout=900, logfile=plog)
    m = re.search(r"VERSIONS_JSON=(\{.*\})", tail)
    event("install", route=route, rc=rc, versions=json.loads(m.group(1)) if m else None)
    sh("pip freeze", shell=True, logfile=os.path.join(OUT, "pip-freeze.txt"))
    if rc != 0:
        sys.exit("training stack install failed")


def llamacpp_ready(bg, wait_min=30):
    t = time.time()
    while bg.poll() is None and time.time() - t < wait_min * 60:
        time.sleep(10)
    q = "/tmp/llama.cpp/build/bin/llama-quantize"
    return os.path.isfile("/tmp/llama.cpp/convert_hf_to_gguf.py"), (q if os.path.isfile(q) else None)


def run_convert(args, logname):
    cons = os.path.join(TMP, "constraints.txt")
    for _ in range(4):
        rc, tail = sh([PY] + args, timeout=3600, logfile=os.path.join(OUT, logname))
        if rc == 0:
            return True
        miss = re.findall(r"No module named '([A-Za-z0-9_\.]+)'", tail)
        if not miss:
            return False
        sh([PY, "-m", "pip", "install", "-q", "-c", cons, miss[-1].split(".")[0].replace("_", "-")],
           timeout=900)
    return False


def merge_to_q4(lora, bg):
    tag = CFG["tag"]
    merged = os.path.join(TMP, "merged-" + tag)
    t = time.time()
    rc, tail = sh([PY, os.path.join(HERE, "sft_merge.py"), lora, merged], timeout=3600,
                  env=dict(os.environ, CUDA_VISIBLE_DEVICES="0"),
                  logfile=os.path.join(OUT, "merge.log"))
    if rc != 0 or not glob.glob(os.path.join(merged, "*.safetensors")):
        event("merge_fail", rc=rc, tail=tail[-1500:])
        sys.exit("merge failed")
    mb = sum(os.path.getsize(f) for f in glob.glob(os.path.join(merged, "*")))
    for c in glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--*Qwen3-14B*")):
        shutil.rmtree(c, ignore_errors=True)
    ok_conv, quant = llamacpp_ready(bg)
    if not ok_conv or not quant:
        event("llamacpp_tools_missing", converter=ok_conv, quantize=quant)
        sys.exit("llama.cpp converter/quantizer missing")
    free = shutil.disk_usage(TMP).free / 1e9
    outtype = "f16" if free > mb / 1e9 * 1.15 + 5 else "q8_0"
    g1 = os.path.join(TMP, "%s-%s.gguf" % (tag, outtype))
    t2 = time.time()
    ok = run_convert(["/tmp/llama.cpp/convert_hf_to_gguf.py", merged, "--outtype", outtype,
                      "--outfile", g1], "convert.log")
    shutil.rmtree(merged, ignore_errors=True)
    if not ok or not os.path.isfile(g1):
        event("convert_fail")
        sys.exit("convert failed")
    t3 = time.time()
    g2 = os.path.join(TMP, "%s-Q4_K_M.gguf" % tag)
    rc, _ = sh([quant] + (["--allow-requantize"] if outtype == "q8_0" else [])
               + [g1, g2, "Q4_K_M", str(os.cpu_count() or 4)], timeout=3600,
               logfile=os.path.join(OUT, "quantize.log"))
    if rc != 0 or not os.path.isfile(g2):
        event("quantize_fail", rc=rc)
        sys.exit("quantize failed")
    os.remove(g1)
    rec = {"merged_bytes": mb, "merge_s": round(t2 - t, 1), "convert_outtype": outtype,
           "convert_s": round(t3 - t2, 1), "quantize_s": round(time.time() - t3, 1),
           "q4_bytes": os.path.getsize(g2), "q4_sha256": _sha256(g2)}
    event("gguf_ready", **rec)
    MAN["gguf"] = dict(rec, source="sft-merge", lora=os.path.relpath(lora, WORK))
    return g2


def main_sft(tok, clone, head):
    preflight(["gh token", "ngspice cache", "llamacpp cache"])
    os.makedirs(TMP, exist_ok=True)
    env_log()
    bg = start_llamacpp_tools()
    install()
    rows = os.path.join(clone, CFG["rows"])
    n_rows = sum(1 for l in open(rows) if l.strip())
    event("rows", path=CFG["rows"], n=n_rows, sha256=_sha256(rows))
    lora = os.path.join(OUT, "lora-" + CFG["tag"])
    deadline = T0 + CFG["train_deadline_min"] * 60
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="0", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True",
               TOKENIZERS_PARALLELISM="false")
    t = time.time()
    rc = stream([PY, os.path.join(HERE, "sft_train.py"), "--rows", rows, "--out-lora", lora,
                 "--log", os.path.join(OUT, "train.jsonl"), "--model", SFT_BASE,
                 "--deadline-epoch", "%.0f" % deadline] + CFG.get("train_args", []),
                os.path.join(OUT, "train.log"), env=env,
                timeout=max(60, (CFG["train_deadline_min"] + 20) * 60 - (time.time() - T0)))
    tr = [json.loads(l) for l in open(os.path.join(OUT, "train.jsonl")) if l.strip()] \
        if os.path.exists(os.path.join(OUT, "train.jsonl")) else []
    fin = [r for r in tr if r.get("phase") == "done"]
    event("train_done", rc=rc, minutes=round((time.time() - t) / 60, 1),
          final=fin[-1] if fin else None)
    if rc != 0 or not fin or not os.path.isfile(os.path.join(lora, "adapter_config.json")):
        sys.exit("training failed")
    gguf = merge_to_q4(lora, bg)
    bootstrap(tok, clone, CFG["repo_branch"])
    untar_llamacpp()
    MAN["server_caps"] = log_server_caps()
    proc = launch_server(gguf, parallel=1, tag="eval")
    try:
        MAN["probe"] = probe_two_phase()
        run_eval(clone, CFG["model_id"], os.path.join(OUT, "gen"), CFG["start_deadline_min"],
                 CFG["hard_wall_min"])
    finally:
        stop_server(proc)


def main(cfg, tok, clone, head):
    CFG.update(cfg)
    os.makedirs(OUT, exist_ok=True)
    MAN.update(kernel=cfg["tag"], clone_head=head, prereg="kaggle/PREREG-PILOT-V0.md (137ea060a) P1")
    rc = 0
    try:
        {"eval": main_eval, "rat": main_rat, "sft": main_sft}[cfg["kind"]](tok, clone, head)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
        event("exit", code=str(e.code))
    except Exception as e:                                           # noqa: BLE001
        import traceback
        rc = 1
        event("crash", error=repr(e)[:800], tb=traceback.format_exc()[-3000:])
    finally:
        save_manifest()
    return rc
