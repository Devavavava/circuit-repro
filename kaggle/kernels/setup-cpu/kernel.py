"""setup-cpu -- Kaggle SCRIPT kernel (CPU, internet ON, no accelerator).

Runs the full bootstrap end-to-end, then tars the built ngspice tree so the
kernel OUTPUT can be saved as the ngspice cache dataset (attach it to loop-gpu so
that session untars instead of rebuilding).

One-time / occasional use: run this whenever ngspice needs a rebuild or the
acceptance gate must be re-proved on a fresh Kaggle image. It is a CPU session on
purpose -- setup and debug NEVER burn GPU quota (see kaggle/PLAYBOOK.md).

Secrets required (Add-ons -> Secrets):  GH_READ_TOKEN
Env this kernel expects you to set via the kernel's own settings or here:
    REPO_SLUG  (your GitHub slug, e.g. youruser/circuit-repro)

After it finishes, "Save Version" -> the /kaggle/working tree (incl.
ngspice47.tar.gz) is downloadable and can be turned into a dataset.
"""
import os
import subprocess
import sys

# The repo is cloned by bootstrap.sh; this kernel file itself is uploaded to
# Kaggle alongside a copy of kaggle/bootstrap.sh (see kernel-metadata.json notes).
# We assume bootstrap.sh sits next to this file when pushed, OR in the clone.
WORK = "/kaggle/working"
NGSPICE_TARBALL = os.path.join(WORK, "ngspice47.tar.gz")
NGSPICE_PREFIX = os.environ.get("NGSPICE_PREFIX", os.path.join(WORK, "ngspice47"))


def _find_bootstrap():
    for cand in (
        "/kaggle/working/bootstrap.sh",
        "/kaggle/input/circuit-repro-kaggle/bootstrap.sh",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bootstrap.sh"),
        "/kaggle/working/circuit-repro/kaggle/bootstrap.sh",
    ):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    sys.exit("bootstrap.sh not found -- attach it (see kernel-metadata.json) "
             "or clone the repo first")


def main():
    bs = _find_bootstrap()
    print("[setup-cpu] running", bs, flush=True)
    # WITH_PANDAS=1 so the proposal round-trip + corpus shims are available in
    # the gate; WITH_TORCH stays off (LLM loop is torch-free).
    env = dict(os.environ, WITH_PANDAS="1")
    rc = subprocess.run(["bash", bs], env=env).returncode
    if rc != 0:
        # still tar whatever ngspice tree exists so a partial build is inspectable
        _tar_ngspice(warn_only=True)
        sys.exit("[setup-cpu] bootstrap FAILED rc=%d (report in /kaggle/working/report)" % rc)
    _tar_ngspice(warn_only=False)
    print("[setup-cpu] DONE -- save this version; ngspice cache =", NGSPICE_TARBALL,
          flush=True)


def _tar_ngspice(warn_only):
    if not os.path.isdir(NGSPICE_PREFIX):
        msg = "[setup-cpu] no ngspice tree at %s to tar" % NGSPICE_PREFIX
        print(msg, flush=True)
        if not warn_only:
            sys.exit(msg)
        return
    print("[setup-cpu] tarring", NGSPICE_PREFIX, "->", NGSPICE_TARBALL, flush=True)
    subprocess.run(["tar", "-czf", NGSPICE_TARBALL, "-C", os.path.dirname(NGSPICE_PREFIX),
                    os.path.basename(NGSPICE_PREFIX)], check=not warn_only)


if __name__ == "__main__":
    main()
