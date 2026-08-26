"""proposal.py -- strict parser + round-trip for the LLM proposal netlist format.

An LLM proposes an LNA as a small line-oriented netlist (see netlist_format.md and
grammar.gbnf). This module turns that text into the repo's internal
`read_netlist` rows -- `[name, net1..netK (pin order), type]` -- which is exactly
what lna/templates.py hands to the upstream AnalogGenie pipeline
(build_connection_matrix -> dfs_all_paths). From there the same
lna/build_lna_corpus shims round-trip the netlist to an AnalogGenie token
sequence that lna/topology.Topology parses back, so a proposal is
indistinguishable from a corpus/template circuit at the point the funnel
consumes it.

Design commitments:
  * stdlib only (no numpy/pandas here); the round-trip helper imports the repo's
    build_lna_corpus lazily, which needs pandas -- so `parse()` works everywhere
    and `to_tokens()` only where the repo funnel already runs.
  * strict: every deviation from the grammar is a ParseError with the offending
    line quoted verbatim (house rule: never summarize evidence). The loop records
    that text untruncated in the trajectory row.
  * pure translation: this file owns NO sizing, screening, or bias logic. It maps
    proposal text <-> the internal netlist row format and drives the repo's own
    round-trip. Everything downstream is the repo's code path.

PROPOSAL LINE FORMAT (one device per line):
    TYPE name node1 node2 [node3 node4]
  TYPE in {NMOS, PMOS, R, C, L}  (case-insensitive)
  name : an identifier unique within the netlist (letters/digits/_)
  nodes: NMOS/PMOS take 4 nodes in order D G S B;  R/C/L take 2 nodes P N
  a node is a net name: reserved VDD VSS VIN1 VOUT1 0, or an internal node
  (any other identifier). '0' is an alias for VSS (ground).

Blank lines and '#'/'*' comment lines are ignored.

    from proposal import parse, to_tokens, round_trip
    rows, ports = parse(text)                 # -> internal read_netlist rows
    tokens = to_tokens(rows, ports)           # -> AnalogGenie token sequence
    info = round_trip(text)                   # parse+tokens+Topology, one call
"""
import os
import re
import sys

# proposal TYPE -> internal read_netlist trailing type token
_TYPE_MAP = {
    "NMOS": "nmos4", "PMOS": "pmos4",
    "R": "resistor", "C": "capacitor", "L": "inductor",
}
# pin count per TYPE (order is significant): MOS = D G S B, passive = P N
_PIN_ORDER = {
    "NMOS": ("D", "G", "S", "B"), "PMOS": ("D", "G", "S", "B"),
    "R": ("P", "N"), "C": ("P", "N"), "L": ("P", "N"),
}
RESERVED_NETS = ("VDD", "VSS", "VIN1", "VOUT1", "0")
PORTS = ["VDD", "VSS", "VIN1", "VOUT1"]      # AnalogGenie port order (templates.PORTS)

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_NET_RE = re.compile(r"^(0|[A-Za-z][A-Za-z0-9_]*)$")


class ParseError(ValueError):
    """A proposal netlist failed strict parsing. Carries the verbatim line."""


def _norm_net(tok):
    """'0' is ground == VSS. Everything else passes through unchanged."""
    return "VSS" if tok == "0" else tok


def parse(text):
    """Strict parse of proposal text -> (rows, ports).

    rows: list of internal read_netlist rows `[name, net1..netK, type]`.
    ports: the AnalogGenie port list actually present (subset of PORTS, in PORTS
           order); VDD/VSS are always included because the funnel + to_spice need
           a supply and a ground even if the proposal omits an explicit rail line.

    Raises ParseError (with the offending line quoted) on any grammar violation,
    duplicate device name, or wrong node count.
    """
    if not isinstance(text, str):
        raise ParseError(f"proposal must be text, got {type(text).__name__}")
    rows = []
    seen_names = set()
    nets_used = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line[0] in "#*":
            continue
        parts = line.split()
        typ = parts[0].upper()
        if typ not in _TYPE_MAP:
            raise ParseError(
                f"line {lineno}: unknown device TYPE {parts[0]!r} "
                f"(allowed: {', '.join(sorted(_TYPE_MAP))}); line: {raw!r}")
        pins = _PIN_ORDER[typ]
        want = 2 + len(pins)               # TYPE name + N nodes
        if len(parts) != want:
            raise ParseError(
                f"line {lineno}: {typ} needs a name and {len(pins)} nodes "
                f"({' '.join(pins)}), got {len(parts) - 2} node(s); line: {raw!r}")
        name = parts[1]
        if not _NAME_RE.match(name):
            raise ParseError(
                f"line {lineno}: bad device name {name!r} "
                f"(letters/digits/underscore, must start with a letter); line: {raw!r}")
        if name in seen_names:
            raise ParseError(
                f"line {lineno}: duplicate device name {name!r}; line: {raw!r}")
        seen_names.add(name)
        nodes = []
        for tok in parts[2:]:
            if not _NET_RE.match(tok):
                raise ParseError(
                    f"line {lineno}: bad node name {tok!r}; line: {raw!r}")
            n = _norm_net(tok)
            nodes.append(n)
            nets_used.add(n)
        rows.append([name] + nodes + [_TYPE_MAP[typ]])
    if not rows:
        raise ParseError("empty proposal: no device lines found")
    # ports actually present, in canonical order; supply+ground always kept
    present = {n for n in PORTS if n in nets_used} | {"VDD", "VSS"}
    ports = [n for n in PORTS if n in present]
    return rows, ports


