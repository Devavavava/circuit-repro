"""Oscillation frequency of every 600-ns-confirmed oscillator (tran_long.json):
re-run the same deck, keep 500-600 ns (tstart=500n, 2 ps step, printed), count
mean-crossings of v(VOUT1) -> f_osc; also a gear re-run verdict (numerical
cross-check of the trapezoidal integrator). usage: osc_freq.py <rawdir> <out.json>"""
import sys, os, json, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_sim as S                                           # noqa: E402
import extract as E                                          # noqa: E402


def wave(body, params, ts, tl, method="trap"):
    deck = S.tran_deck(body, params, term_src=ts, term_load=tl, tstop=600e-9, method=method)
    deck = re.sub(r"^tran \S+ \S+ 0 (\S+)$", r"tran 2p 600n 500n \1", deck, flags=re.M)
    deck = deck.replace(".endc", "linearize v(VOUT1)\nprint v(VOUT1)\n.endc")
    out = E.run_deck(deck, "r4of_", "t.cir", timeout=900) or ""
    pts = []
    for ln in out.splitlines():            # linearized print: "<index> <v(vout1)>"
        t = ln.split()
        if len(t) == 2 and re.match(r"^\d+$", t[0]):
            try:
                pts.append((500e-9 + 2e-12 * int(t[0]), float(t[1])))
            except ValueError:
                pass
    return pts


def freq(pts):
    if len(pts) < 100:
        return None, None
    v = [p[1] for p in pts]
    mean = sum(v) / len(v)
    cr = [pts[i][0] for i in range(1, len(v)) if v[i - 1] < mean <= v[i]]
    pp = max(v) - min(v)
    if len(cr) < 2:
        return None, pp
    return (len(cr) - 1) / (cr[-1] - cr[0]), pp


def main(rawdir, out):
    TL = json.load(open(HERE + "/tran_long.json"))
    P = {d["id"]: d for d in json.load(open(HERE + "/post.json"))["designs"]}
    res = []
    seen = set()
    for k, v in TL.items():
        if v["long_verdict"] != "oscillates" or v["id"] in seen:
            continue
        seen.add(v["id"])                       # one termination per design
        d = P[v["id"]]
        fn = f"{d['tag']}__{d['cell']}__{d['cand'].replace(':', '_')}__{d['mode']}__s{d['seed']}.json"
        rec = json.load(open(os.path.join(rawdir, fn)))
        params = rec["params_win"] if d["role"] == "win" else rec["params_bx"]
        sp_ = S.stab_params(rec, params)
        ts, tl = v["term"].split("/")
        f, pp = freq(wave(rec["body"], sp_, ts, tl))
        g = S.tran_run(rec["body"], sp_, term_src=ts, term_load=tl, tstop=600e-9, method="gear")
        row = {"id": v["id"], "role": d["role"], "term": v["term"], "f_osc_hz": f,
               "pp_v": pp, "gear_600ns_verdict": S.tran_verdict(g),
               "mu_w0p01_50": (d["windows"].get("w0p01_50") or {}).get("mu_min"),
               "mu_gate": (d["windows"].get("w0p1_20") or {}).get("mu_min")}
        res.append(row)
        print(row, flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
