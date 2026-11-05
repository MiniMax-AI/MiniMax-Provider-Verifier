# M2-Her 文本与角色格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_text_tests.py`](../m2_her_text_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**17**；case 函数数：**89**；pytest 收集 items 数：**449**
> 期望值：按 2026-11-05 线上实际返回设定，与官网文档不一致处以线上为准；判定原则与允许的随机性见 [README](../README.md)。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 01 | basic_text | 基础文本 | 6 |
| 02 | system_persona | system 人设 | 5 |
| 03 | user_system | user_system 用户设定 | 4 |
| 04 | group | group 场景 | 3 |
| 05 | sample_messages | 示例对话 sample_message_* | 5 |
| 06 | names | name 字段 | 4 |
| 07 | multiturn | 多轮对话 | 6 |
| 08 | sampling | 采样参数（temperature / top_p） | 5 |
| 09 | completion_limit | 输出预算 max_completion_tokens | 5 |
| 10 | response_usage | 响应结构与 usage | 7 |
| 11 | error_codes | 错误处理 | 9 |
| 12 | long_context | 长输入与 64K 上下文 | 4 |
| 13 | role_combo | 七角色组合 | 5 |
| 16 | guide_alignment | 官网示例结构 | 4 |
| 17 | candidate_count | n 多候选 | 8 |
| 18 | request_metadata | metadata / user / mask_sensitive_info | 3 |
| 19 | language_consistency | 语种一致性 | 6 |

---

