# M3 文本模态格式校验 case 清单

> 对应文件:`data/m3_api_test/m3_text_tests.py`
> 场景说明以 `M3.1-Flash:` 开头的行对应 `m3_format_check/m3_1_flash_text_test.py`,其余行对应上述文件。
> `M3.1-Flash:` 行用到的严格断言(`helpers.py`)在一次响应上检查全部规则,并把所有违规项一起报出:
> - `assert_chat_completion_strict`:单个 JSON 对象(非 SSE),带 `id` / `object=chat.completion` / `created` / `model`;choice `index` 为互不相同的整数;assistant 消息必带 `content` 键(字符串或 null),`refusal` 为字符串或 null;`finish_reason` 取值合法;`tool_calls` 缺省 / null 或为非空数组,元素恰好含 `id` / `type=function` / `function{name, arguments(字符串)}` 且 id 互不相同;usage 规则同流式(见 `m3_stream_cases.md`)。
> - `assert_error_response_strict`:HTTP 400,`Content-Type` 为 JSON,错误体带 `error` 对象(`message` 为非空字符串,`type` 为字符串或 null,`code` 为字符串、整数或 null),不带 `choices`。
> - 流式的 `assert_sse_stream_strict` 见 `m3_stream_cases.md`。
> 命名规范:`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数:**20**;case 函数数:**107**;pytest 收集 items 数:**139**

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 01 | basic_text | 基础文本对话(非流式) | 3 |
| 02 | sse_stream | SSE 流式协议字段 | 6 |
| 03 | multiturn | 多轮对话 | 2 |
| 04 | thinking | thinking 思考开关 | 4 |
| 05 | sampling | 采样参数(temperature / top_p / seed) | 3 |
| 06 | max_tokens | max_tokens / max_completion_tokens 边界 | 11 |
| 07 | message_format | message 内容/角色格式与边界 | 6 |
| 08 | model_compat | 模型名兼容性 | 1 |
| 09 | response_format | response_format JSON 输出(**已全 skip,M3 暂不支持**) | 3 |
| 10 | usage_field | usage 字段语义/算术/cache | 8 |
| 11 | role_root | role=root 协议接受与身份遵循 | 4 |
| 12 | text_semantic | 文本语义遵循 | 6 |
| 13 | tool_call_basic | 工具调用基础 | 12 |
| 14 | tool_call_schema | 工具调用 schema 高级校验 | 6 |
| 15 | tool_call_combo | 工具调用与其他特性组合 | 6 |
| 16 | tool_call_edge | 工具调用边界 / 异常处理 | 14 |
| 17 | param_stress | 参数压力(长对话/长 system) | 2 |
| 18 | reasoning_split | reasoning_split 扩展字段 | 1 |
| 19 | finish_reason | finish_reason 覆盖 | 2 |
| 20 | error_codes | 错误码(纯文本) | 8 |

---

## 01 basic_text — 基础文本对话(非流式)

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 01_01 | `test_01_01_text_non_stream` | 非流式最基本文本对话 | HTTP 200 + 非空 content |
| 01_01 | `test_01_01_text_non_stream` | M3.1-Flash: 非流式基础文本对话,未声明 tools | `assert_chat_completion_strict` + `finish_reason=stop` + 正文非空 + 无工具调用 + `prompt_tokens_details` 缺省或为对象 |
| 01_02 | `test_01_02_content_string` | `user.content` 为纯字符串 | HTTP 200 |
| 01_03 | `test_01_03_content_array` | `user.content` 为 parts 数组 `[{type:text,text:...}]` | HTTP 200 |

## 02 sse_stream — SSE 流式协议字段

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 02_01 | `test_02_01_text_stream` | 文本流式回复 | 流可正常 rebuild content |
| 02_02 | `test_02_02_stream_usage` | 流式末尾 usage chunk | total == prompt + completion + 流式正常完结 |
| 02_03 | `test_02_03_sse_done_marker` | SSE 结束 `[DONE]` 标记 | 缺失则 xfail(已知 BUG) |
| 02_03 | `test_02_03_sse_done_marker` | M3.1-Flash: 读取原始 SSE 行 | 最后一个 data 行是 `[DONE]`,其后紧跟空行,不出现 `event: done`;缺失直接失败,不再 xfail |
| 02_04 | `test_02_04_stream_chunk_fields` | 流式 chunk 必带字段 | id / choices / object 全部存在 |
| 02_04 | `test_02_04_stream_chunk_fields` | M3.1-Flash: `include_usage=true`,遍历含 usage 尾块在内的全部 chunk | `id` / `choices` / `object=chat.completion.chunk` / `created` / `model` 类型正确,且同一条流内 `id`、`created` 不变 |
| 02_05 | `test_02_05_text_include_usage` | `stream_options.include_usage=true` 文本场景 | 流应正常返回 usage chunk |
| 02_06 | — | 已移出(原 `test_02_06_stream_usage_only_in_last_chunk`) | 与 `m3_stream_tests.py::TestSSEStream::test_02_06_stream_usage_only_in_last_chunk` 完全重复,已去重;编号保留空位不回收 |
| 02_07 | `test_02_07_stream_no_utf8_replacement_char_in_emoji` | 高密度 emoji 流式请求连续执行 20 次 | 任意 `delta.content` 中都不出现 `U+FFFD`（`�`）替换字符;防止四字节 emoji 被 UTF-8 分帧从中间截断 |

## 03 multiturn — 多轮对话

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 03_01 | `test_03_01_multiturn` | 两轮对话:自报 Alice 后问名字 | 响应应含 "alice" |
| 03_02 | `test_03_02_multiturn_5_rounds` | 5 轮算术对话 x=10, y=15, z=25 | 响应应含 "50"(x+y+z) |
| 03_04 | `test_03_04_history_message_forms[participant_names\|assistant_text_parts\|assistant_refusal_string\|assistant_refusal_null]` | M3.1-Flash: 历史消息形态:同角色不同 `name`、assistant 文本数组、`refusal` 为字符串 / null | `assert_oai_success` |

## 04 thinking — thinking 思考开关

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 04_02 | `test_04_02_thinking_adaptive` | `thinking.type=adaptive`(模型自决) | HTTP 200 |
| 04_03 | `test_04_03_thinking_invalid_value` | `thinking.type` 非法值 | 400/422 拒绝或 200 回落 |
| 04_04 | `test_04_04_thinking_stream` | adaptive + 流式 | 流式 + 思考共存可用 |

## 05 sampling — 采样参数(temperature / top_p / seed)

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 05_01 | `test_05_01_temperature_values` | temperature 合法值 [0, 0.5, 1, 2] | 各取值均 200 |
| 05_01 | `test_05_01_temperature_top_p_values[...]` | M3.1-Flash: `temperature` 0 / 0.2 / 2 / null,`top_p` 0.1 / 1 / null | `assert_oai_success`(只校验受理,不校验采样效果) |
| 05_02 | `test_05_02_top_p` | top_p 边界值 [0.1, 0.5, 0.95] | 各取值均 200 |
| 05_03 | `test_05_03_seed_parameter` | seed=42 + temperature=0 | 接口接受用于确定性输出 |
| 05_03 | `test_05_03_penalty_and_logit_bias[...]` | M3.1-Flash: presence / frequency penalty 取 -2 / 0 / 2,均带 `max_completion_tokens=64` | `assert_oai_success`,允许 `finish_reason=length` |
| 05_04 | `test_05_04_stop_array_and_null[four_sequences\|null]` | M3.1-Flash: `stop` 为 4 个序列的数组 / null | `assert_oai_success` |
| 05_05 | `test_05_05_seed_values[int64_min\|int64_max\|null]` | M3.1-Flash: `seed` 取 int64 上下界 / null | `assert_oai_success` |
| 05_07 | `test_05_07_same_seed_twice` | M3.1-Flash: 相同 `seed` 连发两次 | 两次均 `assert_oai_success`,不要求输出一致 |

## 06 max_tokens — max_tokens / max_completion_tokens 边界

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 06_01 | `test_06_01_max_tokens_truncation` | max_tokens=10 截断 | finish_reason ∈ {length, stop} |
| 06_02 | `test_06_02_max_completion_tokens` | max_completion_tokens 别名 | HTTP 200 |
| 06_03 | `test_06_03_dual_max_tokens` | 同传 max_tokens + max_completion_tokens | HTTP 200 |
| 06_04 | `test_06_04_both_params_combo` | 同传组合(mct wins 语义) | HTTP 200 |
| 06_05 | `test_06_05_mct_only` | 单传 max_completion_tokens=50 | finish_reason ∈ {length, stop} |
| 06_06 | `test_06_06_max_tokens_1_timeout` | max_tokens=1 极端值 | 200 或 408(BUG-4) |
| 06_07 | `test_06_07_max_tokens_zero` | max_tokens=0(非法值) | 200/400/422 都容忍 |
| 06_08 | `test_06_08_max_tokens_negative` | max_tokens=-1(非法值) | 400/422 拒绝(返 200 即 fail) |
| 06_09 | `test_06_09_max_tokens_at_512k` | max_tokens ∈ {512000, 524288} | HTTP 200 |
| 06_10 | `test_06_10_max_tokens_above_512k` | max_tokens ∈ {524289, 1000000} | 200/400/422 都容忍(严格 provider 拒,宽松 provider 接受截断) |
| 06_11 | `test_06_11_max_completion_tokens_at_512k` | max_completion_tokens=524288 | 200 或 400 |
| 06_12 | `test_06_12_no_output_limit` | M3.1-Flash: 原样发送,不带任何输出预算字段 | `assert_oai_success` |
| 06_14 | `test_06_14_legacy_max_tokens` | M3.1-Flash: 旧字段 `max_tokens=64` | `assert_oai_success` |
| 06_15 | `test_06_15_output_budget_null[max_completion_tokens\|max_tokens]` | M3.1-Flash: `max_completion_tokens` / `max_tokens` 显式 null | `assert_oai_success` |

## 07 message_format — 消息内容/角色格式与边界

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 07_01 | `test_07_01_consecutive_assistant` | 连续两条 assistant 消息 | HTTP 200(非流式/流式各 1 item) |
| 07_02 | `test_07_02_assistant_null_content_with_tool_calls` | assistant.content=null + tool_calls | HTTP 200 |
| 07_03 | `test_07_03_assistant_no_content_field_with_tool_calls` | assistant 省略 content 字段 + tool_calls | HTTP 200 |
| 07_04 | `test_07_04_user_content_empty_array` | user.content=[] 空数组 | status > 0 |
| 07_05 | `test_07_05_user_content_null` | user.content=null | 200 或 400 |
| 07_06 | `test_07_06_multiple_system_messages` | 多条 system 消息 | HTTP 200 + 非空响应 |
| 07_07 | `test_07_07_history_tool_call_empty_object_arguments` | 对话历史中工具调用的 arguments 为 `"{}"`（空 JSON 对象） | HTTP 200 且模型正常续接（产出非空 content 或新的 tool_call） |
| 07_10 | `test_07_10_invalid_message_structure[role_missing\|role_null]` | M3.1-Flash: message 缺 `role` / `role=null` | HTTP 400 |
| 07_12 | `test_07_12_user_content_forms[multiple_text_parts\|cjk_emoji_escapes\|empty_text_part]` | M3.1-Flash: user 多个 text part、含中文 / emoji / 转义的字符串、空 text part 与非空并存 | `assert_oai_success` |

## 08 model_compat — 模型名兼容性

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 08_01 | `test_08_01_model_name_compat` | 主模型 + mini 模型 | 主模型硬断言 200;mini 未注册 xfail |

## 09 response_format — response_format JSON 输出

> ⚠️ **本节全部 case 已 skip**:minimax-M3 目前不支持 `response_format=json_object` 参数,
> `TestResponseFormat` 整个 class 在 `m3_text_tests.py` 中加了 `@pytest.mark.skip(...)`。
> 等 M3 支持该参数后移除 skip 标记重新启用。同时 §15_02 原本含 `response_format` 的组合
> case 也已移除该字段,只保留 tools + tool_choice 共存校验。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 09_01 | `test_09_01_json_object_non_stream` | json_object 非流式(已 skip) | content 是合法 JSON dict |
| 09_01 | `test_09_01_text_and_json_object[type=text\|type=json_object]` | M3.1-Flash: `response_format` 为 text / json_object | `assert_oai_success` |
| 09_02 | `test_09_02_json_object_stream` | json_object 流式 + thinking=disabled(已 skip) | 流应正常返回 |
| 09_02 | `test_09_02_json_schema_strict[strict_schema\|with_description\|small_budget]` | M3.1-Flash: strict json_schema(含 description、小预算允许截断);不覆盖 `"type": [..., "null"]` 可空写法(参照端点不支持) | `assert_oai_success`(只校验受理,不校验 schema 符合度) |
| 09_03 | `test_09_03_json_object_format` | json_object 通用(非流式/流式)(已 skip) | 合法 JSON;BUG-3 包裹则 xfail |
| 09_08 | `test_09_08_schema_keywords[all_json_types]` | M3.1-Flash: strict schema 覆盖全部非 null 的 JSON 类型;不覆盖可空写法 | `assert_oai_success` |

## 10 usage_field — usage 字段语义/算术/cache

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 10_01 | `test_10_01_response_field_completeness` | Response 顶层字段完整性 | id/model/created/object/choices/usage 等都存在 |
| 10_02 | `test_10_02_usage_token_math` | usage 算术 | total == prompt + completion;cached <= prompt |
| 10_03 | `test_10_03_usage_field_types` | usage 三字段类型 | int 且 >= 0 |
| 10_04 | `test_10_04_cached_tokens_presence` | cached_tokens 硬存在 | 同 prompt 跑两次第二次 cached > 0 |
| 10_04 | `test_10_04_cached_tokens_presence` | M3.1-Flash: 唯一前缀的长 prompt 跑两次 | 第一次 `cached_tokens` 不超过 `prompt_tokens` 的一半,第二次命中缓存 |
| 10_05 | `test_10_05_usage_arithmetic_tool_call` | tool_call 下 usage 算术 | total == prompt + completion |
| 10_05 | `test_10_05_usage_arithmetic_tool_call` | M3.1-Flash: tool_call 下的 usage | 原有算术校验 + `completion_tokens > 0` |
| 10_06 | `test_10_06_length_truncation_completion_equals_limit` | finish_reason=length 时 completion == max | 严格相等 |
| 10_07 | `test_10_07_stream_prompt_tokens_aggregated` | 流式 vs 非流式 prompt_tokens 一致 | 两种模式 pt 相等 + 流式算术成立 |
| 10_07 | `test_10_07_stream_prompt_tokens_aggregated` | M3.1-Flash: 流式与非流式 `prompt_tokens` 对比 | 两者严格相等 + 流式 usage 算术成立 |
| 10_08 | `test_10_08_usage_fields_populated` | usage 三字段都 > 0 | prompt/completion/total 均正数 |
| 10_11 | `test_10_11_stream_truncated_usage_within_budget` | M3.1-Flash: 流式,`max_completion_tokens=20` 截断长文 | 流中有 usage + `completion_tokens <= 20` |
| 10_14 | `test_10_14_prompt_tokens_accounting[input_length\|system_and_history\|tool_result]` | M3.1-Flash: 分别加长输入文本、system 与历史轮次、工具结果 | `prompt_tokens` 增量超过阈值(100 / 50 / 100),不校验精确值 |
| 10_15 | `test_10_15_cache_hit_keeps_prompt_tokens` | M3.1-Flash: 唯一前缀的长 prompt 跑两次 | 两次 `prompt_tokens` 差值不超过 8 或 1% 中的较大者,缓存不从 `prompt_tokens` 扣除 |
| 10_16 | `test_10_16_reasoning_tokens_within_completion` | M3.1-Flash: 非流式,`reasoning_effort="high"` | `reasoning_tokens` 不超过 `completion_tokens`,且不重复计入 `total_tokens`;未返回该字段时 skip |

## 11 role_root — role=root 协议接受与身份遵循

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 11_01 | `test_11_01_role_root_accepted` | 接口接受 role=root | 200 + 非空回答 |
| 11_02 | `test_11_02_root_overrides_system` | root + system 冲突,`thinking=adaptive` + `reasoning_split` | 自称 MiniMax-M3-taoxi(整串严格匹配) |
| 11_03 | `test_11_03_only_system_identity` | 仅 system 写身份,`thinking=adaptive` | 自称 MiniMax-M3-taoxi(整串严格匹配) |
| 11_04 | `test_11_04_only_root_identity` | 仅 root 写身份,`thinking=adaptive` | 自称 MiniMax-M3-taoxi(整串严格匹配) |

## 12 text_semantic — 文本语义遵循

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 12_01 | `test_12_01_factual_qa_consistency` | 常识问答:法国首都 | 响应含 "paris" |
| 12_02 | `test_12_02_chinese_text_non_stream` | 中文文本生成(非流式) | 响应含 CJK 字符 |
| 12_03 | `test_12_03_chinese_text_stream` | 中文文本生成(流式) | 响应含 CJK 字符 |
| 12_04 | `test_12_04_code_generation` | Python fibonacci 函数 | 响应含 "def " 和 "fibonacci" |
| 12_05 | `test_12_05_system_prompt_compliance` | 海盗系统提示 | 响应含 "arrr" |
| 12_06 | `test_12_06_long_form_output` | max_tokens=4096 光合作用解释 | content 长度 > 500 |

## 13 tool_call_basic — 工具调用基础

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 13_01 | `test_13_01_tool_call_non_stream` | 非流式 tool_call | get_weather + Beijing + finish_reason=tool_calls |
| 13_02 | `test_13_02_tool_call_stream` | 流式 tool_call | 流可 rebuild + 末尾 finish_reason=tool_calls |
| 13_02 | `test_13_02_tool_call_stream` | M3.1-Flash: 流式 tool_call,由提示词要求调用(不传 `tool_choice`) | 原有校验 |
| 13_03 | `test_13_03_complex_agent_6tools` | 6 工具池里选 get_weather | 模型选对工具 |
| 13_04 | `test_13_04_param_type_coverage` | 6 种参数类型覆盖 | 合法 JSON + 符合 schema + str_param='hello' |
| 13_05 | `test_13_05_tool_without_parameters` | function.parameters 省略 | 接受则触发;拒绝则 xfail |
| 13_06 | `test_13_06_tool_without_description` | function.description 省略 | 模型应仍能触发 get_weather |
| 13_07 | `test_13_07_stream_multi_tool_call` | 流式多 tool_call rebuild | Beijing + Shanghai 都触发 + id 唯一 |
| 13_07 | `test_13_07_stream_multi_tool_call` | M3.1-Flash: 同上 | 原有校验 + 各调用 arguments 符合 schema、id 唯一、两个 location 互不相同(参数不串线) |
| 13_08 | `test_13_08_tool_choice_values` | tool_choice none/required/auto | none 不触发;required/auto 触发 |
| 13_09 | `test_13_09_tool_stream_auto` | tool_choice=auto + 流式 | 流中含 tool_call chunk |
| 13_10 | `test_13_10_tool_structure` | tool_call 返回结构 | get_weather + Beijing + schema required 字段就位 |
| 13_10 | `test_13_10_tool_structure` | M3.1-Flash: 同上 | 原有校验 + `assert_chat_completion_strict`(`finish_reason=tool_calls`,`tool_calls` 元素字段完整,除非流式 `index` 外无多余键) |
| 13_11 | `test_13_11_stream_tool_rebuild` | 流式 tool_call delta 重建 | rebuild 后含 get_weather + Beijing |
| 13_12 | `test_13_12_tool_name_mismatch_prompt` | 用 few-shot 引导:上一轮 assistant 已 tool_call get_weather/Beijing 且 tool 已成功回灌,本轮 user 问上海;tools 只给 read_file | 模型应延续 pattern 输出 tool_call 调 get_weather + location≈Shanghai + finish_reason=tool_calls |
| 13_13 | `test_13_13_undefined_tool_retry_after_error` | 流式 + adaptive thinking，few-shot 引导:上一轮 assistant 已 tool_call list_skills，tool 回灌“暂不可用，稍后重试”，本轮 user system-reminder 冷却结束重试；请求不带任何 tools 定义，list_skills 仅由上下文建立 | 模型应延续 pattern 重新输出 tool_call 调 list_skills + finish_reason=tool_calls（校验 provider 不依赖 tools 声明即可输出 tool_call，且不重写/丢弃工具名；因请求未声明工具，故不校验 schema） |
| 13_22 | `test_13_22_echo_without_description_required` | M3.1-Flash: echo 省略 description,由提示词要求调用 | `finish_reason=tool_calls`,每个调用都是 echo,arguments 为字符串 |
| 13_23 | `test_13_23_function_name_charset` | M3.1-Flash: 函数名含 a-z、A-Z、0-9、`_`、`-` | HTTP 200;若调用工具,函数名已声明、arguments 为 JSON 对象 |
| 13_24 | `test_13_24_long_description` | M3.1-Flash: description 超长 | HTTP 200;调用的函数名只记录(参照端点在超长描述下也会调用未声明的函数名) |
| 13_25 | `test_13_25_duplicate_function_names` | M3.1-Flash: 两个同名函数声明 | HTTP 200;若调用工具,函数名已声明、arguments 为 JSON 对象 |
| 13_26 | `test_13_26_128_tools_boundary` | M3.1-Flash: 声明 128 个函数,`tool_choice=none` | HTTP 200,返回文本,不调用工具 |
| 13_27 | `test_13_27_tool_choice_omitted_auto` | M3.1-Flash: 声明 echo + get_time,省略 `tool_choice` | 按 auto 处理:返回文本,或只调用已声明的函数 |
| 13_28 | `test_13_28_tool_choice_null` | M3.1-Flash: `tool_choice=null` | 按省略处理:返回文本,或调用已声明的 echo |
| 13_31 | `test_13_31_tool_call_id_unique_across_requests` | M3.1-Flash: 两次独立请求,由提示词要求调用 echo | 调用 id 跨请求不重复,不校验格式 |
| 13_32 | `test_13_32_no_arg_function_arguments_braces` | M3.1-Flash: 无参函数 get_time,由提示词要求调用 | arguments 是空对象的 JSON 字符串 `{}`,不是空串或 null |
| 13_33 | `test_13_33_stream_answer_after_tool_result` | M3.1-Flash: 工具结果回填后流式作答,`tool_choice=none` | `finish_reason=stop`,无 tool_calls 增量,正文非空 |

## 14 tool_call_schema — 工具调用 schema 高级校验

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 14_01 | `test_14_01_multi_distinct_tools_parallel` | 不同工具同轮并行 | get_weather + get_current_time 都触发 |
| 14_02 | `test_14_02_enum_constraint` | enum 枚举校验 | unit == "fahrenheit" |
| 14_03 | `test_14_03_numeric_range` | 数值范围 [1, 14] | days ∈ [1, 7] |
| 14_04 | `test_14_04_multi_required_fields` | 多 required 字段 | from_city/to_city/date 都填 + date 前缀正确 |
| 14_05 | `test_14_05_nested_object_array` | 嵌套 array-of-objects | guests=[{Alice 30}, {Bob 25}] |
| 14_06 | `test_14_06_nested_schema_4_levels` | 4 层深嵌套 schema | nested_tool 触发 + 合法 JSON |
| 14_12 | `test_14_12_strict_tool_schema[...]` | M3.1-Flash: strict 支持的 schema:anyOf、enum、nullable、多层嵌套、`$ref`、递归、注解、长度、format、空 properties、中文属性名、转义值,由提示词要求调用 | 至少一个调用、函数名已声明、arguments 为 JSON 对象;schema 符合度和提示词指定取值只记录不判失败(参照端点不执行 strict) |
| 14_14 | `test_14_14_custom_tool_formats[missing_definition\|invalid_syntax]` | M3.1-Flash: custom 工具语法缺 definition / syntax 非法 | HTTP 400 |
| 14_15 | `test_14_15_tool_declaration_invalid[function_container_missing\|name_wrong_type]` | M3.1-Flash: function 缺容器 / name 类型错误 | HTTP 400 |
| 14_16 | `test_14_16_schema_capability_negative[strict_pattern_properties\|non_strict_allof]` | M3.1-Flash: strict 下 patternProperties 与 properties 并存 / strict=false 的 allOf | 受理(由提示词要求调用);arguments 为 JSON 对象;strict 时 schema 符合度只记录 |
| 14_18 | `test_14_18_non_strict_property_oneof_accepted` | M3.1-Flash: strict=false,属性级 oneOf | 受理;arguments 是 JSON 对象,不校验取值 |
| 14_19 | `test_14_19_strict_2d_bool_array[non_stream\|stream]` | M3.1-Flash: strict 二维布尔数组,由提示词要求调用 | 至少一个调用,m 保持二维,元素是布尔值 |
| 14_20 | `test_14_20_non_strict_omit_required_and_additional` | M3.1-Flash: strict=false,省略 required 和 additionalProperties | 受理;arguments 是 JSON 对象,不校验取值 |
| 14_21 | `test_14_21_strict_true` | M3.1-Flash: strict=true 的 echo,由提示词要求调用 | 至少一个调用;arguments 是否只含 text 只记录不判失败 |
| 14_22 | `test_14_22_strict_false_null_omitted[false\|null\|omitted]` | M3.1-Flash: strict 为 false / null / 省略 | 受理,每个调用都是 echo,arguments 为字符串 |
| 14_23 | `test_14_23_strict_value_constraints[pattern_zip\|format_email\|array_length]` | M3.1-Flash: strict 的 pattern / email format / 数组长度,由提示词要求调用 | 至少一个调用;是否满足约束关键字只记录不判失败 |
| 14_24 | `test_14_24_description_not_string` | M3.1-Flash: description=123 | HTTP 400 |
| 14_25 | `test_14_25_tools_element_not_object` | M3.1-Flash: tools 元素不是对象 | HTTP 400 |

## 15 tool_call_combo — 工具调用与其他特性组合

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 15_01 | `test_15_01_thinking_tool_call_multiturn` | thinking + tool + 多轮 | 第二轮 Shanghai 再触发 get_weather |
| 15_02 | `test_15_02_response_format_with_tool_choice` | tools + tool_choice 共存(原 response_format 已剔除,M3 暂不支持) | 路径 A 调工具 / 路径 B JSON 含 Beijing |
| 15_03 | `test_15_03_5_parallel_tool_calls` | 5 个并行 tool_calls | 至少 1 个调用 + 所有 param 非空 |
| 15_04 | `test_15_04_extreme_agent_thinking_fc` | 极端 agent:thinking+FC+4 轮 | HTTP 200 |
| 15_05 | `test_15_05_system_thinking_tools_combo` | system + thinking + tools 三件套 | get_weather + Tokyo |
| 15_06 | `test_15_06_tool_roundtrip` | 完整 tool roundtrip | 已有 tool result 后用户提问直接回答 |
| 15_09 | `test_15_09_history_content_null[non_stream\|stream]` | M3.1-Flash: 历史 assistant 带 tool_calls 且 content=null,`tool_choice=none` | 受理并返回文本 |
| 15_10 | `test_15_10_mixed_tool_and_plain_turns[non_stream\|stream]` | M3.1-Flash: 历史中工具轮和普通轮混合,`tool_choice=none` | 受理并返回文本,不再调用工具 |
| 15_11 | `test_15_11_real_call_string_roundtrip` | M3.1-Flash: 第一轮由提示词要求调用 echo,用真实返回的 id 和 arguments 回填字符串结果 | 第二轮返回文本,不再调用工具 |
| 15_12 | `test_15_12_echo_history_content_omitted[non_stream\|stream]` | M3.1-Flash: 历史 assistant 带 tool_calls 且省略 content,`tool_choice=none` | 受理并返回文本 |
| 15_13 | `test_15_13_assistant_tool_call_content_variants[...]` | M3.1-Flash: 历史 assistant 带 tool_calls,content 为空串 / 文字(非流式 / 流式) | 受理并返回文本 |

## 16 tool_call_edge — 工具调用边界 / 异常处理

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 16_01 | `test_16_01_tool_result_content_object_duplicate` | tool_result.content=object(老用例) | HTTP 400 |
| 16_02 | `test_16_02_tool_result_empty_string` | tool result = '' (空字符串) | 200 或 400(BUG) |
| 16_02 | `test_16_02_tool_result_empty_string[non_stream\|stream]` | M3.1-Flash: 同上 | 必须 HTTP 200(本文件不再接受 400) |
| 16_03 | `test_16_03_tool_result_null` | tool result = null | 200 或 400 |
| 16_04 | `test_16_04_tool_result_no_content` | tool 消息没有 content 字段 | 200 或 400 |
| 16_05 | `test_16_05_tool_result_special_chars` | tool result 含 JSON+HTML+emoji | HTTP 200 |
| 16_06 | `test_16_06_long_tool_result_50k` | 50K 字符 tool result | HTTP 200 |
| 16_07 | `test_16_07_tool_result_object` | tool result = object 类型 | HTTP 400 |
| 16_08 | `test_16_08_tool_call_id_mismatch` | tool_call_id 不匹配 | HTTP 400 |
| 16_09 | `test_16_09_partial_tool_call_reply` | 两 tool_calls 只回填一个 | HTTP 400 |
| 16_10 | `test_16_10_30_tool_definitions` | 30 个 tool definitions | HTTP 200 + 若触发则 args 合法 JSON |
| 16_11 | `test_16_11_tool_name_special_chars` | tool name 含 - 和 . (my-tool.v2) | 模型应正确调用 |
| 16_12 | `test_16_12_invalid_json_arguments` | tool_calls.arguments 非法 JSON | HTTP 400 |
| 16_13 | `test_16_13_long_arguments_10k` | 10K 字符的 arguments | HTTP 200 |
| 16_14 | `test_16_14_tool_choice_nonexistent_tool` | tool_choice 指定不存在的工具 | 200 或 400;模型不应捏造调用 |
| 16_16 | `test_16_16_real_loop_tool_content_variants[empty_string\|text_parts]` | M3.1-Flash: 真实回填,tool.content 为空串 / text 数组,`tool_choice=none` | 受理并返回文本 |
| 16_18 | `test_16_18_tool_content_array_variants[empty_array\|image_part]` | M3.1-Flash: 真实回填,tool.content 为空数组 / 含图片 part | 受理并返回文本 |
| 16_19 | `test_16_19_tool_result_json_string[non_stream\|stream]` | M3.1-Flash: tool.content 是 JSON 字符串,`tool_choice=none` | 受理并返回文本 |
| 16_20 | `test_16_20_tool_message_before_assistant_call` | M3.1-Flash: tool 消息前没有 assistant 调用 | HTTP 400 |

## 17 param_stress — 参数压力(长对话 / 长 system)

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 17_01 | `test_17_01_long_conversation_20_rounds` | 20 轮 / 40 条 message | HTTP 200 |
| 17_02 | `test_17_02_long_system_10k` | ~10K tokens 长 system | HTTP 200 |
| 17_03 | `test_17_03_long_input_512k` | 合成 system,ctx_tokens ∈ {512000, 524288}(覆盖 10 进制 512k 与 2 进制 512×1024 两种解读),max_tokens=16 | HTTP 200(M3 必须兑现宣称的 512k 窗口) |
| 17_04 | `test_17_04_real_text_512k_xiyouji` | 西游记全文(~553k tokens,超过 512k 边界)作 system,提问主角名;max_tokens=4096 | HTTP 200 ≤ status < 500(禁 5xx);**仅当 200** 时校验 content/reasoning 出现"孙悟空 / 唐僧 / 三藏 / 玄奘"等任一 canonical 名 |
| 17_05 | `test_17_05_xiyouji_below_524288_tokens` | 西游记前 624,000 chars(≈ 523.5K tokens,为 512 tokens 输出预算预留空间)作 system,提问主角名;max_tokens=512 | 严格 HTTP 200 + 命中 canonical 主角名 |
| 17_06 | `test_17_06_real_text_1m_xiyouji` | 约 1.1M tokens 的西游记长文本,超过 1M 上限;thinking disabled,max_tokens=512 | HTTP 200 或明确 4xx,禁 5xx;200 时命中 canonical 主角名 |
| 17_07 | `test_17_07_xiyouji_below_1048576_tokens` | 西游记前 1,220,000 chars(官方实测约 1.02M prompt tokens,低于 1,048,576),thinking disabled,max_tokens=512 | 严格 HTTP 200 + 命中 canonical 主角名 |
| 17_07 | `test_17_07_long_text_needle` | M3.1-Flash: 单条约 8 万字符的长 user 消息 | `assert_oai_success` |
| 17_08 | `test_17_08_long_history_needle` | M3.1-Flash: 51 组 user/assistant + 1 条 user,共 103 条消息 | 发送前断言 103 条 + `assert_oai_success` |

## 18 reasoning_split — reasoning_split 扩展字段

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 18_01 | `test_18_01_reasoning_split_text` | reasoning_split=true + 文本 | 200 或 400(BUG-13) |

## 19 finish_reason — finish_reason 覆盖

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 19_01 | `test_19_01_finish_reason_tool_calls` | 有 tool 触发场景 | finish_reason ∈ {tool_calls, stop} + 工具确实被调 |
| 19_02 | `test_19_02_finish_reason_length` | max_tokens=10 强制截断 | finish_reason ∈ {length, stop} |
| 19_02 | `test_19_02_finish_reason_length` | M3.1-Flash: 非流式,`max_completion_tokens=20` | usage 算术成立;发生截断时 `completion_tokens <= 20`,未截断时 skip |

## 20 error_codes — 错误码(纯文本)

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 20_01 | `test_20_01_empty_messages` | 空 messages 数组 | HTTP 400 |
| 20_02 | `test_20_02_invalid_model` | 非法 model 名 | 400 或 404 |
| 20_03 | `test_20_03_temperature_out_of_range` | temperature 超出范围 (5.0) | HTTP 400 |
| 20_04 | `test_20_04_top_p_out_of_range` | top_p 超出范围 (>1 / <0) | HTTP 400 |
| 20_05 | `test_20_05_no_authorization` | 不带 Authorization 头 | HTTP 401 |
| 20_06 | `test_20_06_invalid_role` | 非法 role | HTTP 400 |
| 20_07 | `test_20_07_invalid_api_key` | 非法 API key | HTTP 401 |
| 20_08 | `test_20_08_content_moderation` | 内容审核:有害内容请求 | 400(过滤)或 200(拒答) |
| 20_14 | `test_20_14_messages_wrong_type[messages=null\|message_is_number]` | M3.1-Flash: `messages=null` / 元素为数值 | HTTP 400 |
| 20_26 | `test_20_26_parameter_contract_negative[...]` | M3.1-Flash: `max_completion_tokens=8.5`、`stop` 含非字符串、`n=1.5`、`reasoning_effort` 为数组 | `assert_error_response_strict`;不得被取整或忽略 |
| 20_28 | `test_20_28_model_wrong_type` | M3.1-Flash: `model` 为数组 | 4xx 拒绝 |

---

## 22 logprobs — logprobs 请求字段

> 只适用于 `m3_format_check/m3_1_flash_text_test.py`。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|

## 26 prompt_cache — 缓存请求字段

> 只适用于 `m3_format_check/m3_1_flash_text_test.py`。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 26_01 | `test_26_01_cache_key_repeated` | 相同 `prompt_cache_key` 连发两次 | 两次均 `assert_oai_success`,命中率不在此校验(见 10_04) |
| 26_03 | `test_26_03_cache_key_null` | `prompt_cache_key` 显式 null | `assert_oai_success` |

## 27 passthrough_params — metadata / store / user / service_tier

> 只适用于 `m3_format_check/m3_1_flash_text_test.py`。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 27_01 | `test_27_01_metadata_values[one_key\|empty_string_value\|null]` | `metadata` 单键、空字符串值、null | `assert_oai_success`,不要求回显 |
| 27_02 | `test_27_02_store_values[false\|true\|null]` | `store` 为 false / true / null | `assert_oai_success` |
| 27_03 | `test_27_03_user_identifier[string\|null]` | 旧字段 `user` 为字符串 / null | `assert_oai_success` |

## 28 extended_capability — modalities / audio / web_search_options / prediction

> 只适用于 `m3_format_check/m3_1_flash_text_test.py`。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 28_05 | `test_28_05_prediction_forms[string\|text_parts]` | `prediction` content 为字符串 / 文本数组 | `assert_oai_success`,不校验预测是否被采用 |

---

## 附录:parametrize 展开后的 156 个 items

凡函数签名带 `@pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])` 的会展开为 2 个 items;`max_tokens` 的两个 case 各展开为 2 个 items。

| 展开因子 | 涉及 case |
|:---|:---|
| `stream ∈ {non_stream, stream}` | 07_01 / 07_02 / 07_03 / 07_04 / 07_05 / 07_06 / 09_03 / 11_01 / 11_02 / 11_03 / 11_04 / 14_06 / 15_01 / 15_02 / 15_03 / 15_04 / 15_05 / 16_02 / 16_03 / 16_05 / 16_06 / 16_08 / 16_09 / 16_10 / 16_11 / 16_12 / 16_13 / 17_01 / 17_02 / 17_04 / 17_05 / 17_06 / 17_07 / 18_01 |
| `ctx_tokens ∈ {512000, 524288} × stream ∈ {non_stream, stream}` | 17_03 |
| `mt ∈ {512000, 524288}` | 06_09 |
| `mt ∈ {524289, 1000000}` | 06_10 |

总 items = 117 函数 - 34 (`stream` 双值函数) - 1 (`ctx_tokens × stream` 函数) - 2 (`mt` 双值函数) + 34×2 + 1×4 + 2×2 = **156**。
