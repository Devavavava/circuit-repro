#!/usr/bin/env bash
# CircuitSense under Linux. On Windows the equation-derivation stage failed
# 5/5 with "cannot pickle 'lcapy.mnacpts.Vstep'": it wraps lcapy analysis in
# multiprocessing for timeouts, and Windows spawn has to pickle those objects.
# Linux fork does not, so this should actually derive equations.
set -uo pipefail

CONDA=/opt/miniconda/bin/conda
ROOT=/root/circuit-repro
REPO=$ROOT/CircuitSense

echo "===== clone ====="
mkdir -p "$ROOT"
[ -d "$REPO" ] || git clone --quiet --depth 1 https://github.com/xz-group/CircuitSense.git "$REPO"

echo "===== env ====="
if [ ! -d /opt/miniconda/envs/circuitsense ]; then
    $CONDA create -y -n circuitsense -c conda-forge --override-channels python=3.10 2>&1 | tail -3
fi
PY=/opt/miniconda/envs/circuitsense/bin/python
$PY --version

echo "===== deps ====="
$PY -m pip install -q --no-warn-script-location -r "$REPO/requirements_lcapy.txt" 2>&1 | tail -3
$PY -m pip install -q --no-warn-script-location PyMuPDF PySpice readchar httpx tqdm 2>&1 | tail -3
$PY -c "import lcapy, sympy; print('lcapy', lcapy.__version__, '/ sympy', sympy.__version__)"

echo "===== run symbolic pipeline ====="
cd "$REPO"
PYTHONPATH=. $PY main.py --note smoke_linux --gen_num 5 --symbolic --derive_equations --show_sample_equations 2>&1 | tail -30

echo "===== result ====="
$PY - <<'PYEOF'
import json, os
p = "datasets/smoke_linux/symbolic_equations.json"
if not os.path.exists(p):
    print("no symbolic_equations.json produced"); raise SystemExit(1)
d = json.load(open(p))
s = d["summary"]
print("total_circuits :", s["total_circuits"])
print("successful     :", s["successful"])
print("failed         :", s["failed"])
print("success_rate   :", s["success_rate"])
print("equation_counts:", s["equation_counts"])
if s.get("error_breakdown"):
    print("errors         :", s["error_breakdown"])
for r in d["results"][:2]:
    print("\n--- sample result ---")
    print(json.dumps(r, indent=2)[:700])
PYEOF
