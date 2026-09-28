"""Item (f): how Spec.feasible / Spec.objective and the extraction regex treat
non-finite values. usage: nan_probe.py <out.json>"""
import sys, os, json, math, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_drv as D                                           # noqa: E402
from spec import Spec                                        # noqa: E402
import extract as E                                          # noqa: E402

spec = Spec.load(f"{D.LIB}/v12-nb-f15-g16/spec.yaml")
good = {"s11_db": -12.0, "s21_db": 17.0, "nf_db": 1.5, "idd_ma": 3.0}
out = {}
for k in list(good):
    for bad in (float("nan"), float("inf"), -float("inf"), None):
        m = dict(good, **{k: bad})
        f, v = spec.feasible(m)
        out[f"{k}={bad}"] = {"feasible": f, "viol": v, "objective": spec.objective(m)}
# what the extraction regex does with ngspice's non-finite spellings
pat = rf"m_s21_f0\s*=\s*{E._NUM}"
for txt in ("m_s21_f0 = nan", "m_s21_f0 = -nan", "m_s21_f0 = inf", "m_s21_f0 = -inf",
            "m_s21_f0 = 1.2e+01"):
    mm = re.search(pat, txt, re.IGNORECASE)
    g = mm.group(1) if mm else None
    try:
        val = float(g) if g is not None else None
        err = None
    except ValueError as e:
        val, err = None, repr(e)
    out[f"regex[{txt}]"] = {"group": g, "float": val, "error": err}
json.dump(out, open(sys.argv[1], "w"), indent=1, default=repr)
for k, v in out.items():
    print(k, v)
