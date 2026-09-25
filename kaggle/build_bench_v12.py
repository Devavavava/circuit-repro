import sys,os,json,yaml,shutil
WT="/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (WT,WT+"/lna",WT+"/kaggle",WT+"/kaggle/loop"): sys.path.insert(0,p)
import proposal as P, bench_anchor_prep as PREP
from spec import Spec
PDK="bptm45"
WB_ANCH=WT+"/kaggle/editcap-lib-v1b/bnl-wb-r25-s10-00"   # current-reuse (shown failed circuit for wideband)
NB_ANCH=WT+"/kaggle/editcap-lib-v1a/bnl-1575-diag-t0"    # common-gate (shown failed circuit for narrowband)
BASE_WB=yaml.safe_load(open(WB_ANCH+"/spec.yaml")); BASE_NB=yaml.safe_load(open(NB_ANCH+"/spec.yaml"))
OUT=WT+"/kaggle/editcap-lib-v12-45nm"; shutil.rmtree(OUT,ignore_errors=True); os.makedirs(OUT)

def wb_spec(s11,s21,flo,fhi):
    d=json.loads(json.dumps(BASE_WB)); d["band"]={"type":"wideband","f0":(flo*fhi)**0.5,"f_lo":flo,"f_hi":fhi}
    d["constraints"]={"nf_db":{"max":3.0},"s11_max_db":{"max":s11},"s21_db":{"min":s21},
                      "s21_ripple_db":{"max":2.0},"idd_ma":{"max":10},"iip3_dbm":{"min":5,"status":"unsupported"}}
    d["name"]=f"v12-wb-s11n{abs(s11)}-g{s21}-b{int(flo/1e8):02d}{int(fhi/1e8):02d}"
    d["description"]=f"bench-v1.2 achievable-survivor wideband [{flo/1e9:.2g}-{fhi/1e9:.2g}]GHz S11<={s11} S21>={s21}"
    return d
def nb_spec(f0,s21):
    d=json.loads(json.dumps(BASE_NB)); d["band"]={"type":"narrowband","f0":f0,"f_lo":f0*0.98,"f_hi":f0*1.02}
    d["constraints"]={"nf_db":{"max":1.8},"s11_db":{"max":-10},"s21_db":{"min":s21},
                      "idd_ma":{"max":4},"iip3_dbm":{"min":-10,"status":"unsupported"}}
    d["name"]=f"v12-nb-f{int(f0/1e8):02d}-g{s21}"
    d["description"]=f"bench-v1.2 achievable-survivor narrowband {f0/1e9:.2g}GHz S21>={s21} NF<=1.8"
    return d

# the 8+8 GOOD tiers from calibration
WB=[(-8,12,5e8,3e9),(-8,10,5e8,3e9),(-9,10,5e8,3e9),(-10,10,5e8,3e9),
    (-10,10,8e8,2.4e9),(-10,12,8e8,2.4e9),(-11,10,8e8,2.4e9),(-11,12,8e8,2.4e9)]
NB=[(1.58e9,12),(1.58e9,14),(1.58e9,16),(1.58e9,18),(2.4e9,12),(2.4e9,14),(2.4e9,16),(2.4e9,18)]
specs=[("wb",WB_ANCH,wb_spec(*t)) for t in WB]+[("nb",NB_ANCH,nb_spec(*t)) for t in NB]

def worst(spec,m):
    out={};w=None
    for n,c in (spec.constraints or {}).items():
        if c.get("status")=="unsupported": continue
        a=m.get(n); sup=a is not None; mg=None
        if sup:
            sc=spec._scale(c); mg=(a-c["min"])/sc if "min" in c else (c["max"]-a)/sc if "max" in c else None
        out[n]={"achieved":a,"margin":mg,"supported":sup}
        if mg is not None and (w is None or mg<w[1]): w=[n,mg]
    return out,w

built=0
for kind,anchdir,d in specs:
    cd=OUT+"/"+d["name"]; os.makedirs(cd)
    yaml.safe_dump(d,open(cd+"/spec.yaml","w"))
    shutil.copy(anchdir+"/anchor.net",cd+"/anchor.net"); shutil.copy(anchdir+"/anchor.tokens.json",cd+"/anchor.tokens.json")
    # evidence = shown anchor sized on 45nm (fails), best-over-seeds
    tok=P.round_trip(open(cd+"/anchor.net").read())["tokens"]; spec=Spec.load(cd+"/spec.yaml"); best=None
    for s in (1,2,3):
        r=PREP.smoke_run(list(tok),cd+"/spec.yaml",s,1200,PDK)
        if r is None: continue
        mg,w=worst(spec,r.get("metrics") or {}); wm=w[1] if w else -9
        if best is None or wm>best[0]: best=(wm,r.get("metrics") or {},mg,w,bool(r.get("feasible")))
    m=best[1] if best else {}
    mg,w=worst(spec,m)
    ev={"spec":d["name"],"band":d["band"],"pdk":PDK,"anchor_family":("current-reuse" if kind=="wb" else "common-gate"),
        "feasible":bool(best[4]) if best else False,"worst_margin":w,"margins":mg,"metrics":m,"total_evals":3600}
    json.dump(ev,open(cd+"/evidence.json","w"),indent=1,default=float)
    built+=1
    print(f"  {d['name']:26s} anchor_feasible={ev['feasible']} worst={w}",flush=True)
print(f"\nbuilt {built} bench-v1.2 cells under editcap-lib-v12-45nm")
