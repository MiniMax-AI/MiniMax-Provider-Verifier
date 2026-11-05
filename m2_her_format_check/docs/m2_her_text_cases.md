# M2-Her 文本与角色格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_text_tests.py`](../m2_her_text_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**17**；case 函数数：**80**；pytest 收集 items 数：**343**
> 预期值：取自 MiniMax 官方接口的实测结果（2026-11-05）；判定规则见 [README](../README.md)。
> “请求失败”：HTTP 状态码非 200，或 HTTP 200 但响应中业务码非 0 / 带 error 对象，且没有返回回复内容；不比对具体的错误码和错误信息。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 01 | basic_text | 基础文本 | 6 |
| 02 | system_persona | system 人设 | 4 |
| 03 | user_system | user_system 用户设定 | 3 |
| 04 | group | group 场景 | 3 |
| 05 | sample_messages | 示例对话 sample_message_* | 4 |
| 06 | names | name 字段 | 4 |
| 07 | multiturn | 多轮对话 | 6 |
| 08 | sampling | 采样参数（temperature / top_p） | 5 |
| 09 | completion_limit | 输出长度上限 max_completion_tokens | 5 |
| 10 | response_usage | 响应结构与 usage | 7 |
| 11 | error_codes | 错误处理 | 9 |
| 12 | long_context | 长输入与 64K 上下文 | 4 |
| 13 | role_combo | 七种角色组合 | 5 |
| 16 | guide_alignment | 官网指南中的写法 | 2 |
| 17 | candidate_count | n 多条回复 | 8 |
| 18 | request_metadata | metadata / user / mask_sensitive_info | 3 |
| 19 | language_consistency | 回复语言 | 2 |

---

