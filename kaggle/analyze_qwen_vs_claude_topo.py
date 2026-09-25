import sys,glob,os,re
def parse(txt):
    devs=[]
    for ln in txt.splitlines():
        ln=ln.strip()
        if not ln or ln.startswith("*"): continue
        t=ln.split()
        if not t: continue
        typ=t[0].upper()
        if typ in ("NMOS","PMOS") and len(t)>=6:
            devs.append((typ,t[1],t[2],t[3],t[4],t[5]))  # type,name,D,G,S,B
        elif typ in ("R","C","L") and len(t)>=4:
            devs.append((typ,t[1],t[2],t[3]))             # type,name,a,b
    return devs
SUP={"VDD","VSS","0"}
def has_shunt_feedback(devs):
    mos=[d for d in devs if d[0] in ("NMOS","PMOS")]
    drains_sig=set(); gates_sig=set()
    for _,nm,D,G,S,B in mos:
        diode=(D==G)
        if not diode:
            drains_sig.add(D); gates_sig.add(G)
    for d in devs:
        if d[0]=="R":
            a,b=d[2],d[3]
            if a in SUP or b in SUP: continue
            # feedback: one end a signal drain, other end a signal gate
            if (a in drains_sig and b in gates_sig) or (b in drains_sig and a in gates_sig):
                return True
    return False
def has_cascode(devs):
    mos=[d for d in devs if d[0]in("NMOS","PMOS")]
    dr={}  # drain node -> device
    for m in mos: dr.setdefault(m[2],[]).append(m)
    for _,nm,D,G,S,B in mos:
        diode=(D==G)
        if diode: continue
        # this device's source is another device's drain (stacked), and gate is a fixed/supply/bypassed node
        if S in dr and G in SUP:   # upper device gate at VDD/VSS = cascode
            return True
        if S in dr and G not in (m[3] for m in mos if True):  # gate not signal-driven (rough)
            pass
    return False
def has_tank(devs):
    # an L and a C sharing a node that is also a transistor drain
    lnodes=set(); cnodes=set()
    for d in devs:
        if d[0]=="L": lnodes|={d[2],d[3]}
        if d[0]=="C": cnodes|={d[2],d[3]}
    drains=set(m[2] for m in devs if m[0]in("NMOS","PMOS"))
    shared=(lnodes & cnodes & drains)-SUP
    return len(shared)>0

def analyze(files):
    fb=casc=tank=0; n=0; ex_fb=[]
    for f in files:
        devs=parse(open(f).read()); n+=1
        if has_shunt_feedback(devs): fb+=1; ex_fb.append(f)
        if has_cascode(devs): casc+=1
        if has_tank(devs): tank+=1
    return n,fb,casc,tank,ex_fb

WB=sorted(glob.glob("/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"+"/kaggle/campaigns/editcap-v1-baseline/batch-*/adjudication/bnl-wb-*/B/edit*.net"))
NB=sorted(glob.glob("/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"+"/kaggle/campaigns/editcap-v1-baseline/batch-*/adjudication/bnl-1575-*/B/edit*.net")+
          glob.glob("/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"+"/kaggle/campaigns/editcap-v1-baseline/batch-*/adjudication/bnl-09-*/B/edit*.net"))
# positive controls: my templates
print("=== POSITIVE CONTROLS (my solutions) ===")
for name,f in (("wb shunt-fb","/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"+"/kaggle/claude-solutions/templates/wideband_shunt_feedback.net"),
               ("nb cascode-tank","/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"+"/kaggle/claude-solutions/templates/narrowband_cascode_tank.net")):
    d=parse(open(f).read()); print(f"  {name}: shunt_fb={has_shunt_feedback(d)} cascode={has_cascode(d)} tank={has_tank(d)}")
print("\n=== QWEN WIDEBAND edits (need: shunt-feedback) ===")
n,fb,casc,tank,ex=analyze(WB)
print(f"  {n} edits: with shunt-feedback={fb}  cascode={casc}  tank={tank}")
if ex: print("  example WITH feedback:", os.path.relpath(ex[0],"/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180"))
print("\n=== QWEN NARROWBAND-gain edits (need: cascode + tank) ===")
n,fb,casc,tank,ex=analyze(NB)
print(f"  {n} edits: cascode={casc}  tank={tank}  shunt-feedback={fb}")
