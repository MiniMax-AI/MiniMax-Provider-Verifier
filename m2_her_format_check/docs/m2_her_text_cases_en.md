# M2-Her Text and Role Format Check Cases

> File: [`m2_her_format_check/m2_her_text_tests.py`](../m2_her_text_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **17**; case functions: **80**; collected pytest items: **343**
> Expected values: taken from the official MiniMax API (measured 2026-11-05); see the [README](../README_en.md) for the rules.
> "The request fails": HTTP status is not 200, or HTTP 200 with a non-zero business code / an error object in the response, and no reply text; specific error codes and messages are not compared.

## Module overview

| Module | Name | Topic | Functions |
|:---:|:---|:---|:---:|
| 01 | basic_text | Basic text | 6 |
| 02 | system_persona | system persona | 4 |
| 03 | user_system | user_system user persona | 3 |
| 04 | group | group scene | 3 |
| 05 | sample_messages | Sample dialogues sample_message_* | 4 |
| 06 | names | name field | 4 |
| 07 | multiturn | Multi-turn conversation | 6 |
| 08 | sampling | Sampling parameters (temperature / top_p) | 5 |
| 09 | completion_limit | Output length limit max_completion_tokens | 5 |
| 10 | response_usage | Response structure and usage | 7 |
| 11 | error_codes | Error handling | 9 |
| 12 | long_context | Long input and the 64K context | 4 |
| 13 | role_combo | Seven-role combinations | 5 |
| 16 | guide_alignment | Structures from the official guide | 2 |
| 17 | candidate_count | n multiple replies | 8 |
| 18 | request_metadata | metadata / user / mask_sensitive_info | 3 |
| 19 | language_consistency | Reply language | 2 |

---

## 01 basic_text — Basic text

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 01_01 | [`test_01_01_minimal_user_message`](../m2_her_text_tests.py#L71) | Send a single user message with no system, name or optional parameters; once streaming and once non-streaming. | The request succeeds (HTTP 200, business code 0) with one non-empty assistant reply; the stream parses completely and has a single finish reason. | Default |
| 01_02 | [`test_01_02_system_user_chat`](../m2_her_text_tests.py#L75) | system sets up a "friendly assistant"; the user says "你好" (hello). | The request succeeds with a well-formed, non-empty reply. | Default |
| 01_03 | [`test_01_03_chinese_text`](../m2_her_text_tests.py#L82) | Ask in Chinese for a short greeting. | The reply contains Chinese and no mojibake (U+FFFD). | --run-behavior (model behavior, counted separately) |
| 01_04 | [`test_01_04_english_text`](../m2_her_text_tests.py#L94) | Ask in English for a greeting in English only. | The reply contains English words and no Chinese. | --run-behavior (model behavior, counted separately) |
| 01_05 | [`test_01_05_text_escaping_unicode`](../m2_her_text_tests.py#L105) | The user message contains double quotes, backslashes, newlines and emoji. | The request succeeds and the response parses as UTF-8 / JSON. Only the format is checked, not whether the text is repeated verbatim. | Default |
| 01_06 | [`test_01_06_multilingual_input`](../m2_her_text_tests.py#L121) | A Chinese question that includes a Japanese, Korean, Arabic, Russian or accented greeting. | Every script is accepted and the reply is well-formed. No translation or extraction is required. | Default |

## 02 system_persona — system persona

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 02_01 | [`test_02_01_system_identity`](../m2_her_text_tests.py#L133) | system assigns the ID AI_K72; the user asks the model for its own ID only. | The reply contains AI_K72. | --run-behavior (model behavior, counted separately) |
| 02_02 | [`test_02_02_system_reply_prefix`](../m2_her_text_tests.py#L143) | system requires every reply to start with HER_REPLY:; the user says "你好". | The reply starts with HER_REPLY:. | --run-behavior (model behavior, counted separately) |
| 02_04 | [`test_02_04_system_identity_multiturn`](../m2_her_text_tests.py#L154) | After system sets the identity, insert 4 unrelated turns, then ask for the identity. | The reply still contains AI_K72. | --run-behavior (model behavior, counted separately) |
| 02_05 | [`test_02_05_system_identity_isolation`](../m2_her_text_tests.py#L166) | Two independent requests set the identity to AI_K72 and AI_B19 and ask the same question. | Each reply gives only its own ID, never the other request's ID. | --run-behavior (model behavior, counted separately) |

## 03 user_system — user_system user persona

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 03_01 | [`test_03_01_user_system_identity`](../m2_her_text_tests.py#L180) | Put user ID USER_P38 only in user_system, then ask for the user ID. | The reply contains USER_P38. | --run-behavior (model behavior, counted separately) |
| 03_03 | [`test_03_03_user_system_multiturn`](../m2_her_text_tests.py#L191) | user_system gives team ID TEAM_L63; after 4 turns, ask for it. | The reply contains TEAM_L63. | --run-behavior (model behavior, counted separately) |
| 03_04 | [`test_03_04_user_system_omitted`](../m2_her_text_tests.py#L202) | Only system and user, without user_system. | user_system is optional; the request succeeds. | Default |

## 04 group — group scene

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 04_01 | [`test_04_01_group_scene_name`](../m2_her_text_tests.py#L213) | Put scene ID SCENE_R64 only in a group message, then ask for the current scene. | The reply contains SCENE_R64. | --run-behavior (model behavior, counted separately) |
| 04_02 | [`test_04_02_group_scene_isolation`](../m2_her_text_tests.py#L228) | Send the same question twice, with scenes SCENE_R64 and SCENE_N21. | Each reply gives only its own scene ID. | --run-behavior (model behavior, counted separately) |
| 04_03 | [`test_04_03_group_omitted`](../m2_her_text_tests.py#L242) | A plain user request without group. | group is optional; the request succeeds. | Default |

## 05 sample_messages — Sample dialogues sample_message_*

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 05_01 | [`test_05_01_single_sample_pair`](../m2_her_text_tests.py#L248) | One sample dialogue (sample user + sample ai, both with name) followed by the real question. | The request succeeds with a well-formed reply; copying the sample format is not required. | Default |
| 05_02 | [`test_05_02_three_sample_pairs`](../m2_her_text_tests.py#L257) | Three sample dialogues followed by the real question. | The request succeeds with a well-formed reply. | Default |
| 05_04 | [`test_05_04_sample_vs_current_question`](../m2_her_text_tests.py#L267) | The sample asks about apple, the real question is kiwi; test both "no name" and "every message with a name". | With names: the reply contains kiwi (case-insensitive). Sample messages without names: the request fails. | --run-behavior (model behavior, counted separately) |
| 05_05 | [`test_05_05_samples_with_real_history`](../m2_her_text_tests.py#L290) | Two sample dialogues + one real Q&A turn + the current question, every message with a name. | The request succeeds with a well-formed reply. | Default |

## 06 names — name field

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 06_01 | [`test_06_01_name_omitted`](../m2_her_text_tests.py#L303) | A single user message without name. | The request succeeds. | Default |
| 06_02 | [`test_06_02_name_unicode`](../m2_her_text_tests.py#L310) | The user name is a Chinese, English or emoji-containing string. | All are accepted and the reply is well-formed; the model need not say the name. | Default |
| 06_03 | [`test_06_03_multiple_named_users`](../m2_her_text_tests.py#L320) | Users Alice and Bob each give a pass code; a second request swaps their codes (message order unchanged); the answer is requested as JSON. | Both requests return the correct {"Alice": …, "Bob": …}, so speakers are told apart by name, not by message order. | --run-behavior (model behavior, counted separately) |
| 06_04 | [`test_06_04_multiple_named_assistants`](../m2_her_text_tests.py#L342) | Assistants Alpha and Beta each give a record; a second request swaps their records; the answer is requested as JSON. | Both requests return the correct {"Alpha": …, "Beta": …}. | --run-behavior (model behavior, counted separately) |

## 07 multiturn — Multi-turn conversation

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 07_01 | [`test_07_01_two_turn_memory`](../m2_her_text_tests.py#L365) | The user gave ID HER_M41 in the previous turn; this turn asks for it. | The reply contains HER_M41. | --run-behavior (model behavior, counted separately) |
| 07_02 | [`test_07_02_five_turn_facts`](../m2_her_text_tests.py#L377) | 5 turns of "ID → value" history; ask for entries 0 and 4. | The reply contains both HER_00_VALUE and HER_04_VALUE. | --run-behavior (model behavior, counted separately) |
| 07_03 | [`test_07_03_twenty_turn_history`](../m2_her_text_tests.py#L386) | 20 turns of "ID → value" history; ask for entries 0 and 19. | The reply contains both HER_00_VALUE and HER_19_VALUE. | --run-behavior (model behavior, counted separately) |
| 07_04 | [`test_07_04_actual_response_roundtrip`](../m2_her_text_tests.py#L394) | Turn one asks the model to confirm an ID; turn two sends that reply back verbatim as assistant history and continues. | Both turns succeed and the model's reply can be resubmitted as history; recall accuracy is not checked. | Default |
| 07_05 | [`test_07_05_latest_fact_correction`](../m2_her_text_tests.py#L406) | The user first gives ID OLD_K19, then corrects it to NEW_T83, then asks for the ID. | The reply contains NEW_T83 and not OLD_K19. | --run-behavior (model behavior, counted separately) |
| 07_06 | [`test_07_06_conversation_isolation`](../m2_her_text_tests.py#L420) | Two independent requests each agree on a code word: CODE_A17 and CODE_B29. | Each reply gives only its own conversation's code word. | --run-behavior (model behavior, counted separately) |

## 08 sampling — Sampling parameters (temperature / top_p)

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 08_01 | [`test_08_01_sampling_omitted`](../m2_her_text_tests.py#L434) | No temperature or top_p in the request. | The server defaults are used and the request succeeds; the test code adds no parameters. | Default |
| 08_02 | [`test_08_02_temperature_valid`](../m2_her_text_tests.py#L439) | temperature set to 0.01, 0.5 and 1.0 (non-streaming only). | Values within the documented range (0, 1] work; randomness is not compared. | Default |
| 08_03 | [`test_08_03_temperature_invalid`](../m2_her_text_tests.py#L448) | temperature set to 0, -0.1, 1.01, the string "0.5" and the boolean true; once streaming and once non-streaming. | 0 and 1.01 are outside the documented range (0, 1]: accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx). -0.1, the string and the boolean must fail. | Default |
| 08_04 | [`test_08_04_top_p_valid`](../m2_her_text_tests.py#L461) | top_p set to 0.01, 0.5, 0.95 and 1.0 (non-streaming only). | Values within the documented range (0, 1] work. | Default |
| 08_05 | [`test_08_05_top_p_invalid`](../m2_her_text_tests.py#L470) | top_p set to 0, -0.1, 1.01, the string "0.95" and the boolean true; once streaming and once non-streaming. | 0 is outside the documented range (0, 1]: accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx). -0.1, 1.01, the string and the boolean must fail. | Default |

## 09 completion_limit — Output length limit max_completion_tokens

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 09_01 | [`test_09_01_completion_limit_omitted`](../m2_her_text_tests.py#L484) | Neither max_tokens nor max_completion_tokens in the request. | The server default limit is used and the request succeeds. | Default |
| 09_02 | [`test_09_02_completion_limit_valid`](../m2_her_text_tests.py#L491) | max_completion_tokens set to 1, 2, 32, 2047 and 2048. | The output token count never exceeds the limit and equals it exactly when finish_reason=length; an empty reply is allowed at 1. | Default; needs completion_tokens, reported as unverifiable if missing |
| 09_03 | [`test_09_03_completion_limit_nonpositive`](../m2_her_text_tests.py#L499) | max_completion_tokens set to 0 and -1. | For 0 and -1, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx). | Default |
| 09_04 | [`test_09_04_completion_limit_type`](../m2_her_text_tests.py#L512) | max_completion_tokens set to 1.5, the string "32", the boolean true and null. | For null, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx). The decimal, string and boolean must fail. | Default |
| 09_05 | [`test_09_05_completion_length_truncation`](../m2_her_text_tests.py#L523) | Long continuation with an 8-token limit; if the model finishes early, switch to another continuation prompt with a limit of 1. | At least one attempt ends with finish_reason=length and the output token count equals the limit; the case fails if neither attempt is truncated. | Default; needs completion_tokens, reported as unverifiable if missing |

## 10 response_usage — Response structure and usage

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 10_01 | [`test_10_01_response_envelope`](../m2_her_text_tests.py#L529) | A plain request; check id, object, created, model and choices. | All fields present with correct types; object matches streaming or not; model equals the requested model; id, model and created are the same across stream packets. | Default |
| 10_02 | [`test_10_02_response_message`](../m2_her_text_tests.py#L537) | A plain non-streaming request. | message.role is assistant and content is a non-empty string. | Default |
| 10_03 | [`test_10_03_finish_reason_stop`](../m2_her_text_tests.py#L543) | system and samples restrict the answer to OK; limit 128 tokens, widened to 512 if truncated. | At least one attempt ends with finish_reason=stop within the limit; the case fails if neither stops normally. | Default |
| 10_04 | [`test_10_04_usage_total_tokens`](../m2_her_text_tests.py#L548) | Plain requests with output limits 1 and 32. | usage.total_tokens is a positive integer, even for a 1-token output. | Default |
| 10_05 | [`test_10_05_usage_breakdown_math`](../m2_her_text_tests.py#L557) | A plain request; check the usage structure. | usage is well-formed; when present, prompt_tokens / completion_tokens have correct types and total = prompt + completion. Missing breakdown fields are recorded, not failed. | Default; missing fields are only recorded |
| 10_06 | [`test_10_06_sensitivity_field_types`](../m2_her_text_tests.py#L571) | A plain request; check input_sensitive, output_sensitive and related fields. | When present these fields have correct types (boolean or integer); absence is recorded; moderation itself is not checked. | Default; missing fields are only recorded |
| 10_07 | [`test_10_07_prompt_tokens_across_modes`](../m2_her_text_tests.py#L585) | A plain chat and a full seven-role conversation, each sent as-is and with 256 background segments appended, non-streaming and streaming, 4 requests in total. | Within each mode, prompt_tokens must grow after the input is appended. | --run-compat; needs prompt_tokens |

## 11 error_codes — Error handling

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 11_01 | [`test_11_01_invalid_model`](../m2_her_text_tests.py#L626) | model missing, a non-existent name, an empty string, null or a number. | The request fails; the test code never fills in a default model. | Default |
| 11_02 | [`test_11_02_invalid_messages`](../m2_her_text_tests.py#L642) | messages missing, null, a string or an object. | The request fails and is not treated as a success. | Default |
| 11_03 | [`test_11_03_invalid_role`](../m2_her_text_tests.py#L655) | A message role missing, an undefined value or a number. | The request fails. | Default |
| 11_04 | [`test_11_04_invalid_content`](../m2_her_text_tests.py#L676) | content missing, null, a number, an object, or an array of text / image / video / audio parts. | The request fails (including image, video and audio content that M2-her does not support). | Default; native only |
| 11_05 | [`test_11_05_invalid_name_type`](../m2_her_text_tests.py#L715) | A message name that is a number, an object or an array. | The request fails. | Default |
| 11_06 | [`test_11_06_authentication_errors`](../m2_her_text_tests.py#L728) | No Authorization header, or an invalid key. | The request fails. | Default |
| 11_07 | [`test_11_07_invalid_request_envelope`](../m2_her_text_tests.py#L747) | Truncated JSON, a top-level array, or stream as a string / number. | The request fails. | Default |
| 11_08 | [`test_11_08_legacy_sample_role_spelling`](../m2_her_text_tests.py#L771) | Sample roles written with the legacy names user_sample_message / ai_sample_message; a request with the same content and the correct names is the control. | The correctly named control succeeds and the legacy names fail. | Default; native only; skipped if the control request fails |
| 11_09 | [`test_11_09_invalid_message_item`](../m2_her_text_tests.py#L788) | messages is an array whose element is null, a string, a number or an array. | The request fails. | Default |

## 12 long_context — Long input and the 64K context

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 12_01 | [`test_12_01_long_system`](../m2_her_text_tests.py#L798) | About 500 lines of background in system, with a code word at the start, middle and end. | The request succeeds with a well-formed reply; finding the code words is not required. | --run-slow |
| 12_02 | [`test_12_02_long_persona_and_samples`](../m2_her_text_tests.py#L816) | About 500 lines of text in user_system or a sample ai message. | The request succeeds with a well-formed reply. | --run-slow |
| 12_03 | [`test_12_03_context_within_64k`](../m2_her_text_tests.py#L837) | At runtime, a few 1-token requests build an input close to 64K from real prompt_tokens; then the real request uses a 64-token limit. | The request succeeds and prompt_tokens matches the measured value. | --run-slow; --context-fixture can supply measured inputs |
| 12_04 | [`test_12_04_context_over_64k`](../m2_her_text_tests.py#L854) | Reuse the input from 12_03 and raise the output limit to 2048 so that input + output limit exceeds 64K. | The request fails. | --run-slow; --context-fixture can supply measured inputs |

## 13 role_combo — Seven-role combinations

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 13_01 | [`test_13_01_all_seven_roles`](../m2_her_text_tests.py#L878) | system, user_system, group, one sample dialogue, earlier Q&A and the current question in one request; test the official example as written (some messages without name) and "every message with a name". | With names the request succeeds with a well-formed reply; the official example without names fails. | Default |
| 13_02 | [`test_13_02_persona_samples_named_history`](../m2_her_text_tests.py#L889) | A full seven-role conversation (system, user_system, group, sample dialogue, earlier Q&A and the current question, every message with a name), plus item IDs from two visitors; ask for six values in RESULT: format. | The six values AI_K72\|USER_P38\|SCENE_R64\|CODE_V59\|ITEM_A73\|ITEM_B84 come back in order; the RESULT: prefix is optional. | --run-behavior (model behavior, counted separately) |
| 13_03 | [`test_13_03_long_history_small_output`](../m2_her_text_tests.py#L913) | 20 turns of history with a 64-token output limit. | The output token count is at most 64 and exactly 64 when truncated. | Default; needs completion_tokens, reported as unverifiable if missing |
| 13_04 | [`test_13_04_roles_with_sampling`](../m2_her_text_tests.py#L920) | A full seven-role conversation (system, user_system, group, sample dialogue, earlier Q&A and the current question, every message with a name), with temperature=0.5 and top_p=0.95. | The request succeeds with a well-formed reply. | Default |
| 13_05 | [`test_13_05_one_special_name_omitted`](../m2_her_text_tests.py#L930) | A full seven-role conversation (system, user_system, group, sample dialogue, earlier Q&A and the current question, every message with a name); each time, drop the name of exactly one of user_system, group, sample user or sample ai. | Dropping any one of these names makes the request fail. | Default |

## 16 guide_alignment — Structures from the official guide

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 16_01 | [`test_16_01_guide_role_structures`](../m2_her_text_tests.py#L941) | Send the three structures from the official guide — basic chat, role play and sample-guided — as written (some messages without name) and with every message named. | The named versions and basic chat succeed; role play and sample-guided as written, without names, fail. | Default |
| 16_04 | [`test_16_04_context_recall`](../m2_her_text_tests.py#L957) | 800 records with a marker at the start, middle and end; ask for the three markers in order. | The reply contains BEGIN_P38, MIDDLE_P49 and END_P50. | --run-behavior (model behavior, counted separately); --run-slow |

## 17 candidate_count — n multiple replies

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 17_01 | [`test_17_01_n_default_single_choice`](../m2_her_text_tests.py#L975) | n omitted, null, 0 or -1. | With n omitted, one reply comes back; for null, 0 and -1, accepting or rejecting both pass (an accepted reply must be well-formed, a rejection must be a failed request, never a 5xx), and an accepted request returns one reply. | Default; native only |
| 17_02 | [`test_17_02_n_candidate_count`](../m2_her_text_tests.py#L992) | Non-streaming requests with n=1 and n=2. | The number of choices equals n, indexes are 0..n-1 without duplicates, every reply is complete and usage is valid; replies need not differ. | Default; native only |
| 17_03 | [`test_17_03_n_one_stream`](../m2_her_text_tests.py#L1000) | A streaming request with explicit n=1. | Same as a normal stream: a single reply. | Default; native only |
| 17_04 | [`test_17_04_n_invalid_type`](../m2_her_text_tests.py#L1021) | n as a decimal, a string, true, false, an object, an array or an integer beyond int64. | The request fails. | Default; native only |
| 17_05 | [`test_17_05_n_stream_conflict`](../m2_her_text_tests.py#L1026) | First confirm non-streaming n=2 works, then send stream=true with n=2. | The request fails. | Default; native only |
| 17_06 | [`test_17_06_n_tools_conflict`](../m2_her_text_tests.py#L1036) | First confirm non-streaming n=2 works, then add valid tools to the same request. | The request fails. | Default; native only |
| 17_07 | [`test_17_07_n_with_roles_and_parameters`](../m2_her_text_tests.py#L1056) | A full seven-role conversation (system, user_system, group, sample dialogue, earlier Q&A and the current question, every message with a name) + n=2 + temperature=0.7 + top_p=0.95, with the limit sent as max_tokens=100 and as max_completion_tokens=100. | Two complete replies with valid top-level fields and usage. | Default; native only |
| 17_08 | [`test_17_08_n_configured_boundary`](../m2_her_text_tests.py#L1079) | Non-streaming: send n=4, then n=5 (only after n=4 succeeds). --n-limit changes the limit 4. | n=4 returns 4 complete replies; n=5 fails. | Default; --n-limit changes the limit |

## 18 request_metadata — metadata / user / mask_sensitive_info

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 18_01 | [`test_18_01_request_metadata_valid`](../m2_her_text_tests.py#L1099) | metadata as a string map (including Chinese and 255-byte keys/values), user as a string, mask_sensitive_info=true/false. | The request succeeds with a well-formed response; logging and masking effects are not checked. | Default; native only |
| 18_02 | [`test_18_02_request_metadata_invalid_type`](../m2_her_text_tests.py#L1135) | metadata as a string, an array or with numeric values; user as a number or object; mask_sensitive_info as a string or number. | The request fails. | Default; native only |
| 18_03 | [`test_18_03_metadata_length_boundary`](../m2_her_text_tests.py#L1143) | A metadata key or value 256 bytes long (the limit is 255). | The request fails. | Default; native only |

## 19 language_consistency — Reply language

| Case ID | Function | Scenario | Main checks | Run condition |
|:---:|:---|:---|:---|:---|
| 19_01 | [`test_19_01_reply_follows_user_language`](../m2_her_text_tests.py#L1166) | Ask in 11 languages: Simplified Chinese, Traditional Chinese, English, Japanese, Korean, Spanish, French, German, Portuguese, Russian and Arabic. | The reply uses the question's language without sentences in other languages. Up to 3 attempts per language, 2 must pass; a failed request fails the case at once. | --run-behavior (model behavior, counted separately) |
| 19_04 | [`test_19_04_multiturn_language_retention`](../m2_her_text_tests.py#L1226) | The persona is in language A; the user has already spoken language B for three turns and asks again; all 12 ordered pairs of Chinese, English, Japanese and Korean. | The reply stays in the user's language B and is not pulled into the persona language. | --run-behavior (model behavior, counted separately) |

---

## Appendix: the 343 items after parametrize expansion

| Expansion | Cases |
|:---|:---|
| `stream(2)` | 01_01 / 01_02 / 01_03 / 01_04 / 01_05 / 02_01 / 02_02 / 02_04 / 02_05 / 03_01 / 03_03 / 03_04 / 04_01 / 04_02 / 04_03 / 05_01 / 05_02 / 05_05 / 06_01 / 06_03 / 06_04 / 07_01 / 07_02 / 07_03 / 07_04 / 07_05 / 07_06 / 08_01 / 09_01 / 09_05 / 10_01 / 10_03 / 10_05 / 10_06 / 12_01 / 12_03 / 12_04 / 13_02 / 13_03 / 13_04 / 16_04 |
| `text(5) × stream(2)` | 01_06 |
| `stream(2) × named(2)` | 05_04 / 13_01 |
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
| `persona,language(12) × stream(2)` | 19_04 |

Multiple requests within one function (multi-turn round trips, isolation controls, repeated sampling) are not counted as extra items; see the run log for actual request counts.
