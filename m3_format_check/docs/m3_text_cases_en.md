# M3 Text Modality Format Validation Case List

> Corresponds to: `data/m3_api_test/m3_text_tests.py`
> Tool-call cases added to `m3_1_flash_text_test.py` are listed under "M3.1-Flash tool-call contract cases".
> Naming convention: `test_<module_id>_<intra_module_seq>_<scene>`
> Modules: **20**; Test functions: **107**; Pytest collected items: **139**

## Module Overview

| Module ID | Module Name | Theme | Functions |
|:---:|:---|:---|:---:|
| 01 | basic_text | Basic text conversation (non-stream) | 3 |
| 02 | sse_stream | SSE streaming protocol fields | 6 |
| 03 | multiturn | Multi-turn conversation | 2 |
| 04 | thinking | thinking toggle | 4 |
| 05 | sampling | Sampling params (temperature / top_p / seed) | 3 |
| 06 | max_tokens | max_tokens / max_completion_tokens boundaries | 11 |
| 07 | message_format | Message content/role format & edge cases | 6 |
| 08 | model_compat | Model name compatibility | 1 |
| 09 | response_format | response_format JSON output (**ALL SKIPPED — not supported by M3 yet**) | 3 |
| 10 | usage_field | usage field semantics / arithmetic / cache | 8 |
| 11 | role_root | role=root protocol acceptance & identity adherence | 4 |
| 12 | text_semantic | Text semantic adherence | 6 |
| 13 | tool_call_basic | Tool call basics | 12 |
| 14 | tool_call_schema | Tool call advanced schema validation | 6 |
| 15 | tool_call_combo | Tool call combined with other features | 6 |
| 16 | tool_call_edge | Tool call boundary / exception handling | 14 |
| 17 | param_stress | Parameter stress (long conversation / long system) | 2 |
| 18 | reasoning_split | reasoning_split extension field | 1 |
| 19 | finish_reason | finish_reason coverage | 2 |
| 20 | error_codes | Error codes (text-only) | 8 |

---

## 01 basic_text — Basic text conversation (non-stream)

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 01_01 | `test_01_01_text_non_stream` | Most basic non-stream text conversation | HTTP 200 + non-empty content |
| 01_02 | `test_01_02_content_string` | `user.content` as plain string | HTTP 200 |
| 01_03 | `test_01_03_content_array` | `user.content` as parts array `[{type:text,text:...}]` | HTTP 200 |

## 02 sse_stream — SSE streaming protocol fields

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 02_01 | `test_02_01_text_stream` | Text streaming response | Stream can rebuild content correctly |
| 02_02 | `test_02_02_stream_usage` | Last usage chunk in stream | total == prompt + completion + stream finishes properly |
| 02_03 | `test_02_03_sse_done_marker` | SSE `[DONE]` end marker | xfail if missing (known BUG) |
| 02_04 | `test_02_04_stream_chunk_fields` | Stream chunk required fields | id / choices / object all present |
| 02_05 | `test_02_05_text_include_usage` | `stream_options.include_usage=true` (text) | Stream should return usage chunk |
| 02_06 | — | Removed (formerly `test_02_06_stream_usage_only_in_last_chunk`) | Exact duplicate of `m3_stream_tests.py::TestSSEStream::test_02_06_stream_usage_only_in_last_chunk`; de-duplicated, the ID stays retired |
| 02_07 | `test_02_07_stream_no_utf8_replacement_char_in_emoji` | Emoji-dense streaming request run 20 times | No `U+FFFD` (`�`) replacement char in any `delta.content`; guards against a 4-byte emoji being truncated mid-UTF-8-frame |

## 03 multiturn — Multi-turn conversation

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 03_01 | `test_03_01_multiturn` | Two-turn: introduce as Alice then ask name | Response should contain "alice" |
| 03_02 | `test_03_02_multiturn_5_rounds` | 5-round arithmetic chat: x=10, y=15, z=25 | Response should contain "50" (x+y+z) |

