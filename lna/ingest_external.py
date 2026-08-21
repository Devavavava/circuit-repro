"""Ingest the converted external LNA circuits into the corpus, with gates.

`lna/data/external/<id>/` holds real/cited LNA topologies converted from outside
the AnalogGenie dataset (open IHP SG13G2 tapeouts, an ALIGN example LNA, cited
paper transcriptions), each with a `provenance.json`. This driver takes them the
last mile: Eulerian augmentation (via `build_lna_corpus --stage external`), then
a fixed validation ladder, then the label store, then a manifest.

### The ladder, and which rungs are GATES

A gate failing means the circuit is **quarantined** -- left on disk with the
reason recorded, and excluded from the corpus, the novelty reference and any
training set. A non-gate is measured and reported but decides nothing, because
the corpus is "real LNA topologies", not "topologies that pass our screen": the
existing 41 include inductorless common-gate designs that score 2/5, and index
1081 does not even simulate.

  GATE  provenance      a provenance.json exists, and its source/citation
                        subtree is free of the blind protocol's excluded paper
                        while carrying an explicit independence statement
  GATE  augmentation    >=1 Eulerian path covering every edge exactly once
  GATE  structure       Topology.valid and no floating sub-circuit
  GATE  vocabulary      every token is in the guarded AnalogGenie vocabulary and
                        encode->decode round-trips exactly
  GATE  identity        the augmented representative's WL hash equals the hash of
                        the converter's own token sequence (the conversion and
                        the augmentation must agree on what circuit this is)
  GATE  ngspice         op (+ sp/noise when two-port) completes without a fatal
                        error on the emitted deck
  --    screen          topology.lna_score + the nearest-band spec's L0 screen
  --    L1 bias         bias.insert_bias sweep: how many MOS conduct
  --    L2 label        one cheap ZOAF sizing row against the nearest-band spec,
                        recipe `ingest-v1`
  --    novelty         is this circuit new against ref-v2 (corpus+archetypes)?

### Nearest-band spec

L2 labels need a spec, and these circuits were designed against their own
targets, not ours. `SPEC_OF` maps each id to the closest of the project's specs
by centre frequency and match style, with the reason stated per row. A label is
therefore "how this real topology sizes against our nearest target", not a
reproduction of the original design's published numbers -- and an infeasible
result is expected and informative, not a defect.

    python lna/ingest_external.py --audit          # no ngspice; screen+vocab+novelty
    python lna/ingest_external.py --run            # full ladder, writes the manifest
    python lna/ingest_external.py --run --id ihp-gps-lna-npn
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_lna_corpus as B                              # noqa: E402
import datastore as ds                                    # noqa: E402
import novelty                                            # noqa: E402
from to_spice import Netlist                              # noqa: E402
from topology import Topology                             # noqa: E402

# ---------------------------------------------------------------- blind protocol
# plans2/08-DHRUVA-GOAL.md: the target paper is never fetched, and nothing in the
# corpus may derive from it. The scout verified this per circuit; it is re-checked
# here mechanically before ingestion, because "someone said so in a report" is not
# a gate. Markers are matched against the SOURCE/CITATION subtrees only -- the
# rest of a provenance.json is expected to name the paper, in the sentence that
# says the circuit is unrelated to it.
EXCLUDED_MARKERS = ("kanchetla", "navic", "beidou")
EXCLUDED_SOURCE_KEYS = ("source", "source_family", "cited_paper", "conversion",
                        "transcription")
INDEPENDENCE_RE = re.compile(
    r"(independent of|unrelated to|not related to|neither is derived"
    r"|not derived from|does not derive|nor references)[^.]{0,160}kanchetla",
    re.IGNORECASE | re.DOTALL)

# ------------------------------------------------------------ nearest-band spec
# (spec, why). Chosen by centre frequency first, match style second.
SPEC_OF = {
    "ihp-gps-lna-nmos":    ("gps-l1", "GPS band ~1.575 GHz, narrowband inductive match"),
    "ihp-gps-lna-npn":     ("gps-l1", "GPS-band sibling of the NMOS variant"),
    "ihp-lna-2p45g":       ("wifi24", "2.45 GHz ISM band, narrowband tuned cascode"),
    "align-lna-qm":        ("wideband-sdr",
                            "inductorless resistive-load core; no tuned band, and "
                            "wideband-sdr is the only spec that allows no inductor"),
    "paper-noisecancel":   ("wideband-sdr",
                            "inductorless wideband noise-cancelling, the family "
                            "this spec was written to exercise"),
    "paper-transformerfb": ("wideband-sdr",
                            "transformer feedback for wideband input matching"),
    "paper-currentreuse":  ("wifi24", "paper's narrowband mode is 2.4 GHz"),
    "paper-gmboostcg":     ("wifi24",
                            "narrowband gm-boosted CG with an inductive drain load"),
    "paper-diffcccg":      ("wifi24",
                            "narrowband differential CG with inductive loads; note "
                            "the spec is single-ended, so single_input is expected "
                            "to fail on L0"),
    "paper-sige-hbt-resfb": ("wideband-sdr",
                             "wideband resistive-feedback SiGe-HBT LNA; wideband-sdr "
                             "is the nearest broadband target"),
    "paper-nc-cc-inductorless": ("wideband-sdr",
                                 "inductorless wideband noise-cancelling, same family "
                                 "as paper-noisecancel"),
}

# Cheap ZOAF budget for an ingest label -- deliberately below `candidate-v1`
# (6/6/1). These rows exist to give the store real-circuit coverage, not to make
# a feasibility claim, and the budget is stamped so they can never be pooled with
# candidate-v1 or curated-v1 rows by accident.
INGEST_ZOAF = {"n_candidates": 4, "sgd_iters": 4, "cgd_iters": 1}
INDUCTOR_Q = 12


# ------------------------------------------------------------------ vocabulary
def _vocab():
    """The guarded AnalogGenie vocabulary, without importing torch.

    `genie_common` imports torch at module scope and the analysis interpreter is
    deliberately torch-free (HANDOVER §3), so `build_vocab` is source-sliced out
    of it -- the same technique `build_lna_corpus.load_functions` uses on
    upstream. This is not a second copy of the vocabulary: it executes
    `genie_common.py`'s own definition, which `test_vocab_matches_upstream.py`
    pins against upstream's `Inference.py` in the regression quartet."""
    src = open(os.path.join(HERE, "genie_common.py"), encoding="utf-8").read()
    start = src.index("def build_vocab()")
    end = src.index("\ndef ", start + 1)
    ns = {}
    exec(compile(src[start:end], "genie_common.py(vocab)", "exec"), ns)
    devices = ns["build_vocab"]()          # already ends with VDD/VSS/TRUNCATE
    if len(devices) != 1005 or devices[-1] != "TRUNCATE":
        raise RuntimeError(f"vocabulary slice looks wrong: {len(devices)} tokens, "
                           f"last={devices[-1]!r}")
    return devices


