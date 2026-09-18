"""editcap-gpu -- Kaggle SCRIPT kernel (GPU, internet ON) for campaign
qwen-editcap-v0 (pre-registration kaggle/CAMPAIGN-QWEN-EDITCAP.md).

Models the proven loop-gpu kernel layout VERBATIM (recursive input lookups,
token-from-dataset, pre-clone to /tmp, ngspice fast-path untar, llama-server
launch, REDACTED clone-URL echo). The ONLY behavioural change vs loop-gpu: after
bootstrap it runs `kaggle/editcap_run.py --arm both` over ALL cells in the frozen
failure library (kaggle/editcap-lib/, 13 cells) -- arms B (evidence edit) and C
(blind-edit ablation) interleaved in ONE kernel run, same budgets.

The kernel CLONES origin main tip at run start (existing convention): a script
push uploads only THIS file; the driver + library + loop code come from the
clone. So the GPU leg requires a push of editcap_run.py + editcap-lib to origin
main FIRST (the pre-reg's "GPU leg clones origin => REQUIRES A PUSH" rule). See
README-LAUNCH.md for the launch checklist.

Attach as data sources: circuit-repro-ghtoken, circuit-repro-ngspice47,
circuit-repro-llamacpp-cuda, circuit-repro-gguf-qwen30, circuit-repro-pdk-gf180mcu
(the library is gf180mcu -- evidence.json pdk; sizing is threaded --pdk gf180mcu).

NOTE the server is launched WITHOUT a server-level grammar: the tested Python
parser (proposal.round_trip) is the authoritative validator; a server-level GBNF
would force the diagnosis prose into netlist shape.

Env knobs (defaults are the pre-reg values; v1 additions default OFF so the
constructed command with no new env vars is byte-identical to v0):
    EDITCAP_ARMS (unset->EDITCAP_ARM)  EDITCAP_ARM (both)  EDITCAP_K (3)
    EDITCAP_ANNOTATE (off; truthy->--annotate, arm-E structural annotation)
    EDITCAP_ROUNDS (unset->1; N->--rounds N, arm-F verify-refine)
    PDK (gf180mcu)  GGUF_GLOB (/kaggle/input/**/Qwen3-32B*.gguf)  LLAMA_CTX (16384)
"""
import glob
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request

WORK = "/kaggle/working"
CLONE = os.environ.get("CLONE_DIR", "/tmp/circuit-repro")  # NOT /kaggle/working
REPO_SLUG = "Devavavava/circuit-repro"
REPO_BRANCH = os.environ.get("REPO_BRANCH", "bench-v1-baseline")        # clones origin main tip
LLAMACPP_PREFIX = os.environ.get("LLAMACPP_PREFIX", os.path.join(WORK, "llamacpp"))
ENV_SH = os.path.join(WORK, "env-kaggle.sh")
PORT = int(os.environ.get("LLAMA_PORT", "8080"))

# editcap knobs (pre-reg): run BOTH arms over all 13 library cells, k=3 edits.
# EDITCAP_ARMS (plural, v1) is preferred and takes precedence when set; the v0
# EDITCAP_ARM (singular) remains honoured for back-compat. Both default such that
# WITH NO NEW ENV VARS the constructed command is BYTE-IDENTICAL to v0
# (--arm both, no --annotate / --rounds / --fence flags added).
EDITCAP_ARMS = os.environ.get("EDITCAP_ARMS")            # v1: "B,C" / "E" / "EF"
EDITCAP_ARM = EDITCAP_ARMS or os.environ.get("EDITCAP_ARM", "both")
EDITCAP_K = os.environ.get("EDITCAP_K", "3")
# v1 additive capabilities, OFF by default (byte-identical-to-v0 command):
#   EDITCAP_ANNOTATE truthy -> pass --annotate (arm-E structural annotation).
#   EDITCAP_ROUNDS N (>1)   -> pass --rounds N (arm-F verify-refine).
# Arm letters E/F/EF already imply these in the driver; the env vars let the
# operator layer them onto arm B without changing the arm string.
_TRUTHY = ("1", "true", "yes", "on")
EDITCAP_ANNOTATE = os.environ.get("EDITCAP_ANNOTATE", "").strip().lower() in _TRUTHY
EDITCAP_ROUNDS = os.environ.get("EDITCAP_ROUNDS", "").strip()  # "" => omit --rounds
# The failure library is gf180mcu (evidence.json pdk); sizing threads --pdk.
PDK = os.environ.get("PDK", "gf180mcu")

