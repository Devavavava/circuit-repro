#!/usr/bin/env bash
echo "=== WSL conda envs ==="
for e in /opt/miniconda/envs/*/; do
    n=$(basename "$e")
    v=$("$e/bin/python" --version 2>&1)
    echo "  $n : $v"
done
echo
echo "=== WSL ngspice ==="
ngspice -v 2>&1 | head -2
echo
echo "=== WSL disk used ==="
du -sh /root/circuit-repro /opt/miniconda 2>/dev/null
