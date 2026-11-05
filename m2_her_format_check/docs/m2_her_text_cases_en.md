# M2-Her Text and Role Format Check Cases

> File: [`m2_her_format_check/m2_her_text_tests.py`](../m2_her_text_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **17**; case functions: **89**; collected pytest items: **449**
> Expected values: set from what the live API returned on 2026-11-05; where the public docs disagree, the live API wins. See the [README](../README_en.md) for judging rules and expected randomness.

## Module overview

| Module | Name | Topic | Functions |
|:---:|:---|:---|:---:|
| 01 | basic_text | Basic text | 6 |
| 02 | system_persona | system persona | 5 |
| 03 | user_system | user_system user persona | 4 |
| 04 | group | group scene | 3 |
| 05 | sample_messages | Sample dialogues sample_message_* | 5 |
| 06 | names | name field | 4 |
| 07 | multiturn | Multi-turn conversation | 6 |
| 08 | sampling | Sampling parameters (temperature / top_p) | 5 |
| 09 | completion_limit | Output budget max_completion_tokens | 5 |
| 10 | response_usage | Response structure and usage | 7 |
| 11 | error_codes | Error handling | 9 |
| 12 | long_context | Long input and the 64K context | 4 |
| 13 | role_combo | Seven-role combinations | 5 |
| 16 | guide_alignment | Structures from the official guide | 4 |
| 17 | candidate_count | n candidates | 8 |
| 18 | request_metadata | metadata / user / mask_sensitive_info | 3 |
| 19 | language_consistency | Reply-language consistency | 6 |

---

## 01 basic_text — Basic text

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 01_01 | [`test_01_01_minimal_user_message`](../m2_her_text_tests.py#L85) | A single user message with no system, name or optional parameters, once streaming and once non-streaming. | HTTP 200 with base_resp 0 and one non-empty assistant reply; the SSE stream parses strictly with a single finish reason. | Default |
| 01_02 | [`test_01_02_system_user_chat`](../m2_her_text_tests.py#L89) | system sets a "friendly assistant", user says "你好" (hello). | A plain persona request is accepted with a valid, non-empty reply. | Default |
| 01_03 | [`test_01_03_chinese_text`](../m2_her_text_tests.py#L96) | Ask in Chinese for a short greeting (behavior evaluation). | The text contains Chinese characters and no U+FFFD replacement character. | --run-behavior; counted separately, not part of the format pass rate |
| 01_04 | [`test_01_04_english_text`](../m2_her_text_tests.py#L108) | Ask in English for a greeting in English only (behavior evaluation). | The text contains English words and no Chinese characters. | --run-behavior; counted separately, not part of the format pass rate |
| 01_05 | [`test_01_05_text_escaping_unicode`](../m2_her_text_tests.py#L119) | User content with double quotes, backslashes, newlines and emoji, asked to be echoed verbatim. | The request is accepted and the response decodes as strict UTF-8 / JSON (SSE); verbatim echo is not checked here (see 16_03). | Default |
| 01_06 | [`test_01_06_multilingual_input`](../m2_her_text_tests.py#L135) | A Chinese question containing a Japanese, Korean, Arabic, Russian or combining-accent greeting. | All Unicode inputs are accepted with a valid reply; no translation or extraction is required (see 16_02 for extraction). | Default |

## 02 system_persona — system persona

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 02_01 | [`test_02_01_system_identity`](../m2_her_text_tests.py#L147) | system sets identity AI_K72; user asks for the identity only. | The reply contains AI_K72, showing the system persona was read. | --run-behavior; counted separately, not part of the format pass rate |
| 02_02 | [`test_02_02_system_reply_prefix`](../m2_her_text_tests.py#L157) | system requires every reply to start with HER_REPLY:; user says "你好". | The reply starts with HER_REPLY:. | --run-behavior; counted separately, not part of the format pass rate |
| 02_03 | [`test_02_03_system_output_format`](../m2_her_text_tests.py#L168) | system asks to output only {"status":"ready","count":2}; no response_format is sent. | The text parses directly as that JSON object. This is a prompt-following goal and does not mean the API supports response_format. | --run-behavior; counted separately, not part of the format pass rate |
| 02_04 | [`test_02_04_system_identity_multiturn`](../m2_her_text_tests.py#L182) | After setting the identity, insert 4 unrelated turns, then ask for the identity. | The reply still contains AI_K72; the persona is not lost across turns. | --run-behavior; counted separately, not part of the format pass rate |
| 02_05 | [`test_02_05_system_identity_isolation`](../m2_her_text_tests.py#L194) | Two independent requests set the identity to AI_K72 and AI_B19 and ask the same question. | Each reply returns only its own identity, never the other request's ID. | --run-behavior; counted separately, not part of the format pass rate |

## 03 user_system — user_system user persona

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 03_01 | [`test_03_01_user_system_identity`](../m2_her_text_tests.py#L208) | Provide user ID USER_P38 only through user_system, then ask for the user ID. | The reply contains USER_P38, showing the user persona was read. | --run-behavior; counted separately, not part of the format pass rate |
| 03_02 | [`test_03_02_user_assistant_identity_separation`](../m2_her_text_tests.py#L219) | system gives the AI ID and user_system gives the user ID; ask for the AI identity and the user identity in two requests; compare no names with all named. | As observed live: with all named, asking about the AI returns AI_K72 and asking about the user also returns only replies containing AI_K72, never USER_P38. With names omitted both requests are rejected: non-streaming returns HTTP 200 + business code 2013 "invalid params, 400"; streaming returns a single SSE event with business code 1000 "unknown error, 999". | --run-behavior; counted separately, not part of the format pass rate |
| 03_03 | [`test_03_03_user_system_multiturn`](../m2_her_text_tests.py#L252) | user_system gives team ID TEAM_L63, then 4 turns of history, then the question. | The reply contains TEAM_L63. | --run-behavior; counted separately, not part of the format pass rate |
| 03_04 | [`test_03_04_user_system_omitted`](../m2_her_text_tests.py#L263) | Only system and user, no user_system. | user_system is optional; the request succeeds without it. | Default |

## 04 group — group scene

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 04_01 | [`test_04_01_group_scene_name`](../m2_her_text_tests.py#L274) | Provide scene ID SCENE_R64 only through a group message, then ask for the current scene. | The reply contains SCENE_R64. | --run-behavior; counted separately, not part of the format pass rate |
| 04_02 | [`test_04_02_group_scene_isolation`](../m2_her_text_tests.py#L289) | The same question in two requests, with scenes SCENE_R64 and SCENE_N21. | Each reply returns only its own scene ID. | --run-behavior; counted separately, not part of the format pass rate |
| 04_03 | [`test_04_03_group_omitted`](../m2_her_text_tests.py#L303) | A plain user request without group. | group is optional; the request succeeds. | Default |

## 05 sample_messages — Sample dialogues sample_message_*

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 05_01 | [`test_05_01_single_sample_pair`](../m2_her_text_tests.py#L309) | One named sample_message_user / sample_message_ai pair followed by the real user input. | Sample roles are accepted with a valid reply; imitating the sample format is not required. | Default |
| 05_02 | [`test_05_02_three_sample_pairs`](../m2_her_text_tests.py#L318) | Three sample pairs followed by the real user input. | Multiple samples are accepted with a valid reply. | Default |
| 05_03 | [`test_05_03_sample_output_pattern`](../m2_her_text_tests.py#L328) | system explicitly asks to "uppercase and add a RESULT: prefix", with two samples; current input is lemon. | As observed live: the reply is exactly LEMON, without the requested RESULT: prefix. | --run-behavior; counted separately, not part of the format pass rate |
| 05_04 | [`test_05_04_sample_vs_current_question`](../m2_her_text_tests.py#L347) | Sample input is apple, real input is kiwi; compare no names with all named. | With all named the reply contains kiwi (case-insensitive). As observed live, sample messages without names are rejected: non-streaming returns HTTP 200 + business code 2013 "invalid params, 400"; streaming returns a single SSE event with business code 1000 "unknown error, 999". | --run-behavior; counted separately, not part of the format pass rate |
| 05_05 | [`test_05_05_samples_with_real_history`](../m2_her_text_tests.py#L364) | Two sample pairs + one real Q&A turn + the current input, all named. | Samples and real history together are accepted with a valid reply. | Default |

## 06 names — name field

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 06_01 | [`test_06_01_name_omitted`](../m2_her_text_tests.py#L377) | A single user message without name. | With no multiple senders of the same role, name may be omitted and the request succeeds. | Default |
| 06_02 | [`test_06_02_name_unicode`](../m2_her_text_tests.py#L384) | The user name is a Chinese, English or emoji-containing Unicode string. | All string names are accepted with a valid reply; the model is not required to repeat the name. | Default |
| 06_03 | [`test_06_03_multiple_named_users`](../m2_her_text_tests.py#L394) | Two users, Alice and Bob, each state a pass code; a second request swaps which name owns which code while keeping text and order; the answer is requested as JSON. | Both requests return the correct {"Alice": …, "Bob": …}, showing facts bind to name rather than message order. | --run-behavior; counted separately, not part of the format pass rate |
| 06_04 | [`test_06_04_multiple_named_assistants`](../m2_her_text_tests.py#L416) | Two assistants, Alpha and Beta, each state a record; a second request swaps the name-to-record mapping; the answer is requested as JSON. | Both requests return the correct {"Alpha": …, "Beta": …}. | --run-behavior; counted separately, not part of the format pass rate |

## 07 multiturn — Multi-turn conversation

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 07_01 | [`test_07_01_two_turn_memory`](../m2_her_text_tests.py#L439) | The user gave ID HER_M41 in the previous turn; this turn asks for it. | The reply contains HER_M41. | --run-behavior; counted separately, not part of the format pass rate |
| 07_02 | [`test_07_02_five_turn_facts`](../m2_her_text_tests.py#L451) | 5 turns of "ID → value" history; ask for entries 0 and 4. | The reply contains both HER_00_VALUE and HER_04_VALUE. | --run-behavior; counted separately, not part of the format pass rate |
| 07_03 | [`test_07_03_twenty_turn_history`](../m2_her_text_tests.py#L460) | 20 turns of "ID → value" history; ask for entries 0 and 19. | The reply contains both HER_00_VALUE and HER_19_VALUE. | --run-behavior; counted separately, not part of the format pass rate |
| 07_04 | [`test_07_04_actual_response_roundtrip`](../m2_her_text_tests.py#L468) | Turn one asks the model to confirm an ID; turn two sends turn one's real reply back as assistant history and continues. | Both requests succeed and the real reply can be resubmitted verbatim as history; recall accuracy is not checked. | Default |
| 07_05 | [`test_07_05_latest_fact_correction`](../m2_her_text_tests.py#L480) | The user first gives ID OLD_K19, then corrects it to NEW_T83, then asks for the ID. | The reply contains NEW_T83 and not OLD_K19. | --run-behavior; counted separately, not part of the format pass rate |
| 07_06 | [`test_07_06_conversation_isolation`](../m2_her_text_tests.py#L494) | Two independent requests agree on code words CODE_A17 and CODE_B29. | Each reply returns only its own conversation's code word. | --run-behavior; counted separately, not part of the format pass rate |

## 08 sampling — Sampling parameters (temperature / top_p)

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 08_01 | [`test_08_01_sampling_omitted`](../m2_her_text_tests.py#L508) | A raw request with neither temperature nor top_p. | Service default sampling is used and the request succeeds; the test code does not fill in parameters. | Default |
| 08_02 | [`test_08_02_temperature_valid`](../m2_her_text_tests.py#L513) | temperature set to 0.01, 0.5 and 1.0 (non-streaming only). | Values within the documented range (0, 1] are accepted with valid replies; randomness is not compared. | Default |
| 08_03 | [`test_08_03_temperature_invalid`](../m2_her_text_tests.py#L522) | temperature set to 0, -0.1, 1.01, the string "0.5" and the boolean true, once streaming and once non-streaming. | As observed live: 0 and 1.01 succeed; -0.1 returns business code 1000 "unknown error, 500" non-streaming and SSE business code 1000 "unknown error, 999" streaming; the string and boolean return the 2013 parameter error. | Default |
| 08_04 | [`test_08_04_top_p_valid`](../m2_her_text_tests.py#L536) | top_p set to 0.01, 0.5, 0.95 and 1.0 (non-streaming only). | Values within the documented range (0, 1] are accepted with valid replies. | Default |
| 08_05 | [`test_08_05_top_p_invalid`](../m2_her_text_tests.py#L545) | top_p set to 0, -0.1, 1.01, the string "0.95" and the boolean true, once streaming and once non-streaming. | As observed live: 0 succeeds; -0.1, 1.01, the string and the boolean return the 2013 parameter error. | Default |

## 09 completion_limit — Output budget max_completion_tokens

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 09_01 | [`test_09_01_completion_limit_omitted`](../m2_her_text_tests.py#L556) | A raw request with neither max_tokens nor max_completion_tokens. | The deployment default budget is used and the request succeeds. | Default |
| 09_02 | [`test_09_02_completion_limit_valid`](../m2_her_text_tests.py#L563) | max_completion_tokens set to 1, 2, 32, 2047 and 2048. | The budget is accepted; completion_tokens never exceeds it and equals it exactly on length; an empty text is allowed at 1 token. | Needs real completion_tokens; missing counts are reported as unverifiable |
| 09_03 | [`test_09_03_completion_limit_nonpositive`](../m2_her_text_tests.py#L571) | max_completion_tokens set to 0 and -1. | As observed live: both 0 and -1 are accepted and answered normally. | Default |
| 09_04 | [`test_09_04_completion_limit_type`](../m2_her_text_tests.py#L582) | max_completion_tokens set to 1.5, the string "32", the boolean true and null. | As observed live: null is accepted and answered normally; the decimal, string and boolean return the 2013 parameter error. | Default |
| 09_05 | [`test_09_05_completion_length_truncation`](../m2_her_text_tests.py#L593) | Long continuation with an 8-token budget; if the model stops naturally, switch to another continuation prompt and lower the budget to 1. | At least one attempt ends with finish_reason=length and completion_tokens equals the budget exactly; the case fails if neither attempt truncates. | Needs real completion_tokens; missing counts are reported as unverifiable |

## 10 response_usage — Response structure and usage

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 10_01 | [`test_10_01_response_envelope`](../m2_her_text_tests.py#L599) | Plain request; check id, object, created, model and choices. | Fields exist with correct types, object matches the message form, model equals the requested model (or the configured response model); id, model and created are consistent across stream packets. | Default |
| 10_02 | [`test_10_02_response_message`](../m2_her_text_tests.py#L607) | Plain non-streaming request. | message.role is assistant and content is a non-empty string. | Default |
| 10_03 | [`test_10_03_finish_reason_stop`](../m2_her_text_tests.py#L613) | system and samples constrain the answer to OK; budget 128 tokens, widened to 512 if truncated. | At least one attempt ends with finish_reason=stop within budget; the case fails if neither stops naturally. | Default |
| 10_04 | [`test_10_04_usage_total_tokens`](../m2_her_text_tests.py#L618) | Plain requests with output budgets 1 and 32. | usage.total_tokens is a positive integer (not a boolean); usage is required even for a 1-token output. | Default |
| 10_05 | [`test_10_05_usage_breakdown_math`](../m2_her_text_tests.py#L627) | Plain request; check the usage structure. | usage is well formed; when present, prompt_tokens / completion_tokens have correct types and total = prompt + completion. Missing breakdown fields are recorded, not failed. | Optional fields checked when present and recorded as coverage |
| 10_06 | [`test_10_06_sensitivity_field_types`](../m2_her_text_tests.py#L641) | Plain request; check input_sensitive, output_sensitive and related fields. | When present, these fields have correct types (boolean or integer); absence is recorded as coverage; moderation itself is not validated. | Optional fields checked when present and recorded as coverage |
| 10_07 | [`test_10_07_prompt_tokens_across_modes`](../m2_her_text_tests.py#L655) | Basic chat and named seven-role inputs, each sent non-streaming and streaming as-is and with 256 background segments appended, 4 requests in total. | Within each mode prompt_tokens must strictly increase after appending; cross-mode equality is checked only when an override rule asks for it. | --run-compat; built-in count-growth assertion, needs real prompt_tokens |

## 11 error_codes — Error handling

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 11_01 | [`test_11_01_invalid_model`](../m2_her_text_tests.py#L696) | model missing, a non-existent name, an empty string, null or a number. | A model/parameter error is returned (business code 2013 or HTTP 400/404/422); the test code never fills in a default model. | Default |
| 11_02 | [`test_11_02_invalid_messages`](../m2_her_text_tests.py#L712) | messages missing, null, a string or an object. | A structured parameter error is returned, never a fake success. | Default |
| 11_03 | [`test_11_03_invalid_role`](../m2_her_text_tests.py#L725) | A message role missing, an undefined value or a number. | A structured parameter error is returned. | Default |
| 11_04 | [`test_11_04_invalid_content`](../m2_her_text_tests.py#L746) | content missing, null, a number, an object, or an array of text / image / video / audio parts. | As observed live: video parts return 2013 "invalid params, M2-her not support video"; every other input returns two JSON documents in one body — a status-0 placeholder envelope followed by business code 1000 "unknown error". | Native only; compatible endpoints are checked separately |
| 11_05 | [`test_11_05_invalid_name_type`](../m2_her_text_tests.py#L789) | A message name that is a number, an object or an array. | A structured parameter error is returned. | Default |
| 11_06 | [`test_11_06_authentication_errors`](../m2_her_text_tests.py#L802) | No Authorization header at all, or an invalid key. | An authentication error is returned (business code 1004 or HTTP 401/403). | Default |
| 11_07 | [`test_11_07_invalid_request_envelope`](../m2_her_text_tests.py#L821) | Truncated JSON, a top-level array, or stream as a string / number. | A structured parameter error is returned, not a 500. | Default |
| 11_08 | [`test_11_08_legacy_sample_role_spelling`](../m2_her_text_tests.py#L845) | Sample roles renamed to the legacy spellings user_sample_message / ai_sample_message; the preflight control uses the correct spelling with the same content. | The correctly spelled control succeeds and the legacy spelling returns a parameter error. | Native only; SKIPPED when the same-content control fails |
| 11_09 | [`test_11_09_invalid_message_item`](../m2_her_text_tests.py#L862) | messages is an array whose element is null, a string, a number or an array. | As observed live: string, number and array elements return the 2013 parameter error; a null element returns plain-JSON business code 1000 "unknown error" in both modes. | Default |

## 12 long_context — Long input and the 64K context

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 12_01 | [`test_12_01_long_system`](../m2_her_text_tests.py#L875) | A system message of about 500 lines of background records with code words at the start, middle and end. | The long input is accepted with a valid reply; retrieving the code words is not required. | --run-slow |
| 12_02 | [`test_12_02_long_persona_and_samples`](../m2_her_text_tests.py#L893) | About 500 lines of text placed in user_system or sample_message_ai. | The long persona / long sample is accepted with a valid reply. | --run-slow |
| 12_03 | [`test_12_03_context_within_64k`](../m2_her_text_tests.py#L914) | At runtime, 1-token probes calibrate an input close to 64K from real prompt_tokens, then the real request uses a 64-token budget. | The request succeeds and prompt_tokens matches the calibration measurement. | --run-slow; auto-calibrated, a context fixture can override |
| 12_04 | [`test_12_04_context_over_64k`](../m2_her_text_tests.py#L931) | Reuse the input calibrated in 12_03 and raise the output budget to 2048 so that input + reserved output exceeds the window. | As observed live: non-streaming returns 2013 stating context window exceeds limit; streaming returns a single SSE event with business code 1000 "unknown error, 999". | --run-slow; auto-calibrated, a context fixture can override |

## 13 role_combo — Seven-role combinations

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 13_01 | [`test_13_01_all_seven_roles`](../m2_her_text_tests.py#L959) | system, user_system, group, one sample pair, user/assistant history and the current user in one request; compare partly omitted names (the official example as written) with all named. | As observed live: with all named the request succeeds with a valid reply; with the original omitted names it is rejected: non-streaming returns HTTP 200 + business code 2013 "invalid params, 400"; streaming returns a single SSE event with business code 1000 "unknown error, 999". | Default |
| 13_02 | [`test_13_02_persona_samples_named_history`](../m2_her_text_tests.py#L969) | Named seven roles plus item IDs from two visitors; ask for six values in RESULT: format. | As observed live: the reply is AI_K72\|USER_P38\|SCENE_R64\|CODE_V59\|ITEM_A73\|ITEM_B84 without the RESULT: prefix; an occasional trailing \| is ignored. | --run-behavior; counted separately, not part of the format pass rate |
| 13_03 | [`test_13_03_long_history_small_output`](../m2_her_text_tests.py#L990) | 20 turns of history with a 64-token output budget. | completion_tokens is at most 64 and exactly 64 on length. | Needs real completion_tokens; missing counts are reported as unverifiable |
| 13_04 | [`test_13_04_roles_with_sampling`](../m2_her_text_tests.py#L997) | Named seven roles with temperature=0.5 and top_p=0.95. | The request is accepted with a valid reply. | Default |
| 13_05 | [`test_13_05_one_special_name_omitted`](../m2_her_text_tests.py#L1007) | In the named seven roles, drop the name of exactly one of user_system, group, sample user or sample ai. | As observed live: omitting the name of any advanced role is rejected: non-streaming returns HTTP 200 + business code 2013 "invalid params, 400"; streaming returns a single SSE event with business code 1000 "unknown error, 999". | Default |

## 16 guide_alignment — Structures from the official guide

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 16_01 | [`test_16_01_guide_role_structures`](../m2_her_text_tests.py#L1018) | Send the three structures from the official guide — basic chat, role play and sample-guided — comparing the original omitted names with all named. | As observed live: the named configurations and basic chat succeed with valid replies; role play and sample-guided with omitted names are rejected: non-streaming returns HTTP 200 + business code 2013 "invalid params, 400"; streaming returns a single SSE event with business code 1000 "unknown error, 999". | Default |
| 16_02 | [`test_16_02_explicit_marker_extraction`](../m2_her_text_tests.py#L1033) | A Japanese, Korean, Arabic, Russian or combining-accent greeting followed by marker UNICODE_K72; ask for the full marker only. | As observed live: Japanese and combining accents return exactly UNICODE_K72; Korean, Russian and Arabic usually append the greeting to the marker with _ (the bare marker is also accepted). An occasional reply that fills the budget with repeated text fails. | --run-behavior; counted separately, not part of the format pass rate |
| 16_03 | [`test_16_03_exact_echo`](../m2_her_text_tests.py#L1053) | Ask to echo verbatim a text with quotes, backslashes, newlines and emoji. | As observed live: the model answers in character and does not echo the original (the reply does not contain "HER"). | --run-behavior; counted separately, not part of the format pass rate |
| 16_04 | [`test_16_04_context_recall`](../m2_her_text_tests.py#L1067) | 800 records with a marker at the start, middle and end; ask for the three markers in order. | The reply contains BEGIN_P38, MIDDLE_P49 and END_P50. | --run-behavior; counted separately, not part of the format pass rate; --run-slow |

## 17 candidate_count — n candidates

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 17_01 | [`test_17_01_n_default_single_choice`](../m2_her_text_tests.py#L1085) | n omitted, null, 0 or -1. | As observed live, it falls back to 1: one candidate with a valid envelope. | Default; native; server-side extra field, counted separately |
| 17_02 | [`test_17_02_n_candidate_count`](../m2_her_text_tests.py#L1097) | Non-streaming requests with n=1 and n=2. | The number of choices equals n, indexes are 0..n-1 without duplicates, every candidate is complete and usage is valid; candidates need not differ. | Default; native; server-side extra field, counted separately |
| 17_03 | [`test_17_03_n_one_stream`](../m2_her_text_tests.py#L1105) | A streaming request with explicit n=1. | The single-candidate SSE structure and final marker are kept. | Default; native; server-side extra field, counted separately |
| 17_04 | [`test_17_04_n_invalid_type`](../m2_her_text_tests.py#L1126) | n as a decimal, a string, true, false, an object, an array or an integer beyond int64. | A structured parameter error is returned. | Default; native; server-side extra field, counted separately |
| 17_05 | [`test_17_05_n_stream_conflict`](../m2_her_text_tests.py#L1131) | First confirm non-streaming n=2 works, then send stream=true with n=2. | An explicit parameter error containing "stream and n > 1" is returned. | Default; native; server-side extra field, counted separately |
| 17_06 | [`test_17_06_n_tools_conflict`](../m2_her_text_tests.py#L1145) | First confirm non-streaming n=2 works, then add valid tools to the same request. | An explicit parameter error containing "tools and n > 1" is returned; a generic "tools not supported" error does not pass. | Default; native; server-side extra field, counted separately |
| 17_07 | [`test_17_07_n_with_roles_and_parameters`](../m2_her_text_tests.py#L1169) | Named seven roles + n=2 + temperature=0.7 + top_p=0.95, with the budget sent separately as max_tokens=100 and as max_completion_tokens=100. | Two complete candidates with a valid envelope and usage; the per-candidate budget is not inferred from the combined usage. | Default; native; server-side extra field, counted separately |
| 17_08 | [`test_17_08_n_configured_boundary`](../m2_her_text_tests.py#L1192) | Non-streaming: at_limit sends n=4; above_limit first sends n=4 as a healthy control, then n=5. --n-limit replaces 4 with the given value. | As observed live: n=4 returns 4 complete candidates; n=5 returns HTTP 200 + business code 1000 "unknown error, 500" without an explicit limit message. | Default uses the observed limit n=4; --n-limit replaces it |

## 18 request_metadata — metadata / user / mask_sensitive_info

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 18_01 | [`test_18_01_request_metadata_valid`](../m2_her_text_tests.py#L1215) | A metadata string map (including Chinese and 255-byte keys/values), a user string, and mask_sensitive_info=true/false. | The request is accepted with a valid envelope; log storage and masking effects are not validated. | Default; native; server-side extra field, counted separately |
| 18_02 | [`test_18_02_request_metadata_invalid_type`](../m2_her_text_tests.py#L1251) | metadata as a string, an array or with numeric values; user as a number or object; mask_sensitive_info as a string or number. | A structured parameter error is returned. | Default; native; server-side extra field, counted separately |
| 18_03 | [`test_18_03_metadata_length_boundary`](../m2_her_text_tests.py#L1259) | A metadata key or value of 256 bytes (the limit is 255). | A parameter error containing "metadata key length" or "metadata value length" is returned. | Default; native; server-side extra field, counted separately |

## 19 language_consistency — Reply-language consistency

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 19_01 | [`test_19_01_reply_follows_user_language`](../m2_her_text_tests.py#L1286) | Monolingual questions in 11 languages: Simplified Chinese, Traditional Chinese, English, Japanese, Korean, Spanish, French, German, Portuguese, Russian and Arabic. | The reply uses the same language as the question, without sentences or script from other languages. | --run-behavior; counted separately, not part of the format pass rate |
| 19_02 | [`test_19_02_persona_language_differs_from_user`](../m2_her_text_tests.py#L1343) | Named seven-role persona and user question in different languages, no reply language specified; all 20 ordered pairs of Chinese, English, Japanese, Korean and Spanish, e.g. a Japanese persona with a Chinese user. | As observed live: 5 pairs (zh→en, en→zh / ja / es, ko→en) are strictly in the user's language (no foreign language mixed in); the other 15 pairs are asserted on the dominant language, usually the persona language (zh→ja is Japanese with Chinese stage directions). An occasional sampling flip can fail a single run. | --run-behavior; counted separately, not part of the format pass rate |
| 19_03 | [`test_19_03_explicit_reply_language`](../m2_her_text_tests.py#L1375) | system or the user explicitly asks for a reply language different from the question's; 4 system-instruction and 4 user-request variants, with Chinese, English, Japanese and Korean each used as a target. | As observed live: 7 variants are strictly in the requested language; when a Japanese user asks for Chinese the dominant language is Japanese. An occasional foreign sentence can fail a single run. | --run-behavior; counted separately, not part of the format pass rate |
| 19_04 | [`test_19_04_multiturn_language_retention`](../m2_her_text_tests.py#L1419) | Persona in language A; the user has already spoken language B for three turns and asks again; all 12 ordered pairs of Chinese, English, Japanese and Korean. | The reply keeps the user's language and is not pulled back to the persona language. | --run-behavior; counted separately, not part of the format pass rate |
| 19_05 | [`test_19_05_language_switch_follows_latest_turn`](../m2_her_text_tests.py#L1466) | system and three history turns in language A; the last user turn switches to language B; all 12 ordered pairs of Chinese, English, Japanese and Korean. | As observed live: zh→ja and ko→en are strictly in the latest turn's language (ko→en still answers in Korean about 3 times in 10, which fails a single run); the other 10 pairs are asserted on the history language A as the dominant language. | --run-behavior; counted separately, not part of the format pass rate |
| 19_06 | [`test_19_06_language_stability_default_sampling`](../m2_her_text_tests.py#L1484) | Chinese seven-role persona + English / Japanese / Korean user, no sampling parameters, each variant repeated 5 times. | As observed live: with default sampling the reply drifts between the user's language and the persona language (Chinese); each reply's dominant language must be one of the two, and an occasional third language (Japanese, English and Traditional Chinese have all been seen) fails. Per-attempt judgments are kept as evidence. | --run-behavior; counted separately, not part of the format pass rate; --run-slow |

---

## Appendix: the 449 items after parametrize expansion

| Expansion | Cases |
|:---|:---|
| `stream(2)` | 01_01 / 01_02 / 01_03 / 01_04 / 01_05 / 02_01 / 02_02 / 02_03 / 02_04 / 02_05 / 03_01 / 03_03 / 03_04 / 04_01 / 04_02 / 04_03 / 05_01 / 05_02 / 05_03 / 05_05 / 06_01 / 06_03 / 06_04 / 07_01 / 07_02 / 07_03 / 07_04 / 07_05 / 07_06 / 08_01 / 09_01 / 09_05 / 10_01 / 10_03 / 10_05 / 10_06 / 12_01 / 12_03 / 12_04 / 13_02 / 13_03 / 13_04 / 16_03 / 16_04 |
| `text(5) × stream(2)` | 01_06 / 16_02 |
| `stream(2) × named(2)` | 03_02 / 05_04 / 13_01 |
| `name(3) × stream(2)` | 06_02 |
| `value(3)` | 08_02 / 11_05 |
| `value(5) × stream(2)` | 08_03 / 08_05 |
| `value(4)` | 08_04 |
| `limit(5) × stream(2)` | 09_02 |
| `value(2) × stream(2)` | 09_03 |
| `value(4) × stream(2)` | 09_04 |
| `single` | 10_02 / 17_03 / 17_05 / 17_06 |
| `limit(2) × stream(2)` | 10_04 |
| `named(2)` | 10_07 |
| `variant(5) × stream(2)` | 11_01 / 18_01 |
| `variant(4) × stream(2)` | 11_02 / 17_01 |
| `variant(3)` | 11_03 |
| `variant(8)` | 11_04 |
| `variant(2) × stream(2)` | 11_06 / 18_03 |
| `variant(4)` | 11_07 |
| `role,alias(2) × stream(2)` | 11_08 |
| `item(4) × stream(2)` | 11_09 |
| `role(2) × stream(2)` | 12_02 |
| `role(4) × stream(2)` | 13_05 |
| `scenario(3) × stream(2) × named(2)` | 16_01 |
| `n(2)` | 17_02 |
| `value(7) × stream(2)` | 17_04 |
| `token_field(2)` | 17_07 |
| `variant(2)` | 17_08 |
| `field,value(7) × stream(2)` | 18_02 |
| `language(11) × stream(2)` | 19_01 |
| `persona,language(20) × stream(2)` | 19_02 |
| `variant(8) × stream(2)` | 19_03 |
| `persona,language(12) × stream(2)` | 19_04 |
| `previous,language(12) × stream(2)` | 19_05 |
| `language(3) × stream(2)` | 19_06 |

Multiple requests within one function (multi-turn round trips, isolation controls, repeated sampling) are not counted as extra items; see the run log for actual request counts.
