# `lna/playbook/` — playbook v0, the machine-queryable engineering memory

**What this is.** The N4 deliverable of `lna/plans2/15-ENGINEER-PROPOSAL.md` §4.1:
`JOURNEY.md` (39 stages) and `FINDINGS.md` distilled into atomic, evidence-cited,
machine-retrievable rules. `JOURNEY.md` remains the narrative of record and is
human-readable only; this store is what a session or an agent **queries** before
acting. Nothing here supersedes the corpus — every entry cites the stages and
sections it came from, and a rule with no citation is not admitted.

**Why these schemas.** They were found in the wild, not invented (§2 of the
proposal): the entry format is arXiv:2603.23910's Self-Evolving Memory
(`Trigger → Evidence → Rule → Applicability`, atomic, admission-controlled,
failure-first, verbatim evidence preserved); the typed edges and the
confidence-escalation protocol are `github.com/Arcadia-1/analog-agents`'s wiki.
Retrieval is keyed by **failure signature** per §5.4, so "different circuit, same
disease" collapses into one lesson.

Driver: `lna/playbook.py` (stdlib only — `json`/`os`/`re`/`argparse`; entries are
JSON, not YAML).

```
lna/playbook/
  entries/<id>.json   one atomic entry per file
  edges.jsonl         one typed edge per line
  index.json          REBUILT by the module; never hand-edited
  seed-v0.json        the distillation input that produced this store
  README.md           this file
```

---

## Entry schema

| field | type | meaning |
|---|---|---|
| `id` | kebab slug | unique; must equal the filename stem |
| `type` | enum | `anti-pattern` \| `strategy` \| `corner-lesson` \| `harness-rule` \| `diagnosis` |
| `trigger.family` | list | circuit families this fires on (`any` is a wildcard) |
| `trigger.analysis` | list | analysis kinds (`sp`, `noise`, `op`, `two-tone`, `harmonic-balance`, `sensitivity`, `generation`, `critic`, `sizing`, … ; `any` is a wildcard) |
| `trigger.failure_signature` | list | the **named wall** — controlled vocabulary, see below |
| `trigger.keywords` | list | free retrieval terms |
| `evidence` | list of `{quote, source}` | **VERBATIM** corpus text. A number, a table row, or an exact simulator message — never a paraphrase where one exists |
| `rule` | string | one imperative action |
| `applicability.applies` | string | when it fires |
| `applicability.not` | string | when it does **not** — including the honest limits of the measurement |
| `confidence` | enum | `unverified` \| `verified` |
| `sources` | list | JOURNEY stages, FINDINGS §§, file paths. Non-empty, always |
| `created` | `YYYY-MM-DD` | |
| `escalations` | list, optional | written by `--escalate`; records date, second source, and why it is independent |

**Why `evidence` is verbatim.** arXiv:2603.23910 App. E measured *context
attrition*: iterative LLM refinement decays concrete diagnosis into abstract rule
— `"singular matrix: check nodes vin and vin"` becomes `"sim failed"`. This store
therefore keeps the raw text. Several entries carry ngspice/VACASK output and
FINDINGS table rows exactly as they appear, markdown emphasis included.

---

## Admission control (enforced while distilling; enforce it again before adding)

A rule is admitted **only if** it satisfies at least one of:

1. it **resolves a repeated failure pattern** (the same disease seen more than once);
2. it **enforces a checker/simulator constraint** that has been violated more than once;
3. it is a **stable practice independent of specific parameter values**.

Plus two standing filters:

- **Failure-first.** Store corrective lessons and walls, not successful designs.
  A design that worked belongs in `JOURNEY.md` and the label store; only the
  lesson its failure taught belongs here. This is why there is no entry saying
  "`ace8383c` is good."
- **No trivia.** Every entry must be **design physics**, **harness correctness**,
  or **process discipline**. Syntax notes, API idioms and one-off command
  invocations are excluded by construction — arXiv:2603.23910's own ablation
  showed its memory largely learned PySpice API trivia rather than analog design,
  and that is the failure mode this filter exists to prevent.

---

## Confidence protocol

- `unverified` — one observation, however carefully fenced.
- `verified` — the **same lesson re-observed independently**: two stages, two
  harnesses, two circuits, or two provenance classes. `--check` additionally
  requires ≥ 2 distinct `sources` on a verified entry.

Escalation is **one-way and one-time**, and is the store's *only* sanctioned
mutation:

```bash
python lna/playbook.py --escalate ID --source "FINDINGS §NN" \
    --evidence "<verbatim quote from that source>" --why "why it is independent"
```

It refuses an already-verified entry, refuses a `--source` already cited by the
entry, and refuses a missing `--evidence`.

Current split: **29 verified / 11 unverified**. Some genuinely single-observation
lessons stay `unverified` even where they are obviously true (the node-name-drift
harness rule, the Q-sweep corner lesson) — the protocol counts observations, not
plausibility.

---

## Typed edges (`edges.jsonl`)

