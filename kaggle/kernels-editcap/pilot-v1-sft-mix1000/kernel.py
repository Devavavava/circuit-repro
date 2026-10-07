"""pilot-v1 -- Kaggle SCRIPT kernel (GPU T4 x2, internet ON). Thin launcher.

Pre-registration: kaggle/PREREG-PILOT-V1.md (commit e46157ccf). This file only clones the
repo at the pinned commit REPO_SHA and hands CFG to kaggle/campaigns/pilot-v1/kernel_v1.py
(which reuses pilot-v0's kernel_common.py), so every line that runs is pinned.
See kaggle/campaigns/pilot-v1/README.md for the kernel set and the GPU-h ledger.
"""
import glob
import os
import re
import subprocess
import sys

# ============================ CONFIG ==========================================
REPO_SLUG = "Devavavava/circuit-repro"
REPO_BRANCH = "worktree-externals-gf180"
REPO_SHA = "833313861f53211df94553946074cc3ad1a209da"
CFG = {
    "tag": "sft-mix1000",
    "kind": "sft",
    "rows": "kaggle/campaigns/pilot-v1/sft-data/sft-458.jsonl",
    "model_id": "qwen3-14b-sft-mix1000-q4km",
    "samples": 2,
    "train_deadline_min": 215.0,     # training stops (LoRA saved, truncation recorded) here
    "start_deadline_min": 270.0,     # no held-out completion starts past this wall minute
    "hard_wall_min": 280.0,
    "repo_slug": REPO_SLUG,
    "repo_branch": REPO_BRANCH,
}
# ============================================================================
CLONE = "/tmp/circuit-repro"       # NOT /kaggle/working (must not be output)


def log(*a):
    print("[pv1-launch]", *a, flush=True)


def token():
    for p in sorted(glob.glob("/kaggle/input/**/gh_token*", recursive=True)):
        t = open(p).read().strip()
        if t:
            return t
    sys.exit("no gh token dataset attached")


def run(cmd):
    log("$", re.sub(r"://[^@/\s]+@", "://REDACTED@", " ".join(cmd)))
    subprocess.run(cmd, check=True)


def head():
    return subprocess.run(["git", "-C", CLONE, "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()


def clone_pinned(tok):
    url = "https://x-access-token:%s@github.com/%s.git" % (tok, REPO_SLUG)
    if not os.path.isdir(os.path.join(CLONE, ".git")):
        run(["git", "clone", "--depth", "1", "--branch", REPO_BRANCH, url, CLONE])
    if head() != REPO_SHA:
        run(["git", "-C", CLONE, "fetch", "--depth", "1", "origin", REPO_SHA])
        run(["git", "-C", CLONE, "checkout", "--detach", "FETCH_HEAD"])
    h = head()
    if h != REPO_SHA:
        sys.exit("clone HEAD %s != pinned %s" % (h, REPO_SHA))
    log("clone pinned at", h)
    return h


def main():
    tok = token()
    h = clone_pinned(tok)
    sys.path.insert(0, os.path.join(CLONE, "kaggle", "campaigns", "pilot-v1"))
    import kernel_v1 as KV
    sys.exit(KV.main(CFG, tok, CLONE, h))


if __name__ == "__main__":
    main()
