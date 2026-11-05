# M2-Her Streaming Protocol Format Check Cases

> File: [`m2_her_format_check/m2_her_stream_tests.py`](../m2_her_stream_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **1**; case functions: **11**; collected pytest items: **11**
> Expected values: set from what the live API returned on 2026-11-05; where the public docs disagree, the live API wins. See the [README](../README_en.md) for judging rules and expected randomness.

## Module overview

| Module | Name | Topic | Functions |
|:---:|:---|:---|:---:|
| 14 | sse_stream | SSE streaming protocol | 11 |

---

## 14 sse_stream — SSE streaming protocol

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 14_01 | [`test_14_01_sse_framing`](../m2_her_stream_tests.py#L17) | A plain request with stream=true. | Content-Type is text/event-stream; event boundaries and data JSON parse strictly with no broken events. | Default |
| 14_02 | [`test_14_02_chunk_envelope_consistency`](../m2_her_stream_tests.py#L23) | Plain streaming request; check the top-level fields of every packet. | Field types are correct and id, model and created stay the same within one response. | Default |
| 14_03 | [`test_14_03_delta_role_content_types`](../m2_her_stream_tests.py#L31) | Plain streaming request; check delta.role and delta.content. | role, when present, is assistant and content is a string; later packets may omit role. | Default |
| 14_04 | [`test_14_04_content_reassembly`](../m2_her_stream_tests.py#L40) | Exact-copy task: give an example, then ask to copy 12 ordered markers. | The concatenated text is exactly the 12 markers in order; if a full-message summary packet exists, it matches the concatenated deltas. | --run-behavior; counted separately, not part of the format pass rate |
| 14_05 | [`test_14_05_unicode_escape_chunks`](../m2_her_stream_tests.py#L62) | Streamed exact copy of text with quotes, backslashes, newlines and emoji. | Strict decoding succeeds and the text actually contains ", \, a newline, 🙂 and 🚀. | --run-behavior; counted separately, not part of the format pass rate |
| 14_06 | [`test_14_06_stream_stop`](../m2_her_stream_tests.py#L79) | Streaming request that asks only for OK; budget 128 tokens, widened to 512 if truncated. | At least one attempt ends with finish_reason=stop; no [DONE] marker is required. | Default |
| 14_07 | [`test_14_07_stream_length`](../m2_her_stream_tests.py#L83) | Streamed long continuation with an 8-token budget; if it stops naturally, switch prompt and lower the budget to 1. | At least one attempt ends with finish_reason=length and completion_tokens equals the budget exactly. | Needs real completion_tokens; missing counts are reported as unverifiable |
| 14_08 | [`test_14_08_stream_usage`](../m2_her_stream_tests.py#L87) | Plain streaming request; check packets that carry usage. | At least one packet carries usage and the final total_tokens is greater than 0; intermediate packets may report 0. | Default |
| 14_09 | [`test_14_09_native_summary_message`](../m2_her_stream_tests.py#L100) | Native streaming request; check the final packet and the full-message summary packet. | A packet with finish_reason exists; if a summary packet exists, its content matches the concatenated deltas. | Native only; final structure always checked, optional summary recorded as coverage |
| 14_10 | [`test_14_10_stream_error_response`](../m2_her_stream_tests.py#L116) | stream=true with messages set to null. | A parseable structured error is returned, not an empty successful stream. | Default |
| 14_11 | [`test_14_11_repeated_emoji_integrity`](../m2_her_stream_tests.py#L126) | 20 streamed requests, each asking for 30 emoji (budget 512). | Every response decodes as strict UTF-8 and all 20 contain emoji. | --run-behavior; counted separately, not part of the format pass rate; --run-slow |

---

## Appendix: the 11 items after parametrize expansion

| Expansion | Cases |
|:---|:---|
| `single` | 14_01 / 14_02 / 14_03 / 14_04 / 14_05 / 14_06 / 14_07 / 14_08 / 14_09 / 14_10 / 14_11 |

Multiple requests within one function (multi-turn round trips, isolation controls, repeated sampling) are not counted as extra items; see the run log for actual request counts.
