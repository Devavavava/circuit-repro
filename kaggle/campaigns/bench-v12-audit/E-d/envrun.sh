#!/bin/bash
# env wrapper (inline copy of crenv.sh): envrun.sh <cmd...>
unset PYTHONPATH
export PATH=/home/dpatni/circuit-repro/.env/envs/cr/bin:$PATH
export NGSPICE=/home/dpatni/circuit-repro/.env/ngspice-47/bin/ngspice
export NGSPICE_LIBRARY_PATH=/home/dpatni/circuit-repro/.env/envs/cr/lib/libngspice.so
export SPICE_LIB_DIR=/home/dpatni/circuit-repro/.env/envs/cr/share/ngspice
export LNA_DEPS_ROOT=/home/dpatni/circuit-repro
export LD_LIBRARY_PATH=/home/dpatni/circuit-repro/.env/envs/cr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VACASK_HOME=/home/dpatni/circuit-repro/.env/vacask-0.3.4.rc1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TMPDIR=/tmp/cr-7cd7ffc3-d
exec "$@"
