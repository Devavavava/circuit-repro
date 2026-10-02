"""Extended record audit (deviation D5): bench-v2 rl-v1-FEASIBLE rows whose topology
passes the rl-v1.1 port-DC pre-filter. By bench-v2 AMENDMENT 2 D23 these are
rl-v1.1-feasible designs on record (the behavioural check is a provable no-op for a
pre-filter-passing topology), but they are not in the strict seed set (no rl-v1.1
row). A deterministic sample (sha1 order of tok|spec) is re-sized under rl-v1.1 with
capture and run through R-a..R-e exactly like a seed; they are NOT search parents.

usage: ext_record.py list <out.jsonl> <n>     (writes the sample, seeds.jsonl format)
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402
import seeds as SD  # noqa: E402


def main(out, n):
    tm = SD.tok_map()
    strict = {(json.loads(ln)["tok"], json.loads(ln)["src_spec"])
              for ln in open(f"{HERE}/seeds.jsonl") if json.loads(ln)["origin"] == "bench-v2"}
    strict_tok = {k[0] for k in strict}
    rows = [json.loads(ln) for ln in open(f"{SD.RUN}/results.jsonl")]
    groups = {}
    for r in rows:
        if r.get("profile") != "rl-v1" or not (r.get("res") or {}).get("feasible"):
            continue
        if r.get("derived_from"):
            continue
        groups.setdefault((r["tok"], r["spec"]), []).append(r)
    cand, pf = [], {}
    for (tok, spec), rs in groups.items():
        if tok not in tm or tok in strict_tok or not os.path.exists(f"{X.REPO}/{spec}"):
            continue
        if tok not in pf:
            pf[tok] = X.PREP.port_dc_prefilter(tm[tok])["pass"]
        if not pf[tok]:
            continue
        rs.sort(key=lambda r: (r["seed"], r["ts"]))
        cand.append((hashlib.sha1(f"{tok}|{spec}".encode()).hexdigest(), tok, spec, rs[0]))
    cand.sort()
    print(f"{len(groups)} rl-v1 feasible (tok,spec); {len(cand)} eligible (pre-filter pass, "
          f"not a strict-seed topology); sampling {n}")
    os.makedirs(SD.SPECS, exist_ok=True)
    with open(out, "w") as fh:
        for i, (_h, tok, spec, r) in enumerate(cand[:n]):
            dst = f"{SD.SPECS}/{os.path.basename(spec)}"
            if not os.path.exists(dst):
                import shutil
                shutil.copyfile(f"{X.REPO}/{spec}", dst)
            fh.write(json.dumps({"sid": f"E{i:03d}", "origin": "bench-v2", "tok": tok,
                                 "tokens": tm[tok], "spec": os.path.relpath(dst, X.REPO),
                                 "src_spec": spec, "seed": r["seed"], "kinds": [r["kind"]],
                                 "meta": r.get("meta"), "jid": r["jid"],
                                 "rec_metrics": r["res"]["metrics"], "ext": True}) + "\n")


if __name__ == "__main__":
    main(sys.argv[2], int(sys.argv[3]))
