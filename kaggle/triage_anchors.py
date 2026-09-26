import sys,os,json,glob
from concurrent.futures import ProcessPoolExecutor,as_completed
WT="/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (WT,os.path.join(WT,"lna"),os.path.join(WT,"kaggle"),os.path.join(WT,"kaggle","loop")):
    sys.path.insert(0,p)
BUDGET=2500; SEEDS=(1,2,3); PDK="gf180mcu"
def libdir(cell):
    for L in ("editcap-lib-v1a","editcap-lib-v1b"):
        d=os.path.join(WT,"kaggle",L,cell)
        if os.path.exists(os.path.join(d,"anchor.net")): return d
def cells():
    s=set()
    for L in ("editcap-lib-v1a","editcap-lib-v1b"):
        for d in glob.glob(os.path.join(WT,"kaggle",L,"*","anchor.net")):
            s.add(os.path.basename(os.path.dirname(d)))
    return sorted(s)
def worst(spec,m):
    w=None
    for n,c in (spec.constraints or {}).items():
        if c.get("status")=="unsupported": continue
        a=m.get(n)
        if a is None: continue
        sc=spec._scale(c); mg=(a-c["min"])/sc if "min" in c else (c["max"]-a)/sc if "max" in c else None
        if mg is not None and (w is None or mg<w[1]): w=[n,round(mg,4)]
    return w
def one(cell):
    import proposal as P, bench_anchor_prep as PREP
    from spec import Spec
    d=libdir(cell); sp=os.path.join(d,"spec.yaml")
    tok=P.round_trip(open(os.path.join(d,"anchor.net")).read())["tokens"]
    spec=Spec.load(sp); best=None
    for s in SEEDS:
        try: r=PREP.smoke_run(list(tok),sp,s,BUDGET,PDK)
        except Exception: continue
        if r is None: continue
        wm=worst(spec,r.get("metrics") or {}); feas=bool(r.get("feasible"))
        k=(feas, wm[1] if wm else -1e9)
        if best is None or k>best[0]: best=(k,feas,wm)
    if best is None: return {"cell":cell,"error":"unsizable"}
    return {"cell":cell,"feasible":best[1],"worst":best[2]}
def main():
    cs=cells(); res=[]
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(one,c):c for c in cs}
        for i,f in enumerate(as_completed(futs),1):
            r=f.result(); res.append(r)
            print(f"[{i}/{len(cs)}] {r['cell']:22s} {'FEASIBLE' if r.get('feasible') else r.get('worst') or r.get('error')}",flush=True)
    feas=[r['cell'] for r in res if r.get('feasible')]
    print(f"\nANCHORS FEASIBLE at {SEEDS}x{BUDGET}: {len(feas)}/{len(cs)}")
    print("budget-margin survivors (anchor solves):", feas)
    json.dump({"budget":f"{len(SEEDS)}x{BUDGET}","feasible":feas,"all":res},
              open(os.path.join(WT,"kaggle","campaigns","editcap-v1-baseline","anchor-budget-triage.json"),"w"),indent=1,default=float)
if __name__=="__main__": main()
