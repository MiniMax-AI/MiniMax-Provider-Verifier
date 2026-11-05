# M2-Her 兼容性格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_compat_tests.py`](../m2_her_compat_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**1**；case 函数数：**12**；pytest 收集 items 数：**49**
> 期望值：按 2026-11-05 线上实际返回设定，与官网文档不一致处以线上为准；判定原则与允许的随机性见 [README](../README.md)。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 15 | compat | 端点兼容、旧字段、扩展参数与分包 | 12 |

---

## 15 compat — 端点兼容、旧字段、扩展参数与分包

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L36) | 同一组具名七角色消息，分别通过原生接口 /v1/text/chatcompletion_v2、OpenAI 兼容接口 /v1/chat/completions 的 HTTP 请求，以及官方 OpenAI SDK 发送，流式与非流式各一次。 | 按线上实际：原生 HTTP、OpenAI HTTP 与 SDK 三条路径的流式与非流式都成功。可按实际契约逐个变体覆盖。 | --run-compat；内置观测基线，可覆盖 |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L63) | 长篇续写任务：只传 max_tokens=16；同时传 max_tokens=8 和 max_completion_tokens=32；同时传 max_tokens=32 和 max_completion_tokens=8。 | max_tokens 作为合法别名生效；两者同传时以 max_completion_tokens 为准，实际输出分别在 16 / 32 / 8 token 处截断；32 的变体若自然结束且已超过 8 tokens，也足以证明以 max_completion_tokens 为准。 | --run-compat；内置观测基线，可覆盖 |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L85) | max_completion_tokens 取 2049 和 4096。 | 默认基线：明确返回参数错误。若覆盖为“封顶 2048”，则须实际验证输出不超过 2048。 | --run-compat；内置观测基线，可覆盖 |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L114) | 空 messages、空 content、纯空白 content、只有 name 没有 content 的 system（官网示例写法）、只有 system 没有 user。 | 按线上实际：空 messages 与仅 system 返回 2013；空 content 返回同一响应体内的占位信封 + 业务码 1000「unknown error」；空白内容与仅 name 的 system 请求成功。 | --run-compat；内置观测基线，可覆盖 |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L146) | 多条 system、连续两条 user、连续两条 assistant、只有单边示例，以及 group / user_system 出现在 user 之后。 | 按线上实际：连续 user / assistant 与只有单边示例都成功；多条 system（group chat not supported）与乱序（invalid message role: group）返回 2013。 | --run-compat；内置观测基线，可覆盖 |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L187) | 原生流式请求分别省略 stream_options、传 include_usage=true、传 include_usage=false。 | 按线上实际：省略或携带 stream_options（include_usage 为 true / false）都成功，流式结果带 usage。 | --run-compat；内置观测基线，可覆盖 |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L237) | 普通请求分别附加 tools、tool_choice、thinking、reasoning_split、reasoning_effort、response_format、seed、stop。 | 按线上实际：8 个未声明参数都被接受并正常回答。只验证接受性，不代表 tools / thinking 等功能生效。 | --run-compat；内置观测基线，可覆盖 |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L250) | 游记长文和 JSON 列表两种任务，各先流式采样 3 次；累计正文不足 1000 字符时带上真实回复继续生成，最多共 20 次，每次预算 2048。 | 按线上实际的分包形态：每个响应首包 ≤6 字符（首个 token 立即下发），中间包 ≥5 字符，单包 ≤512 字符。累计正文不足 1000 字符时续写补样，耗尽 20 次仍不足记为未验证；五项分包比例只记录不判定。 | --run-compat；内置观测基线，可覆盖 + --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L306) | 主角色 system 之外再加一条 name=旁白 的 system，配具名 user_system 和 user。 | 按线上实际：两种输出模式都成功，以主角色口吻回复。 | --run-compat；内置观测基线，可覆盖 |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L323) | 最后一条 user 的 name 为“推荐回复”、content 为空，比较带示例与不带示例。 | 按线上实际：有无示例、两种输出模式都成功，生成一句推荐回复。 | --run-compat；内置观测基线，可覆盖 |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L348) | 两条具名 system（角色A、角色B）加一条 user。 | 默认基线：返回参数错误；与合法的 group 场景角色区分开。 | --run-compat；内置观测基线，可覆盖 |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L362) | 旧字段 max_tokens 分别取 -1、0、1，流式与非流式各一次；取 1 时使用长篇续写任务。 | -1 和 0 回落到部署默认预算并成功；取 1 时成功，实际输出在 1 token 处截断。 | --run-compat；内置观测基线，可覆盖 |

---

## 附录：parametrize 展开后的 49 个 items

| 展开因子 | 涉及 case |
|:---|:---|
| `variant(3) × stream(2)` | 15_01 |
| `variant,limits(3)` | 15_02 |
| `limit(2)` | 15_03 |
| `variant(5)` | 15_04 |
| `variant(6)` | 15_05 |
| `variant(3)` | 15_06 |
| `parameter,value(8)` | 15_07 |
| `variant(2)` | 15_08 |
| `stream(2)` | 15_09 / 15_11 |
| `samples(2) × stream(2)` | 15_10 |
| `limit(3) × stream(2)` | 15_12 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。
