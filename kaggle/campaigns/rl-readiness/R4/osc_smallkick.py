"""Is each confirmed winner-oscillation a LINEAR instability (grows from a tiny
kick) or hard excitation (needs the 1 mA kick)? Re-run the oscillating
termination with a 1 uA x 10 ps kick (1000x smaller) for 600 ns, and read mu(f)
near f_osc from the gate grid. usage: osc_smallkick.py <rawdir> <out.json>"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_sim as S                                           # noqa: E402

rawdir, out = sys.argv[1], sys.argv[2]
OF = json.load(open(HERE + "/osc_freq.json"))
P = {d["id"]: d for d in json.load(open(HERE + "/post.json"))["designs"]}
res = []
for o in OF:
    d = P[o["id"]]
    fn = f"{d['tag']}__{d['cell']}__{d['cand'].replace(':', '_')}__{d['mode']}__s{d['seed']}.json"
    rec = json.load(open(os.path.join(rawdir, fn)))
    params = rec["params_win"] if d["role"] == "win" else rec["params_bx"]
    sp_ = S.stab_params(rec, params)
    ts, tl = o["term"].split("/")
    r = S.tran_run(rec["body"], sp_, term_src=ts, term_load=tl, tstop=600e-9, kick=1e-6)
    curve = S.mu_curve(rec["body"], sp_, "lin 3981 1e8 2e10")
    near = [(f, m) for f, m in curve if o["f_osc_hz"] and abs(f - o["f_osc_hz"]) < 0.2 * o["f_osc_hz"]]
    row = {"id": o["id"], "role": o["role"], "term": o["term"], "f_osc_hz": o["f_osc_hz"],
           "smallkick_verdict": S.tran_verdict(r), "smallkick_amp": r,
           "mu_min_near_fosc": min((m for _f, m in near), default=None),
           "mu_min_fine_grid": min((m for _f, m in curve), default=None)}
    res.append(row)
    print(row["role"], row["id"][:55], row["term"], row["smallkick_verdict"],
          (r or {}).get("eout"), (r or {}).get("lout"), row["mu_min_near_fosc"], flush=True)
json.dump(res, open(out, "w"), indent=1)
