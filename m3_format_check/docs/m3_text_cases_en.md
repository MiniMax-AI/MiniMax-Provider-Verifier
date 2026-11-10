# M3 Text Modality Format Validation Case List

> Corresponds to: `data/m3_api_test/m3_text_tests.py`
> Rows whose scenario starts with `M3.1-Flash:` correspond to `m3_format_check/m3_1_flash_text_test.py`; all other rows correspond to the file above.
> The strict assertions used by `M3.1-Flash:` rows (`helpers.py`) check every rule on one response and report all violations together:
> - `assert_chat_completion_strict`: one JSON object (not SSE) with `id` / `object=chat.completion` / `created` / `model`; choice `index` values are distinct integers; the assistant message `content` is a string or null (an omitted `content` key is read as null) and `refusal` is a string or null; a known `finish_reason`; `tool_calls` is absent / null or a non-empty list whose items have exactly `id` / `type=function` / `function{name, arguments (string)}` with distinct ids; usage follows the same rules as the stream helper (see `m3_stream_cases_en.md`).
> - `assert_error_response_strict`: HTTP 400 with a JSON `Content-Type` and an `error` object (`message` a non-empty string, `type` a string or null, `code` a string, int or null) and no `choices`.
> - The stream counterpart `assert_sse_stream_strict` is described in `m3_stream_cases_en.md`.
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
| 01_01 | `test_01_01_text_non_stream` | M3.1-Flash: Basic non-stream text conversation without tools | `assert_chat_completion_strict` + `finish_reason=stop` + non-empty content + no tool call + `prompt_tokens_details` absent or an object |
| 01_02 | `test_01_02_content_string` | `user.content` as plain string | HTTP 200 |
| 01_03 | `test_01_03_content_array` | `user.content` as parts array `[{type:text,text:...}]` | HTTP 200 |

## 02 sse_stream — SSE streaming protocol fields

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 02_01 | `test_02_01_text_stream` | Text streaming response | Stream can rebuild content correctly |
| 02_02 | `test_02_02_stream_usage` | Last usage chunk in stream | total == prompt + completion + stream finishes properly |
| 02_03 | `test_02_03_sse_done_marker` | SSE `[DONE]` end marker | xfail if missing (known BUG) |
| 02_03 | `test_02_03_sse_done_marker` | M3.1-Flash: Reads raw SSE lines | The last data line is `[DONE]`, followed by a blank line, with no `event: done`; a missing marker fails instead of xfail |
| 02_04 | `test_02_04_stream_chunk_fields` | Stream chunk required fields | id / choices / object all present |
| 02_04 | `test_02_04_stream_chunk_fields` | M3.1-Flash: `include_usage=true`; checks every chunk including the usage chunk | `id` / `choices` / `object=chat.completion.chunk` / `created` / `model` have the right types, and `id` and `created` stay constant within a stream |
| 02_05 | `test_02_05_text_include_usage` | `stream_options.include_usage=true` (text) | Stream should return usage chunk |
| 02_06 | — | Removed (formerly `test_02_06_stream_usage_only_in_last_chunk`) | Exact duplicate of `m3_stream_tests.py::TestSSEStream::test_02_06_stream_usage_only_in_last_chunk`; de-duplicated, the ID stays retired |
| 02_07 | `test_02_07_stream_no_utf8_replacement_char_in_emoji` | Emoji-dense streaming request run 20 times | No `U+FFFD` (`�`) replacement char in any `delta.content`; guards against a 4-byte emoji being truncated mid-UTF-8-frame |