_VOCAB = None


def vocab_roundtrip(tokens):
    """(ok, unknown tokens). Encode to ids and decode back; any token outside the
    vocabulary would be unrepresentable to the generator, and a non-identity
    round-trip would mean an id collision."""
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = _vocab()
    stoi = {t: i for i, t in enumerate(_VOCAB)}
    itos = {i: t for t, i in stoi.items()}
    unknown = sorted({t for t in tokens if t not in stoi})
    if unknown:
        return False, unknown
    ids = [stoi[t] for t in tokens]
    return [itos[i] for i in ids] == list(tokens), []


# ------------------------------------------------------------------ provenance
def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_strings(v)


def check_provenance(prov):
    """(ok, note). Gate 1: the blind protocol, re-verified mechanically."""
    if not prov:
        return False, "no provenance.json"
    whole = " ".join(_walk_strings(prov))
    src_text = " ".join(_walk_strings({k: v for k, v in prov.items()
                                       if k in EXCLUDED_SOURCE_KEYS})).lower()
    hits = [m for m in EXCLUDED_MARKERS if m in src_text]
    if hits:
        return False, f"excluded-paper marker {hits} inside a source/citation field"
    if not INDEPENDENCE_RE.search(whole):
        return False, "no explicit independence statement for the excluded paper"
    # The converter may already have flagged a circuit as unfit; honour it rather
    # than re-deciding, and carry its reason through to the manifest.
    if prov.get("quarantine"):
        return False, f"converter quarantined: {prov.get('quarantine_reason')}"
    lic = ((prov.get("source") or {}).get("license")
           or (prov.get("cited_paper") or {}).get("open_access"))
    return True, (lic or "transcription, no file license")[:60]


