"""engineer/mem_playbook.py -- the sidecar that consults the playbook store
hermetically, WITHOUT ever editing or mutating `lna/playbook.py` or `lna/playbook/`.

Charter hard constraint (E-3): the playbook store under `lna/playbook/` is NEVER
mutated by the harness, and cold mode must be HERMETIC -- an empty/temp store
injected, not achieved by moving or emptying real files. `lna/playbook.py`'s
`ROOT`/`ENTRY_DIR`/`EDGES`/`INDEX` are module attributes, so the store path can be
pointed elsewhere by rebinding those attributes -- the house sidecar pattern named
in the constraint -- with no edit to `lna/` at all.

TWO MODES, ONE READ-ONLY API
----------------------------
`consult(family, analysis, failure_signatures, keywords, cold=False)`:

  * warm (cold=False): reads the REAL store through `playbook.load_entries` /
    `playbook.score_entry` with the module attributes UNCHANGED. Read-only: this
    module calls no writer (`_write_entry`, `append_edge`, `write_index`, `cmd_add`,
    `cmd_escalate`) -- it only loads and scores.
  * cold (cold=True): inside `_store(empty=True)` the attributes are rebound to an
    EMPTY temp directory for the duration of the load, then restored. The real
    store's files are never opened for writing and never moved; `git status
    lna/playbook` is clean before and after (asserted by the harness).

Each consult returns a `Consult` carrying the ranked hits, the qualifying hit (the
one the E3-MEMORY.md rule maps to a start count K), and a `store_fingerprint`
(n_entries + a sha256 over the exact entry-file bytes it read) so a cold cell can
be PROVEN empty and a warm cell can be pinned to the store bytes it saw.
"""
import contextlib
import hashlib
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
_LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
if _LNA not in sys.path:
    sys.path.insert(0, _LNA)

import playbook as PB                                          # noqa: E402  (read-only)

# The E3-MEMORY.md 2.2 qualification predicate + score->K map, frozen there.
_INIT_KEYWORDS = ("multi-start", "seed", "coordinate", "descent", "basin",
                  "log-uniform")
_QUALIFYING_TYPES = ("strategy", "anti-pattern")


def _score_to_k(score):
    """E3-MEMORY.md 2.2 score->K table (pre-registered, do not retune here)."""
    if score is None:
        return 1
    if score >= 11:
        return 6
    if score >= 6:
        return 4
    if score >= 1:
        return 2
    return 1


@contextlib.contextmanager
def _store(empty):
    """Temporarily point playbook at an empty temp store (empty=True) or leave the
    real one bound (empty=False). Restores the module attributes on exit either
    way. NEVER writes to the real store; the temp dir is the only thing created."""
    saved = (PB.ENTRY_DIR, PB.EDGES, PB.INDEX, PB.ROOT)
    tmp = None
    try:
        if empty:
            tmp = tempfile.mkdtemp(prefix="pb_cold_")
            os.makedirs(os.path.join(tmp, "entries"), exist_ok=True)
            PB.ROOT = tmp
            PB.ENTRY_DIR = os.path.join(tmp, "entries")
            PB.EDGES = os.path.join(tmp, "edges.jsonl")
            PB.INDEX = os.path.join(tmp, "index.json")
        yield
    finally:
        PB.ENTRY_DIR, PB.EDGES, PB.INDEX, PB.ROOT = saved[0], saved[1], saved[2], saved[3]
        if tmp is not None:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


def _fingerprint():
    """(n_entries, sha256 over the sorted entry-file bytes) of whatever store is
    currently bound -- the exact bytes a consult read. Cold => (0, sha of empty)."""
    h = hashlib.sha256()
    paths = PB.entry_paths()
    for p in paths:
        with open(p, "rb") as fh:
            h.update(os.path.basename(p).encode("utf-8"))
            h.update(fh.read())
    return {"n_entries": len(paths), "sha256": h.hexdigest()}


class Consult(object):
    """The result of one playbook consultation: ranked hits, the qualifying hit
    (mapped to a start count K by the pre-registered rule), and the fingerprint."""

    def __init__(self, query, hits, fingerprint, cold):
        self.query = query
        self.hits = hits                    # [(score, id, entry, why), ...] sorted
        self.fingerprint = fingerprint
        self.cold = cold
        self.qualifying = self._first_qualifying()
        self.k = _score_to_k(self.qualifying["score"] if self.qualifying else None)

    def _first_qualifying(self):
        """First ranked hit that satisfies E3-MEMORY.md 2.2's qualification."""
        for score, eid, e, why in self.hits:
            trig = e.get("trigger", {})
            an = [s.lower() for s in PB.as_list(trig.get("analysis"))]
            kws = [s.lower() for s in PB.as_list(trig.get("keywords"))]
            if (e.get("type") in _QUALIFYING_TYPES
                    and ({"sizing", "search"} & set(an))
                    and (set(_INIT_KEYWORDS) & set(kws))):
                return {"id": eid, "score": score, "type": e.get("type"),
                        "rule": e.get("rule"), "confidence": e.get("confidence"),
                        "matched": why,
                        "sources": e.get("sources", [])}
        return None

    def as_dict(self):
        return {
            "query": self.query, "cold": self.cold,
            "store_fingerprint": self.fingerprint,
            "n_hits": len(self.hits),
            "top_hits": [{"id": eid, "score": s, "type": e.get("type"),
                          "confidence": e.get("confidence")}
                         for s, eid, e, _ in self.hits[:5]],
            "qualifying": self.qualifying,
            "K": self.k,
        }


def consult(family, analysis, failure_signatures, keywords, cold=False,
            top=6):
    """Run one consultation. Returns a `Consult`. Read-only toward the real store;
    cold=True runs against an empty temp store (hermetic)."""
    q = {
        "failure_signature": [s.strip().lower() for s in failure_signatures if s.strip()],
        "family": [s.strip().lower() for s in family if s.strip()],
        "analysis": [s.strip().lower() for s in analysis if s.strip()],
        "keywords": [s.strip().lower() for s in keywords if s.strip()],
    }
    with _store(empty=cold):
        fingerprint = _fingerprint()
        entries = PB.load_entries()
        hits = []
        for eid, e in sorted(entries.items()):
            s, why = PB.score_entry(e, q)
            # same "meaningful hit" floor cmd_consult uses (beat the verified bonus)
            floor = PB.W_VERIFIED if e.get("confidence") == "verified" else 0
            if s > floor:
                hits.append((s, eid, e, why))
        hits.sort(key=lambda r: (-r[0], r[1]))
        hits = hits[:top]
    return Consult(q, hits, fingerprint, cold)
