"""loop-gpu -- Kaggle SCRIPT kernel (GPU t4x2, internet ON).

Runs the reasoning loop on pre-validated code only (all setup/debug happens on CPU
sessions first -- see kaggle/PLAYBOOK.md). Steps:

  1. fast-path bootstrap: untar the cached ngspice tree, clone the repo, export env
     (via kaggle/bootstrap.sh -- which untars the attached ngspice47.tar.gz instead
     of building);
  2. untar the cached llamacpp CUDA build (attached dataset);
  3. launch llama-server with the attached GGUF: --n-gpu-layers 999 (all layers),
     split across 2xT4 (--split-mode layer / --tensor-split), --grammar-file the
     proposal GBNF (constrained decode). Wait for GET /health == 200;
  4. invoke kaggle/loop/driver.py --spec <SPEC> with bounded budgets;
  5. ALWAYS flush /kaggle/working/trajectory/ so the session's rows survive as
     kernel outputs even if the loop or the server dies.

Attach as datasets: the ngspice cache, the llamacpp cache, and the weights
dataset (GGUF + project checkpoints). Set GH_READ_TOKEN as a secret.

Env you set on the kernel:
    SPEC              spec name (default wifi24)
    GGUF_GLOB         glob for the GGUF (default /kaggle/input/*/*.gguf, first match)
    LOOP_K, LOOP_BUDGET, LOOP_SEEDS   bounded loop knobs
"""
import glob
import os
import signal
import subprocess
import sys
import time
import urllib.request

WORK = "/kaggle/working"
CLONE = os.environ.get("CLONE_DIR", os.path.join(WORK, "circuit-repro"))
LLAMACPP_PREFIX = os.environ.get("LLAMACPP_PREFIX", os.path.join(WORK, "llamacpp"))
TRAJ = os.path.join(WORK, "trajectory")
SPEC = os.environ.get("SPEC", "wifi24")
PORT = int(os.environ.get("LLAMA_PORT", "8080"))

LOOP_K = os.environ.get("LOOP_K", "3")
LOOP_BUDGET = os.environ.get("LOOP_BUDGET", "200")
LOOP_SEEDS = os.environ.get("LOOP_SEEDS", "2")


def sh(cmd, **kw):
    print("[loop-gpu] $", " ".join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def find_one(pattern, what):
    hits = sorted(glob.glob(pattern))
    if not hits:
        sys.exit("[loop-gpu] no %s matched %s (attach the dataset)" % (what, pattern))
    return hits[0]


def bootstrap():
    """Fast-path setup via bootstrap.sh (untars cached ngspice, clones, env)."""
    bs = None
    for cand in ("/kaggle/working/bootstrap.sh",
                 "/kaggle/input/circuit-repro-kaggle/bootstrap.sh",
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bootstrap.sh")):
        if os.path.exists(cand):
            bs = os.path.abspath(cand)
            break
    if bs is None:
        sys.exit("[loop-gpu] bootstrap.sh not found (attach kaggle/ or the repo)")
    # WITH_PANDAS=1 so the proposal round-trip works; torch stays off.
    env = dict(os.environ, WITH_PANDAS="1")
    if sh(["bash", bs], env=env).returncode != 0:
        sys.exit("[loop-gpu] bootstrap failed (see /kaggle/working/report)")


def untar_llamacpp():
    if os.path.isdir(os.path.join(LLAMACPP_PREFIX, "bin")):
        print("[loop-gpu] llamacpp already present", flush=True)
        return
    tar = find_one("/kaggle/input/*/llamacpp.tar.gz", "llamacpp cache")
    sh(["tar", "-xzf", tar, "-C", WORK], check=True)


def wait_health(timeout=180):
    url = "http://127.0.0.1:%d/health" % PORT
    t0 = time.time()
    while time.time() - t0 < timeout:
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
    gguf = find_one(os.environ.get("GGUF_GLOB", "/kaggle/input/*/*.gguf"), "GGUF")
    grammar = os.path.join(CLONE, "kaggle", "loop", "grammar.gbnf")
    server = os.path.join(LLAMACPP_PREFIX, "bin", "llama-server")
    if not os.path.isfile(server):
        # some builds ship it under lib/ or the build tree
        cand = glob.glob(os.path.join(LLAMACPP_PREFIX, "**", "llama-server"),
                         recursive=True)
        server = cand[0] if cand else server
    cmd = [server, "-m", gguf, "--host", "127.0.0.1", "--port", str(PORT),
           "--n-gpu-layers", "999",           # offload all layers
           "--split-mode", "layer",           # split across the 2 T4s
           "--tensor-split", "1,1",
           "-c", os.environ.get("LLAMA_CTX", "8192"),
           "--parallel", "1"]
    # --grammar-file constrains decode to the proposal netlist shape; NOTE the
    # OpenAI /v1 route also accepts a per-request "grammar" (driver.py --grammar-file),
    # so this server-level flag is belt-and-suspenders and may be dropped if a tag
    # rejects it.
    if os.path.exists(grammar):
        cmd += ["--grammar-file", grammar]
    log = open(os.path.join(WORK, "llama-server.log"), "w")
    print("[loop-gpu] launching:", " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    return proc


def flush_trajectory():
    os.makedirs(TRAJ, exist_ok=True)
    n = len(glob.glob(os.path.join(TRAJ, "*.jsonl")))
    print("[loop-gpu] trajectory dir has %d jsonl file(s): %s" % (n, TRAJ), flush=True)


def main():
    os.makedirs(TRAJ, exist_ok=True)
    proc = None
    rc = 1
    try:
        bootstrap()
        untar_llamacpp()
        proc = launch_server()
        if not wait_health():
            sys.exit("[loop-gpu] llama-server never became healthy "
                     "(see /kaggle/working/llama-server.log)")
        driver = os.path.join(CLONE, "kaggle", "loop", "driver.py")
        cmd = [sys.executable, driver, "--spec", SPEC,
               "--base-url", "http://127.0.0.1:%d/v1" % PORT,
               "--model", os.environ.get("MODEL_ID", "local"),
               "--k", LOOP_K, "--budget", LOOP_BUDGET, "--seeds", LOOP_SEEDS,
               "--traj-dir", TRAJ, "--out-dir", os.path.join(WORK, "designs")]
        # per-request grammar too, so constrained decode holds even if the server
        # flag was dropped:
        grammar = os.path.join(CLONE, "kaggle", "loop", "grammar.gbnf")
        if os.path.exists(grammar):
            cmd += ["--grammar-file", grammar]
        rc = sh(cmd, env=dict(os.environ, LNA_DEPS_ROOT=CLONE)).returncode
    finally:
        flush_trajectory()                    # rows survive no matter what
        if proc is not None and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except Exception:
                proc.kill()
    sys.exit(rc)


if __name__ == "__main__":
    main()
