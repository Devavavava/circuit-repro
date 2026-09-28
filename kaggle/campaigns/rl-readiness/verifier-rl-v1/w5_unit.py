"""W5 unit test for the lna/extract.py shared-core change (nf_max_db).

usage: w5_unit.py <out.json>

1. Byte-identity at the function level vs the COMMITTED (HEAD) extract.py
   (loaded from `git show HEAD:lna/extract.py` into a private module):
     - build_noise_deck(...) default text identical, for every design below
     - run_and_extract(...) dict identical on the LIBRARY spec (no nf_max_db)
     - measure_nf(...) identical
2. New path correctness on recorded R4 winners (body + final params):
     - measure_nf_band f0 value == measure_nf (bit-for-bit)
     - measure_nf_band max == R4's post-hoc nf_over_band (51-point print max)
     - run_and_extract on the rl-v1-form spec carries nf_max_db and nf_db
3. Cost: wall time of measure_nf vs measure_nf_band (same deck + vecmax),
   N repeats each, interleaved.
"""
import sys, os, json, time, subprocess, types
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)
import extract as E                                           # noqa: E402
import bench_anchor_prep as PREP                              # noqa: E402
from spec import Spec                                         # noqa: E402

R4 = REPO + "/kaggle/campaigns/rl-readiness/R4/results.json"
LIB = REPO + "/kaggle/editcap-lib-v12-45nm"
N_TIME = 15


def head_extract():
    src = subprocess.run(["git", "-C", REPO, "show", "HEAD:lna/extract.py"],
                         capture_output=True, text=True, check=True).stdout
    mod = types.ModuleType("extract_head")
    mod.__file__ = REPO + "/lna/extract.py"      # same model-card resolution
    exec(compile(src, "extract_head", "exec"), mod.__dict__)
    return mod


def pick_rows():
    rows = json.load(open(R4))["rows"]
    want = [("s1", "v12-wb-s11n10-g10-b0824", "template", 1),
            ("s1", "v12-wb-s11n10-g10-b0824", "ec:72945e70a2a1:131", 1),
            ("s1", "v12-wb-s11n8-g10-b0530", "template", 2),
            ("nb", "v12-nb-f15-g16", "template", 1),
            ("nb", "v12-nb-f24-g12", "anchor:lna-a1-inddegen-cascode", 1)]
    out = []
    for tag, cell, cand, seed in want:
        m = [r for r in rows if r["tag"] == tag and r["cell"] == cell
             and r["cand"] == cand and r["seed"] == seed and r.get("params_win")]
        if m:
            out.append(m[0])
    return out


def main(outp):
    H = head_extract()
    res = {"designs": [], "timing": {}}
    od = os.path.join(os.environ.get("TMPDIR", "/tmp"), "rlv1-specs", str(os.getpid()))
    t_nf, t_band = [], []
    for r in pick_rows():
        lib = Spec.load(f"{LIB}/{r['cell']}/spec.yaml")
        rl = Spec.load(PREP.rl_v1_spec(f"{LIB}/{r['cell']}/spec.yaml", out_dir=od))
        body, params = r["body"], PREP._stab_params(lib, r["params_win"])
        b = lib.band
        f0, flo, fhi = float(b["f0"]), float(b["f_lo"]), float(b["f_hi"])
        d_new = E.build_noise_deck(body, params, f0, flo, fhi)
        d_old = H.build_noise_deck(body, params, f0, flo, fhi)
        m_new = E.run_and_extract(body, params, lib)
        m_old = H.run_and_extract(body, params, lib)
        nf_new = E.measure_nf(body, params, lib)
        nf_old = H.measure_nf(body, params, lib)
        f0v, mx = E.measure_nf_band(body, params, rl)
        post = PREP.nf_over_band(lib, body, r["params_win"])
        m_rl = E.run_and_extract(body, params, rl)
        rec = {"row": f"R4 {r['tag']} {r['cell']} {r['cand']} s{r['seed']}",
               "noise_deck_default_identical_to_HEAD": d_new == d_old,
               "run_and_extract_lib_identical_to_HEAD":
                   json.dumps(m_new, sort_keys=True) == json.dumps(m_old, sort_keys=True),
               "measure_nf_identical_to_HEAD": nf_new == nf_old,
               "nf_f0_measure_nf": nf_new, "nf_f0_band_deck": f0v,
               "band_f0_equals_measure_nf": f0v == nf_new,
               "nf_max_db_band_deck": mx, "nf_over_band_R4_posthoc": post,
               "abs_diff_vs_R4_posthoc": (abs(mx - post) if None not in (mx, post) else None),
               "rlv1_run_and_extract_nf_max_db": m_rl.get("nf_max_db") if m_rl else None,
               "rlv1_run_and_extract_nf_db": m_rl.get("nf_db") if m_rl else None,
               "lib_run_and_extract_has_nf_max_db": "nf_max_db" in (m_new or {}),
               "recorded_winner_nf_db": (r["result"].get("metrics") or {}).get("nf_db"),
               "rlv1_nf_limit": (rl.constraints.get("nf_max_db") or rl.constraints.get("nf_db"))}
        res["designs"].append(rec)
        print(json.dumps(rec), flush=True)
        for _ in range(N_TIME):
            t = time.time(); E.measure_nf(body, params, lib); t_nf.append(time.time() - t)
            t = time.time(); E.measure_nf_band(body, params, rl); t_band.append(time.time() - t)
    med = lambda v: sorted(v)[len(v) // 2]
    res["timing"] = {"n_each": len(t_nf), "measure_nf_median_s": round(med(t_nf), 4),
                     "measure_nf_band_median_s": round(med(t_band), 4),
                     "measure_nf_mean_s": round(sum(t_nf) / len(t_nf), 4),
                     "measure_nf_band_mean_s": round(sum(t_band) / len(t_band), 4)}
    ds = res["designs"]
    res["all_ok"] = all(d["noise_deck_default_identical_to_HEAD"]
                        and d["run_and_extract_lib_identical_to_HEAD"]
                        and d["measure_nf_identical_to_HEAD"]
                        and d["band_f0_equals_measure_nf"]
                        and not d["lib_run_and_extract_has_nf_max_db"]
                        and d["abs_diff_vs_R4_posthoc"] is not None
                        and d["abs_diff_vs_R4_posthoc"] < 1e-4 for d in ds)
    print(json.dumps(res["timing"]), "all_ok=", res["all_ok"])
    json.dump(res, open(outp, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
