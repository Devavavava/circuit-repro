"""Compact view of results/<cell>/audit.json (+ results/summary.json when --all)."""
import json, os, sys
OUT = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v2/motif-audit/results"
KEYS = ("s11_max_db", "s21_db", "s21_ripple_db", "nf_max_db", "idd_ma")


def fmt(x):
    return f"{x:.3g}" if isinstance(x, (int, float)) else str(x)


def row(cell):
    a = json.load(open(f"{OUT}/{cell}/audit.json"))
    print(f"=== {cell}  anchor={a['anchor']}  cls={a['cls']}  L-IN-G={a.get('ing_inductors')}  gate={a.get('input_gate_net')}")
    print("  rerun_feasible", a["rerun_feasible"], "stored", a["stored_A1_feasible"], "match", a["rerun_matches_stored_A1"])
    print("  params", a["params"])
    r = a.get("reactance") or {}
    print("  react", {k: ([fmt(v) for v in vv] if isinstance(vv, list) else fmt(vv)) for k, vv in r.items()})
    for k, p in (a.get("probe") or {}).items():
        m = p.get("metrics") or {}
        op = p.get("op") or {}
        d1 = (op.get("devices") or {}).get("mnm1", {})
        nodes = op.get("nodes") or {}
        g = a.get("input_gate_net") or "n1"
        print(f"  {k:18s} final_ok={p.get('final_ok')} spec={p.get('spec_feasible')} tight={p.get('tight_feasible')} muW={fmt(p.get('mu_min_wide'))} "
              + " ".join(f"{kk}={fmt(m.get(kk))}" for kk in KEYS)
              + f" | V(VIN1)={fmt(nodes.get('vin1'))} V(g)={fmt(nodes.get(g.lower()))} NM1 vgs={fmt(d1.get('vgs'))} id={fmt(d1.get('id'))} vds={fmt(d1.get('vds'))} {d1.get('region')} Iport={fmt(op.get('i_port1_dc_A'))}"
              + (f" viol={ {kk: fmt(vv) for kk, vv in p.get('violations', {}).items()} }" if p.get("violations") else ""))
    for k, r in (a.get("resize") or {}).items():
        op = r.get("op_at_winner") or {}
        d1 = (op.get("devices") or {}).get("mnm1", {})
        print(f"  RESIZE {k}: feasible={r['feasible']} spec={r['spec_feasible']} muW={fmt(r.get('mu_min_wide'))} "
              + " ".join(f"{kk}={fmt(v)}" for kk, v in r["metrics"].items())
              + f" | NM1 vgs={fmt(d1.get('vgs'))} id={fmt(d1.get('id'))}")


if __name__ == "__main__":
    cells = sys.argv[1:] or sorted(os.listdir(OUT))
    for c in cells:
        if os.path.exists(f"{OUT}/{c}/audit.json"):
            row(c)
