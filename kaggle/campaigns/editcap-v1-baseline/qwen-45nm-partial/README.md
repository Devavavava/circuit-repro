# Qwen-32B baseline on the clean 45nm benchmark (PARTIAL)
Kernel devavratpatni/circuit-repro-editcap-v11-45nm ERRORED on the Kaggle
runtime limit (31 cells x 2 arms x ~8192-token completions @ ~10 tok/s > 12h).
Got 26/31 arm-B cells before dying; arm C not reached.
RESULT (arm B, 26/31): 0 FEASIBLE. 78 proposed / 72 valid / 62 smoke_pass,
0 empty (8192-token fix worked). Effectively ~0/31.
Pairs with Claude ceiling 3/31 on the same benchmark.
TO COMPLETE: re-submit in 2 batches (~16 cells each, B+C) to fit the time limit.

## AUDIT NOTE (2026-09-26) — unresolved discrepancy
This README says the kernel errored on the 12 h runtime limit, but
`llama-server.log` timestamps put total server uptime for the 26 completions at
~2.6 h (mean ~5.4 min/completion incl. SPICE gaps; ~11 tok/s; mean 3.4k tok).
Either the kernel died for another reason or the 12 h figure refers to something
else. Not resolved; do not use "12 h" as a throughput planning number.