## 03 multiturn — Multi-turn conversation

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 03_01 | `test_03_01_multiturn` | Two-turn: introduce as Alice then ask name | Response should contain "alice" |
| 03_02 | `test_03_02_multiturn_5_rounds` | 5-round arithmetic chat: x=10, y=15, z=25 | Response should contain "50" (x+y+z) |
| 03_04 | `test_03_04_history_message_forms[participant_names\|assistant_text_parts\|assistant_refusal_string\|assistant_refusal_null]` | M3.1-Flash: History message forms: per-message `name`, assistant text-part array, `refusal` as string / null | `assert_oai_success` |

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
| 05_01 | `test_05_01_temperature_top_p_values[...]` | M3.1-Flash: `top_p` 0.1 / 1 / null (temperature is not covered: accepted but not applied by the reference endpoint) | `assert_oai_success` |
| 05_02 | `test_05_02_top_p` | top_p boundaries [0.1, 0.5, 0.95] | All values return 200 |
| 05_03 | `test_05_03_seed_parameter` | seed=42 + temperature=0 | API accepts for deterministic output |
| 05_03 | `test_05_03_penalty_and_logit_bias[...]` | M3.1-Flash: presence / frequency penalty at -2 / 0 / 2, each with `max_completion_tokens=64` | `assert_oai_success`; `finish_reason=length` is allowed |

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
| 06_12 | `test_06_12_no_output_limit` | M3.1-Flash: Sent verbatim with no output budget field | `assert_oai_success` |
| 06_14 | `test_06_14_legacy_max_tokens` | M3.1-Flash: Legacy `max_tokens=64` | `assert_oai_success` |
| 06_15 | `test_06_15_output_budget_null[max_completion_tokens\|max_tokens]` | M3.1-Flash: `max_completion_tokens` / `max_tokens` explicitly null | `assert_oai_success` |

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
| 07_10 | `test_07_10_invalid_message_structure[role_missing\|role_null]` | M3.1-Flash: Message without `role` / `role=null` | HTTP 400 |
| 07_12 | `test_07_12_user_content_forms[multiple_text_parts\|cjk_emoji_escapes\|empty_text_part]` | M3.1-Flash: user content with several text parts, a string with CJK / emoji / escapes, an empty text part next to a non-empty one | `assert_oai_success` |

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
| 09_01 | `test_09_01_text_and_json_object[type=text]` | M3.1-Flash: `response_format` type=text (json_object / json_schema are not covered: accepted but not applied by the reference endpoint) | `assert_oai_success` |
| 09_02 | `test_09_02_json_object_stream` | json_object stream + thinking=disabled (SKIPPED) | Stream returns properly |
| 09_03 | `test_09_03_json_object_format` | json_object generic (non-stream/stream) (SKIPPED) | Valid JSON; xfail if BUG-3 wrap |

