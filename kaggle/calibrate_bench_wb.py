import sys,os,json,yaml,itertools,tempfile
from concurrent.futures import ProcessPoolExecutor,as_completed
WT="/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"
for p in (WT,WT+"/lna",WT+"/kaggle",WT+"/kaggle/loop"): sys.path.insert(0,p)
PDK="bptm45"; SEEDS=(1,2,3); BUDGET=2500
ANCHOR=WT+"/kaggle/editcap-lib-v1b/bnl-wb-r25-s10-00/anchor.net"      # naive current-reuse (shown failed circuit)
SFB=WT+"/kaggle/claude-solutions/templates/wideband_shunt_feedback.net"  # Claude's best broadband topology
BASE=yaml.safe_load(open(WT+"/kaggle/editcap-lib-v1b/bnl-wb-r25-s10-00/spec.yaml"))

def make_spec(s11,s21,nf,rip,idd,flo,fhi):
    d=json.loads(json.dumps(BASE))  # deep copy
    d["band"]={"type":"wideband","f0":(flo*fhi)**0.5,"f_lo":flo,"f_hi":fhi}
    d["constraints"]={"nf_db":{"max":nf},"s11_max_db":{"max":s11},"s21_db":{"min":s21},
                      "s21_ripple_db":{"max":rip},"idd_ma":{"max":idd},
                      "iip3_dbm":{"min":5,"status":"unsupported"}}
    d["name"]=f"wbX-s11{abs(s11)}-g{s21}-b{int(flo/1e8)}{int(fhi/1e8)}"
    return d

def size(spec_path,net,budget):
    import proposal as P, bench_anchor_prep as PREP
    from spec import Spec
    tok=P.round_trip(open(net).read())["tokens"]; spec=Spec.load(spec_path); best=None
    for s in SEEDS:
        try: r=PREP.smoke_run(list(tok),spec_path,s,budget,PDK)
        except Exception: continue
        if r is None: continue
        feas=bool(r.get("feasible"))
        if best is None or feas>best: best=feas
        if best: break
    return bool(best)

def test(cand):
    d=cand; tf=tempfile.NamedTemporaryFile("w",suffix=".yaml",delete=False,dir=os.environ.get("TMPDIR","/tmp"))
    yaml.safe_dump(d,tf); tf.close()
    anchor_ok=size(tf.name,ANCHOR,BUDGET)     # challenge iff FALSE
    claude_ok=size(tf.name,SFB,BUDGET)        # achievable iff TRUE
    os.unlink(tf.name)
    return {"name":d["name"],"cons":{k:(v.get('min',v.get('max'))) for k,v in d["constraints"].items() if k!='iip3_dbm'},
            "band":[d["band"]["f_lo"],d["band"]["f_hi"]],
            "anchor_solves":anchor_ok,"claude_solves":claude_ok,
            "good_benchmark_cell": (not anchor_ok) and claude_ok}

# candidate grid: frontier s11/gain + band width variations (narrower = easier match)
cands=[]
for s11 in (-8,-9,-10,-11):
  for s21 in (10,12):
    for (flo,fhi) in ((5e8,3e9),(8e8,2.4e9),(1e9,2e9)):
      cands.append(make_spec(s11,s21,3.0,2.0,10,flo,fhi))
print(f"testing {len(cands)} candidate wideband specs (anchor-fail + claude-solve @3x{BUDGET})",flush=True)
res=[]
with ProcessPoolExecutor(max_workers=8) as ex:
    futs={ex.submit(test,c):c for c in cands}
    for i,f in enumerate(as_completed(futs),1):
        r=f.result(); res.append(r)
        print(f"[{i}/{len(cands)}] {r['name']:26s} anchor={'Y' if r['anchor_solves'] else 'N'} claude={'Y' if r['claude_solves'] else 'N'} {'<-- GOOD' if r['good_benchmark_cell'] else ''}",flush=True)
good=[r for r in res if r["good_benchmark_cell"]]
print(f"\nGOOD achievable-survivor cells (anchor fails, Claude solves): {len(good)}/{len(cands)}")
json.dump(res,open(WT+"/kaggle/campaigns/editcap-v1-baseline/calibrate-wb.json","w"),indent=1)
