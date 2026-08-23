"""E-12 P0.3 -- FRESH n78 task construction (in-memory; NO lna/specs yaml edit).

Binding pre-reg: engineer/E12-TRAINEDIT.md §2/§3.3/§11.4 + G0-FAIRNESS fresh-task
rules. The FRESH task (user-ruled at GO 2026-08-23): 5G n78 LNA, band
3.4-3.6 GHz, 50 ohm source, dhruva-class power/NF limits. It is a *band-transfer*
axis off dhruva-s: the dhruva-s constraint STRUCTURE (same s11/s21/idd/nf limit
keys and values) is reused verbatim, only the band edges are swapped to
3.4e9-3.6e9. ism58 is excluded as main-touched (user ruling).

The spec is built IN MEMORY as a plain dict and validated through the real
Spec() constructor (same validator every lna spec passes) -- no yaml is written.
The task is anchored to the dhruva-s reached anchor topology (wl f578743a...,
the SAME anchor E-9/E-11 used for dhruva-s), so env.build_task has a real stored
topology to rebuild a deck from; only the spec's band differs, so the harness
genuinely sweeps ngspice at 3.4-3.6 GHz.

The n78 goal on it (FRESH scored delta): `nf_db <= 1.6`. Rationale: the fresh
tier tests transfer to an unseen band; a noise delta parallels H2/G13 (the noise
axis the trained editors are supposed to generalize) without reusing a dhruva
band. 1.6 dB is a moderate NF target for a 3.5 GHz band -- NOT calibrated from a
banked n78 run (none exists; that is the point of a fresh task) but chosen a
priori from the dhruva-class nf limit (base nf<=3.5) tightened toward the noise
regime the DEV/HELD-OUT noise goals occupy (1.25-1.9). A/B baselines are run
fresh in P3 (not here); P0 only builds + sanity-checks the harness.

This module:
  * `n78_spec_dict()` -- the in-memory spec dict.
  * `n78_task()`      -- a tasks.Task anchored to the dhruva-s topology, with
                         spec name monkey-swapped to the n78 spec at load time.
  * `install_n78()`   -- patches Spec.load / size._spec_for_sizing so any code
                         asking for spec "n78" gets the in-memory spec (contained;
                         no yaml written). Idempotent.
  * writes engineer/data/e12/fresh_task.json (full definition) on --emit.

Sanity evals (a handful) on the dhruva-s anchor topology are allowed in P0 and
counted as P0 SANITY sims (not scored) -- see --sanity.

    python e12_tasks.py --emit           # write fresh_task.json (0 sims)
    python e12_tasks.py --sanity 3       # 3 sanity evals on the n78 band
"""
import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LNA = os.path.abspath(os.path.join(HERE, "..", "lna"))
for p in (HERE, LNA):
    if p not in sys.path:
        sys.path.insert(0, p)

from spec import Spec           # noqa: E402
import spec as S_mod            # noqa: E402

N78_NAME = "n78"
DHRUVA_S_ANCHOR = "f578743ae13296d0"     # E-9/E-11 dhruva-s reached anchor
FRESH_JSON = os.path.join(HERE, "data", "e12", "fresh_task.json")

# n78 goal (FRESH scored delta) -- authored a priori, NOT banked-calibrated.
N78_GOAL = {"id": "GN78", "delta": {"nf_db": {"max": 1.6}},
            "desc": "nf_db <= 1.6 (n78, 3.4-3.6 GHz)", "type": "noise"}


def n78_spec_dict():
    """dhruva-s constraint structure, band swapped to n78 (3.4-3.6 GHz)."""
    ds_spec = Spec.load("dhruva-s")
    raw = copy.deepcopy(ds_spec.raw)
    raw["name"] = N78_NAME
    raw["description"] = ("5G n78 band (3.5 GHz center) LNA, 50 ohm source, "
                          "dhruva-class tier-1/2 limits (FRESH transfer task, "
                          "band-swapped from dhruva-s; in-memory, no yaml)")
    raw["band"] = {"type": "narrowband",
                   "f0": 3.5e9, "f_lo": 3.4e9, "f_hi": 3.6e9}
    # ports z0 stays 50 (dhruva-s already 50 ohm). constraints/sizing/topology
    # copied verbatim from dhruva-s (dhruva-class limits).
    return raw


# The n78 task reuses the dhruva-s STORED ROW (real topology tokens) for the
# anchor -- there is no store row under a fabricated "n78" spec name, and pinning
# to a real row is repo law (_pinned_row is loud). So the task keeps spec name
# "dhruva-s" for the row/topology lookup, and the BAND is swapped to n78 only at
# the spec-compile seam (build_task -> size._spec_for_sizing -> Spec.load), gated
# by an explicit context flag so ordinary dhruva-s tasks are untouched.
N78_BAND = {"type": "narrowband", "f0": 3.5e9, "f_lo": 3.4e9, "f_hi": 3.6e9}
_N78 = {"active": False, "installed": False, "orig_sfs": None}


def _swap_band_to_n78(sp):
    sp.band = dict(sp.band)
    sp.band.update(N78_BAND)
    # keep sp.raw coherent for anything that re-reads it
    try:
        sp.raw = copy.deepcopy(sp.raw)
        sp.raw["band"] = dict(N78_BAND)
        sp.raw["name"] = N78_NAME
    except Exception:
        pass
    sp.name = N78_NAME
    return sp


