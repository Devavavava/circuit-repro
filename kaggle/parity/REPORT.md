# goldens-parity comparison — box vs Kaggle, 2026-08-28

RULING STATUS: **RULED — ADOPTED (user, 2026-08-29)** under the verdict-draft
terms below. The binding statement lives in README.md.

## Runs compared

| side | dump | host | ngspice | code |
|---|---|---|---|---|
| box | `box/parity-box-0b4b497e-2026-08-28.json` | RHEL8 (glibc 2.28), source-built `.env/ngspice-47` | ngspice-47 | 0b4b497e |
| Kaggle | `kaggle/parity-kaggle-originmain-2026-08-28.json` | Kaggle CPU image (glibc 2.35), cached kernel-built ngspice-47 | ngspice-47 | aa8923be (origin/main; the sizing fix is bptm45-neutral, golden-proven) |

Kernel: `circuit-repro-parity-cpu` v1 (full bootstrap + acceptance gate GREEN
first, then the dump; `parity_dump.py` embedded byte-identical).

## Result

**34 / 34 compared fields EXACT — bit-identical floats.** Zero fields within
tolerance-but-not-exact, zero fields differing. In-host replay fence clean on
BOTH sides: 3 repeats, max spread exactly 0.0 on every field.

Coverage: both `check_ref` reference decks (9 + 7 fields: S11/S21/NF/Idd/Zin/
gm/gmb) and the fixed-parameter funnel evaluation through the real campaign
measurement path (18 fields: band S-params, NF, Idd, K/mu/delta stability,
ripple) on the funnel-golden corpus topology.

Reproduce the comparison:

    python lna/ref/parity_dump.py --diff \
        kaggle/parity/box/parity-box-0b4b497e-2026-08-28.json \
        kaggle/parity/kaggle/parity-kaggle-originmain-2026-08-28.json

## Honest scope notes (for the ruling)

1. "Exact" means exact at the precision the harness actually consumes: these
   values are ngspice's printed output parsed by `extract.py`/`check_ref.py` —
   the SAME parsed floats that feed objectives, margins, and any store row.
   ngspice prints ~6 significant digits; deeper binary (rawfile) agreement was
   not compared, and does not need to be: a label row can never contain more
   precision than these fields carry.
2. Coverage is bptm45 only. A foreign-PDK parity section (same instrument,
   `--pdk` threading) is a straightforward extension if Kaggle-side foreign-PDK
   rows ever head for a store.
3. One CMA-ES trajectory was NOT compared: chaotic divergence makes trajectory
   equality the wrong instrument; measured-value parity is the right one.

## Verdict draft (user to rule)

The evidence supports: box + this Kaggle image/ngspice-47 recipe = ONE
measurement domain for bptm45 golden quantities. If ruled, suggested terms:
pooling allowed for rows produced by THIS pinned recipe (cached ngspice47
dataset, this image lineage), Kaggle-origin tag RETAINED on every row for
traceability, parity re-run required whenever the ngspice cache dataset or
image generation changes.
