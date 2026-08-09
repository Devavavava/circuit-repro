"""Aggregate the Session-6 NF campaign into the front table (FINDINGS §17)."""
import json, os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for p in sorted(glob.glob(os.path.join(HERE, "out", "_nf", "*.json"))):
    if "scan" in os.path.basename(p):
        continue
    try:
        recs = json.load(open(p))
    except Exception:
        continue
    if not isinstance(recs, list):
        continue
    for r in recs:
        m = r.get("metrics") or {}
        rows.append({
            "file": os.path.basename(p),
            "cand": r.get("candidate") or r.get("move", "") + "/" + str(r.get("wl_hash", ""))[:6],
            "spec": r.get("spec", "dhruva-s"),
            "mode": r.get("mode", "nf"),
            "keep": (r.get("origin") or {}).get("keep") or r.get("keep"),
            "s11": m.get("s11_max_db") if m.get("s11_max_db") is not None else m.get("s11_db"),
            "s21": m.get("s21_db"), "idd": m.get("idd_ma"), "nf": m.get("nf_db"),
            "k": m.get("k_min"), "t1": r.get("tier1_ok"), "viol": r.get("violation"),
        })
f = lambda v, w=7, p=2: (f"{v:{w}.{p}f}" if isinstance(v, (int, float)) else " " * (w - 1) + "-")
print(f"{'file':<20}{'candidate':<24}{'spec':<12}{'mode':<5}{'S11*':>7}{'S21':>7}"
      f"{'Idd':>7}{'NF':>7}{'K':>9}{'t1':>4}{'viol':>8}")
for r in sorted(rows, key=lambda r: (r["spec"], r["nf"] if r["nf"] is not None else 1e9)):
    print(f"{r['file'][:19]:<20}{r['cand'][:23]:<24}{r['spec']:<12}{r['mode']:<5}"
          f"{f(r['s11'])}{f(r['s21'])}{f(r['idd'])}{f(r['nf'])}{f(r['k'],9,1)}"
          f"{str(r['t1'])[:1]:>4}{f(r['viol'],8,3)}")
print(f"\n{len(rows)} sized results")
