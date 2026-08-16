#!/usr/bin/env python3
"""export_registry.py -- freeze the benchmark registry's pinned reference VALUES
into a standalone JSON so the shipped `tasks.py --list` needs neither `lna/` nor
`lna/data/`.

WHY THIS EXISTS
---------------
`engineer/tasks.py` builds its 8-task registry from a hardcoded `_ROWS` table
(the pins are literals in the source, not queried from a store), but importing
it drags in `env` -> `_bind_runtime_deps()` -> `lna/`, the 45 nm model card, and
ZOAF, because `tasks.py` also offers `--check`, which re-derives the pins from
the LIVE `lna/data/topo_labels.jsonl` to detect drift. A stranger who has only
the release tree (no lna clone, no model card) can therefore not even *list* the
benchmark without the manual fetches -- which is absurd, because the pinned
reference values are already constants.

This exporter runs on a box that DOES have `lna/` (the release build box),
imports the live `REGISTRY`, and writes every task's `Task.as_dict()` to
`tasks_registry_v0.json`. The release's patched `tasks.py --list` reads that
file directly (no `env`/lna import). `--check` is unchanged: it still needs the
live store and says so loudly when the store is absent (that is the honest
boundary -- drift-checking against the store REQUIRES the store).

The exported JSON is a byte-for-byte snapshot of the pins as the module defines
them; a stranger re-running this exporter against a live checkout must get the
same values or the registry has drifted (which `tasks.py --check` is what
catches). The file records the harness git SHA it was exported at so a citation
can name the exact registry commit.

    python engineer/release/export_registry.py                 # -> ./tasks_registry_v0.json
    python engineer/release/export_registry.py --out PATH      # explicit output
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINEER = os.path.dirname(HERE)


def _git_sha(cwd):
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd,
                           capture_output=True, text=True, timeout=10)
        return (r.stdout or "").strip() or None
    except Exception:                                          # noqa: BLE001
        return None


def export(out_path):
    # Import the LIVE registry. This needs lna/ + the model card + ZOAF because
    # `tasks.py` imports `env`, whose module-level `_bind_runtime_deps()` binds
    # them. That is exactly why the export happens here (build box) and not in
    # the stranger's tree.
    sys.path.insert(0, ENGINEER)
    import tasks as T                                          # noqa: E402

    tasks_out = []
    for t in T.all_tasks():                                    # sorted by id
        d = t.as_dict()
        d["is_smoke"] = (t.id == T.SMOKE)
        d["is_scoring"] = (t.id in T.SCORING)
        tasks_out.append(d)

    doc = {
        "kind": "engineer_benchmark_registry",
        "schema": "tasks_registry/v0",
        "source": "engineer/tasks.py REGISTRY (_ROWS)",
        "note": ("Frozen pinned reference values for the in-house benchmark. "
                 "Ships so `tasks.py --list` runs without lna/ or lna/data. "
                 "`tasks.py --check` still re-derives these against the live "
                 "store and needs lna/data/topo_labels.jsonl."),
        "harness_git_sha": _git_sha(ENGINEER),
        "smoke_task": T.SMOKE,
        "n_tasks": len(tasks_out),
        "n_scoring": len(T.SCORING),
        "tier3_tasks": 0,
        "tier3_note": ("iip3_dbm is `unsupported` in every spec until WP-LIN "
                       "binds the two-tone harness; there is no tier-3 task."),
        "tasks": tasks_out,
    }
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=False)
        f.write("\n")
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(os.getcwd(),
                    "tasks_registry_v0.json"),
                    help="output JSON path (default: ./tasks_registry_v0.json)")
    a = ap.parse_args()
    doc = export(a.out)
    print(f"wrote {a.out}: {doc['n_tasks']} tasks "
          f"({doc['n_scoring']} scoring, smoke={doc['smoke_task']}), "
          f"harness_git_sha={doc['harness_git_sha']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
