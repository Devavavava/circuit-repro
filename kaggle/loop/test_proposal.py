"""test_proposal.py -- verify the proposal parser + round-trip on this box.

This is the ONE piece the scaffold must prove locally (the driver runs on
Kaggle). It feeds netlists straight out of lna/templates.py's archetype
constructors through the proposal format and asserts:

  1. parse() accepts every rendered archetype;
  2. netlist -> tokens -> Topology is valid;
  3. the WL hash from the proposal path == the WL hash templates.py computes
     directly from its own emit_sequence (round-trip is graph-identical);
  4. strict parse rejects malformed proposals with the line quoted.

Run (from a checkout that has AnalogGenie/repo + pandas):
    source env.sh && export LNA_DEPS_ROOT=<repo-root>
    python kaggle/loop/test_proposal.py

Exit 0 = all pass. Uses only stdlib + the repo (numpy/pandas come via the repo).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proposal as P     # noqa: E402


def _repo_lna():
    root = os.environ.get("LNA_DEPS_ROOT")
    if not root:
        sys.exit("LNA_DEPS_ROOT not set (need the repo clone with AnalogGenie/repo)")
    lna = os.path.join(root, "lna")
    if lna not in sys.path:
        sys.path.insert(0, lna)
    return lna


def _sample_netlists():
    """A spread of templates.py archetypes as internal read_netlist rows, each
    tagged with the WL hash templates computes from its own emit_sequence."""
    _repo_lna()
    import templates as T
    from topology import Topology
    from novelty import wl_features
    builders = [
        ("cs_tapped_degen", T.cs_lna(True, True, False, False, "tapped", False)),
        ("cs_R_plain", T.cs_lna(True, False, False, False, "R", False)),
        ("cs_tank_cascode", T.cs_lna(True, False, False, True, "tank", False)),
        ("cs_tapped_buffer", T.cs_lna(True, True, True, False, "tapped", True)),
        ("cg_R", T.cg_lna("R", False)),
        ("cg_shunt_peak_cc", T.cg_lna("shunt_peak", True)),
        ("rfb_R", T.rfb_lna("R", False, False)),
        ("rfb_tank_buf", T.rfb_lna("tank", True, False)),
        ("cs_cs_tapped", T.cs_cs_lna(True, "tapped", "tapped", False)),
        ("current_reuse", T.current_reuse_lna("tapped", False)),
        ("rfb_cs_tank", T.rfb_cs_lna("tank", False, False)),
        ("rfb_cs3_tapped", T.rfb_cs3_lna("tapped", cascode2=True, buffer=False)),
        ("gmb_cg", T.gmb_cg_lna(1, "tank", True)),
        ("nc_cgcs", T.nc_cgcs_lna(1, "tank")),
    ]
    out = []
    for name, nl in builders:
        seq = T.emit_sequence(nl)
        if seq is None:
            out.append((name, nl, None))       # augmentation gave no path
            continue
        wl = wl_features(Topology(seq))[0]
        out.append((name, nl, wl))
    return out


def test_round_trip():
    _repo_lna()
    samples = _sample_netlists()
    n_ok = 0
    for name, nl, wl_ref in samples:
        # render internal rows -> proposal text -> parse back
        text = P.rows_to_text(nl)
        rows, ports = P.parse(text)
        assert len(rows) == len(nl), f"{name}: row count changed on parse"
        info = P.round_trip(text)
        assert info["ok"], f"{name}: round_trip not ok: {info['error']}"
        assert info["valid"], f"{name}: topology invalid: {info['error']}"
        if wl_ref is not None:
            assert info["wl_hash"] == wl_ref, (
                f"{name}: WL hash drift proposal={info['wl_hash']} "
                f"templates={wl_ref}")
        n_ok += 1
        print(f"  PASS {name:<20} n_dev={info['n_devices']} "
              f"wl={info['wl_hash'][:12]}")
    print(f"[round-trip] {n_ok}/{len(samples)} archetypes round-tripped "
          f"WL-hash-exact")
    return n_ok


def test_strict_rejects():
    bad = [
        ("unknown type", "FOO m1 a b"),
        ("too few nodes", "NMOS m1 d g s"),
        ("too many nodes", "R r1 a b c"),
        ("bad name", "C 1cap a b"),
        ("bad node", "L l1 a b!"),
        ("empty", "# only a comment\n\n"),
        ("duplicate name", "R r1 a b\nR r1 c d"),
    ]
    for label, txt in bad:
        try:
            P.parse(txt)
        except P.ParseError as e:
            print(f"  PASS reject: {label:<16} -> {str(e)[:60]}")
            continue
        raise AssertionError(f"strict parse should have rejected: {label!r}")
    print(f"[strict] {len(bad)}/{len(bad)} malformed proposals rejected")


def test_ground_alias():
    """'0' must alias to VSS so a proposal can use either spelling."""
    _repo_lna()
    rows, ports = P.parse("NMOS m1 d g 0 0\nR r1 VDD d\nC c1 d VOUT1\nC ci VIN1 g")
    # every '0' became VSS in the rows
    flat = [tok for row in rows for tok in row]
    assert "0" not in flat, "'0' not normalized to VSS"
    assert "VSS" in flat, "VSS missing after normalization"
    print("  PASS ground-alias: '0' -> VSS")


def main():
    print("== proposal round-trip (templates.py archetypes) ==")
    test_round_trip()
    print("\n== strict rejection ==")
    test_strict_rejects()
    print("\n== ground alias ==")
    test_ground_alias()
    print("\nALL PROPOSAL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
