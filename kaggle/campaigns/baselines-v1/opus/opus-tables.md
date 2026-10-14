### H1 protocol, k <= 4 (pass = valid & feasible at seed 1, rl-v1.2)

| model | group | pass@1 | pass@2 | pass@4 | coverage@4 |
|---|---|---|---|---|---|
| opus | all (58) | 0.3147 | 0.4224 | 0.5172 | 30 |
| opus | T1 (23) | 0.3261 | 0.3696 | 0.4348 | 10 |
| opus | T2 (32) | 0.3359 | 0.5 | 0.625 | 20 |
| opus | T3 (3) | 0.0 | 0.0 | 0.0 | 0 |
| sft-r1 (samples 1-4) | all (58) | 0.3405 | 0.5057 | 0.6897 | 40 |
| sft-r1 (samples 1-4) | T1 (23) | 0.5 | 0.7391 | 0.9565 | 22 |
| sft-r1 (samples 1-4) | T2 (32) | 0.2578 | 0.3854 | 0.5625 | 18 |
| sft-r1 (samples 1-4) | T3 (3) | 0.0 | 0.0 | 0.0 | 0 |

### 2-sample protocol (samples 1-2; feasible at >= 1 of seeds 1-3)

| model | solved | >= 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | validity |
|---|---|---|---|---|---|---|
| opus | 27 | 20 | 7 | 20 | 0 | 1.0 |
| sft-r1 | 37 | 31 | 19 | 16 | 2 | 0.9828 |

Bootstrap pass@1 (opus - sft-r1 samples 1-4): {"n_items": 58, "diff": -0.0259, "ci95": [-0.1466, 0.0948], "p_le0": 0.67, "better": 22, "worse": 25}
Coverage any of 4: {"opus": 30, "sft-r1 (samples 1-4)": 40}
Opus-only tasks: ["t2-nb090-noise-0240", "t2-nb090-noise-0312", "t2-nb090-noise-0323", "t2-nb090-noise-0411", "t2-wb1020-gain-0089", "t2-wb1020-gain-0128", "t2-wb1020-gain-0142", "t2-wb1020-gain-0160", "t2-wb1020-gain-0184"]
sft-r1-only tasks: ["t2-nb090-noise-0047", "t2-nb090-noise-0254", "t2-nb090-noise-0322", "t2-nb090-noise-0351", "t2-nb090-noise-0397", "t2-wb1020-gain-0001", "t2-wb1020-gain-0026", "t2-wb1020-gain-0028", "t2-wb1020-gain-0043", "t2-wb1020-gain-0044", "t2-wb1020-gain-0088", "t2-wb1020-gain-0107", "t2-wb1020-gain-0109", "t2-wb1020-gain-0126", "t2-wb1020-gain-0182", "t2-wb1020-gain-0183", "t2-wb1020-gain-0205", "t2-wb1020-gain-0206", "t2-wb1020-gain-0223"]
Opus validity 232/232; answers equal to a library anchor: 0; distinct (task, topology): 152
Missing rows: {"h1:opus": {}, "h1:sft-r1 (samples 1-4)": {}, "2s:opus": {}, "2s:sft-r1": {}}
