"""Shared helpers for the opamp-v0 validation gates (run from the worktree root via the env wrapper)."""
import json
import os
import sys

CAMPAIGN = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, CAMPAIGN)
RESULTS = os.path.join(CAMPAIGN, "gates", "results")
CIRCUITS = os.path.join(CAMPAIGN, "circuits")
os.makedirs(RESULTS, exist_ok=True)

# Hard constraints used to size designs for V1/V3 (R1's hard constraints without swing).
SPEC_BASE = {"name": "gate-base", "cl_pf": 2.0,
             "constraints": {"ugf_mhz": {"min": 10.0}, "pm_deg": {"min": 60.0},
                             "idd_ua": {"max": 200.0}}}


def circuit(name):
    with open(os.path.join(CIRCUITS, name)) as fh:
        return fh.read()


def slim(m):
    """Metrics without the per-device op table."""
    return {k: v for k, v in (m or {}).items() if k != "op"}


def dump(name, obj):
    p = os.path.join(RESULTS, name)
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True, default=str)
    return p
