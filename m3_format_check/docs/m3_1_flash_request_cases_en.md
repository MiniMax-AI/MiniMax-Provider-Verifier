# M3_1_Flash Request-Field Contract Cases
> File: `m3_format_check/m3_1_flash_request_test.py`
> Naming: `test_<module id>_<field>`, one parametrized function per request field; the parameter id is the case ID
> Modules: **26**; cases: **130** (expect 200: 116, expect 400: 14)

## Verdict rule

Each case deviates from a minimal valid request in a single request field and checks the transport contract only:

- **Expect 200**: HTTP 200, non-empty `choices`, `choices[0].message.role == "assistant"`
- **Expect 400**: HTTP 400 and the body carries no `choices` (an invalid field must be rejected, not silently accepted)

Generated text, language and capability effects are not asserted; those belong to the behavioural suites. Requests go through `oai_chat_verbatim` so the helper never injects an output budget or rewrites `stream`, which keeps omitted / explicit-null / wrong-type cases on the wire as authored.

Case ID prefixes: `REQ-` valid input, `ERR-` invalid input or accepted edge value, `RES-` structured / predicted output requests.

## Module overview

| Module | Field | Topic | Cases |
|:---:|:---|:---|:---:|
| 01 | `model` | model field | 2 |
| 02 | `messages` | messages structure and message forms | 17 |
| 03 | `messages[].content[type=image_url]` | image_url image input | 18 |
| 04 | `max_completion_tokens` | max_completion_tokens budget | 4 |
| 05 | `max_tokens` | legacy max_tokens | 2 |
| 06 | `stop` | stop sequences | 3 |
| 07 | `temperature` | temperature | 4 |
| 08 | `top_p` | top_p | 5 |
| 09 | `presence_penalty` | presence_penalty | 3 |
| 10 | `frequency_penalty` | frequency_penalty | 3 |
| 11 | `logit_bias` | logit_bias | 6 |
| 12 | `seed` | seed | 4 |
| 13 | `n` | n (choice count) | 2 |
| 14 | `reasoning_effort` | reasoning_effort | 9 |
| 15 | `logprobs` | logprobs | 1 |
| 16 | `response_format` | response_format structured output | 17 |
| 17 | `prediction` | prediction (predicted output) | 6 |
| 18 | `modalities` | modalities | 2 |
| 19 | `audio` | audio | 1 |
| 20 | `prompt_cache_key` | prompt_cache_key | 2 |
| 21 | `prompt_cache_options` | prompt cache options default | 1 |
| 22 | `web_search_options` | web_search_options | 5 |
| 23 | `metadata` | metadata | 3 |
| 24 | `store` | store | 3 |
| 25 | `user` | legacy user | 2 |
| 26 | `service_tier` | service_tier | 5 |

---

## 01 model — model field

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-001 | Minimal request with a single user string | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| ERR-023 | model is an array | `model=[]` | 400 |

