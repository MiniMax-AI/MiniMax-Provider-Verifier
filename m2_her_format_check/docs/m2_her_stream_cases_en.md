# M2-Her Streaming Protocol Format Check Cases

> File: [`m2_her_format_check/m2_her_stream_tests.py`](../m2_her_stream_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **1**; case functions: **11**; collected pytest items: **11**
> Expected values: taken from the official MiniMax API (measured 2026-11-05/06); see the [README](../README_en.md) for the rules.
> "The request fails": HTTP status is not 200, or HTTP 200 with a non-zero business code / an error object in the response, and no reply text; specific error codes and messages are not compared.
> The table describes the bundled baseline. See the [common verdict rules](../README_en.md#verdict-rules) for S / F / E and PASS / FAIL / SKIP. F includes non-200 HTTP 5xx; E forbids 5xx. Network exceptions are not expected rejections; malformed JSON / SSE cannot pass.

## Module overview

| Module | Name | Topic | Functions |
|:---:|:---|:---|:---:|
| 14 | sse_stream | SSE streaming protocol | 11 |

---

## 14 sse_stream — SSE streaming protocol

| Case ID | Function | Verdict rule | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 14_01 | [`test_14_01_sse_framing`](../m2_her_stream_tests.py#L16) | [S: must succeed](../README_en.md#verdict-rules) | Send a short request and ask for the reply as a stream. | Require text/event-stream, valid SSE events, nonempty assembled text and a valid finish reason. This does not measure delivery time. | Default |
| 14_02 | [`test_14_02_chunk_envelope_consistency`](../m2_her_stream_tests.py#L22) | [S: must succeed](../README_en.md#verdict-rules) | Check that all events identify the same reply. | Require stable id, model and created fields, a nonempty ID, the configured response model and a positive integer timestamp. Delta and full-message events use their respective object types. | Default |
| 14_03 | [`test_14_03_delta_role_content_types`](../m2_her_stream_tests.py#L30) | [S: must succeed](../README_en.md#verdict-rules) | Check who is speaking in each delta and what it carries as text. | At least one delta declares role=assistant. Later deltas may omit the role. Supplied roles must be assistant; content may be omitted, null or a string. The assembled reply must contain text. | Default |
| 14_04 | [`test_14_04_content_reassembly`](../m2_her_stream_tests.py#L39) | [S: must succeed](../README_en.md#verdict-rules) | Give a copy example, then ask for HER_00 through HER_11 in order, separated by vertical bars. | Validate the stream first. After trimming outer whitespace, missing, extra or reordered text fails the behavior check. Any full-message summary must also match the untrimmed deltas. | --run-behavior (model behavior, counted separately) |
| 14_05 | [`test_14_05_unicode_escape_chunks`](../m2_her_stream_tests.py#L61) | [S: must succeed](../README_en.md#verdict-rules) | Ask for a copy of text containing quotes, a backslash, a newline and emoji. | Bad UTF-8 or SSE/JSON fails the format check. A valid reply must also contain a quote, a backslash, a newline, 🙂 and 🚀. A missing character fails the behavior check. | --run-behavior (model behavior, counted separately) |
| 14_06 | [`test_14_06_stream_stop`](../m2_her_stream_tests.py#L78) | [S: must succeed](../README_en.md#verdict-rules) | Ask for just OK with 128 tokens; if truncated, widen the budget to 512. | Pass on stop. Skip if both valid replies hit the budget. Check any observed counts; length requires a count equal to the budget. | Default |
| 14_07 | [`test_14_07_stream_length`](../m2_her_stream_tests.py#L82) | [S: must succeed](../README_en.md#verdict-rules) | Ask for more of a long story with 8 tokens. If it stops naturally, try a different continuation with 1 token. | Require length and a count equal to the budget at least once. Every attempt requires complete counts within budget. Skip if both valid replies end naturally. Only the one-token reply may be empty. | Default; needs completion_tokens, reported as unverifiable if missing |
| 14_08 | [`test_14_08_stream_usage`](../m2_her_stream_tests.py#L86) | [S: must succeed](../README_en.md#verdict-rules) | Stream a short answer and check when the request reports its final usage. | Validate every supplied usage object, allowing early zero placeholders. Usage must appear in the first finish event or later; the last reported total_tokens must be positive. An early positive report alone fails. | Default |
| 14_09 | [`test_14_09_native_summary_message`](../m2_her_stream_tests.py#L103) | [S: must succeed](../README_en.md#verdict-rules) | Check how the native stream ends. Some endpoints also send a full copy of the answer. | Require a valid finish reason. If the full answer is included, it must match the deltas. A missing full-message summary is permitted; record how many were observed. | Default; native only |
| 14_10 | [`test_14_10_stream_error_response`](../m2_her_stream_tests.py#L119) | [F: must fail](../README_en.md#verdict-rules) | Confirm a healthy stream at the same endpoint, model and credentials, then set messages to null. | Skip if the control fails. The target must be rejected without normal reply text; a regular JSON error is acceptable. | Default |
| 14_11 | [`test_14_11_repeated_emoji_integrity`](../m2_her_stream_tests.py#L129) | [S: must succeed](../README_en.md#verdict-rules) | Make 20 streaming requests asking for 30 emoji each, within 512 tokens per request. | A malformed stream fails immediately. Pass when each reply contains at least one U+1F300..U+1FAFF character. If any valid reply lacks one, log the coverage count and skip. The prompt does not impose an exact emoji count. | --run-behavior (model behavior, counted separately); --run-slow |

---

## Appendix: the 11 items after parametrize expansion

| Expansion | Cases |
|:---|:---|
| `single` | 14_01 / 14_02 / 14_03 / 14_04 / 14_05 / 14_06 / 14_07 / 14_08 / 14_09 / 14_10 / 14_11 |

Multiple requests within one function (multi-turn round trips, isolation controls, repeated sampling) are not counted as extra items; see the run log for actual request counts.