## 04 thinking — thinking toggle

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 04_02 | `test_04_02_thinking_adaptive` | `thinking.type=adaptive` (model decides) | HTTP 200 |
| 04_03 | `test_04_03_thinking_invalid_value` | `thinking.type` invalid value | 400/422 reject or 200 fallback |
| 04_04 | `test_04_04_thinking_stream` | adaptive + stream | Streaming + thinking coexist |

## 05 sampling — Sampling params (temperature / top_p / seed)

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 05_01 | `test_05_01_temperature_values` | Valid temperatures [0, 0.5, 1, 2] | All values return 200 |
| 05_02 | `test_05_02_top_p` | top_p boundaries [0.1, 0.5, 0.95] | All values return 200 |
| 05_03 | `test_05_03_seed_parameter` | seed=42 + temperature=0 | API accepts for deterministic output |

## 06 max_tokens — max_tokens / max_completion_tokens boundaries

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 06_01 | `test_06_01_max_tokens_truncation` | max_tokens=10 truncation | finish_reason ∈ {length, stop} |
| 06_02 | `test_06_02_max_completion_tokens` | max_completion_tokens alias | HTTP 200 |
| 06_03 | `test_06_03_dual_max_tokens` | Both max_tokens + max_completion_tokens | HTTP 200 |
| 06_04 | `test_06_04_both_params_combo` | Combination (mct wins) | HTTP 200 |
| 06_05 | `test_06_05_mct_only` | max_completion_tokens=50 only | finish_reason ∈ {length, stop} |
| 06_06 | `test_06_06_max_tokens_1_timeout` | max_tokens=1 extreme | 200 or 408 (BUG-4) |
| 06_07 | `test_06_07_max_tokens_zero` | max_tokens=0 (illegal) | 200/400/422 all tolerated |
| 06_08 | `test_06_08_max_tokens_negative` | max_tokens=-1 (illegal) | 400/422 rejected (200 → fail) |
| 06_09 | `test_06_09_max_tokens_at_512k` | max_tokens ∈ {512000, 524288} | HTTP 200 |
| 06_10 | `test_06_10_max_tokens_above_512k` | max_tokens ∈ {524289, 1000000} | 200/400/422 all tolerated (strict providers reject, lenient providers accept and truncate) |
| 06_11 | `test_06_11_max_completion_tokens_at_512k` | max_completion_tokens=524288 | 200 or 400 |

## 07 message_format — Message content/role format & edge cases

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 07_01 | `test_07_01_consecutive_assistant` | Two consecutive assistant messages | HTTP 200 (non-stream/stream each 1 item) |
| 07_02 | `test_07_02_assistant_null_content_with_tool_calls` | assistant.content=null + tool_calls | HTTP 200 |
| 07_03 | `test_07_03_assistant_no_content_field_with_tool_calls` | assistant without content field + tool_calls | HTTP 200 |
| 07_04 | `test_07_04_user_content_empty_array` | user.content=[] empty array | status > 0 |
| 07_05 | `test_07_05_user_content_null` | user.content=null | 200 or 400 |
| 07_06 | `test_07_06_multiple_system_messages` | Multiple system messages | HTTP 200 + non-empty response |
| 07_07 | `test_07_07_history_tool_call_empty_object_arguments` | A tool_call in the conversation history with `arguments: "{}"` (empty JSON object) | HTTP 200 and the model continues the turn (non-empty content or a new tool_call) |

## 08 model_compat — Model name compatibility

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 08_01 | `test_08_01_model_name_compat` | Main model + mini model | Main model hard 200; mini xfail if unregistered |

## 09 response_format — response_format JSON output

