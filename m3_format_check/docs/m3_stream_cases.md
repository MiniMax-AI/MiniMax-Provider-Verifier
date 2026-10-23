# M3 Stream 分包质量测试

> 对应文件：`m3_format_check/m3_stream_tests.py`
> `02_09`、`02_10`、`02_11` 同样适用于 `m3_format_check/m3_1_flash_stream_test.py`。

## 测试范围

- `TestSSEStream`：校验 `stream_options.include_usage=true` 时 usage 仅出现在最后一个 chunk（`02_06` 纯文本、`02_11` 带图多模态，两条共用同一断言但走不同的 usage 组装路径），以及连续 20 次请求中任一 `delta` 不会同时包含非空 `content` 和 `reasoning_content`。原 `m3_text_tests.py::02_06` 与本文件 `02_06` 完全重复已删除，原 `m3_image_tests.py::08_03` 迁入本文件并按本文件 `02_xx` 序号续编为 `02_11`。
- `02_09`、`02_10` 各执行一次 `bash` + `glob` 并行工具调用请求：要求 `bash` 检查仓库状态和提交记录、`glob` 在 `/app` 下查找 `**/AGENTS.md`。使用 `tool_choice="auto"`、`parallel_tool_calls=true`、`max_tokens=64000` 和 `reasoning_split=true`，直接检查完整响应的原始分片。协议违规立即 `FAIL`，报告 response/trace ID 和异常分片位置；未观察到并行调用时 `SKIP`，不重试。只接收模型工具调用，不执行 shell 命令或文件搜索。
- 两项协议规则分别只由 `02_09`、`02_10` 断言；`oai_chat`、通用成功断言和工具参数提取不执行身份校验，避免同一协议问题使其他功能用例连带失败。
- `TestContentStreamPacketLengthDistribution`：纯 content 场景默认执行 5 次，将 5 次的所有非空 `delta.content` 分包合并后统一判定。可通过 `M3_STREAM_CONTENT_RUNS` 调整次数。
- `TestToolCallStreamPacketLengthDistribution`：每个 tool call 场景执行 1 次，独立使用自己的阈值判定非空 `delta.tool_calls[].function.arguments` 分包。并行工具场景同时校验整体分布和每个已观察到的 `tool_call.index` 分布。
- 分包质量场景只关注分包质量，不校验正文长度、JSON 合法性、工具名称、参数内容、工具数量等功能正确性。
- 分包质量场景的结果严格为 `PASS` 或 `FAIL`，不使用 `WARN`。`02_09`、`02_10` 未覆盖并行调用时记为 `SKIP`；已观察到的协议违规仍记为 `FAIL`。

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
| 01_01 | `01_01_essay_500_chars` | 直接返回约 500 字中文作文，默认执行 5 次 | 合并 5 次 `content` 分包后判定 |
| 01_02 | `01_02_structured_json_1k` | 返回不少于 1KB 的结构化 JSON，默认执行 5 次 | 合并 5 次 `content` 分包后判定 |
| 01_03 | `01_03_tool_content_string_500_chars` | 调用仅有 `content: string` 参数的 `save_content`，保存约 500 字作文 | `arguments` 分包 |
| 01_04 | `01_04_tool_json_filename_content_500_chars` | 调用参数为 `filename: string` 和 `content: string` 的 JSON 工具，写入约 500 字产品说明 | `arguments` 分包 |
| 01_05 | `01_05_tool_string_10k_chars` | 调用 `write_file(path: string, content: string)`，将 10K 字符 ASCII payload 原样写入 `content`；标记为 `slow` | `arguments` 分包 |
| 01_06 | `01_06_tool_nested_object_2k` | 约 2KB 的多层 object/array 参数 | `arguments` 分包 |
| 01_07 | `01_07_parallel_5_tool_calls` | 并行调用 5 个不同工具 | 整体及每个已观察 index 的 `arguments` 分包 |
| 01_08 | `01_08_reasoning_then_tool_call` | adaptive reasoning 后调用 `write_file(path: string, content: string)` 写入不少于 500 字的计划 | `arguments` 分包 |

JSONL 记录保留逐包字符数、精确长度分布、六档命中次数，以及用于最终判定的三档包数量/字符量占比和每项阈值检查结果。
