# M2-Her 兼容性格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_compat_tests.py`](../m2_her_compat_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**1**；case 函数数：**12**；pytest 收集 items 数：**49**
> 预期值：取自 MiniMax 官方接口的实测结果（2026-11-05/06）；判定规则见 [README](../README.md)。
> “请求失败”：HTTP 状态码非 200，或 HTTP 200 但响应中业务码非 0 / 带 error 对象，且没有返回回复内容；不比对具体的错误码和错误信息。
> 下表是内置基线。S / F / E 的完整定义及 PASS / FAIL / SKIP 边界见 [统一判定规则](../README.md#verdict-rules)。F 的非 200 包括 5xx；E 明确禁止 5xx。网络异常不算预期拒绝，损坏的 JSON / SSE 不能通过。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 15 | compat | 调用方式、旧参数、额外参数与流式分包 | 12 |

---

## 15 compat — 调用方式、旧参数、额外参数与流式分包

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L37) | [S：必须成功](../README.md#verdict-rules) | 同一段完整七角色对话（每条都带 name），分别用三种方式发送：原生接口 /v1/text/chatcompletion_v2、OpenAI 兼容接口 /v1/chat/completions、官方 OpenAI SDK；流式、非流式各一次。 | 三种方式在流式、非流式下都请求成功。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L64) | [S：必须成功](../README.md#verdict-rules) | 长篇续写：只传 max_tokens=16；同时传 max_tokens=8 和 max_completion_tokens=32；同时传 max_tokens=32 和 max_completion_tokens=8。 | 三组分别验证 16/32/8 token 上限；最多各尝试 3 个续写提示。要求 length 结束且计数等于上限；仅 legacy_smaller 允许 stop 且输出大于 8、不超过 32，作为 max_completion_tokens 优先的证据。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L86) | [F：必须失败](../README.md#verdict-rules) | max_completion_tokens 取 2049 和 4096。 | 请求失败。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L115) | [按变体区分，见校验点](../README.md#verdict-rules) | messages 为空数组、content 为空字符串、content 只有空格、system 只有 name 没有 content（官网示例写法）、只有 system 没有 user。 | empty_messages、empty_content、system_only 必须失败；whitespace 允许成功或失败但不能 5xx；system_name_only（只有 name 的 system 后仍有 user）必须成功。 仅失败/两者均可的分支执行正常对照；对照失败记 SKIP。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L147) | [按变体区分，见校验点](../README.md#verdict-rules) | 六种输入：两条不带 name 的 system；连续 user；连续 assistant；单独示例 user；单独示例 ai；不带 name 的 group/user_system 放在 user 后。 | consecutive_user、consecutive_assistant 必须成功；sample_user_only、sample_ai_only 允许成功或失败但不能 5xx；multiple_system、role_order 这两组具体输入必须失败，不据此单独判断失败原因是角色顺序还是缺 name。 仅失败/两者均可的分支执行正常对照；对照失败记 SKIP。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L188) | [S：必须成功](../README.md#verdict-rules) | 按 M2_HER_API_STYLE 选择原生或 OpenAI 接口，流式下分别省略 stream_options、传 include_usage=true、传 include_usage=false。 | 三种写法均成功。原生接口三种都带 usage；OpenAI 接口仅 include_usage=true 带 usage，省略或 false 时不带。出现的 usage 必须通过类型和计数检查。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L238) | [E：成功或失败，禁 5xx](../README.md#verdict-rules) | 普通请求分别附加 tools、tool_choice、thinking、reasoning_split、reasoning_effort、response_format、seed、stop。 | 每个参数都接受或拒绝都算通过（接受时回复格式正确，拒绝时为请求失败，不能返回 5xx）。只检查能否正常处理，不代表这些功能会生效。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L251) | [S：必须成功](../README.md#verdict-rules) | 写游记长文、生成 JSON 列表两种任务，各流式请求 3 次；累计内容不足 1000 字时带上已有回复继续生成，最多 20 次，每次上限 2048 token。 | 每个响应立即检查非空 delta 的字符数：首包≤6、中间包≥5、任意包≤512；违规立即失败，不被采样不足掩盖。至少请求 3 次且累计≥1000 字符才通过；最多20次仍不足则 SKIP。五项分档比例仅记录，不测首 token 延迟，也不检查正文是否为合法 JSON。 | 需 --run-compat；预期值可用 --contract 文件替换；需 --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L311) | [S：必须成功](../README.md#verdict-rules) | 主角色 system 之外再加一条 name 为“旁白”的 system，并带 user_system 和 user（都带 name）。 | 流式、非流式都请求成功，回复格式正确且正文非空；不检查回复使用哪个角色的口吻。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L328) | [S：必须成功](../README.md#verdict-rules) | 最后一条 user 的 name 为“推荐回复”、content 为空；分别测带示例和不带示例。 | 带不带示例、流式非流式都请求成功，回复格式正确且正文非空；不检查回复的语义或句子数量。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L353) | [F：必须失败](../README.md#verdict-rules) | 两条带 name 的 system（角色A、角色B）加一条 user。 | 此处两条带 name 的 system 加一条 user 的具体输入必须请求失败；不推断所有多角色对话均不支持。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L367) | [按变体区分，见校验点](../README.md#verdict-rules) | 旧参数 max_tokens 分别取 -1、0、1，流式、非流式各一次；取 1 时用长篇续写任务。 OpenAI 流式计数检查会显式传 stream_options.include_usage=true。 | -1、0 允许成功或失败但不能 5xx；1 必须成功，最多 3 个续写提示内至少一次 length 结束且 completion_tokens=1，允许正文为空。 仅失败/两者均可的分支执行正常对照；对照失败记 SKIP。 | 需 --run-compat；预期值可用 --contract 文件替换 |

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