> ⚠️ **All cases in this section are currently SKIPPED**: minimax-M3 does not yet support
> the `response_format=json_object` parameter. The entire `TestResponseFormat` class in
> `m3_text_tests.py` is decorated with `@pytest.mark.skip(...)`. Re-enable by removing
> the skip marker once M3 ships support. The combo case §15_02 also had its
> `response_format` field stripped — it now only exercises tools + tool_choice coexistence.

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 09_01 | `test_09_01_json_object_non_stream` | json_object non-stream (SKIPPED) | content is valid JSON dict |
| 09_02 | `test_09_02_json_object_stream` | json_object stream + thinking=disabled (SKIPPED) | Stream returns properly |
| 09_03 | `test_09_03_json_object_format` | json_object generic (non-stream/stream) (SKIPPED) | Valid JSON; xfail if BUG-3 wrap |

## 10 usage_field — usage field semantics / arithmetic / cache

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 10_01 | `test_10_01_response_field_completeness` | Top-level response field completeness | id/model/created/object/choices/usage all present |
| 10_02 | `test_10_02_usage_token_math` | usage arithmetic | total == prompt + completion; cached <= prompt |
| 10_03 | `test_10_03_usage_field_types` | usage three field types | int and >= 0 |
| 10_04 | `test_10_04_cached_tokens_presence` | cached_tokens hard presence | Same prompt twice; second cached > 0 |
| 10_05 | `test_10_05_usage_arithmetic_tool_call` | usage arithmetic under tool_call | total == prompt + completion |
| 10_06 | `test_10_06_length_truncation_completion_equals_limit` | finish_reason=length → completion == max | Strict equality |
| 10_07 | `test_10_07_stream_prompt_tokens_aggregated` | stream vs non-stream prompt_tokens consistent | Equal pt + stream arithmetic holds |
| 10_08 | `test_10_08_usage_fields_populated` | All three usage fields > 0 | prompt/completion/total all positive |

## 11 role_root — role=root protocol acceptance & identity adherence

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 11_01 | `test_11_01_role_root_accepted` | API accepts role=root | 200 + non-empty response |
| 11_02 | `test_11_02_root_overrides_system` | root + system conflict, `thinking=adaptive` + `reasoning_split` | Claims MiniMax-M3-taoxi (full-string strict match) |
| 11_03 | `test_11_03_only_system_identity` | system-only identity, `thinking=adaptive` | Claims MiniMax-M3-taoxi (full-string strict match) |
| 11_04 | `test_11_04_only_root_identity` | root-only identity, `thinking=adaptive` | Claims MiniMax-M3-taoxi (full-string strict match) |

## 12 text_semantic — Text semantic adherence

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 12_01 | `test_12_01_factual_qa_consistency` | Factual QA: capital of France | Response contains "paris" |
| 12_02 | `test_12_02_chinese_text_non_stream` | Chinese text generation (non-stream) | Response contains CJK chars |
| 12_03 | `test_12_03_chinese_text_stream` | Chinese text generation (stream) | Response contains CJK chars |
| 12_04 | `test_12_04_code_generation` | Python fibonacci function | Response contains "def " and "fibonacci" |
| 12_05 | `test_12_05_system_prompt_compliance` | Pirate system prompt | Response contains "arrr" |
| 12_06 | `test_12_06_long_form_output` | max_tokens=4096 photosynthesis explanation | content length > 500 |

