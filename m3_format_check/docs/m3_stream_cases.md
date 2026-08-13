# M3 Stream 分包质量测试

> 对应文件：`m3_format_check/m3_stream_tests.py`

## 测试范围

- `TestSSEStream`：校验 `stream_options.include_usage=true` 时 usage 仅出现在最后一个 chunk，以及连续 20 次请求中任一 `delta` 不会同时包含非空 `content` 和 `reasoning_content`。
- `TestContentStreamPacketLengthDistribution`：纯 content 场景默认执行 5 次，将 5 次的所有非空 `delta.content` 分包合并后统一判定。可通过 `M3_STREAM_CONTENT_RUNS` 调整次数。
- `TestToolCallStreamPacketLengthDistribution`：每个 tool call 场景执行 1 次，独立使用自己的阈值判定非空 `delta.tool_calls[].function.arguments` 分包。并行工具场景同时校验整体分布和每个已观察到的 `tool_call.index` 分布。
- 分包质量场景只关注分包质量，不校验正文长度、JSON 合法性、工具名称、参数内容、工具数量等功能正确性。
- 结果严格为 `PASS` 或 `FAIL`，不使用 `WARN`。

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
| 01_01 | `01_01_essay_500_chars` | 直接返回约 500 字中文作文，默认执行 5 次 | 合并 5 次 `content` 分包后判定 |
| 01_02 | `01_02_structured_json_1k` | 返回不少于 1KB 的结构化 JSON，默认执行 5 次 | 合并 5 次 `content` 分包后判定 |
| 01_03 | `01_03_tool_content_string_500_chars` | 调用仅有 `content: string` 参数的 `save_content`，保存约 500 字作文 | `arguments` 分包 |
| 01_04 | `01_04_tool_json_filename_content_500_chars` | 调用参数为 `filename: string` 和 `content: string` 的 JSON 工具，写入约 500 字产品说明 | `arguments` 分包 |
| 01_05 | `01_05_tool_string_10k_chars` | 调用 `write_file(path: string, content: string)`，将 10K 字符 ASCII payload 原样写入 `content`；标记为 `slow` | `arguments` 分包 |
| 01_06 | `01_06_tool_nested_object_2k` | 约 2KB 的多层 object/array 参数 | `arguments` 分包 |
| 01_07 | `01_07_parallel_5_tool_calls` | 并行调用 5 个不同工具 | 整体及每个已观察 index 的 `arguments` 分包 |
| 01_08 | `01_08_reasoning_then_tool_call` | adaptive reasoning 后调用 `write_file(path: string, content: string)` 写入不少于 500 字的计划 | `arguments` 分包 |

JSONL 记录保留逐包字符数、精确长度分布、六档命中次数，以及用于最终判定的三档包数量/字符量占比和每项阈值检查结果。
