"""E-11 generator-as-editor: regrow a parent topology's Eulerian token sequence.

Mechanism (generic knobs only -- cut position, temperature, length caps; NOTHING
circuit-specific is hand-injected):

  1. Take the parent topology's Eulerian token sequence `toks` (starts at VSS).
  2. Sample a cut point in the STRUCTURAL BODY (not the first few tokens): the
     kept prefix is toks[:cut].
  3. Feed the model  [<class_token>] + toks[:cut]  and let it complete to TRUNCATE
     (temperature ~1.0). The class token matches the task's band (nb/wb).
  4. Decode the completed token ids -> a `Topology` (union-find replay), drop the
     class token, cut at TRUNCATE.
  5. Realize via moves.realize (token round-trip + structural screen) -> wl-hash.

Loading: the adopted checkpoint lna/out/ft_p5v7_v2.pth is arm p5 winners=True
tag=p5v7 (vocab 1008). We load it via the finetune-era loader (`_attrib_sample`
pattern): rebind `finetune.ckpt_path` to the absolute checkpoint path, then
`finetune.load_ft('p5', device, winners=True, tag='p5v7')`. (generate.py lacks
--ckpt and genie_common.load_model builds vocab 1005 -- both known traps.)

Read-only toward lna/; this module lives under engineer/ and writes nothing.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(HERE)               # wt-e11 root
LNA = os.path.join(WT, "lna")
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

CKPT = "/home/dpatni/circuit-repro/lna/out/ft_p5v7_v2.pth"

_MODEL = {"nb": None, "wb": None, "obj": None, "stoi": None}


def load_model(device="cpu"):
    """Load ft_p5v7_v2 (vocab 1008) once; cache. Returns (model, stoi)."""
    if _MODEL["obj"] is not None:
        return _MODEL["obj"], _MODEL["stoi"]
    import finetune as FT
    FT.ckpt_path = lambda arm, winners=False, tag=None: CKPT
    model = FT.load_ft("p5", device, winners=True, tag="p5v7")
    _, stoi, vocab = FT.ext_vocab("p5", False)
    assert vocab == 1008, f"expected vocab 1008, got {vocab}"
    _MODEL["obj"], _MODEL["stoi"] = model, stoi
    return model, stoi


def class_token_for(spec_name):
    """Band class token: NB if the spec's reference topology bears an inductor,
    else WB. Generic (from the parent circuit's own inductor count) -- no
    target-circuit knowledge. dhruva-l* are inductor LNAs (NB); dhruva-s too."""
    # decided per-parent-topology at regrow time from n_inductors; see regrow().
    return None


def _cut_points(n_tok, rng, n_cuts, min_frac=0.15, max_frac=0.85):
    """Sample cut indices within the structural body (not the first few tokens).
    Generic: uniform in [min_frac, max_frac] of the sequence length, deduped."""
    lo = max(4, int(min_frac * n_tok))
    hi = max(lo + 1, int(max_frac * n_tok))
    cuts = []
    seen = set()
    guard = 0
    while len(cuts) < n_cuts and guard < n_cuts * 20:
        guard += 1
        c = rng.randint(lo, hi)
        if c in seen:
            continue
        seen.add(c)
        cuts.append(c)
    return cuts


def regrow_batch(parent_toks, cls, cuts, temperature, model, stoi,
                 max_new_tokens=256, device="cpu"):
    """Regrow proposals: for each cut in `cuts`, prefix = [<cls>] + parent_toks[:cut],
    complete with the model. Returns list of dicts:
      {cut_index, cut_frac, temperature, n_new_tokens, completed_toks (names) | None,
       decode_ok (has TRUNCATE)}.
    Batched by shared prefix length where possible; here we group by length.
    """
    from genie_common import STOI, ITOS, VOCAB_SIZE, TRUNCATE_ID, generate_batch
    cls_id = stoi["<LNA_NB>" if cls == "nb" else "<LNA_WB>"]
    n_tok = len(parent_toks)
    # build integer prefixes
    prefixes = []
    for c in cuts:
        body = parent_toks[:c]
        try:
            ids = [cls_id] + [STOI[t] for t in body]
        except KeyError:
            ids = None
        prefixes.append((c, ids))
    # group by prefix length so generate_batch can batch (rows share a length)
    out = []
    from collections import defaultdict
    by_len = defaultdict(list)
    for c, ids in prefixes:
        if ids is None:
            out.append({"cut_index": c, "cut_frac": round(c / n_tok, 4),
                        "temperature": temperature, "n_new_tokens": 0,
                        "completed_toks": None, "decode_ok": False,
                        "reason": "prefix-encode-fail"})
            continue
        by_len[len(ids)].append((c, ids))
    for L, group in by_len.items():
        batch_prefixes = [ids for (_c, ids) in group]
        rows, steps = generate_batch(model, batch_prefixes,
                                     max_new_tokens=max_new_tokens,
                                     temperature=temperature, device=device)
        for (c, ids), row in zip(group, rows):
            allids = [int(x) for x in row.tolist()]
            # completed = everything AFTER the class token, up to first TRUNCATE
            body_ids = [x for x in allids if x < VOCAB_SIZE]  # drop class token(s)
            has_trunc = TRUNCATE_ID in body_ids
            circ = (body_ids[:body_ids.index(TRUNCATE_ID)]
                    if has_trunc else body_ids)
            toks = [ITOS[i] for i in circ]
            out.append({"cut_index": c, "cut_frac": round(c / n_tok, 4),
                        "temperature": temperature,
                        "n_new_tokens": max(0, len(circ) - c),
                        "completed_toks": toks, "decode_ok": bool(has_trunc)})
    return out


def decode_to_topo(toks):
    """Completed token names -> (Topology, wl_hash) or None. Union-find replay
    happens inside Topology(); wl-hash via realize's round-trip is done by caller.
    Here we only parse + validity-check."""
    from topology import Topology
    try:
        topo = Topology(toks)
    except Exception:
        return None
    if not topo.valid:
        return None
    return topo


def realize_topo(topo, spec):
    """Round-trip a decoded Topology through the netlist so realize() gives a
    canonical wl-hash + structural screen. Returns (mtopo, seq, wl, canon) or None."""
    import templates as T
    import moves as M
    nl, _ports = T.topo_to_netlist(topo)
    if nl is None:
        return None
    return M.realize(nl, spec)
