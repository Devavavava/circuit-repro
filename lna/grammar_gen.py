"""GR / GR+RAG -- the no-learning generator arms (WP-ATTRIB, plans2/10).

The program has never had a no-learning baseline. Every "the generator did X"
claim in the record is therefore un-attributed: nobody has measured what the
SAME harness (L0 screen, rule-based bias, rung-0 selection, critic, ZOAF sizing)
produces when the candidate stream carries no learned content at all.

This module is that stream. It samples a circuit GRAPH -- a random device
multiset inside a spec's device budget, wired uniformly at random -- and
serializes it through the identical upstream Eulerian pipeline the 50-circuit
corpus, the 148 archetypes, the 9 ingested externals and moves.py's mutants all
use (build_connection_matrix -> dfs_all_paths, via templates.emit_sequence). No
hand-rolled token walk exists anywhere in this file.

WHAT IS AND IS NOT A RULE HERE
------------------------------
The only well-formedness rules applied are the ones REQUIRED for a decodable,
simulable circuit. Each is justified by a mechanism, never by "helps LNAs":

  connected device-pin graph   dfs_all_paths must cover every directed edge
                               starting from VSS; a disconnected graph has NO
                               covering traversal and emit_sequence returns None.
  a terminal on VSS            the traversal's start_node is VSS; with nothing
                               there, VSS is isolated and no sequence exists.
  a terminal on VIN* / VOUT*   the representation encodes ports AS NETS. A net
                               no pin touches never appears in the token stream,
                               so the design is not a decodable two-port and
                               to_spice has nothing to drive or measure.
  two terminals on an internal a one-terminal node is a floating node, i.e. an
  node                         ngspice singular matrix. Not simulable.
  per-kind instance count      NM/PM 34, R 27, C 15, L 23. A 16th capacitor
  inside the frozen vocabulary would emit the token C16, which is NOT one of the
                               1005 tokens. Outside the representation entirely.
  device count in the spec's   the budget the arm is being compared inside.
  device_budget

DELIBERATELY ABSENT: archetype fragments, motif preferences (no source-driven
input bias), device-ratio priors (no inductor targeting -- max_inductors is an
L0 criterion and enforcing it here would manufacture the pass rate being
measured), bulk-to-rail conventions, and any notion of gate/drain/source roles.
Device kinds are uniform over NM, PM, R, C, L; EVERY pin, MOS bulk included,
is assigned uniformly at random.

ONE RECORDED RESTRICTION. Bipolars are in the vocabulary and to_spice has
emitted them since FINDINGS 19, but they are excluded from the kind set because
two HARNESS gaps would otherwise be what this arm measures rather than the
grammar: topology.lna_score / spec.structural_screen count has_transistor as MOS
only (19.1 gap a), and bias.py has no base-bias rule (19.1 gap b). Recorded as a
deviation from "pure syntax", not hidden.

    python lna/grammar_gen.py --arm gr  --n 128 --seed 1337 --out lna/out/gr_s1337
    python lna/grammar_gen.py --arm rag --n 128 --seed 1337 --out lna/out/rag_s1337
    python lna/grammar_gen.py --selftest
"""
import argparse
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from topology import PIN_RE, Topology, is_device  # noqa: E402

PORTS = ["VDD", "VSS", "VIN1", "VOUT1"]
# VSS: dfs_all_paths' start_node. VIN1/VOUT1: the port encoding. VDD is NOT
# required -- a design with no supply connection is a legal (bad) passive
# network, and forcing one would be a prior about what an amplifier looks like.
REQUIRED_PORTS = ("VSS", "VIN1", "VOUT1")

KIND_PINS = {"NM": ["D", "G", "S", "B"], "PM": ["D", "G", "S", "B"],
             "R": ["P", "N"], "C": ["P", "N"], "L": ["P", "N"]}
KIND_TYPE = {"NM": "nmos4", "PM": "pmos4", "R": "resistor",
             "C": "capacitor", "L": "inductor"}
# genie_common.build_vocab's per-prefix ranges (NM/PM 1..34, R 1..27, C 1..15,
# L 1..23). Held as literals so this file stays torch-free; --selftest
# cross-checks them against the real vocabulary under the analoggenie python.
KIND_CAP = {"NM": 34, "PM": 34, "R": 27, "C": 15, "L": 23}
KINDS = ("NM", "PM", "R", "C", "L")

