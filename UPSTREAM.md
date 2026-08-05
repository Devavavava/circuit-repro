# Upstream repositories — pinned commits

Every checkout under `*/repo/`, `extensions/`, and `misc/` is an unmodified clone of a
public repository. None of them are vendored into this repo. This file pins the exact
commit each result in [STATUS.md](STATUS.md) was produced against.

Re-create all of them with:

```bash
bash scripts/fetch_upstream.sh
```

| Local path | Upstream | Pinned commit | Branch | Committed | Patch |
|---|---|---|---|---|---|
| `AnalogGenie/repo` | [xz-group/AnalogGenie](https://github.com/xz-group/AnalogGenie) | `efc25358939c6bedd247f28d3df61066964f3a90` | main | 2025-04-26 | — |
| `AutoCkt/repo` | [ksettaluri6/AutoCkt](https://github.com/ksettaluri6/AutoCkt) | `a6c8a61d3dffb8b433f19251e135994a5b0f6ee4` | master | 2022-03-17 | `patches/autockt.patch` |
| `CktGNN/repo` | [zehao-dong/CktGNN](https://github.com/zehao-dong/CktGNN) | `416cd035f79dd8cfcb60ac0a4792b43255adf0b7` | main | 2023-09-11 | `patches/cktgnn.patch` |
| `Krylov-ICML2023/repo` | [indylab/Circuit-Synthesis](https://github.com/indylab/Circuit-Synthesis) | `98a520ed7e595a72f7e34982134be727ee4dfa40` | main | 2023-05-27 | — |
| `LaMAGIC2/repo` | [turtleben/LaMAGIC](https://github.com/turtleben/LaMAGIC) | `0cde737684571b58a549f093a3ea3f9a55911433` | main | 2025-08-16 | — |
| `extensions/AnalogSAGE` | [xz-group/AnalogSAGE](https://github.com/xz-group/AnalogSAGE) | `2c272f1d730e24759e005081336451abcb167f4f` | main | 2025-11-21 | — |
| `extensions/CircuitSense` | [xz-group/CircuitSense](https://github.com/xz-group/CircuitSense) | `c125509f2a1876536893a349d29e4fca6cc4fca8` | main | 2026-01-27 | — |
| `extensions/RoSE` | [xz-group/RoSE](https://github.com/xz-group/RoSE) | `50776688f9f0fd27f27fb8c7865c901c83e02bb4` | main | 2024-12-09 | — |
| `extensions/ZeroSim` | [xz-group/ZeroSim](https://github.com/xz-group/ZeroSim) | `9af8a6976cf1aae9788eedcd882b7cc201ee95ef` | main | 2026-04-24 | — |
| `misc/AnalogGenie-Lite` | [xz-group/AnalogGenie-Lite](https://github.com/xz-group/AnalogGenie-Lite) | `7ecd75d76549849738a1d0d6128a9f7a3b463b5d` | main | 2026-03-23 | — |
| `misc/AnalogToBi` | [Seungmin0825/AnalogToBi](https://github.com/Seungmin0825/AnalogToBi) | `e2033e9e5347dd0b702d24a8809de0c0f5470f87` | main | 2026-05-07 | — |
| `misc/ZOAF` | [LiyanTan111/ZOAF](https://github.com/LiyanTan111/ZOAF) | `62615e91348691a225fd005bbf51ffd97d6e45f1` | main | 2026-05-12 | — |

`GCN-RL/` is an empty placeholder — the DAC'20 work has no public code, as do L2DC and
DNN-Opt. See the summary table in STATUS.md.

## Patches

Only two upstream files needed real source changes. Both are applied by the fetch script.

**`patches/cktgnn.patch`** — `layers/constants.py` builds a path by slicing on a
hard-coded `"/"`, which yields a garbage path on Windows. Replaced with
`os.path.dirname` / `os.pardir`.

**`patches/autockt.patch`** — `two_stage_opamp.cir` hard-codes the original author's
home directory in its `.include` line. The patch substitutes the token
`@@AUTOCKT_ROOT@@`, which `scripts/fetch_upstream.sh` rewrites to your local
`AutoCkt/repo` path. If you apply the patch by hand, replace that token yourself.

### Changes deliberately not captured

* **LaMAGIC2/repo, extensions/ZeroSim** — reported as dirty by git, but the only
  differences are recompiled `__pycache__/*.pyc` bytecode. No source change.
* **AutoCkt/repo `bsim4v5.out`** — a file ngspice overwrites on every run, not an edit.
* **AnalogGenie/repo** — the `torch.load` / `map_location` bug noted in STATUS.md was
  worked around inside `Inference_smoke.py` (tracked here) rather than by editing the
  upstream source, so there is no patch for it.
