# M2-Her 流式协议格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_stream_tests.py`](../m2_her_stream_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**1**；case 函数数：**11**；pytest 收集 items 数：**11**
> 期望值：按 2026-11-05 线上实际返回设定，与官网文档不一致处以线上为准；判定原则与允许的随机性见 [README](../README.md)。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 14 | sse_stream | SSE 流式协议 | 11 |

---

## 14 sse_stream — SSE 流式协议

| Case ID | 函数名 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|
| 14_01 | [`test_14_01_sse_framing`](../m2_her_stream_tests.py#L17) | stream=true 的普通请求。 | Content-Type 为 text/event-stream，事件边界和 data JSON 都能严格解析，没有坏事件。 | 默认 |
| 14_02 | [`test_14_02_chunk_envelope_consistency`](../m2_her_stream_tests.py#L23) | 流式普通请求，检查每个数据包的顶层字段。 | 各包字段类型正确，同一响应内 id、model、created 保持一致。 | 默认 |
| 14_03 | [`test_14_03_delta_role_content_types`](../m2_her_stream_tests.py#L31) | 流式普通请求，检查 delta.role 和 delta.content。 | 出现 role 时为 assistant，content 为字符串；允许后续包省略 role。 | 默认 |
| 14_04 | [`test_14_04_content_reassembly`](../m2_her_stream_tests.py#L40) | 精确复制任务：先给示例，再要求复制 12 个有序标记。 | 拼接后的正文恰为 12 个标记且顺序正确；若有完整 message 汇总包，须与 delta 拼接结果一致。 | --run-behavior；独立统计，不计入格式通过率 |
| 14_05 | [`test_14_05_unicode_escape_chunks`](../m2_her_stream_tests.py#L62) | 流式精确复制含引号、反斜杠、换行和 emoji 的文本。 | 严格解码成功，且正文实际包含 "、\、换行、🙂、🚀。 | --run-behavior；独立统计，不计入格式通过率 |
| 14_06 | [`test_14_06_stream_stop`](../m2_her_stream_tests.py#L79) | 流式下要求只回答 OK，先给 128 token，若被截断再放宽到 512。 | 至少一次以 finish_reason=stop 结束；不要求 [DONE] 标记。 | 默认 |
| 14_07 | [`test_14_07_stream_length`](../m2_her_stream_tests.py#L83) | 流式长篇续写，先给 8 token，若提前自然结束再换提示、预算降到 1。 | 至少一次以 finish_reason=length 结束，completion_tokens 恰好等于预算。 | 需真实 completion_tokens；缺失报告计数不可验证 |
| 14_08 | [`test_14_08_stream_usage`](../m2_her_stream_tests.py#L87) | 流式普通请求，检查带 usage 的数据包。 | 至少一个包带 usage，最终 total_tokens 大于 0；中间包允许为 0。 | 默认 |
| 14_09 | [`test_14_09_native_summary_message`](../m2_her_stream_tests.py#L100) | 原生流式请求，检查结束包和完整 message 汇总包。 | 存在带 finish_reason 的结束包；若有汇总包，其内容必须与 delta 拼接结果一致。 | 仅 native；结束结构必检，可选汇总记录覆盖 |
| 14_10 | [`test_14_10_stream_error_response`](../m2_her_stream_tests.py#L116) | stream=true 但 messages 为 null。 | 返回可解析的结构化错误，不能当成空的成功流。 | 默认 |
| 14_11 | [`test_14_11_repeated_emoji_integrity`](../m2_her_stream_tests.py#L126) | 流式重复 20 次，每次要求输出 30 个 emoji（预算 512）。 | 每次都严格 UTF-8 解码成功，且 20 次都包含 emoji。 | --run-behavior；独立统计，不计入格式通过率；--run-slow |

---

## 附录：parametrize 展开后的 11 个 items

| 展开因子 | 涉及 case |
|:---|:---|
| `单项` | 14_01 / 14_02 / 14_03 / 14_04 / 14_05 / 14_06 / 14_07 / 14_08 / 14_09 / 14_10 / 14_11 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。
