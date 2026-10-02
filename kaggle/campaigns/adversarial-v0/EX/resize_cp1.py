"""G-CP1 recoverability (deviation D9; diagnostic for the user's ruling, nothing is added to
the verifier): re-size a design ONCE under rl-v1.1 (seed x 2500, smoke_run verbatim,
same capture as ex_lib.sized_run_v11) with the testbench's harness blocks made ideal:
  in  : Cp1 10 pF in parallel with 1 uF (ideal AC-coupled 50-ohm source)
  io  : Cp1 and Cp2 each in parallel with 1 uF (ideal AC coupling at both ports)
(parallel, so the verifier's port-DC check still finds its `Cp1 p1 VIN1 10p` anchor).
Answers: does the proposed guard remove capacity (the topology can no longer meet the
spec) or only the harness crutch (a re-size meets it honestly)?
usage: resize_cp1.py <variant in|io> <raw record.json> <out.json>
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402

CP2 = "Cp2 VOUT1 p2 10p"


def tb(body, variant):
    assert X.CP1_LINE in body and CP2 in body
    b = body.replace(X.CP1_LINE, X.CP1_LINE + "\nCp1x p1 VIN1 1u")
    if variant == "io":
        b = b.replace(CP2, CP2 + "\nCp2x VOUT1 p2 1u")
    return b


def main(variant, raw, out):
    r = json.load(open(raw))
    SZ = X.SZ
    orig = SZ.prepared_body

    def prep(*a, **k):
        res = orig(*a, **k)
        if res is None:
            return res
        body, sizable, fixed = res
        return tb(body, variant), sizable, fixed

    SZ.prepared_body = prep
    t0 = time.time()
    try:
        s = X.sized_run_v11(r["tokens"], f"{X.REPO}/{r['spec']}", int(r.get("seed", 1)))
    finally:
        SZ.prepared_body = orig
    res = s["res"] or {}
    rec = {"id": r.get("sid") or r.get("did"), "variant": variant, "spec": r["spec"],
           "seed": r.get("seed", 1), "meta": r.get("meta"),
           "feasible": bool(res.get("feasible")), "infeasible_reason": res.get("infeasible_reason"),
           "metrics": res.get("metrics"), "mu_min_wide": res.get("mu_min_wide"),
           "port_dc": res.get("port_dc"), "orig_metrics": (r.get("res") or {}).get("metrics"),
           "secs": round(time.time() - t0, 1)}
    tmp = out + ".tmp"
    json.dump(rec, open(tmp, "w"), default=repr)
    os.replace(tmp, out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
