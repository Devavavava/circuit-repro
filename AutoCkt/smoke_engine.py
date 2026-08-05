"""AutoCkt smoke test: the ngspice-in-the-loop evaluation engine.

The RL half of AutoCkt (ray==0.6.3 / tensorflow==1.10.1) has no Windows wheels,
but eval_engines/ is independent of Ray: it renders the two-stage op-amp netlist
with a given sizing, invokes ngspice, parses the AC sweep and returns the specs
(gain / UGBW / phase margin / Ibias) plus the RL reward. That is the part this
script exercises -- one full design evaluation, which is the inner loop the agent
would call at every step.

Two Windows adaptations, both confined to this driver (the repo is not modified):
  * NgSpiceWrapper.simulate() shells out with the POSIX redirect
    "ngspice -b <f> >/dev/null 2>&1", which cmd.exe cannot parse -> replaced with
    an equivalent subprocess call.
  * ngspice from msys2 is a GUI-subsystem binary that writes nothing to stdout, so
    output goes to a log file via -o (the netlist's own `wrdata` still produces the
    data file the parser reads).
"""
import os
import subprocess
import sys

REPO = r"C:\Users\Devavrat\circuit-repro\AutoCkt\repo"
NGSPICE = r"C:\msys64\ucrt64\bin\ngspice.exe"
WORK = r"C:\Users\Devavrat\circuit-repro\AutoCkt\work"
sys.path.insert(0, REPO)
os.chdir(REPO)

from eval_engines.ngspice.ngspice_wrapper import NgSpiceWrapper
from eval_engines.ngspice.TwoStageClass import TwoStageClass


def simulate_win(self, fpath):
    """Windows-safe replacement for the POSIX-redirect os.system call."""
    log = os.path.splitext(fpath)[0] + ".log"
    proc = subprocess.run([NGSPICE, "-b", "-o", log, fpath],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return 0 if proc.returncode == 0 else 1


NgSpiceWrapper.simulate = simulate_win

yaml_path = os.path.join(REPO, "eval_engines/ngspice/ngspice_inputs/yaml_files/two_stage_opamp.yaml")
env = TwoStageClass(num_process=1, yaml_path=yaml_path, path=REPO, root_dir=WORK)
print("netlist :", env.base_design_name)
print("work dir:", env.gen_dir)

# A mid-range sizing from the yaml's own parameter ranges.
state = dict(mp1=10, mn1=38, mp3=4, mn3=9, mn4=20, mn5=20, cc=2.1e-12)
print("sizing  :", state)

state_out, specs, info = env.create_design_and_simulate(state, verbose=True)
print("\ninfo (0 == no simulator error):", info)
print("--- SPECS FROM NGSPICE ---")
for k, v in specs.items():
    print(f"  {k:6s} = {v}")

# The reward the RL agent would receive for these specs against a target.
target = {"gain": 300, "ugbw": 1.0e7, "phm": 60, "ibias": 0.001}
print("\ntarget specs:", target)
ok = (specs["gain"] is not None and specs["ugbw"] is not None
      and specs["phm"] is not None and specs["ibias"] is not None)
print("\nSMOKE TEST:", "PASS - ngspice-in-the-loop evaluation returned all specs"
      if ok and info == 0 else "FAIL")
sys.exit(0 if ok and info == 0 else 1)