def install_n78():
    """Patch size._spec_for_sizing so that WHILE _N78['active'] is set, a
    dhruva-s spec compiles with the n78 band. Contained, idempotent; no yaml
    written, no lna/ mutation."""
    if _N78["installed"]:
        return
    try:
        import size as SZ
    except Exception:
        return
    _real_sfs = SZ._spec_for_sizing
    _N78["orig_sfs"] = _real_sfs

    def patched_sfs(name, nf_gate=None):
        sp = _real_sfs(name, nf_gate=nf_gate)
        if _N78["active"] and name == "dhruva-s":
            sp = _swap_band_to_n78(sp)
        return sp
    SZ._spec_for_sizing = patched_sfs
    _N78["installed"] = True


class n78_active(object):
    """Context manager: within it, dhruva-s specs compile at the n78 band."""
    def __enter__(self):
        install_n78()
        _N78["active"] = True
        return self

    def __exit__(self, *a):
        _N78["active"] = False
        return False


def n78_task(budget=600, seed=1):
    """A tasks.Task for the n78 fresh task: dhruva-s topology + row (real pin),
    band swapped to n78 at compile time (requires the n78_active() context)."""
    from env import Task
    from tasks import get
    ds_task = get("dhruva-s-t2-a")
    t = Task("n78-t2-a", "dhruva-s", DHRUVA_S_ANCHOR, budget=budget, seed=seed,
             tier=2, ref_ts=ds_task.ref_ts, ref_evals=ds_task.ref_evals,
             ref_feasible=False, ref_obj=None, era="current",
             n_devices=ds_task.n_devices,
             notes="FRESH n78 transfer task (dhruva-s topology, band->3.4-3.6GHz)")
    return t


def emit():
    n78 = n78_spec_dict()
    defn = {
        "campaign": "e12", "phase": "P0.3 fresh n78 task",
        "task_id": "n78-t2-a",
        "spec": n78,
        "spec_provenance": ("in-memory band swap of dhruva-s (constraints, "
                            "sizing, topology, ports verbatim; band -> "
                            "3.4-3.6 GHz). NO lna/specs yaml written."),
        "anchor_topology_wl": DHRUVA_S_ANCHOR,
        "anchor_provenance": "E-9/E-11 dhruva-s reached anchor (real stored row)",
        "source_impedance_ohm": n78["ports"]["z0"],
        "band_ghz": [3.4, 3.6],
        "f0_ghz": 3.5,
        "goal": {"id": N78_GOAL["id"], "delta": N78_GOAL["delta"],
                 "desc": N78_GOAL["desc"], "type": N78_GOAL["type"],
                 "authored": "a priori at GO (not banked-calibrated; fresh task)"},
        "fairness_note": ("G0-FAIRNESS fresh-task: different band (3.5 GHz vs "
                          "dhruva 1.18-2.49 GHz); dhruva-class power/NF limits; "
                          "ism58 excluded as main-touched (user ruling)."),
        "ngspice_calls": 0,
    }
    os.makedirs(os.path.dirname(FRESH_JSON), exist_ok=True)
    tmp = FRESH_JSON + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(defn, fh, indent=2, default=str)
    os.replace(tmp, FRESH_JSON)
    print("n78 fresh task written (0 sims):", FRESH_JSON)
    print("  band 3.4-3.6 GHz, z0=%s, anchor=%s" %
          (n78["ports"]["z0"], DHRUVA_S_ANCHOR))
    print("  constraints:", {k: v for k, v in n78["constraints"].items()})
    print("  goal:", N78_GOAL["desc"])
    return defn


def sanity(n_evals=3):
    """A handful of sanity evals on the n78 anchor (dhruva-s topology at the
    n78 band). Counted as P0 SANITY sims (not scored). Prints metrics to prove
    the harness produces numbers on the 3.4-3.6 GHz band."""
    import numpy as np
    from env import Env
    with n78_active():
        t = n78_task(budget=max(n_evals + 2, 8), seed=1)
        env = Env(t, budget=t.budget, seed=1, logger=None)
        print("n78 sanity: spec band =", env.spec.band, "z0 =", env.spec.ports)
        assert abs(float(env.spec.band["f0"]) - 3.5e9) < 1, \
            "n78 band did not take effect"
        anchor_params = env.row.get("best_params")
        x0 = np.asarray(env.arena.encode(anchor_params), dtype=float) \
            if anchor_params else np.full(env.arena.dim, 0.5)
        results = []
        for i in range(n_evals):
            x = x0 if i == 0 else np.clip(x0 + 0.05 * (i), 0.0, 1.0)
            out = env.evaluate(topology=None, params=x, action="sanity")
            m = out.get("metrics") or {}
            keep = {k: m.get(k) for k in ("s11_max_db", "s21_db", "idd_ma",
                                          "nf_db", "s21_ripple_db", "s22_max_db")}
            results.append({"i": i, "objective": out.get("objective"),
                            "metrics": keep})
            print(f"  eval {i}: obj={out.get('objective')} metrics={keep}")
        print(f"n78 sanity: {env.n_evals} evals, {env.ngspice_calls} ngspice "
              "calls (P0 SANITY, not scored)")
        return {"evals": env.n_evals, "ngspice_calls": env.ngspice_calls,
                "results": results, "band": dict(env.spec.band)}


def main():
    ap = argparse.ArgumentParser(description="E-12 fresh n78 task")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--sanity", type=int, default=0)
    a = ap.parse_args()
    if a.emit:
        emit()
    if a.sanity:
        r = sanity(a.sanity)
        # append sanity result into fresh_task.json
        if os.path.exists(FRESH_JSON):
            d = json.load(open(FRESH_JSON))
            d["p0_sanity"] = {"evals": r["evals"],
                              "ngspice_calls": r["ngspice_calls"],
                              "band": r["band"], "results": r["results"]}
            tmp = FRESH_JSON + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(d, fh, indent=2, default=str)
            os.replace(tmp, FRESH_JSON)
    if not (a.emit or a.sanity):
        emit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
