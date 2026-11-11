# M2-Her Text and Role Format Check Cases

> File: [`m2_her_format_check/m2_her_text_tests.py`](../m2_her_text_tests.py)
> Naming: `test_<module>_<sequence within module>_<scenario>`
> Modules: **17**; case functions: **80**; collected pytest items: **343**

Read each row from left to right. It describes the input a provider receives, the response that earns a pass and any flag needed to run it. Unless noted, these cases target the native route. The sample prompts in the tests are often in Chinese.

S requires a valid reply. F requires a rejected request without reply text. E allows either but rejects HTTP 5xx. Branches expecting or permitting rejection first check a working control, reusing its result for the same configuration. Any extra in-case controls are described in the relevant row. A failed preflight is reported as SKIP. The reason for a rejection may vary by provider. Network errors and broken JSON/SSE do not count as a valid rejection. [Verdict rules and configuration](../README_en.md#verdict-rules)

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

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 01_01 | [`test_01_01_minimal_user_message`](../m2_her_text_tests.py#L72) | [S: must succeed](../README_en.md#verdict-rules) | Send a single user message asking for OK, with a 128-token budget and no system message, speaker name or sampling settings. | Both streaming and ordinary HTTP must deliver one nonblank assistant reply. The word OK is optional. | Default |
| 01_02 | [`test_01_02_system_user_chat`](../m2_her_text_tests.py#L76) | [S: must succeed](../README_en.md#verdict-rules) | Set the assistant's persona to “friendly” in a system message, then send a user greeting. | The two-message conversation must produce a nonblank reply. Tone is outside the check. | Default |
| 01_03 | [`test_01_03_chinese_text`](../m2_her_text_tests.py#L83) | [S: must succeed](../README_en.md#verdict-rules) | Ask for one short greeting in Chinese. | Look for at least one basic Han character and no replacement character (U+FFFD). A greeting such as 你好 qualifies. This is a character check. | --run-behavior (model behavior, counted separately) |
| 01_04 | [`test_01_04_english_text`](../m2_her_text_tests.py#L95) | [S: must succeed](../README_en.md#verdict-rules) | Ask for a short greeting in English only. | The reply must contain an ASCII letter and no basic Han characters. Other Latin-script languages can also satisfy this check. | --run-behavior (model behavior, counted separately) |
| 01_05 | [`test_01_05_text_escaping_unicode`](../m2_her_text_tests.py#L106) | [S: must succeed](../README_en.md#verdict-rules) | Send text containing quotes, a backslash, a newline and two emoji. Ask for an exact copy. | The input must be accepted and the reply must decode successfully and contain text. Exact reproduction is outside this case. | Default |
| 01_06 | [`test_01_06_multilingual_input`](../m2_her_text_tests.py#L122) | [S: must succeed](../README_en.md#verdict-rules) | Embed Japanese, Korean, Arabic, Russian or a decomposed accent in a Chinese user message, one input per variant. | Each input must produce text in both modes. A translation or a reply in the quoted language is optional. | Default |

## 02 system_persona — system persona

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 02_01 | [`test_02_01_system_identity`](../m2_her_text_tests.py#L134) | [S: must succeed](../README_en.md#verdict-rules) | Give the assistant the ID AI_K72 only in its system message, then ask for its ID. | The reply must contain AI_K72. Extra wording around it is allowed. | --run-behavior (model behavior, counted separately) |
| 02_02 | [`test_02_02_system_reply_prefix`](../m2_her_text_tests.py#L144) | [S: must succeed](../README_en.md#verdict-rules) | Instruct the assistant to start every reply with HER_REPLY: and send a greeting. | The reply must start with the literal prefix. An introductory sentence, a space or a code fence before it fails. | --run-behavior (model behavior, counted separately) |
| 02_04 | [`test_02_04_system_identity_multiturn`](../m2_her_text_tests.py#L155) | [S: must succeed](../README_en.md#verdict-rules) | Set the assistant ID to AI_K72, add five unrelated turns, then ask for the ID. | The reply must still contain AI_K72 from the initial system message. | --run-behavior (model behavior, counted separately) |
| 02_05 | [`test_02_05_system_identity_isolation`](../m2_her_text_tests.py#L167) | [S: must succeed](../README_en.md#verdict-rules) | Send two independent requests with the same question but different system IDs, AI_K72 then AI_B19. | Each reply must contain its own ID and omit the other one. Additional prose is allowed. | --run-behavior (model behavior, counted separately) |

## 03 user_system — user_system user persona

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 03_01 | [`test_03_01_user_system_identity`](../m2_her_text_tests.py#L181) | [S: must succeed](../README_en.md#verdict-rules) | Put the user ID USER_P38 in an unnamed user_system message and ask for the user's ID. | This particular unnamed input must succeed and the answer must contain USER_P38. | --run-behavior (model behavior, counted separately) |
| 03_03 | [`test_03_03_user_system_multiturn`](../m2_her_text_tests.py#L192) | [S: must succeed](../README_en.md#verdict-rules) | Set the user's team to TEAM_L63 in user_system, insert five unrelated turns and ask for the team ID. | The answer must contain TEAM_L63 from the earlier user profile. | --run-behavior (model behavior, counted separately) |
| 03_04 | [`test_03_04_user_system_omitted`](../m2_her_text_tests.py#L203) | [S: must succeed](../README_en.md#verdict-rules) | Send an assistant system message and a user greeting, omitting user_system entirely. | A normal reply demonstrates that this ordinary conversation works without a user profile. | Default |

## 04 group — group scene

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 04_01 | [`test_04_01_group_scene_name`](../m2_her_text_tests.py#L214) | [S: must succeed](../README_en.md#verdict-rules) | Set SCENE_R64 in an unnamed group message, then ask which scene is active. | The answer must contain SCENE_R64, supplied only in the group message. | --run-behavior (model behavior, counted separately) |
| 04_02 | [`test_04_02_group_scene_isolation`](../m2_her_text_tests.py#L229) | [S: must succeed](../README_en.md#verdict-rules) | Ask the same question in two independent requests, changing the scene ID from SCENE_R64 to SCENE_N21. | Each reply must name the scene in its own request and omit the other ID. | --run-behavior (model behavior, counted separately) |
| 04_03 | [`test_04_03_group_omitted`](../m2_her_text_tests.py#L243) | [S: must succeed](../README_en.md#verdict-rules) | Send a normal user request with no group message. | The endpoint must return text for a conversation without a scene description. | Default |

## 05 sample_messages — Sample dialogues sample_message_*

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 05_01 | [`test_05_01_single_sample_pair`](../m2_her_text_tests.py#L249) | [S: must succeed](../README_en.md#verdict-rules) | Provide a named apple → RESULT:APPLE example, then send lemon from the real user. | The endpoint must accept the example pair before the real turn and return text. It need not imitate the capitalization. | Default |
| 05_02 | [`test_05_02_three_sample_pairs`](../m2_her_text_tests.py#L258) | [S: must succeed](../README_en.md#verdict-rules) | Give three named example pairs for apple, pear and plum, followed by a real user message saying lemon. | The three-pair input must produce a reply. Matching the examples' style is optional here. | Default |
| 05_04 | [`test_05_04_sample_vs_current_question`](../m2_her_text_tests.py#L268) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Give an apple example followed by the actual user input kiwi. Try it once with names on every message and once without any names. | The named input must produce text containing kiwi, case-insensitively. The unnamed combination must be rejected. A failed named preflight skips that rejection check. | --run-behavior (model behavior, counted separately) |
| 05_05 | [`test_05_05_samples_with_real_history`](../m2_her_text_tests.py#L291) | [S: must succeed](../README_en.md#verdict-rules) | Combine two named examples, a real mango exchange and a final kiwi user turn. Every message has a name. | The endpoint must accept this mix of examples and conversation history and return a nonblank reply. | Default |

## 06 names — name field

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 06_01 | [`test_06_01_name_omitted`](../m2_her_text_tests.py#L304) | [S: must succeed](../README_en.md#verdict-rules) | Submit one ordinary user message without a speaker name. | A missing name on this single user message must still allow a normal reply. | Default |
| 06_02 | [`test_06_02_name_unicode`](../m2_her_text_tests.py#L311) | [S: must succeed](../README_en.md#verdict-rules) | Set the user name to 小林, Alice or Zoë🙂 and ask the assistant to name the sender. | All three strings must be accepted and produce text. The returned spelling is outside this check. | Default |
| 06_03 | [`test_06_03_multiple_named_users`](../m2_her_text_tests.py#L321) | [S: must succeed](../README_en.md#verdict-rules) | Have Alice and Bob report PASS_A17 and PASS_B29. Swap the sender names in a second request while keeping the codes in the same order. | Both replies must be JSON objects mapping exactly Alice and Bob to their own codes. Swapped values, a code fence or surrounding prose fail. | --run-behavior (model behavior, counted separately) |
| 06_04 | [`test_06_04_multiple_named_assistants`](../m2_her_text_tests.py#L343) | [S: must succeed](../README_en.md#verdict-rules) | Put NOTE_A17 and NOTE_B29 in assistant messages from Alpha and Beta, then swap their names in a second request. | Each reply must be a JSON object with exactly the two assistant names mapped to their records for that request. | --run-behavior (model behavior, counted separately) |

## 07 multiturn — Multi-turn conversation

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 07_01 | [`test_07_01_two_turn_memory`](../m2_her_text_tests.py#L366) | [S: must succeed](../README_en.md#verdict-rules) | Provide the user ID HER_M41 and an assistant acknowledgment as history, then ask for the ID. | The answer must contain HER_M41 from the preceding turn. Additional text is allowed. | --run-behavior (model behavior, counted separately) |
| 07_02 | [`test_07_02_five_turn_facts`](../m2_her_text_tests.py#L378) | [S: must succeed](../README_en.md#verdict-rules) | Provide five records with independent values and ask for the values at positions 0 and 4. | The reply must contain both CEDAR_87 and FERN_24. A reply containing only the last record fails. | --run-behavior (model behavior, counted separately) |
| 07_03 | [`test_07_03_twenty_turn_history`](../m2_her_text_tests.py#L387) | [S: must succeed](../README_en.md#verdict-rules) | Supply twenty turns of independent records, then ask for records 0 and 19 by position. | The reply must contain both CEDAR_87 and MOSS_36. Neither value is supplied in the final question. | --run-behavior (model behavior, counted separately) |
| 07_04 | [`test_07_04_actual_response_roundtrip`](../m2_her_text_tests.py#L395) | [S: must succeed](../README_en.md#verdict-rules) | Ask for acknowledgment of an ID, copy the actual reply into the next request as assistant history, then ask for the ID. | Both calls must succeed. This checks whether returned text can be sent back as history, irrespective of the recalled ID. | Default |
| 07_05 | [`test_07_05_latest_fact_correction`](../m2_her_text_tests.py#L407) | [S: must succeed](../README_en.md#verdict-rules) | Give the old ID OLD_K19, correct it to NEW_T83 and ask for the corrected ID only. | The answer must contain NEW_T83 and omit OLD_K19. Listing both IDs fails. | --run-behavior (model behavior, counted separately) |
| 07_06 | [`test_07_06_conversation_isolation`](../m2_her_text_tests.py#L421) | [S: must succeed](../README_en.md#verdict-rules) | Send two independent histories with the passphrases CODE_A17 and CODE_B29. Ask for the passphrase in each. | Each answer must include its own passphrase and omit the other. Reusing the first passphrase in the second reply fails. | --run-behavior (model behavior, counted separately) |

## 08 sampling — Sampling parameters (temperature / top_p)

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 08_01 | [`test_08_01_sampling_omitted`](../m2_her_text_tests.py#L435) | [S: must succeed](../README_en.md#verdict-rules) | Send a short prompt without either temperature or top_p in the request body. | A valid reply is sufficient. The test does not infer numeric defaults from the response. | Default |
| 08_02 | [`test_08_02_temperature_valid`](../m2_her_text_tests.py#L440) | [S: must succeed](../README_en.md#verdict-rules) | Send separate non-streaming requests with temperature set to 0.01, 0.5 or 1.0. | Each value must produce a valid reply. The test does not compare randomness. | Default |
| 08_03 | [`test_08_03_temperature_invalid`](../m2_her_text_tests.py#L449) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Supply temperature as 0, −0.1, 1.01, the string “0.5” or the boolean true. | For 0 and 1.01, either a valid reply or a rejection passes, and 5xx fails (E). Negative numbers and the two wrong types must be rejected (F). | Default |
| 08_04 | [`test_08_04_top_p_valid`](../m2_her_text_tests.py#L462) | [S: must succeed](../README_en.md#verdict-rules) | Send non-streaming requests with top_p of 0.01, 0.5, 0.95 and 1.0. | All four values must yield a valid reply, including the upper boundary of 1.0. | Default |
| 08_05 | [`test_08_05_top_p_invalid`](../m2_her_text_tests.py#L471) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Set top_p to 0, −0.1, 1.01, the string “0.95” or the boolean true. | Zero allows either acceptance or rejection, with 5xx failing (E). Both out-of-range nonzero numbers and both wrong types require rejection (F). | Default |

## 09 completion_limit — Output length limit max_completion_tokens

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 09_01 | [`test_09_01_completion_limit_omitted`](../m2_her_text_tests.py#L485) | [S: must succeed](../README_en.md#verdict-rules) | Omit both max_completion_tokens and its older counterpart max_tokens from the request body. | The endpoint must reply. The case makes no assumption about its default token budget. | Default |
| 09_02 | [`test_09_02_completion_limit_valid`](../m2_her_text_tests.py#L492) | [S: must succeed](../README_en.md#verdict-rules) | Ask the same short question with budgets of 1, 2, 32, 2047 and 2048 completion tokens. | Usage must include both counts with a correct total. Output must fit the budget, and length must exactly exhaust it. Only the one-token reply may be blank. Missing counts fail. | Default |
| 09_03 | [`test_09_03_completion_limit_nonpositive`](../m2_her_text_tests.py#L500) | [E: succeed or fail, no 5xx](../README_en.md#verdict-rules) | Request zero or minus one completion tokens. | The service may reject either input or return a valid reply, including blank text. HTTP 5xx fails. No effective token ceiling is inferred. | Default |
| 09_04 | [`test_09_04_completion_limit_type`](../m2_her_text_tests.py#L513) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Set the completion budget to 1.5, the string “32”, the boolean true or null. | Reject the first three inputs (F). For null, a rejection or a valid nonblank reply passes and 5xx fails (E). | Default |
| 09_05 | [`test_09_05_completion_length_truncation`](../m2_her_text_tests.py#L524) | [S: must succeed](../README_en.md#verdict-rules) | Ask for a long continuation with 8 output tokens. If it stops naturally, try a different continuation with just 1 token. | A length finish with an exact budget count passes. Two valid natural stops skip the check. Malformed replies, missing counts or budget violations fail immediately. | Default |

## 10 response_usage — Response structure and usage

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 10_01 | [`test_10_01_response_envelope`](../m2_her_text_tests.py#L530) | [S: must succeed](../README_en.md#verdict-rules) | Inspect the ID, model, creation time and object type on an ordinary reply and across all packets of a streamed reply. | ID and model must be nonempty, created a positive integer, and model must match the configured response alias or request model. Require chat.completion for a full message and chat.completion.chunk for a delta. ID, model and time must stay constant within the reply. | Default |
| 10_02 | [`test_10_02_response_message`](../m2_her_text_tests.py#L538) | [S: must succeed](../README_en.md#verdict-rules) | Send a non-streaming request and inspect the message in its first choice. | Its role must be assistant and its content a nonblank string. Whitespace alone fails. | Default |
| 10_03 | [`test_10_03_finish_reason_stop`](../m2_her_text_tests.py#L544) | [S: must succeed](../README_en.md#verdict-rules) | Use an OK example to encourage a short reply with 128 tokens, then allow 512 if the first reply is truncated. | A valid stop passes regardless of the exact wording. Two valid length finishes skip the check. Enforce the budget when counts are present. A length finish needs an exact count. | Default |
| 10_04 | [`test_10_04_usage_total_tokens`](../m2_her_text_tests.py#L549) | [S: must succeed](../README_en.md#verdict-rules) | Read usage from replies made with a one-token or 32-token output budget. | Both must report a positive integer total_tokens. A one-token reply may be blank. The total counts input as well as output. | Default |
| 10_05 | [`test_10_05_usage_breakdown_math`](../m2_her_text_tests.py#L558) | [S: must succeed](../README_en.md#verdict-rules) | Ask a short question and read the reported total and optional token breakdown. | Usage is required and total_tokens must be a nonnegative integer. Both component counts may be absent. If either appears, require both as nonnegative integers adding up to the total. | Default |
| 10_06 | [`test_10_06_sensitivity_field_types`](../m2_her_text_tests.py#L572) | [S: must succeed](../README_en.md#verdict-rules) | Send an ordinary message and look for input_sensitive, output_sensitive and their two companion _type fields. | Any flag returned must be boolean and any type code must be an integer. All four may be absent. The log records how many occurred. Moderation accuracy is outside this case. | Default; missing fields are only recorded |
| 10_07 | [`test_10_07_prompt_tokens_across_modes`](../m2_her_text_tests.py#L586) | [S: must succeed](../README_en.md#verdict-rules) | Try a simple conversation and one using all seven named roles. For each, send the original and a version with 256 extra phrases in the last message, in both modes. Explicitly request usage in OpenAI streaming mode. | All four calls per variant need full counts. Adding input must increase prompt_tokens in each mode. Cross-mode equality is required only if enabled with prompt_tokens_equal. | --run-compat; needs prompt_tokens |

## 11 error_codes — Error handling

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 11_01 | [`test_11_01_invalid_model`](../m2_her_text_tests.py#L636) | [F: must fail](../README_en.md#verdict-rules) | Use the configured model as a healthy control. Then omit model or supply an unknown name, an empty string, null or 42. | Reject all five inputs. The test sends the target body directly so the client cannot fill in a missing model. | Default |
| 11_02 | [`test_11_02_invalid_messages`](../m2_her_text_tests.py#L652) | [F: must fail](../README_en.md#verdict-rules) | Omit messages or replace the list with null, the string hello or an empty object. | All four requests must be rejected. An ordinary assistant reply fails even if its response structure is valid. | Default |
| 11_03 | [`test_11_03_invalid_role`](../m2_her_text_tests.py#L665) | [F: must fail](../README_en.md#verdict-rules) | Keep the user text Hello and omit its role, use an unknown role name or set the role to 42. | Reject each message whose role is missing, unknown or numeric. | Default |
| 11_04 | [`test_11_04_invalid_content`](../m2_her_text_tests.py#L686) | [F: must fail](../README_en.md#verdict-rules) | On the native route, omit the user content or send null, a number, an object or a parts array containing text, an image, video or audio. | Reject each of these eight concrete inputs. The media examples use placeholder bytes, so this checks the submitted shapes, not the handling of all decodable media. | Default; native only |
| 11_05 | [`test_11_05_invalid_name_type`](../m2_her_text_tests.py#L724) | [F: must fail](../README_en.md#verdict-rules) | Add a numeric name (42), an empty object or an empty list to an otherwise valid user message. | Reject each non-string name. Omitting the name on an ordinary user message is the separate valid case 06_01. | Default |
| 11_06 | [`test_11_06_authentication_errors`](../m2_her_text_tests.py#L737) | [F: must fail](../README_en.md#verdict-rules) | Verify the endpoint with its working Bearer credentials, then omit Authorization or replace it with an invalid Bearer value. | Both modified requests must be rejected. Skip if Bearer auth is disabled or another configured credential such as Cookie, X-API-Key or an access_token query parameter could authorize the request independently. | Default; bearer authentication only |
| 11_07 | [`test_11_07_invalid_request_envelope`](../m2_her_text_tests.py#L771) | [F: must fail](../README_en.md#verdict-rules) | Send truncated JSON, an empty top-level array, or a request with stream set to the string “true” or the number 1. | Reject all four. Automatically repairing the malformed input and returning a reply fails the check. | Default |
| 11_08 | [`test_11_08_legacy_sample_role_spelling`](../m2_her_text_tests.py#L795) | [F: must fail](../README_en.md#verdict-rules) | Start with a working named example pair and replace just one role: sample_message_user with user_sample_message, or sample_message_ai with ai_sample_message. | With all other fields unchanged, the canonical spelling must work before checking rejection of the old spelling. A failed canonical control skips this check. | Default; native only; skipped if the control request fails |
| 11_09 | [`test_11_09_invalid_message_item`](../m2_her_text_tests.py#L812) | [F: must fail](../README_en.md#verdict-rules) | Keep messages as an array but replace its only element with null, a string, a number or another array. | Reject all four malformed elements even though the outer array itself is valid. | Default |

## 12 long_context — Long input and the 64K context

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 12_01 | [`test_12_01_long_system`](../m2_her_text_tests.py#L822) | [S: must succeed](../README_en.md#verdict-rules) | Place 500 lines of background in the system message, with markers at the beginning, middle and end. Ask for a brief response. | The long system message must produce a normal reply. Marker recall and a specific token count are outside this case. | --run-slow |
| 12_02 | [`test_12_02_long_persona_and_samples`](../m2_her_text_tests.py#L840) | [S: must succeed](../README_en.md#verdict-rules) | Put roughly 500 lines of background in a user profile or a sample assistant reply. For the latter, include its sample user turn. End both variants with a real user request. | Both placements must be accepted and yield a reply. Recalling the supplied background is optional. | --run-slow |
| 12_03 | [`test_12_03_context_within_64k`](../m2_her_text_tests.py#L861) | [S: must succeed](../README_en.md#verdict-rules) | Use runtime calibration or a supplied sample to find input within 384 tokens of the configured window that still fits with a small completion budget. Calibration probes with one output token, then normally reserves 64 for the target. | The target must succeed and return complete token counts. Its measured prompt_tokens must match the sample. Missing or changed counts fail. | --run-slow; --context-fixture can supply measured inputs |
| 12_04 | [`test_12_04_context_over_64k`](../m2_her_text_tests.py#L879) | [F: must fail](../README_en.md#verdict-rules) | Send the same near-window input with its smaller budget to verify the prompt count. Increase the requested output until the sum exceeds the window. Automatically prepared samples request 2048 output tokens here. | The within-window control must succeed with matching counts. The default requires rejection of the over-window request. A custom acceptance contract must specify an answer marker to retain. Preparation or transport failures do not prove rejection at the limit. | --run-slow; --context-fixture can supply measured inputs |

## 13 role_combo — Seven-role combinations

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 13_01 | [`test_13_01_all_seven_roles`](../m2_her_text_tests.py#L906) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Build one conversation with all seven roles. Give every message a name, then omit names only on the group and the two sample messages. | The fully named version must succeed (S). The version with these three names omitted must be rejected (F) after a healthy named control. Standalone group and user_system inputs have their own acceptance cases. | Default |
| 13_02 | [`test_13_02_persona_samples_named_history`](../m2_her_text_tests.py#L917) | [S: must succeed](../README_en.md#verdict-rules) | Extend a named seven-role conversation with item IDs for two visitors. Ask for assistant ID, user profile, scene, passphrase and both items in that order. | Require AI_K72, USER_P38, SCENE_R64, CODE_V59, ITEM_A73 and ITEM_B84 in that order, separated by vertical bars. The RESULT: prefix, separator whitespace and outer bars are optional. Missing, reordered or extra answers fail. | --run-behavior (model behavior, counted separately) |
| 13_03 | [`test_13_03_long_history_small_output`](../m2_her_text_tests.py#L941) | [S: must succeed](../README_en.md#verdict-rules) | Submit twenty turns of history with an output budget of only 64 tokens. | Require complete counts and at most 64 output tokens. If the finish reason is length, require exactly 64. Recall accuracy is outside this check. | Default |
| 13_04 | [`test_13_04_roles_with_sampling`](../m2_her_text_tests.py#L948) | [S: must succeed](../README_en.md#verdict-rules) | Send all seven named roles together, including the scene, examples and real history, with temperature=0.5 and top_p=0.95. | This combination of roles and sampling parameters must produce a valid reply. | Default |
| 13_05 | [`test_13_05_one_special_name_omitted`](../m2_her_text_tests.py#L958) | [F: must fail](../README_en.md#verdict-rules) | Take a working seven-role conversation. Delete exactly one name, on user_system, group, sample_message_user or sample_message_ai, keeping all other messages unchanged. | Check the fully named control first, then require rejection for each of these four single deletions. This applies to this specific combined conversation. | Default |

## 16 guide_alignment — Structures from the official guide

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 16_01 | [`test_16_01_guide_role_structures`](../m2_her_text_tests.py#L969) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Try three guide-style conversations: a basic question, a navigator speaking to a trainee, and a chat preceded by an example. Run each using the original unnamed messages and then with names on every message. | Both basic variants must succeed. For role-play and examples, the named inputs must succeed and the unnamed inputs must be rejected. Use a healthy named control before checking rejection. | Default |
| 16_04 | [`test_16_04_context_recall`](../m2_her_text_tests.py#L985) | [S: must succeed](../README_en.md#verdict-rules) | Place markers at the start, middle and end of an 800-record history and ask for all three together. | Require BEGIN_P38, MIDDLE_P49 and END_P50 anywhere in the reply. Their order and surrounding text may vary. | --run-behavior (model behavior, counted separately); --run-slow |

## 17 candidate_count — n multiple replies

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 17_01 | [`test_17_01_n_default_single_choice`](../m2_her_text_tests.py#L1003) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Try omitting the number of candidates n, then explicitly request null, 0 or −1. | Omitting n must yield one candidate (S). The other values may be rejected or yield one candidate, with 5xx failing (E). Check response identity, model and timestamp on accepted replies. | Default; native only |
| 17_02 | [`test_17_02_n_candidate_count`](../m2_her_text_tests.py#L1020) | [S: must succeed](../README_en.md#verdict-rules) | Request one or two candidate replies from a non-streaming call. | Require exactly n complete replies with distinct indices covering 0 through n−1, valid finish reasons, usage and envelope fields. Two candidates may have identical text. | Default; native only |
| 17_03 | [`test_17_03_n_one_stream`](../m2_her_text_tests.py#L1028) | [S: must succeed](../README_en.md#verdict-rules) | Turn on streaming and explicitly ask for one candidate with n=1. | Reassemble one complete response. Choice fragments must use index 0, and the reply ID, model and creation time must stay consistent. | Default; native only |
| 17_04 | [`test_17_04_n_invalid_type`](../m2_her_text_tests.py#L1049) | [F: must fail](../README_en.md#verdict-rules) | Supply n as 1.5, the string “2”, true, false, an object, a list or 2 to the power of 63, beyond the signed 64-bit range. | Reject all seven inputs. The two booleans must not be accepted as integer candidate counts. | Default; native only |
| 17_05 | [`test_17_05_n_stream_conflict`](../m2_her_text_tests.py#L1054) | [F: must fail](../README_en.md#verdict-rules) | Check that ordinary streaming works. Request two non-streamed candidates, then change only stream to true while keeping n=2. | A failed ordinary streaming preflight skips the case. Failure to get two non-streamed replies fails the case. After they succeed, the streamed n=2 request must be rejected. | Default; native only |
| 17_06 | [`test_17_06_n_tools_conflict`](../m2_her_text_tests.py#L1064) | [F: must fail](../README_en.md#verdict-rules) | After a healthy ordinary non-streaming preflight, request two candidates without tools. Then send n=1 with a ping function tool. If both controls work, request n=2 with that same tool. | A failed ordinary preflight skips the case. The first control must return two candidates. A valid rejection of the n=1 tool control skips the case because the service may reject tools on their own. HTTP 5xx or a malformed control response fails. Only after that control succeeds must the combined n=2 request be rejected. | Default; native only. The tool control must accept n=1 to reach the target. |
| 17_07 | [`test_17_07_n_with_roles_and_parameters`](../m2_her_text_tests.py#L1087) | [S: must succeed](../README_en.md#verdict-rules) | Use all seven named roles with n=2, temperature=0.7 and top_p=0.95. Request 100 output tokens using either the old max_tokens field or max_completion_tokens. | Both variants must return two complete candidates and valid envelope fields and usage. Aggregate usage does not establish token consumption per candidate. | Default; native only |
| 17_08 | [`test_17_08_n_configured_boundary`](../m2_her_text_tests.py#L1110) | [Depends on variant; see checks](../README_en.md#verdict-rules) | Request the configured maximum N non-streamed candidates (four by default). The above-limit variant first repeats that control, then requests N+1. | Exactly N complete replies are required at the boundary and N+1 must be rejected. A failed N request fails the case and cannot stand in for the over-limit result. | Default; --n-limit changes the limit |

## 18 request_metadata — metadata / user / mask_sensitive_info

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 18_01 | [`test_18_01_request_metadata_valid`](../m2_her_text_tests.py#L1130) | [S: must succeed](../README_en.md#verdict-rules) | Try ordinary string metadata, a 255-character ASCII key and value, a string user, and each boolean mask_sensitive_info setting. The boundary variant additionally sends a key and value of 85 three-byte Chinese characters. | All five targets must succeed with valid envelope fields. Record how the provider handles the extra 255-byte Chinese input: a valid reply or rejection passes, and 5xx fails (E). Provider logs and masking effects are outside this check. | Default; native only |
| 18_02 | [`test_18_02_request_metadata_invalid_type`](../m2_her_text_tests.py#L1181) | [F: must fail](../README_en.md#verdict-rules) | Test three malformed metadata values (string, list, numeric object value), two invalid user values (number, object), and two invalid mask_sensitive_info values (string, number). | Reject all seven, including the string “true” supplied in place of a boolean. | Default; native only |
| 18_03 | [`test_18_03_metadata_length_boundary`](../m2_her_text_tests.py#L1189) | [F: must fail](../README_en.md#verdict-rules) | Use 256 ASCII characters in the metadata key or value in separate requests. Repeat each with 85 three-byte Chinese characters and one ASCII character, totaling 86 characters but 256 UTF-8 bytes. | Reject both ASCII targets (F). The multibyte probes accept either a valid reply or rejection and fail on 5xx (E). These additional observations do not require every provider to count UTF-8 bytes. | Default; native only |

## 19 language_consistency — Reply language

| Case ID | Function | Verdict rule | What gets sent | How to read the result | Run condition |
|:---:|:---|:---|:---|:---|:---|
| 19_01 | [`test_19_01_reply_follows_user_language`](../m2_her_text_tests.py#L1229) | [S: must succeed](../README_en.md#verdict-rules) | Ask for weekend relaxation ideas in eleven language or script variants: simplified and traditional Chinese, English, Japanese, Korean, Spanish, French, German, Portuguese, Russian and Arabic. Score each streaming mode separately. | Sample up to three valid replies per variant. Two clear matches pass, two clear wrong or mixed-language replies fail, and insufficient evidence after three skips the case. Request and format errors fail immediately. | --run-behavior (model behavior, counted separately) |
| 19_04 | [`test_19_04_multiturn_language_retention`](../m2_her_text_tests.py#L1267) | [S: must succeed](../README_en.md#verdict-rules) | Write the persona in one language and all three travel turns plus the final rainy-day question in another. Try all twelve ordered pairs among Chinese, English, Japanese and Korean. | The reply should stay in the user's established language. Per pair and mode, two clear matches in up to three valid replies pass, two clear wrong or mixed replies fail, and unresolved evidence after three skips. Request and format errors fail immediately. | --run-behavior (model behavior, counted separately) |

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
