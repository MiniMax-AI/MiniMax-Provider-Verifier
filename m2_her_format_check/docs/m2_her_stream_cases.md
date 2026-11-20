# M2-Her 流式协议格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_stream_tests.py`](../m2_her_stream_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**1**；case 函数数：**11**；pytest 收集 items 数：**11**
> 预期值：取自 MiniMax 官方接口的实测结果（2026-11-05/06）；判定规则见 [README](../README.md)。
> “请求失败”：HTTP 状态码非 200，或 HTTP 200 但响应中业务码非 0 / 带 error 对象，且没有返回回复内容；不比对具体的错误码和错误信息。
> 下表是内置基线。S / F / E 的完整定义及 PASS / FAIL / SKIP 边界见 [统一判定规则](../README.md#verdict-rules)。F 的非 200 包括 5xx；E 明确禁止 5xx。网络异常不算预期拒绝，损坏的 JSON / SSE 不能通过。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 14 | sse_stream | SSE 流式协议 | 11 |

---

## 14 sse_stream — SSE 流式协议

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 14_01 | [`test_14_01_sse_framing`](../m2_her_stream_tests.py#L16) | [S：必须成功](../README.md#verdict-rules) | 发一条普通聊天消息，请接口边生成边返回。 | 响应类型须为 text/event-stream。事件能按 SSE 解码，拼出的正文非空，并有合法结束原因。此项不测出字速度。 | 默认运行 |
| 14_02 | [`test_14_02_chunk_envelope_consistency`](../m2_her_stream_tests.py#L22) | [S：必须成功](../README.md#verdict-rules) | 查看同一次回复里的每个数据包是否都属于同一条消息。 | id、model、created 三项在包间一致；id 非空，model 匹配配置的响应模型名，created 为正整数。增量包和完整消息包各用对应的 object 类型。 | 默认运行 |
| 14_03 | [`test_14_03_delta_role_content_types`](../m2_her_stream_tests.py#L30) | [S：必须成功](../README.md#verdict-rules) | 检查增量包有没有说明“这句话是助手说的”，以及正文的类型。 | 至少一个增量包声明 role=assistant，之后可以省略。提供 role 时必须为 assistant；content 可以缺省、为 null 或是字符串。整段拼出来要有正文。 | 默认运行 |
| 14_04 | [`test_14_04_content_reassembly`](../m2_her_stream_tests.py#L39) | [S：必须成功](../README.md#verdict-rules) | 给一个照抄示例，请模型按顺序抄下 HER_00 至 HER_11，用竖线分隔。 | 先校验流式格式。去掉首尾空白后，全文须与目标一致；漏字、增字或换序均记为行为失败。如有完整消息，必须与拼接结果逐字一致。 | 需 --run-behavior（模型行为，单独统计） |
| 14_05 | [`test_14_05_unicode_escape_chunks`](../m2_her_stream_tests.py#L61) | [S：必须成功](../README.md#verdict-rules) | 请模型照抄一段含引号、反斜杠、换行和 emoji 的文字。 | UTF-8 或 SSE/JSON 解码错误直接失败。格式正常后还须在回复里找齐引号、反斜杠、换行、🙂、🚀；缺字符记为行为失败，不据此推断传输丢字。 | 需 --run-behavior（模型行为，单独统计） |
| 14_06 | [`test_14_06_stream_stop`](../m2_her_stream_tests.py#L78) | [S：必须成功](../README.md#verdict-rules) | 请模型只答 OK，先给 128 token；若截断，放宽到 512 再试。 | 观察到 stop 即通过；两次合法回复都未自然结束则 SKIP。已返回的计数须满足限额，报告 length 时须有恰好等于上限的计数。 | 默认运行 |
| 14_07 | [`test_14_07_stream_length`](../m2_her_stream_tests.py#L82) | [S：必须成功](../README.md#verdict-rules) | 请模型续写长故事，先给 8 token；若它自己写完了，换提示并把预算降到 1。 | 至少一次报告 length 且生成数等于上限才通过。每次都须提供完整计数并遵守预算；两次均合法但未截断记 SKIP。只有预算 1 允许空正文。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |
| 14_08 | [`test_14_08_stream_usage`](../m2_her_stream_tests.py#L86) | [S：必须成功](../README.md#verdict-rules) | 让模型流式回答一句话，检查它生成结束时有没有报告本次用量。 | 每份 usage 都须合法，早期包可以报 0。首个带 finish_reason 的包或其后的包须给出用量，最后一份 total_tokens 必须大于 0。只在早期报数会失败。 | 默认运行 |
| 14_09 | [`test_14_09_native_summary_message`](../m2_her_stream_tests.py#L103) | [S：必须成功](../README.md#verdict-rules) | 看原生接口怎样结束流式回复。有的实现会再发送一条包含全文的消息。 | 必须有有效的 finish_reason。如果发送全文，就须与先前增量拼出的内容一致。没有全文包也可通过，出现次数另记入日志。 | 默认运行；仅原生接口 |
| 14_10 | [`test_14_10_stream_error_response`](../m2_her_stream_tests.py#L119) | [F：必须失败](../README.md#verdict-rules) | 先确认同一个接口、模型和凭据能完成正常流式对话，再把 messages 改为 null。 | 正常对照失败记 SKIP。目标请求须被拒绝且没有正常回复正文；允许返回普通 JSON 错误。 | 默认运行 |
| 14_11 | [`test_14_11_repeated_emoji_integrity`](../m2_her_stream_tests.py#L129) | [S：必须成功](../README.md#verdict-rules) | 连续请求 20 次，每次请模型输出 30 个 emoji，每次最多 512 token。 | 每次先验流式格式，出错立即 FAIL。20 次均出现至少一个 U+1F300..U+1FAFF 字符才 PASS；有合法回复未生成目标字符则记录覆盖次数并 SKIP。不要求生成恰好 30 个。 | 需 --run-behavior（模型行为，单独统计）；需 --run-slow |

---

## 附录：parametrize 展开后的 11 个 items

| 展开因子 | 涉及 case |
|:---|:---|
| `单项` | 14_01 / 14_02 / 14_03 / 14_04 / 14_05 / 14_06 / 14_07 / 14_08 / 14_09 / 14_10 / 14_11 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。
