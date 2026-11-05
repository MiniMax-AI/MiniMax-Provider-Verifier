# M2-Her Compatibility Format Check Cases

> File: [`m2_her_format_check/m2_her_compat_tests.py`](../m2_her_compat_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **1**; case functions: **12**; collected pytest items: **49**
> Expected values: set from what the live API returned on 2026-11-05; where the public docs disagree, the live API wins. See the [README](../README_en.md) for judging rules and expected randomness.

## Module overview

| Module | Name | Topic | Functions |
|:---:|:---|:---|:---:|
| 15 | compat | Endpoint compatibility, legacy fields, extension parameters and packets | 12 |

---

## 15 compat — Endpoint compatibility, legacy fields, extension parameters and packets

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L36) | The same named seven-role messages sent through the native endpoint /v1/text/chatcompletion_v2, HTTP requests to the OpenAI-compatible endpoint /v1/chat/completions, and the official OpenAI SDK, once streaming and once non-streaming. | As observed live: native HTTP, OpenAI HTTP and the SDK all succeed in both modes. Each variant can be overridden with the actual contract. | --run-compat; built-in observed baseline, overridable |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L63) | Long continuation task: max_tokens=16 alone; max_tokens=8 with max_completion_tokens=32; max_tokens=32 with max_completion_tokens=8. | max_tokens works as a legal alias; when both are sent max_completion_tokens wins, truncating at 16 / 32 / 8 tokens respectively. For the 32 variant, a natural stop that already exceeds 8 tokens also proves max_completion_tokens wins. | --run-compat; built-in observed baseline, overridable |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L85) | max_completion_tokens set to 2049 and 4096. | Default baseline: an explicit parameter error. If overridden to "capped at 2048", the output must actually stay within 2048. | --run-compat; built-in observed baseline, overridable |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L114) | Empty messages, empty content, whitespace-only content, a system message with name but no content (as in the official example), and system without user. | As observed live: empty messages and system-only return 2013; empty content returns a placeholder envelope followed by business code 1000 "unknown error" in the same body; whitespace content and the name-only system succeed. | --run-compat; built-in observed baseline, overridable |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L146) | Multiple system messages, two consecutive user messages, two consecutive assistant messages, one-sided samples, and group / user_system after user. | As observed live: consecutive user / assistant and one-sided samples succeed; multiple system (group chat not supported) and out-of-order roles (invalid message role: group) return 2013. | --run-compat; built-in observed baseline, overridable |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L187) | Native streaming requests that omit stream_options, send include_usage=true, and send include_usage=false. | As observed live: omitting or sending stream_options (include_usage true / false) all succeed and the stream carries usage. | --run-compat; built-in observed baseline, overridable |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L237) | Plain requests with tools, tool_choice, thinking, reasoning_split, reasoning_effort, response_format, seed or stop added. | As observed live: all 8 undeclared parameters are accepted and answered normally. Only acceptance is checked; it does not mean tools / thinking etc. take effect. | --run-compat; built-in observed baseline, overridable |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L250) | Two tasks, a long travelogue and a JSON list, each sampled 3 times in streaming mode; if the accumulated text is under 1000 characters, continue with the real reply, up to 20 requests in total, budget 2048 each. | Observed packet shape: per response, first packet ≤6 characters (the first token is sent immediately), middle packets ≥5 characters, any packet ≤512 characters. Below 1000 characters, continuation adds samples; still short after 20 requests means not validated. The five packet ratios are recorded, not judged. | --run-compat; built-in observed baseline, overridable + --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L306) | Besides the main-role system, add a system with name=旁白 (narrator), plus named user_system and user. | As observed live: both output modes succeed and reply in the main role's voice. | --run-compat; built-in observed baseline, overridable |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L323) | The last user message has name "推荐回复" (suggested reply) and empty content; compare with and without samples. | As observed live: with or without samples, both output modes succeed and produce one suggested reply. | --run-compat; built-in observed baseline, overridable |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L348) | Two named system messages (角色A, 角色B) plus one user message. | Default baseline: a parameter error, kept distinct from the legal group-scene role. | --run-compat; built-in observed baseline, overridable |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L362) | Legacy max_tokens set to -1, 0 and 1, once streaming and once non-streaming; the long continuation task is used for 1. | -1 and 0 fall back to the deployment default budget and succeed; 1 succeeds and the output is truncated at 1 token. | --run-compat; built-in observed baseline, overridable |

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
