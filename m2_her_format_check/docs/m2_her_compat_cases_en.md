# M2-Her Compatibility Format Check Cases

> File: [`m2_her_format_check/m2_her_compat_tests.py`](../m2_her_compat_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **1**; case functions: **12**; collected pytest items: **49**
> Expected values: taken from the official MiniMax API (measured 2026-11-05); see the [README](../README_en.md) for the rules.
> "The request fails": HTTP status is not 200, or HTTP 200 with a non-zero business code / an error object in the response, and no reply text; specific error codes and messages are not compared.

## Module overview

| Module | Name | Topic | Functions |
|:---:|:---|:---|:---:|
| 15 | compat | Call paths, legacy and extra parameters, stream packets | 12 |

---

## 15 compat — Call paths, legacy and extra parameters, stream packets

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L36) | The same full seven-role conversation (every message with a name) sent three ways: the native endpoint /v1/text/chatcompletion_v2, the OpenAI-compatible endpoint /v1/chat/completions, and the official OpenAI SDK; streaming and non-streaming. | All three ways succeed in both modes. | --run-compat; expectations replaceable with --contract |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L63) | Long continuation: only max_tokens=16; max_tokens=8 with max_completion_tokens=32; max_tokens=32 with max_completion_tokens=8. | max_tokens works in place of max_completion_tokens; when both are sent, max_completion_tokens wins, truncating at 16 / 32 / 8 tokens. In the second case, a reply that finishes early but already exceeds 8 tokens also shows that max_completion_tokens wins. | --run-compat; expectations replaceable with --contract |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L85) | max_completion_tokens set to 2049 and 4096. | The request fails. | --run-compat; expectations replaceable with --contract |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L114) | Empty messages, empty content, whitespace-only content, a system message with name but no content (as in the official example), and only system without user. | Empty messages, empty content and system-only must fail; for whitespace-only content, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx); the name-only system succeeds. | --run-compat; expectations replaceable with --contract |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L146) | Several system messages, two user messages in a row, two assistant messages in a row, half a sample pair (only sample user or only sample ai), and group / user_system after user. | Consecutive user and consecutive assistant succeed; for half a sample pair, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx); several system messages and wrong role order must fail. | --run-compat; expectations replaceable with --contract |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L187) | Native streaming requests without stream_options, with include_usage=true and with include_usage=false. | All three succeed and the stream carries usage. | --run-compat; expectations replaceable with --contract |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L237) | Plain requests with tools, tool_choice, thinking, reasoning_split, reasoning_effort, response_format, seed or stop added. | For each parameter, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx). This only checks the request is handled; it does not mean the feature takes effect. | --run-compat; expectations replaceable with --contract |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L250) | Two tasks, a long travelogue and a JSON list, each streamed 3 times; while the total text is under 1000 characters, continue with the previous replies, up to 20 requests at 2048 tokens each. | Per response, the first packet is at most 6 characters (the first token is sent at once), middle packets at least 5 characters, and no packet over 512 characters. Still under 1000 characters after 20 requests is recorded as not validated. | --run-compat; expectations replaceable with --contract; --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L306) | Besides the main system, add a system with name "旁白" (narrator), plus user_system and user, all with names. | Both modes succeed with a well-formed, nonempty reply; the role or tone of the reply is not checked. | --run-compat; expectations replaceable with --contract |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L323) | The last user message has name "推荐回复" (suggested reply) and empty content; with and without samples. | Both modes succeed with or without samples, with a well-formed, nonempty reply; its meaning or sentence count is not checked. | --run-compat; expectations replaceable with --contract |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L348) | Two system messages with names (角色A, 角色B) plus one user message. | The request fails (this group-chat style is not supported; scenes belong in the group role). | --run-compat; expectations replaceable with --contract |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L362) | Legacy max_tokens set to -1, 0 and 1, streaming and non-streaming; the long continuation task is used for 1. | For -1 and 0, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx); 1 succeeds and the output is truncated at 1 token. | --run-compat; expectations replaceable with --contract |

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
