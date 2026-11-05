# M2-Her Format Check — Standalone Test Package

[中文](README.md)

A standalone `pytest` suite that validates the format of the M2-Her native `/v1/text/chatcompletion_v2` API: text, system persona, the seven roles (system / user_system / group / sample_message_user / sample_message_ai / user / assistant), sample dialogues, multi-speaker conversations with `name`, sampling and output-length parameters, error handling, usage, the SSE streaming protocol, `n` multiple replies, extra request fields, and reply language.
It follows the M3 suite's module numbering, function naming and one-to-one py/md mapping. **After collection there are 103 case functions and 403 items** (text 343 / stream 11 / compat 49).

## Where the expected values come from

M2-Her is an older model and its public docs diverge from the actual API in many places. **The expected values are taken from what the official channel (MiniMax native `/v1/text/chatcompletion_v2`, model `M2-her`) returned on 2026-11-05**, so a third-party M2-Her deployment can be checked against the official format. Every check falls into one of three categories:

| Category | Rule | Examples |
|------|------|------|
| Must succeed | The request succeeds and the reply is well-formed (fields, types, usage, SSE frames are all checked) | All seven roles with `name`; valid temperature / top_p / max_completion_tokens |
| Must fail | **HTTP status is not 200, or HTTP 200 with a non-zero business code (`base_resp.status_code`) or an `error` object**, and no reply text comes back. **Error codes, messages and framing are not compared** | Wrong types, missing fields, bad auth, input over 64K, n=5, advanced roles without `name` |
| Accept or reject | Values the docs rule out but the official API accepts: an acceptance must be a well-formed reply, a rejection must meet "must fail"; **a 5xx always fails** | temperature=0 / 1.01, top_p=0, max_completion_tokens=0 / -1 / null, n=0 / -1 / null, undeclared parameters |

The official API returns HTTP 200 for every error and puts the error in the business code, and some of its codes and messages are not well designed (e.g. `unknown error, 999`). Error cases therefore only require the request to fail; providers are not expected to copy the official error format.

