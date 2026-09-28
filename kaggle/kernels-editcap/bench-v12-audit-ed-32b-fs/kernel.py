"""bench-v12-audit E-d -- Kaggle SCRIPT kernel (GPU 2xT4, internet ON).

Pre-registration: kaggle/PREREG-BENCH-V12-AUDIT.md, experiment E-d (real Qwen
baseline, matched zero-shot vs few-shot). Same kernel pattern as
kaggle/kernels-editcap/editcap-v12-fewshot (preflight -> clone -> bootstrap ->
untar llamacpp -> llama-server -> health-gate -> editcap_run.py), with:

  * library  editcap-lib-v12-45nm (all 16 bench-v1.2 cells), PDK bptm45
  * arm B only, k=3, temperature 0.7 (driver default), 8192-token cap,
    EDITCAP_RECOVER_REASONING=1
  * conditions: ZS = EDITCAP_FEWSHOT ABSENT from the env (the driver tests
    truthiness of os.environ.get, so it is popped, not set to "0");
    FS = EDITCAP_FEWSHOT=1 (the existing generic worked example, unchanged)
  * 2 completions per (cell, condition): editcap_run.py has no repeat flag, so
    the SAME command is run once per sample into a distinct --out dir
    (/kaggle/working/editcap/<COND>-s<N>/). The driver sends no sampling seed, so
    llama-server draws a fresh random seed per request (-1 default) and the two
    samples are independent draws at temp 0.7. The finally-block counts cells
    whose s1/s2 raw outputs are byte-identical as a sanity check.
  * the repo clone is PINNED to REPO_SHA (fetched by sha after the branch
    clone) so every E-d kernel runs identical driver/library/sizer code even if
    the branch moves while kernels queue.

In-kernel smoke/base/escalation sizing is the driver's frozen default
(40 / 2x300 / 3x600) and is RECORDED ONLY: E-d scoring re-sizes every valid edit
locally at seeds 1,2,3 x 2500 bptm45.

Everything run-specific is in the CONFIG block below; the three E-d kernel dirs
(ed-32b-zs, ed-32b-fs, ed-14b) differ ONLY in that block.
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

# ============================ CONFIG (differs per kernel dir) ================
KERNEL_TAG = "ed-32b-fs"
MODEL_ID = "qwen3-32b-q4ks"
# (condition, sample) in execution order
RUNS = [("FS", 1), ("FS", 2)]
# GGUF: either a glob over attached datasets, or an HF download (url,size,sha256)
GGUF_GLOB = "/kaggle/input/**/Qwen3-32B*.gguf"
GGUF_DOWNLOAD = None
# ============================================================================

REPO_SLUG = "Devavavava/circuit-repro"
REPO_BRANCH = "worktree-externals-gf180"
REPO_SHA = "cc5a836bb26fbfef4f128777945ebdae39c3fb66"   # PREREG bench-v12-audit commit
EDITCAP_LIB = "editcap-lib-v12-45nm"
PDK = "bptm45"
ARM = "B"
K = "3"
MAX_TOKENS = "8192"
TEMPERATURE = "0.7"
SOFT_DEADLINE_H = 10.5     # do not START a new run past this (Kaggle hard limit 12 h)
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
    env = dict(os.environ, LNA_DEPS_ROOT=clone, EDITCAP_RECOVER_REASONING="1")
    env.pop("EDITCAP_FEWSHOT", None)
    if cond == "FS":
        env["EDITCAP_FEWSHOT"] = "1"
    elif cond != "ZS":
        raise ValueError(cond)
    return env


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
    manifest = {"kernel": KERNEL_TAG, "prereg": "kaggle/PREREG-BENCH-V12-AUDIT.md#E-d",
                "model_id": MODEL_ID, "lib": EDITCAP_LIB, "pdk": PDK, "arm": ARM,
                "k": K, "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
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
        gguf, prov = fetch_gguf()
        manifest["gguf"] = prov
        proc = launch_server(gguf)
        if not wait_health(proc):
            try:
                print(open(os.path.join(WORK, "llama-server.log")).read()[-4000:], flush=True)
            except Exception:
                pass
            sys.exit("%s llama-server never became healthy" % TAG)
        for cond, sample in RUNS:
            rec = {"cond": cond, "sample": sample, "out": run_dir(cond, sample)}
            manifest["runs"].append(rec)
            if (time.time() - T0) / 3600 > SOFT_DEADLINE_H:
                rec["skipped"] = "soft deadline %.1fh" % SOFT_DEADLINE_H
                log("SKIP %s-s%d: past soft deadline" % (cond, sample))
                continue
            inner = build_inner(cond, sample)
            log("RUN %s-s%d fewshot=%s" % (cond, sample, cond == "FS"))
            t = time.time()
            rec["rc"] = sh(["bash", "-c", inner], env=run_env(cond)).returncode
            rec["minutes"] = round((time.time() - t) / 60, 1)
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
