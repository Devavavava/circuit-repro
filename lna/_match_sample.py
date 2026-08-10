"""Prefix-conditioned sampling from an adopted P5 checkpoint (WP-MATCH step 4).

`finetune.sample` always seeds the model with exactly two tokens -- the class
token and `VSS` -- so every pool is drawn from the unconditioned narrowband (or
wideband) distribution. `generate.py` has carried real-LNA prefix conditioning
since Phase 1, but only for the *base* AnalogGenie checkpoint. This script is
that same technique pointed at a fine-tuned P5 checkpoint.

Nothing new is authored. A prefix is the opening K tokens of an Eulerian
traversal of a circuit **that already exists in this program** -- a corpus LNA, an
ingested external circuit, a `templates.py` archetype, or a stored design. The
only choice being exercised is *which existing designs to seed from*, which is
data selection, not structure creation.

Arms (`--arm`):
    uncond     class token + VSS  (reproduces finetune.sample; the baseline)
    all        prefixes from every corpus/external LNA traversal
    src        prefixes only from designs whose input port reaches a transistor
               SOURCE (`_match_struct.analyze -> port_src`), the motif
               `_match_sep.py` measured as the one that predicts a match
    gate       the complement of `src` -- the control that separates "prefix
               conditioning helps" from "*this* prefix helps"

    <gpu_py> lna/_match_sample.py --arm src --prefix-len 12 --n 256 \
        --tag p5v7 --winners --class nb --out lna/out/_m/pfx_src12
"""
import argparse
import json
import os
import random
import sys
import time

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from genie_common import TRUNCATE_ID, VSS_ID, decode, generate_batch  # noqa: E402
import finetune as FT                                   # noqa: E402
import _match_struct as MS                              # noqa: E402
from novelty import REPO                                # noqa: E402
from topology import Topology                           # noqa: E402

LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))


def _rows_for(cls_want):
    """[(name, [tokens...], port_src)] over every existing LNA traversal we own:
    the 41 dataset LNAs, the 9 ingested externals, and the archetype emission."""
    import numpy as np
    out = []
    for i in LNA_INDICES:
        p = os.path.join(REPO, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        arr = np.load(p, allow_pickle=True)
        src = MS.analyze(Topology([str(t) for t in arr[0]])).get("port_src", False)
        for row in arr:
            toks = [str(t) for t in row]
            toks = toks[:toks.index("TRUNCATE")] if "TRUNCATE" in toks else toks
            out.append((f"corpus{i}", toks, src))
    try:
        import build_lna_corpus as B
        for cid, seqs in B.external_sequences():
            src = MS.analyze(Topology(seqs[0])).get("port_src", False)
            for row in seqs:
                toks = [t for t in row if t != "TRUNCATE"]
                out.append((f"ext:{cid}", toks, src))
    except Exception as e:                                # noqa: BLE001
        print(f"  [warn] external channel unavailable: {e}", flush=True)
    tf = os.path.join(HERE, "out", "templates_train.json")
    if os.path.exists(tf):
        seen = {}
        for r in json.load(open(tf, encoding="utf-8"))["rows"]:
            k = r["arch"]
            if k not in seen:
                seen[k] = MS.analyze(Topology(r["seq"])).get("port_src", False)
            toks = [t for t in r["seq"] if t != "TRUNCATE"]
            out.append((f"arch{k}", toks, seen[k]))
    return out


def build_prefixes(arm, k, n, cls_tok, seed=1337):
    """n prefixes of EXACTLY k+2 ids: [class token, VSS, ...k-1 more real tokens].

    Every traversal already starts at VSS, so taking its first k tokens keeps the
    walk self-consistent with how the model was trained."""
    if arm == "uncond":
        return [[cls_tok, VSS_ID]] * n, {"uncond": n}
    rows = _rows_for(None)
    if arm == "src":
        rows = [r for r in rows if r[2]]
    elif arm == "gate":
        rows = [r for r in rows if not r[2]]
    rows = [r for r in rows if len(r[1]) >= k and r[1][0] == "VSS"]
    if not rows:
        raise SystemExit(f"arm {arm}: no traversals with >= {k} tokens")
    rng = random.Random(seed)
    rng.shuffle(rows)
    from genie_common import STOI
    pre, prov = [], {}
    for j in range(n):
        name, toks, _ = rows[j % len(rows)]
        ids = [STOI[t] for t in toks[:k]]
        pre.append([cls_tok] + ids)
        prov[name] = prov.get(name, 0) + 1
    return pre, prov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["uncond", "all", "src", "gate"], required=True)
    ap.add_argument("--prefix-len", type=int, default=12,
                    help="real tokens taken from the seed traversal (incl. VSS)")
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--tag", default="p5v7")
    ap.add_argument("--winners", action="store_true")
    ap.add_argument("--class", dest="cls", choices=["nb", "wb"], default="nb")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    _, stoi, _ = FT.ext_vocab("p5")
    cls_tok = stoi["<LNA_NB>" if a.cls == "nb" else "<LNA_WB>"]
    model = FT.load_ft("p5", a.device, winners=a.winners, tag=a.tag)
    pre, prov = build_prefixes(a.arm, a.prefix_len, a.n, cls_tok, seed=a.seed)
    print(f"arm={a.arm} prefix_len={a.prefix_len} (ids/row {len(pre[0])}) "
          f"n={a.n} tag={a.tag} class={a.cls} distinct_seed_circuits={len(prov)}",
          flush=True)

    os.makedirs(a.out, exist_ok=True)
    meta, produced, t0 = [], 0, time.time()
    for s in range(0, a.n, a.batch):
        chunk = pre[s:s + a.batch]
        rows, steps = generate_batch(model, chunk, max_new_tokens=a.max_tokens,
                                     temperature=a.temperature, device=a.device)
        for row in rows:
            ids = [int(x) for x in row.tolist()]
            ids = [x for x in ids if x < FT.VOCAB_SIZE]   # drop the class token
            circ = ids[:ids.index(TRUNCATE_ID)] if TRUNCATE_ID in ids else ids
            open(os.path.join(a.out, f"seq{produced:04d}.txt"), "w").write(decode(circ))
            meta.append({"file": f"seq{produced:04d}.txt",
                         "terminated": TRUNCATE_ID in ids,
                         "circuit_tokens": len(circ)})
            produced += 1
        print(f"  [{produced}/{a.n}] {steps} steps", flush=True)
    json.dump({"arm": a.arm, "prefix_len": a.prefix_len, "seed": a.seed,
               "tag": a.tag, "cls": a.cls, "n": a.n, "seed_circuits": prov,
               "meta": meta},
              open(os.path.join(a.out, "meta.json"), "w"), indent=2)
    print(f"sampled {produced} -> {a.out} in {time.time()-t0:.0f}s; "
          f"terminated {sum(m['terminated'] for m in meta)}/{produced}", flush=True)


if __name__ == "__main__":
    main()