## 13 tool_call_basic — Tool call basics

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 13_01 | `test_13_01_tool_call_non_stream` | Non-stream tool_call | get_weather + Beijing + finish_reason=tool_calls |
| 13_02 | `test_13_02_tool_call_stream` | Stream tool_call | Stream rebuild + last chunk finish_reason=tool_calls |
| 13_03 | `test_13_03_complex_agent_6tools` | Pick get_weather from 6-tool pool | Model selects correct tool |
| 13_04 | `test_13_04_param_type_coverage` | 6 parameter types | Valid JSON + schema compliant + str_param='hello' |
| 13_05 | `test_13_05_tool_without_parameters` | function.parameters omitted | Triggers if accepted; xfail if rejected |
| 13_06 | `test_13_06_tool_without_description` | function.description omitted | Model still triggers get_weather |
| 13_07 | `test_13_07_stream_multi_tool_call` | Stream multi tool_call rebuild | Beijing + Shanghai both fire + unique ids |
| 13_08 | `test_13_08_tool_choice_values` | tool_choice none/required/auto | none no fire; required/auto fire |
| 13_09 | `test_13_09_tool_stream_auto` | tool_choice=auto + stream | Stream contains tool_call chunks |
| 13_10 | `test_13_10_tool_structure` | tool_call return structure | get_weather + Beijing + schema required fields present |
| 13_11 | `test_13_11_stream_tool_rebuild` | Stream tool_call delta rebuild | Rebuilt contains get_weather + Beijing |
| 13_12 | `test_13_12_tool_name_mismatch_prompt` | Few-shot priming: prior turn assistant already tool_called get_weather/Beijing with a successful tool result; current user asks Shanghai; `tools` only declares `read_file` | Model should follow the pattern and emit tool_call invoking get_weather + location≈Shanghai + finish_reason=tool_calls |
| 13_13 | `test_13_13_undefined_tool_retry_after_error` | Streaming + adaptive thinking, few-shot priming: prior assistant tool_called `list_skills`, tool result says "unavailable, retry later"; current user system-reminder says cooldown is over, retry; the request declares NO `tools`, `list_skills` is only established by the in-context history | Model should follow the pattern and re-emit tool_call invoking `list_skills` + finish_reason=tool_calls (validates provider does not require a declared tool inventory to emit a tool_call, and does not rewrite/drop the tool name; schema not validated since no tool is declared) |

## 14 tool_call_schema — Tool call advanced schema validation

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 14_01 | `test_14_01_multi_distinct_tools_parallel` | Distinct tools in parallel | get_weather + get_current_time both fire |
| 14_02 | `test_14_02_enum_constraint` | enum constraint validation | unit == "fahrenheit" |
| 14_03 | `test_14_03_numeric_range` | Numeric range [1, 14] | days ∈ [1, 7] |
| 14_04 | `test_14_04_multi_required_fields` | Multiple required fields | from_city/to_city/date filled + date prefix correct |
| 14_05 | `test_14_05_nested_object_array` | Nested array-of-objects | guests=[{Alice 30}, {Bob 25}] |
| 14_06 | `test_14_06_nested_schema_4_levels` | 4-level deep nested schema | nested_tool fires + valid JSON |

## 15 tool_call_combo — Tool call combined with other features

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 15_01 | `test_15_01_thinking_tool_call_multiturn` | thinking + tool + multi-turn | Second turn Shanghai triggers get_weather again |
| 15_02 | `test_15_02_response_format_with_tool_choice` | tools + tool_choice coexist (response_format removed — M3 not yet supported) | Path A calls tool / Path B JSON contains Beijing |
| 15_03 | `test_15_03_5_parallel_tool_calls` | 5 parallel tool_calls | At least 1 call + all params non-empty |
| 15_04 | `test_15_04_extreme_agent_thinking_fc` | Extreme agent: thinking+FC+4 rounds | HTTP 200 |
| 15_05 | `test_15_05_system_thinking_tools_combo` | system + thinking + tools combo | get_weather + Tokyo |
| 15_06 | `test_15_06_tool_roundtrip` | Full tool roundtrip | With tool result, user follow-up answered directly |

## 16 tool_call_edge — Tool call boundary / exception handling

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 16_01 | `test_16_01_tool_result_content_object_duplicate` | tool_result.content=object (legacy) | HTTP 400 |
| 16_02 | `test_16_02_tool_result_empty_string` | tool result = '' (empty string) | 200 or 400 (BUG) |
| 16_03 | `test_16_03_tool_result_null` | tool result = null | 200 or 400 |
| 16_04 | `test_16_04_tool_result_no_content` | tool message without content field | 200 or 400 |
| 16_05 | `test_16_05_tool_result_special_chars` | tool result with JSON+HTML+emoji | HTTP 200 |
| 16_06 | `test_16_06_long_tool_result_50k` | 50K char tool result | HTTP 200 |
| 16_07 | `test_16_07_tool_result_object` | tool result = object | HTTP 400 |
| 16_08 | `test_16_08_tool_call_id_mismatch` | tool_call_id mismatch | HTTP 400 |
| 16_09 | `test_16_09_partial_tool_call_reply` | Reply to only some tool_calls | HTTP 400 |
| 16_10 | `test_16_10_30_tool_definitions` | 30 tool definitions | HTTP 200 + if triggered, args valid JSON |
| 16_11 | `test_16_11_tool_name_special_chars` | tool name with - and . (my-tool.v2) | Model calls correctly |
| 16_12 | `test_16_12_invalid_json_arguments` | tool_calls.arguments invalid JSON | HTTP 400 |
| 16_13 | `test_16_13_long_arguments_10k` | 10K char arguments | HTTP 200 |
| 16_14 | `test_16_14_tool_choice_nonexistent_tool` | tool_choice specifies nonexistent tool | 200 or 400; model must not invent call |

