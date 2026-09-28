"""rl-readiness R2 (thinking-length cap) -- Kaggle SCRIPT kernel (GPU T4, internet ON).

Pre-registration: kaggle/PREREG-RL-READINESS.md, check R2. Clone of the E-d 14B
kernel (kaggle/kernels-editcap/bench-v12-audit-ed-14b): same model (Qwen3-14B
Q4_K_M, official HF repo, sha256-verified), same llama-server flags, lib
editcap-lib-v12-45nm, pdk bptm45, arm B, k=3, temp 0.7, 8192-token cap,
EDITCAP_RECOVER_REASONING=1, EDITCAP_FEWSHOT=1 (FS only). Baseline (thinking ON)
= the existing E-d 14B-FS run; this kernel runs the two NEW conditions:

  * CAP = EDITCAP_THINK_BUDGET=1024: client-side two-phase capped think
          (/apply-template -> /completion n_predict=1024 stop '</think>'; then
          prompt+think+closer -> /completion for the answer; closer = '</think>'
          if the model closed naturally, else Qwen's documented early-exit
          sentence + '</think>'). See editcap_run._LiveLLM._complete_think_budget.
  * NT  = EDITCAP_NO_THINK=1: Qwen3 soft switch, '\n/no_think' appended to the
          user turn (pre-reg wording "thinking off (/no_think)").

Both with EDITCAP_GEN_ONLY=1: no in-kernel smoke/size/escalate (E-d's in-kernel
sizing was RECORDED ONLY and cost ~1.3 GPU-session-min/cell); every valid edit is
scored locally at seeds 1,2,3 x 2500 bptm45 exactly like E-d.
2 samples/cell: the identical command runs once per sample into
/kaggle/working/editcap/<COND>-s<N>/ (no seed sent -> fresh random draw).

Before the runs the kernel logs `llama-server --version` and the reasoning /
think / budget lines of `llama-server --help` (native budget support is LOGGED,
not used), and runs a 64-token two-phase probe that aborts the kernel (cheaply)
if the /completion think text is not rendered the way the CAP path assumes.
HARD wall budget: user-approved <= 1.5 GPU-h; no run starts past START_DEADLINE_MIN
and a running driver is killed at HARD_WALL_MIN.
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

# ============================ CONFIG ==========================================
KERNEL_TAG = "r2-think"
MODEL_ID = "qwen3-14b-q4km"
# (condition, sample) in execution order -- interleaved so a truncated run still
# leaves matched CAP/NT for sample 1.
RUNS = [("CAP", 1), ("NT", 1), ("CAP", 2), ("NT", 2)]
THINK_BUDGET = "1024"
GGUF_GLOB = None
# Official Qwen repo (open, not gated) -- identical to the E-d 14B kernel.
GGUF_DOWNLOAD = {
    "url": "https://huggingface.co/Qwen/Qwen3-14B-GGUF/resolve/main/Qwen3-14B-Q4_K_M.gguf",
    "bytes": 9001752960,
    "sha256": "500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0",
}
START_DEADLINE_MIN = 70.0   # do not START a run past this wall minute
HARD_WALL_MIN = 82.0        # kill a running driver at this wall minute
# ============================================================================

REPO_SLUG = "Devavavava/circuit-repro"
REPO_BRANCH = "worktree-externals-gf180"
REPO_SHA = "b5b90e01ddfb05c429218867dc81354beffcb950"   # commit carrying the R2 editcap_run.py flags
EDITCAP_LIB = "editcap-lib-v12-45nm"
PDK = "bptm45"
ARM = "B"
K = "3"
MAX_TOKENS = "8192"
TEMPERATURE = "0.7"
SCRATCH_DIRS = ("/kaggle/tmp", "/tmp")   # GGUF download target (never /kaggle/working)

WORK = "/kaggle/working"
CLONE = "/tmp/circuit-repro"            # NOT /kaggle/working (must not be output)
LLAMACPP_PREFIX = os.path.join(WORK, "llamacpp")
ENV_SH = os.path.join(WORK, "env-kaggle.sh")
OUT_ROOT = os.path.join(WORK, "editcap")
PORT = 8080
T0 = time.time()
TAG = "[%s]" % KERNEL_TAG


def log(*a):
    print(TAG, "%6.1fm" % ((time.time() - T0) / 60), *a, flush=True)


def sh(cmd, **kw):
    # Redact credentials: kernel logs are archived; a token clone URL IS the PAT.
    shown = re.sub(r"://[^@/\s]+@", "://REDACTED@", " ".join(cmd))
    log("$", shown)
    return subprocess.run(cmd, **kw)


def find_one(pattern, what):
    hits = sorted(glob.glob(pattern, recursive=True))
    if not hits:
        log("/kaggle/input:", glob.glob("/kaggle/input/*") + glob.glob("/kaggle/input/*/*"))
        sys.exit("%s no %s matched %s (attach the dataset)" % (TAG, what, pattern))
    return hits[0]


def _token():
    for p in sorted(glob.glob("/kaggle/input/**/gh_token*", recursive=True)):
        tok = open(p).read().strip()
        if tok:
            log("GH token from", p)
            return tok
    sys.exit("%s no gh token dataset attached" % TAG)


def preflight():
    """Fail in seconds if any attached input is missing."""
    need = {
        "gh token": ["/kaggle/input/**/gh_token*"],
        "ngspice cache": ["/kaggle/input/**/ngspice47.tar.gz",
                          "/kaggle/input/**/ngspice47/bin/ngspice"],
        "llamacpp cache": ["/kaggle/input/**/llamacpp.tar.gz",
                           "/kaggle/input/**/llamacpp/bin/llama-server"],
    }
    if GGUF_DOWNLOAD is None:
        need["GGUF"] = [GGUF_GLOB]
    missing = [k for k, pats in need.items()
               if not any(glob.glob(p, recursive=True) for p in pats)]
    if missing:
        log("/kaggle/input tree:", glob.glob("/kaggle/input/*")
            + glob.glob("/kaggle/input/*/*") + glob.glob("/kaggle/input/*/*/*"))
        sys.exit("%s PREFLIGHT FAILED -- missing inputs: %s" % (TAG, ", ".join(missing)))
    log("preflight OK: %s (pdk=%s)" % (sorted(need), PDK))


def clone_pinned():
    tok = _token()
    url = "https://x-access-token:%s@github.com/%s.git" % (tok, REPO_SLUG)
    if not os.path.isdir(os.path.join(CLONE, ".git")):
        sh(["git", "clone", "--depth", "1", "--branch", REPO_BRANCH, url, CLONE], check=True)
    head = subprocess.run(["git", "-C", CLONE, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    if head != REPO_SHA:
        log("branch tip %s != pinned %s -> fetching pinned sha" % (head, REPO_SHA))
        sh(["git", "-C", CLONE, "fetch", "--depth", "1", "origin", REPO_SHA], check=True)
        sh(["git", "-C", CLONE, "checkout", "--detach", "FETCH_HEAD"], check=True)
        head = subprocess.run(["git", "-C", CLONE, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    if head != REPO_SHA:
        sys.exit("%s clone HEAD %s != pinned REPO_SHA %s" % (TAG, head, REPO_SHA))
    log("clone pinned at", head)
    return tok, head


def bootstrap(tok):
    bs = os.path.join(CLONE, "kaggle", "bootstrap.sh")
    env = dict(os.environ, WITH_PANDAS="1", GH_READ_TOKEN=tok,
               REPO_SLUG=REPO_SLUG, REPO_BRANCH=REPO_BRANCH, CLONE_DIR=CLONE)
    if sh(["bash", bs], env=env).returncode != 0:
        sys.exit("%s bootstrap failed (see /kaggle/working/report)" % TAG)


def untar_llamacpp():
    if os.path.isdir(os.path.join(LLAMACPP_PREFIX, "bin")):
        log("llamacpp already present")
        return
    tars = sorted(glob.glob("/kaggle/input/**/llamacpp.tar.gz", recursive=True))
    if tars:
        sh(["tar", "-xzf", tars[0], "-C", WORK], check=True)
        return
    hits = sorted(glob.glob("/kaggle/input/**/llamacpp/bin/llama-server", recursive=True))
    if not hits:
        sys.exit("%s no llamacpp cache (tarball or extracted) found" % TAG)
    root = os.path.dirname(os.path.dirname(hits[0]))
    sh(["cp", "-r", root, WORK], check=True)
    sh(["bash", "-c", "chmod +x %s/bin/* || true" % LLAMACPP_PREFIX])


def _sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def fetch_gguf():
    """Return (gguf_path, provenance dict). Downloaded weights go to a scratch
    dir OUTSIDE /kaggle/working so they never become kernel output."""
    if GGUF_DOWNLOAD is None:
        p = find_one(GGUF_GLOB, "GGUF")
        return p, {"source": "dataset", "glob": GGUF_GLOB, "path": p,
                   "bytes": os.path.getsize(p)}
    url, size, sha = GGUF_DOWNLOAD["url"], GGUF_DOWNLOAD["bytes"], GGUF_DOWNLOAD["sha256"]
    cands = [d for d in SCRATCH_DIRS if os.path.isdir(d)]
    free = {d: shutil.disk_usage(d).free for d in cands}
    log("scratch free bytes:", free)
    dest_dir = max(cands, key=lambda d: free[d])
    if free[dest_dir] < size + (1 << 30):
        sys.exit("%s not enough scratch disk for GGUF (%d free, need %d)"
                 % (TAG, free[dest_dir], size))
    dest = os.path.join(dest_dir, os.path.basename(url))
    t = time.time()
    log("GET", url, "->", dest)
    req = urllib.request.Request(url, headers={"User-Agent": "circuit-repro-kernel"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as out:
        shutil.copyfileobj(r, out, 1 << 22)
    got = os.path.getsize(dest)
    log("downloaded %d bytes in %.1fs" % (got, time.time() - t))
    if got != size:
        sys.exit("%s GGUF size mismatch: got %d expected %d" % (TAG, got, size))
    digest = _sha256(dest)
    log("sha256", digest)
    if digest != sha:
        sys.exit("%s GGUF sha256 mismatch: got %s expected %s" % (TAG, digest, sha))
    return dest, {"source": "download", "url": url, "path": dest, "bytes": got,
                  "sha256": digest, "verified": True}


def wait_health(proc, timeout=900):
    url = "http://127.0.0.1:%d/health" % PORT
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            log("llama-server EXITED rc=%s during load" % proc.returncode)
            return False
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    log("llama-server healthy after %.1fs" % (time.time() - t0))
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def launch_server(gguf):
    server = os.path.join(LLAMACPP_PREFIX, "bin", "llama-server")
    if not os.path.isfile(server):
        cand = glob.glob(os.path.join(LLAMACPP_PREFIX, "**", "llama-server"), recursive=True)
        server = cand[0] if cand else server
    # NO server-level grammar and NO --seed: default seed -1 => a fresh random
    # seed per request, so repeated samples are independent draws.
    cmd = [server, "-m", gguf, "--host", "127.0.0.1", "--port", str(PORT),
           "--n-gpu-layers", "999", "--split-mode", "layer",
           "-c", "16384", "--parallel", "1"]
    logf = open(os.path.join(WORK, "llama-server.log"), "w")
    log("launching:", " ".join(cmd))
    return subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)


def run_dir(cond, sample):
    return os.path.join(OUT_ROOT, "%s-s%d" % (cond, sample))


def build_inner(cond, sample, clone=CLONE, env_sh=ENV_SH, python=None, extra=""):
    """The exact editcap_run.py command for one (condition, sample) run."""
    editcap = os.path.join(clone, "kaggle", "editcap_run.py")
    lib = os.path.join(clone, "kaggle", EDITCAP_LIB)
    return ("source %s && exec %s %s --lib %s --out %s --arm %s --k %s --pdk %s "
            "--llm-url http://127.0.0.1:%d/v1 --model %s --max-tokens %s "
            "--temperature %s%s"
            % (env_sh, python or sys.executable, editcap, lib, run_dir(cond, sample),
               ARM, K, PDK, PORT, MODEL_ID, MAX_TOKENS, TEMPERATURE, extra))


def run_env(cond, clone=CLONE):
    env = dict(os.environ, LNA_DEPS_ROOT=clone, EDITCAP_RECOVER_REASONING="1",
               EDITCAP_FEWSHOT="1", EDITCAP_GEN_ONLY="1")
    env.pop("EDITCAP_THINK_BUDGET", None)
    env.pop("EDITCAP_NO_THINK", None)
    if cond == "CAP":
        env["EDITCAP_THINK_BUDGET"] = THINK_BUDGET
    elif cond == "NT":
        env["EDITCAP_NO_THINK"] = "1"
    else:
        raise ValueError(cond)
    return env


def _post(path, body, timeout=300):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path),
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def log_server_caps(server):
    """Record the bundled build's version + reasoning-related flags (logged only)."""
    info = {}
    for flag in ("--version", "--help"):
        try:
            r = subprocess.run([server, flag], capture_output=True, text=True, timeout=60)
            info[flag] = (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            info[flag] = "ERROR %r" % (e,)
    with open(os.path.join(WORK, "llama-server-help.txt"), "w") as fh:
        fh.write(info["--version"] + "\n\n" + info["--help"])
    log("llama-server --version:", info["--version"].strip()[-300:])
    hits = [ln for ln in info["--help"].splitlines()
            if re.search(r"reason|think|budget", ln, re.I)]
    log("llama-server --help reasoning/think/budget lines (%d):" % len(hits))
    for ln in hits:
        log("   ", ln)
    return {"version": info["--version"].strip()[-300:], "help_reasoning_lines": hits}


def probe_two_phase():
    """64-token two-phase probe of the CAP path. Aborts if phase 1 does not look
    like a Qwen3 think (no '<think>' in template tail or generated text)."""
    msgs = [{"role": "user", "content": "What is 17*23? Think step by step."}]
    prompt = _post("/apply-template", {"messages": msgs})["prompt"]
    p1 = _post("/completion", {"prompt": prompt, "n_predict": 64, "temperature": 0.7,
                               "stop": ["</think>"], "cache_prompt": True})
    t1 = p1.get("content") or ""
    p2 = _post("/completion", {"prompt": prompt + t1 + "\n</think>\n\n", "n_predict": 128,
                               "temperature": 0.7, "cache_prompt": True})
    rec = {"template_tail": prompt[-60:], "p1_head": t1[:120],
           "p1_tokens": p1.get("tokens_predicted"),
           "p1_stop": p1.get("stop_type"), "p2_head": (p2.get("content") or "")[:200],
           "p2_tokens": p2.get("tokens_predicted"), "p2_stop": p2.get("stop_type"),
           "p1_keys": sorted(p1.keys())}
    log("two-phase probe:", json.dumps(rec))
    ok = ("<think>" in t1) or prompt.rstrip().endswith("<think>")
    if not ok:
        sys.exit("%s PROBE FAILED: phase-1 text has no <think> (CAP path invalid)" % TAG)
    return rec


def _rows(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except Exception:
        return []


def summarize(manifest):
    for r in manifest["runs"]:
        rows = _rows(os.path.join(run_dir(r["cond"], r["sample"]), "results-B.jsonl"))
        r["n_cells_done"] = len(rows)
        r["n_proposed"] = sum(x.get("n_edits_proposed", 0) for x in rows)
        r["n_valid"] = sum(x.get("n_edits_valid", 0) for x in rows)
        r["n_inkernel_feasible_cells"] = sum(1 for x in rows if x.get("feasible"))
        log("run %s-s%d: rc=%s cells=%d proposed=%d valid=%d inkernel_feasible=%d"
            % (r["cond"], r["sample"], r.get("rc"), r["n_cells_done"], r["n_proposed"],
               r["n_valid"], r["n_inkernel_feasible_cells"]))
    # sanity: s1 vs s2 raw outputs must differ (independent draws)
    for cond in sorted({c for c, _ in RUNS}):
        a, b = run_dir(cond, 1), run_dir(cond, 2)
        same = total = 0
        for p in glob.glob(os.path.join(a, "adjudication", "*", ARM, "raw_output.txt")):
            q = p.replace(a, b, 1)
            if os.path.isfile(q):
                total += 1
                same += open(p, "rb").read() == open(q, "rb").read()
        manifest.setdefault("identical_raw_s1_s2", {})[cond] = [same, total]
        log("cond %s: identical s1/s2 raw outputs %d/%d" % (cond, same, total))


def main():
    manifest = {"kernel": KERNEL_TAG, "prereg": "kaggle/PREREG-RL-READINESS.md#R2",
                "model_id": MODEL_ID, "lib": EDITCAP_LIB, "pdk": PDK, "arm": ARM,
                "k": K, "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
                "fewshot": True, "gen_only": True, "think_budget": THINK_BUDGET,
                "recover_reasoning": True, "repo_branch": REPO_BRANCH,
                "repo_sha_pinned": REPO_SHA, "runs": []}
    os.makedirs(OUT_ROOT, exist_ok=True)
    proc = None
    rc = 0
    try:
        preflight()
        tok, head = clone_pinned()
        manifest["clone_head"] = head
        bootstrap(tok)
        untar_llamacpp()
        server = os.path.join(LLAMACPP_PREFIX, "bin", "llama-server")
        manifest["server_caps"] = log_server_caps(server)
        gguf, prov = fetch_gguf()
        manifest["gguf"] = prov
        proc = launch_server(gguf)
        if not wait_health(proc):
            try:
                print(open(os.path.join(WORK, "llama-server.log")).read()[-4000:], flush=True)
            except Exception:
                pass
            sys.exit("%s llama-server never became healthy" % TAG)
        manifest["probe"] = probe_two_phase()
        for cond, sample in RUNS:
            rec = {"cond": cond, "sample": sample, "out": run_dir(cond, sample)}
            manifest["runs"].append(rec)
            wall = (time.time() - T0) / 60
            if wall > START_DEADLINE_MIN:
                rec["skipped"] = "start deadline %.0f min (wall %.1f)" % (START_DEADLINE_MIN, wall)
                log("SKIP %s-s%d: past start deadline" % (cond, sample))
                continue
            inner = build_inner(cond, sample)
            log("RUN %s-s%d" % (cond, sample))
            t = time.time()
            try:
                rec["rc"] = sh(["bash", "-c", inner], env=run_env(cond),
                               timeout=max(60, HARD_WALL_MIN * 60 - (time.time() - T0))
                               ).returncode
            except subprocess.TimeoutExpired:
                rec["rc"] = "killed_at_hard_wall"
                log("KILLED %s-s%d at hard wall %.0f min" % (cond, sample, HARD_WALL_MIN))
            rec["minutes"] = round((time.time() - t) / 60, 1)
            if isinstance(rec["rc"], int):
                rc = rc or rec["rc"]
            with open(os.path.join(OUT_ROOT, "KERNEL-MANIFEST.json"), "w") as fh:
                json.dump(manifest, fh, indent=2)
    finally:
        try:
            summarize(manifest)
        except Exception as e:
            log("summarize failed: %r" % (e,))
        manifest["wall_minutes"] = round((time.time() - T0) / 60, 1)
        try:
            with open(os.path.join(OUT_ROOT, "KERNEL-MANIFEST.json"), "w") as fh:
                json.dump(manifest, fh, indent=2)
        except Exception:
            pass
        if proc is not None and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except Exception:
                proc.kill()
    sys.exit(rc)


if __name__ == "__main__":
    main()
