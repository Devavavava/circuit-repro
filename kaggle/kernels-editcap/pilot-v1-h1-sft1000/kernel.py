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
REPO_SHA = "cbeb6a01758366c15ddb08bf037c717125aaaf3f"
CFG = {
    "tag": "h1-sft1000",
    "kind": "lora_heldout",
    "lora_tag": "sft1000",          # kernel source devavratpatni/circuit-repro-pilot-v0-sft1000
    "expect_q4_sha256": "7f0c59211573434bdebf0ef87050ca1c5d28b943839e357675d123ab7cdeb38c",
    "model_id": "qwen3-14b-sft1000-q4km",
    "samples": 8,
    "start_deadline_min": 145.0,     # no held-out completion starts past this wall minute
    "hard_wall_min": 155.0,
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
