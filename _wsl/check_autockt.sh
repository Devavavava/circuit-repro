#!/usr/bin/env bash
# Locate the ngspice artifacts produced by AutoCkt's RL rollouts.
echo "=== /tmp contents ==="
ls -la /tmp | head -20
echo
echo "=== search for ckt_da / design dirs anywhere ==="
find / -maxdepth 6 -name "ckt_da" -o -maxdepth 6 -name "designs_two_stage_opamp" 2>/dev/null | head
echo
echo "=== any two_stage_opamp netlist copies written by the wrapper ==="
find / -name "two_stage_opamp_*" -maxdepth 8 2>/dev/null | head -5
echo
echo "=== what BASE_TMP_DIR resolves to ==="
/opt/miniconda/envs/autockt/bin/python -c "import os; print(os.path.abspath('/tmp/ckt_da'))"
echo
echo "=== confirm ngspice binary is what the wrapper calls ==="
which ngspice && ngspice -v 2>&1 | head -2
