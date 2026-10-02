"""EX seed set: every rl-v1.1-feasible design on record (READ-ONLY on bench-v2/run).

  bench-v2  : results.jsonl rows with profile rl-v1.1 and feasible (search/confirm,
              A1/A2/A3 cell validation incl. the accepted cells, T-wit training
              witnesses, F2), unique by (tokens, spec); sizing seed = the lowest
              recorded feasible seed. Re-sized with capture (deterministic) to get
              the sized params; the recorded metrics must reproduce.
  rl-ready  : rl-readiness/verifier-rl-v1 rl-v1 winners (body + params_win already
              captured). rl-v1.1 = rl-v1 + port-DC; their rl-v1.1 status is decided
              in ex_drv (pre-filter + behavioural port_dc_check on the captured
              winner, + a re-evaluation of spec + wide mu).
Specs are copied into EX/specs/ (bench-v2) or regenerated with rl_v1_spec (rl-ready).

usage: seeds.py <out seeds.jsonl>
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402
import bv2  # noqa: E402  (read-only: tokhash, sha)
import proposal as P  # noqa: E402

REPO = X.REPO
RUN = f"{REPO}/kaggle/campaigns/bench-v2/run"
SPECS = f"{HERE}/specs"
RLV1 = f"{REPO}/kaggle/campaigns/rl-readiness/verifier-rl-v1/results.json"
LIB = f"{REPO}/kaggle/editcap-lib-v12-45nm"


def tok_map():
    m = {}
    for ln in open(f"{RUN}/rtcache.jsonl"):
        v = json.loads(ln)["v"]
        if v.get("tokens"):
            m[bv2.tokhash(v["tokens"])] = v["tokens"]
    for fn in (f"{RUN}/candidates.jsonl", f"{RUN}/amendment-1-record/candidates.jsonl"):
        for ln in open(fn):
            c = json.loads(ln)
            if c.get("tokens"):
                m[c["tok"]] = c["tokens"]
    for fn in (f"{RUN}/cells.jsonl", f"{RUN}/train.jsonl"):
        for ln in open(fn):
            c = json.loads(ln)
            for k in ("netlist",):
                if c.get(k) and c.get("tok") not in m:
                    rt = P.round_trip(c[k])
                    if rt["ok"]:
                        m[bv2.tokhash(rt["tokens"])] = rt["tokens"]
    return m


def main(out):
    os.makedirs(SPECS, exist_ok=True)
    tm = tok_map()
    rows = [json.loads(ln) for ln in open(f"{RUN}/results.jsonl")]
    feas = [r for r in rows if r.get("profile") == "rl-v1.1"
            and (r.get("res") or {}).get("feasible")]
    groups = {}
    for r in feas:
        groups.setdefault((r["tok"], r["spec"]), []).append(r)
    seeds, miss = [], 0
    for (tok, spec), rs in groups.items():
        if tok not in tm:
            miss += 1
            continue
        rs.sort(key=lambda r: (r["seed"], r["ts"]))
        r = rs[0]
        dst = f"{SPECS}/{os.path.basename(spec)}"
        if not os.path.exists(dst):
            shutil.copyfile(f"{REPO}/{spec}", dst)
        seeds.append({"origin": "bench-v2", "tok": tok, "tokens": tm[tok],
                      "spec": os.path.relpath(dst, REPO), "src_spec": spec,
                      "seed": r["seed"], "kinds": sorted({x["kind"] for x in rs}),
                      "meta": r.get("meta"), "jid": r["jid"],
                      "rec_metrics": r["res"]["metrics"]})
    d = json.load(open(RLV1))
    for r in d["rows"]:
        if r["mode"] != "rlv1" or not (r.get("result") or {}).get("feasible"):
            continue
        if not r.get("params_win"):
            continue
        dst = PREP_spec(r["cell"])
        seeds.append({"origin": "rl-readiness", "tok": bv2.tokhash(r["tokens"]),
                      "tokens": r["tokens"], "spec": os.path.relpath(dst, REPO),
                      "seed": r["seed"], "kinds": [r["tag"]], "meta": {"cell": r["cell"],
                      "cand": r["cand"]}, "body": r["body"], "params": r["params_win"],
                      "rec_metrics": r["result"]["metrics"]})
    seeds.sort(key=lambda s: (s["origin"], s["spec"], s["tok"], s["seed"]))
    for i, s in enumerate(seeds):
        s["sid"] = f"S{i:03d}"
        net = X.tokens_to_net(s["tokens"])
        rt = P.round_trip(net)
        from topology import Topology
        from novelty import wl_features
        s["net"] = net
        s["net_wl_ok"] = bool(rt["ok"] and rt["wl_hash"] == wl_features(Topology(s["tokens"]))[0])
    with open(out, "w") as fh:
        for s in seeds:
            fh.write(json.dumps(s) + "\n")
    print(f"{len(seeds)} seeds ({sum(s['origin'] == 'bench-v2' for s in seeds)} bench-v2, "
          f"{sum(s['origin'] == 'rl-readiness' for s in seeds)} rl-readiness); "
          f"tok misses {miss}; net round-trip ok {sum(s['net_wl_ok'] for s in seeds)}")


def PREP_spec(cell):
    return X.PREP.rl_v1_spec(f"{LIB}/{cell}/spec.yaml", out_dir=SPECS)


if __name__ == "__main__":
    main(sys.argv[1])
