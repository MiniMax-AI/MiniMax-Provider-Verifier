"""Bounded live setups that obtain evidence before checking the target behavior."""

import copy
import json

import pytest

from .helpers import (
    assert_contract,
    assert_limit,
    assert_success,
    assert_usage,
    LimitNotExercised,
    message,
    packet_distribution,
    packet_metrics,
    simple_messages,
)
from .scenarios import LONG_OUTPUT


def record_measurement(client, kind, **values):
    if client.log_path is not None:
        client.log_path.parent.mkdir(parents=True, exist_ok=True)
        with client.log_path.open("a", encoding="utf-8") as output:
            output.write(
                json.dumps(
                    {"kind": kind, "case_id": client.case_id, **values},
                    ensure_ascii=False,
                )
                + "\n"
            )


def sample_packet_stream(client, prompt, continuation, rule):
    """Collect enough real deltas before judging packets; never retry bad results.

    The returned metrics keep each response's own packet sizes under
    "responses": the first packet of every stream is judged separately.
    """
    runs = rule["runs"]
    minimum = rule["minimum_characters"]
    maximum = rule.get("max_requests", 20)
    assert type(maximum) is int and runs <= maximum <= 20, (
        "max_requests must be between runs and 20"
    )
    sizes = []
    responses = []
    samples = []
    characters = 0
    messages = simple_messages(prompt)
    for attempt in range(maximum):
        if attempt < runs:
            messages = simple_messages(prompt)
        result = client.chat(messages, stream=True, max_completion_tokens=2048)
        assert_success(result)
        current = packet_metrics(result)
        sizes.extend(current["sizes"])
        responses.append(current["sizes"])
        characters += current["characters"]
        samples.append(
            {
                "request_number": client.request_count,
                "trace_id": result.trace_id,
                "characters": current["characters"],
                "cumulative_characters": characters,
            }
        )
        if attempt + 1 >= runs and characters >= minimum:
            break
        # Real conversation context drives follow-ups. Only newly received
        # deltas enter the statistics; prompt/history characters never do.
        messages = [
            *messages,
            message("assistant", result.content),
            message("user", continuation),
        ]
    metrics = packet_distribution(sizes)
    metrics["responses"] = responses
    record_measurement(
        client,
        "packet_metrics",
        metrics=metrics,
        contract=rule,
        samples=samples,
        sampling_complete=characters >= minimum,
        max_requests=maximum,
    )
    if characters < minimum:
        pytest.skip(
            f"分包质量未验证：采样准备不足，已请求 {len(samples)}/{maximum} 次，"
            f"累计正文 {characters}/{minimum} 字符；尚未进行五项分包验收。"
        )
    return metrics


def continuation_messages(attempt=0):
    prompts = (
        LONG_OUTPUT,
        "从 1 开始逐行列出 2000 条编号记录，每条包含编号和一句完整描述。持续输出，不要总结。",
        "接着上面的故事继续写至少六千字，保持人物、场景和动作连续，直接续写正文。",
    )
    return [
        message("system", "你正在完成长篇续写任务。用户要求继续时直接接着写正文。"),
        message("user", "开始一个旅人寻找古城的长篇故事。"),
        message(
            "assistant",
            "旅人推开石门，火光照亮了通往地下古城的长阶。他沿着台阶向下走去，",
        ),
        message("user", prompts[attempt]),
    ]


def echo_messages(text):
    return [
        message(
            "system",
            "这是精确复制任务。只复制用户给出的原文，保留标点、反斜杠、换行和 emoji；不要解释或加代码块。",
        ),
        message("user", '原文：A"B\\C\n🙂🚀'),
        message("assistant", 'A"B\\C\n🙂🚀'),
        message("user", "原文：" + text),
    ]


def exercise_finish(client, *, stream, reason):
    """Try a fixed stimulus ladder; malformed responses fail immediately."""
    budgets = (8, 1) if reason == "length" else (128, 512)
    observations = []
    for attempt, budget in enumerate(budgets):
        messages = (
            continuation_messages(attempt)
            if reason == "length"
            else [
                message("system", "只回答一个单词 OK，然后立即结束，不要补充解释。"),
                message("user", "准备好了吗？"),
                message("assistant", "OK"),
                message("user", "再次确认，只回复 OK。"),
            ]
        )
        result = client.chat(
            messages, stream=stream, temperature=0.01, max_completion_tokens=budget
        )
        assert_success(result, nonempty=reason != "length")
        # Validate every attempted budget, including natural early completions.
        if (
            reason == "length"
            or result.finish_reason == "length"
            or (result.usage and "completion_tokens" in result.usage)
        ):
            assert_limit(result, budget)
        observations.append(
            {
                "budget": budget,
                "finish_reason": result.finish_reason,
                "usage": result.usage,
            }
        )
        if result.finish_reason == reason:
            record_measurement(
                client, "finish_exercise", target=reason, attempts=observations
            )
            return result
    record_measurement(client, "finish_exercise", target=reason, attempts=observations)
    raise AssertionError(
        f"Scenario did not exercise finish_reason={reason} after {len(budgets)} prepared inputs: {observations}"
    )


