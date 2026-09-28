"""Local mock of the R3 kernel's reward path (no GPU, no torch).

Extracts the embedded scripts from the kernel, then exercises the reward
functions exactly as TRL would call them (prompts, completions, cell=...), with
the worktree standing in for the kernel's clone, including a real SPICE-sized
rollout through the spawn pool.

    kaggle/campaigns/rl-readiness/R3/envrun.sh python \
        kaggle/campaigns/rl-readiness/R3/localtest/extract_and_test.py
"""
import base64
import importlib.util
import json
import os
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
KP = os.path.join(ROOT, "kaggle", "kernels-editcap", "rl-readiness-r3-grpo", "kernel.py")


def main():
    spec = importlib.util.spec_from_file_location("r3kernel", KP)
    k = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(k)
    for name, src in (("r3_reward.py", k.REWARD_PY), ("r3_trial.py", k.TRIAL_PY),
                      ("spice_bench.py", k.SPICE_BENCH_PY)):
        open(os.path.join(HERE, name), "w").write(src)
        compile(src, name, "exec")
    rows = json.loads(zlib.decompress(base64.b64decode(k.PROMPTS_B64)))
    json.dump(rows, open(os.path.join(HERE, "prompts.json"), "w"), indent=1)
    print("prompts", len(rows), "k", rows[0]["k"])

    os.environ["R3_CLONE"] = ROOT
    os.environ["R3_REWARD_LOG"] = os.path.join(HERE, "reward-local.jsonl")
    sys.path.insert(0, HERE)
    import r3_reward as RW
    RW.start_pool(2)
    cell = "bnl-09-gain-g0"
    anchor = open(os.path.join(ROOT, "kaggle", "editcap-lib-v1a", cell, "anchor.net")).read()
    body = "\n".join(l for l in anchor.splitlines() if l.strip() and not l.startswith("*"))
    comps = [
        "Diagnosis: gain short.\n```netlist\n%s\nR Rfb n2 n1\n```\nPredicted: s21 up." % body,
        "no fence at all",
        "```netlist\nNMOS M1 VOUT1 VIN1\n```",
        "```netlist\n%s\n```" % body,                       # valid but == anchor
        "```\nnetlist\n%s\nC Cx VOUT1 VSS\n```" % body,     # bare fence + tag line
    ]
    cells = [cell] * len(comps)
    t = time.time()
    rv = RW.reward_valid(None, comps, cell=cells)
    rn = RW.reward_novel(None, comps, cell=cells)
    rs = RW.reward_spice(None, comps, cell=cells)
    print("valid", rv)
    print("novel", rn)
    print("spice", rs, "wall %.1fs" % (time.time() - t))
    RW.POOL.terminate()
    assert rv == [1.0, 0.0, 0.0, 1.0, 1.0], rv
    assert rn == [0.5, 0.0, 0.0, 0.0, 0.5], rn
    assert rs[1] == rs[2] == rs[3] == 0.0 and rs[0] > 0 and rs[4] > 0, rs
    print("LOCAL MOCK OK")


if __name__ == "__main__":
    main()
