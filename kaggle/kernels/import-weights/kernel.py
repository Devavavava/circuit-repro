"""import-weights -- Kaggle SCRIPT kernel (CPU, internet ON).

Downloads the GGUF weight files to /kaggle/working so the kernel output can be
saved as a PRIVATE dataset (attach it to loop-gpu). Prints size + sha256 for each
so provenance travels with the dataset.

The two PROJECT checkpoints (AnalogGenie/repo/Pretrain.pth ~190MB and
lna/out/ft_p5v7_v2.pth ~190MB) are NOT downloaded here -- they are gitignored and
live on the box. Add them to this SAME dataset from the box (kaggle datasets
version), so one weights dataset carries both the GGUFs and the project
checkpoints; bootstrap.sh symlinks the .pth files if present.

NOTE: the exact HF repo/filename for each GGUF drifts as quant repos are
re-uploaded. Each filename below is a VARIABLE with a TODO -- verify at run time
(open the HF repo, copy the resolve URL) before trusting the download.
"""
import hashlib
import os
import sys
import urllib.request

WORK = "/kaggle/working/weights"
os.makedirs(WORK, exist_ok=True)

# (label, HF repo, filename)   -- huggingface.co/<repo>/resolve/main/<filename>
# TODO verify exact HF repo/filename at run time (repos get re-uploaded).
TARGETS = [
    # primary: Qwen3-30B-A3B (MoE, ~3B active) Q4_K_M
    ("qwen3-30b-a3b-q4_k_m",
     "Qwen/Qwen3-30B-A3B-GGUF",                     # TODO verify repo
     "Qwen3-30B-A3B-Q4_K_M.gguf"),                  # TODO verify filename
    # fallback: gpt-oss-20b GGUF
    ("gpt-oss-20b",
     "ggml-org/gpt-oss-20b-GGUF",                   # TODO verify repo
     "gpt-oss-20b.gguf"),                           # TODO verify filename
    # volume tier: Qwen3-8B Q6_K
    ("qwen3-8b-q6_k",
     "Qwen/Qwen3-8B-GGUF",                          # TODO verify repo
     "Qwen3-8B-Q6_K.gguf"),                         # TODO verify filename
]

HF_BASE = os.environ.get("HF_BASE", "https://huggingface.co")
ONLY = os.environ.get("ONLY")            # optional: label substring to fetch just one


def resolve_url(repo, filename):
    return "%s/%s/resolve/main/%s" % (HF_BASE.rstrip("/"), repo, filename)


def sha256_of(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def download(url, dest):
    print("[import-weights] GET", url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "circuit-repro-import"})
    tok = os.environ.get("HF_TOKEN")     # optional, for gated repos
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req) as r, open(dest, "wb") as out:
        total = 0
        while True:
            blk = r.read(1 << 20)
            if not blk:
                break
            out.write(blk)
            total += len(blk)
    return total


def main():
    manifest = []
    for label, repo, filename in TARGETS:
        if ONLY and ONLY not in label:
            continue
        dest = os.path.join(WORK, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print("[import-weights]", dest, "already present -- skipping", flush=True)
        else:
            try:
                n = download(resolve_url(repo, filename), dest)
                print("[import-weights] wrote %d bytes -> %s" % (n, dest), flush=True)
            except Exception as e:              # verbatim -- do not swallow
                print("[import-weights] FAILED %s: %r" % (label, e), flush=True)
                continue
        sz = os.path.getsize(dest)
        digest = sha256_of(dest)
        print("[import-weights] %-22s %12d bytes  sha256=%s"
              % (label, sz, digest), flush=True)
        manifest.append({"label": label, "repo": repo, "filename": filename,
                         "bytes": sz, "sha256": digest})
    # write a manifest beside the weights so the dataset self-describes
    import json
    with open(os.path.join(WORK, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("[import-weights] manifest:", os.path.join(WORK, "manifest.json"), flush=True)
    if not manifest:
        sys.exit("[import-weights] nothing downloaded (check TODO filenames/URLs)")


if __name__ == "__main__":
    main()