## 02 messages — messages structure and message forms

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| ERR-027 | messages is an empty array | `[]` | 400 |
| ERR-026 | messages is null | `null` | 400 |
| ERR-029 | message element is a number | `[1]` | 400 |
| REQ-009 | Two consecutive system messages (no forced alternation) | `[{"role": "system", "content": "Reply in English."}, {"role": "system", "content": "Keep the answer short."}, {"role": "user", "content": "Hello"}]` | 200 |
| REQ-016 | tool message content as a text-part array | `assistant tool_calls + tool content=[text part]` | 200 |
| ERR-030 | message missing role | `[{"content": "Hello"}]` | 400 |
| ERR-032 | role is null | `[{"role": null, "content": "Hello"}]` | 400 |
| REQ-003 | Multi-turn history with assistant text | `[{"role": "user", "content": "Remember the code A7."}, {"role": "assistant", "content": "Noted."}, {"role": "user", "content": "What is the code?"}]` | 200 |
| REQ-008 | Same role with different participant names | `[{"role": "user", "name": "a", "content": "Please compare plan A."}, {"role": "user", "name": "b", "content": "Also compare plan B."}]` | 200 |
| REQ-015 | assistant.refusal explicitly null | `[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hello", "refusal": null}, {"role": "user", "content": "Continue"}]` | 200 |
| REQ-012 | assistant history as text-part array | `[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": [{"type": "text", "text": "Hello."}]}, {"role": "user", "content": "Continue"}]` | 200 |
| REQ-014 | assistant.refusal as a string | `[{"role": "user", "content": "Earlier request"}, {"role": "assistant", "content": "I cannot help with the earlier request.", "refusal": "I cannot help with the earlier request."}, {"role": "user", "content": "Please explain caching."}]` | 200 |
| REQ-148 | Long single user message within the context window | `one long user message (~80k characters)` | 200 |
| REQ-149 | 103-message long history within the context window | `51 user/assistant pairs + 1 user, 103 messages` | 200 |
| REQ-010 | user content with multiple text parts | `[{"role": "user", "content": [{"type": "text", "text": "First paragraph."}, {"type": "text", "text": "Second paragraph, please summarize."}]}]` | 200 |
| REQ-011 | String with CJK, emoji and escapes | `[{"role": "user", "content": "输入有中文🙂、引号\"、反斜线\\和换行\n请简短回应。"}]` | 200 |
| REQ-024 | Empty text part alongside a non-empty one | `[{"role": "user", "content": [{"type": "text", "text": ""}, {"type": "text", "text": "Please explain caching."}]}]` | 200 |