## 01 basic_text — 基础文本

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 01_01 | [`test_01_01_minimal_user_message`](../m2_her_text_tests.py#L71) | 只发一条 user 消息，不带 system、name 或任何可选参数；流式、非流式各测一次。 | 请求成功（HTTP 200、业务码 0），返回一条非空的 assistant 回复；流式数据能完整解析，且只有一个结束原因。 | 默认运行 |
| 01_02 | [`test_01_02_system_user_chat`](../m2_her_text_tests.py#L75) | system 设为“友好的助手”，user 说“你好”。 | 请求成功，回复格式正确、内容非空。 | 默认运行 |
| 01_03 | [`test_01_03_chinese_text`](../m2_her_text_tests.py#L82) | 用中文请模型写一句简短问候。 | 回复里有中文，且没有乱码（U+FFFD）。 | 需 --run-behavior（模型行为，单独统计） |
| 01_04 | [`test_01_04_english_text`](../m2_her_text_tests.py#L94) | 用英文请模型只用英文写一句问候。 | 回复里有英文单词，且没有中文。 | 需 --run-behavior（模型行为，单独统计） |
| 01_05 | [`test_01_05_text_escaping_unicode`](../m2_her_text_tests.py#L105) | user 消息里包含双引号、反斜杠、换行和 emoji。 | 请求成功，响应能按 UTF-8 / JSON 正常解析。只检查格式，不检查是否原样复述（原样复述见 16_03）。 | 默认运行 |
| 01_06 | [`test_01_06_multilingual_input`](../m2_her_text_tests.py#L121) | 中文问句里夹着日文、韩文、阿拉伯文、俄文或带重音符号的问候语。 | 各种文字都能正常提交，回复格式正确。不要求翻译或提取（提取见 16_02）。 | 默认运行 |

## 02 system_persona — system 人设

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 02_01 | [`test_02_01_system_identity`](../m2_her_text_tests.py#L133) | system 设定身份编号 AI_K72，user 让模型只回答自己的编号。 | 回复包含 AI_K72。 | 需 --run-behavior（模型行为，单独统计） |
| 02_02 | [`test_02_02_system_reply_prefix`](../m2_her_text_tests.py#L143) | system 要求每次回复以 HER_REPLY: 开头，user 说“你好”。 | 回复以 HER_REPLY: 开头。 | 需 --run-behavior（模型行为，单独统计） |
| 02_04 | [`test_02_04_system_identity_multiturn`](../m2_her_text_tests.py#L154) | system 设定身份后，插入 4 轮无关对话，再问身份。 | 回复仍包含 AI_K72。 | 需 --run-behavior（模型行为，单独统计） |
| 02_05 | [`test_02_05_system_identity_isolation`](../m2_her_text_tests.py#L166) | 两个独立请求分别把身份设为 AI_K72 和 AI_B19，问同一个问题。 | 每次只回答本次请求设定的编号，不出现另一次的编号。 | 需 --run-behavior（模型行为，单独统计） |

## 03 user_system — user_system 用户设定

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 03_01 | [`test_03_01_user_system_identity`](../m2_her_text_tests.py#L180) | 只在 user_system 里写用户编号 USER_P38，然后问用户编号。 | 回复包含 USER_P38。 | 需 --run-behavior（模型行为，单独统计） |
| 03_03 | [`test_03_03_user_system_multiturn`](../m2_her_text_tests.py#L191) | user_system 写小组编号 TEAM_L63，插入 4 轮对话后再问。 | 回复包含 TEAM_L63。 | 需 --run-behavior（模型行为，单独统计） |
| 03_04 | [`test_03_04_user_system_omitted`](../m2_her_text_tests.py#L202) | 只有 system 和 user，没有 user_system。 | user_system 是可选的，请求正常成功。 | 默认运行 |

## 04 group — group 场景

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 04_01 | [`test_04_01_group_scene_name`](../m2_her_text_tests.py#L213) | 只在 group 消息里写场景编号 SCENE_R64，然后问当前场景。 | 回复包含 SCENE_R64。 | 需 --run-behavior（模型行为，单独统计） |
| 04_02 | [`test_04_02_group_scene_isolation`](../m2_her_text_tests.py#L228) | 同一个问题发两次，分别配场景 SCENE_R64 和 SCENE_N21。 | 每次只回答本次请求的场景编号。 | 需 --run-behavior（模型行为，单独统计） |
| 04_03 | [`test_04_03_group_omitted`](../m2_her_text_tests.py#L242) | 普通 user 请求，没有 group。 | group 是可选的，请求正常成功。 | 默认运行 |

## 05 sample_messages — 示例对话 sample_message_*

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 05_01 | [`test_05_01_single_sample_pair`](../m2_her_text_tests.py#L248) | 一组示例对话（示例 user + 示例 ai，都带 name）后接真实提问。 | 请求成功，回复格式正确；不要求模仿示例格式。 | 默认运行 |
| 05_02 | [`test_05_02_three_sample_pairs`](../m2_her_text_tests.py#L257) | 三组示例对话后接真实提问。 | 请求成功，回复格式正确。 | 默认运行 |
| 05_04 | [`test_05_04_sample_vs_current_question`](../m2_her_text_tests.py#L267) | 示例里问的是 apple，真实提问是 kiwi；分别测“不带 name”和“每条都带 name”两种写法。 | 每条都带 name 时：回复包含 kiwi（不区分大小写）。示例消息不带 name 时：请求失败。 | 需 --run-behavior（模型行为，单独统计） |
| 05_05 | [`test_05_05_samples_with_real_history`](../m2_her_text_tests.py#L290) | 两组示例 + 一轮真实问答 + 当前提问，每条都带 name。 | 请求成功，回复格式正确。 | 默认运行 |

## 06 names — name 字段

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 06_01 | [`test_06_01_name_omitted`](../m2_her_text_tests.py#L303) | 单条 user 消息，不带 name。 | 请求正常成功。 | 默认运行 |
| 06_02 | [`test_06_02_name_unicode`](../m2_her_text_tests.py#L310) | user 的 name 分别是中文、英文、含 emoji 的字符串。 | 都能正常提交，回复格式正确；不要求模型说出 name。 | 默认运行 |
| 06_03 | [`test_06_03_multiple_named_users`](../m2_her_text_tests.py#L320) | 用户 Alice 和 Bob 各报一个通行编号；第二次请求把两人的编号对调（消息顺序不变），要求按 JSON 回答。 | 两次都正确回答 {"Alice": …, "Bob": …}，说明模型按 name 区分说话人，而不是按消息顺序。 | 需 --run-behavior（模型行为，单独统计） |
| 06_04 | [`test_06_04_multiple_named_assistants`](../m2_her_text_tests.py#L342) | 助手 Alpha 和 Beta 各报一条记录；第二次请求把两者的记录对调，要求按 JSON 回答。 | 两次都正确回答 {"Alpha": …, "Beta": …}。 | 需 --run-behavior（模型行为，单独统计） |

## 07 multiturn — 多轮对话

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 07_01 | [`test_07_01_two_turn_memory`](../m2_her_text_tests.py#L365) | 上一轮用户说了编号 HER_M41，这一轮问编号。 | 回复包含 HER_M41。 | 需 --run-behavior（模型行为，单独统计） |
| 07_02 | [`test_07_02_five_turn_facts`](../m2_her_text_tests.py#L377) | 5 轮“编号 → 内容”的历史，问第 0 条和第 4 条。 | 回复同时包含 HER_00_VALUE 和 HER_04_VALUE。 | 需 --run-behavior（模型行为，单独统计） |
| 07_03 | [`test_07_03_twenty_turn_history`](../m2_her_text_tests.py#L386) | 20 轮“编号 → 内容”的历史，问第 0 条和第 19 条。 | 回复同时包含 HER_00_VALUE 和 HER_19_VALUE。 | 需 --run-behavior（模型行为，单独统计） |
| 07_04 | [`test_07_04_actual_response_roundtrip`](../m2_her_text_tests.py#L394) | 第一轮请模型确认编号；第二轮把第一轮的回复原样作为 assistant 历史发回，再继续问。 | 两轮都成功，模型的回复可以原样作为历史再提交；不检查记得对不对。 | 默认运行 |
| 07_05 | [`test_07_05_latest_fact_correction`](../m2_her_text_tests.py#L406) | 用户先说编号 OLD_K19，又更正为 NEW_T83，然后问编号。 | 回复包含 NEW_T83，不包含 OLD_K19。 | 需 --run-behavior（模型行为，单独统计） |
| 07_06 | [`test_07_06_conversation_isolation`](../m2_her_text_tests.py#L420) | 两个独立请求各约定一个暗号：CODE_A17 和 CODE_B29。 | 每次只回答本次对话的暗号。 | 需 --run-behavior（模型行为，单独统计） |

## 08 sampling — 采样参数（temperature / top_p）

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 08_01 | [`test_08_01_sampling_omitted`](../m2_her_text_tests.py#L434) | 请求里完全不带 temperature 和 top_p。 | 使用服务端默认值，请求正常成功；测试代码不会自动补参数。 | 默认运行 |
| 08_02 | [`test_08_02_temperature_valid`](../m2_her_text_tests.py#L439) | temperature 分别取 0.01、0.5、1.0（仅非流式）。 | 文档范围 (0, 1] 内的值都能正常使用；不比较随机性。 | 默认运行 |
| 08_03 | [`test_08_03_temperature_invalid`](../m2_her_text_tests.py#L448) | temperature 取 0、-0.1、1.01、字符串 "0.5"、布尔值 true；流式、非流式各测一次。 | 0 和 1.01 超出文档范围 (0, 1]，接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；-0.1、字符串、布尔值必须请求失败。 | 默认运行 |
| 08_04 | [`test_08_04_top_p_valid`](../m2_her_text_tests.py#L461) | top_p 分别取 0.01、0.5、0.95、1.0（仅非流式）。 | 文档范围 (0, 1] 内的值都能正常使用。 | 默认运行 |
| 08_05 | [`test_08_05_top_p_invalid`](../m2_her_text_tests.py#L470) | top_p 取 0、-0.1、1.01、字符串 "0.95"、布尔值 true；流式、非流式各测一次。 | 0 超出文档范围 (0, 1]，接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；-0.1、1.01、字符串、布尔值必须请求失败。 | 默认运行 |

## 09 completion_limit — 输出长度上限 max_completion_tokens

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 09_01 | [`test_09_01_completion_limit_omitted`](../m2_her_text_tests.py#L484) | 请求里既不带 max_tokens，也不带 max_completion_tokens。 | 使用服务端默认上限，请求正常成功。 | 默认运行 |
| 09_02 | [`test_09_02_completion_limit_valid`](../m2_her_text_tests.py#L491) | max_completion_tokens 分别取 1、2、32、2047、2048。 | 实际输出的 token 数不超过上限；因达到上限而结束（finish_reason=length）时恰好等于上限；上限为 1 时允许回复为空。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |
| 09_03 | [`test_09_03_completion_limit_nonpositive`](../m2_her_text_tests.py#L499) | max_completion_tokens 取 0 和 -1。 | 0 和 -1 接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）。 | 默认运行 |
| 09_04 | [`test_09_04_completion_limit_type`](../m2_her_text_tests.py#L512) | max_completion_tokens 取小数 1.5、字符串 "32"、布尔值 true、null。 | null 接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；小数、字符串、布尔值必须请求失败。 | 默认运行 |
| 09_05 | [`test_09_05_completion_length_truncation`](../m2_her_text_tests.py#L523) | 让模型写长篇续写，上限 8 token；如果模型提前写完，换一个续写提示并把上限降到 1 再试。 | 至少一次因达到上限而结束（finish_reason=length），且输出 token 数恰好等于上限；两次都没被截断则判失败。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |

## 10 response_usage — 响应结构与 usage

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 10_01 | [`test_10_01_response_envelope`](../m2_her_text_tests.py#L529) | 普通请求，检查 id、object、created、model、choices。 | 字段齐全、类型正确；object 与是否流式一致；model 等于请求的模型名；流式各数据包的 id、model、created 一致。 | 默认运行 |
| 10_02 | [`test_10_02_response_message`](../m2_her_text_tests.py#L537) | 普通非流式请求。 | message.role 为 assistant，content 是非空字符串。 | 默认运行 |
| 10_03 | [`test_10_03_finish_reason_stop`](../m2_her_text_tests.py#L543) | 用 system 和示例约束模型只回答 OK；上限 128 token，若被截断放宽到 512 再试。 | 至少一次以 finish_reason=stop 结束，且输出 token 数不超过上限；两次都没正常结束则判失败。 | 默认运行 |
| 10_04 | [`test_10_04_usage_total_tokens`](../m2_her_text_tests.py#L548) | 输出上限分别为 1 和 32 的普通请求。 | usage.total_tokens 是正整数；只输出 1 个 token 时也要有用量。 | 默认运行 |
| 10_05 | [`test_10_05_usage_breakdown_math`](../m2_her_text_tests.py#L557) | 普通请求，检查 usage 的结构。 | usage 结构正确；有 prompt_tokens / completion_tokens 时类型正确，且 total = prompt + completion。缺少细分字段只记录，不判失败。 | 默认运行；字段缺失只记录 |
| 10_06 | [`test_10_06_sensitivity_field_types`](../m2_her_text_tests.py#L571) | 普通请求，检查 input_sensitive、output_sensitive 等字段。 | 这些字段出现时类型正确（布尔或整数），没出现只记录；不检查内容审核本身。 | 默认运行；字段缺失只记录 |
| 10_07 | [`test_10_07_prompt_tokens_across_modes`](../m2_her_text_tests.py#L585) | 普通对话和完整七角色对话两种输入，在非流式、流式下分别发送原输入和追加 256 段背景后的输入，共 4 次。 | 同一模式下，追加输入后 prompt_tokens 必须变大。 | 需 --run-compat；需返回 prompt_tokens |

## 11 error_codes — 错误处理

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 11_01 | [`test_11_01_invalid_model`](../m2_her_text_tests.py#L626) | model 不传、填不存在的名字、空字符串、null 或数字。 | 请求失败；测试代码不会补默认模型。 | 默认运行 |
| 11_02 | [`test_11_02_invalid_messages`](../m2_her_text_tests.py#L642) | messages 不传、为 null、字符串或对象。 | 请求失败，不能当作成功处理。 | 默认运行 |
| 11_03 | [`test_11_03_invalid_role`](../m2_her_text_tests.py#L655) | 消息的 role 不传、填未定义的值或数字。 | 请求失败。 | 默认运行 |
| 11_04 | [`test_11_04_invalid_content`](../m2_her_text_tests.py#L676) | content 不传、为 null、数字、对象，或是文本 / 图片 / 视频 / 音频组成的数组。 | 请求失败（包括 M2-her 不支持的图片、视频、音频内容）。 | 默认运行；仅原生接口 |
| 11_05 | [`test_11_05_invalid_name_type`](../m2_her_text_tests.py#L715) | 消息的 name 为数字、对象或数组。 | 请求失败。 | 默认运行 |
| 11_06 | [`test_11_06_authentication_errors`](../m2_her_text_tests.py#L728) | 不带 Authorization，或使用无效的 Key。 | 请求失败。 | 默认运行 |
| 11_07 | [`test_11_07_invalid_request_envelope`](../m2_her_text_tests.py#L747) | 发送截断的 JSON、顶层为数组，或 stream 为字符串 / 数字。 | 请求失败。 | 默认运行 |
| 11_08 | [`test_11_08_legacy_sample_role_spelling`](../m2_her_text_tests.py#L771) | 示例角色写成旧名称 user_sample_message / ai_sample_message；先用相同内容、正确名称的请求做对照。 | 正确名称的对照请求成功，旧名称请求失败。 | 默认运行；仅原生接口；对照请求失败时跳过 |
| 11_09 | [`test_11_09_invalid_message_item`](../m2_her_text_tests.py#L788) | messages 是数组，但其中元素为 null、字符串、数字或数组。 | 请求失败。 | 默认运行 |

## 12 long_context — 长输入与 64K 上下文

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 12_01 | [`test_12_01_long_system`](../m2_her_text_tests.py#L798) | system 中放约 500 行背景记录，开头、中间、结尾各有一个暗号。 | 请求成功，回复格式正确；不要求找出暗号。 | 需 --run-slow |
| 12_02 | [`test_12_02_long_persona_and_samples`](../m2_her_text_tests.py#L816) | 在 user_system 或示例 ai 消息中放约 500 行文本。 | 请求成功，回复格式正确。 | 需 --run-slow |
| 12_03 | [`test_12_03_context_within_64k`](../m2_her_text_tests.py#L837) | 运行时先用若干次只输出 1 个 token 的请求，按真实 prompt_tokens 拼出接近 64K 的输入，再以 64 token 上限正式请求。 | 请求成功，且 prompt_tokens 与拼装时测得的值一致。 | 需 --run-slow；可用 --context-fixture 提供已测好的长输入 |
| 12_04 | [`test_12_04_context_over_64k`](../m2_her_text_tests.py#L854) | 用 12_03 拼好的同一份长输入，把输出上限提高到 2048，使“输入 + 输出上限”超过 64K。 | 请求失败。 | 需 --run-slow；可用 --context-fixture 提供已测好的长输入 |

## 13 role_combo — 七种角色组合

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 13_01 | [`test_13_01_all_seven_roles`](../m2_her_text_tests.py#L878) | system、user_system、group、一组示例对话、历史问答、当前提问一次发送；分别测“按官网示例部分消息不带 name”和“每条都带 name”两种写法。 | 每条都带 name 时请求成功，回复格式正确；按官网示例不带 name 时请求失败。 | 默认运行 |
| 13_02 | [`test_13_02_persona_samples_named_history`](../m2_her_text_tests.py#L889) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name），再加上两位访客的物品编号，要求按 RESULT: 格式依次给出六项信息。 | 依次给出 AI_K72\|USER_P38\|SCENE_R64\|CODE_V59\|ITEM_A73\|ITEM_B84 六项；带不带 RESULT: 前缀都算对。 | 需 --run-behavior（模型行为，单独统计） |
| 13_03 | [`test_13_03_long_history_small_output`](../m2_her_text_tests.py#L913) | 20 轮历史，输出上限 64 token。 | 输出 token 数不超过 64；因达到上限结束时恰好等于 64。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |
| 13_04 | [`test_13_04_roles_with_sampling`](../m2_her_text_tests.py#L920) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name），同时传 temperature=0.5、top_p=0.95。 | 请求成功，回复格式正确。 | 默认运行 |
| 13_05 | [`test_13_05_one_special_name_omitted`](../m2_her_text_tests.py#L930) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name）中，每次只去掉 user_system、group、示例 user、示例 ai 其中一条的 name。 | 去掉任何一条的 name 都会请求失败。 | 默认运行 |

## 16 guide_alignment — 官网指南中的写法

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 16_01 | [`test_16_01_guide_role_structures`](../m2_her_text_tests.py#L941) | 按官网指南发送基础对话、角色扮演、示例引导三种消息结构；分别测“照官网原样（部分消息不带 name）”和“每条都带 name”。 | 每条都带 name 的写法、以及基础对话都成功；角色扮演和示例引导照官网原样不带 name 时请求失败。 | 默认运行 |
| 16_04 | [`test_16_04_context_recall`](../m2_her_text_tests.py#L957) | 800 条记录的开头、中间、结尾各放一个标记，让模型按顺序列出这三个标记。 | 回复同时包含 BEGIN_P38、MIDDLE_P49、END_P50。 | 需 --run-behavior（模型行为，单独统计）；需 --run-slow |

## 17 candidate_count — n 多条回复

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 17_01 | [`test_17_01_n_default_single_choice`](../m2_her_text_tests.py#L975) | n 不传、为 null、0 或 -1。 | 不传 n 时只返回一条回复；null、0、-1 接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx），接受时只返回一条回复。 | 默认运行；仅原生接口 |
| 17_02 | [`test_17_02_n_candidate_count`](../m2_her_text_tests.py#L992) | 非流式请求，n=1 和 n=2。 | choices 条数等于 n，index 为 0 到 n-1 且不重复，每条回复都完整，usage 正确；不要求几条回复内容不同。 | 默认运行；仅原生接口 |
| 17_03 | [`test_17_03_n_one_stream`](../m2_her_text_tests.py#L1000) | 流式请求，显式传 n=1。 | 和普通流式一样，只有一条回复。 | 默认运行；仅原生接口 |
| 17_04 | [`test_17_04_n_invalid_type`](../m2_her_text_tests.py#L1021) | n 为小数、字符串、true、false、对象、数组或超大整数。 | 请求失败。 | 默认运行；仅原生接口 |
| 17_05 | [`test_17_05_n_stream_conflict`](../m2_her_text_tests.py#L1026) | 先确认非流式 n=2 正常，再发送 stream=true、n=2。 | 请求失败。 | 默认运行；仅原生接口 |
| 17_06 | [`test_17_06_n_tools_conflict`](../m2_her_text_tests.py#L1036) | 先确认非流式 n=2 正常，再在同一请求里加上合法的 tools。 | 请求失败。 | 默认运行；仅原生接口 |
| 17_07 | [`test_17_07_n_with_roles_and_parameters`](../m2_her_text_tests.py#L1056) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name） + n=2 + temperature=0.7 + top_p=0.95，输出上限分别用 max_tokens=100 和 max_completion_tokens=100。 | 返回两条完整回复，外层字段和 usage 正确。 | 默认运行；仅原生接口 |
| 17_08 | [`test_17_08_n_configured_boundary`](../m2_her_text_tests.py#L1079) | 非流式请求：先发 n=4；再发 n=5（只在 n=4 成功后发送）。可用 --n-limit 修改上限值 4。 | n=4 返回 4 条完整回复；n=5 请求失败。 | 默认运行；--n-limit 可修改上限值 |

## 18 request_metadata — metadata / user / mask_sensitive_info

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 18_01 | [`test_18_01_request_metadata_valid`](../m2_her_text_tests.py#L1099) | metadata 为字符串键值对（含中文、255 字节长的键和值），user 为字符串，mask_sensitive_info 为 true / false。 | 请求成功，响应格式正确；不检查日志记录或脱敏效果。 | 默认运行；仅原生接口 |
| 18_02 | [`test_18_02_request_metadata_invalid_type`](../m2_her_text_tests.py#L1135) | metadata 为字符串、数组或值为数字；user 为数字或对象；mask_sensitive_info 为字符串或数字。 | 请求失败。 | 默认运行；仅原生接口 |
| 18_03 | [`test_18_03_metadata_length_boundary`](../m2_her_text_tests.py#L1143) | metadata 的键或值长 256 字节（上限 255）。 | 请求失败。 | 默认运行；仅原生接口 |

## 19 language_consistency — 回复语言

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 19_01 | [`test_19_01_reply_follows_user_language`](../m2_her_text_tests.py#L1166) | 分别用简体中文、繁体中文、英、日、韩、西、法、德、葡、俄、阿 11 种语言提问。 | 用提问的语言回复，不夹杂其他语言的句子。每种语言最多请求 3 次，至少 2 次符合即通过；请求本身出错时直接判失败。 | 需 --run-behavior（模型行为，单独统计） |
| 19_04 | [`test_19_04_multiturn_language_retention`](../m2_her_text_tests.py#L1226) | 角色设定用语言 A，用户已经用语言 B 聊了三轮，再继续提问；中英日韩两两组合共 12 组。 | 继续用用户的语言 B 回复，不被设定语言带偏。 | 需 --run-behavior（模型行为，单独统计） |

---

## 附录：parametrize 展开后的 343 个 items

| 展开因子 | 涉及 case |
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
| `单项` | 10_02 / 17_03 / 17_05 / 17_06 |
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

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。