# ------------------------------------------------------- round-trip to tokens
_FUNCS = None


def _pipeline():
    """Lazily load the repo's AnalogGenie shims (needs pandas + the clone).

    Reuses lna/build_lna_corpus.load_functions exactly like lna/templates.py does,
    so the round-trip is the SAME code path the corpus and templates use. Requires
    LNA_DEPS_ROOT to point at a checkout that has AnalogGenie/repo/ present.
    """
    global _FUNCS
    if _FUNCS is None:
        root = os.environ.get("LNA_DEPS_ROOT")
        if not root:
            raise RuntimeError(
                "LNA_DEPS_ROOT not set -- to_tokens/round_trip need the repo clone "
                "(AnalogGenie shims + build_lna_corpus). Set it to a checkout root.")
        lna_dir = os.path.join(root, "lna")
        if lna_dir not in sys.path:
            sys.path.insert(0, lna_dir)
        import build_lna_corpus as B      # noqa: E402  (needs pandas)
        g = B.load_functions("SPICE2GRAPH_compress.py", "\nstart = 1")
        a = B.load_functions("Augmentation.py", "\nbase_dirs = {")
        _FUNCS = (g["build_connection_matrix"], a["read_connection_matrix"],
                  a["dfs_all_paths"])
    return _FUNCS


def to_tokens(rows, ports=PORTS, max_solutions=1, run_num=1):
    """Internal rows -> one canonical AnalogGenie token sequence (or None).

    Mirrors lna/templates.emit_sequence: build_connection_matrix -> a scratch CSV
    -> read_connection_matrix -> dfs_all_paths(start='VSS'). Uses lna/extract's
    self-deleting scratch dir if available, else a tempfile fallback.
    """
    bcm, rcm, dfs = _pipeline()
    m, _ = bcm(rows, list(ports))
    try:
        from extract import scratch       # repo's self-deleting scratch
        ctx = scratch("propose_")
    except Exception:
        import tempfile
        import contextlib

        @contextlib.contextmanager
        def _tmp(_):
            d = tempfile.mkdtemp(prefix="propose_")
            try:
                yield d
            finally:
                import shutil
                shutil.rmtree(d, ignore_errors=True)
        ctx = _tmp("propose_")
    with ctx as d:
        csv = os.path.join(d, "g.csv")
        m.to_csv(csv)
        paths = dfs(rcm(csv), start_node="VSS", max_solutions=max_solutions,
                    run_num=run_num)
    if not paths:
        return None
    return [str(t) for t in paths[0]]


def round_trip(text):
    """Parse proposal text, round-trip to tokens, and parse back to a Topology.

    Returns a dict:
      {"ok": bool, "rows", "ports", "tokens", "n_devices", "wl_hash",
       "valid", "error"}
    `error` is a verbatim message on failure (ok=False); the loop stores it
    untruncated. Never raises for a well-typed proposal that simply fails to
    round-trip -- that is a first-class recorded outcome, not an exception.
    """
    out = {"ok": False, "rows": None, "ports": None, "tokens": None,
           "n_devices": None, "wl_hash": None, "valid": None, "error": None}
    try:
        rows, ports = parse(text)
    except ParseError as e:
        out["error"] = f"ParseError: {e}"
        return out
    out["rows"], out["ports"] = rows, ports
    try:
        tokens = to_tokens(rows, ports)
    except Exception as e:                 # upstream augmentation raises broadly
        out["error"] = f"round-trip failed: {type(e).__name__}: {e}"
        return out
    if not tokens:
        out["error"] = "round-trip produced no Eulerian token path from VSS"
        return out
    out["tokens"] = tokens
    root = os.environ["LNA_DEPS_ROOT"]
    lna_dir = os.path.join(root, "lna")
    if lna_dir not in sys.path:
        sys.path.insert(0, lna_dir)
    from topology import Topology          # noqa: E402
    from novelty import wl_features        # noqa: E402
    topo = Topology(tokens)
    out["valid"] = bool(topo.valid)
    out["n_devices"] = topo.n_devices
    out["wl_hash"] = wl_features(topo)[0]
    out["ok"] = out["valid"]
    if not out["valid"]:
        out["error"] = ("topology parsed but is structurally invalid "
                        f"(bad_ctx={topo.bad_device_ctx[:3]}, "
                        f"illegal_pins={topo.illegal_pins[:3]}, "
                        f"orphans={topo.orphan_pins[:3]})")
    return out


def rows_to_text(rows):
    """Render internal read_netlist rows back to proposal text (for exemplars).

    Inverse of parse() at the line level: `[name, nets.., type]` ->
    `TYPE name nets..`. Used to turn stored corpus/template netlists into
    few-shot exemplars in the propose prompt.
    """
    inv = {v: k for k, v in _TYPE_MAP.items()}
    lines = []
    for row in rows:
        name, typ = row[0], row[-1]
        nets = row[1:-1]
        lines.append(" ".join([inv[typ], name] + list(nets)))
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    txt = sys.stdin.read()
    info = round_trip(txt)
    info_print = dict(info)
    if info_print.get("tokens"):
        info_print["tokens"] = "->".join(info_print["tokens"])
    print(json.dumps(info_print, indent=2))
    sys.exit(0 if info["ok"] else 1)
