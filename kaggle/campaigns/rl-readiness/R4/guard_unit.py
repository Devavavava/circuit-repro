"""Unit-test the post-hoc R4 guards (bench_anchor_prep._r4_posthoc) on CAPTURED
winners without re-sizing: the recorded result dict + decode := the captured
winner params. Compares guard verdicts with r4_post's independent measurements.
usage: guard_unit.py <out.json> <raw.json> [raw.json ...]"""
import sys, os, json, copy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r4_sim as S                                           # noqa: E402
import bench_anchor_prep as PREP                             # noqa: E402

FLAGS = {"VERIFY_FINITE": "1", "VERIFY_NF_BAND": "1", "VERIFY_NO_INERT": "1",
         "VERIFY_ROBUST": "10", "VERIFY_BAND_METRICS": "1"}


def main(out, raws):
    rows = []
    for fn in raws:
        rec = json.load(open(fn))
        if not rec.get("params_win"):
            continue
        spec = S.spec_of(rec)
        row = {"raw": os.path.basename(fn)}
        for k in FLAGS:
            os.environ.pop(k, None)
        res = copy.deepcopy(rec["result"])
        PREP_before = json.dumps(res, sort_keys=True)
        # flags unset: smoke_run does not call the hook; the hook itself must be a no-op
        PREP._r4_posthoc(res, spec, rec["body"], rec["sizable"],
                         lambda x: rec["params_win"], rec["x_win"], rec["seed"])
        row["flags_off_noop"] = json.dumps(res, sort_keys=True) == PREP_before
        os.environ.update(FLAGS)
        res = copy.deepcopy(rec["result"])
        PREP._r4_posthoc(res, spec, rec["body"], rec["sizable"],
                         lambda x: rec["params_win"], rec["x_win"], rec["seed"])
        for k in FLAGS:
            os.environ.pop(k, None)
        row.update({k: res.get(k) for k in ("feasible", "infeasible_reason", "nf_band_max_db",
                                            "inert_devices", "robust_frac", "nonfinite_metrics")})
        row["recorded_feasible"] = rec["result"]["feasible"]
        # NaN injection: VERIFY_FINITE must reject
        res = copy.deepcopy(rec["result"])
        res["metrics"] = dict(res["metrics"], s21_db=float("nan"))
        res["feasible"] = bool(spec.feasible(res["metrics"])[0])
        row["nan_injected_spec_feasible"] = res["feasible"]
        os.environ["VERIFY_FINITE"] = "1"
        PREP._r4_posthoc(res, spec, rec["body"], rec["sizable"],
                         lambda x: rec["params_win"], rec["x_win"], rec["seed"])
        os.environ.pop("VERIFY_FINITE")
        row["nan_injected_after_guard"] = res["feasible"]
        rows.append(row)
        print(row, flush=True)
    json.dump(rows, open(out, "w"), indent=1, default=repr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
