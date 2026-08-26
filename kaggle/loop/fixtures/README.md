# Dry-run fixtures

Canned LLM responses so `driver.py --dry-run` exercises the *entire* loop path on
a box with no GPU and no llama-server. `DryRunClient` (in `driver.py`) returns
these in place of a live `/v1/chat/completions` call, keyed by loop phase:

| file           | phase(s) served | what it contains |
|----------------|-----------------|------------------|
| `propose.json` | `propose`       | a list of K candidate completions, each an OpenAI `chat.completions` response whose message content is a fenced netlist + rationale + `predicted_deltas` JSON, in the output contract the propose prompt asks for. |
| `edit.json`    | `edit`          | one completion: a revised netlist responding to a margin table. |

Each file is a JSON object:

```json
{ "responses": [ <chat.completions response>, ... ] }
```

The driver pops responses in order per phase (cycling if it runs past the list).
The netlists here are lifted verbatim from `lna/templates.py` archetypes via
`proposal.rows_to_text`, so they round-trip WL-hash-exact (see `test_proposal.py`)
and are guaranteed sizable -- the dry-run loop therefore reaches every phase
(`consult -> propose -> roundtrip -> screen -> bias -> size -> diagnose -> edit`)
with real deterministic outcomes, only the *LLM text* being canned.

The message `content` follows the propose output contract exactly: a one-paragraph
rationale, then a fenced ```netlist block, then a fenced ```json block holding
`{"predicted_deltas": {...}}`. `driver.py`'s `parse_completion()` is the single
reader of this shape and is used for both live and dry-run responses, so the
fixtures exercise the real parser.
