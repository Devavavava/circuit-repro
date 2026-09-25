import sys,os,json,yaml,tempfile
from concurrent.futures import ProcessPoolExecutor,as_completed
WT="/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (WT,WT+"/lna",WT+"/kaggle",WT+"/kaggle/loop"): sys.path.insert(0,p)
PDK="bptm45"; SEEDS=(1,2,3); BUDGET=2500
ANCHOR=WT+"/kaggle/editcap-lib-v1a/bnl-1575-diag-t0/anchor.net"        # naive common-gate (shown)
CASC=WT+"/kaggle/claude-solutions/templates/narrowband_cascode_tank.net"  # Claude's cascode+tank
BASE=yaml.safe_load(open(WT+"/kaggle/editcap-lib-v1a/bnl-1575-diag-t0/spec.yaml"))
def make_spec(f0,s21,nf,s11,idd):
    d=json.loads(json.dumps(BASE))
    d["band"]={"type":"narrowband","f0":f0,"f_lo":f0*0.98,"f_hi":f0*1.02}
    d["constraints"]={"nf_db":{"max":nf},"s11_db":{"max":s11},"s21_db":{"min":s21},
                      "idd_ma":{"max":idd},"iip3_dbm":{"min":-10,"status":"unsupported"}}
    d["name"]=f"nbX-f{f0/1e9:.2g}-g{s21}-nf{nf}"
    return d
def size(sp,net,b):
    import proposal as P, bench_anchor_prep as PREP
    from spec import Spec
    tok=P.round_trip(open(net).read())["tokens"]; best=None
    for s in SEEDS:
        try: r=PREP.smoke_run(list(tok),sp,s,b,PDK)
        except Exception: continue
        if r is None: continue
        if bool(r.get("feasible")): return True
    return False
def test(d):
    tf=tempfile.NamedTemporaryFile("w",suffix=".yaml",delete=False,dir=os.environ.get("TMPDIR","/tmp"))
    yaml.safe_dump(d,tf); tf.close()
    a=size(tf.name,ANCHOR,BUDGET); c=size(tf.name,CASC,BUDGET); os.unlink(tf.name)
    return {"name":d["name"],"cons":{k:(v.get('min',v.get('max'))) for k,v in d["constraints"].items() if k!='iip3_dbm'},
            "f0":d["band"]["f0"],"anchor_solves":a,"claude_solves":c,"good":(not a) and c}
cands=[]
for f0 in (0.9e9,1.58e9,2.4e9):
  for s21 in (12,14,16,18):
    cands.append(make_spec(f0,s21,1.8,-10,4))
print(f"testing {len(cands)} narrowband candidates (CG-fail + cascode-solve @3x{BUDGET})",flush=True)
res=[]
with ProcessPoolExecutor(max_workers=8) as ex:
    futs={ex.submit(test,c):c for c in cands}
    for i,f in enumerate(as_completed(futs),1):
        r=f.result(); res.append(r)
        print(f"[{i}/{len(cands)}] {r['name']:20s} anchor={'Y' if r['anchor_solves'] else 'N'} claude={'Y' if r['claude_solves'] else 'N'} {'<-- GOOD' if r['good'] else ''}",flush=True)
good=[r for r in res if r["good"]]
print(f"\nGOOD narrowband achievable-survivor cells: {len(good)}/{len(cands)}")
json.dump(res,open(WT+"/kaggle/campaigns/editcap-v1-baseline/calibrate-nb.json","w"),indent=1)