## 10 usage_field — usage field semantics / arithmetic / cache

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 10_01 | `test_10_01_response_field_completeness` | Top-level response field completeness | id/model/created/object/choices/usage all present |
| 10_02 | `test_10_02_usage_token_math` | usage arithmetic | total == prompt + completion; cached <= prompt |
| 10_03 | `test_10_03_usage_field_types` | usage three field types | int and >= 0 |
| 10_04 | `test_10_04_cached_tokens_presence` | cached_tokens hard presence | Same prompt twice; second cached > 0 |
| 10_04 | `test_10_04_cached_tokens_presence` | M3.1-Flash: Long prompt with a unique prefix, sent twice | First `cached_tokens` is at most half of `prompt_tokens`; second request hits the cache |
| 10_05 | `test_10_05_usage_arithmetic_tool_call` | usage arithmetic under tool_call | total == prompt + completion |
| 10_05 | `test_10_05_usage_arithmetic_tool_call` | M3.1-Flash: usage under tool_call | Existing arithmetic check + `completion_tokens > 0` |
| 10_06 | `test_10_06_length_truncation_completion_equals_limit` | finish_reason=length → completion == max | Strict equality |
| 10_07 | `test_10_07_stream_prompt_tokens_aggregated` | stream vs non-stream prompt_tokens consistent | Equal pt + stream arithmetic holds |
| 10_07 | `test_10_07_stream_prompt_tokens_aggregated` | M3.1-Flash: stream vs non-stream `prompt_tokens` | Strictly equal + stream usage arithmetic holds |
| 10_08 | `test_10_08_usage_fields_populated` | All three usage fields > 0 | prompt/completion/total all positive |
| 10_11 | `test_10_11_stream_truncated_usage_within_budget` | M3.1-Flash: Stream, long essay cut by `max_completion_tokens=20` | usage present in the stream + `completion_tokens <= 20` |
| 10_14 | `test_10_14_prompt_tokens_accounting[input_length\|system_and_history\|tool_result]` | M3.1-Flash: Extends input text, system and history turns, or tool results | `prompt_tokens` grows by more than the threshold (100 / 50 / 100); exact values are not checked |
| 10_15 | `test_10_15_cache_hit_keeps_prompt_tokens` | M3.1-Flash: Long prompt with a unique prefix, sent twice | `prompt_tokens` differ by at most the larger of 8 or 1%; cached tokens are not deducted |
| 10_16 | `test_10_16_reasoning_tokens_within_completion` | M3.1-Flash: Non-stream with `reasoning_effort="high"` | `reasoning_tokens` stays within `completion_tokens` and is not counted twice in `total_tokens`; skip when the field is not returned |

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
| 13_02 | `test_13_02_tool_call_stream` | M3.1-Flash: Stream tool_call requested by the prompt (no `tool_choice`) | Existing checks |
| 13_03 | `test_13_03_complex_agent_6tools` | Pick get_weather from 6-tool pool | Model selects correct tool |
| 13_04 | `test_13_04_param_type_coverage` | 6 parameter types | Valid JSON + schema compliant + str_param='hello' |
| 13_05 | `test_13_05_tool_without_parameters` | function.parameters omitted | Triggers if accepted; xfail if rejected |
| 13_06 | `test_13_06_tool_without_description` | function.description omitted | Model still triggers get_weather |
| 13_07 | `test_13_07_stream_multi_tool_call` | Stream multi tool_call rebuild | Beijing + Shanghai both fire + unique ids |
| 13_07 | `test_13_07_stream_multi_tool_call` | M3.1-Flash: Same as above | Existing checks + each call's arguments match the schema, ids are unique, and the two locations differ (no argument bleed) |
| 13_08 | `test_13_08_tool_choice_values` | tool_choice none/required/auto | none no fire; required/auto fire |
| 13_09 | `test_13_09_tool_stream_auto` | tool_choice=auto + stream | Stream contains tool_call chunks |
| 13_10 | `test_13_10_tool_structure` | tool_call return structure | get_weather + Beijing + schema required fields present |
| 13_10 | `test_13_10_tool_structure` | M3.1-Flash: Same as above | Existing checks + `assert_chat_completion_strict` (`finish_reason=tool_calls`, complete `tool_calls` items without extra keys apart from a non-stream `index`) |
| 13_11 | `test_13_11_stream_tool_rebuild` | Stream tool_call delta rebuild | Rebuilt contains get_weather + Beijing |
| 13_12 | `test_13_12_tool_name_mismatch_prompt` | Few-shot priming: prior turn assistant already tool_called get_weather/Beijing with a successful tool result; current user asks Shanghai; `tools` only declares `read_file` | Model should follow the pattern and emit tool_call invoking get_weather + location≈Shanghai + finish_reason=tool_calls |
| 13_13 | `test_13_13_undefined_tool_retry_after_error` | Streaming + adaptive thinking, few-shot priming: prior assistant tool_called `list_skills`, tool result says "unavailable, retry later"; current user system-reminder says cooldown is over, retry; the request declares NO `tools`, `list_skills` is only established by the in-context history | Model should follow the pattern and re-emit tool_call invoking `list_skills` + finish_reason=tool_calls (validates provider does not require a declared tool inventory to emit a tool_call, and does not rewrite/drop the tool name; schema not validated since no tool is declared) |
| 13_22 | `test_13_22_echo_without_description_required` | M3.1-Flash: echo without description, call requested by the prompt | `finish_reason=tool_calls`; every call is echo with string arguments |
| 13_23 | `test_13_23_function_name_charset` | M3.1-Flash: Function name using a-z, A-Z, 0-9, `_` and `-` | HTTP 200; any call uses a declared name with JSON-object arguments |
| 13_24 | `test_13_24_long_description` | M3.1-Flash: Very long description | HTTP 200; the called name is recorded only (the reference endpoint also calls undeclared names with a very long description) |
| 13_25 | `test_13_25_duplicate_function_names` | M3.1-Flash: Two declarations with the same name | HTTP 200; any call uses a declared name with JSON-object arguments |
| 13_26 | `test_13_26_128_tools_boundary` | M3.1-Flash: 128 function declarations, `tool_choice=none` | HTTP 200 with a text answer and no tool call |
| 13_27 | `test_13_27_tool_choice_omitted_auto` | M3.1-Flash: echo + get_time declared, `tool_choice` omitted | Behaves as auto: a text answer, or calls to declared functions only |
| 13_28 | `test_13_28_tool_choice_null` | M3.1-Flash: `tool_choice=null` | Treated as omitted: a text answer, or calls to the declared echo |
| 13_31 | `test_13_31_tool_call_id_unique_across_requests` | M3.1-Flash: Two independent requests asking for echo in the prompt | Call ids do not repeat across requests; the id format is not checked |
| 13_32 | `test_13_32_no_arg_function_arguments_braces` | M3.1-Flash: No-parameter get_time, call requested by the prompt | arguments is the JSON string of an empty object `{}`, never an empty string or null |
| 13_33 | `test_13_33_stream_answer_after_tool_result` | M3.1-Flash: Streamed answer after a tool result, `tool_choice=none` | `finish_reason=stop`, no tool_calls deltas, non-empty content |

