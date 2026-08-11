"""WP-OUTCOME -- the outcome-token vocabulary and the label-domain policy.

Decision-transformer-style conditioning for the P5 generator: every training row
derived from a topology the pipeline has actually *measured* is prefixed with
four tokens saying what that topology achieved, so the model can be asked at
sampling time for an outcome rather than only for a class.

    <LNA_NB> <S11_MET> <S21_MET> <IDD_MET> <NF_MET> VSS ...

Sixteen new ids (4 gated metrics x 4 bins) are appended AFTER the 1005 upstream
ids and the three P5 class tokens, exactly the way `<LNA_NB>` was, so the vocab
guard (`test_vocab_matches_upstream.py`) still sees an untouched base vocabulary.

This module is deliberately dependency-free (stdlib only): it is imported both by
`finetune.py` under the WSL GPU python and by `_out_emit.py` under the torch-free
Windows analysis python.

The policy decisions this file owns are pre-registered in
`lna/plans2/11-WP-OUTCOME.md` (bin thresholds, label domain, tie-break); the
docstrings below restate them so code and registration cannot drift.
"""

# ------------------------------------------------------------------ vocabulary
METRICS = ("S11", "S21", "IDD", "NF")
BINS = ("VIOL", "MARG", "MET", "UNK")

#: appended after DEVICES + CLASS_TOKENS["p5"], in exactly this order
OUTCOME_TOKENS = ["<%s_%s>" % (m, b) for m in METRICS for b in BINS]

#: the store metric name(s) each conditioning slot reads, in slot order. A spec
#: gates either `s11_db` (narrowband, S11 at f0) or `s11_max_db` (broadband,
#: worst-case over the band); whichever the spec declares is the S11 slot.
SLOT_METRICS = (("s11_db", "s11_max_db"), ("s21_db",), ("idd_ma",), ("nf_db",))

#: MARGINAL/MET boundary on the stored per-spec normalized margin.
#: 0.05 is one label-noise unit: FINDINGS 14.1 measured sigma(S21) = 0.726 dB
#: under best-of-3 labeling, which on a 15 dB gain floor (scale 15) is 0.048 in
#: normalized units. A row inside one sigma of its constraint is not reliably
#: distinguishable from a violating one, so MARGINAL means exactly "meets it by
#: less than the label noise".
TAU = 0.05


def bin_of(margin):
    """Signed normalized margin -> bin name. None (missing / unsupported /
    era-invalid) -> UNK. This is the whole binning rule."""
    if margin is None:
        return "UNK"
    if margin < 0.0:
        return "VIOL"
    if margin < TAU:
        return "MARG"
    return "MET"


def token(slot, b):
    return "<%s_%s>" % (METRICS[slot], b)


def tokens_for(bins):
    """['VIOL','MET',...] (4 bin names, slot order) -> the 4 token names."""
    return [token(i, b) for i, b in enumerate(bins)]


# --------------------------------------------------------------- label domain
#: The current measurement era, as stamped on every row (Block 6 is law).
#: `w_finger` set means the multi-finger MOS emission (FINDINGS 27: the cutover
#: moved NF a median of -2.08 dB store-wide, so a pre-cutover NF number is a
#: different measurement, not a noisier one); `nf_method == "series_rs"` is the
#: golden-validated NF harness (FINDINGS 13; the port-referred method is retired).
#: The same geometry change also moves the input match, so the registered policy
#: is the safe one: S11/S21/Idd bins come from current-era rows too, and a
#: pre-cutover row contributes no bin at all rather than three.
CURRENT_W_FINGER = 2e-06
CURRENT_NF_METHOD = "series_rs"


def in_domain(row):
    """Is this L2 row inside the single label domain bins may be drawn from?"""
    z = row.get("zoaf_cfg") or {}
    m = row.get("metrics") or {}
    return (z.get("w_finger") == CURRENT_W_FINGER
            and m.get("nf_method") == CURRENT_NF_METHOD)


def margins_of(row):
    """-> [s11, s21, idd, nf] signed normalized margins, None where the row's own
    spec does not support / did not measure that metric.

    Read straight out of the stored `margins` block -- `datastore.margins_for`
    already normalized it per spec, and that normalization is what makes a bin
    spec-agnostic."""
    mar = row.get("margins") or {}
    out = []
    for names in SLOT_METRICS:
        v = None
        for n in names:
            e = mar.get(n)
            if e and e.get("supported") and e.get("margin") is not None:
                v = e["margin"]
                break
        out.append(v)
    return out


def bins_of(row):
    return [bin_of(v) for v in margins_of(row)]


def _rank(row):
    """Tie-break key for "the best row of a (wl_hash, spec) key". Feasibility
    first, and every term is read from the row's own stored margins so no spec
    has to be re-derived (a spec's gating can change between the label and today;
    the row cannot):

      1. more labeled slots wins   -- a 4-bin row carries strictly more label
                                      than a 3-bin one
      2. least total violation     -- sum of min(margin, 0), i.e. -1 x the
                                      infeasible branch of `spec.objective`
      3. best worst-case margin    -- min(margin)
      4. latest timestamp          -- deterministic, and prefers the most
                                      recently re-derived measurement
    """
    mm = [v for v in margins_of(row) if v is not None]
    return (len(mm),
            sum(min(v, 0.0) for v in mm),
            min(mm) if mm else -9e99,
            row.get("ts") or "")


def best_per_key(rows):
    """L2 rows -> {(wl_hash, spec): best row}, restricted to the current label
    domain. Rows without a wl_hash or without stored tokens are dropped (they are
    reference decks, not topologies that can be augmented)."""
    keys = {}
    for r in rows:
        if not in_domain(r):
            continue
        if not r.get("wl_hash") or not ((r.get("graph") or {}).get("tokens")):
            continue
        keys.setdefault((r["wl_hash"], r["spec"]), []).append(r)
    return dict((k, max(v, key=_rank)) for k, v in keys.items())
