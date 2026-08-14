"""engineer/test_env.py -- the E-1 API-hardening tests of the `engineer` line.

Charter §6 E-1 wants `env.py` proven as an API someone else can hold, not just one
seam run end to end. Four contracts are asserted here, in the house test style
(`lna/test_vocab_matches_upstream.py`): a plain `main()` that PRINTS what it
checked and `sys.exit(1)` on the first failure. No pytest -- this tree does not
assume it.

    python engineer/test_env.py            # all four
    python engineer/test_env.py --only foreign

WHAT EACH TEST PROVES, AND ITS FALSIFIER
----------------------------------------
  round_trip    `encode` inverts `make_objective`'s `decode` to ~6 sig figs (the
                decode's own print precision), on the pinned deck AND a foreign
                one. Falsifier: a params dict that does not come back to its x.
  foreign       a topology that is NOT the task's pinned one is evaluated through
                `Env` and behaves: metrics returned, harness stamp present, a
                trajectory row written. The topology is produced via `lna/moves.py`
                (read-only import) -- see `_foreign_topology` for why the last
                re-tokenisation step falls back on this box.
  not_sizable   a topology the sizer declines raises `NotSizable` (the documented
                contract, charter E-1 deliverable 3) BEFORE the budget is charged.
  loud_dep      a simulated dep-resolution failure (bogus search roots, in
                process, no files moved) raises loudly, naming the probe and the
                `LNA_DEPS_ROOT` override (charter R-1).
"""
import argparse
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import env as EV                                              # noqa: E402
from env import Env, NotSizable, TrajectoryLogger            # noqa: E402
from tasks import get                                        # noqa: E402

import datastore as ds                                       # noqa: E402
import size as S                                             # noqa: E402
from topology import Topology                                # noqa: E402

TASK = "wifi24-smoke"


# --------------------------------------------------------------------- helpers
def _pinned_wl():
    return get(TASK).wl_hash


def _stored_foreign_row(spec="wifi24"):
    """The smallest stored L2 topology for `spec` whose wl_hash is NOT the pinned
    one and that the sizer accepts -- a genuine foreign, sizable deck."""
    pinned = _pinned_wl()
    rows = [r for r in ds.load("topo_labels")
            if r.get("spec") == spec and (r.get("graph") or {}).get("tokens")
            and r.get("wl_hash") != pinned]
    rows.sort(key=lambda r: len(r["graph"]["tokens"]))
    for r in rows:
        t = Topology(r["graph"]["tokens"])
        if t.valid and S.prepared_body(t, inductor_q=12) is not None:
            return r, t
    raise RuntimeError("no foreign sizable wifi24 topology in the store")


def _foreign_topology(spec_name="wifi24"):
    """A foreign `Topology` produced through `lna/moves.py`, plus a provenance tag.

    The intended path is `moves.mutate` (a structural graph edit) then
    `moves.realize` (Eulerian re-tokenisation) -- and the MUTATION runs here (it
    is netlist algebra, no upstream clone). The re-tokenisation, however, goes
    through AnalogGenie's `SPICE2GRAPH`/`Augmentation` pipeline, which needs both
    the (gitignored) `AnalogGenie/repo` clone and `pandas`; NEITHER is present on
    this RHEL box (E-1 finding -- see the module and the report). So when
    `realize` cannot re-tokenise (it swallows the ImportError and returns None),
    the foreign topology falls back to a stored L2 row's tokens. Either way the
    result is a valid `Topology` with a wl_hash != the pinned one, which is what
    exercises `Env._arena_for` -- the point of the test."""
    import templates as T
    import moves
    from spec import Spec
    spec = Spec.load(spec_name)
    ctx = {"max_dev": spec.topology.get("device_budget", [3, 16])[1],
           "min_dev": spec.topology.get("device_budget", [3, 16])[0],
           "max_inductors": spec.topology.get("max_inductors", 99)}
    row, seed_topo = _stored_foreign_row(spec_name)
    seed_nl, _ports = T.topo_to_netlist(seed_topo)          # no AnalogGenie needed
    rng = random.Random(1)
    move = None
    for _ in range(16):
        mut, mv = moves.mutate(seed_nl, rng, ctx)
        if mv is None:
            continue
        move = mv
        realized = moves.realize(mut, spec)                 # needs the pipeline
        if realized is not None:
            topo, _seq, wl, _canon = realized
            if wl != _pinned_wl() and S.prepared_body(topo, inductor_q=12):
                moves.sweep_tmp()
                return topo, wl, f"moves.{mv} (realized)"
    moves.sweep_tmp()
    # Re-tokenisation unavailable on this box: use the stored foreign topology,
    # after proving the move operators ran (`move` is not None).
    if move is None:
        raise RuntimeError("moves.mutate produced no move -- the move set is broken")
    return seed_topo, row["wl_hash"], f"stored foreign (moves.{move} ran; " \
                                      "realize() needs AnalogGenie+pandas, absent)"