## 17 param_stress — Parameter stress (long conversation / long system)

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 17_01 | `test_17_01_long_conversation_20_rounds` | 20 rounds / 40 messages | HTTP 200 |
| 17_02 | `test_17_02_long_system_10k` | ~10K tokens long system | HTTP 200 |
| 17_03 | `test_17_03_long_input_512k` | Synthetic system, ctx_tokens ∈ {512000, 524288} (covers both decimal 512k and binary 512×1024 readings), max_tokens=16 | HTTP 200 (provider must honor advertised 512k window) |
| 17_04 | `test_17_04_real_text_512k_xiyouji` | Full 西遊記 (~553k tokens, exceeds 512k boundary) as system, ask for protagonist name; max_tokens=4096 | HTTP 200 ≤ status < 500 (no 5xx); **only when 200**, content/reasoning must contain a canonical protagonist name (孙悟空 / 唐僧 / 三藏 / 玄奘 / etc.) |
| 17_05 | `test_17_05_xiyouji_below_524288_tokens` | First 624,000 chars of 西遊記 (≈523.5K tokens, leaving room for a 512-token completion budget) as system, ask for protagonist name; max_tokens=512 | Strict HTTP 200 + canonical protagonist name match |
| 17_06 | `test_17_06_real_text_1m_xiyouji` | Journey-to-the-West text around 1.1M tokens, above the 1M boundary; thinking disabled, max_tokens=512 | HTTP 200 or explicit 4xx, never 5xx; on 200, canonical protagonist hit |
| 17_07 | `test_17_07_xiyouji_below_1048576_tokens` | First 1,220,000 chars (officially measured at about 1.02M prompt tokens, below 1,048,576); thinking disabled, max_tokens=512 | Strict HTTP 200 + canonical protagonist hit |

## 18 reasoning_split — reasoning_split extension field

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 18_01 | `test_18_01_reasoning_split_text` | reasoning_split=true + text | 200 or 400 (BUG-13) |

## 19 finish_reason — finish_reason coverage

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 19_01 | `test_19_01_finish_reason_tool_calls` | Tool-triggered scenario | finish_reason ∈ {tool_calls, stop} + tool actually called |
| 19_02 | `test_19_02_finish_reason_length` | max_tokens=10 forced truncation | finish_reason ∈ {length, stop} |

## 20 error_codes — Error codes (text-only)

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 20_01 | `test_20_01_empty_messages` | Empty messages array | HTTP 400 |
| 20_02 | `test_20_02_invalid_model` | Invalid model name | 400 or 404 |
| 20_03 | `test_20_03_temperature_out_of_range` | temperature out of range (5.0) | HTTP 400 |
| 20_04 | `test_20_04_top_p_out_of_range` | top_p out of range (>1 / <0) | HTTP 400 |
| 20_05 | `test_20_05_no_authorization` | No Authorization header | HTTP 401 |
| 20_06 | `test_20_06_invalid_role` | Invalid role | HTTP 400 |
| 20_07 | `test_20_07_invalid_api_key` | Invalid API key | HTTP 401 |
| 20_08 | `test_20_08_content_moderation` | Content moderation: harmful request | 400 (filtered) or 200 (refused) |

