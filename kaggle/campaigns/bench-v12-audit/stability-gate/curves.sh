#!/bin/bash
# mu(f) diagnostics on 5 gated winners (where is the wide mu minimum?)
D=/home/dpatni/circuit-repro/.claude/worktrees/externals-gf180/kaggle/campaigns/bench-v12-audit/stability-gate
O=$D/curves
mkdir -p $O
$D/envrun.sh python $D/mu_curve.py v12-nb-f15-g16 ec:d0be8b9bc6d6:032 1 $O/negctl_nb-f15-g16_s1.json &
$D/envrun.sh python $D/mu_curve.py v12-nb-f15-g12 template 1 $O/tpl_nb-f15-g12_s1.json &
$D/envrun.sh python $D/mu_curve.py v12-nb-f24-g14 lna-a1-inddegen-cascode 1 $O/a1_nb-f24-g14_s1.json &
$D/envrun.sh python $D/mu_curve.py v12-nb-f15-g14 lna-a1-inddegen-cascode 2 $O/a1_nb-f15-g14_s2.json &
$D/envrun.sh python $D/mu_curve.py v12-wb-s11n10-g10-b0530 template 2 $O/tpl_wb-s11n10-g10-b0530_s2.json &
wait
