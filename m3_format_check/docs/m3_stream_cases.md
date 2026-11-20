# M3 Stream 分包质量测试

> 对应文件：`m3_format_check/m3_stream_tests.py`
> `02_09`、`02_10`、`02_11` 同样适用于 `m3_format_check/m3_1_flash_stream_test.py`。
> `02_12`、`02_14`、`02_20`、`02_21`、`02_22`、`02_23`、`02_24` 只适用于 `m3_format_check/m3_1_flash_stream_test.py`。

## 测试范围

- `TestSSEStream`：校验 `stream_options.include_usage=true` 时 usage 仅出现在最后一个 chunk（`02_06` 纯文本、`02_11` 带图多模态，两条共用同一断言但走不同的 usage 组装路径），以及连续 20 次请求中任一 `delta` 不会同时包含非空 `content` 和 `reasoning_content`。原 `m3_text_tests.py::02_06` 与本文件 `02_06` 完全重复已删除，原 `m3_image_tests.py::08_03` 迁入本文件并按本文件 `02_xx` 序号续编为 `02_11`。
- `02_09`、`02_10` 各执行一次 `bash` + `glob` 并行工具调用请求：要求 `bash` 检查仓库状态和提交记录、`glob` 在 `/app` 下查找 `**/AGENTS.md`。使用 `tool_choice="auto"`、`parallel_tool_calls=true`、`max_tokens=64000`，直接检查完整响应的原始分片。协议违规立即 `FAIL`，报告 response/trace ID 和异常分片位置；未观察到并行调用时 `SKIP`，不重试。只接收模型工具调用，不执行 shell 命令或文件搜索。
- 两项协议规则分别只由 `02_09`、`02_10` 断言；`oai_chat`、通用成功断言和工具参数提取不执行身份校验，避免同一协议问题使其他功能用例连带失败。
- `TestContentStreamPacketLengthDistribution`：纯 content 场景默认执行 5 次，将 5 次的所有非空 `delta.content` 分包合并后统一判定。可通过 `M3_STREAM_CONTENT_RUNS` 调整次数。
- `TestToolCallStreamPacketLengthDistribution`：每个 tool call 场景执行 1 次，独立使用自己的阈值判定非空 `delta.tool_calls[].function.arguments` 分包。并行工具场景同时校验整体分布和每个已观察到的 `tool_call.index` 分布。
- 分包质量场景只关注分包质量，不校验正文长度、JSON 合法性、工具名称、参数内容、工具数量等功能正确性。
- 分包质量场景的结果严格为 `PASS` 或 `FAIL`，不使用 `WARN`。`02_09`、`02_10` 未覆盖并行调用时记为 `SKIP`；已观察到的协议违规仍记为 `FAIL`。
- `assert_sse_stream_strict`（`helpers.py`）在一次响应上检查全部规则，并把所有违规项一起报出：每个 data 帧都是 JSON 且单行不超过 1 MiB、`[DONE]` 之后不再有数据帧、流内没有 `error` 对象、`created` 为整数且 `object=chat.completion.chunk`；`content` / `reasoning_content` 为字符串或 null，工具调用分片的 `index` 为整数、`arguments` 为字符串；带 `tool_calls` 的 delta 不能带 `reasoning_content`（只允许缺省或 null，空字符串也算带了）；工具调用分片通过 `stream_protocol.inspect_stream_tool_calls`（index 从 0 连续、id 唯一且不变），每个调用的首个分片带 `id`、`type=function` 和 `name`，拼接后的参数可解析为 JSON 对象；每个 choice 恰好一个结束分片且 `finish_reason` 取值合法，结束后不再有该 choice 的分片，`stop` 结束时正文非空；带 `include_usage` 的请求至少有一个 usage 对象，取最后一个校验 token 计数。
- `TestGzipRequestBody`（`02_21`–`02_24`）：同一请求体先以明文发送，再以 gzip 压缩发送（`Content-Encoding: gzip`，`oai_chat(..., gzip_body=True)`）。gzip 请求必须返回 200、作为流正常结束（`assert_oai_stream_success`），且 `prompt_tokens` 存在并与明文请求相等，以此确认服务端解压出的内容与原文一致。同一 endpoint 背后的多个后端可能对同一明文请求给出不同的 `prompt_tokens`，因此不一致时明文和 gzip 各补发一次，任一 gzip 结果与任一明文结果相等即通过；完整 SSE 协议由 `02_12` 校验，与请求编码无关的流格式问题不在此判定。gzip 请求被拒时，失败信息给出 HTTP 状态码和响应体。明文基线请求失败时直接 `FAIL`，不做比较。`02_24` 为逆向用例：发送截断一半的 gzip 请求体，必须返回 4xx，不能是 5xx 或 200。默认运行；临时排除可用 `-k "not Gzip"`。jsonl 日志的 `request_encoding` 字段记录压缩前后字节数。