## 03 image_url — image_url image input

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-020 | PNG image as data URL | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<PNG data URL>"}}]}]` | 200 |
| REQ-019 | JPEG image as data URL | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<JPEG data URL>"}}]}]` | 200 |
| REQ-021 | WEBP image as data URL | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<WEBP data URL>"}}]}]` | 200 |
| REQ-022 | Static GIF image as data URL | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<GIF data URL>"}}]}]` | 200 |
| REQ-028 | Same image sent twice | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}, {"type": "image_url", "image_url": {"url": "<PNG data ...` | 200 |
| REQ-025 | Image only, no text part | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}]}]` | 200 |
| REQ-027 | Two images: HTTPS URL + data URL | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<HTTPS image URL>"}}, {"type": "image_url", "image_url": {"url": "<PNG da...` | 200 |
| REQ-034 | Per-image detail low and high in one message | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "low"}}, {"type": "image_url", "image_url": {"...` | 200 |
| REQ-026 | text-image-text interleaving | `[{"role": "user", "content": [{"type": "text", "text": "Look at this image first."}, {"type": "image_url", "image_url": {"url": "<PNG data URL>"}}, {"type": "text", "...` | 200 |
| REQ-030 | detail=low | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "low"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |
| REQ-031 | detail=high | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "high"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |
| ERR-041 | image_url object missing url | `[{"role": "user", "content": [{"type": "image_url", "image_url": {}}]}]` | 400 |
| ERR-042 | image_url.url is not a string | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": 12}}]}]` | 400 |
| REQ-033 | detail omitted (defaults to auto) | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |
| ERR-045 | Image part inside a system message is accepted | `[{"role": "system", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}]}, {"role": "user", "content": "Hello"}]` | 200 |
| REQ-023 | HTTPS image URL | `[{"role": "user", "content": [{"type": "text", "text": "Describe the image."}, {"type": "image_url", "image_url": {"url": "<HTTPS image URL>"}}]}]` | 200 |
| ERR-044 | detail explicitly null is treated as omitted | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": null}}]}]` | 200 |
| REQ-029 | detail=auto | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "auto"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |

## 04 max_completion_tokens — max_completion_tokens budget

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-060 | Small completion budget together with reasoning_effort | `{"max_completion_tokens": 32, "reasoning_effort": "low"}` | 200 |
| ERR-076 | max_completion_tokens is a float | `{"max_completion_tokens": 8.5}` | 400 |
| REQ-061 | No output budget set at all | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| REQ-131 | max_completion_tokens explicitly null | `{"max_completion_tokens": null}` | 200 |

## 05 max_tokens — legacy max_tokens

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-132 | max_tokens explicitly null | `{"max_tokens": null}` | 200 |
| REQ-062 | Legacy max_tokens | `{"max_tokens": 64}` | 200 |

## 06 stop — stop sequences

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| ERR-081 | stop element is not a string | `{"stop": ["a", 1]}` | 400 |
| REQ-067 | stop with four sequences | `{"stop": ["#A#", "#B#", "#C#", "#D#"]}` | 200 |
| REQ-068 | stop explicitly null | `{"stop": null}` | 200 |

## 07 temperature — temperature

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-040 | temperature=0 | `{"temperature": 0}` | 200 |
| REQ-041 | temperature=0.2 | `{"temperature": 0.2}` | 200 |
| REQ-042 | temperature=2 | `{"temperature": 2}` | 200 |
| REQ-125 | temperature explicitly null | `{"temperature": null}` | 200 |

## 08 top_p — top_p

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| ERR-065 | top_p below 0 | `{"top_p": -0.1}` | 400 |
| ERR-066 | top_p above 1 | `{"top_p": 1.1}` | 400 |
| REQ-044 | top_p=0.1 | `{"top_p": 0.1}` | 200 |
| REQ-045 | top_p=1 | `{"top_p": 1}` | 200 |
| REQ-126 | top_p explicitly null | `{"top_p": null}` | 200 |

## 09 presence_penalty — presence_penalty

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-049 | presence_penalty=-2 | `{"presence_penalty": -2}` | 200 |
| REQ-050 | presence_penalty=0 | `{"presence_penalty": 0}` | 200 |
| REQ-051 | presence_penalty=2 | `{"presence_penalty": 2}` | 200 |

## 10 frequency_penalty — frequency_penalty

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-046 | frequency_penalty=-2 | `{"frequency_penalty": -2}` | 200 |
| REQ-047 | frequency_penalty=0 | `{"frequency_penalty": 0}` | 200 |
| REQ-048 | frequency_penalty=2 | `{"frequency_penalty": 2}` | 200 |

## 11 logit_bias — logit_bias

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-052 | logit_bias=-100 | `{"logit_bias": {"1000": -100}}` | 200 |
| REQ-053 | logit_bias=-1 | `{"logit_bias": {"1000": -1}}` | 200 |
| REQ-054 | logit_bias=0 | `{"logit_bias": {"1000": 0}}` | 200 |
| REQ-055 | logit_bias=1 | `{"logit_bias": {"1000": 1}}` | 200 |
| REQ-056 | logit_bias=100 | `{"logit_bias": {"1000": 100}}` | 200 |
| REQ-129 | logit_bias explicitly null | `{"logit_bias": null}` | 200 |

## 12 seed — seed

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-063 | Same seed sent twice | `2  requests: {"seed": 42}` | 200 |
| REQ-064 | Minimum int64 seed | `{"seed": -9223372036854775808}` | 200 |
| REQ-065 | Maximum int64 seed | `{"seed": 9223372036854775807}` | 200 |
| REQ-133 | seed explicitly null | `{"seed": null}` | 200 |

## 13 n — n (choice count)

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-058 | n omitted defaults to one choice | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| ERR-074 | n is a float | `{"n": 1.5}` | 400 |

## 14 reasoning_effort — reasoning_effort

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-071 | reasoning_effort=low | `{"reasoning_effort": "low"}` | 200 |
| REQ-072 | reasoning_effort=medium | `{"reasoning_effort": "medium"}` | 200 |
| REQ-073 | reasoning_effort=high | `{"reasoning_effort": "high"}` | 200 |
| REQ-074 | reasoning_effort=xhigh | `{"reasoning_effort": "xhigh"}` | 200 |
| REQ-075 | reasoning_effort=max | `{"reasoning_effort": "max"}` | 200 |
| REQ-134 | reasoning_effort explicitly null | `{"reasoning_effort": null}` | 200 |
| REQ-077 | Switch reasoning_effort between two turns | `2  requests: {"reasoning_effort": "low"}` | 200 |
| REQ-076 | reasoning_effort omitted uses model default | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| ERR-083 | reasoning_effort has the wrong type | `{"reasoning_effort": ["low"]}` | 400 |

## 15 logprobs — logprobs

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-081 | logprobs=false | `{"logprobs": false}` | 200 |

## 16 response_format — response_format structured output

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| RES-063 | response_format accepted (json_schema) | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-064 | response_format.type=text | `{"response_format": {"type": "text"}}` | 200 |
| RES-145 | type=text does not require JSON | `{"response_format": {"type": "text"}}` | 200 |
| RES-146 | JSON mode returns a JSON object | `{"response_format": {"type": "json_object"}}` | 200 |
| RES-065 | json_schema object | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-066 | json_schema.name | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-067 | json_schema.description | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-068 | json_schema.schema | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-069 | json_schema.strict | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-070 | schema.type with nullable property | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-071 | schema.properties | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-072 | schema.required | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-073 | schema.additionalProperties=false | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-148 | strict schema output on normal completion | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-150 | Truncation under a small budget is classified separately | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-075 | schema enum with null | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-169 | Scalar, object, array and null types | `{"response_format": {"type": "json_schema", "json_schema": {"name": "types_card", "strict": true, "schema": {"type": "object", "properties": {"s": ...` | 200 |

## 17 prediction — prediction (predicted output)

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| RES-088 | prediction object | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-089 | prediction.type=content | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-090 | prediction.content string | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-091 | prediction.content[*].type | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-092 | prediction.content[*].text | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-161 | prediction content as string and as text-part array | `2  requests: {"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |

## 18 modalities — modalities

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-099 | modalities=[text] | `{"modalities": ["text"]}` | 200 |
| REQ-143 | modalities explicitly null | `{"modalities": null}` | 200 |

## 19 audio — audio

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-144 | audio explicitly null | `{"audio": null}` | 200 |

## 20 prompt_cache_key — prompt_cache_key

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-107 | Same prompt_cache_key sent twice | `2  requests: {"prompt_cache_key": "suite-prefix"}` | 200 |
| REQ-145 | prompt_cache_key explicitly null | `{"prompt_cache_key": null}` | 200 |

## 21 prompt_cache_options — prompt cache options default

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-108 | Cache options omitted (implicit caching default) | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |

## 22 web_search_options — web_search_options

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-120 | web_search_options context=low | `{"web_search_options": {"search_context_size": "low"}}` | 200 |
| REQ-121 | web_search_options context=medium | `{"web_search_options": {"search_context_size": "medium"}}` | 200 |
| REQ-122 | web_search_options context=high | `{"web_search_options": {"search_context_size": "high"}}` | 200 |
| REQ-123 | web_search_options with full approximate location | `{"web_search_options": {"user_location": {"type": "approximate", "approximate": {"city": "San Francisco", "country": "US", "region": "California", ...` | 200 |
| REQ-124 | web_search_options with country only | `{"web_search_options": {"user_location": {"type": "approximate", "approximate": {"country": "US"}}}}` | 200 |

## 23 metadata — metadata

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-086 | metadata with one key | `{"metadata": {"suite": "format-check"}, "store": true}` | 200 |
| REQ-088 | metadata with empty string value | `{"metadata": {"case": ""}, "store": true}` | 200 |
| REQ-138 | metadata explicitly null | `{"metadata": null}` | 200 |

## 24 store — store

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-089 | store=false | `{"store": false}` | 200 |
| REQ-090 | store=true | `{"store": true}` | 200 |
| REQ-139 | store explicitly null | `{"store": null}` | 200 |

## 25 user — legacy user

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-092 | Legacy user string | `{"user": "synthetic-user-hash"}` | 200 |
| REQ-141 | user explicitly null | `{"user": null}` | 200 |

## 26 service_tier — service_tier

| Case ID | Scenario | Key request | Expect |
|:---:|:---|:---|:---:|
| REQ-093 | service_tier=auto | `{"service_tier": "auto"}` | 200 |
| REQ-094 | service_tier=default | `{"service_tier": "default"}` | 200 |
| REQ-095 | service_tier=flex | `{"service_tier": "flex"}` | 200 |
| REQ-096 | service_tier=priority | `{"service_tier": "priority"}` | 200 |
| REQ-142 | service_tier explicitly null | `{"service_tier": null}` | 200 |
