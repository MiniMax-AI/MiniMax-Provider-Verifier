# M3 Streaming Protocol and Packet-Quality Tests

> Corresponding file: `m3_format_check/m3_stream_tests.py`

## Scope

- `TestSSEStream`: checks final-chunk usage (`02_06`), mutually exclusive non-empty content and reasoning_content (`02_07`, 20 requests), valid finish_reason values (`02_08`), and tool-call index uniqueness and identity stability (`02_09` and `02_10`, one request each).
- `02_09` and `02_10` each send one parallel `bash` + `glob` request: ask `bash` to inspect repository status and recent commits, and `glob` to find `**/AGENTS.md` under `/app`. Use `tool_choice="auto"`, `parallel_tool_calls=true`, `max_tokens=64000`, and `reasoning_split=true`, then inspect the complete response as raw deltas. Fail on a protocol violation with response/trace IDs and fragment positions; skip without retrying if parallel calls are not observed. The tests receive tool calls without executing shell commands or file searches.
- These protocol rules are asserted only by `02_09` and `02_10`, respectively. `oai_chat`, generic success assertions, and tool-argument extraction do not validate call identities, so one protocol defect does not cause unrelated functional cases to fail.
- `TestContentStreamPacketLengthDistribution`: each pure-content scenario runs five times by default. All non-empty `delta.content` fragments from the five runs are merged and evaluated once. Override the run count with `M3_STREAM_CONTENT_RUNS`.
- `TestToolCallStreamPacketLengthDistribution`: each tool-call scenario runs once and uses its own thresholds for non-empty `delta.tool_calls[].function.arguments` fragments. The parallel-tool scenario evaluates both the combined distribution and every observed `tool_call.index` distribution.
- The packet-quality scenarios evaluate packet-size quality only. They do not validate output length, JSON validity, tool names, argument contents, or tool-call counts.
- Packet-quality scenarios report only `PASS` or `FAIL`, with no `WARN` state. Cases `02_09` and `02_10` report `SKIP` when parallel calls are not observed; any observed protocol violation still reports `FAIL`.

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
| Tool: `content`-only string, about 500 characters | 15% | 85% | 0% | 95% | 0% |
| Tool: `filename` + `content` JSON, about 500 characters | 10% | 90% | 0% | 95% | 0% |
| Tool: 10K-character string | 5% | 90% | 10% | 65% | 35% |
| Tool: nested 2K object | 20% | 75% | 10% | 60% | 40% |
| Tool: five parallel calls | 15% | 85% | 0% | 95% | 0% |
| Tool: reasoning then tool | 10% | 85% | 5% | 85% | 15% |

## Cases

| Case ID | Scenario | Description | Packet-Quality Target |
|:---:|:---|:---|:---|
| 02_06 | `test_02_06_stream_usage_only_in_last_chunk` | Text request with `stream_options.include_usage=true` | Independent SSE protocol check; not part of packet-quality rules |
| 02_07 | `test_02_07_content_and_reasoning_content_not_coexist_in_chunk` | Run a long-reasoning, long-answer request 20 times and verify that non-empty `content` and `reasoning_content` never coexist in one `delta` | Independent SSE protocol check; not part of packet-quality rules |
| 02_08 | `test_02_08_finish_reason_never_empty_string` | Send one streaming request and check each choice: finish_reason may be missing or null; otherwise it must be a valid non-empty termination reason | Independent SSE protocol check; not part of packet-quality rules |
| 02_09 | `test_02_09_tool_call_index_unique_in_chunk` | Send one parallel `bash` + `glob` request and verify unique `index` values within `delta.tool_calls` for every chunk and choice in the response | Independent SSE protocol check; not part of packet-quality rules |
| 02_10 | `test_02_10_tool_call_identity_stable` | Send one parallel `bash` + `glob` request and inspect all raw deltas before merging: new indices in each choice first appear consecutively from zero; every call eventually has a non-empty ID; IDs stay stable and are not reused by another call (later fragments may omit the ID) | Independent SSE protocol check; not part of packet-quality rules |
| 01_01 | `01_01_essay_500_chars` | Return an approximately 500-character Chinese essay five times | Merged `content` fragments from all five runs |
| 01_02 | `01_02_structured_json_1k` | Return at least 1KB of structured JSON five times | Merged `content` fragments from all five runs |
| 01_03 | `01_03_tool_content_string_500_chars` | Save an approximately 500-character essay through `save_content(content: string)` | `arguments` fragments |
| 01_04 | `01_04_tool_json_filename_content_500_chars` | Write an approximately 500-character product description through a JSON tool with `filename: string` and `content: string` | `arguments` fragments |
| 01_05 | `01_05_tool_string_10k_chars` | Call `write_file(path: string, content: string)` and copy a 10K-character ASCII payload verbatim into `content`; marked `slow` | `arguments` fragments |
| 01_06 | `01_06_tool_nested_object_2k` | Approximately 2KB of nested object/array arguments | `arguments` fragments |
| 01_07 | `01_07_parallel_5_tool_calls` | Five distinct tool calls in parallel | Combined and per-observed-index `arguments` fragments |
| 01_08 | `01_08_reasoning_then_tool_call` | Adaptive reasoning followed by `write_file(path: string, content: string)` with a plan of at least 500 characters | `arguments` fragments |

Each JSONL record retains per-packet character counts, exact length distributions, the six display buckets, the three decision buckets, packet and character ratios, and every threshold-check result.