# --------------------------------------------------------------------- ngspice
def sanity_sim(topo):
    """(ok, note, s11min, s21max). One deck, op + (sp + noise when two-port)."""
    import extract as E
    nl = Netlist(topo, inductor_q=INDUCTOR_Q)
    bad = nl.missing_pins()
    if bad:
        return False, f"not emittable: {bad[0][0]} {bad[0][1]}", None, None
    out = E.run_deck(nl.emit(), "ingest_", "sanity.cir")
    if out is None:
        return False, "ngspice timed out", None, None
    low = out.lower()
    for fatal in ("singular matrix", "fatal error", "error on line",
                  "simulation aborted"):
        if fatal in low:
            return False, f"ngspice: {fatal}", None, None
    s11 = re.search(r"vecmin\(s11db\)\s*=\s*([-\d.eE+]+)", out)
    s21 = re.search(r"vecmax\(s21db\)\s*=\s*([-\d.eE+]+)", out)
    if nl.two_port and not (s11 and s21):
        return False, "two-port deck produced no S-parameters", None, None
    note = "op+sp+noise clean" if nl.two_port else "op clean (no two-port)"
    return (True, note,
            float(s11.group(1)) if s11 else None,
            float(s21.group(1)) if s21 else None)


# ------------------------------------------------------------------ L1 and L2
def l1_label(topo, cid, log=True):
    import bias
    nl, inserter, rep, swept = bias.insert_bias(
        topo, sweep=True, log=log, inductor_q=INDUCTOR_Q,
        provenance={"source_arm": "external-ingest", "external_id": cid,
                    "recipe": B.INGEST_RECIPE})
    if rep.get("skipped"):
        return {"skipped": rep["skipped"], "n_mos": rep.get("n_mos")}
    return {"n_mos": rep["n_mos"], "n_conducting": swept["n_conducting"],
            "all_conduct": bool(swept["all_conduct"]),
            "n_bias_nets": inserter.n_bias_nets}


def l2_label(topo, cid, spec_name, seed=1, log=True):
    """One cheap ZOAF sizing row, logged with recipe `ingest-v1`.

    The row is assembled here rather than inside `size.size_topology` so the
    recipe and the (deliberately reduced) budget land on the row honestly --
    `size_topology`'s own logging path hardcodes `candidate-v1`/`curated-v1`,
    and mislabelling the budget would silently pool these with a different label
    domain."""
    import size
    spec = size._spec_for_sizing(spec_name)
    res = size.size_topology(topo, spec, seed=seed, log=False, enrich_nf=True,
                             inductor_q=INDUCTOR_Q, **INGEST_ZOAF)
    if res is None:
        return {"status": "unsizable (bias skipped or no two-port / no free params)"}
    m = res.get("metrics")
    cfg = dict(size._zoaf_cfg(seed, INGEST_ZOAF["n_candidates"],
                              INGEST_ZOAF["sgd_iters"], INGEST_ZOAF["cgd_iters"],
                              B.INGEST_RECIPE, inductor_q=INDUCTOR_Q, spec=spec))
    status = "not-logged"
    if log:
        row = ds.row_l2(spec, m, res["feasible"], res["n_evals"],
                        best_params=res.get("best_params"),
                        best_obj=res.get("best_obj"), topo=topo,
                        wl_hash=novelty.wl_features(topo)[0],
                        provenance={"source_arm": "external-ingest",
                                    "external_id": cid,
                                    "recipe": B.INGEST_RECIPE},
                        zoaf_cfg=cfg)
        status, _ = ds.append_l2(row)
    out = {"spec": spec_name, "status": status, "feasible": res["feasible"],
           "viol": res.get("viol"), "n_evals": res["n_evals"],
           "nf_gated": cfg.get("nf_gated")}
    if m:
        out["metrics"] = {k: m.get(k) for k in
                          ("s11_db", "s11_max_db", "s21_db", "idd_ma", "nf_db")}
    return out


