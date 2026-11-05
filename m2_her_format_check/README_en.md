# M2-Her Format Check — Standalone Test Package

[中文](README.md)

A standalone `pytest` suite that validates the format of the M2-Her native `/v1/text/chatcompletion_v2` API: text, system persona, the seven roles (system / user_system / group / sample_message_user / sample_message_ai / user / assistant), sample dialogues, named history, sampling and output-budget parameters, error handling, usage, the SSE streaming protocol, `n` candidates, extra request fields, and reply-language consistency.
It follows the M3 suite's module numbering, function naming and one-to-one py/md mapping. **After collection there are 112 case functions and 509 items** (text 449 / stream 11 / compat 49).

## Expected values follow the live API

M2-Her is an older model and its public docs diverge from the actual API in many places. **Every assertion in this suite is set from what the official channel (MiniMax native `/v1/text/chatcompletion_v2`, model `M2-her`) actually returned on 2026-11-05.** Where the docs or common assumptions disagree, the live API wins. Once a third-party provider serves M2-Her, this suite can be run against it directly to check that its format matches the official one.

- Expected values live in [`observed.py`](observed.py) (error envelopes, `n` limit, language behavior) and [`acceptance_baseline.json`](acceptance_baseline.json) (compatibility cases). The per-case expectations are listed in the case docs under `docs/`.
- **Engineering assertions are exact**: HTTP status, business code `base_resp.status_code`, the literal `status_msg`, the error framing (plain JSON / two JSON documents in one body / a single SSE event), whether a parameter is accepted, candidate count, usage structure, and packet shape. For example, omitting the name of an advanced role yields HTTP 200 + `2013 "invalid params, 400"` non-streaming and a single SSE event `1000 "unknown error, 999"` streaming; both are asserted verbatim.
- **Model-behavior and language assertions describe the usual behavior** (`--run-behavior`) and are not loosened to reach 100%. The following occasional outcomes have been observed and can fail a single run; this randomness is expected:
  - 16_02 sometimes fills the budget with repeated text after the marker;
  - 19_02 pairs that usually keep the persona language occasionally switch to the user's language; 19_03 / 19_01 occasionally slip in a sentence in another language; 19_05 ko→en still answers in Korean about 3 times in 10;
  - 19_06 default sampling occasionally drifts to a third language;
  - 15_08 is occasionally SKIPPED (not validated) when replies are too short to reach 1000 characters within 20 requests.
- If a behavior case keeps failing across runs, the live behavior has changed: re-observe and update `observed.py` and the case docs.

## Directory layout

```
m2_her_format_check/
├── conftest.py                 # pytest options / fixtures / log path (xdist-aware)
├── helpers.py                  # HTTP + SSE transport, request logging and all assertion helpers
├── exercises.py                # multi-request flows: budget ladders, context calibration, packet sampling
├── scenarios.py                # deterministic message builders (seven roles, samples, long text)
├── language.py                 # deterministic reply-language rules (no model involved)
├── observed.py                 # expected values observed on the official channel
├── acceptance_baseline.json    # built-in baseline for compatibility cases (15_* / 10_07 / 12_04)
├── m2_her_text_tests.py        # text and roles, 449 items (modules 01–13, 16–19)
├── m2_her_stream_tests.py      # SSE streaming protocol, 11 items (module 14)
├── m2_her_compat_tests.py      # endpoint compatibility, legacy fields, extensions, packets, 49 items (module 15)
├── pytest.ini                  # python_files=m2_her_*_tests.py
├── requirements.txt            # httpx + pytest + pytest-xdist + openai
├── logs/                       # per-run jsonl logs (created at runtime, git-ignored)
└── docs/                       # case explanations (Chinese/English, one-to-one with m2_her_*_tests.py)
    ├── m2_her_text_cases.md   / m2_her_text_cases_en.md
    ├── m2_her_stream_cases.md / m2_her_stream_cases_en.md
    └── m2_her_compat_cases.md / m2_her_compat_cases_en.md
```

## Required environment variables

```bash
export M2_HER_BASE_URL="https://your-endpoint.example.com"   # server root or an SDK base ending in /v1, without the completion path
export M2_HER_API_KEY="sk-xxx"
```

## Optional environment variables

| Variable | Default | Description |
|------|------|------|
| `M2_HER_MODEL` | `M2-her` | Model ID sent in requests; may be a provider alias |
| `M2_HER_RESPONSE_MODEL` | same as `M2_HER_MODEL` | Expected `model` in responses; set it when the API returns a canonical name |
| `M2_HER_API_STYLE` | `native` | `native` → `/v1/text/chatcompletion_v2`; `openai` → `/v1/chat/completions` (only the 15_* compatibility cases run) |
| `M2_HER_TIMEOUT` | `120` | Per-request timeout in seconds |
| `M2_HER_EXTRA_HEADERS` | (empty) | JSON string of extra request headers, e.g. `'{"X-Custom-Header": "value"}'` |
| `M2_HER_QUERY_PARAMS` | (empty) | JSON string of query parameters appended to the URL, e.g. `'{"GroupId": "your-group-id"}'` |
| `M2_HER_RUN_LOG` | `logs/run_<UTC-ts>.jsonl` | Custom jsonl path; worker and process IDs are appended to the file name |

