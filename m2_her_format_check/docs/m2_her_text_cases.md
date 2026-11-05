# M2-Her 文本与角色格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_text_tests.py`](../m2_her_text_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**17**；case 函数数：**80**；pytest 收集 items 数：**343**
> 预期值：取自 MiniMax 官方接口的实测结果（2026-11-05/06）；判定规则见 [README](../README.md)。
> “请求失败”：HTTP 状态码非 200，或 HTTP 200 但响应中业务码非 0 / 带 error 对象，且没有返回回复内容；不比对具体的错误码和错误信息。
> 下表是内置基线。S / F / E 的完整定义及 PASS / FAIL / SKIP 边界见 [统一判定规则](../README.md#verdict-rules)。F 的非 200 包括 5xx；E 明确禁止 5xx。网络异常不算预期拒绝，损坏的 JSON / SSE 不能通过。

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

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 01_01 | [`test_01_01_minimal_user_message`](../m2_her_text_tests.py#L71) | [S：必须成功](../README.md#verdict-rules) | 只发一条 user 消息，不带 system、name 或采样参数；显式设置输出上限 128，流式、非流式各测一次。 | HTTP 200，返回一条非空 assistant 回复；若有 base_resp，status_code 为整数 0；流式完整解析且结束原因一致。 | 默认运行 |
| 01_02 | [`test_01_02_system_user_chat`](../m2_her_text_tests.py#L75) | [S：必须成功](../README.md#verdict-rules) | system 设为“友好的助手”，user 说“你好”。 | 请求成功，回复格式正确、内容非空。 | 默认运行 |
| 01_03 | [`test_01_03_chinese_text`](../m2_her_text_tests.py#L82) | [S：必须成功](../README.md#verdict-rules) | 用中文请模型写一句简短问候。 | 回复包含汉字区字符，且不包含 U+FFFD；这不是完整的语种识别。 | 需 --run-behavior（模型行为，单独统计） |
| 01_04 | [`test_01_04_english_text`](../m2_her_text_tests.py#L94) | [S：必须成功](../README.md#verdict-rules) | 用英文请模型只用英文写一句问候。 | 回复包含拉丁字母且没有汉字区字符；不据此判断是否为纯英文。 | 需 --run-behavior（模型行为，单独统计） |
| 01_05 | [`test_01_05_text_escaping_unicode`](../m2_her_text_tests.py#L105) | [S：必须成功](../README.md#verdict-rules) | user 消息里包含双引号、反斜杠、换行和 emoji。 | 请求成功，响应按 UTF-8 / JSON / SSE 完整解析；不检查是否原样复述。 | 默认运行 |
| 01_06 | [`test_01_06_multilingual_input`](../m2_her_text_tests.py#L121) | [S：必须成功](../README.md#verdict-rules) | 中文问句里夹着日文、韩文、阿拉伯文、俄文或带重音符号的问候语。 | 各种文字均被接受，回复格式正确；不要求翻译或提取。 | 默认运行 |

## 02 system_persona — system 人设

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 02_01 | [`test_02_01_system_identity`](../m2_her_text_tests.py#L133) | [S：必须成功](../README.md#verdict-rules) | system 设定身份编号 AI_K72，user 让模型只回答自己的编号。 | 回复包含 AI_K72。 | 需 --run-behavior（模型行为，单独统计） |
| 02_02 | [`test_02_02_system_reply_prefix`](../m2_her_text_tests.py#L143) | [S：必须成功](../README.md#verdict-rules) | system 要求每次回复以 HER_REPLY: 开头，user 说“你好”。 | 回复以 HER_REPLY: 开头。 | 需 --run-behavior（模型行为，单独统计） |
| 02_04 | [`test_02_04_system_identity_multiturn`](../m2_her_text_tests.py#L154) | [S：必须成功](../README.md#verdict-rules) | system 设定身份后，插入 5 轮历史问答，再询问该信息。 | 回复仍包含 AI_K72。 | 需 --run-behavior（模型行为，单独统计） |
| 02_05 | [`test_02_05_system_identity_isolation`](../m2_her_text_tests.py#L166) | [S：必须成功](../README.md#verdict-rules) | 两个独立请求分别把身份设为 AI_K72 和 AI_B19，问同一个问题。 | 每次回复包含本次身份编号，且不包含另一个请求的编号；允许有其他文字。 | 需 --run-behavior（模型行为，单独统计） |

## 03 user_system — user_system 用户设定

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 03_01 | [`test_03_01_user_system_identity`](../m2_her_text_tests.py#L180) | [S：必须成功](../README.md#verdict-rules) | 只在 user_system 里写用户编号 USER_P38，然后问用户编号。 | 回复包含 USER_P38。 | 需 --run-behavior（模型行为，单独统计） |
| 03_03 | [`test_03_03_user_system_multiturn`](../m2_her_text_tests.py#L191) | [S：必须成功](../README.md#verdict-rules) | user_system 写小组编号 TEAM_L63后，插入 5 轮历史问答，再询问该信息。 | 回复包含 TEAM_L63。 | 需 --run-behavior（模型行为，单独统计） |
| 03_04 | [`test_03_04_user_system_omitted`](../m2_her_text_tests.py#L202) | [S：必须成功](../README.md#verdict-rules) | 只有 system 和 user，没有 user_system。 | user_system 是可选的，请求正常成功。 | 默认运行 |

## 04 group — group 场景

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 04_01 | [`test_04_01_group_scene_name`](../m2_her_text_tests.py#L213) | [S：必须成功](../README.md#verdict-rules) | 只在 group 消息里写场景编号 SCENE_R64，然后问当前场景。 | 回复包含 SCENE_R64。 | 需 --run-behavior（模型行为，单独统计） |
| 04_02 | [`test_04_02_group_scene_isolation`](../m2_her_text_tests.py#L228) | [S：必须成功](../README.md#verdict-rules) | 同一个问题发两次，分别配场景 SCENE_R64 和 SCENE_N21。 | 每次回复包含本次场景编号，且不包含另一个场景编号。 | 需 --run-behavior（模型行为，单独统计） |
| 04_03 | [`test_04_03_group_omitted`](../m2_her_text_tests.py#L242) | [S：必须成功](../README.md#verdict-rules) | 普通 user 请求，没有 group。 | group 是可选的，请求正常成功。 | 默认运行 |

## 05 sample_messages — 示例对话 sample_message_*

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 05_01 | [`test_05_01_single_sample_pair`](../m2_her_text_tests.py#L248) | [S：必须成功](../README.md#verdict-rules) | 一组示例对话（示例 user + 示例 ai，都带 name）后接真实提问。 | 请求成功，回复格式正确；不要求模仿示例格式。 | 默认运行 |
| 05_02 | [`test_05_02_three_sample_pairs`](../m2_her_text_tests.py#L257) | [S：必须成功](../README.md#verdict-rules) | 三组示例对话后接真实提问。 | 请求成功，回复格式正确。 | 默认运行 |
| 05_04 | [`test_05_04_sample_vs_current_question`](../m2_her_text_tests.py#L267) | [按变体区分，见校验点](../README.md#verdict-rules) | 示例里问的是 apple，真实提问是 kiwi；分别测“不带 name”和“每条都带 name”两种写法。 | 每条都带 name 时：回复包含 kiwi（不区分大小写）。示例消息不带 name 时：请求失败。 失败分支先用同内容带 name 的请求做对照；对照失败记 SKIP。 | 需 --run-behavior（模型行为，单独统计） |
| 05_05 | [`test_05_05_samples_with_real_history`](../m2_her_text_tests.py#L290) | [S：必须成功](../README.md#verdict-rules) | 两组示例 + 一轮真实问答 + 当前提问，每条都带 name。 | 请求成功，回复格式正确。 | 默认运行 |

## 06 names — name 字段

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 06_01 | [`test_06_01_name_omitted`](../m2_her_text_tests.py#L303) | [S：必须成功](../README.md#verdict-rules) | 单条 user 消息，不带 name。 | 请求正常成功。 | 默认运行 |
| 06_02 | [`test_06_02_name_unicode`](../m2_her_text_tests.py#L310) | [S：必须成功](../README.md#verdict-rules) | user 的 name 分别是中文、英文、含 emoji 的字符串。 | 都能正常提交，回复格式正确；不要求模型说出 name。 | 默认运行 |
| 06_03 | [`test_06_03_multiple_named_users`](../m2_her_text_tests.py#L320) | [S：必须成功](../README.md#verdict-rules) | 用户 Alice 和 Bob 各报一个通行编号；第二次请求把两人的编号对调（消息顺序不变），要求按 JSON 回答。 | 两次都正确回答 {"Alice": …, "Bob": …}，说明模型按 name 区分说话人，而不是按消息顺序。 | 需 --run-behavior（模型行为，单独统计） |
| 06_04 | [`test_06_04_multiple_named_assistants`](../m2_her_text_tests.py#L342) | [S：必须成功](../README.md#verdict-rules) | 助手 Alpha 和 Beta 各报一条记录；第二次请求把两者的记录对调，要求按 JSON 回答。 | 两次都正确回答 {"Alpha": …, "Beta": …}。 | 需 --run-behavior（模型行为，单独统计） |

## 07 multiturn — 多轮对话

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 07_01 | [`test_07_01_two_turn_memory`](../m2_her_text_tests.py#L365) | [S：必须成功](../README.md#verdict-rules) | 上一轮用户说了编号 HER_M41，这一轮问编号。 | 回复包含 HER_M41。 | 需 --run-behavior（模型行为，单独统计） |
| 07_02 | [`test_07_02_five_turn_facts`](../m2_her_text_tests.py#L377) | [S：必须成功](../README.md#verdict-rules) | 5 轮“编号 → 内容”的历史，问第 0 条和第 4 条。 | 回复同时包含 HER_00_VALUE 和 HER_04_VALUE。 | 需 --run-behavior（模型行为，单独统计） |
| 07_03 | [`test_07_03_twenty_turn_history`](../m2_her_text_tests.py#L386) | [S：必须成功](../README.md#verdict-rules) | 20 轮“编号 → 内容”的历史，问第 0 条和第 19 条。 | 回复同时包含 HER_00_VALUE 和 HER_19_VALUE。 | 需 --run-behavior（模型行为，单独统计） |
| 07_04 | [`test_07_04_actual_response_roundtrip`](../m2_her_text_tests.py#L394) | [S：必须成功](../README.md#verdict-rules) | 第一轮请模型确认编号；第二轮把第一轮的回复原样作为 assistant 历史发回，再继续问。 | 两轮都成功，模型的回复可以原样作为历史再提交；不检查记得对不对。 | 默认运行 |
| 07_05 | [`test_07_05_latest_fact_correction`](../m2_her_text_tests.py#L406) | [S：必须成功](../README.md#verdict-rules) | 用户先说编号 OLD_K19，又更正为 NEW_T83，然后问编号。 | 回复包含 NEW_T83，不包含 OLD_K19。 | 需 --run-behavior（模型行为，单独统计） |
| 07_06 | [`test_07_06_conversation_isolation`](../m2_her_text_tests.py#L420) | [S：必须成功](../README.md#verdict-rules) | 两个独立请求各约定一个暗号：CODE_A17 和 CODE_B29。 | 每次回复包含本次暗号，且不包含另一个请求的暗号。 | 需 --run-behavior（模型行为，单独统计） |

## 08 sampling — 采样参数（temperature / top_p）

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 08_01 | [`test_08_01_sampling_omitted`](../m2_her_text_tests.py#L434) | [S：必须成功](../README.md#verdict-rules) | 请求里完全不带 temperature 和 top_p。 | 请求成功；只确认 temperature、top_p 省略时可调用，不验证服务端默认数值。 | 默认运行 |
| 08_02 | [`test_08_02_temperature_valid`](../m2_her_text_tests.py#L439) | [S：必须成功](../README.md#verdict-rules) | temperature 分别取 0.01、0.5、1.0（仅非流式）。 | 文档范围 (0, 1] 内的值都能正常使用；不比较随机性。 | 默认运行 |
| 08_03 | [`test_08_03_temperature_invalid`](../m2_her_text_tests.py#L448) | [按变体区分，见校验点](../README.md#verdict-rules) | temperature 取 0、-0.1、1.01、字符串 "0.5"、布尔值 true；流式、非流式各测一次。 | 0 和 1.01 超出文档范围 (0, 1]，接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；-0.1、字符串、布尔值必须请求失败。 仅失败/两者均可的分支执行正常对照；对照失败记 SKIP。 | 默认运行 |
| 08_04 | [`test_08_04_top_p_valid`](../m2_her_text_tests.py#L461) | [S：必须成功](../README.md#verdict-rules) | top_p 分别取 0.01、0.5、0.95、1.0（仅非流式）。 | 文档范围 (0, 1] 内的值都能正常使用。 | 默认运行 |
| 08_05 | [`test_08_05_top_p_invalid`](../m2_her_text_tests.py#L470) | [按变体区分，见校验点](../README.md#verdict-rules) | top_p 取 0、-0.1、1.01、字符串 "0.95"、布尔值 true；流式、非流式各测一次。 | 0 超出文档范围 (0, 1]，接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；-0.1、1.01、字符串、布尔值必须请求失败。 仅失败/两者均可的分支执行正常对照；对照失败记 SKIP。 | 默认运行 |

## 09 completion_limit — 输出长度上限 max_completion_tokens

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 09_01 | [`test_09_01_completion_limit_omitted`](../m2_her_text_tests.py#L484) | [S：必须成功](../README.md#verdict-rules) | 请求里既不带 max_tokens，也不带 max_completion_tokens。 | 两个长度参数均省略时请求成功；不验证默认上限的具体数值。 | 默认运行 |
| 09_02 | [`test_09_02_completion_limit_valid`](../m2_her_text_tests.py#L491) | [S：必须成功](../README.md#verdict-rules) | max_completion_tokens 分别取 1、2、32、2047、2048。 | 必须返回 prompt_tokens、completion_tokens，且计数与 total_tokens 相加一致。输出 token 数不超过上限；finish_reason=length 时恰好等于上限。仅上限为 1 时允许正文为空；计数缺失判失败。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |
| 09_03 | [`test_09_03_completion_limit_nonpositive`](../m2_her_text_tests.py#L499) | [E：成功或失败，禁 5xx](../README.md#verdict-rules) | max_completion_tokens 取 0 和 -1。 | 0、-1 均允许成功或请求失败，但不能返回 5xx；成功分支允许正文为空，仍检查响应结构，不验证这些值对应的有效输出上限。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |
| 09_04 | [`test_09_04_completion_limit_type`](../m2_her_text_tests.py#L512) | [按变体区分，见校验点](../README.md#verdict-rules) | max_completion_tokens 取小数 1.5、字符串 "32"、布尔值 true、null。 | null 接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；小数、字符串、布尔值必须请求失败。 仅失败/两者均可的分支执行正常对照；对照失败记 SKIP。 | 默认运行 |
| 09_05 | [`test_09_05_completion_length_truncation`](../m2_her_text_tests.py#L523) | [S：必须成功](../README.md#verdict-rules) | 让模型写长篇续写，上限 8 token；如果模型提前写完，换一个续写提示并把上限降到 1 再试。 | 至少一次因达到上限而结束（finish_reason=length），且输出 token 数恰好等于上限；两次都没被截断则判失败。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |

## 10 response_usage — 响应结构与 usage

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 10_01 | [`test_10_01_response_envelope`](../m2_her_text_tests.py#L529) | [S：必须成功](../README.md#verdict-rules) | 普通请求，检查 id、object、created、model、choices。 | id、model 为非空字符串，created 为正整数；model 匹配 M2_HER_RESPONSE_MODEL（默认请求模型名）。普通回复及完整消息汇总包的 object 为 chat.completion，delta 包为 chat.completion.chunk；流式各包 id、model、created 一致。 | 默认运行 |
| 10_02 | [`test_10_02_response_message`](../m2_her_text_tests.py#L537) | [S：必须成功](../README.md#verdict-rules) | 普通非流式请求。 | message.role 为 assistant，content 是非空字符串。 | 默认运行 |
| 10_03 | [`test_10_03_finish_reason_stop`](../m2_her_text_tests.py#L543) | [S：必须成功](../README.md#verdict-rules) | 用 system 和示例约束模型只回答 OK；上限 128 token，若被截断放宽到 512 再试。 | 两次内至少一次 finish_reason=stop；不检查正文是否恰好 OK。有 completion_tokens 时验证上限；若以 length 结束则必须有计数且等于上限；两次都没有 stop 判失败。 | 默认运行 |
| 10_04 | [`test_10_04_usage_total_tokens`](../m2_her_text_tests.py#L548) | [S：必须成功](../README.md#verdict-rules) | 输出上限分别为 1 和 32 的普通请求。 | usage.total_tokens 为正整数；上限为 1 时允许正文为空。此项检查用量字段，不单独证明输出在 1/32 token 处截断。 | 默认运行 |
| 10_05 | [`test_10_05_usage_breakdown_math`](../m2_her_text_tests.py#L557) | [S：必须成功](../README.md#verdict-rules) | 普通请求，检查 usage 的结构。 | usage 必须存在，total_tokens 为非负整数。prompt_tokens、completion_tokens 可以一起缺省；出现任何一个就要求两个都存在、为非负整数，且 total=prompt+completion。 | 默认运行；字段缺失只记录 |
| 10_06 | [`test_10_06_sensitivity_field_types`](../m2_her_text_tests.py#L571) | [S：必须成功](../README.md#verdict-rules) | 普通请求，检查 input_sensitive、output_sensitive 等字段。 | 这些字段出现时类型正确（布尔或整数），没出现只记录；不检查内容审核本身。 | 默认运行；字段缺失只记录 |
| 10_07 | [`test_10_07_prompt_tokens_across_modes`](../m2_her_text_tests.py#L585) | [S：必须成功](../README.md#verdict-rules) | 普通对话与完整七角色对话分别为一个变体；每个变体在非流式、流式下各发送原输入和追加 256 段背景后的输入，共 4 次。 OpenAI 流式计数检查会显式传 stream_options.include_usage=true。 | 所有请求成功并返回完整 token 计数；同一模式下，追加输入后的 prompt_tokens 大于原值。默认不要求跨模式相等；--contract 中 prompt_tokens_equal=true 时才比较两种模式的计数。 | 需 --run-compat；需返回 prompt_tokens |

## 11 error_codes — 错误处理

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 11_01 | [`test_11_01_invalid_model`](../m2_her_text_tests.py#L635) | [F：必须失败](../README.md#verdict-rules) | model 不传、填不存在的名字、空字符串、null 或数字。 | 请求失败；测试代码不会补默认模型。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |
| 11_02 | [`test_11_02_invalid_messages`](../m2_her_text_tests.py#L651) | [F：必须失败](../README.md#verdict-rules) | messages 不传、为 null、字符串或对象。 | 请求失败，不能当作成功处理。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |
| 11_03 | [`test_11_03_invalid_role`](../m2_her_text_tests.py#L664) | [F：必须失败](../README.md#verdict-rules) | 消息的 role 不传、填未定义的值或数字。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |
| 11_04 | [`test_11_04_invalid_content`](../m2_her_text_tests.py#L685) | [F：必须失败](../README.md#verdict-rules) | content 不传、为 null、数字、对象，或是文本 / 图片 / 视频 / 音频组成的数组。 | 请求失败（包括 M2-her 不支持的图片、视频、音频内容）。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行；仅原生接口 |
| 11_05 | [`test_11_05_invalid_name_type`](../m2_her_text_tests.py#L723) | [F：必须失败](../README.md#verdict-rules) | 消息的 name 为数字、对象或数组。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |
| 11_06 | [`test_11_06_authentication_errors`](../m2_her_text_tests.py#L736) | [F：必须失败](../README.md#verdict-rules) | 配置 Bearer 鉴权时，分别不带 Authorization 或使用无效的 Key。 | 请求失败。M2_HER_AUTH_TYPE=none 时跳过；本用例不验证自定义鉴权。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行；仅 Bearer 鉴权 |
| 11_07 | [`test_11_07_invalid_request_envelope`](../m2_her_text_tests.py#L759) | [F：必须失败](../README.md#verdict-rules) | 发送截断的 JSON、顶层为数组，或 stream 为字符串 / 数字。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |
| 11_08 | [`test_11_08_legacy_sample_role_spelling`](../m2_her_text_tests.py#L783) | [F：必须失败](../README.md#verdict-rules) | 示例角色写成旧名称 user_sample_message / ai_sample_message；先用相同内容、正确名称的请求做对照。 | 正确名称的对照请求成功，旧名称请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行；仅原生接口；对照请求失败时跳过 |
| 11_09 | [`test_11_09_invalid_message_item`](../m2_her_text_tests.py#L800) | [F：必须失败](../README.md#verdict-rules) | messages 是数组，但其中元素为 null、字符串、数字或数组。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |

## 12 long_context — 长输入与 64K 上下文

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 12_01 | [`test_12_01_long_system`](../m2_her_text_tests.py#L810) | [S：必须成功](../README.md#verdict-rules) | system 中放约 500 行背景记录，开头、中间、结尾各有一个暗号。 | 请求成功，回复格式正确；不要求找出暗号。 | 需 --run-slow |
| 12_02 | [`test_12_02_long_persona_and_samples`](../m2_her_text_tests.py#L828) | [S：必须成功](../README.md#verdict-rules) | 在 user_system 或示例 ai 消息中放约 500 行文本。 | 请求成功，回复格式正确。 | 需 --run-slow |
| 12_03 | [`test_12_03_context_within_64k`](../m2_her_text_tests.py#L849) | [S：必须成功](../README.md#verdict-rules) | 运行时先用若干次只输出 1 个 token 的请求，按真实 prompt_tokens 拼出接近 64K 的输入，再以 64 token 上限正式请求。 | 正式请求成功，必须返回完整 token 计数，prompt_tokens 必须与校准样本相同；缺失或变化均失败。 | 需 --run-slow；可用 --context-fixture 提供已测好的长输入 |
| 12_04 | [`test_12_04_context_over_64k`](../m2_her_text_tests.py#L864) | [F：必须失败](../README.md#verdict-rules) | 用 12_03 拼好的同一份长输入，把输出上限提高到 2048，使“输入 + 输出上限”超过 64K。 | 默认基线要求请求失败。先完成校准与正常对照；准备失败不能算超窗检查通过。可用 --contract 替换该项规则；--context-fixture 可替换测量样本。 | 需 --run-slow；可用 --context-fixture 提供已测好的长输入 |

## 13 role_combo — 七种角色组合

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 13_01 | [`test_13_01_all_seven_roles`](../m2_her_text_tests.py#L888) | [按变体区分，见校验点](../README.md#verdict-rules) | 完整七角色对话分两组：all_named 每条带 name；original_names 保留 system、user_system、历史问答和当前 user 的 name，只省略 group 和两条示例的 name。 | all_named 必须成功；original_names 在带 name 的同内容对照成功后必须请求失败。该结论只针对这里的消息组合，不表示所有角色缺 name 都失败。 失败分支先用同内容带 name 的请求做对照；对照失败记 SKIP。 | 默认运行 |
| 13_02 | [`test_13_02_persona_samples_named_history`](../m2_her_text_tests.py#L899) | [S：必须成功](../README.md#verdict-rules) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name），再加上两位访客的物品编号，要求按 RESULT: 格式依次给出六项信息。 | 依次给出 AI_K72\|USER_P38\|SCENE_R64\|CODE_V59\|ITEM_A73\|ITEM_B84 六项；带不带 RESULT: 前缀都算对。 | 需 --run-behavior（模型行为，单独统计） |
| 13_03 | [`test_13_03_long_history_small_output`](../m2_her_text_tests.py#L923) | [S：必须成功](../README.md#verdict-rules) | 20 轮历史，输出上限 64 token。 | 输出 token 数不超过 64；因达到上限结束时恰好等于 64。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |
| 13_04 | [`test_13_04_roles_with_sampling`](../m2_her_text_tests.py#L930) | [S：必须成功](../README.md#verdict-rules) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name），同时传 temperature=0.5、top_p=0.95。 | 请求成功，回复格式正确。 | 默认运行 |
| 13_05 | [`test_13_05_one_special_name_omitted`](../m2_her_text_tests.py#L940) | [F：必须失败](../README.md#verdict-rules) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name）中，每次只去掉 user_system、group、示例 user、示例 ai 其中一条的 name。 | 先确认完整带 name 的同内容对话成功；在该七角色组合中省略指定一条消息的 name 后必须请求失败。 失败分支先用同内容带 name 的请求做对照；对照失败记 SKIP。 | 默认运行 |

## 16 guide_alignment — 官网指南中的写法

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 16_01 | [`test_16_01_guide_role_structures`](../m2_her_text_tests.py#L951) | [按变体区分，见校验点](../README.md#verdict-rules) | 按官网指南发送基础对话、角色扮演、示例引导三种消息结构；分别测“照官网原样（部分消息不带 name）”和“每条都带 name”。 | basic 两种 name 写法均成功；roleplay、samples 的 all_named 成功，original_names 在同内容带 name 对照成功后必须失败。只约束这些组合。 失败分支先用同内容带 name 的请求做对照；对照失败记 SKIP。 | 默认运行 |
| 16_04 | [`test_16_04_context_recall`](../m2_her_text_tests.py#L967) | [S：必须成功](../README.md#verdict-rules) | 800 条记录的开头、中间、结尾各放一个标记，让模型按顺序列出这三个标记。 | 回复同时包含 BEGIN_P38、MIDDLE_P49、END_P50；不检查三者顺序或是否还有其他文字。 | 需 --run-behavior（模型行为，单独统计）；需 --run-slow |

## 17 candidate_count — n 多条回复

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 17_01 | [`test_17_01_n_default_single_choice`](../m2_her_text_tests.py#L985) | [按变体区分，见校验点](../README.md#verdict-rules) | n 不传、为 null、0 或 -1。 | 不传 n 时只返回一条回复；null、0、-1 接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx），接受时只返回一条回复。 仅失败/两者均可的分支执行正常对照；对照失败记 SKIP。 | 默认运行；仅原生接口 |
| 17_02 | [`test_17_02_n_candidate_count`](../m2_her_text_tests.py#L1002) | [S：必须成功](../README.md#verdict-rules) | 非流式请求，n=1 和 n=2。 | choices 条数等于 n，index 为 0 到 n-1 且不重复，每条回复都完整，usage 正确；不要求几条回复内容不同。 | 默认运行；仅原生接口 |
| 17_03 | [`test_17_03_n_one_stream`](../m2_her_text_tests.py#L1010) | [S：必须成功](../README.md#verdict-rules) | 流式请求，显式传 n=1。 | 和普通流式一样，只有一条回复。 | 默认运行；仅原生接口 |
| 17_04 | [`test_17_04_n_invalid_type`](../m2_her_text_tests.py#L1031) | [F：必须失败](../README.md#verdict-rules) | n 为小数、字符串、true、false、对象、数组或超大整数。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行；仅原生接口 |
| 17_05 | [`test_17_05_n_stream_conflict`](../m2_her_text_tests.py#L1036) | [F：必须失败](../README.md#verdict-rules) | 先确认非流式 n=2 正常，再发送 stream=true、n=2。 | 先做普通流式正常对照（失败则 SKIP）；本例内非流式 n=2 必须成功，再要求流式 n=2 失败。本例内 n=2 对照不成功则 FAIL。 | 默认运行；仅原生接口 |
| 17_06 | [`test_17_06_n_tools_conflict`](../m2_her_text_tests.py#L1046) | [F：必须失败](../README.md#verdict-rules) | 先确认非流式 n=2 正常，再在同一请求里加上合法的 tools。 | 普通非流式对照成功后，本例内 n=2 必须成功，加入 tools 后必须失败；本例内 n=2 对照失败则 FAIL，不算正确拒绝。 | 默认运行；仅原生接口 |
| 17_07 | [`test_17_07_n_with_roles_and_parameters`](../m2_her_text_tests.py#L1066) | [S：必须成功](../README.md#verdict-rules) | 完整七角色对话（system、user_system、group、示例对话、历史问答、当前提问，每条都带 name） + n=2 + temperature=0.7 + top_p=0.95，输出上限分别用 max_tokens=100 和 max_completion_tokens=100。 | 返回两条完整回复，外层字段和 usage 正确；此项不检查每条回复的 100 token 上限。 | 默认运行；仅原生接口 |
| 17_08 | [`test_17_08_n_configured_boundary`](../m2_her_text_tests.py#L1089) | [按变体区分，见校验点](../README.md#verdict-rules) | 两个非流式变体：at_limit 只发 n=N；above_limit 先发 n=N，成功后再发 n=N+1。N 默认为4，可由 --n-limit 修改。 | n=N 必须返回 N 条完整回复；above_limit 的第二步必须失败。首步失败直接 FAIL，不能当作超过上限的正确拒绝。 | 默认运行；--n-limit 可修改上限值 |

## 18 request_metadata — metadata / user / mask_sensitive_info

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 18_01 | [`test_18_01_request_metadata_valid`](../m2_her_text_tests.py#L1109) | [S：必须成功](../README.md#verdict-rules) | metadata 为字符串键值对（含中文、255 字节长的键和值），user 为字符串，mask_sensitive_info 为 true / false。 | 请求成功，响应格式正确；不检查日志记录或脱敏效果。 | 默认运行；仅原生接口 |
| 18_02 | [`test_18_02_request_metadata_invalid_type`](../m2_her_text_tests.py#L1145) | [F：必须失败](../README.md#verdict-rules) | metadata 为字符串、数组或值为数字；user 为数字或对象；mask_sensitive_info 为字符串或数字。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行；仅原生接口 |
| 18_03 | [`test_18_03_metadata_length_boundary`](../m2_her_text_tests.py#L1153) | [F：必须失败](../README.md#verdict-rules) | metadata 的键或值长 256 字节（上限 255）。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行；仅原生接口 |

## 19 language_consistency — 回复语言

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 19_01 | [`test_19_01_reply_follows_user_language`](../m2_her_text_tests.py#L1176) | [S：必须成功](../README.md#verdict-rules) | 分别用简体中文、繁体中文、英、日、韩、西、法、德、葡、俄、阿 11 种语言提问。 | 每个语种、每种流式模式最多 3 次，至少 2 次通过语种检查；达到2次通过即停止，已有2次语种失败即判失败。请求或响应格式错误立即失败，不用重试掩盖。 | 需 --run-behavior（模型行为，单独统计） |
| 19_04 | [`test_19_04_multiturn_language_retention`](../m2_her_text_tests.py#L1236) | [S：必须成功](../README.md#verdict-rules) | 角色设定用语言 A，用户已经用语言 B 聊了三轮，再继续提问；中英日韩两两组合共 12 组。 | 继续用用户的语言 B 回复，不被设定语言带偏。 | 需 --run-behavior（模型行为，单独统计） |

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
