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
| 14_01 | [`test_14_01_sse_framing`](../m2_her_stream_tests.py#L17) | [S: must succeed](../README_en.md#verdict-rules) | A plain streaming request. | Content-Type is text/event-stream and every event parses; no broken events. | Default |
| 14_02 | [`test_14_02_chunk_envelope_consistency`](../m2_her_stream_tests.py#L23) | [S: must succeed](../README_en.md#verdict-rules) | A plain streaming request; check each packet's top-level fields. | Each packet has nonempty id/model and positive integer created, constant across the response; model matches the configured response model. Delta and full-message summary packets use their respective object types. | Default |
| 14_03 | [`test_14_03_delta_role_content_types`](../m2_her_stream_tests.py#L31) | [S: must succeed](../README_en.md#verdict-rules) | A plain streaming request; check delta.role and delta.content. | At least one delta.role is assistant, and any supplied role must be assistant. delta.content may be absent, null or a string; the final assembled text is nonempty. | Default |
| 14_04 | [`test_14_04_content_reassembly`](../m2_her_stream_tests.py#L40) | [S: must succeed](../README_en.md#verdict-rules) | Give an example, then ask the model to copy 12 ordered markers. | The concatenated text is exactly the 12 markers in order; if a full-message summary packet exists, it matches the concatenated text. | --run-behavior (model behavior, counted separately) |
| 14_05 | [`test_14_05_unicode_escape_chunks`](../m2_her_stream_tests.py#L62) | [S: must succeed](../README_en.md#verdict-rules) | Streamed copy of text containing quotes, backslashes, newlines and emoji. | Decoding succeeds and the text really contains ", \, a newline, 🙂 and 🚀. | --run-behavior (model behavior, counted separately) |
| 14_06 | [`test_14_06_stream_stop`](../m2_her_stream_tests.py#L79) | [S: must succeed](../README_en.md#verdict-rules) | Streaming, ask the model to answer only OK; limit 128 tokens, widened to 512 if truncated. | Reach finish_reason=stop within two attempts, without requiring exact text OK or [DONE]. Otherwise fail. Validate reported counts against the budget; length termination requires exact counts. | Default |
| 14_07 | [`test_14_07_stream_length`](../m2_her_stream_tests.py#L83) | [S: must succeed](../README_en.md#verdict-rules) | Streamed long continuation with an 8-token limit; if it finishes early, switch prompt and lower the limit to 1. | Reach finish_reason=length within two attempts with the count equal to the budget. Every attempt requires complete counts within budget. Missing counts or no truncation fail; only budget=1 permits empty text. | Default; needs completion_tokens, reported as unverifiable if missing |
| 14_08 | [`test_14_08_stream_usage`](../m2_her_stream_tests.py#L87) | [S: must succeed](../README_en.md#verdict-rules) | A plain streaming request; check packets that carry usage. | At least one packet carries usage and the final total_tokens is greater than 0; intermediate packets may report 0. | Default |
| 14_09 | [`test_14_09_native_summary_message`](../m2_her_stream_tests.py#L100) | [S: must succeed](../README_en.md#verdict-rules) | A native streaming request; check the final packet and the full-message summary packet. | A packet with finish_reason exists; if a summary packet exists, it matches the concatenated text. | Default; native only |
| 14_10 | [`test_14_10_stream_error_response`](../m2_her_stream_tests.py#L116) | [F: must fail](../README_en.md#verdict-rules) | stream=true with messages set to null. | The request fails and is not an empty "successful" stream. First require a healthy control for the same endpoint, model, auth and stream mode; a failed preflight is SKIP. | Default |
| 14_11 | [`test_14_11_repeated_emoji_integrity`](../m2_her_stream_tests.py#L126) | [S: must succeed](../README_en.md#verdict-rules) | 20 streaming requests, each asking for 30 emoji (limit 512 tokens). | All 20 replies decode and pass format checks, each containing at least one character in U+1F300..U+1FAFF; exactly 30 emoji is not required. | --run-behavior (model behavior, counted separately); --run-slow |

---

## Appendix: the 11 items after parametrize expansion

| Expansion | Cases |
|:---|:---|
| `single` | 14_01 / 14_02 / 14_03 / 14_04 / 14_05 / 14_06 / 14_07 / 14_08 / 14_09 / 14_10 / 14_11 |

Multiple requests within one function (multi-turn round trips, isolation controls, repeated sampling) are not counted as extra items; see the run log for actual request counts.
