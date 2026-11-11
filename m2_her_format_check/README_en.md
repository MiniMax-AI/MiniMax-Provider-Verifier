# M2-Her Format Check — Standalone Test Package

[中文](README.md)

A standalone `pytest` suite that validates the format of the M2-Her native `/v1/text/chatcompletion_v2` API: text, system persona, the seven roles (system / user_system / group / sample_message_user / sample_message_ai / user / assistant), sample dialogues, multi-speaker conversations with `name`, sampling and output-length parameters, error handling, usage, the SSE streaming protocol, `n` multiple replies, extra request fields, and reply language.
It follows the M3 suite's module numbering, function naming and one-to-one py/md mapping. **After collection there are 103 case functions and 403 items** (text 343 / stream 11 / compat 49).

## Verification of the revised cases

The case and verdict changes are in [commit `f30ce27`](https://github.com/hustc5622/MiniMax-Provider-Verifier/commit/f30ce2704a9ddd4b803af4f544dbf8d73f8593f5). A follow-up added common Simplified/Traditional character pairs: short Chinese replies from the official endpoint (e.g. 咖啡馆, 当地) previously contained no distinguishing character, so the six Chinese-user variants of `19_04` were skipped.

The current branch collects 103 case functions and 403 live test items. All 84 offline regression tests pass. All 206 Chinese and English case rows were checked against the implementation.

Live runs of the current branch against the official M2-her native endpoint on 2026-11-06:

| Configuration | Command | Result |
|---|---|---|
| Native, all options | `pytest -n 8 --run-behavior --run-compat --run-slow` | **403 passed** in two consecutive runs, no skips |
| Native, default | `pytest -n 8` | 251 passed, 152 skipped because their options were not enabled |
| OpenAI-compatible, all options | `M2_HER_API_STYLE=openai pytest -n 8 --run-compat --run-slow --run-behavior` | **49 passed**; the other 354 items do not apply to this protocol |
| OpenAI-compatible without `--run-compat` | `M2_HER_API_STYLE=openai pytest` | configuration error, exit code 4 |

The run logs contain none of the configured key or query-parameter values.

## Where the expected values come from

M2-Her is an older model and its public docs diverge from the actual API in many places. **The expected values are taken from what the official channel (MiniMax native `/v1/text/chatcompletion_v2`, model `M2-her`) returned on 2026-11-05, with OpenAI streaming usage additionally measured on 2026-11-06**, so a third-party M2-Her deployment can be checked against the official format. Every check falls into one of three categories:

| Category | Rule | Examples |
|------|------|------|
| Must succeed | The request succeeds and the reply is well-formed (the required fields, types, usage and SSE checks are specified by each case) | All seven roles with `name`; valid temperature / top_p / max_completion_tokens |
| Must fail | **HTTP status is not 200, or HTTP 200 with a non-zero business code (`base_resp.status_code`) or an `error` object**, and no reply text comes back. **Error codes, messages and framing are not compared** | Wrong types, missing fields, bad auth, input over 64K, n=5, specified role combinations without `name` |
| Accept or reject | Values the docs rule out but the official API accepts: an acceptance must be a well-formed reply, a rejection must meet "must fail"; **a 5xx always fails** | temperature=0 / 1.01, top_p=0, max_completion_tokens=0 / -1 / null, n=0 / -1 / null, undeclared parameters |

The measured error scenarios all returned HTTP 200 with a business error code, sometimes with inconsistent codes or messages. Error cases therefore use the common request-failure rule without requiring providers to copy those codes or messages.

Error responses may use JSON, SSE, or several consecutive complete JSON objects. Parsing must consume the complete response: invalid UTF-8, trailing JSON garbage, and malformed or incomplete SSE events fail. Non-200 plain-text or HTML error pages may also indicate rejection; responses declared as JSON / SSE or starting with a JSON object or array must parse correctly.

Model behavior is opt-in via `--run-behavior`. The historical ten-run official baseline used the earlier prompts and verifier. Both language cases now take up to three samples per variant under the voting rule below.

Expected values live in [`observed.py`](observed.py) (the `n` limit), [`acceptance_baseline.json`](acceptance_baseline.json) (compatibility cases) and the test functions; the per-case expectations are listed in the case docs under `docs/`.

<a id="verdict-rules"></a>

## Common verdict rules (referenced by every case)

S / F / E specify the **target request's expected outcome**, not the test result. A failed request passes the test only when it meets that case's F/E rule. A healthy control alone does not finish the test. Tables show bundled expectations; `--contract` replaces each selected rule in full.

| Rule | Test passes when | Cannot pass |
|---|---|---|
| **S: must succeed** | HTTP 200 with a fully parsed normal reply satisfying the case's format and content checks | Non-200 HTTP, business errors, malformed responses or failed assertions |
| **F: must fail** | An HTTP response was received: non-200, or HTTP 200 containing an integer nonzero `base_resp.status_code` / a dictionary `error` (including an empty object), without non-whitespace `choices[].message.content` / `delta.content` | An ordinary HTTP 200 success; an empty stream, `[DONE]` or empty success envelope without an error marker; string/boolean business codes or non-object error used as HTTP 200 error markers; reply text followed by an error; malformed declared JSON/SSE |
| **E: success or failure, no 5xx** | Reject HTTP 5xx first, then apply S or F and any case-specific checks | Any HTTP 5xx, an empty response without an error marker, malformed accepted or rejected responses |

**HTTP boundaries:** Under the agreed non-200 rule, F can accept 3xx, 4xx (including 429), and 5xx as the HTTP failure condition; E always fails on 5xx. This proves failure, not that the mutated field caused it. A healthy control reduces outage-related false positives but cannot exclude a later fault. Connection failures and timeouts without a usable response are not passing rejections; such exceptions on the target request are reported as errors.

**Error parsing:** Accept one JSON object, several consecutive complete objects, or complete SSE events with parseable data. Invalid UTF-8, NaN/Infinity/-Infinity, trailing JSON garbage and malformed or incomplete events fail. Non-200 plain-text/HTML errors may represent rejection; declared JSON/SSE or bodies starting with a JSON object/array must parse accordingly. Codes, wording and JSON/SSE framing need not match the official endpoint.

**Common success checks:** Non-streaming expects one reply unless an n case specifies otherwise, checking indexes, message role/content, finish reason and usage. Streaming checks SSE, delta types, assembled content, a consistent terminal reason, no content after termination, and any full-message summary against the deltas. Text is nonempty by default; `09_03` permits empty text for nonpositive budgets, while output-budget checks permit it only at limit=1. Mandatory streaming usage and envelope id/model/created checks are stated by each case; a generic format check does not imply every optional field is checked everywhere.

**Interpreting SKIP and exit codes**

- F/E cases usually need a healthy control using the same endpoint, model, credentials and stream mode. Each worker caches its control results. A failed preflight skips the dependent case.
- In-case positive controls must succeed. For example, `12_04` remeasures the same near-window input and `17_05/06/08` establish the supported candidate count. If even a single candidate with tools is explicitly rejected, `17_06` skips the untestable combination.
- Cases can skip for an inapplicable protocol, disabled flags, an unobserved finish reason or output ceiling, inconclusive language votes, or insufficient emoji or packet samples. Observed protocol, count and packet violations still fail.
- A live command with missing endpoint/credentials, or OpenAI mode without `--run-compat`, exits with configuration error 4. A live run producing only skips exits with 5. Collection and explicit offline regressions need no credentials.

**Name scope:** Required rejection for missing names only covers the concrete combinations in `05_04`, `13_01`, `13_05` and `16_01`. Unnamed standalone user_system in `03_01`, standalone group in `04_01`, and plain user in `06_01` still must succeed. Do not generalize this into a requirement that every advanced role must have a name.

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
- Headers = `Content-Type` + `M2_HER_EXTRA_HEADERS`; when `M2_HER_AUTH_TYPE=bearer`, set `Authorization: Bearer $M2_HER_API_KEY`
- Body `model` = `M2_HER_MODEL`

## Optional environment variables

| Variable | Default | Description |
|------|------|------|
| `M2_HER_MODEL` | `M2-her` | Model ID sent in requests; may be the provider's model name |
| `M2_HER_RESPONSE_MODEL` | same as `M2_HER_MODEL` | Expected `model` in responses; set it when the API returns a different name |
| `M2_HER_AUTH_TYPE` | `bearer` | `none` disables automatic bearer authentication (case 11_06 is skipped); explicitly configured headers in `M2_HER_EXTRA_HEADERS`, including custom `Authorization`, are preserved. HTTP and SDK use the same rules. 11_06 also skips when another recognized credential might authorize requests without Bearer |
| `M2_HER_API_STYLE` | `native` | `native` → `/v1/text/chatcompletion_v2`; `openai` → `/v1/chat/completions` (the 15_* and 10_07 compatibility cases run) |
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

Native mode selects 251 items by default. OpenAI mode requires `--run-compat` for its 47 regular cases. Add `--run-slow` to run all 49 applicable items. Both OpenAI clients stay on the configured compatible endpoint.

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

# Provider exposing only the OpenAI-compatible API
M2_HER_API_STYLE=openai pytest --run-compat --run-slow

# Offline verifier regressions
pytest verifier_regressions/test_*.py

# 3d. Model-behavior cases only
pytest --run-behavior -m behavior

# 3e. Reproduce a single case (quote node ids containing brackets in zsh)
pytest -v 'm2_her_text_tests.py::TestCombinations::test_13_01_all_seven_roles[non_stream-all_named]'
```

When checking a new endpoint for the first time, run the default cases serially first so that authentication or rate-limit problems are not amplified by concurrency.

## How results are judged

- **Validation tiers**: each item carries a `validation_tier` junit property: `documented_api` (public API format, 202 items), `implementation_api` (server-side extra fields such as `n` and `metadata`, 59 items), `behavior` (model behavior, 91 items) and `endpoint_contract` (compatibility, 51 items).
- **Healthy control first**: "must fail" and "accept or reject" cases first send a normal request with the same endpoint, model, auth and stream mode. If that control fails, the case is SKIPPED as not validated, so an outage is never counted as a correct rejection. Missing-field, malformed-JSON and no-auth cases go through the raw request path; the test code never fills in parameters. There are no automatic retries.
- **Output length.** Finish-reason checks use up to two stimuli. Compatibility ceilings use up to three continuations. A sequence of valid replies that never exercises the target yields SKIP. A truncated reply must report exactly the budget. Missing required counts or inconsistent counts fail.
- **Context.** Automatic calibration uses up to eight probes per mode. An external fixture must use the same valid messages and measured prompt count on both sides, within 384 tokens of the window. Even the over-window case run alone remeasures this input before increasing the reserved output.
- **Streaming.** Native streams may omit `[DONE]`. Every usage-bearing event must have valid counts, including intermediate zero placeholders. Case `14_08` requires positive final usage at or after the finish event.
- **Packet size (15_08)**: per response, first packet ≤6 characters, middle packets ≥5 characters, any packet ≤512 characters. The five M3 bucket ratios are recorded only.
- **Reply language (19_01 and 19_04).** Local rules use scripts, distinctive letters and common words. Each variant samples up to three replies. Two clear matches pass, two clear mismatches fail, and all other combinations skip. Request or protocol errors fail immediately. Model behavior is excluded from the default format gate.

Cases `18_01/18_03` retain the observed acceptance and rejection requirements for 255/256 ASCII characters. Additional multibyte probes record the provider’s outcome. The original ASCII measurements alone cannot distinguish a byte limit from a character limit.

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
- **JSONL logs.** Each worker writes its own file using the M3 convention. Request records include the case ID, request number, protocol, path, model, status and response evidence. Logged URLs exclude user information and the query string. Only Accept, Content-Type and Content-Length header values are retained, for both requests and responses. Evidence repeating a configured private value is withheld together with its wire copies. Packet and calibration measurements have separate kind fields. Logs contain real model input and output.
