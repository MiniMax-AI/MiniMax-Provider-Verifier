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

Rejection and either-outcome branches first run a healthy control with the same endpoint, model, credentials and streaming mode. If the control fails, the target is skipped.

| Case ID | Function | Verdict rule | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L37) | [S: must succeed](../README_en.md#verdict-rules) | Take one conversation using all seven message roles, each with a name. Send it over native HTTP, OpenAI-compatible HTTP and the OpenAI SDK, once with streaming and once without. | Native configuration requires all six combinations. OpenAI configuration runs the four OpenAI HTTP and SDK combinations only; both native variants skip without sending a request. The SDK must extract the same text as the raw response. | --run-compat; expectations replaceable with --contract |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L66) | [S: must succeed](../README_en.md#verdict-rules) | Ask for a long continuation, first using only the legacy budget, then making each of the two budgets smaller in turn. | Legacy 16 alone must truncate at 16. Legacy 32 with new 8 must truncate at 8. Legacy 8 with new 32 may truncate at 32 or stop naturally at 9–32. Each branch allows up to three prompts. Skip if three valid replies give no evidence of the limit or precedence; fail on missing or invalid counts. | --run-compat; expectations replaceable with --contract |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L88) | [F: must fail](../README_en.md#verdict-rules) | Set max_completion_tokens to 2049 or 4096, both beyond the 2048 limit. | The default requires rejection for both. If a provider contract explicitly accepts and caps these budgets, verify actual truncation at 2048. Skip if three valid attempts fail to reach that budget; missing or invalid counts fail. | --run-compat; expectations replaceable with --contract |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L117) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Try an empty message list, empty user text, whitespace-only user text, a name-only system followed by a user, and a system alone. | Reject the empty list, empty user text and system alone. Whitespace may be accepted or rejected, with no 5xx. Accept the name-only system when followed by a normal user. | --run-compat; expectations replaceable with --contract |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L149) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Try consecutive user turns, consecutive assistant turns, one half of a sample pair, two unnamed systems, and unnamed group/user_system messages after a user. | Accept consecutive user or assistant turns. Either half of a sample pair may be accepted or rejected, with no 5xx. Reject the two specific unnamed combinations. The mixed-order input changes both names and order. | --run-compat; expectations replaceable with --contract |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L190) | [S: must succeed](../README_en.md#verdict-rules) | Omit stream_options, enable include_usage, then disable it. For each request inspect the reply and usage. | All three must succeed. Native must include usage each time; OpenAI must include it only when enabled. Validate every non-null usage, including early events. Constrain it to the final event only if the provider contract sets usage_only_last. | --run-compat; expectations replaceable with --contract |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L246) | [E: succeed or fail, no 5xx](../README_en.md#verdict-rules) | Add one extra option to an ordinary request: tools, tool_choice, thinking, reasoning_split, reasoning_effort, response_format, seed or stop. | Accept a valid reply or a rejection for each option; 5xx fails. A server that ignores the option can pass, so the result does not establish feature support. | --run-compat; expectations replaceable with --contract |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L259) | [S: must succeed](../README_en.md#verdict-rules) | Ask for a travelogue or a JSON list. For each task request at least three streams, then continue the conversation until 1000 characters, up to 50 requests of at most 2048 tokens each. | Count nonempty text deltas separately for each reply. First ≤6 characters, middle ≥5, each ≤512. Fail immediately on a violation. Skip if still short at 50. Packet size is judged independently of text quality, JSON validity and delivery latency. | --run-compat; expectations replaceable with --contract; --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L319) | [S: must succeed](../README_en.md#verdict-rules) | Alongside a main character, add a second system message named 旁白 (narrator), followed by the user profile and question. Name each message. | Both streaming and non-streaming must return valid nonempty text. The narrator’s tone is outside the check. | --run-compat; expectations replaceable with --contract |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L336) | [S: must succeed](../README_en.md#verdict-rules) | End a travel conversation with an empty user message named 推荐回复 (suggest a reply). Try both with and without sample dialogue. | Both conversations must return valid nonempty text in both modes. The number of suggested sentences and their meaning are outside the check. | --run-compat; expectations replaceable with --contract |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L361) | [F: must fail](../README_en.md#verdict-rules) | Set up characters A and B in two named system messages, then send one user greeting from A to B. | Require rejection in both streaming and non-streaming. This applies to these three messages; the narrator conversation in 15_09 has a separate expectation. | --run-compat; expectations replaceable with --contract |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L375) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Try legacy max_tokens of −1, 0 and 1 with both streaming and non-streaming. At 1, ask for a long continuation. | At −1 or 0, accept a valid reply or rejection, never 5xx. At 1, require truncation with completion_tokens=1 within three prompts; empty text is allowed. The OpenAI stream explicitly requests usage. Skip if three valid attempts end naturally; missing or invalid counts fail. | --run-compat; expectations replaceable with --contract |

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
