# goldens-parity evidence (label-domain rule)

RULING STATUS: **not ruled — pooling stays BLOCKED.** Every Kaggle-produced
measurement row keeps its Kaggle-domain tag and stays out of the box stores
until the user rules on the evidence here (rule text: `kaggle/PLAYBOOK.md`
§label-domain, `kaggle/schemas/README.md`).

The question: is a number measured on Kaggle the SAME number the box would
have measured — digit for digit — so that rows from both machines may ever be
pooled into one training/label store?

The instrument: `lna/ref/parity_dump.py` (read-only). It measures, at full
float precision, with 3 repeats each (replay-fence: in-host spread must be
exactly 0.0):

1. the two `check_ref` reference decks (every extracted field, no rounding,
   no tolerances — raw values);
2. one fixed-parameter evaluation through the actual campaign measurement path
   (bias-inserted corpus topology `d6c0e6fc...`, spec cap-e01-wifi, bptm45,
   all sizable params at the exact decode midpoint) — deterministic, unlike a
   CMA trajectory, so it can be compared across hosts.

Layout:

    box/     parity-box-<commit>-<date>.json     (this box)
    kaggle/  parity-kaggle-<commit>-<date>.json  (pulled from the
             circuit-repro-parity-cpu kernel; the kernel embeds a
             byte-identical copy of parity_dump.py)
    REPORT.md  field-by-field comparison + verdict draft for the ruling

Compare any two dumps:

    python lna/ref/parity_dump.py --diff box/<a>.json kaggle/<b>.json

Notes: the Kaggle run's clone is origin/main; the cross-PDK sizing fix
(c8114a59) is bptm45-neutral (byte-identical golden), so bptm45-only parity
numbers are comparable across that code delta. The fingerprint block in each
dump records host, ngspice build, python/numpy, and git commit.