# ------------------------------------------------------------------- the ladder
def ingest_one(cid, d, run=True, seed=1, log=True):
    row = {"id": cid, "recipe": B.INGEST_RECIPE, "gates": {}, "ingested": False}
    prov_path = os.path.join(d, "provenance.json")
    prov = json.load(open(prov_path, encoding="utf-8")) if os.path.isfile(prov_path) else None

    ok, note = check_provenance(prov)
    row["gates"]["provenance"] = {"ok": ok, "note": note}
    row["source"] = {
        "project": ((prov or {}).get("source") or {}).get("project")
                   or ((prov or {}).get("cited_paper") or {}).get("title"),
        "license": ((prov or {}).get("source") or {}).get("license"),
        "family": (prov or {}).get("source_family"),
    }
    if not ok:
        row["quarantine_reason"] = f"provenance: {note}"
        return row

    graph, seqfile, npy = B._external_paths(cid, d)
    seqs = []
    if os.path.exists(npy):
        import numpy as np
        seqs = [[str(t) for t in r] for r in np.load(npy, allow_pickle=True)]
    row["gates"]["augmentation"] = {"ok": bool(seqs), "n_sequences": len(seqs),
                                    "budget": B.external_budget(cid, d)}
    if not seqs:
        row["quarantine_reason"] = "augmentation: no Eulerian sequences on disk"
        return row

    topo = Topology(seqs[0])
    floating = sorted(topo.floating_devices())
    struct_ok = topo.valid and not floating
    row["gates"]["structure"] = {"ok": struct_ok, "valid": topo.valid,
                                 "floating": floating}
    counts = topo.counts()
    score, crit = topo.lna_score()
    row["graph"] = {"n_devices": topo.n_devices, "counts": counts,
                    "n_inductors": topo.n_inductors,
                    "inductor_ratio": round(topo.inductor_ratio, 3),
                    "lna_score": score,
                    "lna_score_missed": sorted(k for k, v in crit.items() if not v)}
    if not struct_ok:
        row["quarantine_reason"] = (f"structure: valid={topo.valid} "
                                    f"floating={floating}")
        return row

    # vocabulary: check the un-padded content of every augmented row
    bad_rows = []
    for i, s in enumerate(seqs):
        toks = s[:s.index("TRUNCATE")] if "TRUNCATE" in s else s
        rt, unknown = vocab_roundtrip(toks)
        if not rt or unknown:
            bad_rows.append((i, unknown[:5]))
            break
    row["gates"]["vocabulary"] = {"ok": not bad_rows, "bad": bad_rows}
    if bad_rows:
        row["quarantine_reason"] = f"vocabulary: {bad_rows}"
        return row

    wl = novelty.wl_features(topo)[0]
    row["wl_hash"] = wl
    ident = {"ok": None, "converter_wl": None}
    if os.path.exists(seqfile):
        from topology import parse_arrow_file
        conv_wl = novelty.wl_features(Topology(parse_arrow_file(seqfile)))[0]
        ident = {"ok": conv_wl == wl, "converter_wl": conv_wl}
    row["gates"]["identity"] = ident
    if ident["ok"] is False:
        row["quarantine_reason"] = ("identity: augmented representative is a "
                                    "different graph from the converted netlist")
        return row

    # novelty against the *previous* reference: is this circuit actually new?
    ref_hashes, ref_feats, ref_meta = novelty.reference(novelty.REF_V2)
    nn, who = novelty.nn_similarity(novelty.wl_features(topo)[1], ref_feats)
    row["novelty"] = {"ref": novelty.ref_tag(ref_meta), "novel": wl not in ref_hashes,
                      "nn_sim": round(nn, 4), "nearest": who}

    spec_name, why = SPEC_OF.get(cid, ("wifi24", "default"))
    row["spec"] = {"name": spec_name, "why": why}
    try:
        from spec import Spec
        passed, scrit = Spec.load(spec_name).structural_screen(topo)
        row["spec"]["l0_pass"] = bool(passed)
        row["spec"]["l0_missed"] = sorted(k for k, v in scrit.items() if not v)
    except Exception as exc:
        row["spec"]["l0_error"] = str(exc)

    if not run:
        row["ingested"] = True
        row["gates"]["ngspice"] = {"ok": None, "note": "--audit: not simulated"}
        return row

    ok, note, s11, s21 = sanity_sim(topo)
    row["gates"]["ngspice"] = {"ok": ok, "note": note,
                               "s11_min_db": s11, "s21_max_db": s21}
    if not ok:
        row["quarantine_reason"] = f"ngspice: {note}"
        return row

    row["l1"] = l1_label(topo, cid, log=log)
    row["l2"] = l2_label(topo, cid, spec_name, seed=seed, log=log)
    row["ingested"] = True
    return row


