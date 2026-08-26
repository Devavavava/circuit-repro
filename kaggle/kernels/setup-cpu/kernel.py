"""setup-cpu -- Kaggle SCRIPT kernel (CPU, internet ON, no accelerator).

Launch behaviors proven necessary on the first real pushes (2026-08-26):
  1. GH token resolution order: (a) gh_token.txt from an attached private
     dataset -- the ONLY form that survives CLI (API) pushes; (b) kaggle_secrets
     -- works only for browser-initiated runs, editor-attached secrets are NOT
     available to API-pushed batch runs; (c) GH_READ_TOKEN env (local testing).
  2. The repo is pre-cloned here, because a script push uploads only this file --
     bootstrap.sh lives in the clone, which would otherwise be chicken-and-egg.
loop-gpu/kernel.py needs the same two treatments before its first push (TODO).

Runs the full bootstrap end-to-end, then tars the built ngspice tree so the
kernel OUTPUT can be saved as the ngspice cache dataset (attach it to loop-gpu).
Setup and debug NEVER burn GPU quota (see kaggle/PLAYBOOK.md).

Token supply (pick one):
  - private dataset (recommended, CLI-autonomous): a dataset containing
    gh_token.txt (the fine-grained read-only PAT), listed in this kernel's
    kernel-metadata.json dataset_sources;
  - or Add-ons -> Secrets: GH_READ_TOKEN, browser Save & Run All only.
"""
import glob
import os
import subprocess
import sys

REPO_SLUG = "Devavavava/circuit-repro"
REPO_BRANCH = "main"
WORK = "/kaggle/working"
CLONE_DIR = os.path.join(WORK, "circuit-repro")
NGSPICE_TARBALL = os.path.join(WORK, "ngspice47.tar.gz")
NGSPICE_PREFIX = os.environ.get("NGSPICE_PREFIX", os.path.join(WORK, "ngspice47"))


def _get_token():
    for p in sorted(glob.glob("/kaggle/input/*/gh_token*")):
        tok = open(p).read().strip()
        if tok:
            print("[setup-cpu] GH token from attached dataset:", p, flush=True)
            return tok
    try:
        from kaggle_secrets import UserSecretsClient
        tok = UserSecretsClient().get_secret("GH_READ_TOKEN")
        print("[setup-cpu] GH token from kaggle_secrets", flush=True)
        return tok
    except Exception as e:
        print("[setup-cpu] kaggle_secrets unavailable (%s)" % e, flush=True)
    tok = os.environ.get("GH_READ_TOKEN", "").strip()
    if tok:
        return tok
    sys.exit(
        "[setup-cpu] no GH token. Either attach the private token dataset\n"
        "(gh_token.txt, see kernel docstring) -- required for CLI-pushed runs --\n"
        "or attach the GH_READ_TOKEN secret and rerun from the browser."
    )


def _preclone(token):
    if os.path.isdir(os.path.join(CLONE_DIR, ".git")):
        print("[setup-cpu] clone exists, skipping", flush=True)
        return
    url = "https://x-access-token:%s@github.com/%s.git" % (token, REPO_SLUG)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", REPO_BRANCH, url, CLONE_DIR],
        check=True,
    )


def main():
    token = _get_token()
    _preclone(token)
    bs = os.path.join(CLONE_DIR, "kaggle", "bootstrap.sh")
    if not os.path.exists(bs):
        sys.exit("[setup-cpu] %s missing after clone" % bs)
    print("[setup-cpu] running", bs, flush=True)
    # WITH_PANDAS=1 so the proposal round-trip + corpus shims are in the gate;
    # WITH_TORCH stays off (LLM loop is torch-free).
    env = dict(
        os.environ,
        WITH_PANDAS="1",
        GH_READ_TOKEN=token,
        REPO_SLUG=REPO_SLUG,
        REPO_BRANCH=REPO_BRANCH,
        CLONE_DIR=CLONE_DIR,
    )
    rc = subprocess.run(["bash", bs], env=env).returncode
    if rc != 0:
        _tar_ngspice(warn_only=True)
        sys.exit("[setup-cpu] bootstrap FAILED rc=%d (report in /kaggle/working/report)" % rc)
    _tar_ngspice(warn_only=False)
    print("[setup-cpu] DONE -- save this version; ngspice cache =", NGSPICE_TARBALL, flush=True)


def _tar_ngspice(warn_only):
    if not os.path.isdir(NGSPICE_PREFIX):
        msg = "[setup-cpu] no ngspice tree at %s to tar" % NGSPICE_PREFIX
        print(msg, flush=True)
        if not warn_only:
            sys.exit(msg)
        return
    print("[setup-cpu] tarring", NGSPICE_PREFIX, "->", NGSPICE_TARBALL, flush=True)
    subprocess.run(
        ["tar", "-czf", NGSPICE_TARBALL, "-C", os.path.dirname(NGSPICE_PREFIX),
         os.path.basename(NGSPICE_PREFIX)],
        check=not warn_only,
    )


if __name__ == "__main__":
    main()