## 14 tool_call_schema — Tool call advanced schema validation

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 14_01 | `test_14_01_multi_distinct_tools_parallel` | Distinct tools in parallel | get_weather + get_current_time both fire |
| 14_02 | `test_14_02_enum_constraint` | enum constraint validation | unit == "fahrenheit" |
| 14_03 | `test_14_03_numeric_range` | Numeric range [1, 14] | days ∈ [1, 7] |
| 14_04 | `test_14_04_multi_required_fields` | Multiple required fields | from_city/to_city/date filled + date prefix correct |
| 14_05 | `test_14_05_nested_object_array` | Nested array-of-objects | guests=[{Alice 30}, {Bob 25}] |
| 14_06 | `test_14_06_nested_schema_4_levels` | 4-level deep nested schema | nested_tool fires + valid JSON |
| 14_12 | `test_14_12_complex_schema_keywords[...]` | M3.1-Flash: Complex schema keywords OpenAI supports (no strict): anyOf, enum, nullable, nesting, `$ref`, recursion, annotations, length, format, empty properties, non-ASCII property names, escaped values; call requested by the prompt | At least one call to the declared function with JSON-object arguments; schema conformance and prompt-fixed values are recorded, not asserted |
| 14_15 | `test_14_15_tool_declaration_invalid[function_container_missing\|name_wrong_type]` | M3.1-Flash: function container missing / name of the wrong type | HTTP 400 |
| 14_16 | `test_14_16_schema_capability_negative[allof]` | M3.1-Flash: Property-level allOf | Accepted (call requested by the prompt); arguments are a JSON object, values not checked |
| 14_18 | `test_14_18_non_strict_property_oneof_accepted` | M3.1-Flash: Property-level oneOf | Accepted; arguments are a JSON object, values not checked |
| 14_20 | `test_14_20_non_strict_omit_required_and_additional` | M3.1-Flash: required and additionalProperties omitted | Accepted; arguments are a JSON object, values not checked |
| 14_24 | `test_14_24_description_not_string` | M3.1-Flash: description=123 | HTTP 400 |
| 14_25 | `test_14_25_tools_element_not_object` | M3.1-Flash: A tools element that is not an object | HTTP 400 |