---

## M3.1-Flash tool-call contract cases

> Corresponds to: `m3_format_check/m3_1_flash_text_test.py` (module 24 is `TestToolContract` in that file). These cases are not in `m3_text_tests.py` and are not included in the counts at the top of this document.
> `TC-xxx` ids refer to the OpenAI Chat Completions verification design; there are 60 of them.

Verdict rules:

- The new shared checks only treat the HTTP status and a parsable response as hard conditions. Shared format problems, such as a missing `message.content` key or extra keys on a `tool_calls` item, are recorded and do not fail the case. Set `M3_FORMAT_ISSUES` to write them to a jsonl file; they are also raised as pytest warnings.
- The new shared checks skip the test on a 401, 403, 429 or 5xx response, so it neither passes nor fails.
- Non-strict cases do not check `arguments` values.

07_03, 14_01, 14_10, 15_01, 15_04, 15_06 and 16_05 also run the shared reply checks on top of their existing assertions.

| Case ID | Function Name | TC | Scene Description | Key Assertions |
|:---:|:---|:---|:---|:---|
| 01_01 | `test_01_01_text_non_stream` | TC-040 | No tools declared | finish_reason=stop, no tool_calls, non-empty content |
| 07_03b | `test_07_03b_echo_history_content_omitted` | TC-192 | History assistant with tool_calls and no content key, tool_choice=none | Accepted with a text answer and no new tool call |
| 13_01b | `test_13_01b_tool_choice_omitted_auto` | TC-036 | echo + get_time declared, tool_choice omitted | Behaves as auto: a text answer, or calls to declared names only |
| 13_06b | `test_13_06b_echo_without_description_required` | TC-002 | echo without description, tool_choice=required | finish_reason=tool_calls, every call is echo, arguments is a string |
| 13_07 | `test_13_07_stream_multi_tool_call` | TC-154 | Streamed calls to the same function | Each call reassembled by index satisfies the schema; arguments do not bleed across calls |
| 13_07b | `test_13_07b_stream_multi_distinct_tools` | TC-070 | Stream, echo + get_time, required, parallel=true | Distinct ids, declared names, arguments valid per schema; a single call is allowed |
| 13_07c | `test_13_07c_same_name_parallel_non_stream` | TC-152 | Non-stream, one get_weather tool, required, parallel=true | Every call valid per schema; when two fire, cities differ and cover Beijing and Shanghai |
| 14_01b | `test_14_01b_multi_tools_required_parallel_fields` | TC-151 | Non-stream, echo + get_time, required, parallel=true | Complete fields, arguments valid per schema, distinct ids |
| 14_07b | `test_14_07b_non_strict_property_oneof_accepted` | TC-135 | strict=false with a property-level oneOf | Accepted; arguments is a JSON object, values not checked |
| 14_11 | `test_14_11_strict_2d_bool_array` | TC-118 | Strict 2-D boolean array (non-stream/stream) | Exactly one call, m stays 2-D with real booleans |
| 14_12 | `test_14_12_strict_tool_schema` | TC-101..115, TC-117 | Strict schemas: anyOf, enum, nullable, nesting, $ref, length, format and others (parametrized by TC) | Exactly one call, arguments fully valid; prompt-fixed values are checked where set |
| 14_12b | `test_14_12b_non_strict_omit_required_and_additional` | TC-138 | strict=false without required / additionalProperties | Accepted; arguments is a JSON object, values not checked |
| 14_14 | `test_14_14_custom_tool_formats` | TC-033, TC-034 | Custom tool grammar missing definition / with an invalid syntax | HTTP 400 |
| 14_15 | `test_14_15_tool_declaration_invalid` | TC-004, TC-006 | Missing function container / wrong name type | HTTP 400 |
| 14_16 | `test_14_16_schema_capability_negative` | TC-125, TC-136 | Strict patternProperties next to properties / strict=false allOf | Accepted; strict arguments valid per schema, non-strict only need to be a JSON object |
| 15_01b | `test_15_01b_history_content_null` | TC-191 | History assistant with content=null, tool_choice=none | Accepted with a text answer |
| 15_04b | `test_15_04b_mixed_tool_and_plain_turns` | TC-204 | History mixing tool and plain turns, tool_choice=none | Accepted with a text answer and no new tool call |
| 15_06b | `test_15_06b_real_call_string_roundtrip` | TC-059 | String result replayed with the real id and arguments from turn 1 | Turn 2 answers with text and no new tool call |
| 16_02 / 16_02b | `test_16_02_tool_result_empty_string` / `test_16_02b_real_loop_tool_content_variants` | TC-060 | tool.content is an empty string or a text array | Must be accepted with a well-formed reply (in this file 16_02 no longer accepts 400) |
| 16_05b | `test_16_05b_tool_result_json_string` | TC-195 | tool.content is a JSON string, tool_choice=none | Accepted with a text answer |
| 24_013 | `test_24_013_strict_true` | TC-013 | strict=true | Exactly one call; arguments carry only text |
| 24_014 | `test_24_014_strict_false_null_omitted` | TC-014, TC-015, TC-016 | strict is false / null / omitted | Accepted; every call is echo, arguments is a string |
| 24_023 | `test_24_023_strict_value_constraints` | TC-023, TC-024, TC-026 | Strict pattern / email / array length | Arguments satisfy the constraint keywords |
| 24_161 | `test_24_161_function_name_charset` | TC-161 | Function name using a-z, A-Z, 0-9, _ and - | Accepted |
| 24_165 | `test_24_165_long_description` | TC-165 | Very long description | Accepted |
| 24_166 | `test_24_166_description_not_string` | TC-166 | description=123 | HTTP 400 |
| 24_170 | `test_24_170_tools_element_not_object` | TC-170 | tools element is not an object | HTTP 400 |
| 24_171 | `test_24_171_duplicate_function_names` | TC-171 | Two declarations with the same name | Accepted |
| 24_180 | `test_24_180_128_tools_boundary` | TC-180 | 128 function declarations, tool_choice=none | Accepted with a text answer |
| 24_048 | `test_24_048_tool_choice_null` | TC-048 | tool_choice=null | Treated as omitted: a text answer, or calls to the declared echo |
| 24_143 | `test_24_143_tool_call_id_unique_across_requests` | TC-143 | Two independent requests naming echo | Call ids differ; format not checked |
| 24_144 | `test_24_144_no_arg_function_arguments_braces` | TC-144 | No-argument get_time, tool_choice=required | arguments is the JSON string of an empty object, never "" or null |
| 24_062 | `test_24_062_tool_content_array_variants` | TC-062, TC-063 | Real loop with tool.content as an empty array / an image part | Accepted with a text answer |
| 24_094 | `test_24_094_stream_answer_after_tool_result` | TC-094 | Streamed answer after a tool result, tool_choice=none | finish_reason=stop, no tool_calls deltas, non-empty content |
| 24_193 | `test_24_193_assistant_tool_call_content_variants` | TC-193, TC-194 | History assistant with tool_calls and content "" / text (non-stream/stream) | Accepted with a text answer |
| 24_197 | `test_24_197_tool_message_before_assistant_call` | TC-197 | Tool message with no preceding assistant call | HTTP 400 |

