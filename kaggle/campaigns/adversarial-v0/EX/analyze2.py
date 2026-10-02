"""EX final analysis (supersedes analyze.py, which covered seeds + phase-1 only).

Reads every full raw output (strict seeds, extended record, search children of both
phases, guard-impact witnesses), the harness diagnostic (harness_diag.py), the R-b
diagnostics (rb_diag.json, osc50_mech.json, window_scan.json) and the impact snapshot.
Writes results/summary.json (compact) and prints the tables used in README.md.

Exploit = verifier (rl-v1.1) PASS and a MATERIAL reality-check failure:
  R-a  P1 (1 uF AC-coupled source) or P2 (DC-grounded source) worst normalized
       violation > 0.02 (the bench-v2 2 % cushion on the constraint scale)
  R-b  a LINEAR oscillation (grows/sustains from the 1 uA kick) under any of the 25
       terminations (1 mA-only limit cycles are W4 large-signal, not scored)
  R-c  dense-grid worst normalized violation > 0.02
Classes (by mechanism; see README):
  C-cp1    R-a fails and P2 adds nothing beyond P1  (harness 10 pF input block is
           part of the design's matching network)
  C-pdc    R-a P2 fails materially more than P1     (port-DC; closed by rl-v1.1?)
  C-osc50  R-b linear oscillation with r50/r50 terminations (internal loop: the
           verifier's own 50-ohm bench oscillates, mu cannot see it)
  C-oscX   R-b linear oscillation only under reactive terminations
  C-grid   R-c material
Independence: distinct search ROOTS (a seed / extended / impact record is its own
root; a child inherits its parent's root) AND distinct topologies (tok).
usage: analyze2.py <out summary.json>
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.environ.get("TMPDIR", "/tmp/cr-7cd7ffc3-ex")
M = 0.02
CORNERS = ("T-40", "T85", "V0.9", "V1.1")


def load():
    recs = []
    for grp, pat in (("seed", f"{T}/raw/seeds/S*.json"), ("ext", f"{T}/raw/ext/E*.json"),
                     ("search", f"{T}/ex-jobs/G*.out.json"), ("impact", f"{T}/raw/impact/I*.json")):
        for f in sorted(glob.glob(pat)):
            try:
                r = json.load(open(f))
            except Exception:                                    # noqa: BLE001
                continue
            r["grp"] = grp
            r["id"] = r.get("sid") or r.get("did")
            if grp == "search":
                r["phase"] = 2 if int(r["id"][1:4]) >= 60 else 1
            else:
                r["root"] = r["id"]
            recs.append(r)
    return recs


def tags_of(r):
    s = r.get("summary") or {}
    ra = s.get("Ra") or {}
    p1, p2 = (ra.get("P1") or {}).get("mag", 0.0), (ra.get("P2") or {}).get("mag", 0.0)
    rb = s.get("Rb") or {}
    lin = rb.get("linear_osc") or []
    rc = (s.get("Rc") or {}).get("mag", 0.0)
    cls = []
    if max(p1, p2) > M:
        cls.append("C-cp1" if p2 <= p1 + M else "C-pdc")
    if lin:
        cls.append("C-osc50" if "r50/r50" in lin else "C-oscX")
    if rc > M:
        cls.append("C-grid")
    return cls, {"P1": p1, "P2": p2, "Rc": rc, "Rb_linear": lin}


def frag(r):
    rde = ((r.get("summary") or {}).get("Rde")) or {}
    return {k: (bool((rde.get(k) or {}).get("perf_ok")), bool((rde.get(k) or {}).get("stable")),
                (rde.get(k) or {}).get("perf_worst")) for k in CORNERS}


def main(out):
    recs = load()
    hd = json.load(open(f"{T}/harness_diag.json")) if os.path.exists(f"{T}/harness_diag.json") else {}
    snap = json.load(open(f"{HERE}/impact_snapshot.json"))
    byid = {r["id"]: r for r in recs}
    passing = [r for r in recs if r.get("verifier_pass") and r.get("summary")]
    # ---------------- search stats
    gens = [json.loads(ln) for ln in open(f"{T}/state/gens.jsonl")]
    kids = [json.loads(ln) for ln in open(f"{T}/state/results.jsonl")]
    st = {}
    for ph in (1, 2):
        g = [x for x in gens if (x.get("phase") or 1) == ph]
        k = [x for x in kids if (x.get("phase") or 1) == ph]
        sized = [x for x in k if x.get("sized")]
        st[f"phase{ph}"] = {
            "gens": len(g), "children_drawn": len(k), "sized": len(sized),
            "pre_sizing_rejects": dict(Counter(x["why"].split(":")[0] for x in k if not x.get("sized"))),
            "verifier_pass": sum(bool(x.get("verifier_pass")) for x in sized),
            "pass_with_material_failure": sum(bool((x.get("summary") or {}).get("material")) for x in sized
                                              if x.get("verifier_pass"))}
    grp_stats = {}
    for grp in ("seed", "ext", "search", "impact"):
        L = [r for r in recs if r["grp"] == grp]
        P = [r for r in L if r.get("verifier_pass") and r.get("summary")]
        grp_stats[grp] = {"n": len(L), "verifier_pass": len(P),
                          "reproduced": sum(bool(r.get("reproduced")) for r in L if "reproduced" in r),
                          "exploit": sum(bool(tags_of(r)[0]) for r in P)}
    # ---------------- classes
    inst = defaultdict(list)
    for r in passing:
        cls, mags = tags_of(r)
        for c in cls:
            inst[c].append({"id": r["id"], "grp": r["grp"], "root": r.get("root"), "tok": r.get("tok"),
                            "spec": os.path.basename(r["spec"]), "mags": mags,
                            "phase": r.get("phase")})
    classes = {}
    for c, L in sorted(inst.items()):
        roots = {i["root"] for i in L}
        toks = {i["tok"] for i in L}
        mags = sorted(max(i["mags"]["P1"], i["mags"]["P2"]) if c in ("C-cp1", "C-pdc") else 1.0
                      for i in L)
        classes[c] = {"n_instances": len(L), "n_roots": len(roots), "n_topologies": len(toks),
                      "by_group": dict(Counter(i["grp"] for i in L)),
                      "qualifies": len(roots) >= 2 and len(toks) >= 2,
                      "mag_median": mags[len(mags) // 2], "mag_max": mags[-1],
                      "mag_bins": dict(Counter(("<=0.05" if m <= 0.05 else "<=0.1" if m <= 0.1 else
                                                "<=0.2" if m <= 0.2 else ">0.2") for m in mags)),
                      "instances": [i["id"] for i in L]}
    # C-cp1 by band and worst metric
    cp1_band = defaultdict(lambda: [0, 0])
    worst = Counter()
    for r in passing:
        sp = os.path.basename(r["spec"]).replace("probe-amd1-", "probe-").replace("__rlv1", "")
        b = sp.split("-")[1] if not sp.startswith("v12") else sp.split("-")[2] + "-" + sp.split("-")[1]
        cls, mags = tags_of(r)
        cp1_band[b][1] += 1
        if "C-cp1" in cls:
            cp1_band[b][0] += 1
            worst[((r["summary"].get("Ra") or {}).get("P1") or {}).get("worst")] += 1
    # ---------------- harness diag
    hdiag = {}
    for k in ("P1o", "P1io"):
        v = [hd[r["id"]][k] for r in passing if r["id"] in hd]
        hdiag[k] = {"n": len(v), "strict_fail": sum(not x["ok"] for x in v),
                    "material": sum(x["mag"] > M for x in v)}
    hdiag["P1_strict_fail"] = sum(not ((r["summary"].get("Ra") or {}).get("P1") or {}).get("ok", True)
                                  for r in passing)
    hdiag["P1_material"] = sum(((r["summary"].get("Ra") or {}).get("P1") or {}).get("mag", 0) > M
                               for r in passing)
    cin = [v["cin"] for v in hd.values() if v.get("cin")]
    hdiag["own_input_C_present"] = f"{sum(bool(c) for c in cin)}/{len(hd)}"
    # ---------------- guard impact on accepted cells / training witnesses
    imp_rows = {}
    for r in recs:
        if r["grp"] == "impact":
            kind = r["kinds"][0]
            imp_rows[r["meta"][kind]] = (kind, r)
    for name, v in snap["reuse"].items():
        if v["record"] in byid:
            imp_rows[name] = (v["kind"], byid[v["record"]])
    impact = {}
    for kind in ("cell", "train"):
        L = [(n, r) for n, (k, r) in imp_rows.items() if k == kind]
        P = [(n, r) for n, r in L if r.get("verifier_pass") and r.get("summary")]
        row = {"n_total": len(L), "n_rl_v11_pass": len(P),
               "n_rl_v11_fail": len(L) - len(P),
               "fail_reasons": dict(Counter(((r.get("res") or {}).get("infeasible_reason") or "spec/stability")
                                            .split(":")[0][:40] for n, r in L
                                            if not (r.get("verifier_pass") and r.get("summary"))))}
        g = {}
        g["G-CP1in (Cp1->1uF), strict"] = sorted(n for n, r in P if not r["summary"]["Ra"]["P1"]["ok"])
        g["G-CP1in, material"] = sorted(n for n, r in P if r["summary"]["Ra"]["P1"]["mag"] > M)
        g["G-CP1io (Cp1,Cp2->1uF), strict"] = sorted(n for n, r in P if r["id"] in hd and not hd[r["id"]]["P1io"]["ok"])
        g["G-CP1io, material"] = sorted(n for n, r in P if r["id"] in hd and hd[r["id"]]["P1io"]["mag"] > M)
        g["G-OSC50 (r50/r50 linear osc)"] = sorted(n for n, r in P if "r50/r50" in (r["summary"]["Rb"]["linear_osc"] or []))
        g["any linear R-b"] = sorted(n for n, r in P if r["summary"]["Rb"]["linear_osc"])
        g["R-c material"] = sorted(n for n, r in P if r["summary"]["Rc"]["mag"] > M)
        row["guards"] = {k: {"n": len(v), "names": v} for k, v in g.items()}
        impact[kind] = row
    # ---------------- R-c / R-b small print
    rc_mu = [r["id"] for r in passing if (r["summary"]["Rc"]["mag"] or 0) > 0]
    rc_max = max((r["summary"]["Rc"]["mag"] or 0) for r in passing)
    ls = [r["id"] for r in passing if r["summary"]["Rb"]["large_signal_only"]]
    # ---------------- fragility
    fr = {}
    for grp in ("seed", "ext", "search", "impact", "all"):
        L = [r for r in passing if grp == "all" or r["grp"] == grp]
        row = {"n": len(L)}
        for k in CORNERS:
            f = [frag(r)[k] for r in L]
            row[k] = {"perf_within_2pct": sum(x[0] for x in f), "stable_mu>=1": sum(x[1] for x in f),
                      "both": sum(x[0] and x[1] for x in f)}
        row["all_4_corners"] = sum(all(frag(r)[k][0] and frag(r)[k][1] for k in CORNERS) for r in L)

        def gross(r, k):
            c = (((r.get("checks") or {}).get("Rde") or {}).get(k)) or {}
            mw = c.get("mu_wide")
            return ((c.get("perf_worst") if c.get("perf_worst") is not None else 1.0) > 0.10
                    or not isinstance(mw, (int, float)) or mw < 0.98
                    or not isinstance(c.get("mu_inband"), (int, float)) or c["mu_inband"] < 0.98)
        row["gross_fail (perf viol>0.10 or mu<0.98)"] = {k: sum(gross(r, k) for r in L) for k in CORNERS}
        row["gross_fail_any_corner"] = sum(any(gross(r, k) for k in CORNERS) for r in L)
        fr[grp] = row
    rs = {}
    for f in sorted(glob.glob(f"{T}/raw/resize/*.io.json")):
        x = json.load(open(f))
        rs[os.path.basename(f)[:-8]] = {"feasible": x["feasible"], "reason": x.get("infeasible_reason")}
    recov = {"n": len(rs), "feasible_after_resize": sum(v["feasible"] for v in rs.values()),
             "reasons": dict(Counter((v["reason"] or "")[:50] for v in rs.values() if not v["feasible"])),
             "rows": rs}
    res = {"search": st, "G-CP1io_recoverability": recov, "groups": grp_stats, "n_verifier_pass_checked": len(passing),
           "classes": classes, "cp1_by_band": {k: f"{a}/{b}" for k, (a, b) in sorted(cp1_band.items())},
           "cp1_P1_worst_metric": dict(worst), "harness_diag": hdiag, "impact": impact,
           "impact_snapshot": {k: v for k, v in snap.items() if k != "reuse"},
           "Rc": {"n_mag_gt0": len(rc_mu), "max_mag": rc_max, "ids_gt0": rc_mu},
           "Rb_large_signal_only": ls, "fragility": fr}
    json.dump(res, open(out, "w"), indent=1, default=repr)
    show = {k: res[k] for k in ("search", "groups", "G-CP1io_recoverability", "n_verifier_pass_checked", "cp1_by_band",
                                "cp1_P1_worst_metric", "harness_diag", "Rc")}
    print(json.dumps(show, indent=1))
    for c, v in classes.items():
        print(c, {k: v[k] for k in v if k != "instances"})
        if len(v["instances"]) <= 12:
            print("   ", v["instances"])
    for kind, v in impact.items():
        print(kind, {k: v[k] for k in v if k != "guards"})
        for g, x in v["guards"].items():
            print("   ", g, x["n"], x["names"][:20])
    print(json.dumps(fr, indent=0))


if __name__ == "__main__":
    main(sys.argv[1])