## 分档与判定

零长度控制包不参与分布判定。非空包分为三档：

| 档位 | 字符数 | 目标 |
|:---|:---:|:---|
| tiny | 1–4 | 避免过多极小包，例如逐字符输出 |
| normal | 5–200 | 期望主要分布区间 |
| large | >200 | 避免大包或缓冲后集中输出 |

每个档位同时统计包数量占比和字符量占比。仅当以下五项全部满足时为 `PASS`：

- tiny 包数量占比不超过上限。
- normal 包数量占比不低于下限。
- large 包数量占比不超过上限。
- normal 字符量占比不低于下限。
- large 字符量占比不超过上限。

目标字段没有任何非空分包时直接 `FAIL`。校验不使用最少非空包数量或最大单包字符占比。

## 阈值矩阵

| 场景 | tiny 包占比上限 | normal 包占比下限 | large 包占比上限 | normal 字符占比下限 | large 字符占比上限 |
|:---|---:|---:|---:|---:|---:|
| content：500 字作文 ×5 | 5% | 95% | 2% | 90% | 10% |
| content：结构化 JSON ×5 | 5% | 95% | 2% | 90% | 10% |
| tool：仅 `content` string（约 500 字） | 15% | 85% | 0% | 95% | 0% |
| tool：`filename` + `content` JSON（约 500 字） | 10% | 90% | 0% | 95% | 0% |
| tool：10K 字符 string | 5% | 90% | 10% | 65% | 35% |
| tool：2K 嵌套对象 | 20% | 75% | 10% | 60% | 40% |
| tool：5 个并行调用 | 15% | 85% | 0% | 95% | 0% |
| tool：reasoning 后调用 | 10% | 85% | 5% | 85% | 15% |

## Case 列表

