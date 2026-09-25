# Qwen-32B baseline on the clean 45nm benchmark (PARTIAL)
Kernel devavratpatni/circuit-repro-editcap-v11-45nm ERRORED on the Kaggle
runtime limit (31 cells x 2 arms x ~8192-token completions @ ~10 tok/s > 12h).
Got 26/31 arm-B cells before dying; arm C not reached.
RESULT (arm B, 26/31): 0 FEASIBLE. 78 proposed / 72 valid / 62 smoke_pass,
0 empty (8192-token fix worked). Effectively ~0/31.
Pairs with Claude ceiling 3/31 on the same benchmark.
TO COMPLETE: re-submit in 2 batches (~16 cells each, B+C) to fit the time limit.
