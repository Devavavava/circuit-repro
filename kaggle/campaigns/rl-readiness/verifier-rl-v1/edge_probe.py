"""Where is the rl-v1 wide-mu minimum, and how close to 1 is it really?
usage: edge_probe.py <rawdir> <out.json>

For every rl-v1 `diff` run whose final winner was captured (body + params_win),
re-run the rl-v1 wide sweep (sp lin 1001 1e7..5e10, same lets as
extract.measure_stability) with 12 printed digits and report the mu minimum,
its frequency, mu at the first grid points, and the verdict the gate saw
(recorded mu_min_wide, from `meas` at default precision).
"""
import sys, os, json, re
REPO = "/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (REPO, REPO + "/lna", REPO + "/kaggle", REPO + "/kaggle/loop"):
    sys.path.insert(0, p)
import extract as E                                           # noqa: E402


def curve(body, params):
    lines = [body.rstrip(), ".param " + " ".join(f"{k}={v}" for k, v in params.items()),
             "\n".join([".control", "set numdgt=12", "op", "sp lin 1001 1e7 5e10 1"]
                       + E._stability_lets() + ["print mul", ".endc", ".end"])]
    txt = E.run_deck("\n".join(lines) + "\n", "edge_", "s.cir", timeout=120) or ""
    pts = []
    for ln in txt.splitlines():
        t = ln.split()
        if len(t) == 3 and re.match(r"^\d+$", t[0]):
            try:
                pts.append((float(t[1]), float(t[2])))
            except ValueError:
                pass
    return pts


def main(rawdir, outp):
    out = []
    for f in sorted(os.listdir(rawdir)):
        if not f.startswith("diff__"):
            continue
        r = json.load(open(os.path.join(rawdir, f)))
        res = r.get("result") or {}
        if not r.get("params_win") or not res.get("spec_feasible"):
            continue
        pts = curve(r["body"], r["params_win"])
        if not pts:
            continue
        fmin, mmin = min(pts, key=lambda p: p[1])
        rec = {"cell": r["cell"], "cand": r["cand"], "seed": r["seed"],
               "final_feasible": res.get("feasible"),
               "mu_min_wide_recorded": res.get("mu_min_wide"),
               "mu_min_12dig": mmin, "argmin_hz": fmin,
               "argmin_is_10MHz_edge": fmin == pts[0][0],
               "mu_at_10MHz": pts[0][1], "mu_at_60MHz": pts[1][1] if len(pts) > 1 else None,
               "interior_mu_min": min(p[1] for p in pts[1:]),
               "n_pts": len(pts)}
        out.append(rec)
        print(json.dumps(rec), flush=True)
    json.dump(out, open(outp, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
