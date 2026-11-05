# M2-Her 兼容性格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_compat_tests.py`](../m2_her_compat_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**1**；case 函数数：**12**；pytest 收集 items 数：**49**
> 预期值：取自 MiniMax 官方接口的实测结果（2026-11-05）；判定规则见 [README](../README.md)。
> “请求失败”：HTTP 状态码非 200，或 HTTP 200 但响应中业务码非 0 / 带 error 对象，且没有返回回复内容；不比对具体的错误码和错误信息。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 15 | compat | 调用方式、旧参数、额外参数与流式分包 | 12 |

---

## 15 compat — 调用方式、旧参数、额外参数与流式分包

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L36) | 同一段完整七角色对话（每条都带 name），分别用三种方式发送：原生接口 /v1/text/chatcompletion_v2、OpenAI 兼容接口 /v1/chat/completions、官方 OpenAI SDK；流式、非流式各一次。 | 三种方式在流式、非流式下都请求成功。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L63) | 长篇续写：只传 max_tokens=16；同时传 max_tokens=8 和 max_completion_tokens=32；同时传 max_tokens=32 和 max_completion_tokens=8。 | max_tokens 可以替代 max_completion_tokens 使用；两个都传时以 max_completion_tokens 为准，输出分别在 16 / 32 / 8 token 处截断。第二种情况如果模型提前写完、但已超过 8 个 token，同样说明以 max_completion_tokens 为准。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L85) | max_completion_tokens 取 2049 和 4096。 | 请求失败。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L114) | messages 为空数组、content 为空字符串、content 只有空格、system 只有 name 没有 content（官网示例写法）、只有 system 没有 user。 | 空 messages、空 content、只有 system 必须请求失败；只有空格的 content 接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；只有 name 的 system 请求成功。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L146) | 多条 system、连续两条 user、连续两条 assistant、示例只有一半（只有示例 user 或只有示例 ai）、group / user_system 放在 user 之后。 | 连续 user、连续 assistant 请求成功；只有一半的示例接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；多条 system、顺序错乱必须请求失败。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L187) | 原生接口流式请求，分别不传 stream_options、传 include_usage=true、传 include_usage=false。 | 三种写法都成功，且流式结果都带 usage。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L237) | 普通请求分别附加 tools、tool_choice、thinking、reasoning_split、reasoning_effort、response_format、seed、stop。 | 每个参数都接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）。只检查能否正常处理，不代表这些功能会生效。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L250) | 写游记长文、生成 JSON 列表两种任务，各流式请求 3 次；累计内容不足 1000 字时带上已有回复继续生成，最多 20 次，每次上限 2048 token。 | 每次响应的第一个包不超过 6 个字符（首个 token 立刻下发），中间的包不少于 5 个字符，任何一个包不超过 512 个字符。请求 20 次仍不足 1000 字时记为“未验证”。 | 需 --run-compat；预期值可用 --contract 文件替换；需 --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L306) | 主角色 system 之外再加一条 name 为“旁白”的 system，并带 user_system 和 user（都带 name）。 | 流式、非流式都成功，以主角色的口吻回复。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L323) | 最后一条 user 的 name 为“推荐回复”、content 为空；分别测带示例和不带示例。 | 带不带示例、流式非流式都成功，返回一句推荐回复。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L348) | 两条带 name 的 system（角色A、角色B）加一条 user。 | 请求失败（合法的场景描述应使用 group 角色）。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L362) | 旧参数 max_tokens 分别取 -1、0、1，流式、非流式各一次；取 1 时用长篇续写任务。 | -1 和 0 接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）；取 1 时成功，输出在 1 个 token 处截断。 | 需 --run-compat；预期值可用 --contract 文件替换 |

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
