"""Stage 2 shared definitions: circuits, regime hard constraints (pre-reg Stage 3), golden
demonstration specs, and a resumable parallel sizing-job runner.

Run every Stage 2 script from the worktree root through the env wrapper, e.g.
  ~/.claude/jobs/7cd7ffc3/tmp/run_cr.sh kaggle/campaigns/opamp-v0/stage2/goldens.py
"""
import json
import multiprocessing as mp
import os
import sys

CAMPAIGN = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, CAMPAIGN)
import opamp_v0 as O  # noqa: E402

RESULTS = os.path.join(CAMPAIGN, "stage2", "results")
os.makedirs(RESULTS, exist_ok=True)

LIB = {   # F1 library (anchors = ota5t, two_stage_rz)
    "ota5t": "circuits/lib/ota5t.net",
    "two_stage_rz": "circuits/lib/two_stage_rz.net",
    "telescopic": "circuits/lib/telescopic.net",
    "folded_cascode": "circuits/lib/folded_cascode.net",
    "three_stage_nmc": "circuits/lib/three_stage_nmc.net",
}
ANCHORS = ("ota5t", "two_stage_rz")
WITNESSES = {   # EVAL-ONLY
    "W-R1": "witnesses/w_r1_fc_cs.net",
    "W-R23": "witnesses/w_r23_affc.net",
    "W-R4": "witnesses/w_r4_complementary.net",
}
CIRCUITS = dict(LIB, **WITNESSES)

# Regime hard constraints, verbatim from PREREG-OPAMP-V0-D0.md Stage 3; M = the max: target.
REGIMES = {
    "R1": {"M": "gain_db", "spec": {"name": "R1-hard", "cl_pf": 2.0, "constraints": {
        "swing_vpp": {"min": 0.6}, "ugf_mhz": {"min": 10.0}, "pm_deg": {"min": 60.0},
        "idd_ua": {"max": 200.0}}}},
    "R23": {"M": "fom_mhzpf_ma", "spec": {"name": "R23-hard", "cl_pf": 200.0, "constraints": {
        "gain_db": {"min": 80.0}, "pm_deg": {"min": 55.0}, "idd_ua": {"max": 300.0}}}},
    "R4": {"M": "icmr_v", "spec": {"name": "R4-hard", "cl_pf": 2.0, "constraints": {
        "gain_db": {"min": 40.0}, "ugf_mhz": {"min": 5.0}, "pm_deg": {"min": 60.0},
        "idd_ua": {"max": 200.0}}}},
}
WITNESS_REGIME = {"W-R1": "R1", "W-R23": "R23", "W-R4": "R4"}


def _spec(name, cl, **c):
    cons = {}
    for k, v in c.items():
        kind, metric = k.split("_", 1)
        cons.setdefault(metric, {})[kind] = v
    return {"name": name, "cl_pf": cl, "constraints": cons}


# Golden demonstration specs (margin mode). Chosen by the Stage-2 builder (README, D-O19):
# the regime-style base (UGF/PM/Idd at CL 2 pF) plus one circuit-appropriate requirement.
GOLDEN_SPECS = {
    "ota5t": _spec("g-ota5t", 2.0, min_gain_db=25.0, min_ugf_mhz=10.0, min_pm_deg=60.0,
                   max_idd_ua=200.0),
    "two_stage_rz": _spec("g-two_stage_rz", 2.0, min_gain_db=55.0, min_swing_vpp=0.6,
                          min_ugf_mhz=10.0, min_pm_deg=60.0, max_idd_ua=200.0),
    "telescopic": _spec("g-telescopic", 2.0, min_gain_db=45.0, min_ugf_mhz=10.0,
                        min_pm_deg=60.0, max_idd_ua=200.0),
    "folded_cascode": _spec("g-folded_cascode", 2.0, min_gain_db=45.0, min_ugf_mhz=10.0,
                            min_pm_deg=60.0, max_idd_ua=200.0),
    "three_stage_nmc": _spec("g-three_stage_nmc", 2.0, min_gain_db=75.0, min_ugf_mhz=5.0,
                             min_pm_deg=55.0, max_idd_ua=200.0),
    "W-R1": _spec("g-W-R1", 2.0, min_gain_db=70.0, min_swing_vpp=0.6, min_ugf_mhz=10.0,
                  min_pm_deg=60.0, max_idd_ua=200.0),
    "W-R23": _spec("g-W-R23", 200.0, min_gain_db=80.0, min_ugf_mhz=1.0, min_pm_deg=55.0,
                   max_idd_ua=300.0),
    "W-R4": _spec("g-W-R4", 2.0, min_icmr_v=0.8, min_gain_db=40.0, min_ugf_mhz=5.0,
                  min_pm_deg=60.0, max_idd_ua=200.0),
}


def circuit_text(name):
    with open(os.path.join(CAMPAIGN, CIRCUITS[name])) as fh:
        return fh.read()


SUMMARY_KEYS = ("gain_db", "ugf_mhz", "pm_deg", "idd_ua", "swing_vpp", "swing_lo", "swing_hi",
                "icmr_v", "icmr_lo", "icmr_hi", "fom_mhzpf_ma", "slew_vus", "cmrr_db", "psrr_db",
                "vout_dc", "tran_settled", "flags", "valid")


def summary(r):
    m = r.get("metrics") or {}
    out = {k: m.get(k) for k in SUMMARY_KEYS}
    out.update(feasible=r["feasible"], worst_margin=r.get("worst_margin"), target=r.get("target"),
               target_raw=r.get("target_raw"), best_eval=r.get("best_eval"), evals=r.get("evals"),
               cpu_s=r.get("cpu_s"), secs=r.get("secs"), n_params=len(r.get("params") or {}),
               n_devices=len(O.parse(r["netlist"])))
    return out


def run_job(job):
    """job: dict(tag, circuit, spec, objective, seed, evals[, netlist]). Writes RESULTS/<tag>.json."""
    path = os.path.join(job.get("outdir") or RESULTS, job["tag"] + ".json")
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    os.environ.setdefault("OPAMP_V0_TMP", "/home/dpatni/.claude/jobs/7cd7ffc3/tmp/opamp")
    text = job.get("netlist") or circuit_text(job["circuit"])
    r = O.size(text, job["spec"], seed=job["seed"], evals=job["evals"], objective=job["objective"])
    rec = {"job": {k: v for k, v in job.items() if k != "netlist"}, "summary": summary(r),
           "params": r.get("params"), "margins": r.get("margins"),
           "op": (r.get("metrics") or {}).get("op"), "netlist": r["netlist"],
           "profile": r["profile"], "prefilter": r["prefilter"]}
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=str)
    os.replace(tmp, path)
    s = rec["summary"]
    print("%-28s feas=%s tgt=%s wm=%s gain=%.2f ugf=%s pm=%s idd=%.1f cpu=%.0fs" % (
        job["tag"], s["feasible"], s["target_raw"], s["worst_margin"], s["gain_db"] or -1,
        s["ugf_mhz"], s["pm_deg"], s["idd_ua"] or -1, s["cpu_s"]), flush=True)
    return rec


def run_jobs(jobs, procs=4):
    if procs <= 1:
        return [run_job(j) for j in jobs]
    with mp.Pool(procs) as pool:
        return pool.map(run_job, jobs, chunksize=1)
