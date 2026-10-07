| model | train ex. | solved | >= 2/3 seeds | T1 /23 | T2 /32 | T3 /3 | T1/T2/T3 >= 2/3 | validity | copy rate: own training targets | copy: any pilot-v0 training target | distinct WLs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sft300 | 298 | 28 | 24 | 10 | 18 | 0 | 9/15/0 | 0.991 | 0/115 = 0.0 | 3/115 | 113 |
| sft1000 | 994 | 28 | 24 | 19 | 8 | 1 | 16/7/1 | 0.991 | 46/115 = 0.4 | 46/115 | 67 |
| mix1000 | 458 | 26 | 18 | 5 | 20 | 1 | 5/13/0 | 1.0 | 5/116 = 0.0431 | 5/116 | 115 |

Decision: {"t2_gain_vs_sft1000": 12, "t1_loss_vs_sft1000": 14, "copy_rate_mix": 0.0431, "copy_rate_sft1000": 0.4, "cond_t2": true, "cond_t1": false, "cond_copy": true, "t2_gain_vs_sft300": 2, "t1_loss_vs_sft300": 5, "works": false}
Solved overlap: {"sft300": {"both": 16, "union": 38, "only_mix": 10, "only_other": 12}, "sft1000": {"both": 10, "union": 44, "only_mix": 16, "only_other": 18}}
