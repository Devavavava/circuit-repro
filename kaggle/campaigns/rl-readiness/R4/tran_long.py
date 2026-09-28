"""Item (e) confirmation: every (design, termination) whose 80-ns transient is
not a decay (verdict oscillates / marginal / dc_shift) is re-run for 600 ns
(same kick, trap) and re-classified on windows at 300 and 540 ns. "ringing"
(late < 0.95x mid window: already decaying, high-Q) is not re-run; the first 14
ringing cases that were re-run all ended "decays" (kept in the output).
usage: tran_long.py <rawdir> <post.json> <out.json>"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_sim as S                                           # noqa: E402


def main(rawdir, post, out):
    P = json.load(open(post))["designs"]
    raws = {}
    res = {}
    if os.path.exists(out):
        res = json.load(open(out))
    for d in P:
        todo = [k for k, v in d["tran"].items()
                if S.tran_verdict(v["amp"]) in ("oscillates", "marginal", "dc_shift")]
        if not todo:
            continue
        fn = f"{d['tag']}__{d['cell']}__{d['cand'].replace(':', '_')}__{d['mode']}__s{d['seed']}.json"
        rec = raws.get(fn) or json.load(open(os.path.join(rawdir, fn)))
        raws[fn] = rec
        params = rec["params_win"] if d["role"] == "win" else rec["params_bx"]
        sp_ = S.stab_params(rec, params)
        for k in todo:
            key = d["id"] + "|" + k
            if key in res:
                continue
            ts, tl = k.split("/")
            r = S.tran_run(rec["body"], sp_, term_src=ts, term_load=tl, tstop=600e-9)
            res[key] = {"id": d["id"], "role": d["role"], "term": k,
                        "short_verdict": S.tran_verdict(d["tran"][k]["amp"]),
                        "long_verdict": S.tran_verdict(r), "amp": r}
            print(key, res[key]["short_verdict"], "->", res[key]["long_verdict"], flush=True)
            json.dump(res, open(out, "w"), indent=1)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
