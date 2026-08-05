"""Load, validate, and *compile* an LNA specification.

A spec (a YAML file in lna/specs/) is the single source of truth for what LNA we
are designing. Nothing in the pipeline reads a spec ad hoc; instead a loaded
`Spec` exposes exactly three views of itself (plans/01-SPEC.md §1, D1):

    spec.structural_screen(topology)  -> (passed, criteria)   # L0, screen.py
    spec.feasible(metrics) / objective(metrics)               # L2, sizing loop
    spec.seed_filter(topology)        -> bool                  # conditioned gen

Design commitments carried from the plan:

  * D2 -- hard `constraints:` (pass/fail) and soft `objectives:` (improve after
    feasible) are structurally separate; they are only blended feasibility-first
    at the ZOAF boundary, and there the `1 +` offset keeps every feasible point
    below every infeasible one.
  * D3 -- every requirement is checked at the earliest stage that can see it.
    structural_screen is L0 (graph only). It never claims a topology "meets NF";
    it claims the topology is not structurally *disqualified*.
  * D4 -- the L0 criteria are DERIVED from spec fields, not hand-written, so one
    screen no longer serves all targets (the H-Q4 59.4% "ceiling" was an
    artefact of that). See `structural_screen` for the derivation table.
  * D5 -- a constraint may carry `status: unsupported`; it is loaded, reported as
    UNMEASURED everywhere, and ignored by the objective (linearity has no harness
    yet).

Only PyYAML + a hand validator -- no pandas/pydantic -- so the WSL and Windows
environments stay identical.

    python lna/spec.py wifi24                 # validate + summary
    python lna/spec.py --all                  # validate every spec in specs/
    python lna/spec.py wideband-sdr --screen-index 487
"""
import argparse
import os
import sys
from collections import OrderedDict, defaultdict, deque

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import Topology, base_of  # noqa: E402

SPECS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specs")

# ---- schema (unknown keys are an error; typo tolerance ships wrong specs) ----
_ALLOWED = {
    "_top": {"name", "description", "process", "band", "ports",
             "constraints", "objectives", "topology", "sizing"},
    "process": {"models", "vdd", "temp"},
    "band": {"type", "f0", "f_lo", "f_hi"},
    "ports": {"z0", "input", "output"},
    "topology": {"differential", "device_budget", "max_inductors",
                 "min_inductor_ratio", "l_min", "l_max", "allow_inductorless"},
    "sizing": {"w_um", "l_fixed", "r_ohm", "c_f", "vb_v"},
    "_constraint": {"min", "max", "status"},
    "_objective": {"metric", "direction", "weight"},
}


class SpecError(ValueError):
    """A spec failed to load or validate. Raised loudly on purpose."""


