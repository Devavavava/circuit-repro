"""WP-DIAGHEADS Bar 2: does the multi-task model regress the shipped margin head?

plans2/13 section 3. Both arms are trained IN ONE PROCESS on LITERALLY the same
splits and the same spec scaler, so the comparison is a comparison of models and
not of splits -- the two separate `--eval` runs this replaces each recomputed
`family_split` and could in principle have disagreed for that reason alone.

Writes its JSON after every configuration and prints unbuffered, because a long
CPU job on a shared machine gets reaped and a buffered result is a lost one.

    "<analoggenie py>" -u lna/_diag_nonreg.py --snapshot v7-diag --n-models 3
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import critic                      # noqa: E402
import critic_gnn as G             # noqa: E402
import datastore as ds             # noqa: E402


def _row(tag, te, mean, std, sigma_norm):
    Yte = np.array([d["y"] for d in te])
    rhos = [critic.spearman(Yte[:, k], mean[:, k]) for k in range(3)]
    nf_i = [i for i, d in enumerate(te) if d.get("y_nf") is not None]
    rho_nf = (critic.spearman(np.array([te[i]["y_nf"] for i in nf_i]),
                              mean[nf_i, 3]) if len(nf_i) >= 3 else float("nan"))
    st = critic.c1_stats(Yte, critic._feasibility_score(mean[:, :3]))
    err = np.abs(mean[:, 1] - Yte[:, 1])
    out = {"tag": tag, "n_test": len(te), "rho_S11": rhos[0], "rho_S21": rhos[1],
           "rho_Idd": rhos[2], "rho_NF": rho_nf,
           "rankacc": critic.pairwise_rank_acc(Yte[:, 1], mean[:, 1], sigma_norm),
           "prec20": st["prec"], "skill": st["skill"], "base": st["base"],
           "unc_cal": critic.spearman(std[:, 1], err),
           "C1": bool(critic.c1_pass(rhos[1], st["skill"]))}
    return out


def run(snapshot=None, n_models=3, out=None, only=None):
    data = critic.load_dataset(snapshot=snapshot)
    n_noise, n_cond = G.attach_diag(data, snapshot=snapshot)
    sigma = critic._sigma_s21(snapshot=snapshot)
    sigma_norm = sigma / 12.0
    print("Bar 2 -- snapshot=%s, %d rows, sigma_S21=%.3f, diag labels %d noise / "
          "%d conduction, ens-%d" % (snapshot, len(data), sigma, n_noise, n_cond,
                                     n_models), flush=True)
    sp = ds.family_split(k_holdout=0.25, rows=[d["row"] for d in data])
    id2d = dict((id(d["row"]), d) for d in data)
    splits = []
    tr = [id2d[id(r)] for r in sp["train"] if id(r) in id2d]
    va = [id2d[id(r)] for r in sp["val"] if id(r) in id2d]
    te = [id2d[id(r)] for r in sp["test"] if id(r) in id2d]
    splits.append(("family-holdout", tr, va, te))
    tr2, te2 = critic._source_shift(data)
    va2_ids = set(id(d) for d in tr2[::6])
    splits.append(("source-shift",
                   [d for d in tr2 if id(d) not in va2_ids],
                   [d for d in tr2 if id(d) in va2_ids], te2))
    if only:
        splits = [s for s in splits if s[0] == only]
    res = {"snapshot": snapshot, "n_models": n_models, "sigma_S21": sigma,
           "n_noise_rows": n_noise, "n_cond_rows": n_cond, "rows": []}
    for split_name, a, b, c in splits:
        print("\n== %s: train %d / val %d / test %d ==" % (split_name, len(a),
                                                           len(b), len(c)),
              flush=True)
        for diag in (False, True):
            t0 = time.time()
            S = np.array([critic.spec_vector(d["spec"]) for d in a], np.float32)
            G._SPEC_MU = (S.mean(0), S.std(0) + 1e-6)   # TRAIN only, both arms
            mean, std = G.ensemble_predict(a, b, c, sigma_norm, n=n_models,
                                           diag=diag)
            r = _row("multi-task" if diag else "margin-only", c, mean, std,
                     sigma_norm)
            r.update(split=split_name, secs=round(time.time() - t0, 1),
                     n_train=len(a), n_val=len(b))
            res["rows"].append(r)
            print("  %-11s rho_S11 %+.3f  rho_S21 %+.3f  rho_Idd %+.3f  "
                  "rho_NF %+.3f  rankacc %.3f  prec@20 %.3f  skill %.3f  "
                  "unc_cal %+.3f  C1 %s  [%.0fs]"
                  % (r["tag"], r["rho_S11"], r["rho_S21"], r["rho_Idd"],
                     r["rho_NF"], r["rankacc"], r["prec20"], r["skill"],
                     r["unc_cal"], r["C1"], r["secs"]), flush=True)
            if out:
                with open(out, "w") as fh:
                    json.dump(res, fh, indent=1, default=float)
    verdict(res)
    if out:
        with open(out, "w") as fh:
            json.dump(res, fh, indent=1, default=float)
        print("wrote " + out, flush=True)
    return 0


def verdict(res):
    print("\n=== Bar 2 (plans2/13 section 3): rho(S21) within 0.02 of "
          "margin-only on BOTH splits, and Gate C1 still passing ===", flush=True)
    ok = True
    for split in ("family-holdout", "source-shift"):
        a = next((r for r in res["rows"] if r["split"] == split
                  and r["tag"] == "margin-only"), None)
        b = next((r for r in res["rows"] if r["split"] == split
                  and r["tag"] == "multi-task"), None)
        if not a or not b:
            print("  %-15s INCOMPLETE" % split, flush=True)
            ok = False
            continue
        d = b["rho_S21"] - a["rho_S21"]
        good = d >= -0.02
        ok = ok and good
        print("  %-15s margin-only %.3f -> multi-task %.3f  (%+.3f)  %s"
              % (split, a["rho_S21"], b["rho_S21"], d,
                 "OK" if good else "REGRESSION"), flush=True)
    c1 = next((r["C1"] for r in res["rows"] if r["split"] == "family-holdout"
               and r["tag"] == "multi-task"), None)
    print("  Gate C1 on family holdout, multi-task: %s" % c1, flush=True)
    res["bar2_met"] = bool(ok and c1)
    print("  Bar 2: %s" % ("MET -- the multi-task model may ship as the critic"
                           if res["bar2_met"] else
                           "NOT MET -- the diagnosis heads ship as a SEPARATE "
                           "model (Block 10, adopt-only-if-better)"), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot")
    ap.add_argument("--n-models", type=int, default=3)
    ap.add_argument("--out", default="lna/data/reports/diagheads-nonreg.json")
    ap.add_argument("--only", choices=("family-holdout", "source-shift"),
                    help="run one split (the other half is already in the JSON)")
    a = ap.parse_args()
    return run(snapshot=a.snapshot, n_models=a.n_models, out=a.out,
               only=a.only)


if __name__ == "__main__":
    sys.exit(main())