LNA_INDICES = list(range(461, 493)) + list(range(1081, 1091))
MAX_REPAIR_ROUNDS = 400


def sample_kinds(rng, budget):
    """Uniform device count in the spec's budget, uniform kind per device,
    rejecting only multisets outside the frozen vocabulary's capacity."""
    lo, hi = budget
    for _ in range(64):
        n = rng.randint(lo, hi)
        kinds = [rng.choice(KINDS) for _ in range(n)]
        c = Counter(kinds)
        if all(c[k] <= KIND_CAP[k] for k in c):
            return kinds
    return None


def _pin_list(kinds):
    return [(i, p) for i, k in enumerate(kinds) for p in KIND_PINS[k]]


def random_assign(rng, kinds, fixed=None, extra_nodes=()):
    """Assign every pin uniformly at random over the node pool.

    The pool is the four port nets plus K internal nodes, K uniform over the
    range a two-terminal-per-node wiring could fill, plus any nodes a retrieved
    seed already contributes. Pins in `fixed` are left where the seed put them."""
    fixed = dict(fixed or {})
    pins = _pin_list(kinds)
    n_pins = len(pins)
    K = rng.randint(1, max(1, n_pins // 2))
    nodes = list(PORTS) + list(extra_nodes) + [f"g{j}" for j in range(1, K + 1)]
    assign = dict(fixed)
    for pp in pins:
        if pp not in assign:
            assign[pp] = rng.choice(nodes)
    return assign


def _by_node(assign):
    d = defaultdict(list)
    for pp, node in assign.items():
        d[node].append(pp)
    return d


def _components(kinds, assign):
    """Union-find over nodes joined by a shared device; returns {node: root}."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, k in enumerate(kinds):
        ns = [assign[(i, p)] for p in KIND_PINS[k]]
        for n in ns[1:]:
            union(ns[0], n)
    return {n: find(n) for n in set(assign.values())}


def _donor_pin(rng, assign, free, exclude_node):
    """A FREE pin on a node that can spare it: an internal node with 3+ pins or
    a port with 2+. Moving one can never create a new floating node."""
    by = _by_node(assign)
    cands = []
    for node, pps in by.items():
        if node == exclude_node:
            continue
        floor = 2 if node in PORTS else 3
        if len(pps) >= floor:
            cands.extend(pp for pp in pps if pp in free)
    return rng.choice(cands) if cands else None


def repair(rng, kinds, assign, free=None):
    """Minimal repair to the validity rules; None if the draw is unrepairable
    without moving a seeded pin.

    `free` is the set of pins the repair may move: all of them for GR, all
    except the retrieved seed's for GR+RAG."""
    assign = dict(assign)
    free = set(free) if free is not None else set(assign)
    for _ in range(MAX_REPAIR_ROUNDS):
        by = _by_node(assign)

        dangling = [n for n, pps in by.items() if n not in PORTS and len(pps) == 1]
        if dangling:                              # R1: floating node
            node = rng.choice(dangling)
            pin = by[node][0]
            if pin in free:                       # dissolve it
                others = [n for n in by if n != node]
                assign[pin] = rng.choice(others)
            else:                                 # seeded: pull a free pin in
                donor = _donor_pin(rng, assign, free, node)
                if donor is None:
                    return None
                assign[donor] = node
            continue

        empty = [p for p in REQUIRED_PORTS if p not in by]
        if empty:                                 # R2: unencodable port
            donor = _donor_pin(rng, assign, free, empty[0])
            if donor is None:
                return None
            assign[donor] = empty[0]
            continue

        comp = _components(kinds, assign)
        main = comp.get("VSS") or comp[assign[(0, KIND_PINS[kinds[0]][0])]]
        off = sorted({n for n, r in comp.items() if r != main})
        if off:                                   # R3: uncoverable graph
            off_pins = [pp for pp, n in sorted(assign.items())
                        if comp.get(n) != main and pp in free]
            main_nodes = sorted(n for n, r in comp.items() if r == main)
            if off_pins:
                assign[rng.choice(off_pins)] = rng.choice(main_nodes)
            else:
                donor = _donor_pin(rng, assign, free, None)
                if donor is None or comp.get(assign[donor]) != main:
                    return None
                assign[donor] = rng.choice(off)
            continue
        return assign
    return None


def check_valid(kinds, assign):
    """The rule table, re-checked independently of how the wiring was made."""
    by = _by_node(assign)
    for node, pps in by.items():
        if node not in PORTS and len(pps) < 2:
            return False, f"floating node {node}"
    for p in REQUIRED_PORTS:
        if p not in by:
            return False, f"required port {p} has no terminal"
    if len(set(_components(kinds, assign).values())) != 1:
        return False, "disconnected"
    for k, v in Counter(kinds).items():
        if v > KIND_CAP[k]:
            return False, f"{k} count {v} exceeds vocabulary capacity"
    return True, "ok"


def to_netlist(kinds, assign):
    """read_netlist form: [name, one net per pin in order, type]. The name is
    cosmetic -- build_connection_matrix renumbers instances by type order."""
    return [[f"X{i}"] + [assign[(i, p)] for p in KIND_PINS[k]] + [KIND_TYPE[k]]
            for i, k in enumerate(kinds)]


# ------------------------------------------------------------ RAG retrieval
def corpus_seeds(spec, indices=LNA_INDICES):
    """[(index, [traversal tokens...])] over corpus LNAs eligible as generation
    seeds under the spec's own seed_filter -- the identical predicate the
    conditioned-generation path uses (spec.py view 3)."""
    import numpy as np
    repo = os.path.abspath(os.path.join(HERE, "..", "AnalogGenie", "repo"))
    out = []
    for i in indices:
        p = os.path.join(repo, "Dataset", str(i), f"Sequence_total{i}.npy")
        if not os.path.exists(p):
            continue
        arr = np.load(p, allow_pickle=True)
        topo = Topology([str(t) for t in arr[0]])
        if not spec.seed_filter(topo):
            continue
        for row in arr:
            toks = [str(t) for t in row]
            if "TRUNCATE" in toks:
                toks = toks[:toks.index("TRUNCATE")]
            if len(toks) >= 24:
                out.append((i, toks))
    return out


def _base(tok):
    return "".join(ch for ch in tok if not ch.isdigit())


def seed_subgraph(prefix):
    """Decode a token PREFIX into the partial graph it carries.

    Returns (kinds, fixed, seed_nodes), where `kinds` lists the seed's devices
    in first-appearance order, `fixed` maps (device_index, pin) -> node name for
    every pin the prefix actually places, and `seed_nodes` are the node names
    the prefix's own electrical groups occupy. Grouping is union-find over
    adjacent non-device token pairs -- byte-identical to Topology's own rule.

    A group containing one of the four port nets takes that port's name. The
    program's other structural nets (VB*, VCM*, ...) are not in the four-port
    list templates.emit_sequence serializes against, so they become ordinary
    internal nodes: the arm is a GRAPH-level seed, and this is recorded.

    None if the prefix carries a device kind outside this arm's kind set."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    order = []
    for t in prefix:
        if is_device(t) and t not in order:
            if _base(t) not in KIND_PINS:
                return None
            order.append(t)
    if not order:
        return None
    devset = set(order)
    for a, b in zip(prefix, prefix[1:]):
        if a in devset or b in devset:
            continue
        union(a, b)

    groups = defaultdict(set)
    for t in prefix:
        if t in devset:
            continue
        groups[find(t)].add(t)
    root_name, seed_nodes = {}, []
    for j, (root, members) in enumerate(sorted(groups.items(),
                                               key=lambda kv: min(kv[1]))):
        port = next((p for p in PORTS if p in members), None)
        name = port if port else f"s{j + 1}"
        root_name[root] = name
        if not port:
            seed_nodes.append(name)

    idx = {d: i for i, d in enumerate(order)}
    fixed = {}
    for t in prefix:
        m = PIN_RE.match(t)
        if not m or m.group("dev") not in idx:
            continue
        pin = m.group("pin")
        if pin not in KIND_PINS[_base(m.group("dev"))]:
            return None
        fixed[(idx[m.group("dev")], pin)] = root_name[find(t)]
    return [_base(d) for d in order], fixed, seed_nodes


# ---------------------------------------------------------------- sampling
def sample_graph(rng, budget, seed_pool=None, prefix_lens=(12, 24), tries=200):
    """One (kinds, assign, info) draw, or None if `tries` draws all fail repair.

    With `seed_pool` this is GR+RAG: a retrieved corpus traversal's opening
    K tokens (K uniform over prefix_lens) are decoded to a partial graph, its
    devices and placed pins are FIXED, and the random sampler completes the rest
    inside the same device budget."""
    for attempt in range(tries):
        info = {"attempt": attempt}
        if seed_pool:
            src, toks = seed_pool[rng.randrange(len(seed_pool))]
            klen = rng.randint(prefix_lens[0], prefix_lens[1])
            sub = seed_subgraph(toks[:klen])
            if sub is None:
                continue
            seed_kinds, fixed, seed_nodes = sub
            lo, hi = budget
            if len(seed_kinds) > hi:
                continue
            n = rng.randint(max(lo, len(seed_kinds)), hi)
            extra = sample_kinds(rng, (n - len(seed_kinds), n - len(seed_kinds))) \
                if n > len(seed_kinds) else []
            if extra is None:
                continue
            kinds = list(seed_kinds) + list(extra)
            c = Counter(kinds)
            if any(c[k] > KIND_CAP[k] for k in c):
                continue
            free = set(_pin_list(kinds)) - set(fixed)
            assign = random_assign(rng, kinds, fixed=fixed, extra_nodes=seed_nodes)
            info.update(seed_circuit=src, prefix_len=klen,
                        seed_devices=len(seed_kinds), seed_pins=len(fixed))
        else:
            kinds = sample_kinds(rng, budget)
            if kinds is None:
                continue
            free = None
            assign = random_assign(rng, kinds)
            info.update(seed_circuit=None, prefix_len=0, seed_devices=0,
                        seed_pins=0)
        rep = repair(rng, kinds, assign, free=free)
        if rep is None:
            continue
        ok, why = check_valid(kinds, rep)
        if not ok:
            continue
        info["n_devices"] = len(kinds)
        info["n_nodes"] = len(set(rep.values()))
        return kinds, rep, info
    return None


def emit(arm, n, seed, out, spec_name="wifi24", prefix_lens=(12, 24),
         verbose=True):
    """Sample `n` circuits and write them as seq*.txt + meta.json, in exactly
    the on-disk shape generate.py / finetune.sample produce, so novelty.evaluate
    / screen.py / search.py consume this pool with no special case."""
    import templates as T
    from spec import Spec
    spec = Spec.load(spec_name)
    budget = tuple(spec.topology.get("device_budget", [3, 16]))
    rng = random.Random(seed)
    seed_pool = corpus_seeds(spec) if arm == "rag" else None
    if arm == "rag" and not seed_pool:
        raise SystemExit("no corpus LNA passes the spec's seed_filter")
    os.makedirs(out, exist_ok=True)
    meta, stats, t0 = [], Counter(), time.time()
    produced = 0
    while produced < n:
        stats["proposals"] += 1
        g = sample_graph(rng, budget, seed_pool=seed_pool, prefix_lens=prefix_lens)
        if g is None:
            stats["unrepairable"] += 1
            continue
        kinds, assign, info = g
        stats["repaired_ok"] += 1
        try:
            seq = T.emit_sequence(to_netlist(kinds, assign))
        except Exception as e:                                    # noqa: BLE001
            stats["emit_exception"] += 1
            stats[f"exc:{type(e).__name__}"] += 1
            continue
        if not seq:
            stats["no_traversal"] += 1
            continue
        topo = Topology(seq)
        if not topo.valid:
            stats["invalid_decode"] += 1
            continue
        stats["emitted"] += 1
        path = os.path.join(out, f"seq{produced:04d}.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("->".join(seq) + "->")
        meta.append({"file": os.path.basename(path), "terminated": True,
                     "circuit_tokens": len(seq), "n_devices": topo.n_devices,
                     "n_inductors": topo.n_inductors,
                     "source_circuit": info.get("seed_circuit"),
                     "prefix_len": info.get("prefix_len"),
                     "seed_devices": info.get("seed_devices"),
                     "seed_pins": info.get("seed_pins"),
                     "repair_attempt": info["attempt"]})
        produced += 1
        if verbose and produced % 32 == 0:
            print(f"  [{produced}/{n}] {time.time() - t0:.0f}s", flush=True)
    obj = {"arm": f"grammar-{arm}", "generator": "grammar_gen.py", "seed": seed,
           "spec": spec_name, "device_budget": list(budget),
           "kinds": list(KINDS), "prefix_lens": list(prefix_lens),
           "learned_content": "none",
           "stats": dict(stats), "wall_s": round(time.time() - t0, 1),
           "meta": meta}
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(obj, fh, indent=2)
    if verbose:
        print(f"{arm}: {produced} circuits -> {out} in {obj['wall_s']}s; "
              f"stats {dict(stats)}")
    return obj


# ---------------------------------------------------------------- selftest
def selftest(n=40):
    """Mechanism checks only -- nothing here measures an arm.

    1. the vocabulary-capacity literals match the real vocabulary (skipped
       without torch; run under the analoggenie python to exercise it);
    2. every emitted graph re-parses, is Topology.valid, and satisfies the rule
       table when re-derived from the DECODED topology rather than from the
       assignment the sampler built;
    3. GR+RAG's retrieved devices all survive into the emitted circuit."""
    from spec import Spec
    print("== 1. vocabulary capacity ==")
    try:
        from genie_common import DEVICES
        real = Counter()
        for d in DEVICES:
            b = _base(d)
            if b in KIND_CAP and "_" not in d:
                real[b] += 1
        bad = [k for k in KIND_CAP if real[k] != KIND_CAP[k]]
        print(f"   measured {dict(real)} vs literals {KIND_CAP} -> "
              f"{'MATCH' if not bad else 'MISMATCH ' + str(bad)}")
        if bad:
            return 1
    except Exception as e:                                        # noqa: BLE001
        print(f"   skipped (torch-free env): {e}")

    print("== 2. GR: emit -> decode -> re-check the rule table ==")
    spec = Spec.load("wifi24")
    budget = tuple(spec.topology.get("device_budget", [3, 16]))
    rng = random.Random(20260811)
    import templates as T
    ok = 0
    for _ in range(n):
        g = sample_graph(rng, budget)
        assert g is not None, "sample_graph exhausted its tries"
        kinds, assign, _ = g
        seq = T.emit_sequence(to_netlist(kinds, assign))
        assert seq, "no traversal for a graph the repair declared connected"
        topo = Topology(seq)
        assert topo.valid, "decoded topology invalid"
        assert topo.n_devices == len(kinds), (topo.n_devices, len(kinds))
        assert budget[0] <= topo.n_devices <= budget[1]
        assert topo.has_net("VIN") and topo.has_net("VOUT")
        assert not topo.has_floating_subcircuit
        for root, members in topo.nodes.items():
            nets = [m for m in members if m in topo.nets]
            pins = [m for m in members if PIN_RE.match(m)]
            if not nets:
                assert len(pins) >= 2, f"decoded floating node {members}"
        ok += 1
    print(f"   {ok}/{n} GR draws emit, decode, and satisfy the rule table")

    print("== 3. GR+RAG: the retrieved devices survive ==")
    pool = corpus_seeds(spec)
    print(f"   seed pool: {len(pool)} traversals from "
          f"{len({i for i, _ in pool})} seed_filter-eligible corpus LNAs")
    kept = 0
    for _ in range(n):
        g = sample_graph(rng, budget, seed_pool=pool)
        assert g is not None
        kinds, assign, info = g
        seq = T.emit_sequence(to_netlist(kinds, assign))
        assert seq
        topo = Topology(seq)
        assert topo.valid and topo.n_devices == len(kinds)
        assert info["seed_devices"] >= 1
        kept += 1
    print(f"   {kept}/{n} GR+RAG draws emit and decode")
    print("\ngrammar_gen selftest: GREEN")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", choices=["gr", "rag"])
    ap.add_argument("--n", type=int, default=128)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--spec", default="wifi24")
    ap.add_argument("--prefix-lo", type=int, default=12)
    ap.add_argument("--prefix-hi", type=int, default=24)
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.arm or not a.out:
        ap.error("give --arm and --out (or --selftest)")
    emit(a.arm, a.n, a.seed, a.out, spec_name=a.spec,
         prefix_lens=(a.prefix_lo, a.prefix_hi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
