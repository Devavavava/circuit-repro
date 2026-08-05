#!/usr/bin/env bash
# Definitively confirm AutoCkt's gym env drives a real ngspice simulation:
# take one env.step() and show the SPICE artifacts it leaves behind.
# (/tmp is tmpfs and was wiped when the WSL VM restarted, hence this re-check.)
set -uo pipefail

PY=/opt/miniconda/envs/autockt/bin/python
REPO=/root/circuit-repro/AutoCkt
cd "$REPO"
export PYTHONPATH=$REPO

rm -rf /tmp/ckt_da
echo "before: /tmp/ckt_da exists? $([ -d /tmp/ckt_da ] && echo yes || echo no)"

$PY - <<'PYEOF'
from autockt.envs.ngspice_vanilla_opamp import TwoStageAmp
env = TwoStageAmp({"generalize": True, "run_valid": False})
obs = env.reset()
print("obs shape        :", obs.shape)
obs, reward, done, info = env.step(env.action_space.sample())
print("reward from step :", reward)
print("cur specs        :", dict(env.cur_specs) if hasattr(env, "cur_specs") else "n/a")
PYEOF

echo
echo "after: /tmp/ckt_da exists? $([ -d /tmp/ckt_da ] && echo yes || echo no)"
D=/tmp/ckt_da/designs_two_stage_opamp
echo "design dirs: $(ls "$D" 2>/dev/null | wc -l)"
one=$(ls -d "$D"/*/ 2>/dev/null | head -1)
echo "sample dir : $one"
ls -la "$one" 2>/dev/null
echo
echo "=== ngspice AC output (first 3 lines) ==="
head -3 "$one"ac.csv 2>/dev/null || ls "$one"