---

## Appendix: 156 items after parametrize expansion

Functions decorated with `@pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])` expand to 2 items each; the two `max_tokens` parametrized cases each expand to 2 items.

| Expansion Factor | Cases Involved |
|:---|:---|
| `stream ∈ {non_stream, stream}` | 07_01 / 07_02 / 07_03 / 07_04 / 07_05 / 07_06 / 09_03 / 11_01 / 11_02 / 11_03 / 11_04 / 14_06 / 15_01 / 15_02 / 15_03 / 15_04 / 15_05 / 16_02 / 16_03 / 16_05 / 16_06 / 16_08 / 16_09 / 16_10 / 16_11 / 16_12 / 16_13 / 17_01 / 17_02 / 17_04 / 17_05 / 17_06 / 17_07 / 18_01 |
| `ctx_tokens ∈ {512000, 524288} × stream ∈ {non_stream, stream}` | 17_03 |
| `mt ∈ {512000, 524288}` | 06_09 |
| `mt ∈ {524289, 1000000}` | 06_10 |

Total items = 117 functions - 34 two-value `stream` functions - 1 `ctx_tokens × stream` function - 2 two-value `mt` functions + 34×2 + 1×4 + 2×2 = **156**.

## M3.1-Flash Response and Stream Contract Additions

