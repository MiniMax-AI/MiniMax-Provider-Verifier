# M2-Her Compatibility Format Check Cases

> File: [`m2_her_format_check/m2_her_compat_tests.py`](../m2_her_compat_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **1**; case functions: **12**; collected pytest items: **49**
> Expected values: taken from the official MiniMax API (measured 2026-11-05/06); see the [README](../README_en.md) for the rules.
> "The request fails": HTTP status is not 200, or HTTP 200 with a non-zero business code / an error object in the response, and no reply text; specific error codes and messages are not compared.
> The table describes the bundled baseline. See the [common verdict rules](../README_en.md#verdict-rules) for S / F / E and PASS / FAIL / SKIP. F includes non-200 HTTP 5xx; E forbids 5xx. Network exceptions are not expected rejections; malformed JSON / SSE cannot pass.

## Module overview

| Module | Name | Topic | Functions |
|:---:|:---|:---|:---:|
| 15 | compat | Call paths, legacy and extra parameters, stream packets | 12 |

---

## 15 compat — Call paths, legacy and extra parameters, stream packets

| Case ID | Function | Verdict rule | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L37) | [S: must succeed](../README_en.md#verdict-rules) | The same full seven-role conversation (every message with a name) sent three ways: the native endpoint /v1/text/chatcompletion_v2, the OpenAI-compatible endpoint /v1/chat/completions, and the official OpenAI SDK; streaming and non-streaming. | All three ways succeed in both modes. | --run-compat; expectations replaceable with --contract |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L64) | [S: must succeed](../README_en.md#verdict-rules) | Long continuation: only max_tokens=16; max_tokens=8 with max_completion_tokens=32; max_tokens=32 with max_completion_tokens=8. | Verify budgets 16/32/8 with at most three continuation prompts each. Require length termination with counts equal to the budget; only legacy_smaller may stop naturally with more than 8 and at most 32 tokens as evidence of max_completion_tokens precedence. | --run-compat; expectations replaceable with --contract |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L86) | [F: must fail](../README_en.md#verdict-rules) | max_completion_tokens set to 2049 and 4096. | The request fails. First require a healthy control for the same endpoint, model, auth and stream mode; a failed preflight is SKIP. | --run-compat; expectations replaceable with --contract |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L115) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Empty messages, empty content, whitespace-only content, a system message with name but no content (as in the official example), and only system without user. | empty_messages, empty_content and system_only must fail. whitespace may succeed or fail, never with 5xx. system_name_only (a name-only system followed by a user) must succeed. Only rejection/either branches require a preflight; a failed preflight is SKIP. | --run-compat; expectations replaceable with --contract |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L147) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Six inputs: two unnamed system messages; consecutive user; consecutive assistant; sample-user only; sample-ai only; unnamed group/user_system placed after user. | consecutive_user and consecutive_assistant must succeed. sample_user_only and sample_ai_only may succeed or fail, never with 5xx. The specific multiple_system and role_order inputs must fail; this does not isolate ordering from missing names as the cause. Only rejection/either branches require a preflight; a failed preflight is SKIP. | --run-compat; expectations replaceable with --contract |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L188) | [S: must succeed](../README_en.md#verdict-rules) | Use the native or OpenAI endpoint selected by M2_HER_API_STYLE; stream with stream_options omitted, include_usage=true and include_usage=false. | All three succeed. Native streams carry usage in all variants; OpenAI streams carry usage only with include_usage=true, not when omitted or false. Any reported usage must pass type and count checks. | --run-compat; expectations replaceable with --contract |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L238) | [E: succeed or fail, no 5xx](../README_en.md#verdict-rules) | Plain requests with tools, tool_choice, thinking, reasoning_split, reasoning_effort, response_format, seed or stop added. | For each parameter, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx). This only checks the request is handled; it does not mean the feature takes effect. First require a healthy control for the same endpoint, model, auth and stream mode; a failed preflight is SKIP. | --run-compat; expectations replaceable with --contract |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L251) | [S: must succeed](../README_en.md#verdict-rules) | Two tasks, a long travelogue and a JSON list, each streamed 3 times; while the total text is under 1000 characters, continue with the previous replies, up to 20 requests at 2048 tokens each. | Check each response immediately using nonempty delta character counts: first packet≤6, middle packets≥5, every packet≤512. Violations fail before the sampling gate. Pass after at least 3 requests and 1000 characters; SKIP if still short after 20. Bucket ratios are recorded only; token latency and JSON text compliance are not checked. | --run-compat; expectations replaceable with --contract; --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L311) | [S: must succeed](../README_en.md#verdict-rules) | Besides the main system, add a system with name "旁白" (narrator), plus user_system and user, all with names. | Both modes succeed with a well-formed, nonempty reply; the role or tone of the reply is not checked. | --run-compat; expectations replaceable with --contract |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L328) | [S: must succeed](../README_en.md#verdict-rules) | The last user message has name "推荐回复" (suggested reply) and empty content; with and without samples. | Both modes succeed with or without samples, with a well-formed, nonempty reply; its meaning or sentence count is not checked. | --run-compat; expectations replaceable with --contract |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L353) | [F: must fail](../README_en.md#verdict-rules) | Two system messages with names (角色A, 角色B) plus one user message. | This specific input with two named system messages and one user must fail; this does not imply that all multi-role conversations are unsupported. First require a healthy control for the same endpoint, model, auth and stream mode; a failed preflight is SKIP. | --run-compat; expectations replaceable with --contract |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L367) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Legacy max_tokens set to -1, 0 and 1, streaming and non-streaming; the long continuation task is used for 1. OpenAI streaming count measurements explicitly request stream_options.include_usage=true. | -1 and 0 may succeed or fail, never with 5xx. 1 must succeed and reach length termination with completion_tokens=1 within three continuation prompts; empty text is allowed. Only rejection/either branches require a preflight; a failed preflight is SKIP. | --run-compat; expectations replaceable with --contract |

---

## Appendix: the 49 items after parametrize expansion

| Expansion | Cases |
|:---|:---|
| `variant(3) × stream(2)` | 15_01 |
| `variant,limits(3)` | 15_02 |
| `limit(2)` | 15_03 |
| `variant(5)` | 15_04 |
| `variant(6)` | 15_05 |
| `variant(3)` | 15_06 |
| `parameter,value(8)` | 15_07 |
| `variant(2)` | 15_08 |
| `stream(2)` | 15_09 / 15_11 |
| `samples(2) × stream(2)` | 15_10 |
| `limit(3) × stream(2)` | 15_12 |

Multiple requests within one function (multi-turn round trips, isolation controls, repeated sampling) are not counted as extra items; see the run log for actual request counts.