def run(only=None, do_run=True, seed=1, log=True, out=B.EXTERNAL_MANIFEST):
    circuits, t0 = [], time.time()
    for cid, d in B.external_dirs(only):
        t1 = time.time()
        r = ingest_one(cid, d, run=do_run, seed=seed, log=log)
        r["seconds"] = round(time.time() - t1, 1)
        circuits.append(r)
        verdict = "INGESTED" if r["ingested"] else "QUARANTINED"
        print(f"  {cid:<22} {verdict:<12} "
              f"score {r.get('graph', {}).get('lna_score', '-')}/5  "
              f"{r.get('quarantine_reason', '')}", flush=True)

    manifest = {
        "recipe": B.INGEST_RECIPE,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git_sha": ds.git_sha(),
        "augmentation": {"ladder": B.EXT_BUDGET_LADDER,
                         "timeout_s": B.EXT_TIMEOUT_S, "pad": B.SEQ_PAD,
                         "note": "per-circuit budget is in each row's "
                                 "gates.augmentation.budget"},
        "zoaf": dict(INGEST_ZOAF, inductor_q=INDUCTOR_Q),
        "n_attempted": len(circuits),
        "n_ingested": sum(1 for c in circuits if c["ingested"]),
        "n_quarantined": sum(1 for c in circuits if not c["ingested"]),
        "circuits": circuits,
    }
    if do_run and only is None:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(manifest, fh, indent=1)
        print(f"\nwrote {out}")
    print(f"{manifest['n_ingested']} ingested / {manifest['n_quarantined']} "
          f"quarantined of {manifest['n_attempted']} in {time.time()-t0:.1f}s")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true",
                    help="no ngspice: provenance/structure/vocab/screen only")
    ap.add_argument("--run", action="store_true",
                    help="full ladder incl. ngspice, L1, L2; writes the manifest")
    ap.add_argument("--id", action="append", default=None,
                    help="restrict to these ids (repeatable; skips the manifest)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-log", action="store_true",
                    help="do not append L1/L2 rows to the label store")
    args = ap.parse_args()
    if not (args.audit or args.run):
        ap.error("pass --audit or --run")
    run(only=args.id, do_run=args.run, seed=args.seed, log=not args.no_log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
