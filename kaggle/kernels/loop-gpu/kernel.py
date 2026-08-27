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

# RUN_MODE=campaign -> the capability arm-B ladder (campaign.py) instead of the
# single-spec smoke. Default stays the proven single-spec driver smoke.
RUN_MODE = os.environ.get("RUN_MODE", "smoke")
WALL_BUDGET_MIN = os.environ.get("WALL_BUDGET_MIN", "500")
# ARM selects the capability-v1 variant when RUN_MODE=campaign:
#   v0        ARM1 v0-repeat (byte-identical v0 arm-B; the default)
#   arch      ARM2 concentration + self-diversity
#   selflearn ARM3 arch + reflect-first overlay consult
ARM = os.environ.get("ARM", "v0")

# PDK selects the process the WHOLE ladder runs on (cross-PDK campaign, passed to
# campaign.py --pdk). Default bptm45 (the built-in 45 nm flow -- needs no PDK
# dataset). A foundry PDK (sky130/gf180mcu/ihp_sg13g2) requires its dataset
# attached: preflight checks for it and bootstrap.sh links it into LNA_PDK_ROOT.
# bptm45 arms already exist (capability-v0 armA + v1 arm2), so only the 3 foundry
# PDKs are new campaign work.
PDK = os.environ.get("PDK", "bptm45")

# per-PDK dataset marker (a file unique to each extracted layout) -- what
# preflight greps for; bootstrap.sh links the same layout into LNA_PDK_ROOT.
_PDK_MARKERS = {
    "sky130": "/kaggle/input/**/sky130/sky130_fd_pr/models/sky130.lib.min.spice",
    "gf180mcu": "/kaggle/input/**/gf180mcu/models/ngspice/sm141064.ngspice",
    "ihp_sg13g2": "/kaggle/input/**/ihp_sg13g2/libs.tech/ngspice/osdi/psp103.osdi",
}


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
           "-c", os.environ.get("LLAMA_CTX", "16384"),  # 8192 starved the reflect prompt (11.3k tok); KV @16k ~1.6 GB, fits the 2xT4
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
    # cross-PDK: a foundry PDK run needs its dataset attached (bptm45 needs none).
    # Fail in seconds if it is missing rather than mid-ladder with model errors.
    if PDK != "bptm45":
        marker = _PDK_MARKERS.get(PDK)
        if marker is None:
            sys.exit("[loop-gpu] PREFLIGHT FAILED -- unknown PDK %r "
                     "(know: bptm45, %s)" % (PDK, ", ".join(_PDK_MARKERS)))
        need["pdk:%s" % PDK] = [marker]
    missing = [k for k, pats in need.items()
               if not any(glob.glob(p, recursive=True) for p in pats)]
    if missing:
        print("[loop-gpu] /kaggle/input tree (3 levels):",
              glob.glob("/kaggle/input/*") + glob.glob("/kaggle/input/*/*")
              + glob.glob("/kaggle/input/*/*/*"), flush=True)
        sys.exit("[loop-gpu] PREFLIGHT FAILED -- missing inputs: %s "
                 "(datasets still processing? retry the push)" % ", ".join(missing))
    print("[loop-gpu] preflight OK: %d inputs present (pdk=%s)"
          % (len(need), PDK), flush=True)


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
        campaign = os.path.join(CLONE, "kaggle", "loop", "campaign.py")
        ladder = os.path.join(CLONE, "kaggle", "specs-ladder", "ladder.json")
        grammar = os.path.join(CLONE, "kaggle", "loop", "grammar.gbnf")
        model_id = os.environ.get("MODEL_ID", "qwen3-30b-a3b-instruct-2507-q4km")
        # NO --grammar-file: the netlist-only GBNF constrains the WHOLE
        # completion, which is incompatible with the netlist+rationale+deltas
        # output contract (v6 live run: prose got mangled into pseudo-device
        # lines). The tested Python parser is the authoritative validator.
        # --max-tokens 3072: v6 truncated at the old 1024 default.
        if RUN_MODE == "campaign":
            # capability arm-B ladder: campaign.py owns per-spec budgets
            # (k/edit_rounds/seeds/budget), escalation, and the variant
            # (v0/arch/selflearn); the kernel only passes the endpoint, ladder,
            # wall budget, variant, PDK, and output dir. Launch code is untouched.
            # --pdk runs the WHOLE ladder on the selected process (bptm45 default
            # is a no-op that keeps the existing campaign byte-identical).
            print("[loop-gpu] RUN_MODE=campaign variant=%s pdk=%s -> arm-B "
                  "ladder (%s)" % (ARM, PDK, ladder), flush=True)
            pdk_arg = " --pdk %s" % PDK if PDK != "bptm45" else ""
            inner = (
                "source %s && exec %s %s --arm B --variant %s%s --ladder %s "
                "--base-url http://127.0.0.1:%d/v1 --model %s "
                "--wall-budget-min %s --out %s"
                % (ENV_SH, sys.executable, campaign, ARM, pdk_arg, ladder, PORT,
                   model_id, WALL_BUDGET_MIN, os.path.join(WORK, "campaign"))
            )
        else:
            inner = (
                "source %s && exec %s %s --spec %s --base-url http://127.0.0.1:%d/v1 "
                "--model %s --k %s --budget %s --seeds %s --max-tokens %s "
                "--traj-dir %s --out-dir %s"
                % (ENV_SH, sys.executable, driver, SPEC, PORT, model_id,
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