Model-behavior cases (`--run-behavior`) are limited to core capabilities that passed in all 10 full runs against the official API. 19_01 (reply in the user's language) allows up to 3 attempts per language and needs 2 to pass.

Expected values live in [`observed.py`](observed.py) (the `n` limit), [`acceptance_baseline.json`](acceptance_baseline.json) (compatibility cases) and the test functions; the per-case expectations are listed in the case docs under `docs/`.

## Directory layout

```
m2_her_format_check/
├── conftest.py                 # pytest options / fixtures / log path (xdist-aware)
├── helpers.py                  # HTTP + SSE transport, jsonl logging and all assertion helpers
├── exercises.py                # multi-request flows: budget ladders, context calibration, packet sampling
├── scenarios.py                # deterministic message builders (seven roles, samples, long text)
├── language.py                 # deterministic reply-language rules (no model involved)
├── observed.py                 # values observed on the official API (the n limit)
├── acceptance_baseline.json    # built-in expectations for compatibility cases (15_* / 10_07 / 12_04)
├── m2_her_text_tests.py        # text and roles, 343 items (modules 01–13, 16–19)
├── m2_her_stream_tests.py      # SSE streaming protocol, 11 items (module 14)
├── m2_her_compat_tests.py      # call paths, legacy and extra parameters, packets, 49 items (module 15)
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
export M2_HER_BASE_URL="https://your-endpoint.example.com"   # API root (or ending in /v1), without the completion path
export M2_HER_API_KEY="sk-xxx"
```

The request URL, headers and the `model` in the request body all come from environment variables; the cases contain no hard-coded address, key or routing information:

- URL = `M2_HER_BASE_URL` + `/v1/text/chatcompletion_v2` (`/v1/chat/completions` with `M2_HER_API_STYLE=openai`) + `M2_HER_QUERY_PARAMS`
- Headers = `Content-Type` + `M2_HER_EXTRA_HEADERS` + `Authorization: Bearer $M2_HER_API_KEY`
- Body `model` = `M2_HER_MODEL`

## Optional environment variables

| Variable | Default | Description |
|------|------|------|
| `M2_HER_MODEL` | `M2-her` | Model ID sent in requests; may be the provider's model name |
| `M2_HER_RESPONSE_MODEL` | same as `M2_HER_MODEL` | Expected `model` in responses; set it when the API returns a different name |
| `M2_HER_AUTH_TYPE` | `bearer` | `none` sends no `Authorization` (the auth case 11_06 is skipped); for endpoints without auth or with a custom auth header in `M2_HER_EXTRA_HEADERS` |
| `M2_HER_API_STYLE` | `native` | `native` → `/v1/text/chatcompletion_v2`; `openai` → `/v1/chat/completions` (only the 15_* compatibility cases run) |
| `M2_HER_TIMEOUT` | `120` | Per-request timeout in seconds |
| `M2_HER_EXTRA_HEADERS` | (empty) | JSON string of extra request headers, e.g. `'{"X-Custom-Header": "value"}'` |
| `M2_HER_QUERY_PARAMS` | (empty) | JSON string of query parameters appended to the URL, e.g. `'{"GroupId": "your-group-id"}'` |
| `M2_HER_RUN_LOG` | `logs/run_<UTC-ts>.jsonl` | Custom jsonl path; under xdist each worker appends `_gw<N>` |

## pytest options

| Option | Effect |
|------|------|
| `--run-behavior` | Run model-behavior cases (91 items, validation_tier=behavior) |
| `--run-compat` | Run the 15_* compatibility cases and 10_07 |
| `--run-slow` | Run long-input and multi-request cases (12_*, 14_11, 15_08, 16_04) |
| `--contract FILE` | Replace rules in `acceptance_baseline.json` one by one from a JSON file |
| `--context-fixture FILE` | Supply measured within/over-window inputs instead of auto-calibration for 12_03/12_04 |
| `--context-window` | Context window, `64000` (default) or `65536` |
| `--n-limit N` | Change the `n` limit used by 17_08 (default: the official 4) |

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

# 3b. All 403 items with 5 workers
pytest -n 5 --run-behavior --run-compat --run-slow

# 3c. Per file
pytest m2_her_text_tests.py
pytest m2_her_stream_tests.py
pytest m2_her_compat_tests.py --run-compat --run-slow

# 3d. Model-behavior cases only
pytest --run-behavior -m behavior

# 3e. Reproduce a single case (quote node ids containing brackets in zsh)
pytest -v 'm2_her_text_tests.py::TestCombinations::test_13_01_all_seven_roles[non_stream-all_named]'
```

When checking a new endpoint for the first time, run the default cases serially first so that authentication or rate-limit problems are not amplified by concurrency.

## How results are judged

- **Validation tiers**: each item carries a `validation_tier` junit property: `documented_api` (public API format, 202 items), `implementation_api` (server-side extra fields such as `n` and `metadata`, 59 items), `behavior` (model behavior, 91 items) and `endpoint_contract` (compatibility, 51 items).
- **Healthy control first**: "must fail" and "accept or reject" cases first send a normal request with the same endpoint, model, auth and stream mode. If that control fails, the case is SKIPPED as not validated, so an outage is never counted as a correct rejection. Missing-field, malformed-JSON and no-auth cases go through the raw request path; the test code never fills in parameters. There are no automatic retries.
- **Output length**: truncation and natural stops use a bounded retry ladder. With `finish_reason=length`, `completion_tokens` must equal the limit exactly; a missing real count is reported as unverifiable.
- **Context**: 12_03/12_04 use up to 8 one-token probes per mode to build an input close to 64K from real `prompt_tokens`, then raise the output limit to exceed the window.
- **Streaming**: native streams are not required to send `[DONE]`; the final full-message summary packet and the delta text are checked separately; usage on intermediate packets may be 0.
- **Packet size (15_08)**: per response, first packet ≤6 characters, middle packets ≥5 characters, any packet ≤512 characters. The five M3 bucket ratios are recorded only.
- **Reply language (19_*)**: [`language.py`](language.py) decides the language from Unicode script runs, Simplified/Traditional and Chinese/Japanese character sets, and function words for Latin-script languages; no model or third-party detector is used. The reply may only use the target language (Latin-script loanwords excepted).

## Replacing the built-in expectations

When another endpoint legitimately differs from the official behavior and the difference is documented, use `--contract` to replace rules in `acceptance_baseline.json` one by one; rules that are not replaced keep their built-in values:

```json
{
  "15_03/2049": {
    "source": "reference to the provider's API docs or a recorded decision",
    "outcome": "success",
    "completion_limit": 2048
  }
}
```

Every rule needs a non-empty `source` and an `outcome`: `success` (must succeed), `reject` (must fail) or `either` (accept or reject). See the [compatibility case list](docs/m2_her_compat_cases_en.md) and the built-in file for available keys. Do not generate passing rules automatically from a single run.

## Output

- **stdout**: standard pytest output; the jsonl path is printed first, e.g. `[m2_her_api_test] run log → .../logs/run_20261105T120000Z.jsonl`. `--junitxml` keeps each item's `validation_tier`.
- **jsonl logs**: the same mechanism as the M3 suite (`helpers.RUN_LOG_PATH` + `_write_log_line`). Written to `logs/run_<UTC-ts>.jsonl` by default, or `run_<UTC-ts>_gw<N>.jsonl` per xdist worker. One line per request: `ts`, `case_id`, `endpoint`, `url`, `model`, `stream`, `elapsed_ms`, `status`, `trace_id`, `request`, `request_headers` (Authorization keeps only its first and last characters), `response` (including raw response bytes and SSE events) and any exception. Measurement records (packets, calibration) are tagged by `kind`; count requests only from records that have `request_number`. Logs contain real responses; do not commit them.
