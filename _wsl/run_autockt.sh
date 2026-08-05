#!/usr/bin/env bash
# Run AutoCkt's real PPO/RLlib training loop with ngspice in the loop,
# capped at a few iterations (the repo's own stop condition is convergence).
set -uo pipefail

PY=/opt/miniconda/envs/autockt/bin/python
REPO=/root/circuit-repro/AutoCkt
cd "$REPO"

echo "===== rllib needs cv2 (atari wrappers import it unconditionally) ====="
$PY -m pip install -q --no-warn-script-location "opencv-python-headless<4.7" 2>&1 | tail -3
$PY -c "import ray.rllib.agents.ppo as ppo; print('rllib PPO import: OK')" || exit 1

echo "===== point netlist at the bundled PTM 45nm models ====="
$PY eval_engines/ngspice/ngspice_inputs/correct_inputs.py
grep -m1 '\.include' eval_engines/ngspice/ngspice_inputs/netlist/two_stage_opamp.cir

echo "===== generate design specs ====="
mkdir -p autockt/gen_specs
$PY autockt/gen_specs.py --num_specs 20
ls -la autockt/gen_specs/

echo "===== capped training script ====="
# Same PPO config as val_autobag_ray.py, but stop after 2 iterations with a
# smaller batch and fewer workers so this stays a smoke test, not a training run.
cat > autockt/val_autobag_ray_smoke.py <<'PYEOF'
import ray
import ray.tune as tune
from autockt.envs.ngspice_vanilla_opamp import TwoStageAmp

ray.init(num_cpus=4, object_store_memory=int(1e9))

config_train = {
    "sample_batch_size": 50,
    # PPO defaults sgd_minibatch_size to 128, so train_batch_size must be >= that.
    "train_batch_size": 256,
    "sgd_minibatch_size": 64,
    "num_sgd_iter": 2,
    "horizon": 30,
    "num_gpus": 0,
    "model": {"fcnet_hiddens": [64, 64]},
    "num_workers": 2,
    "env_config": {"generalize": True, "run_valid": False},
}

trials = tune.run_experiments({
    "train_45nm_ngspice_smoke": {
        "checkpoint_freq": 1,
        "run": "PPO",
        "env": TwoStageAmp,
        "stop": {"training_iteration": 2},
        "config": config_train,
    },
})
print("SMOKE TRAINING COMPLETE")
PYEOF

echo "===== run PPO (2 iterations, ngspice in the loop) ====="
# README runs this from ipython at the top level, which puts the repo root on
# sys.path; invoking the script directly does not, hence the explicit PYTHONPATH.
export PYTHONPATH=$REPO
time $PY autockt/val_autobag_ray_smoke.py 2>&1 | tail -70
echo "RUN EXIT: $?"