class Spec(object):
    def __init__(self, data, source="<dict>"):
        self.source = source
        self.raw = data
        self._validate(data)
        self.name = data["name"]
        self.description = data.get("description", "")
        self.process = data.get("process", {})
        self.band = data.get("band", {})
        self.ports = data.get("ports", {})
        self.constraints = OrderedDict(data.get("constraints", {}) or {})
        self.objectives = list(data.get("objectives", []) or [])
        self.topology = data.get("topology", {})
        self.sizing = data.get("sizing", {})

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, name_or_path):
        """Resolve a spec by bare name (looked up in lna/specs/) or by path."""
        path = name_or_path
        if not os.path.exists(path):
            cand = os.path.join(SPECS_DIR, name_or_path)
            for p in (cand, cand + ".yaml", cand + ".yml"):
                if os.path.exists(p):
                    path = p
                    break
            else:
                raise SpecError(f"no spec named {name_or_path!r} (looked in "
                                f"{SPECS_DIR} and as a path)")
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise SpecError(f"{path}: top level must be a mapping")
        return cls(data, source=path)

    # -------------------------------------------------------------- validate
    def _validate(self, d):
        where = self.source

        def unknown(section, keys, allowed):
            bad = set(keys) - allowed
            if bad:
                raise SpecError(f"{where}: unknown key(s) in {section}: "
                                f"{sorted(bad)}; allowed: {sorted(allowed)}")

        if "name" not in d:
            raise SpecError(f"{where}: missing required key 'name'")
        if "topology" not in d:
            raise SpecError(f"{where}: missing required 'topology' section "
                            "(the structural screen is derived from it)")
        unknown("<top level>", d.keys(), _ALLOWED["_top"])
        for sect in ("process", "band", "ports", "topology", "sizing"):
            if sect in d and d[sect] is not None:
                if not isinstance(d[sect], dict):
                    raise SpecError(f"{where}: '{sect}' must be a mapping")
                unknown(sect, d[sect].keys(), _ALLOWED[sect])

        # constraints: arbitrary metric names, but each value a limit dict
        for m, c in (d.get("constraints") or {}).items():
            if not isinstance(c, dict):
                raise SpecError(f"{where}: constraint {m!r} must be a mapping "
                                "like {max: -10} or {min: 12, status: unsupported}")
            unknown(f"constraint {m!r}", c.keys(), _ALLOWED["_constraint"])
            if "min" not in c and "max" not in c:
                raise SpecError(f"{where}: constraint {m!r} sets neither min nor max")
            if c.get("status") not in (None, "unsupported"):
                raise SpecError(f"{where}: constraint {m!r} status must be "
                                "omitted or 'unsupported'")

        for o in (d.get("objectives") or []):
            if not isinstance(o, dict):
                raise SpecError(f"{where}: each objective must be a mapping")
            unknown("objective", o.keys(), _ALLOWED["_objective"])
            if "metric" not in o or "direction" not in o:
                raise SpecError(f"{where}: objective {o} needs 'metric' and 'direction'")
            if o["direction"] not in ("min", "max"):
                raise SpecError(f"{where}: objective {o['metric']!r} direction "
                                "must be 'min' or 'max'")

        b = d.get("band", {}) or {}
        if b.get("type") not in (None, "narrowband", "wideband"):
            raise SpecError(f"{where}: band.type must be narrowband or wideband")

    # ---------------------------------------------------------------- helpers
    @property
    def band_type(self):
        return self.band.get("type", "narrowband")

    @property
    def allow_inductorless(self):
        return bool(self.topology.get("allow_inductorless", False))

    def _resolve_net(self, topo, name):
        """A port net-name may be exact (VIN1) or a prefix (VIN); return the net."""
        if name in topo.nets:
            return name
        for n in sorted(topo.nets):
            if n.startswith(name):
                return n
        return None

    # ================================================================ view 1
    def structural_screen(self, topo):
        """L0 screen, derived from the spec (D4). Returns (passed, criteria).

        Derivation table (only the criteria a spec's fields activate are checked;
        `passed` is the AND of the active ones):

          field                              -> criterion
          --------------------------------------------------------------------
          (always)                           -> has_transistor  (>=1 MOS)
          topology.device_budget [lo,hi]     -> device_budget   (lo<=n_dev<=hi)
          ports.input/output                 -> has_ports       (both nets present)
          topology.differential: false       -> single_input    (exactly one VIN net)
          topology.allow_inductorless: false -> has_inductor    (>=1 L)
          topology.min_inductor_ratio: r     -> inductor_ratio  (ratio >= r)
          topology.max_inductors: N          -> max_inductors   (n_L <= N)
          topology.allow_inductorless: true  -> match_plausible (inductorless RF
                                                input structure present)

        Bias-insertability (03-BIAS R-checks) and the floating-subcircuit check
        (H-Q3) are further "any spec" criteria in the plan; they depend on the
        DC-graph analysis built in WP-BIAS and are wired in there, not here.
        """
        topocfg = self.topology
        crit = OrderedDict()
        counts = topo.counts()

        crit["has_transistor"] = (counts.get("NM", 0) + counts.get("PM", 0)) >= 1

        if "device_budget" in topocfg:
            lo, hi = topocfg["device_budget"]
            crit["device_budget"] = lo <= topo.n_devices <= hi

        inp = self.ports.get("input")
        outp = self.ports.get("output")
        if inp and outp:
            crit["has_ports"] = topo.has_net(inp) and topo.has_net(outp)

        if topocfg.get("differential") is False:
            prefix = (inp or "VIN").rstrip("0123456789") or (inp or "VIN")
            n_in = len({n for n in topo.nets if n.startswith(prefix)})
            crit["single_input"] = n_in == 1

        if topocfg.get("allow_inductorless") is False:
            crit["has_inductor"] = topo.n_inductors >= 1

        if "min_inductor_ratio" in topocfg:
            crit["inductor_ratio"] = topo.inductor_ratio >= topocfg["min_inductor_ratio"]

        if "max_inductors" in topocfg:
            crit["max_inductors"] = topo.n_inductors <= topocfg["max_inductors"]

        if topocfg.get("allow_inductorless") is True:
            crit["match_plausible"] = self._match_plausible(topo)

        return all(crit.values()), crit

    def _node_index(self, topo):
        """Map every pin/net token to a canonical electrical-node id."""
        tok2node = {}
        for members in topo.nodes.values():
            nets_here = [m for m in members if m in topo.nets]
            rep = min(nets_here) if nets_here else min(members)
            for m in members:
                tok2node[m] = rep
        return tok2node

    def _match_plausible(self, topo):
        """Does an inductorless topology carry a recognizable RF-input structure?

        For wideband/inductorless-allowed specs, has_inductor no longer gates, so
        without this an arbitrary transistor+resistor gain stage would pass. The
        two legitimate inductorless LNA input structures are detected structurally
        (validated to pass all 14 inductorless corpus LNAs while rejecting the
        non-LNA calibration circuits 14/17/20/22):

          * common-gate / 1/gm-match: the input signal reaches a transistor SOURCE;
          * resistive shunt feedback: a resistor bridges the input signal side and
            the output signal side.

        "Signal side" = nodes reachable from the port net through 2-terminal
        passives (R/C/L bridges), so a gate coupled to VIN1 through a DC-block cap
        still counts as input-side. A single shunt-peaking inductor also qualifies.
        """
        if topo.n_inductors >= 1:
            return True
        tok2node = self._node_index(topo)

        def nd(dev, pin):
            return tok2node.get(f"{dev}_{pin}")

        fets = [d for d in topo.devices if base_of(d) in ("NM", "PM")]
        passives = [d for d in topo.devices if base_of(d) in ("R", "C", "L")]

        adj = defaultdict(set)
        for d in passives:
            a, b = nd(d, "P"), nd(d, "N")
            if a and b and a != b:
                adj[a].add(b)
                adj[b].add(a)

        def reach(net):
            start = tok2node.get(net)
            if start is None:
                return set()
            seen, dq = {start}, deque([start])
            while dq:
                u = dq.popleft()
                for v in adj[u]:
                    if v not in seen:
                        seen.add(v)
                        dq.append(v)
            return seen

        in_net = self._resolve_net(topo, self.ports.get("input", "VIN1"))
        out_net = self._resolve_net(topo, self.ports.get("output", "VOUT1"))
        in_side, out_side = reach(in_net), reach(out_net)

        if any(nd(f, "S") in in_side for f in fets):        # common-gate
            return True
        for d in passives:                                  # shunt feedback R
            if base_of(d) == "R":
                p, n = nd(d, "P"), nd(d, "N")
                if (p in in_side and n in out_side) or (n in in_side and p in out_side):
                    return True
        return False

    # ================================================================ view 2
    def _scale(self, limit):
        """Normalizer for a constraint: the magnitude of its threshold (>=1)."""
        vals = [abs(limit[k]) for k in ("min", "max") if k in limit]
        return max(max(vals) if vals else 1.0, 1.0)

    def feasible(self, metrics):
        """(feasible?, {metric: normalized violation}) over hard constraints.

        `status: unsupported` constraints are skipped. A supported constraint whose
        metric is absent from `metrics` counts as violated (cannot be confirmed).
        """
        viol = OrderedDict()
        for name, c in self.constraints.items():
            if c.get("status") == "unsupported":
                continue
            val = metrics.get(name)
            scale = self._scale(c)
            if val is None:
                viol[name] = 1.0
                continue
            v = 0.0
            if "max" in c and val > c["max"]:
                v += (val - c["max"]) / scale
            if "min" in c and val < c["min"]:
                v += (c["min"] - val) / scale
            if v > 0:
                viol[name] = v
        return len(viol) == 0, viol

    def objective(self, metrics):
        """Single float for ZOAF (minimized), feasibility-first (05-SIZING §1).

            infeasible: 1 + sum(normalized violations)   -- always > any feasible
            feasible  : -sum(w_j * normalized improvement beyond the floor)
        """
        feas, viol = self.feasible(metrics)
        if not feas:
            return 1.0 + sum(viol.values())
        total = 0.0
        for o in self.objectives:
            name = o["metric"]
            if metrics.get(name) is None:
                continue
            m = metrics[name]
            c = self.constraints.get(name, {})
            scale = self._scale(c) if c else max(abs(m), 1.0)
            if o["direction"] == "max":
                floor = c.get("min", 0.0)
                imp = (m - floor) / scale
            else:
                floor = c.get("max", 0.0)
                imp = (floor - m) / scale
            total += o.get("weight", 1.0) * imp
        return -total

    # ================================================================ view 3
    def seed_filter(self, topo):
        """Should this corpus circuit be used as a conditioned-generation seed?

        Narrowband/inductor-required specs seed from inductor-bearing LNAs;
        inductorless-allowed (wideband) specs seed from the inductorless class
        (plans/01-SPEC.md §5), so the prefix pool becomes spec-aware.
        """
        if self.allow_inductorless:
            return topo.n_inductors == 0
        return topo.n_inductors >= 1

    # ------------------------------------------------------------- reporting
    def report(self, metrics):
        """Human-readable L2 pass/fail table; unsupported constraints as UNMEASURED."""
        lines = [f"spec {self.name}: {self.description}"]
        feas, viol = self.feasible(metrics)
        lines.append("  constraints:")
        for name, c in self.constraints.items():
            lim = ", ".join(f"{k}={c[k]}" for k in ("min", "max") if k in c)
            if c.get("status") == "unsupported":
                lines.append(f"    {name:<14} [{lim}]  UNMEASURED (no harness)")
                continue
            val = metrics.get(name)
            if val is None:
                lines.append(f"    {name:<14} [{lim}]  MISSING")
            else:
                ok = name not in viol
                lines.append(f"    {name:<14} [{lim}]  {val:<10g} "
                             f"{'PASS' if ok else 'FAIL'}")
        lines.append(f"  feasible: {feas}   objective: {self.objective(metrics):.4g}")
        return "\n".join(lines)


