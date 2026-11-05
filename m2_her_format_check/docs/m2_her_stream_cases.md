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
| 14_01 | [`test_14_01_sse_framing`](../m2_her_stream_tests.py#L17) | [S：必须成功](../README.md#verdict-rules) | 普通流式请求。 | Content-Type 为 text/event-stream，每个事件都能完整解析，没有损坏的事件。 | 默认运行 |
| 14_02 | [`test_14_02_chunk_envelope_consistency`](../m2_her_stream_tests.py#L23) | [S：必须成功](../README.md#verdict-rules) | 普通流式请求，检查每个数据包的顶层字段。 | 各包 id、model 为非空字符串，created 为正整数，且响应内一致；model 匹配配置的响应模型名。delta 包与完整消息汇总包各使用对应 object 类型。 | 默认运行 |
| 14_03 | [`test_14_03_delta_role_content_types`](../m2_her_stream_tests.py#L31) | [S：必须成功](../README.md#verdict-rules) | 普通流式请求，检查 delta.role 和 delta.content。 | 至少一个 delta.role 为 assistant；role 出现时只能为 assistant。delta.content 可缺省、为 null 或字符串，最终拼接正文非空。 | 默认运行 |
| 14_04 | [`test_14_04_content_reassembly`](../m2_her_stream_tests.py#L40) | [S：必须成功](../README.md#verdict-rules) | 先给一个示例，再让模型照抄 12 个按顺序排列的标记。 | 拼接后的内容恰好是这 12 个标记且顺序正确；如果最后有完整消息汇总包，其内容须与拼接结果一致。 | 需 --run-behavior（模型行为，单独统计） |
| 14_05 | [`test_14_05_unicode_escape_chunks`](../m2_her_stream_tests.py#L62) | [S：必须成功](../README.md#verdict-rules) | 流式下让模型照抄含引号、反斜杠、换行和 emoji 的文本。 | 能正常解码，且内容里确实有 "、\、换行、🙂、🚀。 | 需 --run-behavior（模型行为，单独统计） |
| 14_06 | [`test_14_06_stream_stop`](../m2_her_stream_tests.py#L79) | [S：必须成功](../README.md#verdict-rules) | 流式下让模型只回答 OK；上限 128 token，若被截断放宽到 512 再试。 | 两次内至少一次 finish_reason=stop，不要求正文恰好 OK 或有 [DONE]；两次仍未 stop 判失败。计数出现时验证输出上限，length 结束时必须提供准确计数。 | 默认运行 |
| 14_07 | [`test_14_07_stream_length`](../m2_her_stream_tests.py#L83) | [S：必须成功](../README.md#verdict-rules) | 流式长篇续写，上限 8 token；若提前写完，换提示并把上限降到 1 再试。 | 两次内至少一次 finish_reason=length，输出 token 数恰好等于上限；每次都必须有完整计数且不能超上限。缺计数或两次未截断均失败；只有上限 1 允许正文为空。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |
| 14_08 | [`test_14_08_stream_usage`](../m2_her_stream_tests.py#L87) | [S：必须成功](../README.md#verdict-rules) | 普通流式请求，检查带 usage 的数据包。 | 至少一个数据包带 usage，最终 total_tokens 大于 0；中间包可以为 0。 | 默认运行 |
| 14_09 | [`test_14_09_native_summary_message`](../m2_her_stream_tests.py#L100) | [S：必须成功](../README.md#verdict-rules) | 原生接口流式请求，检查结束包和完整消息汇总包。 | 有带 finish_reason 的结束包；如果有汇总包，其内容须与拼接结果一致。 | 默认运行；仅原生接口 |
| 14_10 | [`test_14_10_stream_error_response`](../m2_her_stream_tests.py#L116) | [F：必须失败](../README.md#verdict-rules) | stream=true，但 messages 为 null。 | 请求失败，不能是一个空的“成功”流。 先做同端点、模型、鉴权和流式模式的正常对照；对照失败记 SKIP。 | 默认运行 |
| 14_11 | [`test_14_11_repeated_emoji_integrity`](../m2_her_stream_tests.py#L126) | [S：必须成功](../README.md#verdict-rules) | 流式请求 20 次，每次让模型输出 30 个 emoji（上限 512 token）。 | 20 次回复全部成功解码、格式正确，且每次至少包含一个 U+1F300..U+1FAFF 范围字符；不要求恰好 30 个 emoji。 | 需 --run-behavior（模型行为，单独统计）；需 --run-slow |

---

## 附录：parametrize 展开后的 11 个 items

| 展开因子 | 涉及 case |
|:---|:---|
| `单项` | 14_01 / 14_02 / 14_03 / 14_04 / 14_05 / 14_06 / 14_07 / 14_08 / 14_09 / 14_10 / 14_11 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。
