# M3 文本模态格式校验 case 清单

> 对应文件:`data/m3_api_test/m3_text_tests.py`
> 命名规范:`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数:**20**;case 函数数:**108**;pytest 收集 items 数:**140**

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
| 01_02 | `test_01_02_content_string` | `user.content` 为纯字符串 | HTTP 200 |
| 01_03 | `test_01_03_content_array` | `user.content` 为 parts 数组 `[{type:text,text:...}]` | HTTP 200 |

## 02 sse_stream — SSE 流式协议字段

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 02_01 | `test_02_01_text_stream` | 文本流式回复 | 流可正常 rebuild content |
| 02_02 | `test_02_02_stream_usage` | 流式末尾 usage chunk | total == prompt + completion + 流式正常完结 |
| 02_03 | `test_02_03_sse_done_marker` | SSE 结束 `[DONE]` 标记 | 缺失则 xfail(已知 BUG) |
| 02_04 | `test_02_04_stream_chunk_fields` | 流式 chunk 必带字段 | id / choices / object 全部存在 |
| 02_05 | `test_02_05_text_include_usage` | `stream_options.include_usage=true` 文本场景 | 流应正常返回 usage chunk |
| 02_06 | `test_02_06_stream_usage_only_in_last_chunk` | `stream_options.include_usage=true` 文本场景 | usage 非空且三字段 > 0,且只出现在流式最后一个 data chunk |

## 03 multiturn — 多轮对话

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 03_01 | `test_03_01_multiturn` | 两轮对话:自报 Alice 后问名字 | 响应应含 "alice" |
| 03_02 | `test_03_02_multiturn_5_rounds` | 5 轮算术对话 x=10, y=15, z=25 | 响应应含 "50"(x+y+z) |

## 04 thinking — thinking 思考开关

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 04_01 | `test_04_01_thinking_disabled` | `thinking.type=disabled` | 响应不应含任何思考信号 |
| 04_02 | `test_04_02_thinking_adaptive` | `thinking.type=adaptive`(模型自决) | HTTP 200 |
| 04_03 | `test_04_03_thinking_invalid_value` | `thinking.type` 非法值 | 400/422 拒绝或 200 回落 |
| 04_04 | `test_04_04_thinking_stream` | adaptive + 流式 | 流式 + 思考共存可用 |

## 05 sampling — 采样参数(temperature / top_p / seed)

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 05_01 | `test_05_01_temperature_values` | temperature 合法值 [0, 0.5, 1, 2] | 各取值均 200 |
| 05_02 | `test_05_02_top_p` | top_p 边界值 [0.1, 0.5, 0.95] | 各取值均 200 |
| 05_03 | `test_05_03_seed_parameter` | seed=42 + temperature=0 | 接口接受用于确定性输出 |

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

## 07 message_format — 消息内容/角色格式与边界

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 07_01 | `test_07_01_consecutive_assistant` | 连续两条 assistant 消息 | HTTP 200(非流式/流式各 1 item) |
| 07_02 | `test_07_02_assistant_null_content_with_tool_calls` | assistant.content=null + tool_calls | HTTP 200 |
| 07_03 | `test_07_03_assistant_no_content_field_with_tool_calls` | assistant 省略 content 字段 + tool_calls | HTTP 200 |
| 07_04 | `test_07_04_user_content_empty_array` | user.content=[] 空数组 | status > 0 |
| 07_05 | `test_07_05_user_content_null` | user.content=null | 200 或 400 |
| 07_06 | `test_07_06_multiple_system_messages` | 多条 system 消息 | HTTP 200 + 非空响应 |
| 07_07 | `test_07_07_history_tool_call_empty_string_arguments` | 对话历史中工具调用的 arguments 为 `""`（空字符串） | HTTP 200 且模型正常续接（产出非空 content 或新的 tool_call） |
| 07_08 | `test_07_08_history_tool_call_empty_object_arguments` | 对话历史中工具调用的 arguments 为 `"{}"`（空 JSON 对象） | HTTP 200 且模型正常续接（产出非空 content 或新的 tool_call） |

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
| 09_02 | `test_09_02_json_object_stream` | json_object 流式 + thinking=disabled(已 skip) | 流应正常返回 |
| 09_03 | `test_09_03_json_object_format` | json_object 通用(非流式/流式)(已 skip) | 合法 JSON;BUG-3 包裹则 xfail |

## 10 usage_field — usage 字段语义/算术/cache

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 10_01 | `test_10_01_response_field_completeness` | Response 顶层字段完整性 | id/model/created/object/choices/usage 等都存在 |
| 10_02 | `test_10_02_usage_token_math` | usage 算术 | total == prompt + completion;cached <= prompt |
| 10_03 | `test_10_03_usage_field_types` | usage 三字段类型 | int 且 >= 0 |
| 10_04 | `test_10_04_cached_tokens_presence` | cached_tokens 硬存在 | 同 prompt 跑两次第二次 cached > 0 |
| 10_05 | `test_10_05_usage_arithmetic_tool_call` | tool_call 下 usage 算术 | total == prompt + completion |
| 10_06 | `test_10_06_length_truncation_completion_equals_limit` | finish_reason=length 时 completion == max | 严格相等 |
| 10_07 | `test_10_07_stream_prompt_tokens_aggregated` | 流式 vs 非流式 prompt_tokens 一致 | 两种模式 pt 相等 + 流式算术成立 |
| 10_08 | `test_10_08_usage_fields_populated` | usage 三字段都 > 0 | prompt/completion/total 均正数 |

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
| 13_03 | `test_13_03_complex_agent_6tools` | 6 工具池里选 get_weather | 模型选对工具 |
| 13_04 | `test_13_04_param_type_coverage` | 6 种参数类型覆盖 | 合法 JSON + 符合 schema + str_param='hello' |
| 13_05 | `test_13_05_tool_without_parameters` | function.parameters 省略 | 接受则触发;拒绝则 xfail |
| 13_06 | `test_13_06_tool_without_description` | function.description 省略 | 模型应仍能触发 get_weather |
| 13_07 | `test_13_07_stream_multi_tool_call` | 流式多 tool_call rebuild | Beijing + Shanghai 都触发 + id 唯一 |
| 13_08 | `test_13_08_tool_choice_values` | tool_choice none/required/auto | none 不触发;required/auto 触发 |
| 13_09 | `test_13_09_tool_stream_auto` | tool_choice=auto + 流式 | 流中含 tool_call chunk |
| 13_10 | `test_13_10_tool_structure` | tool_call 返回结构 | get_weather + Beijing + schema required 字段就位 |
| 13_11 | `test_13_11_stream_tool_rebuild` | 流式 tool_call delta 重建 | rebuild 后含 get_weather + Beijing |
| 13_12 | `test_13_12_tool_name_mismatch_prompt` | 用 few-shot 引导:上一轮 assistant 已 tool_call get_weather/Beijing 且 tool 已成功回灌,本轮 user 问上海;tools 只给 read_file | 模型应延续 pattern 输出 tool_call 调 get_weather + location≈Shanghai + finish_reason=tool_calls |
| 13_13 | `test_13_13_undefined_tool_retry_after_error` | 流式 + adaptive thinking，few-shot 引导:上一轮 assistant 已 tool_call list_skills，tool 回灌“暂不可用，稍后重试”，本轮 user system-reminder 冷却结束重试；请求不带任何 tools 定义，list_skills 仅由上下文建立 | 模型应延续 pattern 重新输出 tool_call 调 list_skills + finish_reason=tool_calls（校验 provider 不依赖 tools 声明即可输出 tool_call，且不重写/丢弃工具名；因请求未声明工具，故不校验 schema） |

## 14 tool_call_schema — 工具调用 schema 高级校验

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 14_01 | `test_14_01_multi_distinct_tools_parallel` | 不同工具同轮并行 | get_weather + get_current_time 都触发 |
| 14_02 | `test_14_02_enum_constraint` | enum 枚举校验 | unit == "fahrenheit" |
| 14_03 | `test_14_03_numeric_range` | 数值范围 [1, 14] | days ∈ [1, 7] |
| 14_04 | `test_14_04_multi_required_fields` | 多 required 字段 | from_city/to_city/date 都填 + date 前缀正确 |
| 14_05 | `test_14_05_nested_object_array` | 嵌套 array-of-objects | guests=[{Alice 30}, {Bob 25}] |
| 14_06 | `test_14_06_nested_schema_4_levels` | 4 层深嵌套 schema | nested_tool 触发 + 合法 JSON |

## 15 tool_call_combo — 工具调用与其他特性组合

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 15_01 | `test_15_01_thinking_tool_call_multiturn` | thinking + tool + 多轮 | 第二轮 Shanghai 再触发 get_weather |
| 15_02 | `test_15_02_response_format_with_tool_choice` | tools + tool_choice 共存(原 response_format 已剔除,M3 暂不支持) | 路径 A 调工具 / 路径 B JSON 含 Beijing |
| 15_03 | `test_15_03_5_parallel_tool_calls` | 5 个并行 tool_calls | 至少 1 个调用 + 所有 param 非空 |
| 15_04 | `test_15_04_extreme_agent_thinking_fc` | 极端 agent:thinking+FC+4 轮 | HTTP 200 |
| 15_05 | `test_15_05_system_thinking_tools_combo` | system + thinking + tools 三件套 | get_weather + Tokyo |
| 15_06 | `test_15_06_tool_roundtrip` | 完整 tool roundtrip | 已有 tool result 后用户提问直接回答 |

## 16 tool_call_edge — 工具调用边界 / 异常处理

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 16_01 | `test_16_01_tool_result_content_object_duplicate` | tool_result.content=object(老用例) | HTTP 400 |
| 16_02 | `test_16_02_tool_result_empty_string` | tool result = '' (空字符串) | 200 或 400(BUG) |
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

## 18 reasoning_split — reasoning_split 扩展字段

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 18_01 | `test_18_01_reasoning_split_text` | reasoning_split=true + 文本 | 200 或 400(BUG-13) |

## 19 finish_reason — finish_reason 覆盖

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 19_01 | `test_19_01_finish_reason_tool_calls` | 有 tool 触发场景 | finish_reason ∈ {tool_calls, stop} + 工具确实被调 |
| 19_02 | `test_19_02_finish_reason_length` | max_tokens=10 强制截断 | finish_reason ∈ {length, stop} |

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

---

## 附录:parametrize 展开后的 155 个 items

凡函数签名带 `@pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])` 的会展开为 2 个 items;`max_tokens` 的两个 case 各展开为 2 个 items。

| 展开因子 | 涉及 case |
|:---|:---|
| `stream ∈ {non_stream, stream}` | 07_01 / 07_02 / 07_03 / 07_04 / 07_05 / 07_06 / 09_03 / 11_01 / 11_02 / 11_03 / 11_04 / 14_06 / 15_01 / 15_02 / 15_03 / 15_04 / 15_05 / 16_02 / 16_03 / 16_05 / 16_06 / 16_08 / 16_09 / 16_10 / 16_11 / 16_12 / 16_13 / 17_01 / 17_02 / 17_04 / 17_05 / 17_06 / 17_07 / 18_01 |
| `ctx_tokens ∈ {512000, 524288} × stream ∈ {non_stream, stream}` | 17_03 |
| `mt ∈ {512000, 524288}` | 06_09 |
| `mt ∈ {524289, 1000000}` | 06_10 |

总 items = 116 函数 - 34 (`stream` 双值函数) - 1 (`ctx_tokens × stream` 函数) - 2 (`mt` 双值函数) + 34×2 + 1×4 + 2×2 = **155**。
