"""V2 replay: AutoCkt's stored two-stage deck, re-pointed at the bptm45 card the harness uses
(lna/pdk/bptm45 adapter -> AutoCkt 45nm_bulk.txt), run through the harness's ngspice runner
and row reader, must reproduce the stored ac.csv. Pass: same number of rows and
max relative complex difference <= 1e-6 (the stored file has 8 significant digits)."""
import math
import os
import re

from common import dump
import opamp_v0  # noqa: F401  (puts lna/ on sys.path)
from opamp_v0 import testbench as TB

DIR = os.path.join(TB.REPO, "AutoCkt", "work", "designs_two_stage_opamp",
                   "two_stage_opamp_10_38_4_9_20_20_2.1e-122594")
DECK = os.path.join(DIR, "two_stage_opamp_10_38_4_9_20_20_2.1e-12.cir")


def main():
    wd = TB.work_dir()
    src = open(DECK).read()
    src = re.sub(r'\.include ".*?"', '.include "%s"' % TB.MODEL_PATH, src)
    src = re.sub(r"wrdata \S+ac\.csv", "wrdata %s/ac_replay.csv" % wd, src)
    src = re.sub(r"wrdata \S+dc\.csv", "wrdata %s/dc_replay.csv" % wd, src)
    text, err = TB.run_ngspice(src, wd, ["ac_replay.csv", "dc_replay.csv"])
    new = TB.read_rows(os.path.join(wd, "ac_replay.csv"))
    old = TB.read_rows(os.path.join(DIR, "ac.csv"))
    n = min(len(new), len(old))
    worst, worst_f = 0.0, None
    for a, b in zip(new[:n], old[:n]):
        za, zb = complex(a[1], a[2]), complex(b[1], b[2])
        d = abs(za - zb) / max(abs(zb), 1e-30)
        if d > worst:
            worst, worst_f = d, b[0]
    fdiff = max(abs(a[0] - b[0]) / b[0] for a, b in zip(new[:n], old[:n]))
    # AutoCkt drives the differential input with +gain at v(net6): metrics on A = +v(net6)
    neg = [[r[0], -r[1], -r[2]] for r in new]
    negold = [[r[0], -r[1], -r[2]] for r in old]
    m_new, m_old = TB.ac_metrics(neg), TB.ac_metrics(negold)
    idd_new = TB.read_rows(os.path.join(wd, "dc_replay.csv"))
    idd_old = TB.read_rows(os.path.join(DIR, "dc.csv"))
    ok = (len(new) == len(old) and n > 0 and worst <= 1e-6 and fdiff <= 1e-9)
    res = {"gate": "V2", "pass": ok, "rows_new": len(new), "rows_stored": len(old),
           "worst_rel_diff": worst, "worst_at_hz": worst_f, "freq_rel_diff": fdiff,
           "model": TB.MODEL_PATH, "ngspice": TB.NGSPICE,
           "metrics_replay": m_new, "metrics_stored": m_old,
           "dc_replay": idd_new, "dc_stored": idd_old,
           "dc_gain_vv": abs(complex(new[0][1], new[0][2])) if new else None}
    dump("v2.json", res)
    print("rows new/stored %d/%d worst rel diff %.3g (at %s Hz) freq diff %.3g; gain %.4f V/V; "
          "dc i(vdd) replay %s stored %s" % (len(new), len(old), worst, worst_f, fdiff,
                                              res["dc_gain_vv"] or math.nan, idd_new, idd_old))
    print("V2", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