> Corresponds to: `m3_format_check/m3_1_flash_text_test.py`. These cases apply to the M3.1-Flash suite only. `m3_text_tests.py`, described by the tables above, is unchanged; for cases with the same ID in the M3.1-Flash suite, this section applies.

### Strengthened cases

| Case ID | Function | Scenario | Assertion |
|:---:|:---|:---|:---|
| 01_01 | `test_01_01_text_non_stream` | Basic non-stream text conversation | `assert_chat_completion_ok` (JSON `Content-Type`, one ChatCompletion object) + `finish_reason=stop` + string `content` + valid usage arithmetic + `prompt_tokens_details` absent or an object |
| 02_01 | `test_02_01_text_stream` | Text streaming response | `assert_sse_stream_ok` (defined in `m3_stream_cases_en.md`) |
| 02_03 | `test_02_03_sse_done_marker` | Reads raw SSE lines | The last data line is `[DONE]`, followed by a blank line, with no `event: done`; a missing marker fails instead of xfail |
| 02_04 | `test_02_04_stream_chunk_fields` | `include_usage=true`; checks every chunk including the usage chunk | `id` / `choices` / `object=chat.completion.chunk` / `created` / `model` have the right types, and `id` and `created` stay constant within a stream |
| 10_04 | `test_10_04_cached_tokens_presence` | Long prompt with a unique prefix, sent twice | First `cached_tokens` is at most half of `prompt_tokens`; second request hits the cache |
| 10_05 | `test_10_05_usage_arithmetic_tool_call` | usage under tool_call | Existing arithmetic check + `completion_tokens > 0` |
| 10_07 | `test_10_07_stream_prompt_tokens_aggregated` | stream vs non-stream `prompt_tokens` | Strictly equal + `assert_sse_stream_ok` + exactly one usage object in the stream |
| 13_02 | `test_13_02_tool_call_stream` | Stream tool_call with `tool_choice="required"` | Existing checks + `assert_sse_stream_ok` |

### New cases

| Case ID | Function | Scenario | Assertion |
|:---:|:---|:---|:---|
| 10_11 | `test_10_11_stream_truncated_usage_within_budget` | Stream, long essay cut by `max_completion_tokens=20` | `assert_sse_stream_ok` + exactly one usage object + `completion_tokens <= 20` |
| 10_12 | `test_10_12_stream_small_budget_finish_length` | Stream with `max_completion_tokens=1` | `assert_sse_stream_ok` + `finish_reason=length`; visible text is not required; skip on `content_filter` |
| 10_14 | `test_10_14_prompt_tokens_accounting[input_length\|system_and_history\|tool_result]` | Extends input text, system and history turns, or tool results | `prompt_tokens` grows by more than the threshold (100 / 50 / 100); exact values are not checked |
| 10_15 | `test_10_15_cache_hit_keeps_prompt_tokens` | Long prompt with a unique prefix, sent twice | `prompt_tokens` differ by at most the larger of 8 or 1%; cached tokens are not deducted |
| 10_16 | `test_10_16_reasoning_tokens_within_completion` | Non-stream with `reasoning_effort="high"` | `reasoning_tokens` stays within `completion_tokens` and is not counted twice in `total_tokens`; skip when the field is not returned |
| 19_02 | `test_19_02_finish_reason_length` | Non-stream with `max_completion_tokens=20` | Valid usage arithmetic; `completion_tokens <= 20` when truncated; skip when not truncated |
