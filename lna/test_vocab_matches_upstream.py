"""Guard: lna/genie_common.py must reproduce upstream's vocabulary exactly.

Token ids are positional, so any drift in the device list silently decodes the
checkpoint's output into the wrong device names. This execs the vocabulary
section of upstream Inference.py and diffs it against ours.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from genie_common import DEVICES, REPO, VOCAB_SIZE, STOI  # noqa: E402


def upstream_devices():
    src = open(os.path.join(REPO, "Inference.py"), encoding="utf-8").read()
    cut = src.index("# Create a mapping from device names to integers")
    body = src[:cut]
    # drop the imports and the model-side hyperparameters; keep the list building
    body = "\n".join(ln for ln in body.splitlines()
                     if not ln.startswith(("import ", "from ")))
    import torch  # the stripped header still references torch for device selection
    ns = {"torch": torch}
    exec(compile(body, "Inference.py(vocab)", "exec"), ns)
    return ns["devices"]


def main():
    ours = DEVICES
    theirs = upstream_devices()

    print(f"upstream vocab size : {len(theirs)}")
    print(f"ours                : {len(ours)}")

    if ours == theirs:
        print("MATCH: token lists are identical")
    else:
        print("MISMATCH")
        if len(ours) != len(theirs):
            print(f"  length differs by {len(ours) - len(theirs)}")
        for i, (a, b) in enumerate(zip(ours, theirs)):
            if a != b:
                print(f"  first divergence at index {i}: ours={a!r} upstream={b!r}")
                break
        sys.exit(1)

    # the ids inference.py hardcodes
    assert VOCAB_SIZE == 1005, VOCAB_SIZE
    assert STOI["VSS"] == 1003, STOI["VSS"]
    assert STOI["TRUNCATE"] == 1004, STOI["TRUNCATE"]
    print("ids OK: VSS=1003 (upstream's generation seed), TRUNCATE=1004, vocab=1005")


if __name__ == "__main__":
    main()