| Case ID | 场景名 | 场景说明 | 分包判定目标 |
|:---:|:---|:---|:---|
| 02_06 | `test_02_06_stream_usage_only_in_last_chunk` | `stream_options.include_usage=true` 文本场景 | 独立 SSE 协议校验，不属于分包质量规则 |
| 02_07 | `test_02_07_content_and_reasoning_content_not_coexist_in_chunk` | 使用长推理和长回答请求连续执行 20 次，检查每个 `delta` 中非空 `content` 与 `reasoning_content` 不会同时出现 | 独立 SSE 协议校验，不属于分包质量规则 |
| 02_09 | `test_02_09_tool_call_index_unique_in_chunk` | 单次 `bash` + `glob` 并行工具调用，检查响应中每个 chunk、每个 choice 的 `delta.tool_calls` 内 `index` 不重复 | 独立 SSE 协议校验，不属于分包质量规则 |
| 02_10 | `test_02_10_tool_call_identity_stable` | 单次 `bash` + `glob` 并行工具调用，在合并前检查全部原始 `delta.tool_calls`：每个 choice 的新 `index` 首次出现时从 0 连续递增；每个调用最终具有非空 `id`；同一调用的 `id` 稳定，且不被其他调用复用（后续分片允许省略 `id`） | 独立 SSE 协议校验，不属于分包质量规则 |
| 02_11 | `test_02_11_image_stream_usage_only_in_last_chunk` | `stream_options.include_usage=true` + 672×672 base64 图片的多模态场景（由原图片套件 `08_03` 迁入） | 独立 SSE 协议校验，不属于分包质量规则 |
| 02_12 | `test_02_12_stream_chunk_contract[text\|reasoning\|length\|tool_single\|tool_after_reasoning\|image_input]` | 每个场景一次请求（均带 `include_usage=true`），覆盖不同类型的包：普通文本、reasoning 增量、`finish_reason=length`、单个工具调用分片、思考后紧接工具调用（`reasoning_effort=high`）、图片输入；全部通过 `assert_sse_stream_strict`。reasoning 场景未出现 `reasoning_content`时记为 `SKIP` | 独立 SSE 协议校验，不属于分包质量规则 |
| 02_14 | `test_02_14_stream_omitted_returns_json` | 请求体不含 `stream` 键，经 `oai_chat_verbatim` 原样发送，返回单个 JSON 的 ChatCompletion，不是 SSE（`assert_chat_completion_strict`） | 独立协议校验，不属于分包质量规则 |
| 02_20 | `test_02_20_stream_reasoning_tokens_within_completion` | `reasoning_effort="high"`，`include_usage=true`，`0 <= reasoning_tokens <= completion_tokens`；未返回该字段时记为 `SKIP` | 独立 SSE 协议校验，不属于分包质量规则 |
| 02_21 | `test_02_21_gzip_request_body_stream` | 短文本流式请求分别以明文和 gzip 请求体发送；gzip 请求返回 200、流正常结束，`prompt_tokens` 与明文相等 | 独立请求编码校验，不属于分包质量规则 |
| 02_22 | `test_02_22_gzip_request_body_long_agent_context` | 约 420 KB 的 agent 请求（tools + 4 段 `read_file` 工具结果）以明文和 gzip 分别发送，判定同 `02_21`。压缩比高，覆盖服务端对解压比例或解压后大小的限制 | 独立请求编码校验，不属于分包质量规则 |
| 02_23 | `test_02_23_gzip_request_body_large_image` | 约 9 MB PNG 的 base64 图片以明文和 gzip 分别发送，判定同 `02_21`。压缩后仍约 9 MB，覆盖请求体大小限制，不应返回 413 | 独立请求编码校验，不属于分包质量规则 |
| 02_24 | `test_02_24_truncated_gzip_request_body_rejected` | 发送截断一半的 gzip 请求体（`Content-Encoding: gzip`，经 `oai_chat_verbatim(..., body=..., headers=...)`）；必须返回 4xx，不能是 5xx 或 200 | 独立请求编码校验，不属于分包质量规则 |
| 01_01 | `01_01_essay_500_chars` | 直接返回约 500 字中文作文，默认执行 5 次 | 合并 5 次 `content` 分包后判定 |
| 01_02 | `01_02_structured_json_1k` | 返回不少于 1KB 的结构化 JSON，默认执行 5 次 | 合并 5 次 `content` 分包后判定 |
| 01_03 | `01_03_tool_content_string_500_chars` | 调用仅有 `content: string` 参数的 `save_content`，保存约 500 字作文 | `arguments` 分包 |
| 01_04 | `01_04_tool_json_filename_content_500_chars` | 调用参数为 `filename: string` 和 `content: string` 的 JSON 工具，写入约 500 字产品说明 | `arguments` 分包 |
| 01_05 | `01_05_tool_string_10k_chars` | 调用 `write_file(path: string, content: string)`，将 10K 字符 ASCII payload 原样写入 `content`；标记为 `slow` | `arguments` 分包 |
| 01_06 | `01_06_tool_nested_object_2k` | 约 2KB 的多层 object/array 参数 | `arguments` 分包 |
| 01_07 | `01_07_parallel_5_tool_calls` | 并行调用 5 个不同工具 | 整体及每个已观察 index 的 `arguments` 分包 |
| 01_08 | `01_08_reasoning_then_tool_call` | adaptive reasoning 后调用 `write_file(path: string, content: string)` 写入不少于 500 字的计划 | `arguments` 分包 |

JSONL 记录保留逐包字符数、精确长度分布、六档命中次数，以及用于最终判定的三档包数量/字符量占比和每项阈值检查结果。
