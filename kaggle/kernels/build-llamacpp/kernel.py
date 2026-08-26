"""build-llamacpp -- Kaggle SCRIPT kernel.

Two-phase quota discipline (kaggle/PLAYBOOK.md): v1 runs with GGML_CUDA=OFF on a
CPU session (free) to validate the clone/cmake/install/tar plumbing; the real
build is the SAME kernel restaged with GGML_CUDA "ON" + enable_gpu true (t4x2),
~8-15 min of quota, once. Its /kaggle/working/llamacpp.tar.gz output becomes the
llamacpp cache dataset that loop-gpu untars (never rebuilds).

Requires the private gh-token dataset attached (gh_token file), same as setup-cpu.
"""
import glob
import os
import subprocess
import sys

REPO_SLUG = "Devavavava/circuit-repro"
REPO_BRANCH = "main"
CLONE_DIR = "/tmp/circuit-repro"  # not /kaggle/working: must not become output
GGML_CUDA = os.environ.get("GGML_CUDA", "OFF")  # staged default; "ON" for the GPU build


def _token():
    for p in sorted(glob.glob("/kaggle/input/*/gh_token*")):
        tok = open(p).read().strip()
        if tok:
            print("[build-llamacpp-kernel] GH token from", p, flush=True)
            return tok
    print("[build-llamacpp-kernel] /kaggle/input contents:",
          glob.glob("/kaggle/input/*") + glob.glob("/kaggle/input/*/*"), flush=True)
    sys.exit("[build-llamacpp-kernel] no gh token dataset attached "
             "(need the circuit-repro-ghtoken dataset in dataset_sources)")


def main():
    tok = _token()
    if not os.path.isdir(os.path.join(CLONE_DIR, ".git")):
        url = "https://x-access-token:%s@github.com/%s.git" % (tok, REPO_SLUG)
        subprocess.run(["git", "clone", "--depth", "1", "--branch", REPO_BRANCH,
                        url, CLONE_DIR], check=True)
    script = os.path.join(CLONE_DIR, "kaggle", "build-llamacpp.sh")
    if not os.path.exists(script):
        sys.exit("[build-llamacpp-kernel] %s missing after clone" % script)
    env = dict(os.environ, GGML_CUDA=GGML_CUDA, BUILD_DIR="/tmp/_llamacpp_build")
    print("[build-llamacpp-kernel] running", script, "GGML_CUDA=" + GGML_CUDA,
          flush=True)
    sys.exit(subprocess.run(["bash", script], env=env).returncode)


if __name__ == "__main__":
    main()