def _ok(msg):
    print(f"  ok: {msg}")


def _fail(msg):
    print(f"  FAIL: {msg}")
    sys.exit(1)


# ----------------------------------------------------------------------- tests
def test_round_trip():
    """encode(decode(x)) == x to the decode's print precision, pinned + foreign."""
    print("round_trip: encode inverts make_objective's decode")
    env = Env(get(TASK), budget=5)
    foreign, wl, tag = _foreign_topology()
    env.evaluate(topology=foreign, params=[0.5] * _dim_of(env, foreign))  # build arena
    checked = 0
    for arena, label in ((env.arena, "pinned"),
                         (env._arena_for(foreign), f"foreign {wl}")):
        rng = random.Random(7)
        worst = 0.0
        for _ in range(200):
            x = [rng.random() for _ in range(arena.dim)]
            params = arena.decode(x)                # dict: fixed + sizable, strings
            x2 = arena.encode(params)               # back to [0,1]^d
            worst = max(worst, max(abs(a - b) for a, b in zip(x, x2)))
        if worst > 1e-4:
            _fail(f"{label}: encode(decode(x)) off by {worst:.2e} (> 1e-4)")
        # decode is a genuine fixpoint on the sizable names (the values it emits)
        x = [rng.random() for _ in range(arena.dim)]
        p1 = arena.decode(x)
        p2 = arena.decode(arena.encode(p1))
        if any(p1[n] != p2[n] for n in arena.names):
            _fail(f"{label}: decode not a fixpoint under encode")
        _ok(f"{label}: d={arena.dim}, max |dx|={worst:.2e}, decode fixpoint holds")
        checked += 1
    if checked != 2:
        _fail("expected to check both the pinned and a foreign deck")
    return True


def test_foreign_topology():
    """A foreign topology evaluates through Env: metrics, stamp, trajectory row."""
    print("foreign: a non-pinned topology runs through Env and behaves")
    foreign, wl, tag = _foreign_topology()
    if wl == _pinned_wl():
        _fail("the 'foreign' topology is the pinned one")
    _ok(f"topology via {tag}; wl={wl} != pinned {_pinned_wl()}")

    # Write to a throwaway path, not the canonical trajectories.jsonl: the test
    # asserts the append-of-one behaviour without polluting the committed table.
    import tempfile
    tmp = os.path.join(tempfile.mkdtemp(prefix="engineer_test_"), "traj.jsonl")
    logger = TrajectoryLogger(path=tmp, run_id="test-foreign",
                              meta={"driver": "test_env"})
    before = _line_count(logger.path)
    env = Env(get(TASK), budget=5, logger=logger)
    dim = _dim_of(env, foreign)
    out = env.evaluate(topology=foreign, params=[0.5] * dim, action="foreign-probe")

    if out["metrics"] is None:
        _fail("foreign eval returned no metrics (silent-None failure mode)")
    for k in ("nf_db", "s11_db", "s21_db", "idd_ma"):
        if k not in out["metrics"]:
            _fail(f"foreign metrics missing {k}")
    _ok(f"metrics returned (obj={out['objective']:.4f}, "
        f"sim_ok={out['sim_ok']}, feasible={out['feasible']})")

    stamp = env.harness()
    if not stamp.get("deps", {}).get("models"):
        _fail("harness stamp has no resolved model-card path")
    _ok(f"harness stamp present (models={os.path.basename(stamp['deps']['models'])}"
        f", era={stamp['era']}, nf_gated={stamp['nf_gated']})")

    after = _line_count(logger.path)
    if after != before + 1:
        _fail(f"expected exactly 1 trajectory row appended, got {after - before}")
    _ok(f"exactly one trajectory row appended ({before} -> {after})")

    # the foreign deck is cached (a second eval builds no new arena)
    n_arenas = len(env._arenas)
    env.evaluate(topology=foreign, params=[0.4] * dim)
    if len(env._arenas) != n_arenas:
        _fail("foreign arena was rebuilt instead of cached")
    _ok(f"foreign arena cached ({n_arenas} arenas, stable across evals)")
    return True