def load_spec(name_or_path):
    return Spec.load(name_or_path)


# ------------------------------------------------------------------------ CLI
def _corpus_topology(index):
    import numpy as np
    # define REPO locally (like screen.py) so analysis needs no torch import
    repo = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "AnalogGenie", "repo"))
    p = os.path.join(repo, "Dataset", str(index), f"Sequence_total{index}.npy")
    if not os.path.exists(p):
        raise SpecError(f"no preprocessed sequence for corpus index {index}")
    arr = np.load(p, allow_pickle=True)
    return Topology([str(t) for t in arr[0]])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="spec name (in lna/specs/) or path")
    ap.add_argument("--all", action="store_true",
                    help="validate every spec in lna/specs/")
    ap.add_argument("--screen-index", type=int,
                    help="run the L0 structural screen against a corpus circuit")
    args = ap.parse_args()

    if args.all:
        ok = True
        for fn in sorted(os.listdir(SPECS_DIR)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            try:
                s = Spec.load(os.path.join(SPECS_DIR, fn))
                print(f"  OK   {fn:<20} {s.name} ({s.band_type})")
            except SpecError as e:
                ok = False
                print(f"  FAIL {fn:<20} {e}")
        return 0 if ok else 1

    if not args.spec:
        ap.error("give a spec name, or --all")

    s = Spec.load(args.spec)
    print(f"loaded {s.source}")
    print(f"  name        : {s.name}")
    print(f"  description : {s.description}")
    print(f"  band        : {s.band_type}"
          + (f"  f0={s.band.get('f0')}" if s.band.get("f0") else ""))
    print(f"  inductorless: {'allowed' if s.allow_inductorless else 'no'}")
    print("  hard constraints:")
    for name, c in s.constraints.items():
        lim = ", ".join(f"{k}={c[k]}" for k in ("min", "max") if k in c)
        tag = "  (UNMEASURED)" if c.get("status") == "unsupported" else ""
        print(f"      {name:<14} {lim}{tag}")
    print("  objectives  : " + ", ".join(
        f"{o['direction']} {o['metric']}(w={o.get('weight', 1.0)})"
        for o in s.objectives))

    # which L0 criteria will this spec's fields activate? (probe on a dummy)
    if args.screen_index is not None:
        topo = _corpus_topology(args.screen_index)
        passed, crit = s.structural_screen(topo)
        print(f"\n  L0 screen of corpus circuit {args.screen_index} "
              f"(devices={topo.n_devices}, inductors={topo.n_inductors}):")
        for k, v in crit.items():
            print(f"      {k:<16} {'pass' if v else 'FAIL'}")
        print(f"      => {'PASS' if passed else 'reject'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
