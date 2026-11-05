# M2-Her 流式协议格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_stream_tests.py`](../m2_her_stream_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**1**；case 函数数：**11**；pytest 收集 items 数：**11**
> 预期值：取自 MiniMax 官方接口的实测结果（2026-11-05）；判定规则见 [README](../README.md)。
> “请求失败”：HTTP 状态码非 200，或 HTTP 200 但响应中业务码非 0 / 带 error 对象，且没有返回回复内容；不比对具体的错误码和错误信息。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 14 | sse_stream | SSE 流式协议 | 11 |

---

## 14 sse_stream — SSE 流式协议

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 14_01 | [`test_14_01_sse_framing`](../m2_her_stream_tests.py#L17) | 普通流式请求。 | Content-Type 为 text/event-stream，每个事件都能完整解析，没有损坏的事件。 | 默认运行 |
| 14_02 | [`test_14_02_chunk_envelope_consistency`](../m2_her_stream_tests.py#L23) | 普通流式请求，检查每个数据包的顶层字段。 | 字段类型正确，同一次响应里 id、model、created 不变。 | 默认运行 |
| 14_03 | [`test_14_03_delta_role_content_types`](../m2_her_stream_tests.py#L31) | 普通流式请求，检查 delta.role 和 delta.content。 | role 出现时为 assistant，content 为字符串；后续数据包可以不带 role。 | 默认运行 |
| 14_04 | [`test_14_04_content_reassembly`](../m2_her_stream_tests.py#L40) | 先给一个示例，再让模型照抄 12 个按顺序排列的标记。 | 拼接后的内容恰好是这 12 个标记且顺序正确；如果最后有完整消息汇总包，其内容须与拼接结果一致。 | 需 --run-behavior（模型行为，单独统计） |
| 14_05 | [`test_14_05_unicode_escape_chunks`](../m2_her_stream_tests.py#L62) | 流式下让模型照抄含引号、反斜杠、换行和 emoji 的文本。 | 能正常解码，且内容里确实有 "、\、换行、🙂、🚀。 | 需 --run-behavior（模型行为，单独统计） |
| 14_06 | [`test_14_06_stream_stop`](../m2_her_stream_tests.py#L79) | 流式下让模型只回答 OK；上限 128 token，若被截断放宽到 512 再试。 | 至少一次以 finish_reason=stop 结束；不要求 [DONE] 结束标记。 | 默认运行 |
| 14_07 | [`test_14_07_stream_length`](../m2_her_stream_tests.py#L83) | 流式长篇续写，上限 8 token；若提前写完，换提示并把上限降到 1 再试。 | 至少一次以 finish_reason=length 结束，输出 token 数恰好等于上限。 | 默认运行；需返回 completion_tokens，缺失时判为无法验证 |
| 14_08 | [`test_14_08_stream_usage`](../m2_her_stream_tests.py#L87) | 普通流式请求，检查带 usage 的数据包。 | 至少一个数据包带 usage，最终 total_tokens 大于 0；中间包可以为 0。 | 默认运行 |
| 14_09 | [`test_14_09_native_summary_message`](../m2_her_stream_tests.py#L100) | 原生接口流式请求，检查结束包和完整消息汇总包。 | 有带 finish_reason 的结束包；如果有汇总包，其内容须与拼接结果一致。 | 默认运行；仅原生接口 |
| 14_10 | [`test_14_10_stream_error_response`](../m2_her_stream_tests.py#L116) | stream=true，但 messages 为 null。 | 请求失败，不能是一个空的“成功”流。 | 默认运行 |
| 14_11 | [`test_14_11_repeated_emoji_integrity`](../m2_her_stream_tests.py#L126) | 流式请求 20 次，每次让模型输出 30 个 emoji（上限 512 token）。 | 每次都能正常解码，且 20 次回复里都有 emoji。 | 需 --run-behavior（模型行为，单独统计）；需 --run-slow |

---

## 附录：parametrize 展开后的 11 个 items

| 展开因子 | 涉及 case |
|:---|:---|
| `单项` | 14_01 / 14_02 / 14_03 / 14_04 / 14_05 / 14_06 / 14_07 / 14_08 / 14_09 / 14_10 / 14_11 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。