def test_not_sizable():
    """A non-sizable topology raises NotSizable, before the budget is charged."""
    print("not_sizable: the sizer's refusal is an explicit, budget-free contract")
    # A single MOS whose four terminals reach only private internal nets -- valid
    # as a parsed graph, but a floating subcircuit the bias inserter declines, so
    # `size.prepared_body` returns None. (Constructed, not stored: every stored
    # topology passed the structural screen and is sizable by construction.)
    toks = ["n1", "NM1_D", "NM1", "NM1_G", "n2", "NM1_G", "NM1", "NM1_S",
            "n3", "NM1_S", "NM1", "NM1_B", "n1"]
    topo = Topology(toks)
    if not topo.valid:
        _fail("the constructed non-sizable topology does not even parse valid")
    if S.prepared_body(topo, inductor_q=12) is not None:
        _fail("the constructed topology is unexpectedly sizable")
    _ok(f"constructed a valid-but-non-sizable topology (n_devices={topo.n_devices})")

    env = Env(get(TASK), budget=5)
    spent_before = env.n_evals
    try:
        env.evaluate(topology=topo, params=[0.5])
        _fail("evaluate() on a non-sizable topology did not raise")
    except NotSizable as e:
        if getattr(e, "wl_digest", None) is None:
            _fail("NotSizable carries no wl_digest")
        _ok(f"NotSizable raised, wl_digest={e.wl_digest}")
    if env.n_evals != spent_before:
        _fail(f"a non-sizable topology charged {env.n_evals - spent_before} evals")
    _ok(f"no eval charged for the refused topology (still {env.n_evals})")
    # NotSizable IS a ValueError, so an `except ValueError` driver still catches it
    if not issubclass(NotSizable, ValueError):
        _fail("NotSizable is not a ValueError subclass -- breaks existing callers")
    _ok("NotSizable subclasses ValueError (existing except-ValueError still catches)")
    return True


def test_loud_dep():
    """A dep-resolution failure raises loudly, naming the probe and the override.

    Simulated IN PROCESS: `BIND` is cleared and the candidate-root search is
    monkeypatched to a bogus path only. No files are moved; `BIND` is restored in
    a `finally` so the rest of the suite still evaluates."""
    print("loud_dep: resolution failure is impossible to miss (charter R-1)")
    saved = dict(EV.BIND)
    orig = EV._candidate_roots
    EV.BIND.clear()
    EV._candidate_roots = lambda: ["/nonexistent/bogus/deps/root"]
    try:
        EV._bind_runtime_deps()
        _fail("dep resolution against a bogus root did not raise")
    except RuntimeError as e:
        msg = str(e)
        for needle in ("not found", "LNA_DEPS_ROOT", "/nonexistent/bogus/deps/root"):
            if needle not in msg:
                _fail(f"loud message is missing {needle!r}: {msg[:120]}")
        _ok(f"RuntimeError names the probe, the searched root, and the override")
    finally:
        EV._candidate_roots = orig
        EV.BIND.clear()
        EV.BIND.update(saved)
    if not EV.BIND.get("models"):
        _fail("BIND was not restored after the simulated failure")
    _ok("BIND restored (models path present again)")
    return True


# --------------------------------------------------------------------- utils
def _dim_of(env, topo):
    return env._arena_for(topo).dim


def _line_count(path):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh)


TESTS = {"round_trip": test_round_trip, "foreign": test_foreign_topology,
         "not_sizable": test_not_sizable, "loud_dep": test_loud_dep}


def main():
    ap = argparse.ArgumentParser(description="engineer env E-1 tests")
    ap.add_argument("--only", choices=sorted(TESTS),
                    help="run one test instead of all four")
    a = ap.parse_args()
    names = [a.only] if a.only else ["round_trip", "foreign", "not_sizable",
                                     "loud_dep"]
    for name in names:
        TESTS[name]()
    print(f"\nALL {len(names)} E-1 TEST(S) PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
