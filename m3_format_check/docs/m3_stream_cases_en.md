# M3 Streaming Packet-Quality Tests

> Corresponding file: `m3_format_check/m3_stream_tests.py`

## Scope

- `TestContentStreamPacketLengthDistribution`: each pure-content scenario runs five times by default. All non-empty `delta.content` fragments from the five runs are merged and evaluated once. Override the run count with `M3_STREAM_CONTENT_RUNS`.
- `TestToolCallStreamPacketLengthDistribution`: each tool-call scenario runs once and uses its own thresholds for non-empty `delta.tool_calls[].function.arguments` fragments. The parallel-tool scenario evaluates both the combined distribution and every observed `tool_call.index` distribution.
- These cases evaluate packet-size quality only. They do not validate output length, JSON validity, tool names, argument contents, or tool-call counts.
- Results are strictly `PASS` or `FAIL`; there is no `WARN` state.

## Buckets and Decision

Zero-length control packets are excluded. Non-empty fragments use three buckets:

| Bucket | Characters | Goal |
|:---|:---:|:---|
| tiny | 1–4 | Avoid excessive tiny fragments such as character-by-character streaming |
| normal | 5–200 | Preferred packet-size range |
| large | >200 | Avoid large buffered fragments |

The suite calculates both packet-count ratios and character-mass ratios. A scenario is `PASS` only when all five checks pass:

- Tiny packet ratio is at or below its maximum.
- Normal packet ratio is at or above its minimum.
- Large packet ratio is at or below its maximum.
- Normal character ratio is at or above its minimum.
- Large character ratio is at or below its maximum.

A target field with no non-empty fragments is an immediate `FAIL`. The decision does not use a minimum non-empty packet count or a largest-single-packet share.

## Threshold Matrix

| Scenario | Tiny packets max | Normal packets min | Large packets max | Normal chars min | Large chars max |
|:---|---:|---:|---:|---:|---:|
| Content: 500-character essay ×5 | 5% | 95% | 2% | 90% | 10% |
| Content: structured JSON ×5 | 5% | 95% | 2% | 90% | 10% |
| Tool: essay to file | 15% | 85% | 0% | 95% | 0% |
| Tool: 500-character string | 10% | 90% | 0% | 95% | 0% |
| Tool: 10K-character string | 5% | 90% | 10% | 65% | 35% |
| Tool: nested 2K object | 20% | 75% | 10% | 60% | 40% |
| Tool: five parallel calls | 15% | 85% | 0% | 95% | 0% |
| Tool: reasoning then tool | 10% | 85% | 5% | 85% | 15% |

## Cases

| Case ID | Scenario | Description | Packet-Quality Target |
|:---:|:---|:---|:---|
| 02_06 | `test_02_06_stream_usage_only_in_last_chunk` | Text request with `stream_options.include_usage=true` | Independent SSE protocol check; not part of packet-quality rules |
| stream-01 | `essay_500_chars` | Return an approximately 500-character Chinese essay five times | Merged `content` fragments from all five runs |
| stream-02 | `essay_500_chars_to_temp_file` | Write an approximately 500-character essay through `write_file` | `arguments` fragments |
| stream-03 | `structured_json_1k` | Return at least 1KB of structured JSON five times | Merged `content` fragments from all five runs |
| stream-04 | `tool_string_500_chars` | One tool call with an approximately 500-character string argument | `arguments` fragments |
| stream-05 | `tool_string_10k_chars` | One tool call with an approximately 10K-character string argument; marked `slow` | `arguments` fragments |
| stream-06 | `tool_nested_object_2k` | Approximately 2KB of nested object/array arguments | `arguments` fragments |
| stream-07 | `parallel_5_tool_calls` | Five distinct tool calls in parallel | Combined and per-observed-index `arguments` fragments |
| stream-08 | `reasoning_then_tool_call` | Adaptive reasoning followed by a file-writing tool call | `arguments` fragments |

Each JSONL record retains per-packet character counts, exact length distributions, the six display buckets, the three decision buckets, packet and character ratios, and every threshold-check result.