| type | meaning |
|---|---|
| `prevents` | following A's rule avoids the failure B describes |
| `contradicts` | A and B are in genuine tension; both are on file and the tension is the finding |
| `derived_from` | A was derived from B (usually a general rule from a specific measurement) |
| `validated` | A is an independent instance that validated B |

The `contradicts` edges are the most load-bearing ones in v0 and are deliberately
not smoothed over:

- `ndl-is-blind-to-function` **contradicts** `adopt-only-if-better` — every
  adoption decision in this program's history was gated on NDL@256, and a
  generator with no learning in it wins that comparison outright (168 vs 63)
  while returning zero near-feasible designs. Resolving it is a frozen-protocol
  change and therefore the user's call.
- `replay-fence-is-not-correctness` **contradicts** `replay-fence-before-any-reuse`
  — the fence is necessary and not sufficient; three reproducible *wrong* balun
  answers and a whole four-band IIP3 run on the wrong decks were all fenced clean.

---

## Retrieval — `--consult`

Deterministic integer scoring, no embeddings, no substring-over-prose search, so
a query is reproducible under the same frozen-protocol culture as every other
number in this repo. Ties break on `id`, giving a total order.

| match | points |
|---|---|
| `failure_signature` exact | 10 |
| `failure_signature` substring either way | 5 |
| `family` exact / `family: any` | 4 / 1 |
| `analysis` exact / `analysis: any` | 3 / 1 |
| keyword exact / keyword substring / anywhere in rule+trigger text | 2 / 1 / 1 |
| entry is `verified` | +1 (tiebreak only) |

```bash
python lna/playbook.py --consult --failure-signature iip3-wall
python lna/playbook.py --consult --family dhruva --analysis sensitivity --keywords s11,margin
python lna/playbook.py --consult --failure-signature band-match-wall --type diagnosis --json
```

Controlled failure-signature vocabulary (extend it in `playbook.FAILURE_SIGNATURES`;
`--check` reports an unknown signature as a NOTE, not an error, because the
program keeps discovering new named walls):

```
attribution-error   band-match-wall     bias-regulation      copy-migration
coverage-collapse   device-budget       era-mismatch         harness-artefact
iip3-wall           imbalance           instrument-perturbation
label-domain-mismatch   metric-blind-spot   model-port-mismatch
move-repertoire     nf-wall             node-name-drift      novelty-collapse
numerical-artefact  objective-omission  output-swing-wall
replay-false-confidence  s11-knife-edge  selector-artefact   spec-governance
surrogate-era       topology-exhaustion weak-inversion-blindness
```

---

## Append-only

A correction is a **new entry plus an edge** (`contradicts` / `derived_from`),
never a silent edit — the same discipline `JOURNEY.md`'s maintenance contract and
the append-only label store already follow. `--add` refuses to overwrite an
existing id with different content (and silently skips a byte-identical one, so
re-seeding is idempotent).

## Operations

```bash
python lna/playbook.py --check                     # schema, edges, index, retrieval self-test
python lna/playbook.py --list [--type T] [--confidence C]
python lna/playbook.py --consult ...               # see above
python lna/playbook.py --add FILE.json             # entry | [entries] | {entries, edges}
python lna/playbook.py --link SRC TYPE DST [--note "..."]
python lna/playbook.py --escalate ID --source ... --evidence ... [--why ...]
python lna/playbook.py --reindex                   # index.json is a pure function of entries+edges
```

`--check` is the store's golden and belongs in the regression set. It validates
every entry against the schema, requires unique ids matching their filenames,
requires every edge endpoint to exist, requires non-empty `sources`, requires
`index.json` to be exactly what `--reindex` would write, and runs a retrieval
self-test (`failure_signature=iip3-wall` must rank `iip3-output-swing-wall`
first). Exit code 0 = GREEN.

---

## Reproducing this store

```bash
rm -rf lna/playbook/entries lna/playbook/edges.jsonl lna/playbook/index.json
python lna/playbook.py --add lna/playbook/seed-v0.json
python lna/playbook.py --check
```

`seed-v0.json` is kept as the distillation record: it is the exact input the v0
store was built from, and it makes the 40 entries + 26 edges reviewable as one
diff instead of 40.

## What v0 does NOT do

1. **No cold-start control has been run.** Per §2.2 item 4 of the proposal, when
   this memory's value is *claimed* — "the playbook made the loop better" — the
   claim needs an explicit warm-vs-cold comparison. None exists yet; v0 is a
   store, not a measured improvement.
2. **No automatic ingestion.** New entries are distilled by hand from the corpus.
   Wiring `--add` into a work-package wrap-up (alongside the `JOURNEY.md` stage
   append) is the obvious next step and was not taken.
3. **Retrieval is not indexed by the label store.** §5.4's `diagnosis` field on
   L2/campaign rows does not exist yet, so a design row cannot yet be joined to
   the lesson that explains it. When it lands, its controlled vocabulary should
   be the `FAILURE_SIGNATURES` list above.
4. **Coverage is stages 1–39 only**, and it is deliberately thin on Phase-1
   pipeline mechanics — those are settled practice, not corrective lessons.