## pytest options

| Option | Effect |
|------|------|
| `--run-behavior` | Run model-behavior and language cases (197 items, validation_tier=behavior) |
| `--run-compat` | Run the 15_* compatibility cases and 10_07 |
| `--run-slow` | Run long-input and repeated-sampling cases (12_*, 14_11, 15_08, 16_04, 19_06) |
| `--contract FILE` | Override `acceptance_baseline.json` key by key from a JSON file |
| `--context-fixture FILE` | Use measured within/over-window samples instead of auto-calibration for 12_03/12_04 |
| `--context-window` | Context-window baseline, `64000` (default) or `65536` |
| `--n-limit N` | Replace the `n` limit used by 17_08 (default: the observed value 4) |

Without options, the documented_api and implementation_api tiers run (251 items); everything not selected is SKIPPED with an explicit reason.

## Running

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables (see above)
export M2_HER_BASE_URL=...
export M2_HER_API_KEY=...

# 3a. Default format cases (no behavior / compat / long input)
pytest

# 3b. All 509 items with 5 workers
pytest -n 5 --run-behavior --run-compat --run-slow

# 3c. Per file
pytest m2_her_text_tests.py
pytest m2_her_stream_tests.py
pytest m2_her_compat_tests.py --run-compat --run-slow

# 3d. Behavior / language only
pytest --run-behavior -m behavior
pytest m2_her_text_tests.py -k '19_' --run-behavior --run-slow

# 3e. Reproduce a single case (quote node ids containing brackets in zsh)
pytest -v 'm2_her_text_tests.py::TestCombinations::test_13_01_all_seven_roles[non_stream-all_named]'
```

When checking a new endpoint for the first time, run the default cases serially first so that authentication or rate-limit problems are not amplified by concurrency.

## How results are judged

- **Validation tiers**: each item carries a `validation_tier` junit property: `documented_api` (public API format, 202 items), `implementation_api` (server-side extra fields such as `n` and `metadata`, 59 items), `behavior` (model behavior and language, 197 items) and `endpoint_contract` (compatibility, 51 items). Behavior items are not part of the format pass rate.
- **Negative cases run a healthy control first**: if a normal request with the same endpoint, model, auth and stream mode fails, the negative case is SKIPPED as not validated instead of counting an environment problem as a correct rejection. Missing-field, malformed-JSON and no-auth cases go through the raw request path; the test code never fills in parameters. There are no automatic retries.
- **Output budget**: truncation and natural stops use a bounded budget ladder. With `finish_reason=length`, `completion_tokens` must equal the budget exactly; a missing real count is reported as a failed measurement precondition.
- **Context**: 12_03/12_04 use up to 8 one-token probes per mode to calibrate an input close to 64K from real `prompt_tokens`, then raise the output budget to exceed the window. `1039` is a TPM rate limit, not a context rejection.
- **Streaming**: native streams are not required to send `[DONE]`; the final full-message summary packet and the delta text are checked separately and never concatenated twice; usage on intermediate packets may be 0.
- **Packet quality (15_08)**: accepted by the observed packet shape — first packet ≤6 characters, middle packets ≥5 characters, any packet ≤512 characters per response. The five M3 bucket ratios are recorded only.
- **Language consistency (19_*)**: [`language.py`](language.py) decides the dominant language from Unicode script runs, Simplified/Traditional and Chinese/Japanese character sets, and function words for Latin-script languages; no model or third-party detector is used. Strict cases require the reply to use only the target language (Latin-script loanwords excepted); pairs observed to keep the persona language assert the dominant language.

## Overriding the built-in baseline

When another endpoint legitimately differs from the official behavior and the difference is documented, use `--contract` to override `acceptance_baseline.json` key by key with complete rules; keys that are not overridden keep their built-in values:

```json
{
  "15_03/2049": {
    "source": "reference to the provider's API docs or a recorded decision",
    "outcome": "success",
    "completion_limit": 2048
  }
}
```

Every rule needs a non-empty `source` and an `outcome` (`success` / `reject` / `error`). `reject` requires `error_kind` (`parameter` / `model` / `auth` / `context`); `error` requires `status_code`, `status_msg` and `framing`. See the [compatibility case list](docs/m2_her_compat_cases_en.md) and the built-in file for available keys. Do not generate passing rules automatically from a single run.

## Output

- **stdout**: standard pytest output; `--junitxml` keeps each item's `validation_tier`.
- **jsonl logs**: written to `logs/run_<UTC-ts>_<worker>_<pid>.jsonl` by default. Each request keeps the full payload, the actual request headers, HTTP status and business response, raw response bytes (Base64), raw SSE events, parsed result, trace_id, latency and exceptions. **Nothing is redacted; do not commit logs.** Measurement records (packets, calibration, counts) are tagged by `kind`; count requests only from records that have `request_number`.