# per-PDK dataset marker (a file unique to each extracted layout) -- what
# preflight greps for; bootstrap.sh links the same layout into LNA_PDK_ROOT.
_PDK_MARKERS = {
    "sky130": "/kaggle/input/**/sky130/sky130_fd_pr/models/sky130.lib.min.spice",
    "gf180mcu": "/kaggle/input/**/gf180mcu/models/ngspice/sm141064.ngspice",
    "ihp_sg13g2": "/kaggle/input/**/ihp_sg13g2/libs.tech/ngspice/osdi/psp103.osdi",
}


def sh(cmd, **kw):
    # Redact credentials from the echo: kernel logs become output artifacts
    # that get archived into git, and an x-access-token clone URL printed
    # verbatim IS the GH PAT (push protection caught exactly this before).
    shown = re.sub(r"://[^@/\s]+@", "://REDACTED@", " ".join(cmd))
    print("[editcap-gpu] $", shown, flush=True)
    return subprocess.run(cmd, **kw)


def find_one(pattern, what):
    hits = sorted(glob.glob(pattern, recursive=True))
    if not hits:
        print("[editcap-gpu] /kaggle/input:", glob.glob("/kaggle/input/*")
              + glob.glob("/kaggle/input/*/*"), flush=True)
        sys.exit("[editcap-gpu] no %s matched %s (attach the dataset)"
                 % (what, pattern))
    return hits[0]


def _token():
    for p in sorted(glob.glob("/kaggle/input/**/gh_token*", recursive=True)):
        tok = open(p).read().strip()
        if tok:
            print("[editcap-gpu] GH token from", p, flush=True)
            return tok
    sys.exit("[editcap-gpu] no gh token dataset attached")


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
        sys.exit("[editcap-gpu] bootstrap failed (see /kaggle/working/report)")


def untar_llamacpp():
    if os.path.isdir(os.path.join(LLAMACPP_PREFIX, "bin")):
        print("[editcap-gpu] llamacpp already present", flush=True)
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
        sys.exit("[editcap-gpu] no llamacpp cache (tarball or extracted) found")
    root = os.path.dirname(os.path.dirname(hits[0]))
    sh(["cp", "-r", root, WORK], check=True)
    sh(["bash", "-c", "chmod +x %s/bin/* || true" % LLAMACPP_PREFIX])


def wait_health(proc, timeout=600):
    """Model load for a 17 GiB GGUF takes minutes; fail fast if the server dies."""
    url = "http://127.0.0.1:%d/health" % PORT
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            print("[editcap-gpu] llama-server EXITED rc=%s during load"
                  % proc.returncode, flush=True)
            return False
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    print("[editcap-gpu] llama-server healthy after %.1fs"
                          % (time.time() - t0), flush=True)
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def launch_server():
    gguf = find_one(os.environ.get("GGUF_GLOB", "/kaggle/input/**/Qwen3-32B*.gguf"),
                    "GGUF")
    server = os.path.join(LLAMACPP_PREFIX, "bin", "llama-server")
    if not os.path.isfile(server):
        cand = glob.glob(os.path.join(LLAMACPP_PREFIX, "**", "llama-server"),
                         recursive=True)
        server = cand[0] if cand else server
    cmd = [server, "-m", gguf, "--host", "127.0.0.1", "--port", str(PORT),
           "--n-gpu-layers", "999",
           "--split-mode", "layer",
           "-c", os.environ.get("LLAMA_CTX", "16384"),  # editcap evidence prompt is long; KV @16k fits the 2xT4
           "--parallel", "1"]
    log = open(os.path.join(WORK, "llama-server.log"), "w")
    print("[editcap-gpu] launching:", " ".join(cmd), flush=True)
    return subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)


