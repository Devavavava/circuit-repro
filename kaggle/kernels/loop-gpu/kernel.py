"""loop-gpu -- Kaggle SCRIPT kernel (GPU, internet ON).

Runs the reasoning loop on pre-validated code only (all setup/debug happens on
CPU sessions first -- kaggle/PLAYBOOK.md). Applies every launch behavior proven
on setup-cpu/build-llamacpp (2026-08-26): recursive input lookups (mount layout
varies by image generation), token-from-dataset, pre-clone to /tmp (a script
push uploads only this file; /kaggle/working becomes output), bootstrap fast
path (untars the attached ngspice cache instead of building), driver env
sourced from bootstrap's own env-kaggle.sh.

Attach as data sources: circuit-repro-ghtoken, circuit-repro-ngspice47,
circuit-repro-llamacpp-cuda, circuit-repro-gguf-qwen30.

NOTE the server is launched WITHOUT a server-level grammar: driver.py sends the
GBNF per-request on propose/edit calls only -- a server-level --grammar-file
would force diagnose responses into netlist shape.

Env knobs (defaults are the bounded first-smoke values):
    SPEC (wifi24)  LOOP_K (2)  LOOP_BUDGET (150)  LOOP_SEEDS (1)
    GGUF_GLOB (/kaggle/input/**/Qwen3-30B*.gguf)  LLAMA_CTX (8192)
"""
import glob
import os
import signal
import subprocess
import sys
import time
import urllib.request

WORK = "/kaggle/working"
CLONE = os.environ.get("CLONE_DIR", "/tmp/circuit-repro")  # NOT /kaggle/working
REPO_SLUG = "Devavavava/circuit-repro"
REPO_BRANCH = "main"
LLAMACPP_PREFIX = os.environ.get("LLAMACPP_PREFIX", os.path.join(WORK, "llamacpp"))
ENV_SH = os.path.join(WORK, "env-kaggle.sh")
TRAJ = os.path.join(WORK, "trajectory")
SPEC = os.environ.get("SPEC", "wifi24")
PORT = int(os.environ.get("LLAMA_PORT", "8080"))

LOOP_K = os.environ.get("LOOP_K", "2")
LOOP_BUDGET = os.environ.get("LOOP_BUDGET", "150")
LOOP_SEEDS = os.environ.get("LOOP_SEEDS", "1")


def sh(cmd, **kw):
    print("[loop-gpu] $", " ".join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def find_one(pattern, what):
    hits = sorted(glob.glob(pattern, recursive=True))
    if not hits:
        print("[loop-gpu] /kaggle/input:", glob.glob("/kaggle/input/*")
              + glob.glob("/kaggle/input/*/*"), flush=True)
        sys.exit("[loop-gpu] no %s matched %s (attach the dataset)" % (what, pattern))
    return hits[0]


def _token():
    for p in sorted(glob.glob("/kaggle/input/**/gh_token*", recursive=True)):
        tok = open(p).read().strip()
        if tok:
            print("[loop-gpu] GH token from", p, flush=True)
            return tok
    sys.exit("[loop-gpu] no gh token dataset attached")


def bootstrap():
    """Pre-clone (script push uploads only this file), then bootstrap fast path."""
    tok = _token()
    if not os.path.isdir(os.path.join(CLONE, ".git")):
        url = "https://x-access-token:%s@github.com/%s.git" % (tok, REPO_SLUG)
        sh(["git", "clone", "--depth", "1", "--branch", REPO_BRANCH, url, CLONE],
           check=True)
    bs = os.path.join(CLONE, "kaggle", "bootstrap.sh")
    env = dict(os.environ, WITH_PANDAS="1", GH_READ_TOKEN=tok,
               REPO_SLUG=REPO_SLUG, REPO_BRANCH=REPO_BRANCH, CLONE_DIR=CLONE)
    if sh(["bash", bs], env=env).returncode != 0:
        sys.exit("[loop-gpu] bootstrap failed (see /kaggle/working/report)")


def untar_llamacpp():
    if os.path.isdir(os.path.join(LLAMACPP_PREFIX, "bin")):
        print("[loop-gpu] llamacpp already present", flush=True)
        return
    tars = sorted(glob.glob("/kaggle/input/**/llamacpp.tar.gz", recursive=True))
    if tars:
        sh(["tar", "-xzf", tars[0], "-C", WORK], check=True)
        return
    # Kaggle auto-extracts uploaded archives (nested under an archive-named
    # dir, execute bits stripped): copy the extracted tree and restore +x.
    hits = sorted(glob.glob("/kaggle/input/**/llamacpp/bin/llama-server",
                            recursive=True))
    if not hits:
        sys.exit("[loop-gpu] no llamacpp cache (tarball or extracted) found")
    root = os.path.dirname(os.path.dirname(hits[0]))
    sh(["cp", "-r", root, WORK], check=True)
    sh(["bash", "-c", "chmod +x %s/bin/* || true" % LLAMACPP_PREFIX])


def wait_health(proc, timeout=600):
    """Model load for a 17 GiB GGUF takes minutes; fail fast if the server dies."""
    url = "http://127.0.0.1:%d/health" % PORT
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            print("[loop-gpu] llama-server EXITED rc=%s during load" % proc.returncode,
                  flush=True)
            return False
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    print("[loop-gpu] llama-server healthy after %.1fs"
                          % (time.time() - t0), flush=True)
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def launch_server():
    gguf = find_one(os.environ.get("GGUF_GLOB", "/kaggle/input/**/Qwen3-30B*.gguf"),
                    "GGUF")
    server = os.path.join(LLAMACPP_PREFIX, "bin", "llama-server")
    if not os.path.isfile(server):
        cand = glob.glob(os.path.join(LLAMACPP_PREFIX, "**", "llama-server"),
                         recursive=True)
        server = cand[0] if cand else server
    cmd = [server, "-m", gguf, "--host", "127.0.0.1", "--port", str(PORT),
           "--n-gpu-layers", "999",
           "--split-mode", "layer",
           "-c", os.environ.get("LLAMA_CTX", "8192"),
           "--parallel", "1"]
    log = open(os.path.join(WORK, "llama-server.log"), "w")
    print("[loop-gpu] launching:", " ".join(cmd), flush=True)
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)


