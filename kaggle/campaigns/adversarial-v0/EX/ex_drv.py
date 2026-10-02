"""EX worker: size one design under rl-v1.1 (capture) and, on a verifier pass, run
the reality checks R-a..R-e on the sized winner.

usage:
  ex_drv.py seed  <seeds.jsonl> <sid> <out.json>
  ex_drv.py child <job.json> <out.json>
  ex_drv.py checks <in.json (body, params, spec)> <out.json>
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402

KEEP_RES = ("feasible", "metrics", "n_evals", "infeasible_reason", "spec_feasible",
            "mu_min_wide", "stab_wide_ok", "stab_winner_replaced", "n_inert_devices",
            "inert_devices", "port_dc", "port_dc_prefilter", "structural_degeneracy",
            "topo_limits_ok", "nonfinite_metrics", "verifier", "sim_error", "n_sim_fail")


def _write(out, rec):
    tmp = out + f".{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(rec, fh, default=repr)
    os.replace(tmp, out)


def _checks(rec, spec):
    if rec.get("verifier_pass") and rec.get("params"):
        rc = X.reality_checks(rec["body"], rec["params"], spec)
        rec["checks"] = rc
        rec["summary"] = X.summarize_checks(rc)
        rec["exploit_score"] = rc["exploit_mag"]
    else:
        rec["checks"] = None
        rec["summary"] = None
        rec["exploit_score"] = 0.0
    return rec


def size_and_check(tokens, spec_path, seed, extra):
    spec = X.load_spec(f"{X.REPO}/{spec_path}")
    t0 = time.time()
    s = X.sized_run_v11(tokens, f"{X.REPO}/{spec_path}", seed)
    res = s["res"]
    rec = dict(extra)
    rec.update(tokens=list(tokens), spec=spec_path, seed=seed, secs_size=s["secs"],
               sizable=res is not None,
               res={k: (res or {}).get(k) for k in KEEP_RES} if res else None,
               verifier_pass=bool(res and res.get("feasible")),
               body=s.get("body"), params=s.get("params"))
    _checks(rec, spec)
    rec["secs_total"] = round(time.time() - t0, 1)
    return rec


def main():
    mode = sys.argv[1]
    if mode == "seed":
        sid = sys.argv[3]
        out = sys.argv[4]
        s = next(json.loads(ln) for ln in open(sys.argv[2]) if json.loads(ln)["sid"] == sid)
        extra = {k: s[k] for k in ("sid", "origin", "tok", "kinds", "meta", "src_spec")
                 if k in s}
        if s["origin"] == "bench-v2":
            rec = size_and_check(s["tokens"], s["spec"], s["seed"], extra)
            m0, m1 = s["rec_metrics"], ((rec.get("res") or {}).get("metrics") or {})
            rec["reproduced"] = all(m0.get(k) == m1.get(k) for k in m0)
            rec["repro_diff"] = {k: [m0.get(k), m1.get(k)] for k in m0 if m0.get(k) != m1.get(k)}
        else:
            spec = X.load_spec(f"{X.REPO}/{s['spec']}")
            t0 = time.time()
            pre = X.PREP.port_dc_prefilter(s["tokens"])
            ev = X.full_eval(s["body"], s["params"], spec)
            pdc = X.PREP.port_dc_check(spec, s["body"], s["params"]) if pre["pass"] else None
            rec = dict(extra)
            rec.update(tokens=s["tokens"], spec=s["spec"], seed=s["seed"], body=s["body"],
                       params=s["params"], sizable=True,
                       res={"feasible": bool(ev["ok"] and pre["pass"] and pdc and pdc["pass"]),
                            "metrics": ev.get("metrics"), "port_dc_prefilter": pre,
                            "port_dc": pdc, "mu_min_wide": ev.get("mu_wide"),
                            "reeval_ok": ev["ok"], "reeval_worst": ev.get("worst"),
                            "reeval_mag": ev.get("mag")},
                       secs_size=0.0)
            rec["verifier_pass"] = rec["res"]["feasible"]
            m0, m1 = s["rec_metrics"], ev.get("metrics") or {}
            rec["reproduced"] = all(m0.get(k) == m1.get(k) for k in m0 if k in m1)
            _checks(rec, spec)
            rec["secs_total"] = round(time.time() - t0, 1)
        _write(out, rec)
    elif mode == "child":
        job = json.load(open(sys.argv[2]))
        rec = size_and_check(job["tokens"], job["spec"], job.get("seed", 1),
                             {k: v for k, v in job.items() if k != "tokens"})
        _write(sys.argv[3], rec)
    elif mode == "checks":
        d = json.load(open(sys.argv[2]))
        spec = X.load_spec(d["spec_abs"])
        rc = X.reality_checks(d["body"], d["params"], spec, which=tuple(d.get("which") or
                              ("Ra", "Rb", "Rc", "Rde")))
        d["checks"] = rc
        d["summary"] = X.summarize_checks(rc)
        _write(sys.argv[3], d)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