def preflight():
    """Fail in seconds -- not after a 5-min source build -- if any input is
    missing (a prior leg raced dataset processing and burned quota on fallback)."""
    need = {
        "gh token": ["/kaggle/input/**/gh_token*"],
        # tarball OR the auto-extracted tree (Kaggle unpacks uploaded archives)
        "ngspice cache": ["/kaggle/input/**/ngspice47.tar.gz",
                          "/kaggle/input/**/ngspice47/bin/ngspice"],
        "llamacpp cache": ["/kaggle/input/**/llamacpp.tar.gz",
                           "/kaggle/input/**/llamacpp/bin/llama-server"],
        "GGUF": [os.environ.get("GGUF_GLOB", "/kaggle/input/**/Qwen3-32B*.gguf")],
    }
    # The failure library is gf180mcu: its PDK dataset must be attached.
    if PDK != "bptm45":
        marker = _PDK_MARKERS.get(PDK)
        if marker is None:
            sys.exit("[editcap-gpu] PREFLIGHT FAILED -- unknown PDK %r "
                     "(know: bptm45, %s)" % (PDK, ", ".join(_PDK_MARKERS)))
        need["pdk:%s" % PDK] = [marker]
    missing = [k for k, pats in need.items()
               if not any(glob.glob(p, recursive=True) for p in pats)]
    if missing:
        print("[editcap-gpu] /kaggle/input tree (3 levels):",
              glob.glob("/kaggle/input/*") + glob.glob("/kaggle/input/*/*")
              + glob.glob("/kaggle/input/*/*/*"), flush=True)
        sys.exit("[editcap-gpu] PREFLIGHT FAILED -- missing inputs: %s "
                 "(datasets still processing? retry the push)" % ", ".join(missing))
    print("[editcap-gpu] preflight OK: %d inputs present (pdk=%s)"
          % (len(need), PDK), flush=True)


def main():
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
            sys.exit("[editcap-gpu] llama-server never became healthy")
        editcap = os.path.join(CLONE, "kaggle", "editcap_run.py")
        lib = os.path.join(CLONE, "kaggle", os.environ.get("EDITCAP_LIB", "editcap-lib-v1a"))
        out = os.path.join(WORK, "editcap")
        model_id = os.environ.get("MODEL_ID", "qwen3-32b-q4ks")
        # NO --grammar: the netlist-only GBNF would constrain the WHOLE
        # completion (diagnosis prose + k fenced edits), which is incompatible
        # with the editcap output contract. proposal.round_trip is the validator.
        # v1 additive flags -- appended ONLY when their env vars are set, so with
        # no new env vars the command below is byte-identical to the v0 kernel's.
        extra = ""
        if EDITCAP_ANNOTATE:
            extra += " --annotate"
        if EDITCAP_ROUNDS:
            extra += " --rounds %s" % EDITCAP_ROUNDS
        if os.environ.get("EDITCAP_SCHEMA"):
            extra += " --diagnosis-first"
        print("[editcap-gpu] arm=%s k=%s pdk=%s annotate=%s rounds=%s -> editcap "
              "over library %s"
              % (EDITCAP_ARM, EDITCAP_K, PDK, EDITCAP_ANNOTATE,
                 EDITCAP_ROUNDS or "1", lib), flush=True)
        inner = (
            "source %s && exec %s %s --lib %s --out %s --arm %s --k %s "
            "--pdk %s --llm-url http://127.0.0.1:%d/v1 --model %s --max-tokens %s%s"
            % (ENV_SH, sys.executable, editcap, lib, out, EDITCAP_ARM, EDITCAP_K,
               PDK, PORT, model_id, os.environ.get("EDITCAP_MAX_TOKENS", "3072"),
               extra)
        )
        # env-kaggle.sh carries NGSPICE/SPICE_LIB_DIR/LNA_DEPS_ROOT from
        # bootstrap's own process (env set inside bootstrap.sh does not persist
        # to this one). LNA_DEPS_ROOT=CLONE -> the driver runs the clone's modules.
        rc = sh(["bash", "-c", inner],
                env=dict(os.environ, LNA_DEPS_ROOT=CLONE)).returncode
    finally:
        out = os.path.join(WORK, "editcap")
        try:
            n = len(glob.glob(os.path.join(out, "results-*.jsonl")))
            print("[editcap-gpu] editcap out has %d results-*.jsonl file(s): %s"
                  % (n, out), flush=True)
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