def flush_trajectory():
    os.makedirs(TRAJ, exist_ok=True)
    n = len(glob.glob(os.path.join(TRAJ, "*.jsonl")))
    print("[loop-gpu] trajectory dir has %d jsonl file(s): %s" % (n, TRAJ), flush=True)


def preflight():
    """Fail in seconds -- not after a 5-min source build -- if any input is
    missing (v1 raced dataset processing and burned quota on the fallback)."""
    need = {
        "gh token": ["/kaggle/input/**/gh_token*"],
        # tarball OR the auto-extracted tree (Kaggle unpacks uploaded archives)
        "ngspice cache": ["/kaggle/input/**/ngspice47.tar.gz",
                          "/kaggle/input/**/ngspice47/bin/ngspice"],
        "llamacpp cache": ["/kaggle/input/**/llamacpp.tar.gz",
                           "/kaggle/input/**/llamacpp/bin/llama-server"],
        "GGUF": [os.environ.get("GGUF_GLOB", "/kaggle/input/**/Qwen3-30B*.gguf")],
    }
    missing = [k for k, pats in need.items()
               if not any(glob.glob(p, recursive=True) for p in pats)]
    if missing:
        print("[loop-gpu] /kaggle/input tree (3 levels):",
              glob.glob("/kaggle/input/*") + glob.glob("/kaggle/input/*/*")
              + glob.glob("/kaggle/input/*/*/*"), flush=True)
        sys.exit("[loop-gpu] PREFLIGHT FAILED -- missing inputs: %s "
                 "(datasets still processing? retry the push)" % ", ".join(missing))
    print("[loop-gpu] preflight OK: all four inputs present", flush=True)


def main():
    os.makedirs(TRAJ, exist_ok=True)
    proc = None
    rc = 1
    try:
        preflight()
        bootstrap()
        untar_llamacpp()
        proc = launch_server()
        if not wait_health(proc):
            try:
                print(open(os.path.join(WORK, "llama-server.log")).read()[-4000:],
                      flush=True)
            except Exception:
                pass
            sys.exit("[loop-gpu] llama-server never became healthy")
        driver = os.path.join(CLONE, "kaggle", "loop", "driver.py")
        grammar = os.path.join(CLONE, "kaggle", "loop", "grammar.gbnf")
        # NO --grammar-file: the netlist-only GBNF constrains the WHOLE
        # completion, which is incompatible with the netlist+rationale+deltas
        # output contract (v6 live run: prose got mangled into pseudo-device
        # lines). The tested Python parser is the authoritative validator.
        # --max-tokens 3072: v6 truncated at the old 1024 default.
        inner = (
            "source %s && exec %s %s --spec %s --base-url http://127.0.0.1:%d/v1 "
            "--model %s --k %s --budget %s --seeds %s --max-tokens %s "
            "--traj-dir %s --out-dir %s"
            % (ENV_SH, sys.executable, driver, SPEC, PORT,
               os.environ.get("MODEL_ID", "qwen3-30b-a3b-instruct-2507-q4km"),
               LOOP_K, LOOP_BUDGET, LOOP_SEEDS,
               os.environ.get("LOOP_MAX_TOKENS", "3072"), TRAJ,
               os.path.join(WORK, "designs"))
        )
        # env-kaggle.sh carries NGSPICE/SPICE_LIB_DIR/LNA_DEPS_ROOT from bootstrap's
        # own process (env set inside bootstrap.sh does not persist to this one).
        rc = sh(["bash", "-c", inner],
                env=dict(os.environ, LNA_DEPS_ROOT=CLONE)).returncode
    finally:
        flush_trajectory()
        if proc is not None and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except Exception:
                proc.kill()
    sys.exit(rc)


if __name__ == "__main__":
    main()
