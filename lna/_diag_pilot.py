"""WP-DIAGHEADS pilot: targeted vs random move selection (plans2/13 section 4).

Three phases, because two of them need torch (py3.8) and one needs the sizer
(py3.14):

  1. --predict   [analoggenie python]  train the multi-task ensemble with the
                 five pilot parents' WL FAMILIES excluded, run the diagnosis
                 heads on the parents, dump the head output.
  2. --plan      [py3.14]              generate both arms' children with
                 `moves.py` (READ-ONLY: moves are applied, the file is untouched).
  3. --size      [py3.14]              size all 20 children and score the arms.

The comparison is balanced by construction -- the same five parents, the same
number of children, the same ZOAF budget -- so the parent's own stored margin
(which came from a different campaign's sizing budget) cancels out of the
between-arm difference.
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SNAP = "v7-diag"
ARM = "diagheads-pilot"
N_CHILD = 2
SEED_RANDOM = 20260811
SEED_TARGETED = 20260812
ZOAF = dict(n_candidates=8, sgd_iters=8, cgd_iters=2)     # == evolve.py defaults

# plans2/13 section 4.2 -- fixed before the heads were trained.
ALLOWED = {
    "MOS": ("degen_add", "cascode_add", "input_class_swap", "stage_add"),
    "R": ("load_swap", "passive_type_swap", "match_elem_add"),
    "L": ("load_swap", "match_elem_add", "passive_type_swap"),
}
COND_EXTRA = ("stage_add", "cascode_remove")


# --------------------------------------------------------------- phase 1
def predict(out_path, n_models=3):
    import numpy as np
    import critic
    import critic_gnn as G
    import _diag_parents as P
    parents = P.select(5)
    data = critic.load_dataset(snapshot=SNAP)
    n_noise, n_cond = G.attach_diag(data, snapshot=SNAP)
    sigma = critic._sigma_s21(snapshot=SNAP)
    pw = [p["wl_hash"] for p in parents]
    t0 = time.time()
    models, tr, va, te = G.fit_diag(data, sigma / 12.0, n_models=n_models,
                                    exclude_fams=pw)
    print("pool %d -> train %d / val %d / test %d after excluding the parents' "
          "families (%d rows dropped)" % (len(data), len(tr), len(va), len(te),
                                          len(data) - len(tr) - len(va) - len(te)))
    key = {}
    for d in data:
        key[(d["row"].get("wl_hash"), d["row"].get("spec"),
             d["row"].get("ts"))] = d
    items, keep = [], []
    for p in parents:
        d = key.get((p["wl_hash"], p["spec"], p["ts"]))
        if d is None:
            print("MISSING parent row " + p["wl_hash"])
            continue
        items.append(d)
        keep.append(p)
    nlg, clp = G.diag_predict_ens(models, items)
    outp = {"snapshot": SNAP, "n_models": n_models, "secs": round(time.time() - t0, 1),
            "n_noise_rows": n_noise, "n_cond_rows": n_cond, "parents": []}
    for i, (p, d) in enumerate(zip(keep, items)):
        names = G.dev_names(d["topo"])
        noisy = [(j, nm) for j, nm in enumerate(names)
                 if G.base_of(nm) in G.NOISE_KINDS]
        rank = sorted(noisy, key=lambda t: -float(nlg[i, t[0]]))
        dom = rank[0][1]
        cond = {}
        for j, nm in enumerate(names):
            if G.base_of(nm) in ("NM", "PM"):
                cond[nm] = G.COND_CLASSES[int(np.argmax(clp[i, j]))]
        true = None
        if d.get("noise_lab"):
            true = max(d["noise_lab"], key=d["noise_lab"].get)
        outp["parents"].append({
            "wl_hash": p["wl_hash"], "spec": p["spec"], "binding": p["binding"],
            "worst_margin": p["worst"], "n_devices": p["n_devices"],
            "arm": p["arm"], "ts": p["ts"], "tokens": d["row"]["graph"]["tokens"],
            "dom": dom, "dom_kind": G.base_of(dom),
            "rank": [nm for _, nm in rank][:6],
            "cond": cond,
            "held_out_true_dom": true,
        })
        print("%-18s %-10s dom=%-5s (%s)  true=%-5s  cond=%s"
              % (p["wl_hash"], p["spec"], dom, G.base_of(dom), true,
                 json.dumps(cond)))
    with open(out_path, "w") as fh:
        json.dump(outp, fh, indent=1)
    print("wrote " + out_path)
    return 0


# --------------------------------------------------------------- phase 2
def _entry(nl, name):
    import moves as M
    for e in nl:
        if M.dname(e) == name:
            return e
    return None


def touches(parent_nl, child_nl, dom):
    """Did this edit actually land on `dom` (plans2/13 4.2, locality filter)?

    Three ways it can: `dom` is gone (removed/replaced), `dom` was rewired (any
    of its pins moved), or a NEW device was attached to one of the nets `dom`
    pins. Supply rails are excluded from the last test -- every circuit touches
    VDD/VSS, so counting them would make every move 'local' to everything."""
    import moves as M
    pe = _entry(parent_nl, dom)
    if pe is None:
        return False
    ce = _entry(child_nl, dom)
    if ce is None:
        return True
    if [str(x) for x in pe[1:]] != [str(x) for x in ce[1:]]:
        return True
    pnets = set(M.dnets(pe)) - set(M.SUPPLY)
    pnames = set(M.dname(e) for e in parent_nl)
    for e in child_nl:
        if M.dname(e) in pnames:
            continue
        if set(M.dnets(e)) & pnets:
            return True
    return False


def _draw(nl, spec, ctx, rng, n, parent_wl, accept=None, tries=800):
    import collections
    import moves as M
    got, seen = [], set([parent_wl])
    stats = collections.Counter()
    for _ in range(tries):
        child, name = M.mutate(nl, rng, ctx)
        stats["proposed"] += 1
        if not child:
            stats["no_move"] += 1
            continue
        if accept is not None and not accept(name, child):
            stats["off_target"] += 1
            continue
        r = M.realize(child, spec)
        if not r:
            stats["unrealizable"] += 1
            continue
        topo, seq, wl, canon = r
        if wl in seen:
            stats["dup"] += 1
            continue
        seen.add(wl)
        got.append({"move": name, "wl_hash": wl, "tokens": list(seq)})
        stats["kept"] += 1
        if len(got) >= n:
            break
    return got, dict(stats)


def plan(heads_path, out_path):
    import moves as M
    import templates as T
    from spec import Spec
    from topology import Topology
    H = json.load(open(heads_path))
    out = {"snapshot": SNAP, "zoaf": ZOAF, "n_child": N_CHILD,
           "seed_random": SEED_RANDOM, "seed_targeted": SEED_TARGETED,
           "parents": []}
    for i, p in enumerate(H["parents"]):
        spec = Spec.load(p["spec"])
        topo = Topology(p["tokens"])
        nl, ports = T.topo_to_netlist(topo)
        db = spec.topology.get("device_budget", [3, 16])
        ctx = {"max_dev": db[1], "min_dev": db[0],
               "max_inductors": spec.topology.get("max_inductors", 99)}
        kind = "MOS" if p["dom_kind"] in ("NM", "PM") else p["dom_kind"]
        allowed = set(ALLOWED.get(kind, ALLOWED["MOS"]))
        weak_or_off = [k for k, v in (p.get("cond") or {}).items()
                       if v in ("off", "weak")]
        if weak_or_off:
            allowed |= set(COND_EXTRA)
        rnd, srnd = _draw(nl, spec, ctx, random.Random(SEED_RANDOM + i), N_CHILD,
                          p["wl_hash"])
        dom = p["dom"]
        tgt, stgt = _draw(nl, spec, ctx, random.Random(SEED_TARGETED + i), N_CHILD,
                          p["wl_hash"],
                          accept=lambda nm, ch: (nm in allowed
                                                 and touches(nl, ch, dom)))
        fallback = 0
        if len(tgt) < N_CHILD:
            fallback = N_CHILD - len(tgt)
            more, s2 = _draw(nl, spec, ctx, random.Random(SEED_TARGETED + 100 + i),
                             N_CHILD - len(tgt), p["wl_hash"],
                             accept=lambda nm, ch: nm in allowed)
            tgt += more
            stgt["fallback_stats"] = s2
        rec = dict(p)
        rec.pop("tokens", None)
        rec.update(parent_tokens=p["tokens"], allowed=sorted(allowed),
                   weak_or_off=weak_or_off, fallback=fallback,
                   stats={"random": srnd, "targeted": stgt},
                   children={"random": rnd, "targeted": tgt})
        out["parents"].append(rec)
        print("%-18s %-10s dom=%-5s allowed=%s" % (p["wl_hash"], p["spec"], dom,
                                                   ",".join(sorted(allowed))))
        for arm in ("targeted", "random"):
            print("   %-9s %s" % (arm, ", ".join(
                "%s->%s" % (c["move"], c["wl_hash"][:8]) for c in rec["children"][arm])))
        if fallback:
            print("   (targeted fell back on locality for %d child(ren))" % fallback)
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote " + out_path)
    return 0


# --------------------------------------------------------------- phase 3
def feasibility_score(vec):
    """05-SIZING's feasibility-first scalar (== evolve.feasibility_score, five
    lines, copied rather than imported so this file pulls in no search stack)."""
    short = sum(min(v, 0.0) for v in vec)
    return short if short < 0 else sum(max(v, 0.0) for v in vec)


def margin_cols(spec):
    """== evolve.margin_cols: which of (S11, S21, Idd, NF) this spec gates."""
    cols = [0, 1, 2]
    c = spec.constraints.get("nf_db") or {}
    if c.get("status") != "unsupported" and c.get("max") is not None:
        cols.append(3)
    return cols


def _vec4(row):
    """(S11, S21, Idd, NF) normalized margins for a row-shaped dict."""
    import critic
    m = critic._margins(row)
    if m is None:
        return None
    return list(m) + [critic.nf_margin(row)]


def _score(row, spec):
    v = _vec4(row)
    if v is None:
        return None, None
    cols = margin_cols(spec)
    vec = [(-4.0 if v[c] is None else v[c]) for c in cols]
    return feasibility_score(vec), min(vec)


def size_children(plan_path, out_path, cap_secs=900):
    import datastore as ds
    import size as S
    from spec import Spec
    from topology import Topology
    plan_d = json.load(open(plan_path))
    store = ds.load("topo_labels")
    res = {"zoaf": plan_d["zoaf"], "cap_secs": cap_secs, "rows": []}
    for p in plan_d["parents"]:
        spec = Spec.load(p["spec"])
        prow = next((r for r in store if r.get("wl_hash") == p["wl_hash"]
                     and r.get("spec") == p["spec"] and r.get("ts") == p["ts"]), None)
        pfs, pmin = _score(prow, spec) if prow else (None, None)
        print("== parent %s %s dom=%s  parent fs=%s min=%s"
              % (p["wl_hash"], p["spec"], p["dom"],
                 None if pfs is None else round(pfs, 4),
                 None if pmin is None else round(pmin, 4)))
        for arm in ("targeted", "random"):
            for k, c in enumerate(p["children"][arm]):
                topo = Topology(c["tokens"])
                prov = {"source_arm": ARM, "pilot_arm": arm,
                        "parent_wl": p["wl_hash"], "parent_dom": p["dom"],
                        "move": c["move"], "child_i": k}
                t0 = time.time()
                try:
                    r = S.size_topology(topo, spec, seed=0, inductor_q=12,
                                        provenance=prov, **plan_d["zoaf"])
                except Exception as exc:
                    print("   %-9s %-8s %-16s SIZING RAISED %s"
                          % (arm, c["move"], c["wl_hash"][:16], exc))
                    r = None
                secs = time.time() - t0
                row = {"parent": p["wl_hash"], "spec": p["spec"], "arm": arm,
                       "move": c["move"], "wl_hash": c["wl_hash"],
                       "dom": p["dom"], "secs": round(secs, 1),
                       "parent_fs": pfs, "parent_min": pmin, "ok": r is not None,
                       "over_cap": secs > cap_secs}
                if r is not None:
                    m = r.get("metrics") or {}
                    fake = {"spec": p["spec"], "metrics": m,
                            "margins": ds.margins_for(spec, m)}
                    fs, mn = _score(fake, spec)
                    row.update(feasible=bool(r.get("feasible")), fs=fs, worst=mn,
                               n_evals=r.get("n_evals"),
                               s21=m.get("s21_db"), s11=m.get("s11_max_db",
                                                              m.get("s11_db")),
                               idd=m.get("idd_ma"), nf=m.get("nf_db"),
                               d_fs=(None if (fs is None or pfs is None)
                                     else fs - pfs),
                               d_worst=(None if (mn is None or pmin is None)
                                        else mn - pmin))
                res["rows"].append(row)
                print("   %-9s %-16s %-16s fs=%s d_fs=%s  %.0fs"
                      % (arm, c["move"], c["wl_hash"][:16],
                         None if row.get("fs") is None else round(row["fs"], 4),
                         None if row.get("d_fs") is None else round(row["d_fs"], 4),
                         secs))
                with open(out_path, "w") as fh:
                    json.dump(res, fh, indent=1)
    report(res)
    with open(out_path, "w") as fh:
        json.dump(res, fh, indent=1)
    print("wrote " + out_path)
    return 0


def report(res):
    rows = res["rows"]
    print("")
    print("=== targeted vs random, %d sizings ===" % len(rows))
    print("%-10s %5s %6s %10s %10s %8s %8s" % ("arm", "n", "sized", "mean d_fs",
                                               "mean d_worst", "n d_fs>0", "feas"))
    summ = {}
    for arm in ("targeted", "random"):
        a = [r for r in rows if r["arm"] == arm]
        ok = [r for r in a if r.get("d_fs") is not None]
        mfs = sum(r["d_fs"] for r in ok) / len(ok) if ok else float("nan")
        mw = (sum(r["d_worst"] for r in ok) / len(ok)) if ok else float("nan")
        pos = sum(1 for r in ok if r["d_fs"] > 0)
        feas = sum(1 for r in a if r.get("feasible"))
        summ[arm] = {"n": len(a), "sized": len(ok), "mean_d_fs": mfs,
                     "mean_d_worst": mw, "n_pos": pos, "feasible": feas}
        print("%-10s %5d %6d %10.4f %10.4f %8d %8d"
              % (arm, len(a), len(ok), mfs, mw, pos, feas))
    res["summary"] = summ
    if summ["targeted"]["sized"] and summ["random"]["sized"]:
        d = summ["targeted"]["mean_d_fs"] - summ["random"]["mean_d_fs"]
        print("")
        print("  targeted - random on mean d_fs = %+.4f  -> P4 %s"
              % (d, "MET" if d > 0 else "NOT MET"))
        res["p4_delta"] = d
        res["p4_met"] = bool(d > 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predict", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--size", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--heads", default="lna/out/_diag/heads.json")
    ap.add_argument("--plan-file", default="lna/out/_diag/plan.json")
    ap.add_argument("--out", default="lna/out/_diag/pilot.json")
    ap.add_argument("--n-models", type=int, default=3)
    a = ap.parse_args()
    if a.predict:
        return predict(a.heads, n_models=a.n_models)
    if a.plan:
        return plan(a.heads, a.plan_file)
    if a.size:
        return size_children(a.plan_file, a.out)
    if a.report:
        r = json.load(open(a.out))
        report(r)
        return 0
    ap.error("give --predict | --plan | --size | --report")


if __name__ == "__main__":
    sys.exit(main())
