import json, os, sys
sys.path.insert(0, "lna")
import datastore as ds, size, bias
from topology import Topology
from _trackb_bpolish import bounded_polish, in_box
spec = size._spec_for_sizing("dhruva-l1", nf_gate=False)
# the ORIGINAL scan row (ZOAF, in-box by construction), not the polished one
rows = [r for r in ds.load("topo_labels")
        if r.get("spec") == "dhruva-l1" and r.get("wl_hash") == "20bca9a7c3a5f263"
        and (r.get("provenance") or {}).get("how") is None]
row = rows[0]
topo = Topology(row["graph"]["tokens"])
nl, _, _, _ = bias.insert_bias(topo, sweep=True, inductor_q=12)
sz, _ = size.classify_params(nl)
print("start row viol:", spec.feasible(row["metrics"]), "in-box violations:",
      in_box(row["best_params"], sz, spec))
res = bounded_polish(topo, spec, row["best_params"], budget=500)
m, p = res["metrics"], res["best_params"]
bad = in_box(p, sz, spec)
feas, viol = spec.feasible(m)
print(f"BOUNDED polish: S11max={m['s11_max_db']:.3f} S21={m['s21_db']:.3f} "
      f"Idd={m['idd_ma']:.3f} feasible={feas} viol={sum(viol.values()) if viol else 0:.5f}")
print("out-of-box params:", bad or "NONE -- all inside the spec device box")
print("inductors:", {k: v for k, v in p.items() if k.startswith("pL")})
if feas and not bad:
    prov = {"source_arm": "trackb-p5v6", "how": "bounded-polish", "trackb": True,
            "token_file": "lna/out/ft_p5v6_nb_s1337/seq0192.txt",
            "wl_hash": "20bca9a7c3a5f263", "curated": False, "polished": True,
            "nf_gated": False, "in_box_verified": True}
    m2 = size.log_l2_result(spec, topo, m, True, p, prov, "p5v6-gen-boxed", 500)
    print("logged; enriched NF =", m2.get("nf_db"))
    json.dump({"seq": "seq0192.txt", "wl": "20bca9a7c3a5f263", "metrics": m2,
               "params": p, "in_box": True},
              open("lna/out/trackb_dhruva_l1_seq0192.params.json", "w"), indent=1)