## 15 tool_call_combo — Tool call combined with other features

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 15_01 | `test_15_01_thinking_tool_call_multiturn` | thinking + tool + multi-turn | Second turn Shanghai triggers get_weather again |
| 15_02 | `test_15_02_response_format_with_tool_choice` | tools + tool_choice coexist (response_format removed — M3 not yet supported) | Path A calls tool / Path B JSON contains Beijing |
| 15_03 | `test_15_03_5_parallel_tool_calls` | 5 parallel tool_calls | At least 1 call + all params non-empty |
| 15_04 | `test_15_04_extreme_agent_thinking_fc` | Extreme agent: thinking+FC+4 rounds | HTTP 200 |
| 15_05 | `test_15_05_system_thinking_tools_combo` | system + thinking + tools combo | get_weather + Tokyo |
| 15_06 | `test_15_06_tool_roundtrip` | Full tool roundtrip | With tool result, user follow-up answered directly |
| 15_09 | `test_15_09_history_content_null[non_stream\|stream]` | M3.1-Flash: History assistant with tool_calls and content=null, `tool_choice=none` | Accepted with a text answer |
| 15_10 | `test_15_10_mixed_tool_and_plain_turns[non_stream\|stream]` | M3.1-Flash: History mixing tool turns and plain turns, `tool_choice=none` | Accepted with a text answer and no new tool call |
| 15_11 | `test_15_11_real_call_string_roundtrip` | M3.1-Flash: Turn 1 asks for echo in the prompt; replay the real turn-1 id and arguments with a string tool result | Turn 2 answers with text and no new tool call |
| 15_12 | `test_15_12_echo_history_content_omitted[non_stream\|stream]` | M3.1-Flash: History assistant with tool_calls and no content key, `tool_choice=none` | Accepted with a text answer |
| 15_13 | `test_15_13_assistant_tool_call_content_variants[...]` | M3.1-Flash: History assistant with tool_calls and content "" or text (non-stream / stream) | Accepted with a text answer |

## 16 tool_call_edge — Tool call boundary / exception handling

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 16_01 | `test_16_01_tool_result_content_object_duplicate` | tool_result.content=object (legacy) | HTTP 400 |
| 16_02 | `test_16_02_tool_result_empty_string` | tool result = '' (empty string) | 200 or 400 (BUG) |
| 16_02 | `test_16_02_tool_result_empty_string[non_stream\|stream]` | M3.1-Flash: Same as above | Must return HTTP 200 (400 is no longer accepted in this file) |
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
| 16_16 | `test_16_16_real_loop_tool_content_variants[empty_string\|text_parts]` | M3.1-Flash: Real loop, tool.content "" or a text-parts array, `tool_choice=none` | Accepted with a text answer |
| 16_18 | `test_16_18_tool_content_array_variants[empty_array\|image_part]` | M3.1-Flash: Real loop, tool.content an empty array / an image part | Accepted with a text answer |
| 16_19 | `test_16_19_tool_result_json_string[non_stream\|stream]` | M3.1-Flash: tool.content is a JSON string, `tool_choice=none` | Accepted with a text answer |
| 16_20 | `test_16_20_tool_message_before_assistant_call` | M3.1-Flash: A tool message with no preceding assistant call | HTTP 400 |

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
| 17_07 | `test_17_07_long_text_needle` | M3.1-Flash: One long user message (~80k characters) | `assert_oai_success` |
| 17_08 | `test_17_08_long_history_needle` | M3.1-Flash: 51 user/assistant pairs + 1 user, 103 messages | 103 messages asserted before sending + `assert_oai_success` |

## 18 reasoning_split — reasoning_split extension field

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 18_01 | `test_18_01_reasoning_split_text` | reasoning_split=true + text | 200 or 400 (BUG-13) |

## 19 finish_reason — finish_reason coverage

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 19_01 | `test_19_01_finish_reason_tool_calls` | Tool-triggered scenario | finish_reason ∈ {tool_calls, stop} + tool actually called |
| 19_02 | `test_19_02_finish_reason_length` | max_tokens=10 forced truncation | finish_reason ∈ {length, stop} |
| 19_02 | `test_19_02_finish_reason_length` | M3.1-Flash: Non-stream with `max_completion_tokens=20` | Valid usage arithmetic; `completion_tokens <= 20` when truncated; skip when not truncated |

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
| 20_14 | `test_20_14_messages_wrong_type[messages=null\|message_is_number]` | M3.1-Flash: `messages=null` / a numeric element | HTTP 400 |
| 20_26 | `test_20_26_parameter_contract_negative[...]` | M3.1-Flash: `max_completion_tokens=8.5`, a non-string `stop` element, `n=1.5`, `reasoning_effort` as an array | `assert_error_response_strict`; must not be coerced or ignored |
| 20_28 | `test_20_28_model_wrong_type` | M3.1-Flash: `model` is an array | A 4xx rejection |

---

## 27 passthrough_params — user

> Applies to `m3_format_check/m3_1_flash_text_test.py` only.

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 27_03 | `test_27_03_user_identifier[string\|null]` | Legacy `user` as a string / null | `assert_oai_success` |

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
