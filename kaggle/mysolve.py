"""Interactive design-loop helper: size ONE candidate topology against a cell's
spec, deterministically (gf180 MC-off), and print the full per-constraint margin
table so I can iterate on the topology.

Usage:  python mysolve.py <cell> <netlist_file> [budget] [seeds]
  cell         : e.g. bnl-35-lown-n0 (spec.yaml resolved from editcap-lib-v1*/)
  netlist_file : a topology in the harness dialect (connectivity only; no values,
                 no bias, no sources -- the harness inserts bias & sizes)
  budget       : evals per seed (default 1500)
  seeds        : comma list (default 1,2,3), best-over-seeds reported
"""
import sys, os, json
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO, os.path.join(REPO, "lna"), os.path.join(REPO, "kaggle"),
          os.path.join(REPO, "kaggle", "loop")):
    sys.path.insert(0, p)
import proposal as P
import bench_anchor_prep as PREP
from spec import Spec

PDK = "gf180mcu"


def _spec_path(cell):
    for L in ("editcap-lib-v1a", "editcap-lib-v1b", "editcap-lib-v1"):
        p = os.path.join(REPO, "kaggle", L, cell, "spec.yaml")
        if os.path.exists(p):
            return p
    raise SystemExit("no spec for %s" % cell)


def _margins(spec, m):
    rows, worst = [], None
    for name, c in (spec.constraints or {}).items():
        if c.get("status") == "unsupported":
            continue
        ach = m.get(name)
        if ach is None:
            rows.append((name, None, c, None, False)); continue
        scale = spec._scale(c)
        mg = ((ach - c["min"]) / scale if "min" in c
              else (c["max"] - ach) / scale if "max" in c else None)
        rows.append((name, ach, c, mg, True))
        if mg is not None and (worst is None or mg < worst[1]):
            worst = [name, mg]
    return rows, worst


def main():
    cell = sys.argv[1]
    net = open(sys.argv[2], encoding="utf-8").read()
    budget = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
    seeds = [int(s) for s in (sys.argv[4].split(",") if len(sys.argv) > 4 else ["1", "2", "3"])]
    sp = _spec_path(cell)
    spec = Spec.load(sp)
    info = P.round_trip(net)
    if not info.get("ok"):
        print("ROUND-TRIP FAIL:", info.get("error")); return
    tokens = info["tokens"]
    print(f"cell={cell}  round_trip OK ({len(tokens)} tokens)  budget={budget}x{len(seeds)} seeds MC-off")
    best = None
    for seed in seeds:
        try:
            res = PREP.smoke_run(list(tokens), sp, seed, budget, PDK)
        except Exception as e:                                   # noqa: BLE001
            print(f"  seed{seed}: EXC {e!r}"); continue
        if res is None:
            print(f"  seed{seed}: not sizable"); continue
        rows, worst = _margins(spec, res.get("metrics") or {})
        feas = bool(res.get("feasible"))
        wm = worst[1] if worst else -1e9
        key = (feas, wm)
        if best is None or key > best[0]:
            best = (key, seed, rows, feas, worst, res.get("metrics"))
    if best is None:
        print("  NO SIZABLE SEED"); return
    _key, seed, rows, feas, worst, metrics = best
    print(f"\nBEST (seed {seed}):  {'*** FEASIBLE ***' if feas else 'infeasible'}")
    print(f"  {'metric':14s} {'achieved':>12s} {'target':>16s} {'margin':>9s}")
    for name, ach, c, mg, sup in rows:
        tgt = (f">={c['min']}" if 'min' in c else f"<={c['max']}" if 'max' in c else "?")
        achs = f"{ach:.4g}" if isinstance(ach, (int, float)) else "None"
        mgs = f"{mg:+.3f}" if isinstance(mg, (int, float)) else "  n/a"
        flag = "" if (mg is None or mg >= 0) else "  <-- FAIL"
        print(f"  {name:14s} {achs:>12s} {tgt:>16s} {mgs:>9s}{flag}")
    print(f"  worst: {worst}")


if __name__ == "__main__":
    main()