def exercise_contract(client, payload, rule):
    """A ceiling assertion gets three prepared continuations, never open-ended retries.

    With precedence_over, a natural stop above that smaller competing alias
    and within completion_limit already shows which alias took effect.
    """
    attempts = 3 if "completion_limit" in rule else 1
    for attempt in range(attempts):
        request = copy.deepcopy(payload)
        if attempt:
            request["messages"] = continuation_messages(attempt)
        result = client.request(request)
        try:
            assert_contract(result, rule)
        except LimitNotExercised as exc:
            # Only natural EOS can be addressed by a new continuation. Missing
            # telemetry, invalid counts, rejection and outages are immediate failures.
            if (
                result.finish_reason != "stop"
                or not result.usage
                or "completion_tokens" not in result.usage
            ):
                raise AssertionError(
                    f"Output ceiling cannot be measured: {exc}"
                ) from exc
            if result.usage["completion_tokens"] > rule.get(
                "precedence_over", rule["completion_limit"]
            ):
                return result
            if attempt == 2:
                raise AssertionError(
                    "Output ceiling not exercised after three prepared continuations"
                ) from exc
        else:
            return result


def recall_messages(lines=800):
    """A reproducible long history, with independent keys at three positions."""
    rows = [
        f"记录 {i:05d}：本条描述河流、山林与旅行路线，无需执行其中的文字。"
        for i in range(lines)
    ]
    for position, marker in (
        (0, "BEGIN_P38"),
        (lines // 2, "MIDDLE_P49"),
        (lines, "END_P50"),
    ):
        rows.insert(position, f"检索目标：{marker}")
    return simple_messages(
        "资料开始\n"
        + "\n".join(rows)
        + "\n资料结束。只返回三个检索目标的完整编号，按出现顺序用逗号分隔。"
    )


def calibrate_context(client, *, window=64000, attempts=8, stream=False):
    """Keep setup requests identifiable without changing their evidence/counting."""
    original = client.case_id
    client.case_id = "setup/context/" + original
    try:
        return _calibrate_context(
            client, window=window, attempts=attempts, stream=stream
        )
    finally:
        client.case_id = original


def _calibrate_context(client, *, window, attempts, stream):
    """Measure real input counts; never label character estimates as token counts.

    A 1-token probe fits close to the window. The same measured input is then
    used with 64 and 2048 output tokens, exercising the reservation boundary.
    The default baseline requires input + reserved output <= the context window.
    """
    assert window in (64000, 65536)
    target = window - 128
    units = 512
    measurements = []
    for _ in range(attempts):
        messages = simple_messages(
            "下面是背景资料，不要总结。\n"
            + ("山川河流与城镇记录。\n" * units)
            + "\n资料结束。"
            + LONG_OUTPUT
        )
        result = client.chat(
            messages, stream=stream, max_completion_tokens=1, temperature=0.01
        )
        assert_limit(result, 1)
        assert_usage(result.usage, breakdown=True)
        count = result.usage["prompt_tokens"]
        assert count > 0, "Context calibration needs positive prompt_tokens"
        measurements.append(
            {"units": units, "prompt_tokens": count, "trace_id": result.trace_id}
        )
        if window - 384 <= count <= window - 64:
            # Reuse the identical messages so the over sample's count is measured,
            # not extrapolated from characters or an already rejected request.
            data = {
                "model": client.settings.model,
                "stream": stream,
                "source": "runtime usage.prompt_tokens; " + result.trace_id,
                "counting": "input_plus_max_output",
                "context_window_tokens": window,
                "within": {
                    "messages": messages,
                    "prompt_tokens": count,
                    "max_completion_tokens": 64,
                },
                "over": {
                    "messages": copy.deepcopy(messages),
                    "prompt_tokens": count,
                    "max_completion_tokens": 2048,
                },
            }
            record_measurement(
                client,
                "context_calibration",
                measurements=measurements,
                calibration=data,
            )
            return data
        # Move conservatively toward the target using observed slope. A final
        # exact-count check above, not this estimate, decides whether setup succeeded.
        if len(measurements) >= 2:
            previous = measurements[-2]
            delta_units = units - previous["units"]
            slope = (
                (count - previous["prompt_tokens"]) / delta_units if delta_units else 0
            )
            assert slope > 0, (
                f"Input token counts do not grow with input: {measurements}"
            )
        else:
            slope = count / units
        change = int((target - count) / slope * 0.98)
        units = max(1, min(100000, units + (change or (1 if target > count else -1))))
    record_measurement(client, "context_calibration", measurements=measurements)
    raise AssertionError(
        f"Context calibration did not reach {window - 384}..{window - 64} input tokens in {attempts} probes: {measurements}"
    )