## 01 basic_text — 基础文本

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 01_01 | [`test_01_01_minimal_user_message`](../m2_her_text_tests.py#L85) | 只发送一条 user 消息，不带 system、name 和可选参数，流式与非流式各一次。 | HTTP 200 且 base_resp 为 0，返回一条非空的 assistant 回复；流式 SSE 可严格解析、结束原因唯一。 | 默认 |
| 01_02 | [`test_01_02_system_user_chat`](../m2_her_text_tests.py#L89) | system 设定为“友好的助手”，user 发送“你好”。 | 普通人设请求被接受，回复结构合法、正文非空。 | 默认 |
| 01_03 | [`test_01_03_chinese_text`](../m2_her_text_tests.py#L96) | 用中文要求写一句简短问候（行为评估）。 | 正文包含中文字符，且没有 U+FFFD 替换字符。 | --run-behavior；独立统计，不计入格式通过率 |
| 01_04 | [`test_01_04_english_text`](../m2_her_text_tests.py#L108) | 用英文要求只用英文写一句问候（行为评估）。 | 正文包含英文单词，且不夹带中文字符。 | --run-behavior；独立统计，不计入格式通过率 |
| 01_05 | [`test_01_05_text_escaping_unicode`](../m2_her_text_tests.py#L119) | user 内容包含双引号、反斜杠、换行和 emoji，并要求原样输出。 | 请求被接受，响应按严格 UTF-8 / JSON（SSE）解码成功；不检查是否逐字回显，逐字回显见 16_03。 | 默认 |
| 01_06 | [`test_01_06_multilingual_input`](../m2_her_text_tests.py#L135) | 中文问句里夹带日文、韩文、阿拉伯文、俄文或组合重音字符的问候。 | 各类 Unicode 输入均被接受，回复结构合法；不要求翻译或提取，提取任务见 16_02。 | 默认 |

## 02 system_persona — system 人设

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 02_01 | [`test_02_01_system_identity`](../m2_her_text_tests.py#L147) | system 设定身份编号 AI_K72，user 要求只返回身份编号。 | 回复包含 AI_K72，说明模型读取了 system 设定。 | --run-behavior；独立统计，不计入格式通过率 |
| 02_02 | [`test_02_02_system_reply_prefix`](../m2_her_text_tests.py#L157) | system 要求每条回复以 HER_REPLY: 开头，user 发送“你好”。 | 回复以 HER_REPLY: 开头。 | --run-behavior；独立统计，不计入格式通过率 |
| 02_03 | [`test_02_03_system_output_format`](../m2_her_text_tests.py#L168) | system 要求只输出 {"status":"ready","count":2}，不发送 response_format。 | 正文可直接解析为该 JSON 对象。这是提示词遵循目标，不代表接口支持 response_format。 | --run-behavior；独立统计，不计入格式通过率 |
| 02_04 | [`test_02_04_system_identity_multiturn`](../m2_her_text_tests.py#L182) | system 设定身份后插入 4 轮无关历史，再询问身份。 | 回复仍包含 AI_K72，人设没有在多轮中丢失。 | --run-behavior；独立统计，不计入格式通过率 |
| 02_05 | [`test_02_05_system_identity_isolation`](../m2_her_text_tests.py#L194) | 两次独立请求分别把身份设为 AI_K72 和 AI_B19，并用同一问题询问。 | 每次只返回本次请求的身份，不出现另一次请求的编号。 | --run-behavior；独立统计，不计入格式通过率 |

## 03 user_system — user_system 用户设定

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 03_01 | [`test_03_01_user_system_identity`](../m2_her_text_tests.py#L208) | 只通过 user_system 提供用户编号 USER_P38，再询问用户编号。 | 回复包含 USER_P38，说明模型读取了用户人设。 | --run-behavior；独立统计，不计入格式通过率 |
| 03_02 | [`test_03_02_user_assistant_identity_separation`](../m2_her_text_tests.py#L219) | system 提供 AI 编号、user_system 提供用户编号，分两次询问 AI 身份和用户身份；比较不带 name 与全部具名两种配置。 | 按线上实际：全部具名时，问 AI 返回 AI_K72，问用户也只返回含 AI_K72 的回复，从不返回 USER_P38；省略 name 时两次请求都被拒：非流式返回 HTTP 200 + 业务码 2013「invalid params, 400」；流式返回单个 SSE 事件，业务码 1000「unknown error, 999」。 | --run-behavior；独立统计，不计入格式通过率 |
| 03_03 | [`test_03_03_user_system_multiturn`](../m2_her_text_tests.py#L252) | user_system 提供小组编号 TEAM_L63，之后插入 4 轮历史再询问。 | 回复包含 TEAM_L63。 | --run-behavior；独立统计，不计入格式通过率 |
| 03_04 | [`test_03_04_user_system_omitted`](../m2_her_text_tests.py#L263) | 只有 system 和 user，不带 user_system。 | user_system 是可选角色，缺少时请求正常成功。 | 默认 |

## 04 group — group 场景

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 04_01 | [`test_04_01_group_scene_name`](../m2_her_text_tests.py#L274) | 只用 group 消息提供场景编号 SCENE_R64，再询问当前场景。 | 回复包含 SCENE_R64。 | --run-behavior；独立统计，不计入格式通过率 |
| 04_02 | [`test_04_02_group_scene_isolation`](../m2_her_text_tests.py#L289) | 同一问题分两次请求，分别搭配场景 SCENE_R64 和 SCENE_N21。 | 每次只返回本次请求的场景编号。 | --run-behavior；独立统计，不计入格式通过率 |
| 04_03 | [`test_04_03_group_omitted`](../m2_her_text_tests.py#L303) | 普通 user 请求，不带 group。 | group 非必填，请求正常成功。 | 默认 |

## 05 sample_messages — 示例对话 sample_message_*

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 05_01 | [`test_05_01_single_sample_pair`](../m2_her_text_tests.py#L309) | 一组具名 sample_message_user / sample_message_ai 后接真实 user 输入。 | 示例角色被接受，回复结构合法；不要求模仿示例的输出格式。 | 默认 |
| 05_02 | [`test_05_02_three_sample_pairs`](../m2_her_text_tests.py#L318) | 三组示例对话后接真实 user 输入。 | 多组示例被接受，回复结构合法。 | 默认 |
| 05_03 | [`test_05_03_sample_output_pattern`](../m2_her_text_tests.py#L328) | system 明确要求“转为大写并加 RESULT: 前缀”，配两组示例，当前输入 lemon。 | 按线上实际：回复恰好是 LEMON，不带要求的 RESULT: 前缀。 | --run-behavior；独立统计，不计入格式通过率 |
| 05_04 | [`test_05_04_sample_vs_current_question`](../m2_her_text_tests.py#L347) | 示例输入为 apple，真实输入为 kiwi；比较不带 name 与全部具名两种配置。 | 全部具名时回复包含 kiwi（忽略大小写）；按线上实际，示例消息省略 name 时请求被拒：非流式返回 HTTP 200 + 业务码 2013「invalid params, 400」；流式返回单个 SSE 事件，业务码 1000「unknown error, 999」。 | --run-behavior；独立统计，不计入格式通过率 |
| 05_05 | [`test_05_05_samples_with_real_history`](../m2_her_text_tests.py#L364) | 两组示例 + 一轮真实问答历史 + 当前输入，全部具名。 | 示例和真实历史同时出现时请求被接受，回复结构合法。 | 默认 |

## 06 names — name 字段

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 06_01 | [`test_06_01_name_omitted`](../m2_her_text_tests.py#L377) | 单条 user 消息，不带 name。 | 没有多个同类发送者时 name 可省略，请求正常成功。 | 默认 |
| 06_02 | [`test_06_02_name_unicode`](../m2_her_text_tests.py#L384) | user 的 name 分别为中文、英文和带 emoji 的 Unicode 字符串。 | 各种字符串 name 均被接受，回复结构合法；不要求模型复述 name。 | 默认 |
| 06_03 | [`test_06_03_multiple_named_users`](../m2_her_text_tests.py#L394) | 两位用户 Alice、Bob 各报一个通行编号；第二次请求交换 name 与编号的对应关系，正文和顺序不变，要求按 JSON 返回。 | 两次都返回正确的 {"Alice": …, "Bob": …}，说明事实绑定到 name，而不是消息顺序。 | --run-behavior；独立统计，不计入格式通过率 |
| 06_04 | [`test_06_04_multiple_named_assistants`](../m2_her_text_tests.py#L416) | 两位助手 Alpha、Beta 各报一条记录；第二次请求交换 name 与记录的对应关系，要求按 JSON 返回。 | 两次都返回正确的 {"Alpha": …, "Beta": …}。 | --run-behavior；独立统计，不计入格式通过率 |

## 07 multiturn — 多轮对话

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 07_01 | [`test_07_01_two_turn_memory`](../m2_her_text_tests.py#L439) | 上一轮用户告知编号 HER_M41，本轮询问该编号。 | 回复包含 HER_M41。 | --run-behavior；独立统计，不计入格式通过率 |
| 07_02 | [`test_07_02_five_turn_facts`](../m2_her_text_tests.py#L451) | 5 轮“编号 → 记录值”历史，询问第 0 条和第 4 条。 | 回复同时包含 HER_00_VALUE 和 HER_04_VALUE。 | --run-behavior；独立统计，不计入格式通过率 |
| 07_03 | [`test_07_03_twenty_turn_history`](../m2_her_text_tests.py#L460) | 20 轮“编号 → 记录值”历史，询问第 0 条和第 19 条。 | 回复同时包含 HER_00_VALUE 和 HER_19_VALUE。 | --run-behavior；独立统计，不计入格式通过率 |
| 07_04 | [`test_07_04_actual_response_roundtrip`](../m2_her_text_tests.py#L468) | 第一轮请模型确认编号；第二轮把第一轮的真实回答作为 assistant 历史回传，再继续提问。 | 两轮请求都成功，真实回答可以原样作为历史再次提交；不检查回忆是否准确。 | 默认 |
| 07_05 | [`test_07_05_latest_fact_correction`](../m2_her_text_tests.py#L480) | 用户先给出编号 OLD_K19，随后更正为 NEW_T83，再询问编号。 | 回复包含 NEW_T83，且不包含 OLD_K19。 | --run-behavior；独立统计，不计入格式通过率 |
| 07_06 | [`test_07_06_conversation_isolation`](../m2_her_text_tests.py#L494) | 两次独立请求各自约定暗号 CODE_A17 和 CODE_B29。 | 每次只返回本次对话的暗号。 | --run-behavior；独立统计，不计入格式通过率 |

## 08 sampling — 采样参数（temperature / top_p）

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 08_01 | [`test_08_01_sampling_omitted`](../m2_her_text_tests.py#L508) | 原始请求完全不带 temperature 和 top_p。 | 使用服务默认采样，请求正常成功；测试代码不会自动补参数。 | 默认 |
| 08_02 | [`test_08_02_temperature_valid`](../m2_her_text_tests.py#L513) | temperature 分别取 0.01、0.5、1.0（仅非流式）。 | 官网范围 (0, 1] 内的取值都被接受，回复合法；不比较随机性。 | 默认 |
| 08_03 | [`test_08_03_temperature_invalid`](../m2_her_text_tests.py#L522) | temperature 取 0、-0.1、1.01、字符串 "0.5" 和布尔值 true，流式与非流式各一次。 | 按线上实际：0 与 1.01 请求成功；-0.1 非流式返回业务码 1000「unknown error, 500」、流式返回 SSE 业务码 1000「unknown error, 999」；字符串与布尔值返回 2013 参数错误。 | 默认 |
| 08_04 | [`test_08_04_top_p_valid`](../m2_her_text_tests.py#L536) | top_p 分别取 0.01、0.5、0.95、1.0（仅非流式）。 | 官网范围 (0, 1] 内的取值都被接受，回复合法。 | 默认 |
| 08_05 | [`test_08_05_top_p_invalid`](../m2_her_text_tests.py#L545) | top_p 取 0、-0.1、1.01、字符串 "0.95" 和布尔值 true，流式与非流式各一次。 | 按线上实际：0 请求成功；-0.1、1.01、字符串与布尔值返回 2013 参数错误。 | 默认 |

## 09 completion_limit — 输出预算 max_completion_tokens

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 09_01 | [`test_09_01_completion_limit_omitted`](../m2_her_text_tests.py#L556) | 原始请求既不带 max_tokens，也不带 max_completion_tokens。 | 使用部署默认预算，请求正常成功。 | 默认 |
| 09_02 | [`test_09_02_completion_limit_valid`](../m2_her_text_tests.py#L563) | max_completion_tokens 分别取 1、2、32、2047、2048。 | 预算被接受，实际 completion_tokens 不超过预算，触发 length 时必须恰好等于预算；1 token 时允许正文为空。 | 需真实 completion_tokens；缺失报告计数不可验证 |
| 09_03 | [`test_09_03_completion_limit_nonpositive`](../m2_her_text_tests.py#L571) | max_completion_tokens 取 0 和 -1。 | 按线上实际：0 与 -1 都被接受，正常回答。 | 默认 |
| 09_04 | [`test_09_04_completion_limit_type`](../m2_her_text_tests.py#L582) | max_completion_tokens 取小数 1.5、字符串 "32"、布尔值 true 和 null。 | 按线上实际：null 被接受并正常回答；小数、字符串与布尔值返回 2013 参数错误。 | 默认 |
| 09_05 | [`test_09_05_completion_length_truncation`](../m2_her_text_tests.py#L593) | 长篇续写任务，先给 8 token 预算；若模型提前自然结束，再换一个续写提示、预算降到 1。 | 至少一次以 finish_reason=length 结束，且 completion_tokens 恰好等于预算；两次都没截断则用例失败。 | 需真实 completion_tokens；缺失报告计数不可验证 |

## 10 response_usage — 响应结构与 usage

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 10_01 | [`test_10_01_response_envelope`](../m2_her_text_tests.py#L599) | 普通请求，检查 id、object、created、model 和 choices。 | 字段存在且类型正确，object 与消息形态一致，model 等于请求模型（或配置的响应模型名）；流式各包的 id、model、created 一致。 | 默认 |
| 10_02 | [`test_10_02_response_message`](../m2_her_text_tests.py#L607) | 非流式普通请求。 | message.role 为 assistant，content 为非空字符串。 | 默认 |
| 10_03 | [`test_10_03_finish_reason_stop`](../m2_her_text_tests.py#L613) | system 和示例约束只回答 OK；先给 128 token 预算，若被截断再放宽到 512。 | 至少一次以 finish_reason=stop 结束，且实际计数不超过预算；两次都没自然结束则用例失败。 | 默认 |
| 10_04 | [`test_10_04_usage_total_tokens`](../m2_her_text_tests.py#L618) | 输出预算分别为 1 和 32 的普通请求。 | usage.total_tokens 为正整数（不能是布尔值）；只输出 1 token 时也必须有用量。 | 默认 |
| 10_05 | [`test_10_05_usage_breakdown_math`](../m2_her_text_tests.py#L627) | 普通请求，检查 usage 的结构。 | usage 结构合法；出现 prompt_tokens / completion_tokens 时类型正确，且 total = prompt + completion。细分字段缺失只记录，不判失败。 | 可选字段按出现检查并记录覆盖 |
| 10_06 | [`test_10_06_sensitivity_field_types`](../m2_her_text_tests.py#L641) | 普通请求，检查 input_sensitive、output_sensitive 等字段。 | 这些字段出现时类型正确（布尔或整数），缺失只记录覆盖情况；不验证内容审核本身。 | 可选字段按出现检查并记录覆盖 |
| 10_07 | [`test_10_07_prompt_tokens_across_modes`](../m2_her_text_tests.py#L655) | 基础对话和具名七角色两种输入，分别在非流式、流式下发送原输入和追加 256 段背景的输入，共 4 次请求。 | 同一模式下追加输入后 prompt_tokens 必须严格增加；跨模式计数相等只在显式覆盖规则时检查。 | --run-compat；自带计数增长断言，需真实 prompt_tokens |

## 11 error_codes — 错误处理

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 11_01 | [`test_11_01_invalid_model`](../m2_her_text_tests.py#L696) | model 缺失、为不存在的名称、空字符串、null 或数字。 | 返回模型/参数错误（业务码 2013 或 HTTP 400/404/422）；测试代码不会补默认模型。 | 默认 |
| 11_02 | [`test_11_02_invalid_messages`](../m2_her_text_tests.py#L712) | messages 缺失、为 null、字符串或对象。 | 返回结构化参数错误，不能假成功。 | 默认 |
| 11_03 | [`test_11_03_invalid_role`](../m2_her_text_tests.py#L725) | 消息的 role 缺失、为未定义的取值或数字。 | 返回结构化参数错误。 | 默认 |
| 11_04 | [`test_11_04_invalid_content`](../m2_her_text_tests.py#L746) | content 缺失、为 null、数字、对象，或为文本 / 图片 / 视频 / 音频 parts 数组。 | 按线上实际：视频 parts 返回 2013「invalid params, M2-her not support video」；其余输入返回同一响应体内的两个 JSON——先是状态 0 的占位信封，再是业务码 1000「unknown error」。 | 仅 native；兼容端点单独核对 |
| 11_05 | [`test_11_05_invalid_name_type`](../m2_her_text_tests.py#L789) | 消息的 name 为数字、对象或数组。 | 返回结构化参数错误。 | 默认 |
| 11_06 | [`test_11_06_authentication_errors`](../m2_her_text_tests.py#L802) | 完全不带 Authorization，或使用无效的 Key。 | 返回鉴权错误（业务码 1004 或 HTTP 401/403）。 | 默认 |
| 11_07 | [`test_11_07_invalid_request_envelope`](../m2_her_text_tests.py#L821) | 发送被截断的 JSON、顶层数组，或 stream 为字符串 / 数字。 | 返回结构化参数错误，不能是 500。 | 默认 |
| 11_08 | [`test_11_08_legacy_sample_role_spelling`](../m2_her_text_tests.py#L845) | 把示例角色改成旧拼写 user_sample_message / ai_sample_message；前置对照使用同内容的正确拼写。 | 正确拼写的对照成功，旧拼写返回参数错误。 | 仅 native；同内容正确角色对照失败时 SKIP |
| 11_09 | [`test_11_09_invalid_message_item`](../m2_her_text_tests.py#L862) | messages 是数组，但元素为 null、字符串、数字或数组。 | 按线上实际：字符串、数字、数组元素返回 2013 参数错误；null 元素在两种模式下都返回纯 JSON 业务码 1000「unknown error」。 | 默认 |

## 12 long_context — 长输入与 64K 上下文

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 12_01 | [`test_12_01_long_system`](../m2_her_text_tests.py#L875) | system 约 500 行背景记录，首、中、尾各有一个暗号。 | 长输入被接受，回复结构合法；不要求检索暗号。 | --run-slow |
| 12_02 | [`test_12_02_long_persona_and_samples`](../m2_her_text_tests.py#L893) | 在 user_system 或 sample_message_ai 中放入约 500 行长文本。 | 长人设 / 长示例被接受，回复结构合法。 | --run-slow |
| 12_03 | [`test_12_03_context_within_64k`](../m2_her_text_tests.py#L914) | 运行时先用 1-token 探针按真实 prompt_tokens 校准出接近 64K 的输入，再以 64 token 预算正式请求。 | 请求成功，且 prompt_tokens 与校准时的测量值一致。 | --run-slow；自动校准，可提供 context fixture 覆盖 |
| 12_04 | [`test_12_04_context_over_64k`](../m2_her_text_tests.py#L931) | 复用 12_03 校准出的同一长输入，把输出预算提高到 2048，使“输入 + 预留输出”超过窗口。 | 按线上实际：非流式返回 2013 且说明 context window exceeds limit；流式返回单个 SSE 事件，业务码 1000「unknown error, 999」。 | --run-slow；自动校准，可提供 context fixture 覆盖 |

## 13 role_combo — 七角色组合

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 13_01 | [`test_13_01_all_seven_roles`](../m2_her_text_tests.py#L959) | system、user_system、group、一组示例、user/assistant 历史和当前 user 一次发送；比较部分省略 name（官网原始写法）与全部具名两种配置。 | 按线上实际：全部具名时成功、回复结构合法；保留原始省略名称时请求被拒：非流式返回 HTTP 200 + 业务码 2013「invalid params, 400」；流式返回单个 SSE 事件，业务码 1000「unknown error, 999」。 | 默认 |
| 13_02 | [`test_13_02_persona_samples_named_history`](../m2_her_text_tests.py#L969) | 具名七角色加两位访客的物品编号，要求按 RESULT: 格式依次返回六项信息。 | 按线上实际：回复为 AI_K72\|USER_P38\|SCENE_R64\|CODE_V59\|ITEM_A73\|ITEM_B84，不带 RESULT: 前缀；结尾偶尔多一个 \|，不影响判定。 | --run-behavior；独立统计，不计入格式通过率 |
| 13_03 | [`test_13_03_long_history_small_output`](../m2_her_text_tests.py#L990) | 20 轮历史配 64 token 输出预算。 | completion_tokens 不超过 64，触发 length 时恰好等于 64。 | 需真实 completion_tokens；缺失报告计数不可验证 |
| 13_04 | [`test_13_04_roles_with_sampling`](../m2_her_text_tests.py#L997) | 具名七角色，同时传 temperature=0.5、top_p=0.95。 | 请求被接受，回复结构合法。 | 默认 |
| 13_05 | [`test_13_05_one_special_name_omitted`](../m2_her_text_tests.py#L1007) | 具名七角色中每次只去掉 user_system、group、示例 user 或示例 ai 其中一个的 name。 | 按线上实际：省略任一高级角色的 name 都被拒：非流式返回 HTTP 200 + 业务码 2013「invalid params, 400」；流式返回单个 SSE 事件，业务码 1000「unknown error, 999」。 | 默认 |

## 16 guide_alignment — 官网示例结构

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 16_01 | [`test_16_01_guide_role_structures`](../m2_her_text_tests.py#L1018) | 按官网指南的基础对话、角色扮演、示例引导三种结构发送，比较原始省略 name 与全部具名。 | 按线上实际：具名配置与基础聊天成功、回复结构合法；角色扮演、示例引导省略名称时请求被拒：非流式返回 HTTP 200 + 业务码 2013「invalid params, 400」；流式返回单个 SSE 事件，业务码 1000「unknown error, 999」。 | 默认 |
| 16_02 | [`test_16_02_explicit_marker_extraction`](../m2_her_text_tests.py#L1033) | 日文、韩文、阿拉伯文、俄文或组合重音字符的问候后跟标记 UNICODE_K72，要求只返回完整标记。 | 按线上实际：日语、组合重音恰好返回 UNICODE_K72；韩语、俄语、阿拉伯语通常把问候语用 _ 接在标记后（也接受只返回标记）。偶发写满预算的重复内容会判失败。 | --run-behavior；独立统计，不计入格式通过率 |
| 16_03 | [`test_16_03_exact_echo`](../m2_her_text_tests.py#L1053) | 要求原样输出含引号、反斜杠、换行和 emoji 的文本。 | 按线上实际：模型以角色口吻回应，不回显原文（回复中不含 "HER"）。 | --run-behavior；独立统计，不计入格式通过率 |
| 16_04 | [`test_16_04_context_recall`](../m2_her_text_tests.py#L1067) | 800 条记录的开头、中间、结尾各放一个标记，要求按顺序返回三个标记。 | 回复同时包含 BEGIN_P38、MIDDLE_P49、END_P50。 | --run-behavior；独立统计，不计入格式通过率；--run-slow |

## 17 candidate_count — n 多候选

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 17_01 | [`test_17_01_n_default_single_choice`](../m2_her_text_tests.py#L1085) | n 省略、为 null、0 或 -1。 | 按线上实际回落为 1，只返回一条候选，响应外层合法。 | 默认；native；服务端附加字段，独立统计 |
| 17_02 | [`test_17_02_n_candidate_count`](../m2_her_text_tests.py#L1097) | 非流式请求，n=1 和 n=2。 | choices 数量等于 n，index 为 0..n-1 且不重复，每条候选结构完整，usage 合法；不要求候选内容互不相同。 | 默认；native；服务端附加字段，独立统计 |
| 17_03 | [`test_17_03_n_one_stream`](../m2_her_text_tests.py#L1105) | 流式请求显式传 n=1。 | 保持单候选 SSE 结构和结束标记。 | 默认；native；服务端附加字段，独立统计 |
| 17_04 | [`test_17_04_n_invalid_type`](../m2_her_text_tests.py#L1126) | n 为小数、字符串、true、false、对象、数组或超出 int64 的整数。 | 返回结构化参数错误。 | 默认；native；服务端附加字段，独立统计 |
| 17_05 | [`test_17_05_n_stream_conflict`](../m2_her_text_tests.py#L1131) | 先确认非流式 n=2 正常，再发送 stream=true 且 n=2。 | 返回包含 “stream and n > 1” 的明确参数错误。 | 默认；native；服务端附加字段，独立统计 |
| 17_06 | [`test_17_06_n_tools_conflict`](../m2_her_text_tests.py#L1145) | 先确认非流式 n=2 正常，再在同一请求上附加合法的 tools。 | 返回包含 “tools and n > 1” 的明确参数错误；普通的“不支持 tools”错误不算通过。 | 默认；native；服务端附加字段，独立统计 |
| 17_07 | [`test_17_07_n_with_roles_and_parameters`](../m2_her_text_tests.py#L1169) | 具名七角色 + n=2 + temperature=0.7 + top_p=0.95，预算字段分别单独使用 max_tokens=100 和 max_completion_tokens=100。 | 返回两条完整候选，外层和 usage 合法；不以合计 usage 推算单条候选的预算。 | 默认；native；服务端附加字段，独立统计 |
| 17_08 | [`test_17_08_n_configured_boundary`](../m2_her_text_tests.py#L1192) | 非流式请求：at_limit 发送 n=4；above_limit 先发 n=4 作为正常对照，再发 n=5。传 --n-limit 时用指定值替换 4。 | 按线上实际：n=4 返回 4 条完整候选；n=5 返回 HTTP 200 + 业务码 1000「unknown error, 500」，没有明确的上限声明。 | 默认按观测上限 n=4；--n-limit 可替换上限值 |

## 18 request_metadata — metadata / user / mask_sensitive_info

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 18_01 | [`test_18_01_request_metadata_valid`](../m2_her_text_tests.py#L1215) | metadata 字符串映射（含中文、255 字节键值）、user 字符串、mask_sensitive_info=true/false。 | 请求被接受，响应外层合法；不验证日志存储或脱敏效果。 | 默认；native；服务端附加字段，独立统计 |
| 18_02 | [`test_18_02_request_metadata_invalid_type`](../m2_her_text_tests.py#L1251) | metadata 为字符串、数组或值为数字；user 为数字或对象；mask_sensitive_info 为字符串或数字。 | 返回结构化参数错误。 | 默认；native；服务端附加字段，独立统计 |
| 18_03 | [`test_18_03_metadata_length_boundary`](../m2_her_text_tests.py#L1259) | metadata 的键或值长度为 256 字节（上限 255）。 | 返回包含 “metadata key length” 或 “metadata value length” 的参数错误。 | 默认；native；服务端附加字段，独立统计 |

## 19 language_consistency — 语种一致性

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 19_01 | [`test_19_01_reply_follows_user_language`](../m2_her_text_tests.py#L1286) | 简中、繁中、英、日、韩、西、法、德、葡、俄、阿 11 种语言的单语提问。 | 回复使用与提问相同的语种，不夹带其他语种的句子或文字。 | --run-behavior；独立统计，不计入格式通过率 |
| 19_02 | [`test_19_02_persona_language_differs_from_user`](../m2_her_text_tests.py#L1343) | 具名七角色设定与用户提问使用不同语言，未指定回复语种；中、英、日、韩、西 5 种语言两两排列共 20 组，如日文设定配中文用户。 | 按线上实际：中→英、英→中 / 日 / 西、韩→英 5 组严格为用户语种（不夹带外语）；其余 15 组的主体语种为通常沿用的设定语种（中→日为日语夹中文动作描写）。采样偶发翻转可能导致单轮失败。 | --run-behavior；独立统计，不计入格式通过率 |
| 19_03 | [`test_19_03_explicit_reply_language`](../m2_her_text_tests.py#L1375) | system 或用户明确要求用某种语言回复，且与提问语种不同；system 指令与用户自述各 4 组，中、英、日、韩都会作为目标语种。 | 按线上实际：7 组严格为指定语种；日语用户要求中文时主体语种为日语。偶发夹带外语可能导致单轮失败。 | --run-behavior；独立统计，不计入格式通过率 |
| 19_04 | [`test_19_04_multiturn_language_retention`](../m2_her_text_tests.py#L1419) | 人设使用语种 A，用户已用语种 B 进行三轮对话后继续提问；中、英、日、韩两两排列共 12 组。 | 继续使用用户的语种，不被人设语种拉回。 | --run-behavior；独立统计，不计入格式通过率 |
| 19_05 | [`test_19_05_language_switch_follows_latest_turn`](../m2_her_text_tests.py#L1466) | system 和三轮历史都是语种 A，最后一轮用户改用语种 B；中、英、日、韩两两排列共 12 组。 | 按线上实际：中→日、韩→英严格为最新一轮的语种（韩→英约 3/10 仍回韩语，会导致单轮失败）；其余 10 组主体语种为历史语种 A。 | --run-behavior；独立统计，不计入格式通过率 |
| 19_06 | [`test_19_06_language_stability_default_sampling`](../m2_her_text_tests.py#L1484) | 中文七角色设定 + 英 / 日 / 韩用户，不传采样参数，每个变体重复 5 次。 | 按线上实际：默认采样下回复在用户语种与设定语种（中文）之间漂移；每次的主体语种须是两者之一，偶发的第三种语言（日语、英语、繁体中文都出现过）判失败。逐次判定作为证据保存。 | --run-behavior；独立统计，不计入格式通过率；--run-slow |

---

## 附录：parametrize 展开后的 449 个 items

| 展开因子 | 涉及 case |
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
| `persona,language(20) × stream(2)` | 19_02 |
| `variant(8) × stream(2)` | 19_03 |
| `persona,language(12) × stream(2)` | 19_04 |
| `previous,language(12) × stream(2)` | 19_05 |
| `language(3) × stream(2)` | 19_06 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。
