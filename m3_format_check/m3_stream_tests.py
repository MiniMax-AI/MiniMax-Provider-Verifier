"""
M3 API Test — streaming protocol and packet-size checks.

Add new packet-size scenarios to the content or tool-call scenario list. Each request
records the character length of ``delta.reasoning_content`` and
``delta.content`` for every SSE data packet, then writes an exact length
distribution and a binary packet-quality result to a companion jsonl file.
"""

import json
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import helpers
from helpers import (
    assert_oai_stream_success,
    assert_stream_usage_only_in_last_chunk,
    oai_chat,
    oai_simple_messages,
)


WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write the complete text content to the specified file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Destination file path.",
                },
                "content": {
                    "type": "string",
                    "description": "Complete UTF-8 text to write to the file.",
                },
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
}

SAVE_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "save_report",
        "description": "Save a structured project report.",
        "parameters": {
            "type": "object",
            "properties": {
                "metadata": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "author": {"type": "string"},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["title", "author", "tags"],
                    "additionalProperties": False,
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "paragraphs": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["heading", "paragraphs"],
                        "additionalProperties": False,
                    },
                },
                "conclusion": {"type": "string"},
            },
            "required": ["metadata", "sections", "conclusion"],
            "additionalProperties": False,
        },
    },
}

PARALLEL_TOOL_NAMES = (
    "save_background",
    "save_risks",
    "save_plan",
    "save_metrics",
    "save_summary",
)

