"""Harness-block diagnostic for the C-cp1 class (D8; diagnostic, outside the pre-registered
R-a, which changes only the SOURCE side): for every verifier-passing design, the full
spec + wide-mu evaluation (ex_lib.full_eval, no re-sizing) with
  P1o   output harness block Cp2 10 pF -> 1 uF (ideal AC-coupled 50-ohm load)
  P1io  both blocks -> 1 uF (ideal AC-coupled source AND load)
plus the DUT's own input series capacitor value (the device(s) at VIN1).
usage: harness_diag.py <out.json> <raw.json files ...>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ex_lib as X  # noqa: E402

CP2 = "Cp2 VOUT1 p2 10p"


def variants(body):
    assert X.CP1_LINE in body and CP2 in body
    o = body.replace(CP2, "Cp2 VOUT1 p2 1u")
    return {"P1o": o, "P1io": o.replace(X.CP1_LINE, "Cp1 p1 VIN1 1u")}


def own_cin(body, params):
    """values (F) of the capacitors with a terminal on VIN1 (DUT side)."""
    out = {}
    for ln in body.splitlines():
        t = ln.split()
        if len(t) >= 4 and t[0].upper().startswith("C") and t[0] != "Cp1" and "VIN1" in t[1:3]:
            v = t[3].strip("{}")
            try:
                out[t[0]] = float(params.get(v, v))
            except (TypeError, ValueError):
                out[t[0]] = None
    return out


def main(out, files):
    res = {}
    if os.path.exists(out):
        res = json.load(open(out))
    specs = {}
    for f in files:
        try:
            r = json.load(open(f))
        except Exception:                                        # noqa: BLE001
            continue
        did = r.get("sid") or r.get("did")
        if not r.get("verifier_pass") or not r.get("params") or did in res:
            continue
        if r["spec"] not in specs:
            specs[r["spec"]] = X.load_spec(f"{X.REPO}/{r['spec']}")
        spec = specs[r["spec"]]
        row = {"cin": own_cin(r["body"], r["params"])}
        for k, b in variants(r["body"]).items():
            e = X.full_eval(b, r["params"], spec)
            row[k] = {"ok": e["ok"], "mag": e["mag"], "worst": e.get("worst")}
        res[did] = row
    json.dump(res, open(out, "w"), indent=0)
    n = len(res)
    for k in ("P1o", "P1io"):
        print(k, "strict fail", sum(not v[k]["ok"] for v in res.values()), "/", n,
              " material(>0.02)", sum(v[k]["mag"] > X.MATERIAL for v in res.values()))


if __name__ == "__main__":
    import glob
    main(sys.argv[1], [f for a in sys.argv[2:] for f in (sorted(glob.glob(a)) if "*" in a else [a])])