PARALLEL_TOOLS = tuple({
    "type": "function",
    "function": {
        "name": name,
        "description": f"Save the {name.removeprefix('save_')} section.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Complete section content.",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
} for name in PARALLEL_TOOL_NAMES)

LONG_TOOL_PAYLOAD = "".join(f"{index:04x}" for index in range(2500))
assert len(LONG_TOOL_PAYLOAD) == 10000


@dataclass(frozen=True)
class PacketQualityRule:
    tiny_packet_max: float
    normal_packet_min: float
    large_packet_max: float
    normal_char_min: float
    large_char_max: float


PACKET_QUALITY_RULES = {
    "content": PacketQualityRule(0.05, 0.95, 0.02, 0.90, 0.10),
    "essay_500_chars_to_temp_file": PacketQualityRule(
        0.15, 0.85, 0.00, 0.95, 0.00
    ),
    "tool_string_500_chars": PacketQualityRule(0.10, 0.90, 0.00, 0.95, 0.00),
    "tool_string_10k_chars": PacketQualityRule(0.05, 0.90, 0.10, 0.65, 0.35),
    "tool_nested_object_2k": PacketQualityRule(0.20, 0.75, 0.10, 0.60, 0.40),
    "parallel_5_tool_calls": PacketQualityRule(0.15, 0.85, 0.00, 0.95, 0.00),
    "reasoning_then_tool_call": PacketQualityRule(0.10, 0.85, 0.05, 0.85, 0.15),
}


@dataclass(frozen=True)
class StreamScenario:
    """One streaming packet-size scenario.

    Add pure-content cases to ``CONTENT_STREAM_SCENARIOS`` and tool-call cases
    to ``TOOL_CALL_STREAM_SCENARIOS``. ``payload_overrides`` supports
    scenario-specific API fields without changing the shared test body.
    """

    name: str
    prompt: str
    quality_rule: PacketQualityRule
    tools: tuple[dict[str, Any], ...] = ()
    tool_choice: dict[str, Any] | None = None
    payload_overrides: dict[str, Any] = field(default_factory=dict)
    validate_each_tool_call: bool = False
    slow: bool = False


CONTENT_STREAM_SCENARIOS = (
    StreamScenario(
        name="essay_500_chars",
        prompt=(
            "请以《一次难忘的合作》为题，写一篇约500字的中文作文。"
            "直接输出作文正文，不要解释写作过程，不要使用 Markdown 代码块。"
        ),
        quality_rule=PACKET_QUALITY_RULES["content"],
    ),
    StreamScenario(
        name="structured_json_1k",
        prompt=(
            "请只输出一个合法 JSON 对象，包含 title、summary、sections、metadata。"
            "sections 必须包含 8 个对象，每个对象包含 heading 和不少于100字的 "
            "description；整个 JSON 文本不少于1000个字符。不要使用 Markdown 代码块。"
        ),
        quality_rule=PACKET_QUALITY_RULES["content"],
        payload_overrides={"response_format": {"type": "json_object"}},
    ),
)

TOOL_CALL_STREAM_SCENARIOS = (
    StreamScenario(
        name="essay_500_chars_to_temp_file",
        prompt=(
            "请以《一次难忘的合作》为题，写一篇约500字的中文作文，并调用 "
            "write_file 工具把完整作文写入 temp.txt。path 必须精确为 temp.txt，"
            "content 必须是完整作文正文。不要只在普通回复中输出作文。"
        ),
        quality_rule=PACKET_QUALITY_RULES["essay_500_chars_to_temp_file"],
        tools=(WRITE_FILE_TOOL,),
        tool_choice={"type": "function", "function": {"name": "write_file"}},
    ),
    StreamScenario(
        name="tool_string_500_chars",
        prompt=(
            "调用 write_file，把一篇约500字的中文产品说明写入 stream_500.txt。"
            "path 必须精确为 stream_500.txt，content 必须包含完整正文，不要省略。"
        ),
        quality_rule=PACKET_QUALITY_RULES["tool_string_500_chars"],
        tools=(WRITE_FILE_TOOL,),
        tool_choice={"type": "function", "function": {"name": "write_file"}},
    ),
    StreamScenario(
        name="tool_string_10k_chars",
        prompt=(
            "调用 write_file 写入 stream_10k.txt。请把 <PAYLOAD> 与 </PAYLOAD> 之间的"
            "10000字符 ASCII 内容逐字符原样复制到 content；不能总结、改写、截断，也不能"
            "使用省略号或占位符。path 必须精确为 stream_10k.txt。\n<PAYLOAD>"
            f"{LONG_TOOL_PAYLOAD}</PAYLOAD>"
        ),
        quality_rule=PACKET_QUALITY_RULES["tool_string_10k_chars"],
        tools=(WRITE_FILE_TOOL,),
        tool_choice={"type": "function", "function": {"name": "write_file"}},
        payload_overrides={"max_tokens": 16384},
        slow=True,
    ),
    StreamScenario(
        name="tool_nested_object_2k",
        prompt=(
            "调用 save_report 保存一份详细项目报告。metadata 要完整；sections 至少6节，"
            "每节至少包含2个 paragraph，每个 paragraph 不少于150字；conclusion 不少于200字。"
            "所有内容必须放入工具参数，工具参数 JSON 总长度应超过2000字符。"
        ),
        quality_rule=PACKET_QUALITY_RULES["tool_nested_object_2k"],
        tools=(SAVE_REPORT_TOOL,),
        tool_choice={"type": "function", "function": {"name": "save_report"}},
        payload_overrides={"max_tokens": 8192},
    ),
    StreamScenario(
        name="parallel_5_tool_calls",
        prompt=(
            "请并行调用提供的5个工具，每个工具必须恰好调用一次。每个工具的 content 都写"
            "约300字中文，分别描述项目背景、风险、执行计划、衡量指标和最终总结。"
            "不要把这些内容放在普通回复中。"
        ),
        quality_rule=PACKET_QUALITY_RULES["parallel_5_tool_calls"],
        tools=PARALLEL_TOOLS,
        payload_overrides={"max_tokens": 8192, "parallel_tool_calls": True},
        validate_each_tool_call=True,
    ),
    StreamScenario(
        name="reasoning_then_tool_call",
        prompt=(
            "先仔细分析一个跨团队发布计划需要考虑的依赖、风险、回滚、监控和验收标准，"
            "完成推理后调用 write_file，把不少于500字的最终计划写入 reasoning_plan.txt。"
            "path 必须精确为 reasoning_plan.txt，不要只返回普通文本。"
        ),
        quality_rule=PACKET_QUALITY_RULES["reasoning_then_tool_call"],
        tools=(WRITE_FILE_TOOL,),
        payload_overrides={"max_tokens": 8192},
    ),
)

CONTENT_SCENARIO_PARAMS = tuple(
    pytest.param(scenario, id=scenario.name)
    for scenario in CONTENT_STREAM_SCENARIOS
)

TOOL_CALL_SCENARIO_PARAMS = tuple(
    pytest.param(scenario, marks=pytest.mark.slow, id=scenario.name)
    if scenario.slow
    else pytest.param(scenario, id=scenario.name)
    for scenario in TOOL_CALL_STREAM_SCENARIOS
)

CONTENT_SCENARIO_RUNS = int(os.environ.get("M3_STREAM_CONTENT_RUNS", "5"))
if CONTENT_SCENARIO_RUNS < 1:
    raise ValueError("M3_STREAM_CONTENT_RUNS must be at least 1")


_FALLBACK_STATS_PATH = (
    Path(__file__).parent
    / "logs"
    / f"stream_stats_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
)


def _text_length(value: Any) -> int:
    return len(value) if isinstance(value, str) else 0


def _packet_kind(chunk: dict[str, Any]) -> str:
    if chunk.get("_done"):
        return "done"
    if "_event" in chunk:
        return "event"
    if "_raw" in chunk:
        return "raw"
    if chunk.get("choices"):
        return "data"
    if chunk.get("usage"):
        return "usage"
    return "metadata"


def _collect_packet_lengths(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one length record for every received stream packet."""
    packets = []
    for packet_index, chunk in enumerate(chunks):
        reasoning_content_chars = 0
        content_chars = 0
        tool_call_name_chars = 0
        tool_call_arguments_chars = 0
        tool_call_arguments_chars_by_index: dict[str, int] = {}
        finish_reasons = []

        if isinstance(chunk, dict):
            for choice in chunk.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta") or {}
                if not isinstance(delta, dict):
                    delta = {}
                reasoning_content_chars += _text_length(
                    delta.get("reasoning_content")
                )
                content_chars += _text_length(delta.get("content"))
                for tool_call in delta.get("tool_calls") or []:
                    if not isinstance(tool_call, dict):
                        continue
                    function = tool_call.get("function") or {}
                    if isinstance(function, dict):
                        tool_call_name_chars += _text_length(function.get("name"))
                        argument_chars = _text_length(function.get("arguments"))
                        tool_call_arguments_chars += argument_chars
                        tool_index = str(tool_call.get("index", 0))
                        tool_call_arguments_chars_by_index[tool_index] = (
                            tool_call_arguments_chars_by_index.get(tool_index, 0)
                            + argument_chars
                        )
                if choice.get("finish_reason") is not None:
                    finish_reasons.append(choice["finish_reason"])

        packets.append({
            "packet_index": packet_index,
            "packet_kind": _packet_kind(chunk) if isinstance(chunk, dict) else "unknown",
            "reasoning_content_chars": reasoning_content_chars,
            "content_chars": content_chars,
            "tool_call_name_chars": tool_call_name_chars,
            "tool_call_arguments_chars": tool_call_arguments_chars,
            "tool_call_arguments_chars_by_index": tool_call_arguments_chars_by_index,
            "finish_reasons": finish_reasons,
        })
    return packets


def _percentile(sorted_values: list[int], quantile: float) -> int:
    if not sorted_values:
        return 0
    index = round((len(sorted_values) - 1) * quantile)
    return sorted_values[index]


def _bucket_hits(lengths: list[int]) -> dict[str, int]:
    """Count non-empty packet lengths in fixed user-facing buckets.

    Boundaries are ``<10``, ``[10,20)``, ``[20,50)``, ``[50,100)``,
    ``[100,200]``, and ``>200`` so every integer length is counted once.
    """
    buckets = {
        "<10": 0,
        "10-20": 0,
        "20-50": 0,
        "50-100": 0,
        "100-200": 0,
        ">200": 0,
    }
    for length in lengths:
        if length <= 0:
            continue
        if length < 10:
            buckets["<10"] += 1
        elif length < 20:
            buckets["10-20"] += 1
        elif length < 50:
            buckets["20-50"] += 1
        elif length < 100:
            buckets["50-100"] += 1
        elif length <= 200:
            buckets["100-200"] += 1
        else:
            buckets[">200"] += 1
    return buckets


def _quality_buckets(lengths: list[int]) -> dict[str, Any]:
    non_empty_lengths = [length for length in lengths if length > 0]
    measured_packet_count = len(non_empty_lengths)
    measured_chars = sum(non_empty_lengths)
    ranges = {
        "tiny_1_4": [length for length in non_empty_lengths if length <= 4],
        "normal_5_200": [
            length for length in non_empty_lengths if 5 <= length <= 200
        ],
        "large_gt_200": [length for length in non_empty_lengths if length > 200],
    }
    buckets = {}
    for name, bucket_lengths in ranges.items():
        packet_count = len(bucket_lengths)
        char_count = sum(bucket_lengths)
        buckets[name] = {
            "packet_count": packet_count,
            "packet_ratio": round(
                packet_count / measured_packet_count, 6
            ) if measured_packet_count else 0,
            "char_count": char_count,
            "char_ratio": round(char_count / measured_chars, 6) if measured_chars else 0,
        }
    return {
        "measured_packet_count": measured_packet_count,
        "measured_chars": measured_chars,
        "buckets": buckets,
    }


def _summarize_values(lengths: list[int]) -> dict[str, Any]:
    sorted_lengths = sorted(lengths)
    non_empty_lengths = [length for length in lengths if length > 0]
    distribution = Counter(lengths)
    total_chars = sum(lengths)
    non_empty_mean = (
        sum(non_empty_lengths) / len(non_empty_lengths)
        if non_empty_lengths
        else 0
    )
    non_empty_variance = (
        sum((length - non_empty_mean) ** 2 for length in non_empty_lengths)
        / len(non_empty_lengths)
        if non_empty_lengths
        else 0
    )
    return {
        "packet_count": len(lengths),
        "non_empty_packet_count": len(non_empty_lengths),
        "total_chars": total_chars,
        "min_chars": min(lengths, default=0),
        "max_chars": max(lengths, default=0),
        "mean_chars": round(total_chars / len(lengths), 2) if lengths else 0,
        "non_empty_mean_chars": round(non_empty_mean, 2),
        "coefficient_of_variation": (
            round(math.sqrt(non_empty_variance) / non_empty_mean, 4)
            if non_empty_mean
            else 0
        ),
        "p50_chars": _percentile(sorted_lengths, 0.50),
        "p90_chars": _percentile(sorted_lengths, 0.90),
        "p99_chars": _percentile(sorted_lengths, 0.99),
        "bucket_hits": _bucket_hits(lengths),
        "quality_buckets": _quality_buckets(lengths),
        "length_distribution": {
            str(length): distribution[length] for length in sorted(distribution)
        },
    }


def _summarize_lengths(
    packets: list[dict[str, Any]], field_name: str
) -> dict[str, Any]:
    return _summarize_values([int(packet[field_name]) for packet in packets])


def _summarize_tool_arguments_by_index(
    packets: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    tool_indices = sorted({
        tool_index
        for packet in packets
        for tool_index in packet["tool_call_arguments_chars_by_index"]
    }, key=lambda value: (0, int(value)) if value.isdigit() else (1, value))
    return {
        tool_index: _summarize_values([
            packet["tool_call_arguments_chars_by_index"].get(tool_index, 0)
            for packet in packets
        ])
        for tool_index in tool_indices
    }


def _quality_rule_dict(rule: PacketQualityRule) -> dict[str, float]:
    return {
        "tiny_packet_max": rule.tiny_packet_max,
        "normal_packet_min": rule.normal_packet_min,
        "large_packet_max": rule.large_packet_max,
        "normal_char_min": rule.normal_char_min,
        "large_char_max": rule.large_char_max,
    }


def _evaluate_distribution(
    distribution: dict[str, Any], rule: PacketQualityRule
) -> dict[str, Any]:
    quality = distribution["quality_buckets"]
    if quality["measured_packet_count"] == 0:
        return {
            "status": "FAIL",
            "reason": "no_non_empty_target_fragments",
            "rule": _quality_rule_dict(rule),
            "checks": {},
        }

    buckets = quality["buckets"]
    actuals = {
        "tiny_packet_ratio": buckets["tiny_1_4"]["packet_ratio"],
        "normal_packet_ratio": buckets["normal_5_200"]["packet_ratio"],
        "large_packet_ratio": buckets["large_gt_200"]["packet_ratio"],
        "normal_char_ratio": buckets["normal_5_200"]["char_ratio"],
        "large_char_ratio": buckets["large_gt_200"]["char_ratio"],
    }
    checks = {
        "tiny_packet_ratio": {
            "actual": actuals["tiny_packet_ratio"],
            "operator": "<=",
            "threshold": rule.tiny_packet_max,
            "passed": actuals["tiny_packet_ratio"] <= rule.tiny_packet_max,
        },
        "normal_packet_ratio": {
            "actual": actuals["normal_packet_ratio"],
            "operator": ">=",
            "threshold": rule.normal_packet_min,
            "passed": actuals["normal_packet_ratio"] >= rule.normal_packet_min,
        },
        "large_packet_ratio": {
            "actual": actuals["large_packet_ratio"],
            "operator": "<=",
            "threshold": rule.large_packet_max,
            "passed": actuals["large_packet_ratio"] <= rule.large_packet_max,
        },
        "normal_char_ratio": {
            "actual": actuals["normal_char_ratio"],
            "operator": ">=",
            "threshold": rule.normal_char_min,
            "passed": actuals["normal_char_ratio"] >= rule.normal_char_min,
        },
        "large_char_ratio": {
            "actual": actuals["large_char_ratio"],
            "operator": "<=",
            "threshold": rule.large_char_max,
            "passed": actuals["large_char_ratio"] <= rule.large_char_max,
        },
    }
    return {
        "status": "PASS" if all(check["passed"] for check in checks.values()) else "FAIL",
        "reason": None,
        "rule": _quality_rule_dict(rule),
        "checks": checks,
    }


def _stats_log_path() -> Path:
    override = os.environ.get("M3_STREAM_STATS_LOG")
    if override:
        path = Path(override).expanduser().resolve()
        worker_id = os.environ.get("PYTEST_XDIST_WORKER")
        if worker_id and worker_id != "master":
            path = path.with_name(f"{path.stem}_{worker_id}{path.suffix}")
        return path

    if helpers.RUN_LOG_PATH is not None:
        run_log_path = Path(helpers.RUN_LOG_PATH)
        return run_log_path.with_name(
            f"{run_log_path.stem}_stream_stats{run_log_path.suffix}"
        )
    return _FALLBACK_STATS_PATH


def _write_stats_record(record: dict[str, Any]) -> Path:
    path = _stats_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
    return path


def _build_distributions(packets: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "reasoning_content_chars": _summarize_lengths(
            packets, "reasoning_content_chars"
        ),
        "content_chars": _summarize_lengths(packets, "content_chars"),
        "tool_call_name_chars": _summarize_lengths(
            packets, "tool_call_name_chars"
        ),
        "tool_call_arguments_chars": _summarize_lengths(
            packets, "tool_call_arguments_chars"
        ),
    }


def _build_stats_record(
    scenario: StreamScenario, result: dict[str, Any]
) -> dict[str, Any]:
    packets = _collect_packet_lengths(result.get("chunks") or [])
    distributions = _build_distributions(packets)
    by_index = _summarize_tool_arguments_by_index(packets)
    overall_evaluation = _evaluate_distribution(
        distributions["tool_call_arguments_chars"], scenario.quality_rule
    )
    index_evaluations = (
        {
            tool_index: _evaluate_distribution(distribution, scenario.quality_rule)
            for tool_index, distribution in by_index.items()
        }
        if scenario.validate_each_tool_call
        else {}
    )
    quality_statuses = [overall_evaluation["status"]]
    quality_statuses.extend(
        evaluation["status"] for evaluation in index_evaluations.values()
    )
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "category": "tool_call",
        "scenario": scenario.name,
        "run_count": 1,
        "trace_id": result.get("trace_id"),
        "trace_ids": [result.get("trace_id")],
        "packet_count": len(packets),
        "packets": packets,
        "distributions": distributions,
        "tool_call_argument_distributions_by_index": by_index,
        "quality_evaluation": {
            "status": (
                "PASS"
                if all(status == "PASS" for status in quality_statuses)
                else "FAIL"
            ),
            "target_field": "tool_call_arguments_chars",
            "overall": overall_evaluation,
            "by_tool_call_index": index_evaluations,
        },
    }


def _build_content_aggregate_stats_record(
    scenario: StreamScenario,
    results: list[dict[str, Any]],
    requested_run_count: int,
) -> dict[str, Any]:
    aggregate_packets = []
    run_summaries = []
    trace_ids = []
    for run_index, result in enumerate(results, start=1):
        packets = _collect_packet_lengths(result.get("chunks") or [])
        aggregate_packets.extend({
            **packet,
            "run_index": run_index,
        } for packet in packets)
        trace_id = result.get("trace_id")
        trace_ids.append(trace_id)
        run_summaries.append({
            "run_index": run_index,
            "trace_id": trace_id,
            "packet_count": len(packets),
            "distributions": _build_distributions(packets),
        })

    distributions = _build_distributions(aggregate_packets)
    overall_evaluation = _evaluate_distribution(
        distributions["content_chars"], scenario.quality_rule
    )
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "category": "content",
        "scenario": scenario.name,
        "run_count": len(results),
        "requested_run_count": requested_run_count,
        "trace_ids": trace_ids,
        "packet_count": len(aggregate_packets),
        "packets": aggregate_packets,
        "runs": run_summaries,
        "distributions": distributions,
        "tool_call_argument_distributions_by_index": {},
        "quality_evaluation": {
            "status": overall_evaluation["status"],
            "target_field": "content_chars",
            "overall": overall_evaluation,
            "by_tool_call_index": {},
        },
    }


def _print_distribution(record: dict[str, Any], stats_path: Path) -> None:
    output = {
        "category": record["category"],
        "scenario": record["scenario"],
        "run_count": record["run_count"],
        "trace_id": record.get("trace_id"),
        "trace_ids": record.get("trace_ids"),
        "packet_count": record["packet_count"],
        "distributions": record["distributions"],
        "tool_call_argument_distributions_by_index": (
            record["tool_call_argument_distributions_by_index"]
        ),
        "quality_evaluation": record["quality_evaluation"],
        "stats_log": str(stats_path),
    }
    print(f"\n[m3_stream_stats] {json.dumps(output, ensure_ascii=False)}")


def _assert_packet_quality(record: dict[str, Any]) -> None:
    evaluation = record["quality_evaluation"]
    assert evaluation["status"] == "PASS", (
        f"{record['scenario']}: packet quality FAIL; "
        f"target={evaluation['target_field']}; "
        f"overall={evaluation['overall']}; "
        f"by_tool_call_index={evaluation['by_tool_call_index']}"
    )


def _build_payload(scenario: StreamScenario) -> dict[str, Any]:
    payload = {
        "messages": oai_simple_messages(scenario.prompt),
        "max_tokens": 4096,
        "thinking": {"type": "adaptive"},
    }
    if scenario.tools:
        payload["tools"] = list(scenario.tools)
    if scenario.tool_choice is not None:
        payload["tool_choice"] = scenario.tool_choice
    payload.update(scenario.payload_overrides)
    return payload


class TestSSEStream:
    """SSE streaming protocol validation."""

    def test_02_06_stream_usage_only_in_last_chunk(self):
        """stream_options.include_usage=true: usage appears only in the final chunk."""
        result = oai_chat({
            "messages": oai_simple_messages("Say hi"),
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(result)
        assert_stream_usage_only_in_last_chunk(
            result, msg="02_06 text include_usage"
        )

    def test_02_07_content_and_reasoning_content_not_coexist_in_chunk(self):
        """同一 SSE chunk 的 delta 内 content 和 reasoning_content 不得同时非空。

        M3 流式协议约定:思考阶段只吐 reasoning_content,回答阶段只吐 content,
        两者在时间上不重叠。若单个 delta 同时携带两者会打乱下游解析(如 TTFT
        统计、think/answer 分离渲染)。

        用长思考 + 长回答的 prompt 提高覆盖:短响应包少,交界处不容易踩中混合包;
        长响应包多,思考→回答切换窗口更宽,更能暴露实现里 flush 边界的问题。
        连续跑 20 次,任意一次出现混合包即判失败。
        """
        prompt = (
            "请分两步完成,思考和回答都要足够详细:\n"
            "1) 详细推理:一辆车以 60 km/h 匀速行驶 2.5 小时后减速到 45 km/h "
            "再行驶 1.75 小时,期间中途休息了 20 分钟(不计入行驶),"
            "全程平均速度是多少?请把每一步的中间量都写出来。\n"
            "2) 给出最终答案:用一段不少于 300 字的中文说明,"
            "把结论、单位换算、以及为什么休息时间要单独扣除讲清楚,"
            "并举一个日常生活中类似的例子帮助理解。"
        )
        run_count = 20
        first_failure = None
        for run_idx in range(1, run_count + 1):
            result = oai_chat({
                "messages": oai_simple_messages(prompt),
                "max_tokens": 4096,
                "thinking": {"type": "adaptive"},
            }, stream=True)
            assert_oai_stream_success(result)

            offenders = []
            for idx, chunk in enumerate(result.get("chunks") or []):
                if not isinstance(chunk, dict):
                    continue
                for choice_idx, choice in enumerate(chunk.get("choices") or []):
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta") or {}
                    if not isinstance(delta, dict):
                        continue
                    content = delta.get("content")
                    reasoning = delta.get("reasoning_content")
                    if (isinstance(content, str) and content
                            and isinstance(reasoning, str) and reasoning):
                        offenders.append({
                            "chunk_index": idx,
                            "choice_index": choice_idx,
                            "content_preview": content[:80],
                            "reasoning_preview": reasoning[:80],
                        })

            if offenders:
                first_failure = {
                    "run": run_idx,
                    "offender_count": len(offenders),
                    "samples": offenders[:3],
                }
                break

        assert first_failure is None, (
            f"02_07 连续 {run_count} 次中第 {first_failure['run']} 次出现 "
            f"{first_failure['offender_count']} 个 chunk 同时携带非空 "
            f"content 与 reasoning_content,示例: {first_failure['samples']}"
        )


class TestContentStreamPacketLengthDistribution:
    """Run pure-content scenarios repeatedly, then aggregate packet statistics."""

    @pytest.mark.parametrize(
        "scenario",
        CONTENT_SCENARIO_PARAMS,
    )
    def test_content_stream_packet_length_distribution(
        self, scenario: StreamScenario
    ):
        results = []
        for _ in range(CONTENT_SCENARIO_RUNS):
            result = oai_chat(_build_payload(scenario), stream=True)
            results.append(result)

        record = _build_content_aggregate_stats_record(
            scenario,
            results,
            requested_run_count=CONTENT_SCENARIO_RUNS,
        )
        stats_path = _write_stats_record(record)
        _print_distribution(record, stats_path)
        _assert_packet_quality(record)


class TestToolCallStreamPacketLengthDistribution:
    """Run tool-call scenarios once and record packet statistics."""

    @pytest.mark.parametrize(
        "scenario",
        TOOL_CALL_SCENARIO_PARAMS,
    )
    def test_tool_call_stream_packet_length_distribution(
        self, scenario: StreamScenario
    ):
        result = oai_chat(_build_payload(scenario), stream=True)
        record = _build_stats_record(scenario, result)
        stats_path = _write_stats_record(record)
        _print_distribution(record, stats_path)
        _assert_packet_quality(record)
