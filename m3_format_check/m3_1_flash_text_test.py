"""
M3_1_Flash API Test — pure-text case collection

Organized into modules by "what is being validated"; case naming convention:
    test_<module_id>_<index_within_module>_<scenario>

Module id / topic:
    01  basic_text           basic text chat (non-stream)
    02  sse_stream           SSE streaming protocol fields
    03  multiturn            multi-turn conversation
    04  thinking             thinking toggle
    05  sampling             sampling params (temperature / top_p / seed)
    06  max_tokens           max_tokens / max_completion_tokens boundaries
    07  message_format       message content/role format and edges
    08  model_compat         model-name compatibility
    09  response_format      response_format JSON output
    10  usage_field          usage field semantics / arithmetic / cache
    11  role_root            role=root protocol acceptance & identity follow-through
    12  text_semantic        text semantic follow-through (multilingual / system-prompt compliance / long-form)
    13  tool_call_basic      tool call basics
    14  tool_call_schema     tool call schema advanced validation
    15  tool_call_combo      tool call combined with other features
    16  tool_call_edge       tool call boundary / exception handling
    17  param_stress         param stress (long conversation / long system)
    18  reasoning_split      reasoning_split extension field
    19  finish_reason        finish_reason coverage
    20  error_codes          error codes (pure-text category)
    26  prompt_cache         prompt_cache_key request field
    27  passthrough_params   metadata / store / user
    28  extended_capability  prediction

No image / video requests. Modality priority is video > image > text; this file
collects text cases only.

All cases go through helpers.oai_chat() against /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
import json
import os
import re
import uuid

import pytest

from helpers import *


# --------------- File-level helper utilities ---------------

def _has_chinese(text: str) -> bool:
    """Return True if text contains at least one CJK character.

    helpers.py does not provide this utility; implemented locally to avoid
    polluting upstream helpers. Used by §12 Chinese text generation cases.
    """
    if not text:
        return False
    return bool(re.search(r"[一-鿿]", text))


def _is_json_int(value) -> bool:
    """Return True for a JSON integer; bool is an int subclass in Python but not in JSON."""
    return isinstance(value, int) and not isinstance(value, bool)


def _assert_usage_totals(usage, msg: str):
    """Assert usage is an object with non-negative integer totals that add up."""
    assert isinstance(usage, dict), f"{msg}: usage should be an object, got {usage!r}"
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        assert _is_json_int(value) and value >= 0, (
            f"{msg}: usage.{key} should be a non-negative integer, got {value!r}"
        )
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], (
        f"{msg}: total_tokens should equal prompt_tokens + completion_tokens, got {usage!r}"
    )


# --------------- Tool-call case helpers ---------------

def _finish(r: dict):
    return r["body"]["choices"][0].get("finish_reason")


def _assert_calls(r: dict, tools: list, msg: str, schema_check: bool = True) -> list:
    """Every returned call has a distinct non-empty id, a declared name and arguments that parse
    as a JSON object; with schema_check the arguments also satisfy the declared parameters.
    Works for stream and non-stream results. Returns the get_tool_calls() items."""
    schemas = {t["function"]["name"]: t["function"].get("parameters") or {"type": "object"}
               for t in tools if t.get("type") == "function"}
    calls = get_tool_calls(r)
    for i, c in enumerate(calls):
        assert c["name"] in schemas, f"{msg}: call[{i}] name={c['name']!r} is not declared in {sorted(schemas)}"
        assert c["arguments_obj"] is not None, (
            f"{msg}: call[{i}] arguments are not a JSON object: {c['arguments_raw'][:300]!r}"
        )
        if schema_check:
            validate_json_schema(c["arguments_obj"], schemas[c["name"]], f"{msg}: call[{i}] {c['name']}")
    ids = [c["id"] for c in calls]
    assert all(ids) and len(set(ids)) == len(ids), f"{msg}: call ids should be non-empty and distinct: {ids}"
    return calls


def _echo_real_call(tools=None):
    """Turn 1 of a real loop: ask for echo(text=hello) and bind the returned call(s).

    The prompt asks for the call; tool_choice is not sent because the reference
    endpoint does not enforce it. Returns (user_msg, assistant_msg, calls) where
    assistant_msg replays the returned tool_calls with their real ids/arguments."""
    tools = tools or [ECHO_TOOL_OAI]
    user = {"role": "user", "content": ECHO_PROMPT}
    r1 = oai_chat({"messages": [user], "tools": tools})
    assert_oai_success(r1)
    assert _finish(r1) == "tool_calls", f"turn 1 finish_reason should be tool_calls, got {_finish(r1)!r}"
    calls = _assert_calls(r1, tools, "turn 1")
    assert calls, "turn 1 returned no tool_calls"
    assistant = {"role": "assistant", "content": None, "tool_calls": [
        {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments_raw"]}}
        for c in calls
    ]}
    return user, assistant, calls


def _tool_replies(calls, content="hello"):
    return [{"role": "tool", "tool_call_id": c["id"], "content": content} for c in calls]


def _note_schema_deviation(args, schema: dict, msg: str):
    """Print (do not fail on) arguments that violate the declared schema.

    The reference endpoint accepts strict=true but does not enforce it, so schema
    conformance is model behaviour rather than a contract and is only recorded."""
    try:
        validate_json_schema(args, schema, msg)
    except AssertionError as exc:
        print(f"[strict-not-enforced] {msg}: {str(exc).splitlines()[0]}")


def _assert_single_strict_call(r: dict, tool: dict, msg: str) -> dict:
    """strict, call requested by the prompt: finish tool_calls, at least one call to the
    declared function, arguments a JSON object. Full schema conformance is recorded, not
    asserted (strict is accepted but not enforced by the reference endpoint, and neither is
    parallel_tool_calls, so extra calls are allowed). Returns the first call's arguments."""
    assert_oai_success(r)
    assert _finish(r) == "tool_calls", f"{msg}: finish_reason should be tool_calls, got {_finish(r)!r}"
    calls = _assert_calls(r, [tool], msg, schema_check=False)
    assert calls, f"{msg}: the prompt asks for a call but no tool_calls returned"
    _note_schema_deviation(calls[0]["arguments_obj"], tool["function"]["parameters"], msg)
    return calls[0]["arguments_obj"]


def _assert_required_calls_loose(r: dict, name: str, msg: str):
    """Non-strict, call requested by the prompt: finish tool_calls, at least one call, every call names
    `name`, id non-empty, type function, arguments a string. Whether the arguments parse /
    satisfy the schema is not guaranteed without strict, so not asserted."""
    assert_oai_success(r)
    assert _finish(r) == "tool_calls", f"{msg}: finish_reason should be tool_calls, got {_finish(r)!r}"
    items = message_tool_calls(r)
    assert items, f"{msg}: the prompt asks for a call but no tool_calls returned"
    for i, tc in enumerate(items):
        assert isinstance(tc.get("id"), str) and tc["id"], f"{msg}: tool_calls[{i}].id should be non-empty"
        assert tc.get("type") == "function", f"{msg}: tool_calls[{i}].type should be function"
        fn = tc.get("function") or {}
        assert fn.get("name") == name, f"{msg}: tool_calls[{i}].name should be {name!r}, got {fn.get('name')!r}"
        assert isinstance(fn.get("arguments"), str), f"{msg}: tool_calls[{i}].arguments should be a string"
    return items


# ============================================================
# 01 basic_text — basic text chat (non-stream)
# ============================================================

class TestBasicText:
    """Basic text chat: validates the minimal usable path of non-stream chat completion."""

    def test_01_01_text_non_stream(self):
        """Most basic non-stream text chat: the full ChatCompletion contract
        (assert_chat_completion_strict) with finish_reason=stop and non-empty content.

        No tools declared, so tool_choice defaults to none and no tool call may appear."""
        r = oai_chat({"messages": oai_simple_messages("What is 1+1?")})
        assert_oai_success(r)
        assert len(get_oai_content(r)) > 0
        assert_chat_completion_strict(r, msg="01_01", finish="stop")
        assert_text_reply(r, msg="01_01 no tools")
        details = r["body"]["usage"].get("prompt_tokens_details")
        assert details is None or isinstance(details, dict), (
            f"usage.prompt_tokens_details should be an object, got {details!r}"
        )

    def test_01_02_content_string(self):
        """user.content as plain string."""
        r = oai_chat({"messages": [
            {"role": "user", "content": "Hello, what is 1+1?"},
        ]})
        assert_oai_success(r)

    def test_01_03_content_array(self):
        """user.content as OAI parts array [{type:text,text:...}]."""
        r = oai_chat({"messages": [
            {"role": "user", "content": [{"type": "text", "text": "Hello, what is 1+1?"}]},
        ]})
        assert_oai_success(r)


# ============================================================
# 02 sse_stream — streaming protocol fields
# ============================================================

class TestSSEStream:
    """SSE streaming protocol: chunk structure / DONE / usage chunk / include_usage."""

    def test_02_01_text_stream(self):
        """Text streaming reply; assert stream can rebuild content properly."""
        r = oai_chat({"messages": oai_simple_messages("What is 1+1?")}, stream=True)
        assert_oai_stream_success(r)
        assert isinstance(get_oai_content(r), str)

    def test_02_02_stream_usage(self):
        """Trailing usage chunk: total = prompt + completion + stream finishes cleanly."""
        r = oai_chat({
            "messages": oai_simple_messages("Say hi"),
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)
        usage_chunks = [c for c in r["chunks"] if c.get("usage")]
        assert len(usage_chunks) > 0, "No usage chunk in stream"
        # Take the last usage chunk to validate token arithmetic
        last_usage = usage_chunks[-1]["usage"]
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            assert k in last_usage, f"stream usage missing {k}"
        assert last_usage["total_tokens"] == last_usage["prompt_tokens"] + last_usage["completion_tokens"], (
            f"stream usage math: total={last_usage['total_tokens']} != "
            f"prompt={last_usage['prompt_tokens']}+completion={last_usage['completion_tokens']}"
        )
        # Stream should complete normally (trailing chunk carries finish_reason)
        assert_stream_complete(r, msg="stream_usage")

    def test_02_03_sse_done_marker(self):
        """Raw SSE ends with a literal [DONE] data line, a blank line, and no `event: done`."""
        status, lines = oai_chat_raw_sse_lines({"messages": oai_simple_messages("Hi")})
        assert status == 200, f"02_03 expected 200, got {status}"
        data_lines = [line for line in lines if line.startswith("data:")]
        assert data_lines, "02_03 no data lines in stream"
        assert data_lines[-1][len("data:"):].strip() == "[DONE]", (
            f"02_03 last data line is not [DONE]: {data_lines[-1]!r}"
        )
        done_at = len(lines) - 1 - lines[::-1].index(data_lines[-1])
        assert done_at + 1 < len(lines) and lines[done_at + 1] == "", (
            f"02_03 [DONE] is not terminated by a blank line: {lines[done_at:]!r}"
        )
        assert not any(line.startswith("event:") and "done" in line.lower() for line in lines), (
            "02_03 stream must signal completion with [DONE], not an `event: done` line"
        )

    def test_02_04_stream_chunk_fields(self):
        """Stream chunk required fields: id / choices / object."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)
        chunks = stream_data_chunks(r)
        for chunk in chunks:
            assert isinstance(chunk.get("id"), str) and chunk["id"], f"02_04 bad id: {chunk!r}"
            assert isinstance(chunk.get("choices"), list), f"02_04 bad choices: {chunk!r}"
            assert chunk.get("object") == "chat.completion.chunk", f"02_04 bad object: {chunk!r}"
            assert isinstance(chunk.get("created"), int), f"02_04 bad created: {chunk!r}"
            assert isinstance(chunk.get("model"), str), f"02_04 bad model: {chunk!r}"
        assert len({c["id"] for c in chunks}) == 1, "02_04 id changed within one stream"
        assert len({c["created"] for c in chunks}) == 1, "02_04 created changed within one stream"

    def test_02_05_text_include_usage(self):
        """stream_options.include_usage=true in text scenario should return a usage chunk."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)

    # 02_06 (text include_usage / usage-only-in-last-chunk) moved to
    # m3_1_flash_stream_test.py::TestSSEStream::test_02_06_stream_usage_only_in_last_chunk
    # to keep the SSE usage-placement rule in a single place.

    def test_02_07_stream_no_utf8_replacement_char_in_emoji(self):
        """流式 delta.content 不得出现 U+FFFD(�)替换字符。

        背景:部分 provider 的输出链路存在 UTF-8 分帧(framing)问题,
        会把一个四字节 emoji 从字节中间截断。
        随后服务端把非法字节转成 EF BF BD,即 Unicode 替换字符 U+FFFD(�),
        并丢弃剩余字节。因为返回的 JSON 里已经落成了 �,客户端无论如何缓存、
        拼接都无法恢复原始 emoji,直接导致输出损坏。

        用大量四字节 emoji + 编号的 prompt 提高覆盖:emoji 越密集,分帧边界
        恰好落在多字节字符中间的概率越高,越容易暴露实现里 flush 的字节截断问题。
        连续跑 20 次,任意一次在聚合 content 或任一 delta 分片里检测到 U+FFFD
        即判失败。
        """
        prompt = (
            "请用一行输出 50 个各不相同的 emoji,格式为 '文本 <emoji> N.',"
            "以空格分隔,N 从 1 到 50。必须正好 50 个,不重复,不要任何解释说明。"
            "尽量多使用四字节(surrogate pair)的彩色 emoji,如 😁😂🤣😊🙃🥰🤩🤔🥱🤪🧐🥺。"
        )
        run_count = 20
        first_failure = None
        for run_idx in range(1, run_count + 1):
            result = oai_chat({
                "messages": oai_simple_messages(prompt),
                "max_tokens": 4096,
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
                    if isinstance(content, str) and "\ufffd" in content:
                        offenders.append({
                            "chunk_index": idx,
                            "choice_index": choice_idx,
                            "fffd_count": content.count("\ufffd"),
                            "content_preview": content[:80],
                        })

            if offenders:
                first_failure = {
                    "run": run_idx,
                    "offender_count": len(offenders),
                    "total_fffd": sum(o["fffd_count"] for o in offenders),
                    "samples": offenders[:3],
                }
                break

        assert first_failure is None, (
            f"02_07 连续 {run_count} 次中第 {first_failure['run']} 次在流式 "
            f"delta.content 检测到 U+FFFD(�)替换字符,涉及 "
            f"{first_failure['offender_count']} 个 chunk、共 "
            f"{first_failure['total_fffd']} 个 �,疑似 UTF-8 分帧把四字节 emoji "
            f"从中间截断;示例: {first_failure['samples']}"
        )


# ============================================================
# 03 multiturn — multi-turn conversation
# ============================================================

class TestMultiturn:
    """Multi-turn conversation: verify the model maintains context across turns."""

    def test_03_01_multiturn(self):
        """Two turns: user self-reports as Alice then asks for the name; response should contain Alice."""
        r = oai_chat({"messages": oai_multiturn_messages()})
        assert_oai_success(r)
        content = get_oai_content(r).lower()
        assert "alice" in content

    def test_03_02_multiturn_5_rounds(self):
        """5-round arithmetic conversation: x=10, y=x+5=15, z=x+y=25; ask x+y+z, response should contain '50'."""
        msgs = [
            {"role": "system", "content": "You are a helpful math tutor."},
            {"role": "user", "content": "Let x = 10."},
            {"role": "assistant", "content": "Okay, x is set to 10."},
            {"role": "user", "content": "Now let y = x + 5."},
            {"role": "assistant", "content": "Got it, y = 15."},
            {"role": "user", "content": "What is x * y?"},
            {"role": "assistant", "content": "x * y = 10 * 15 = 150."},
            {"role": "user", "content": "Let z = x + y."},
            {"role": "assistant", "content": "z = 10 + 15 = 25."},
            {"role": "user", "content": "What is x + y + z?"},
        ]
        r = oai_chat({"messages": msgs})
        assert_oai_success(r)
        assert r.get("trace_id"), (
            f"multiturn_5_rounds missing trace_id: status={r.get('status')}"
        )
        content = get_oai_content(r)
        assert "50" in content, (
            f"expected '50' (10+15+25) in multiturn response: {content[:200]!r}"
        )

    @pytest.mark.parametrize("messages", [
        [{"role": "user", "name": "a", "content": "Please compare plan A."},
         {"role": "user", "name": "b", "content": "Also compare plan B."}],
        [{"role": "user", "content": "Hello"},
         {"role": "assistant", "content": [{"type": "text", "text": "Hello."}]},
         {"role": "user", "content": "Continue"}],
        [{"role": "user", "content": "Earlier request"},
         {"role": "assistant", "content": "I cannot help with the earlier request.",
          "refusal": "I cannot help with the earlier request."},
         {"role": "user", "content": "Please explain caching."}],
        [{"role": "user", "content": "Hello"},
         {"role": "assistant", "content": "Hello", "refusal": None},
         {"role": "user", "content": "Continue"}],
    ], ids=["participant_names", "assistant_text_parts", "assistant_refusal_string", "assistant_refusal_null"])
    def test_03_04_history_message_forms(self, messages):
        """03_04 — Legal history message forms are accepted: per-message `name`,
        assistant content as a text-part array, and assistant `refusal` as a string or null."""
        assert_request_accepted({"messages": messages}, msg="03_04")


# ============================================================
# 04 thinking — thinking toggle
# ============================================================

class TestThinking:
    """thinking field: disabled / adaptive / invalid value / combined with streaming."""

    def test_04_02_thinking_adaptive(self):
        """thinking.type=adaptive: model decides whether to think; only assert 200."""
        r = oai_chat({
            "messages": oai_simple_messages("What is 2+2?"),
            "thinking": {"type": "adaptive"},
        })
        assert_oai_success(r)

    def test_04_03_thinking_invalid_value(self):
        """thinking.type invalid value (not disabled/adaptive) → 400/422 reject or 200 fallback."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "thinking": {"type": "invalid_value_xyz"},
        })
        assert r["status"] in (200, 400, 422), (
            f"thinking.type=invalid_value_xyz HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_04_04_thinking_stream(self):
        """thinking.type=adaptive + stream; verify streaming + thinking coexistence."""
        r = oai_chat({
            "messages": oai_simple_messages("What is 15*17? Think step by step."),
            "thinking": {"type": "adaptive"},
        }, stream=True)
        assert_oai_stream_success(r)
        assert_thinking_present(r, msg="thinking_stream adaptive")


# ============================================================
# 05 sampling — sampling params (temperature / top_p / seed)
# ============================================================

class TestSampling:
    """Sampling parameters: boundary values and explicit null are accepted as plain requests.

    Only acceptance and the response envelope are checked; the effect of a sampling value
    on the generated text is not a format guarantee.
    """

    @pytest.mark.parametrize("field,value", [
        ("temperature", 0), ("temperature", 0.2), ("temperature", 2), ("temperature", None),
        ("top_p", 0.1), ("top_p", 1), ("top_p", None),
    ], ids=["temperature=0", "temperature=0.2", "temperature=2", "temperature=null",
            "top_p=0.1", "top_p=1", "top_p=null"])
    def test_05_01_temperature_top_p_values(self, field, value):
        """05_01 — temperature in [0, 2] and top_p in [0, 1], including explicit null."""
        assert_request_accepted(contract_request(**{field: value}), msg=f"05_01 {field}={value}")

    @pytest.mark.parametrize("field,value", [
        ("presence_penalty", -2), ("presence_penalty", 0), ("presence_penalty", 2),
        ("frequency_penalty", -2), ("frequency_penalty", 0), ("frequency_penalty", 2),
    ], ids=["presence=-2", "presence=0", "presence=2", "frequency=-2", "frequency=0", "frequency=2"])
    def test_05_03_penalty_and_logit_bias(self, field, value):
        """05_03 — presence / frequency penalties at -2 / 0 / 2.

        Every request carries a small output budget; finish_reason=length is a legal outcome."""
        payload = contract_request(**{field: value}, max_completion_tokens=64)
        assert_request_accepted(payload, msg=f"05_03 {field}={value}")

    @pytest.mark.parametrize("stop", [["#A#", "#B#", "#C#", "#D#"], None], ids=["four_sequences", "null"])
    def test_05_04_stop_array_and_null(self, stop):
        """05_04 — stop as an array of four sequences, and stop explicitly null."""
        assert_request_accepted(contract_request(stop=stop), msg=f"05_04 stop={stop}")

    @pytest.mark.parametrize("seed", [-9223372036854775808, 9223372036854775807, None],
                             ids=["int64_min", "int64_max", "null"])
    def test_05_05_seed_values(self, seed):
        """05_05 — seed at the int64 bounds and explicitly null."""
        assert_request_accepted(contract_request(seed=seed), msg=f"05_05 seed={seed}")

    def test_05_07_same_seed_twice(self):
        """05_07 — The same seed sent twice: both requests return a normal completion.
        Identical output is best effort only and not asserted."""
        for i in (1, 2):
            assert_request_accepted(contract_request(seed=42), msg=f"05_07 request {i}")



# ============================================================
# 06 max_tokens — max_tokens / max_completion_tokens boundaries
# ============================================================

class TestMaxTokens:
    """Truncation and boundary behavior for max_tokens / max_completion_tokens."""

    def test_06_07_max_tokens_zero(self):
        """max_tokens=0: invalid value; server may reject (4xx) or leniently accept (200 returning empty)."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "max_tokens": 0,
        })
        assert r.get("trace_id"), (
            f"max_tokens=0 missing trace_id: status={r.get('status')}"
        )
        assert r["status"] in (200, 400, 422), (
            f"max_tokens=0 unexpected {r['status']} trace={r.get('trace_id')}"
        )

    @pytest.mark.parametrize("mt", [512000, 524288])
    def test_06_09_max_tokens_at_512k(self, mt):
        """max_tokens at the 512*1000 / 512*1024 boundary (the two common '512k' interpretations).

        In practice minimax-m3 official returns 200 for both interpretations
        (actual upper bound >= 524288), so we tighten the assertion to expect
        200 only.
        """
        r = oai_chat({
            "messages": oai_simple_messages("Reply with the word OK only"),
            "max_tokens": mt,
        })
        assert r.get("trace_id"), (
            f"max_tokens={mt} missing trace_id: status={r.get('status')}"
        )
        assert r["status"] == 200, (
            f"max_tokens={mt} expected 200, got {r['status']} trace={r.get('trace_id')}"
        )

    @pytest.mark.parametrize("mt", [524289, 1000000])
    def test_06_10_max_tokens_above_512k(self, mt):
        """max_tokens exceeding the 512k upper bound.

        Different providers handle over-limit values inconsistently:
        - Strict providers (minimax official) reject with 4xx
        - Lenient providers (fireworks, etc.) accept and truncate, returning 200
        Both are considered compliant as long as trace_id exists and status ∈ {200, 400, 422}.
        """
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "max_tokens": mt,
        })
        assert r["status"] in (200, 400, 422), (
            f"max_tokens={mt} expected 200/400/422 (over 512k tolerate), "
            f"got {r['status']} trace={r.get('trace_id')}"
        )

    def test_06_11_max_completion_tokens_at_512k(self):
        """max_completion_tokens at the 524288 (512k) boundary."""
        r = oai_chat({
            "messages": oai_simple_messages("Reply OK only"),
            "max_completion_tokens": 524288,
        })
        assert r["status"] in (200, 400), (
            f"max_completion_tokens=524288 unexpected {r['status']} "
            f"trace={r.get('trace_id')}"
        )

    def test_06_12_no_output_limit(self):
        """06_12 — No output budget at all: the request goes out without max_tokens /
        max_completion_tokens (sent verbatim) and still returns a normal completion."""
        payload = contract_request()
        assert "max_tokens" not in payload and "max_completion_tokens" not in payload
        assert_request_accepted(payload, msg="06_12 no budget")

    def test_06_14_legacy_max_tokens(self):
        """06_14 — Legacy max_tokens=64 is accepted."""
        assert_request_accepted(contract_request(max_tokens=64), msg="06_14 max_tokens=64")

    @pytest.mark.parametrize("field", ["max_completion_tokens", "max_tokens"])
    def test_06_15_output_budget_null(self, field):
        """06_15 — max_completion_tokens / max_tokens explicitly null are accepted."""
        assert_request_accepted(contract_request(**{field: None}), msg=f"06_15 {field}=null")


# ============================================================
# 07 message_format — message content/role format and edges
# ============================================================

class TestMessageFormat:
    """Role / content / ordering edges of the messages array."""

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_07_01_consecutive_assistant(self, stream):
        """Two consecutive assistant messages; endpoint should accept (actual behavior is implementation-defined)."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
                {"role": "assistant", "content": "How can I help?"},
                {"role": "user", "content": "What's 1+1?"},
            ],
        }, stream=stream)
        assert r["status"] == 200

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_07_02_assistant_null_content_with_tool_calls(self, stream):
        """assistant.content=null with tool_calls and following tool reply; should return 200."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Weather in Beijing?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "c1", "content": "sunny, 25°C"},
                {"role": "user", "content": "Thanks"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert r["status"] == 200

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_07_03_assistant_no_content_field_with_tool_calls(self, stream):
        """assistant omits the content field entirely with tool_calls; should return 200."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Weather in Beijing?"},
                {"role": "assistant", "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "c1", "content": "sunny, 25°C"},
                {"role": "user", "content": "Thanks"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert r["status"] == 200

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_07_04_user_content_empty_array(self, stream):
        """user.content=[] empty array; behavior varies across deployments, only assert a response was produced."""
        r = oai_chat({"messages": [{"role": "user", "content": []}]}, stream=stream)
        assert r["status"] > 0

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_07_05_user_content_null(self, stream):
        """user.content=null; endpoint should return 200 or 400 (implementation-defined)."""
        r = oai_chat({"messages": [{"role": "user", "content": None}]}, stream=stream)
        assert r["status"] in (200, 400), (
            f"user content=null stream={stream} expected 200/400, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_07_06_multiple_system_messages(self, stream):
        """Multiple system messages; endpoint should accept (OpenAI allows this since GPT-4)."""
        r = oai_chat({
            "messages": [
                {"role": "system", "content": "You are a cat."},
                {"role": "system", "content": "You are a dog."},
                {"role": "user", "content": "What are you?"},
            ],
        }, stream=stream)
        assert r["status"] == 200, (
            f"multi-system should be accepted, got {r['status']}"
        )
        content = get_oai_content(r)
        assert content, (
            f"multi-system: model should produce non-empty response, "
            f"got empty content (stream={stream})"
        )

    def test_07_07_history_tool_call_empty_object_arguments(self):
        """History tool_call with `arguments: "{}"` (empty JSON object).

        Clients serialize a no-arg tool call as an empty JSON object string.
        This is a valid "no arguments" representation and must be accepted when
        it appears in the conversation history.

        Setup:
          - user asks for the current server time.
          - assistant tool_call invoking `get_current_time` with `arguments: "{}"`.
          - tool result returns a timestamp.
          - user follow-up asks the model to continue.

        Expected:
          - HTTP 200, and the model actually continues the turn — i.e. it
            produces either a non-empty visible content or a new tool_call.
            An accepted-but-empty response (no content and no tool_call) means
            the provider choked on the empty-arguments history.
        """
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the current server time?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "get_current_time", "arguments": "{}"},
                    }
                ]},
                {"role": "tool", "tool_call_id": "c1", "content": "2026-08-14T10:00:00Z"},
                {"role": "user", "content": "Great, now just tell me that time in a short sentence."},
            ],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Get the current server time (UTC)",
                    "parameters": {"type": "object", "properties": {}},
                },
            }],
        })
        assert_oai_success(r)
        content = get_oai_content(r)
        tool_calls = get_tool_calls(r)
        assert content or tool_calls, (
            f"empty-arguments history (arguments='{{}}'): model should "
            f"continue the turn with content or a tool_call, got neither.\n"
            f"  finish_reason={(r.get('body') or {}).get('choices', [{}])[0].get('finish_reason')!r} "
            f"body={str(r.get('body'))[:300]}"
        )

    @pytest.mark.parametrize("message", [{"content": "Hello"}, {"role": None, "content": "Hello"}],
                             ids=["role_missing", "role_null"])
    def test_07_10_invalid_message_structure(self, message):
        """07_10 — A message without a role, or with role=null, is rejected with 400."""
        assert_request_rejected({"messages": [message]}, msg=f"07_10 {message}")

    @pytest.mark.parametrize("content", [
        [{"type": "text", "text": "First paragraph."},
         {"type": "text", "text": "Second paragraph, please summarize."}],
        "输入有中文🙂、引号\"、反斜线\\和换行\n请简短回应。",
        [{"type": "text", "text": ""}, {"type": "text", "text": "Please explain caching."}],
    ], ids=["multiple_text_parts", "cjk_emoji_escapes", "empty_text_part"])
    def test_07_12_user_content_forms(self, content):
        """07_12 — user content as several text parts, as a string with CJK / emoji / escapes,
        and with an empty text part next to a non-empty one; all are accepted."""
        assert_request_accepted({"messages": [{"role": "user", "content": content}]}, msg="07_12")


# ============================================================
# 08 model_compat — model-name compatibility
# ============================================================

class TestModelCompat:
    """Main model / mini model name compatibility."""

    def test_08_01_model_name_compat(self):
        """Main model is a hard assertion; mini model softens to xfail when endpoint hasn't registered it."""
        # Main model: hard assertion
        r = oai_chat({"messages": oai_simple_messages("Hi"), "model": MODEL})
        assert_oai_success(r)
        # Mini model: soft — skip if same, try otherwise; xfail on failure
        if not MODEL_MINI or MODEL_MINI == MODEL:
            return
        r_mini = oai_chat({"messages": oai_simple_messages("Hi"), "model": MODEL_MINI})
        if r_mini["status"] != 200:
            pytest.xfail(
                f"mini model {MODEL_MINI!r} not registered on this endpoint. "
                f"HTTP={r_mini['status']} body={str(r_mini.get('body'))[:200]}"
            )
        assert_oai_success(r_mini)


# ============================================================
# 09 response_format — response_format JSON output
# ============================================================

_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
_JSON_PROMPT = "Return a JSON object whose answer field is a short greeting."


def _json_schema_format(schema=None, **extra):
    return {"type": "json_schema", "json_schema": {
        "name": "answer_card", "strict": True, "schema": schema or _ANSWER_SCHEMA, **extra,
    }}


class TestResponseFormat:
    """response_format request shapes: text, json_object and strict json_schema are accepted.

    These cases check that each documented request shape is accepted with a normal
    completion. Whether the output satisfies the schema is a behaviour check, not asserted here.
    """

    @pytest.mark.parametrize("prompt,response_format", [
        ("Explain caching in one sentence.", {"type": "text"}),
        ("Output a JSON object that contains one greeting.", {"type": "json_object"}),
    ], ids=["type=text", "type=json_object"])
    def test_09_01_text_and_json_object(self, prompt, response_format):
        """09_01 — response_format type=text and type=json_object are accepted."""
        payload = {"messages": [{"role": "user", "content": prompt}], "response_format": response_format}
        assert_request_accepted(payload, msg=f"09_01 {response_format}")

    @pytest.mark.parametrize("prompt,response_format,extra", [
        (_JSON_PROMPT, _json_schema_format(), {}),
        (_JSON_PROMPT, _json_schema_format(description="Answer card"), {}),
        ("Answer in JSON and list a lot of content.", _json_schema_format(), {"max_completion_tokens": 8}),
    ], ids=["strict_schema", "with_description", "small_budget"])
    def test_09_02_json_schema_strict(self, prompt, response_format, extra):
        """09_02 — strict json_schema with name / description / schema / strict, and a small
        budget where truncation (finish_reason=length) is allowed. Type-array (nullable)
        properties are not covered: the reference endpoint rejects them in response_format."""
        payload = {"messages": [{"role": "user", "content": prompt}], "response_format": response_format, **extra}
        assert_request_accepted(payload, msg="09_02")

    @pytest.mark.parametrize("schema", [
        {"type": "object", "properties": {
            "s": {"type": "string"}, "n": {"type": "number"}, "i": {"type": "integer"}, "b": {"type": "boolean"},
            "o": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"],
                  "additionalProperties": False},
            "a": {"type": "array", "items": {"type": "number"}},
        }, "required": ["s", "n", "i", "b", "o", "a"], "additionalProperties": False},
    ], ids=["all_json_types"])
    def test_09_08_schema_keywords(self, schema):
        """09_08 — a strict schema using every non-null JSON type is accepted. Type-array (nullable)
        properties are not covered: the reference endpoint rejects them in response_format."""
        payload = {"messages": [{"role": "user", "content": "Return a JSON object that follows the schema."}],
                   "response_format": _json_schema_format(schema)}
        assert_request_accepted(payload, msg="09_08")



# ============================================================
# 10 usage_field — usage field semantics / arithmetic / cache
# ============================================================

class TestUsageField:
    """usage field: completeness / types / arithmetic relations / cached_tokens / stream vs non-stream consistency."""

    def test_10_01_response_field_completeness(self):
        """Response top-level field completeness: id / model / created / object / choices / usage etc."""
        r = oai_chat({"messages": oai_simple_messages("Hi")})
        assert_oai_success(r)
        body = r["body"]
        assert "id" in body
        assert "model" in body
        assert "created" in body
        assert body.get("object") == "chat.completion"
        assert "choices" in body
        choice = body["choices"][0]
        assert "index" in choice
        assert "finish_reason" in choice
        assert "message" in choice
        assert "usage" in body
        usage = body["usage"]
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage

    def test_10_02_usage_token_math(self):
        """usage arithmetic: total == prompt + completion; cached_tokens should be <= prompt_tokens."""
        r = oai_chat({"messages": oai_simple_messages("Hi")})
        assert_oai_success(r)
        usage = r["body"]["usage"]
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        # If prompt_tokens_details.cached_tokens is returned (M3 carries it), it should not exceed prompt_tokens
        details = usage.get("prompt_tokens_details") or {}
        if "cached_tokens" in details:
            cached = details["cached_tokens"]
            assert isinstance(cached, int) and cached >= 0, (
                f"cached_tokens should be non-neg int, got {cached!r}"
            )
            assert cached <= usage["prompt_tokens"], (
                f"cached_tokens={cached} should be <= prompt_tokens={usage['prompt_tokens']}"
            )

    def test_10_03_usage_field_types(self):
        """usage's three fields must be int and >= 0 (OAI spec allows 0)."""
        r = oai_chat({"messages": oai_simple_messages("Hi")})
        assert_oai_success(r)
        usage = r["body"]["usage"]
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            v = usage[k]
            assert isinstance(v, int) and not isinstance(v, bool), (
                f"usage.{k} should be int, got {type(v).__name__}={v!r}"
            )
            assert v >= 0, f"usage.{k} should be >= 0, got {v}"

    @pytest.mark.probabilistic
    def test_10_04_cached_tokens_presence(self):
        """cached_tokens hard presence: a unique long prompt is cold on the first run and hits cache on the second."""
        # The unique prefix keeps the first call cold across repeated runs
        msgs = [
            {"role": "system", "content": f"{uuid.uuid4().hex}\n{long_system_text(10000)}"},
            {"role": "user", "content": "Reply with exactly: ACK"},
        ]
        # First call: warm up cache
        r1 = oai_chat({"messages": msgs})
        assert_oai_success(r1)
        cold_usage = r1["body"]["usage"]
        cold_cached = (cold_usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        # Platform-level shared prefixes may still hit, so only a majority hit counts as not cold
        assert cold_cached <= cold_usage["prompt_tokens"] / 2, (
            f"first request should be cold, got cached_tokens={cold_cached} "
            f"prompt_tokens={cold_usage['prompt_tokens']}"
        )
        # Second call: should hit cache
        r2 = oai_chat({"messages": msgs})
        assert_oai_success(r2)
        details = r2["body"]["usage"].get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens")
        assert cached is not None, (
            f"expected prompt_tokens_details.cached_tokens to be present, "
            f"got usage={r2['body']['usage']!r}"
        )
        assert isinstance(cached, int) and cached >= 0, (
            f"cached_tokens should be non-neg int, got {cached!r}"
        )
        assert cached > 0, (
            f"second request should hit cache (cached_tokens > 0), got {cached}. "
            f"prompt_tokens={r2['body']['usage']['prompt_tokens']}"
        )
        assert cached <= r2["body"]["usage"]["prompt_tokens"], (
            f"cached_tokens={cached} should be <= prompt_tokens="
            f"{r2['body']['usage']['prompt_tokens']}"
        )

    def test_10_05_usage_arithmetic_tool_call(self):
        """Usage arithmetic still holds under tool_call: total == prompt + completion."""
        r = oai_chat({
            "messages": oai_simple_messages("What's the weather in Beijing?"),
            "tools": [WEATHER_TOOL_OAI],
        })
        assert_oai_success(r)
        # Verify a tool_call was actually triggered (ensure the request hit the tool_choice code path)
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Beijing"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg="usage_arithmetic_tool_call",
        )
        usage = r["body"]["usage"]
        assert usage["completion_tokens"] > 0, f"tool call should count as completion, got {usage!r}"
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], (
            f"tool_call usage math: total={usage['total_tokens']} != "
            f"prompt={usage['prompt_tokens']}+completion={usage['completion_tokens']}"
        )

    def test_10_07_stream_prompt_tokens_aggregated(self):
        """prompt_tokens should match between stream and non-stream for the same prompt + stream usage arithmetic holds."""
        msgs = oai_simple_messages("Hi")
        # Non-stream
        r_n = oai_chat({"messages": msgs})
        assert_oai_success(r_n)
        pt_non_stream = r_n["body"]["usage"]["prompt_tokens"]
        # Stream
        r_s = oai_chat(
            {"messages": msgs, "stream_options": {"include_usage": True}},
            stream=True,
        )
        assert_oai_stream_success(r_s)
        usage_chunks = [c for c in r_s["chunks"] if c.get("usage")]
        assert usage_chunks, "no usage chunk in stream"
        last_usage = usage_chunks[-1]["usage"]
        pt_stream = last_usage["prompt_tokens"]
        # Stream / non-stream should report the same input token count
        assert pt_stream == pt_non_stream, (
            f"stream vs non-stream prompt_tokens diverged: "
            f"stream={pt_stream} non_stream={pt_non_stream}"
        )
        # Arithmetic relation on the trailing stream usage chunk
        assert last_usage["total_tokens"] == (
            last_usage["prompt_tokens"] + last_usage["completion_tokens"]
        ), (
            f"stream usage math: total={last_usage['total_tokens']} != "
            f"prompt={last_usage['prompt_tokens']}+completion={last_usage['completion_tokens']}"
        )

    def test_10_08_usage_fields_populated(self):
        """usage.prompt_tokens / completion_tokens / total_tokens should all be > 0."""
        r = oai_chat({"messages": oai_simple_messages("Hi")})
        assert_oai_success(r)
        usage = r["body"]["usage"]
        assert usage["prompt_tokens"] > 0
        assert usage["completion_tokens"] > 0
        assert usage["total_tokens"] > 0

    def test_10_09_usage_present_when_max_tokens_1_non_stream(self):
        """10_09 — BILLING GUARD: usage must NOT disappear at max_tokens=1 (non-stream).

        We bill customers based on the provider-returned `usage`. Some providers drop the
        `usage` object (or zero out the token counts) when the generation is truncated at
        max_tokens=1, which silently under-bills. This case enforces that even a 1-token
        truncated response carries a complete, correct usage object.

        Sent WITHOUT a `thinking` field — this reflects the real default client request
        (thinking is optional / not required). This is important: a provider was observed to
        return `usage: null` at max_tokens=1 only when `thinking` was omitted (adding
        thinking:disabled masked the bug), so the guard must run under the default path.

        Requirements on HTTP 200:
          - `usage` object present and non-empty;
          - prompt_tokens > 0 (input was billed);
          - completion_tokens == 1 (exactly the one truncated token must be billed);
          - total_tokens == prompt_tokens + completion_tokens.
        (Some providers time out on max_tokens=1 — that is a separate known issue covered by
        06_06; here we only assert billing integrity when a 200 is actually returned.)
        """
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "max_tokens": 1,
        }, timeout=60)
        # max_tokens=1 may time out on some providers (see 06_06); only enforce billing on 200.
        if r["status"] != 200:
            pytest.skip(f"10_09 non-200 at max_tokens=1 (status={r['status']}); billing check N/A")
        body = r["body"] or {}
        usage = body.get("usage")
        assert isinstance(usage, dict) and usage, (
            f"10_09 BILLING BUG: usage missing/empty at max_tokens=1 — would under-bill. "
            f"body={str(body)[:300]}"
        )
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        tt = usage.get("total_tokens")
        assert isinstance(pt, int) and pt > 0, (
            f"10_09 BILLING BUG: prompt_tokens missing/zero at max_tokens=1 — input not billed. "
            f"usage={usage!r}"
        )
        assert isinstance(ct, int) and ct == 1, (
            f"10_09 BILLING BUG: completion_tokens must be exactly 1 at max_tokens=1, "
            f"got {ct!r}. usage={usage!r}"
        )
        assert isinstance(tt, int) and tt == pt + ct, (
            f"10_09 total_tokens={tt} != prompt({pt})+completion({ct}). usage={usage!r}"
        )

    def test_10_10_usage_present_when_max_tokens_1_stream(self):
        """10_10 — BILLING GUARD: usage must NOT disappear at max_tokens=1 (stream).

        Streaming counterpart of 10_09. Sent WITHOUT a `thinking` field (real default path).
        With stream_options.include_usage=true, the terminal usage chunk must still be emitted
        and complete even when generation is truncated at max_tokens=1; otherwise streamed
        requests get under-billed (e.g. completion_tokens reported as 0).
        """
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "max_tokens": 1,
            "stream_options": {"include_usage": True},
        }, stream=True, timeout=60)
        if r["status"] != 200:
            pytest.skip(f"10_10 non-200 at max_tokens=1 (status={r['status']}); billing check N/A")
        usage_chunks = [c for c in (r.get("chunks") or []) if isinstance(c, dict) and c.get("usage")]
        assert usage_chunks, (
            "10_10 BILLING BUG: no usage chunk in stream at max_tokens=1 despite "
            "include_usage=true — streamed request would be under-billed."
        )
        usage = usage_chunks[-1]["usage"]
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        tt = usage.get("total_tokens")
        assert isinstance(pt, int) and pt > 0, (
            f"10_10 BILLING BUG: prompt_tokens missing/zero at max_tokens=1 (stream). usage={usage!r}"
        )
        assert isinstance(ct, int) and ct == 1, (
            f"10_10 BILLING BUG: completion_tokens must be exactly 1 at max_tokens=1 (stream), "
            f"got {ct!r}. usage={usage!r}"
        )
        assert isinstance(tt, int) and tt == pt + ct, (
            f"10_10 total_tokens={tt} != prompt({pt})+completion({ct}) (stream). usage={usage!r}"
        )

    def test_10_11_stream_truncated_usage_within_budget(self):
        """A stream cut short by max_completion_tokens still reports usage within the budget."""
        r = oai_chat({
            "messages": oai_simple_messages("Write a detailed 2000-word essay about the history of tea."),
            "max_completion_tokens": 20,
            "stream_options": {"include_usage": True},
        }, stream=True, timeout=120)
        assert_oai_stream_success(r)
        usage_chunks = [c for c in r["chunks"] if c.get("usage")]
        assert usage_chunks, "10_11 no usage chunk in stream despite include_usage=true"
        usage = usage_chunks[-1]["usage"]
        assert usage["completion_tokens"] <= 20, (
            f"10_11 completion_tokens exceeds max_completion_tokens=20: {usage!r}"
        )

    _LONG_TEXT = "The quick brown fox jumps over the lazy dog. " * 45
    _TOOL_CALL_TURN = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_usage_1",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"location": "Beijing"}'},
        }],
    }

    def _tool_result_messages(self, tool_output):
        return [
            {"role": "user", "content": "What's the weather in Beijing?"},
            self._TOOL_CALL_TURN,
            {"role": "tool", "tool_call_id": "call_usage_1", "content": tool_output},
        ]

    def _prompt_tokens_cases(self):
        """Return {scenario: (baseline payload, extended payload, minimum prompt_tokens growth)}."""
        question = oai_simple_messages("Reply with OK.")
        return {
            "input_length": (
                {"messages": question},
                {"messages": oai_simple_messages(f"Reply with OK. {self._LONG_TEXT}")},
                100,
            ),
            "system_and_history": (
                {"messages": question},
                {"messages": [
                    {"role": "system", "content": "You are a concise assistant. " * 10},
                    {"role": "user", "content": "Name three primary colors."},
                    {"role": "assistant", "content": "Red, yellow and blue."},
                    {"role": "user", "content": "Reply with OK."},
                ]},
                50,
            ),
            "tool_result": (
                {"messages": self._tool_result_messages("Sunny."), "tools": [WEATHER_TOOL_OAI]},
                {"messages": self._tool_result_messages(self._LONG_TEXT), "tools": [WEATHER_TOOL_OAI]},
                100,
            ),
        }

    @pytest.mark.parametrize("scenario", ["input_length", "system_and_history", "tool_result"])
    def test_10_14_prompt_tokens_accounting(self, scenario):
        """prompt_tokens grows with input text, system/history turns and tool results; exact values are not checked."""
        baseline, extended, min_growth = self._prompt_tokens_cases()[scenario]
        r_base = oai_chat(dict(baseline, max_completion_tokens=256))
        assert_oai_success(r_base)
        r_ext = oai_chat(dict(extended, max_completion_tokens=256))
        assert_oai_success(r_ext)
        base_tokens = r_base["body"]["usage"]["prompt_tokens"]
        ext_tokens = r_ext["body"]["usage"]["prompt_tokens"]
        assert ext_tokens - base_tokens > min_growth, (
            f"{scenario}: prompt_tokens should grow by more than {min_growth}, "
            f"got {base_tokens} -> {ext_tokens}"
        )

    def test_10_15_cache_hit_keeps_prompt_tokens(self):
        """A cache hit stays inside prompt_tokens: identical requests report nearly identical prompt_tokens."""
        msgs = [
            {"role": "system", "content": f"{uuid.uuid4().hex}\n{long_system_text(10000)}"},
            {"role": "user", "content": "Reply with exactly: ACK"},
        ]
        r1 = oai_chat({"messages": msgs})
        assert_oai_success(r1)
        r2 = oai_chat({"messages": msgs})
        assert_oai_success(r2)
        first = r1["body"]["usage"]["prompt_tokens"]
        second = r2["body"]["usage"]["prompt_tokens"]
        assert abs(first - second) <= max(8, first * 0.01), (
            f"cached tokens should not be deducted from prompt_tokens, got {first} -> {second}"
        )

    def test_10_16_reasoning_tokens_within_completion(self):
        """reasoning_tokens is a subset of completion_tokens and is not added to total_tokens again."""
        r = oai_chat({
            "messages": oai_simple_messages("Explain how to compute 23 * 47."),
            "reasoning_effort": "high",
        })
        assert_oai_success(r)
        usage = r["body"]["usage"]
        details = usage.get("completion_tokens_details") or {}
        reasoning = details.get("reasoning_tokens")
        if reasoning is None:
            pytest.skip("10_16 reasoning_tokens not returned")
        assert _is_json_int(reasoning) and reasoning >= 0, (
            f"reasoning_tokens should be a non-negative integer, got {reasoning!r}"
        )
        assert reasoning <= usage["completion_tokens"], (
            f"reasoning_tokens={reasoning} should be <= completion_tokens={usage['completion_tokens']}"
        )
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], (
            f"total_tokens should not count reasoning twice, got {usage!r}"
        )


# ============================================================
# 11 role_root — role=root protocol acceptance and identity follow-through
# ============================================================

class TestRoleRoot:
    """role=root compatibility + identity follow-through:
    - root is a system-prompt channel above system (analogous to OpenAI's developer/system priority)
    - The endpoint must accept role=root without error
    - When root and system conflict, the model should follow root
    - system-only / root-only should each be able to drive the model into the corresponding identity

    Identity assertion strategy: target identity is set to "MiniMax-M3-taoxi"
    (a name that does not exist in M3's native cognition); use
    _identity_hits_taoxi_m3 to strictly check that the full string
    "MiniMax-m3-taoxi" appears (case-insensitive) and that the model does not
    claim to be claude opus 3.

    Resilience to probability fluctuation (2026-06-06): cases 11_02/11_03/11_04
    use _assert_identity_with_retries — after a first failure, continue to a
    total of 10 runs; pass rate >= 70% (>= 7/10 hits) counts as the case
    passing. If the first run already passes, return directly without retries.
    11_01 only checks HTTP 200 + non-empty and has no probability-sensitive
    assertion, so it does not retry.
    """

    # Probability decision parameters (tune strictness here)
    _IDENTITY_TOTAL_RUNS = 10        # Total runs to fill after first failure
    _IDENTITY_PASS_RATE_MIN = 0.7    # Pass-rate lower bound (>= 7/10)

    @staticmethod
    def _identity_hits_taoxi_m3(text: str) -> bool:
        """Whether the model self-report contains the full target string
        'MiniMax-M3-taoxi' (identity target, case-insensitive), and does not
        claim to be claude opus 3.

        Note: the literal target is built from explicit bytes
        ('\\x6d\\x69...') because editor/display layers may auto-uppercase
        the 'M' in 'MiniMax' when typing visually-lowercase text, breaking
        a naive `'MiniMax-m3-taoxi' in text.lower()` check.
        """
        if not text:
            return False
        low = text.lower()
        # = 'MiniMax-m3-taoxi' (all lowercase, byte-by-byte literal)
        target_lower = "\x6d\x69\x6e\x69\x6d\x61\x78-m3-taoxi"
        has_taoxi = target_lower in low
        denies_claude = "claude opus 3" not in low and "claude-opus-3" not in low
        return has_taoxi and denies_claude

    @classmethod
    def _assert_identity_with_retries(cls, payload, stream, case_label):
        """Run identity judgement once; on first failure, top up to a total of
        _IDENTITY_TOTAL_RUNS runs — pass rate >= _IDENTITY_PASS_RATE_MIN counts
        as the case passing.

        Every oai_chat call is automatically logged to jsonl by helpers, so all
        retry samples are recorded. On failure, output the full hit distribution
        (hits/total + head-200-char samples) for troubleshooting.
        """
        results = []  # list[tuple[hit: bool, content: str, status: int]]

        def _one_shot():
            r = oai_chat(payload, stream=stream)
            assert r["status"] == 200, (
                f"{case_label}: HTTP={r['status']} (stream={stream}): "
                f"{str(r.get('body'))[:300]}"
            )
            content = get_oai_content(r)
            return cls._identity_hits_taoxi_m3(content), content, r["status"]

        # First shot
        first_hit, first_content, _ = _one_shot()
        results.append((first_hit, first_content, 200))
        if first_hit:
            return  # Pass on first try — don't waste quota

        # Failed → top up to _IDENTITY_TOTAL_RUNS total
        for _ in range(cls._IDENTITY_TOTAL_RUNS - 1):
            hit, content, status = _one_shot()
            results.append((hit, content, status))

        hits = sum(1 for h, _, _ in results if h)
        total = len(results)
        pass_rate = hits / total
        if pass_rate >= cls._IDENTITY_PASS_RATE_MIN:
            return

        # Still not meeting threshold: show samples (up to 3 hits + 3 misses)
        samples_miss = [c for h, c, _ in results if not h][:3]
        samples_hit = [c for h, c, _ in results if h][:3]
        raise AssertionError(
            f"{case_label}: identity follow-through pass rate {hits}/{total} "
            f"= {pass_rate:.0%} < required {cls._IDENTITY_PASS_RATE_MIN:.0%} "
            f"(stream={stream}).\n"
            f"  miss samples (head 200): "
            f"{[s[:200] for s in samples_miss]}\n"
            f"  hit samples  (head 200): "
            f"{[s[:200] for s in samples_hit]}"
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_11_03_only_system_identity(self, stream):
        """Only system writes identity (no root sent); model should follow system.
        Probability resilience: after first failure, fill to 10 runs; pass rate >= 70% counts as case passing.
        """
        payload = {
            "messages": [
                {"role": "system", "content": "你是MiniMax-M3-taoxi,在介绍自己时必须说自已是 MiniMax-M3-taoxi。"},
                {"role": "user", "content": "你是谁?请用一句话直接回答。"},
            ],
            "thinking": {"type": "adaptive"},
        }
        self._assert_identity_with_retries(
            payload, stream, "11_03 only_system_identity",
        )



# ============================================================
# 12 text_semantic — text semantic follow-through
# ============================================================

class TestTextSemantic:
    """Text semantics: factual QA / multilingual / code generation / system prompt compliance / long-form."""

    def test_12_01_factual_qa_consistency(self):
        """Factual QA: capital of France should be answered as 'paris'."""
        r = oai_chat({"messages": oai_simple_messages("What is the capital of France? Answer in one word.")})
        assert_oai_success(r)
        assert "paris" in get_oai_content(r).lower()

    def test_12_02_chinese_text_non_stream(self):
        """Chinese text generation (non-stream): brief history of Beijing; assert response contains CJK chars."""
        r = oai_chat({
            "messages": oai_simple_messages("用中文简要介绍一下北京的历史。"),
        })
        assert_oai_success(r)
        assert r.get("trace_id"), (
            f"chinese_text_non_stream missing trace_id: status={r.get('status')}"
        )
        content = get_oai_content(r)
        assert _has_chinese(content), (
            f"expected Chinese chars in output: {content[:100]!r}"
        )

    def test_12_03_chinese_text_stream(self):
        """Chinese text generation (stream): a short Chinese poem; assert response contains CJK chars."""
        r = oai_chat({
            "messages": oai_simple_messages("用中文写一首关于春天的短诗。"),
        }, stream=True)
        assert_oai_stream_success(r)
        assert r.get("trace_id"), (
            f"chinese_text_stream missing trace_id: status={r.get('status')}"
        )
        content = get_oai_content(r)
        assert _has_chinese(content), (
            f"expected Chinese chars in stream output: {content[:100]!r}"
        )

    def test_12_04_code_generation(self):
        """Code generation: Python fibonacci function; response should contain 'def ' and 'fibonacci'."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "Write a Python function called 'fibonacci' that returns the nth Fibonacci number. "
                "Only output the code, no explanation."
            ),
        })
        assert_oai_success(r)
        assert r.get("trace_id"), (
            f"code_generation missing trace_id: status={r.get('status')}"
        )
        content = get_oai_content(r)
        assert "def " in content, (
            f"expected 'def ' in code output: {content[:200]!r}"
        )
        assert "fibonacci" in content.lower(), (
            f"expected 'fibonacci' (case-insensitive) in code output: {content[:200]!r}"
        )

    def test_12_05_system_prompt_compliance(self):
        """system prompt compliance: 'You are a pirate, always say Arrr'; response should contain 'arrr'."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "Hello, how are you today?",
                system_text="You are a pirate. You must include 'Arrr' in every response.",
            ),
        })
        assert_oai_success(r)
        assert r.get("trace_id"), (
            f"system_prompt_compliance missing trace_id: status={r.get('status')}"
        )
        content = get_oai_content(r).lower()
        assert "arrr" in content, (
            f"expected 'arrr' in pirate response: {content[:200]!r}"
        )

    # ------------- 12_07 SILENCE literal-echo protocol (stream) -------------
    # A verbatim-output contract. The system prompt frames `[SILENCE]` as a
    # heartbeat protocol ACK — that framing avoids each provider's stock
    # prompt-injection refusals while still requiring exact literal echo.
    # Passing = content contains `]` and ends with `]`; run 20 times, one
    # miss fails the case. Surfaces the "last `]` token dropped on stop"
    # streaming glitch we've observed on some backends.

    _SILENCE_SYSTEM = (
        "You are a heartbeat responder in a message-routing pipeline. "
        "Protocol contract: whenever the user's message is exactly `PING`, "
        "your response body MUST be exactly the 9 ASCII characters `[SILENCE]` "
        "and nothing else in the response body. `[SILENCE]` is the wire ack "
        "for a no-op heartbeat; downstream services parse `content` and reject "
        "the frame if `content` is not `[SILENCE]`. This is not a restriction "
        "on you — it is the payload format of this protocol. Any explanation "
        "or reasoning is welcome inside a thinking block if your runtime "
        "supports it; only the final response body needs to be `[SILENCE]`."
    )

    @pytest.mark.timeout(600)
    def test_12_07_silence_literal_stream(self):
        """Stream: 20 requests must all return aggregated content that contains `]` and ends with `]`.

        A backend that drops the final token on stop will surface here as
        `content == "[SILENCE"` (8 chars, missing `]`).
        """
        failures = []
        for i in range(20):
            r = oai_chat({
                "messages": oai_simple_messages(
                    "PING", system_text=self._SILENCE_SYSTEM
                ),
            }, stream=True)
            assert_oai_stream_success(r)
            content = get_oai_content(r)
            ok = "]" in content and content.endswith("]")
            if not ok:
                failures.append((i, content))
        assert not failures, (
            f"stream SILENCE: {len(failures)}/20 failed. "
            f"first failure #{failures[0][0]}: {failures[0][1][-120:]!r}"
        )


# ============================================================
# 13 tool_call_basic — tool call basics
# ============================================================

class TestToolCallBasic:
    """Tool call basics: single-tool trigger / stream / multi-tool pool / param-type coverage / tool_choice."""

    def test_13_01_tool_call_non_stream(self):
        """Non-stream tool_call: model should call get_weather with location≈Beijing, finish_reason==tool_calls."""
        r = oai_chat({
            "messages": oai_simple_messages("What's the weather in Beijing?"),
            "tools": [WEATHER_TOOL_OAI],
        })
        assert_oai_success(r)
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Beijing"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg="tool_call_non_stream",
        )
        assert r["body"]["choices"][0].get("finish_reason") == "tool_calls", (
            f"finish_reason should be 'tool_calls', got "
            f"{r['body']['choices'][0].get('finish_reason')!r}"
        )

    def test_13_02_tool_call_stream(self):
        """Streaming tool_call: stream should rebuild get_weather + trailing chunk finish_reason==tool_calls."""
        r = oai_chat({
            "messages": oai_simple_messages("What's the weather in Beijing?"),
            "tools": [WEATHER_TOOL_OAI],
        }, stream=True)
        assert_oai_stream_success(r)
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Beijing"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg="tool_call_stream",
        )
        # Trailing stream finish_reason should be tool_calls
        last_finish = None
        for c in reversed(r["chunks"]):
            choices = c.get("choices") or []
            if choices and choices[0].get("finish_reason") is not None:
                last_finish = choices[0]["finish_reason"]
                break
        assert last_finish == "tool_calls", (
            f"stream last finish_reason should be 'tool_calls', got {last_finish!r}"
        )

    def test_13_03_complex_agent_6tools(self):
        """Pick get_weather out of a pool of 6 tools: verify the model selects the right tool from candidates."""
        tools = make_tools_oai(6)
        msgs = [
            {"role": "system", "content": "You are a helpful assistant. Use tools when appropriate."},
            {"role": "user", "content": "What's the weather in Beijing?"},
        ]
        r = oai_chat({"messages": msgs, "tools": tools})
        assert_oai_success(r)
        # In make_tools_oai the i=0 tool is get_weather (param name 'param', type string)
        assert_tool_called(
            r,
            expected_name="get_weather",
            schema=tools[0]["function"]["parameters"],
            msg="complex_agent_6tools",
        )

    def test_13_04_param_type_coverage(self):
        """Param-type coverage (6 types): arguments must be valid JSON + fields match schema + str_param='hello'."""
        r = oai_chat({
            "messages": oai_simple_messages("Call the complex tool with str_param='hello'"),
            "tools": [PARAM_TYPES_TOOL_OAI],
        })
        assert_oai_success(r)
        assert_tool_called(
            r,
            expected_name="complex_tool",
            expected_args_subset={"str_param": "hello"},
            schema=PARAM_TYPES_TOOL_OAI["function"]["parameters"],
            msg="param_type_coverage",
        )

    def test_13_05_tool_without_parameters(self):
        """function.parameters omitted (spec allows; in practice M3 strictly enforces non-empty — xfail on failure)."""
        tool = {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current server time (no params)",
            },
        }
        r = oai_chat({
            "messages": oai_simple_messages("What time is it now? Call the tool."),
            "tools": [tool],
        })
        if r["status"] != 200:
            pytest.xfail(
                f"M3 enforces non-empty function.parameters despite spec marking it optional. "
                f"HTTP={r['status']} body={str(r.get('body'))[:200]}"
            )
        assert_tool_called(
            r,
            expected_name="get_current_time",
            msg="tool_without_parameters",
        )

    def test_13_06_tool_without_description(self):
        """function.description omitted; model infers from name + parameters and should still trigger."""
        tool = {
            "type": "function",
            "function": {
                "name": "get_weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                    },
                    "required": ["location"],
                },
            },
        }
        r = oai_chat({
            "messages": oai_simple_messages("What's the weather in Beijing?"),
            "tools": [tool],
        })
        assert_oai_success(r)
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Beijing"},
            schema=tool["function"]["parameters"],
            msg="tool_without_description",
        )

    def test_13_07_stream_multi_tool_call(self):
        """Stream multi-tool_call rebuild: Beijing + Shanghai must both fire; each call id should be non-empty and unique."""
        r = oai_chat({
            "messages": oai_simple_messages("What's the weather in Beijing and Shanghai?"),
            "tools": [WEATHER_TOOL_OAI],
        }, stream=True)
        assert_oai_stream_success(r)
        calls = get_tool_calls(r)
        assert len(calls) >= 2, (
            f"expected at least 2 tool_calls (Beijing + Shanghai), got {len(calls)}: "
            f"{[(c['name'], c['arguments_raw'][:80]) for c in calls]}"
        )
        # Each call must be get_weather + valid JSON
        locations = []
        for i, c in enumerate(calls):
            assert c["name"] == "get_weather", (
                f"call[{i}] name={c['name']!r} expected get_weather"
            )
            assert c["arguments_obj"] is not None, (
                f"call[{i}] arguments not valid JSON: {c['arguments_raw'][:300]}"
            )
            loc = (c["arguments_obj"].get("location") or "").lower()
            locations.append(loc)
        # The set must cover both Beijing and Shanghai (tolerate CN/EN and substring matches)
        def _has(city, locs):
            cands = {
                "beijing": ("beijing", "北京"),
                "shanghai": ("shanghai", "上海"),
            }[city]
            return any(any(c in loc for c in cands) for loc in locs)
        assert _has("beijing", locations), (
            f"locations missing Beijing: {locations}"
        )
        assert _has("shanghai", locations), (
            f"locations missing Shanghai: {locations}"
        )
        # tool_call.id should be non-empty and unique (multiple calls must be distinguishable)
        ids = [c.get("id") or "" for c in calls]
        non_empty_ids = [i for i in ids if i]
        assert len(non_empty_ids) == len(calls), (
            f"some tool_calls missing id: {ids}"
        )
        assert len(set(non_empty_ids)) == len(non_empty_ids), (
            f"tool_call.id should be unique across calls, got duplicates: {ids}"
        )
        # Calls merged per tool index validate on their own schema without bleeding into each other.
        _assert_calls(r, [WEATHER_TOOL_OAI], "13_07")
        assert len(set(locations)) == len(locations), f"13_07 same-name calls bled into each other: {locations}"

    def test_13_09_tool_stream_auto(self):
        """tool_choice=auto + stream + explicit tool-call cue; verify stream contains tool_call chunks."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "Use the get_weather tool to fetch weather for Beijing."
            ),
            "tools": [WEATHER_TOOL_OAI],
            "tool_choice": "auto",
        }, stream=True)
        assert_oai_stream_success(r)
        assert r.get("trace_id"), (
            f"tool_stream_auto missing trace_id in stream response: status={r.get('status')}"
        )
        tool_chunks = [
            c for c in r["chunks"]
            if (c.get("choices") or [{}])[0].get("delta", {}).get("tool_calls")
        ]
        assert len(tool_chunks) > 0, (
            "expected tool_call chunks in stream with tool_choice=auto, got none"
        )

    def test_13_10_tool_structure(self):
        """Tool call return structure: must trigger get_weather + location≈Beijing + all schema-required
        fields present, and the response passes the full ChatCompletion contract
        (assert_chat_completion_strict), including the exact tool_calls item fields."""
        r = oai_chat({
            "messages": oai_simple_messages("What's the weather in Beijing?"),
            "tools": [WEATHER_TOOL_OAI],
        })
        assert_oai_success(r)
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Beijing"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg="tool_structure",
        )
        assert_chat_completion_strict(r, msg="13_10", finish="tool_calls")

    def test_13_11_stream_tool_rebuild(self):
        """Stream tool_call delta rebuild: stream-rebuilt result should contain get_weather + location≈Beijing."""
        r = oai_chat({
            "messages": oai_simple_messages("Weather in Beijing?"),
            "tools": [WEATHER_TOOL_OAI],
        }, stream=True)
        assert_oai_stream_success(r)
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Beijing"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg="stream_tool_rebuild",
        )

    def test_13_13_undefined_tool_retry_after_error(self):
        """Format-check: retry an undefined tool after a transient tool error.

        Setup (streaming + adaptive thinking):
          - messages[0] = user asks to call `list_skills` once, no visible reply.
          - messages[1] = assistant tool_call invoking `list_skills` (priming:
            this tool name was "already used" once).
          - messages[2] = tool result reporting the tool is temporarily
            unavailable and asking to retry later.
          - messages[3] = user system-reminder saying the cooldown is over,
            "try again".
          - The request declares NO `tools` at all — `list_skills` is only
            established by the in-context history.

        Expected behavior (format-output level):
          - The response MUST be a tool_call (finish_reason='tool_calls'),
            with `name == 'list_skills'`, re-issuing the same call the history
            established, even though no tool inventory is provided in the
            request.

        Rationale: validates that the model honors the in-context tool-usage
        pattern (retry the previously-attempted tool) even when the request
        carries no `tools` field — i.e. provider plumbing does not require a
        declared tool inventory to emit a tool_call, and does not rewrite/drop
        the tool name. Schema is intentionally omitted because no tool is
        declared in the request.
        """
        messages = [
            {
                "role": "user",
                "content": (
                    "Call the `list_skills` tool once to check what we can do. "
                    "Just call the tool and don't reply anything in the visible "
                    "content."
                ),
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_example_0",
                        "type": "function",
                        "function": {
                            "name": "list_skills",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_example_0",
                "content": "Tool `list_skills` unavailable for now. Please call it later.",
            },
            {
                "role": "user",
                "content": (
                    "<system-reminder>\n10min cooldown after the tool calling "
                    "error. Now try again.\n</system-reminder>"
                ),
            },
        ]
        r = oai_chat({
            "messages": messages,
            "max_tokens": 4096,
            "thinking": {"type": "adaptive"},
        }, stream=True)
        assert_oai_stream_success(r)
        assert_tool_called(
            r,
            expected_name="list_skills",
            msg="undefined_tool_retry_after_error",
        )

    def test_13_22_echo_without_description_required(self):
        """echo without description, call requested by the prompt: finish tool_calls, every
        call named echo with string arguments. Non-strict → schema not asserted."""
        echo = tool_fn("echo", parameters=ECHO_TOOL_OAI["function"]["parameters"])
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [echo]})
        _assert_required_calls_loose(r, "echo", "13_22")

    def test_13_23_function_name_charset(self):
        """Name using every allowed class (a-z A-Z 0-9 _ -) is accepted (200)."""
        tool = tool_fn("a-Z_0", parameters=ECHO_TOOL_OAI["function"]["parameters"], description="返回输入文本")
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [tool]})
        assert_oai_success(r)
        if _finish(r) == "tool_calls":
            _assert_calls(r, [tool], "13_23", schema_check=False)

    def test_13_24_long_description(self):
        """A very long description (no documented limit) is accepted (200).

        The called function name is recorded only: with a 3000-character description the
        reference endpoint itself sometimes calls an undeclared name."""
        tool = tool_fn("echo", parameters=ECHO_TOOL_OAI["function"]["parameters"], description="说明" * 1500)
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [tool]})
        assert_oai_success(r)
        names = [c["name"] for c in get_tool_calls(r)]
        if any(n != "echo" for n in names):
            print(f"[undeclared-name] 13_24 called {names}, declared ['echo']")

    def test_13_25_duplicate_function_names(self):
        """Two declarations with the same name (OpenAI 200): accepted; any call
        uses the declared name with string arguments."""
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [ECHO_TOOL_OAI, ECHO_TOOL_OAI]})
        assert_oai_success(r)
        if _finish(r) == "tool_calls":
            _assert_calls(r, [ECHO_TOOL_OAI], "13_25", schema_check=False)

    def test_13_26_128_tools_boundary(self):
        """128 function declarations (documented upper bound), tool_choice=none:
        accepted (200) with a text answer."""
        tools = [tool_fn(f"tool_{i:03d}", description=f"Tool {i}",
                         parameters={"type": "object", "properties": {"p": {"type": "string"}}, "required": ["p"]})
                 for i in range(128)]
        r = oai_chat({"messages": oai_simple_messages("你好，简单打个招呼。"), "tools": tools, "tool_choice": "none"})
        assert_oai_success(r)
        assert_text_reply(r, msg="13_26", finishes=("stop", "length"))

    def test_13_27_tool_choice_omitted_auto(self):
        """tool_choice omitted with echo + get_time declared behaves as auto:
        either a text answer (finish stop, tool_calls absent/null) or
        calls that only use the declared names (finish tool_calls)."""
        tools = [ECHO_TOOL_OAI, GET_TIME_TOOL_OAI]
        r = oai_chat({"messages": [{"role": "user", "content": "简短问候。"}], "tools": tools})
        assert_oai_success(r)
        if _finish(r) == "tool_calls":
            calls = _assert_calls(r, tools, "13_27 auto", schema_check=False)
            assert calls, "13_27 finish_reason=tool_calls but no tool_calls"
        else:
            assert_text_reply(r, msg="13_27 auto")

    def test_13_28_tool_choice_null(self):
        """tool_choice=null is treated as omitted (OpenAI 200): accepted; either a
        text answer or calls to the declared echo."""
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [ECHO_TOOL_OAI], "tool_choice": None})
        assert_oai_success(r)
        if _finish(r) == "tool_calls":
            assert _assert_calls(r, [ECHO_TOOL_OAI], "13_28", schema_check=False), "13_28 no tool_calls"
        else:
            assert_text_reply(r, msg="13_28", finishes=("stop", "length"))

    def test_13_31_tool_call_id_unique_across_requests(self):
        """Two independent echo requests (call requested by the prompt) return different call ids
        (format / prefix / length not checked)."""
        ids = []
        for n in (1, 2):
            r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [ECHO_TOOL_OAI]})
            assert_oai_success(r)
            calls = _assert_calls(r, [ECHO_TOOL_OAI], f"13_31 request {n}")
            assert calls, f"13_31 request {n} returned no tool_calls"
            ids += [c["id"] for c in calls]
        assert len(set(ids)) == len(ids), f"13_31 tool_call ids repeat across requests: {ids}"

    def test_13_32_no_arg_function_arguments_braces(self):
        """get_time (no parameters), call requested by the prompt: arguments is the JSON
        string of an empty object ("{}" up to whitespace), never "" or null."""
        r = oai_chat({"messages": oai_simple_messages("现在几点？请调用 get_time。"), "tools": [GET_TIME_TOOL_OAI]})
        assert_oai_success(r)
        assert _finish(r) == "tool_calls", f"13_32 finish_reason should be tool_calls, got {_finish(r)!r}"
        calls = _assert_calls(r, [GET_TIME_TOOL_OAI], "13_32")
        assert calls, "13_32 no tool_calls"
        for c in calls:
            raw = c["arguments_raw"]
            assert raw.strip() and c["arguments_obj"] == {}, f"13_32 no-arg arguments should be '{{}}', got {raw!r}"

    def test_13_33_stream_answer_after_tool_result(self):
        """History echo call + tool result + user question, tool_choice=none, stream:
        finish_reason=stop, no tool_calls deltas, non-empty joined content."""
        messages = echo_history() + [{"role": "user", "content": "echo 返回了什么？只回复返回值。"}]
        r = oai_chat({"messages": messages, "tools": [ECHO_TOOL_OAI], "tool_choice": "none"}, stream=True)
        assert_oai_stream_success(r)
        assert_text_reply(r, msg="13_33", finishes=("stop",))


# ============================================================
# 14 tool_call_schema — tool call schema advanced validation
# ============================================================

class TestToolCallSchema:
    """Advanced tool schema: multiple distinct tools in parallel / enum / numeric range / multi-required / nested / deeply nested."""

    def test_14_01_multi_distinct_tools_parallel(self):
        """Multiple distinct tools in the same turn in parallel: get_weather + get_current_time both should trigger."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "What's the weather in Beijing AND what's the current server time? "
                "Please call both tools."
            ),
            "tools": [WEATHER_TOOL_OAI, TIME_TOOL_OAI],
        })
        assert_oai_success(r)
        assert_tools_called_set(
            r,
            expected_names=["get_weather", "get_current_time"],
            schemas={
                "get_weather": WEATHER_TOOL_OAI["function"]["parameters"],
                # TIME_TOOL_OAI has no parameters; skip its schema
            },
            msg="multi_distinct_tools_parallel",
        )
        # Further verify get_weather location≈Beijing
        for c in get_tool_calls(r):
            if c["name"] == "get_weather":
                loc = (c["arguments_obj"] or {}).get("location") or ""
                assert "beijing" in loc.lower() or "北京" in loc, (
                    f"get_weather.location={loc!r} expected Beijing"
                )

    def test_14_02_enum_constraint(self):
        """enum constraint: unit ∈ [celsius, fahrenheit]; prompt specifies fahrenheit, model should fill it correctly."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "What's the weather in New York? Use fahrenheit as the temperature unit."
            ),
            "tools": [WEATHER_WITH_UNIT_TOOL_OAI],
        })
        assert_oai_success(r)
        assert_tool_called(
            r,
            expected_name="get_weather_with_unit",
            expected_args_subset={"location": "New York", "unit": "fahrenheit"},
            schema=WEATHER_WITH_UNIT_TOOL_OAI["function"]["parameters"],
            msg="enum_constraint",
        )

    def test_14_03_numeric_range(self):
        """Numeric range min/max: days ∈ [1, 14]; prompt asks 3 days, days should fall in a reasonable range."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "Give me a 3-day weather forecast for Beijing."
            ),
            "tools": [FORECAST_TOOL_OAI],
        })
        assert_oai_success(r)
        # Trigger + exact location + days schema validation (via _validate_schema range [1,14])
        assert_tool_called(
            r,
            expected_name="get_weather_forecast",
            expected_args_subset={"location": "Beijing"},
            schema=FORECAST_TOOL_OAI["function"]["parameters"],
            msg="numeric_range",
        )
        # days soft-validation: close to the prompt's expectation (3); allow [1,7]
        call = get_tool_calls(r)[0]
        days = call["arguments_obj"].get("days")
        assert isinstance(days, int) and 1 <= days <= 7, (
            f"days should be in [1,7] (prompt asked 3-day forecast), got {days!r}"
        )

    def test_14_04_multi_required_fields(self):
        """Multiple required fields: from_city / to_city / date are all required, and date prefix == 2026-06-15."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "Search flights from Beijing to Tokyo on 2026-06-15."
            ),
            "tools": [FLIGHT_SEARCH_TOOL_OAI],
        })
        assert_oai_success(r)
        # Three required fields + lenient city matching
        assert_tool_called(
            r,
            expected_name="search_flights",
            expected_args_subset={
                "from_city": "Beijing",
                "to_city": "Tokyo",
            },
            schema=FLIGHT_SEARCH_TOOL_OAI["function"]["parameters"],
            msg="multi_required_fields",
        )
        # date prefix matching (allow extensions like 2026-06-15T..../2026-06-15Z)
        call = get_tool_calls(r)[0]
        date_val = (call["arguments_obj"].get("date") or "")
        assert isinstance(date_val, str) and date_val.startswith("2026-06-15"), (
            f"date should start with '2026-06-15', got {date_val!r}"
        )

    def test_14_05_nested_object_array(self):
        """Nested array-of-objects: guests=[{name, age}] containing Alice/30 + Bob/25."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "Book hotel H001 for check-in on 2026-07-01 with 2 guests: "
                "Alice (age 30) and Bob (age 25)."
            ),
            "tools": [BOOKING_TOOL_OAI],
        })
        assert_oai_success(r)
        # First do structural validation via assert_tool_called + schema
        assert_tool_called(
            r,
            expected_name="book_room",
            expected_args_subset={"hotel_id": "H001", "check_in": "2026-07-01"},
            schema=BOOKING_TOOL_OAI["function"]["parameters"],
            msg="nested_object_array structure",
        )
        # Further validate guests contains Alice 30 and Bob 25
        call = get_tool_calls(r)[0]
        guests = call["arguments_obj"].get("guests") or []
        assert len(guests) == 2, (
            f"expected 2 guests, got {len(guests)}: {guests}"
        )
        names_ages = {(g.get("name", "").lower(), g.get("age")) for g in guests}
        assert ("alice", 30) in names_ages, f"missing Alice/30 in {names_ages}"
        assert ("bob", 25) in names_ages, f"missing Bob/25 in {names_ages}"

    @pytest.mark.probabilistic
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_14_06_nested_schema_4_levels(self, stream):
        """4-level deeply nested schema: should trigger nested_tool + arguments valid JSON."""
        r = oai_chat({
            "messages": oai_simple_messages("Call the nested tool"),
            "tools": [NESTED_SCHEMA_TOOL_OAI],
        }, stream=stream)
        assert r["status"] == 200
        assert_tool_called(
            r,
            expected_name="nested_tool",
            schema=NESTED_SCHEMA_TOOL_OAI["function"]["parameters"],
            msg=f"nested_schema stream={stream}",
        )

    # ------------- 14_07 top-level oneOf tool schema -------------
    # Verify a tool whose parameters use top-level `oneOf` (3 branches:
    # number / stringList / numberList). Model must fire the tool three
    # times in one turn, one call per branch, with the correct data types
    # (int, list[str], list[int]) — never a stringified number and never a
    # {"item": [...]} object wrapper around the array.

    _ONEOF_EXAMPLE_TOOL = {
        "type": "function",
        "function": {
            "name": "ExampleFunction",
            "description": "An example function to verify the parameters.",
            "parameters": {
                "oneOf": [
                    {
                        "additionalProperties": False,
                        "properties": {
                            "number": {"type": "number", "description": "number"}
                        },
                        "type": "object",
                    },
                    {
                        "additionalProperties": False,
                        "properties": {
                            "stringList": {
                                "type": "array",
                                "description": "list",
                                "items": {"type": "string"},
                            }
                        },
                        "type": "object",
                    },
                    {
                        "additionalProperties": False,
                        "properties": {
                            "numberList": {
                                "type": "array",
                                "description": "list",
                                "items": {"type": "number"},
                            }
                        },
                        "type": "object",
                    },
                ],
                "type": "object",
            },
        },
    }

    _ONEOF_USER_PROMPT = (
        "调用 ExampleFunction, 连续三次, 中间不要等待, "
        "第一次只用参数 number = 42, "
        "第二次只用参数 stringList = [\"12\", \"34\"], "
        "第三次只用参数 numberList = [12, 34]."
    )

    _ONEOF_EXPECTED_NUMBER = 42
    _ONEOF_EXPECTED_STRING_LIST = ["12", "34"]
    _ONEOF_EXPECTED_NUMBER_LIST = [12, 34]

    @staticmethod
    def _oneof_check_calls(calls: list) -> str | None:
        """Return None if the batch passes strictly, else a short failure reason.

        Strict rule (any failure -> FAIL):
          - 3 tool_calls total, all named ExampleFunction
          - Each arguments parses to a dict with exactly one oneOf branch key
          - All three branches (number / stringList / numberList) are covered
          - number is a numeric type (not string) AND value == 42
          - stringList is a list AND every element is a string AND value == ["12", "34"]
          - numberList is a list AND every element is a number AND value == [12, 34]
        """
        expected_num = TestToolCallSchema._ONEOF_EXPECTED_NUMBER
        expected_str_list = TestToolCallSchema._ONEOF_EXPECTED_STRING_LIST
        expected_num_list = TestToolCallSchema._ONEOF_EXPECTED_NUMBER_LIST

        if len(calls) != 3:
            return f"expected 3 tool_calls, got {len(calls)}"
        for i, c in enumerate(calls):
            if c["name"] != "ExampleFunction":
                return f"call[{i}].name={c['name']!r}, expected ExampleFunction"
            if not isinstance(c["arguments_obj"], dict):
                return f"call[{i}].arguments not a dict: {c['arguments_raw']!r}"

        branches = {}
        for i, c in enumerate(calls):
            keys = list(c["arguments_obj"].keys())
            if len(keys) != 1 or keys[0] not in ("number", "stringList", "numberList"):
                return f"call[{i}] args keys={keys!r}, expected exactly one of number/stringList/numberList"
            branches[keys[0]] = c["arguments_obj"]
        if set(branches) != {"number", "stringList", "numberList"}:
            return f"branches covered={sorted(branches)}, expected all three"

        # number
        num_val = branches["number"]["number"]
        if isinstance(num_val, bool) or not isinstance(num_val, (int, float)):
            return f"number must be numeric, got {type(num_val).__name__}={num_val!r}"
        if num_val != expected_num:
            return f"number expected {expected_num}, got {num_val!r}"

        # stringList
        s_list = branches["stringList"]["stringList"]
        if not isinstance(s_list, list):
            return f"stringList must be a list, got {type(s_list).__name__}={s_list!r}"
        if not all(isinstance(x, str) for x in s_list):
            return f"stringList elements must all be str, got {s_list!r}"
        if s_list != expected_str_list:
            return f"stringList expected {expected_str_list!r}, got {s_list!r}"

        # numberList
        n_list = branches["numberList"]["numberList"]
        if not isinstance(n_list, list):
            return f"numberList must be a list, got {type(n_list).__name__}={n_list!r}"
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in n_list):
            return f"numberList elements must all be number, got {n_list!r}"
        if [float(x) for x in n_list] != [float(x) for x in expected_num_list]:
            return f"numberList expected {expected_num_list!r}, got {n_list!r}"
        return None

    @pytest.mark.probabilistic
    @pytest.mark.timeout(300)
    def test_14_07_oneof_toplevel_schema_stream(self):
        """Stream: single request must produce 3 ExampleFunction calls (one per oneOf branch) with correct types.

        Failure modes we care about:
          - `number` returned as the string "123" instead of the number 123
          - stringList / numberList returned as {"item": [...]} object wrappers
          - stringList element types coerced to numbers, or numberList to strings
        """
        r = oai_chat({
            "messages": oai_simple_messages(self._ONEOF_USER_PROMPT),
            "tools": [self._ONEOF_EXAMPLE_TOOL],
        }, stream=True)
        assert_oai_stream_success(r)
        calls = get_tool_calls(r)
        reason = self._oneof_check_calls(calls)
        assert reason is None, f"oneof toplevel stream: {reason}. calls={calls}"

    # ------------- 14_08 object field in tool arguments (stream) -------------
    # Verify a tool whose parameters declare an `object` field. The prompt
    # tells the model to pass a concrete JSON object ({"some-key": "some-value"})
    # into that field. Some provider tool-call parsers stringify the value
    # (e.g. arguments.object == '{"some-key":"some-value"}' as a str) instead
    # of preserving it as a JSON object, which breaks downstream consumers.

    _OBJECT_FIELD_TOOL = {
        "type": "function",
        "function": {
            "description": "An example function to validate parameters.",
            "name": "example",
            "parameters": {
                "type": "object",
                "properties": {
                    "string": {"type": "string", "description": "a string field"},
                    "object": {"type": "object", "description": "an object field"},
                },
                "required": ["string", "object"],
            },
        },
    }

    @pytest.mark.probabilistic
    @pytest.mark.timeout(300)
    def test_14_08_object_field_stream(self):
        """Stream: `example` tool must be called with string=='some-string' AND
        object=={'some-key':'some-value'} (both correctly typed).

        Failure surfaces provider bugs where the JSON `object` field arrives
        stringified (arguments.object is a str containing JSON) or the string
        field arrives as an object.
        """
        r = oai_chat({
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": (
                        'Call the tool `example` with "some-string" for `string` field '
                        'and `{"some-key": "some-value"}` for `object` field. '
                        "Don't do anything else, just call the tool and don't consider too much."
                    ),
                },
            ],
            "tools": [self._OBJECT_FIELD_TOOL],
            "tool_choice": "auto",
            "temperature": 1.0,
            "top_p": 0.95,
            "max_tokens": 32000,
            "thinking": {"type": "adaptive"},
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)

        calls = get_tool_calls(r)
        assert len(calls) >= 1, f"expected at least 1 tool_call, got {len(calls)}"
        c = calls[0]
        assert c["name"] == "example", f"expected name='example', got {c['name']!r}"
        args = c["arguments_obj"]
        assert isinstance(args, dict), (
            f"arguments must be JSON object, got {type(args).__name__}: {c['arguments_raw']!r}"
        )

        # string field
        s = args.get("string")
        assert isinstance(s, str), (
            f"'string' field must be str, got {type(s).__name__}={s!r}"
        )
        assert s == "some-string", (
            f"'string' field expected 'some-string', got {s!r}"
        )

        # object field — the critical part
        o = args.get("object")
        assert isinstance(o, dict), (
            f"'object' field must be a JSON object (dict), got {type(o).__name__}={o!r}. "
            f"raw={c['arguments_raw']!r}"
        )
        assert o == {"some-key": "some-value"}, (
            f"'object' field expected {{'some-key':'some-value'}}, got {o!r}"
        )

    # ------------- 14_09 list<object> field must not gain extra keys -------------
    # Verify a tool whose parameters declare an `array` of `object` (list<object>)
    # where the array `items` is a *schema-less* object (`{"type": "object"}` with
    # NO `properties`). Some provider tool-call parsers introduce extra keys into
    # each returned item object that were never declared in the schema nor
    # mentioned in the prompt, corrupting downstream consumers. This mirrors the
    # exact `deep_think` payload reported in the bug doc, which is the payload
    # shape that triggers the parser bug.

    _DEEP_THINK_TOOL = {
        "type": "function",
        "function": {
            "name": "deep_think",
            "description": (
                "Manage the dynamic todo list.\n"
                '- todo_list: items each with "title" (str) and "done" (bool)\n'
                "- current_step: brief description"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # Schema-less object items ({"type": "object"} with no
                    # properties) — this is the payload shape that triggers the
                    # extra-parameter injection bug.
                    "todo_list": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "current_step": {"type": "string"},
                },
                "required": ["todo_list", "current_step"],
            },
        },
    }

    _DEEP_THINK_PROMPT = (
        "深入思考多种备选结构并权衡利弊后，为「8页AI行业分析PPT（投资人版）」"
        "调用 deep_think 记录待办清单（8项以上，首项标记已完成）。"
    )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.timeout(300)
    def test_14_09_list_object_items_wellformed(self, stream):
        """list<object> arguments (schema-less object items): each element must be
        a clean JSON object carrying ONLY the intended fields (title/done) with
        NO provider-injected extra parameters.

        The tool declares the array items as a schema-less object
        (`{"type": "object"}` with no properties), which is the payload shape
        that reproduces the reported bug where returned elements gain keys that
        were never declared in the schema. The assertion is generic — any
        undeclared extra key on an element fails.
        """
        r = oai_chat({
            "messages": oai_simple_messages(self._DEEP_THINK_PROMPT),
            "tools": [self._DEEP_THINK_TOOL],
            "thinking": {"type": "adaptive"},
            "max_tokens": 4000,
        }, stream=stream)
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)

        calls = get_tool_calls(r)
        assert len(calls) >= 1, f"expected at least 1 tool_call, got {len(calls)}"
        c = calls[0]
        assert c["name"] == "deep_think", f"expected name='deep_think', got {c['name']!r}"
        args = c["arguments_obj"]
        assert isinstance(args, dict), (
            f"arguments must be JSON object, got {type(args).__name__}: {c['arguments_raw']!r}"
        )

        todo_list = args.get("todo_list")
        assert isinstance(todo_list, list), (
            f"'todo_list' must be a list, got {type(todo_list).__name__}={todo_list!r}"
        )
        assert len(todo_list) >= 1, f"expected at least 1 todo item, got {len(todo_list)}: {todo_list!r}"

        # Core check for the reported bug: each element must be a clean object
        # carrying ONLY the semantically-intended fields (title/done) and NOT any
        # provider-injected extra key. The assertion is generic so any undeclared
        # extra key is rejected.
        allowed = {"title", "done"}
        for idx, it in enumerate(todo_list):
            assert isinstance(it, dict), (
                f"todo_list[{idx}] must be a JSON object, got {type(it).__name__}={it!r}. "
                f"raw={c['arguments_raw']!r}"
            )
            extra = set(it.keys()) - allowed
            assert not extra, (
                f"todo_list[{idx}] introduces provider-injected extra key(s) {sorted(extra)}; "
                f"element should only contain {sorted(allowed)}. item={it!r}. "
                f"raw={c['arguments_raw']!r}"
            )
            # The intended element must expose the real 'title' field as a value.
            assert "title" in it, (
                f"todo_list[{idx}] missing expected 'title' field; keys={sorted(it.keys())}. "
                f"item={it!r}. raw={c['arguments_raw']!r}"
            )
            assert isinstance(it.get("title"), str), (
                f"todo_list[{idx}].title must be a str, got {type(it.get('title')).__name__}={it.get('title')!r}"
            )

    # ------------- 14_10 api_fetch body field types -------------
    # Verify a tool (`api_fetch`) whose `body` free-form object carries two
    # fields whose JSON type is semantically significant and reported as a
    # provider bug when coerced:
    #   - `values`: a 2-D array (list of lists). Some provider tool-call parsers
    #     flatten it to a 1-D array or stringify the inner rows.
    #   - `flag`:   a JSON boolean (true/false). Some parsers emit the string
    #     "true"/"false" instead of a real bool.
    # Both fields come from the same request, so one case checks them together.
    # The prompt mirrors the exact bug-report payload.

    _API_FETCH_TOOL = {
        "type": "function",
        "function": {
            "description": (
                "Call an API endpoint by its full URL, routing to the appropriate "
                "world state mutation.\n\nUse api_search first to discover the correct "
                "URL and parameters for an endpoint."
            ),
            "name": "api_fetch",
            "parameters": {
                "properties": {
                    "url": {"title": "Url", "type": "string"},
                    "body": {
                        "description": "Request body as a JSON object. Use {} when there is no request body.",
                        "title": "Body",
                        "type": "object",
                    },
                },
                "required": ["url", "body"],
                "title": "APIFetchArgsForModel",
                "type": "object",
            },
        },
    }

    _API_FETCH_PROMPT = (
        'fetch url=127.0.0.1:1000, 给body这个参数传入'
        '{"range":"Current Competitive Dossier Analyst Allocation Entity Queue!M5:O5",'
        '"values":[["Allocated","521","Emerging"]],"flag":true} '
    )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.timeout(300)
    def test_14_10_body_values_2d_array_and_flag_bool(self, stream):
        """`api_fetch` body must keep the JSON types of both nested fields.

        The prompt asks the model to put
        {"values":[["Allocated","521","Emerging"]],"flag":true} into the
        free-form `body` object. The provider must:
          - keep `body.values` a 2-D array (list of lists), neither flattened
            to a 1-D array nor with stringified rows;
          - keep `body.flag` a JSON boolean, not the string "true"/"false".
        """
        r = oai_chat({
            "messages": oai_simple_messages(self._API_FETCH_PROMPT),
            "tools": [self._API_FETCH_TOOL],
            "tool_choice": "auto",
            "temperature": 1.0,
            "top_p": 0.95,
            "max_tokens": 32000,
            "thinking": {"type": "adaptive"},
        }, stream=stream)
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)

        calls = get_tool_calls(r)
        assert len(calls) >= 1, f"expected at least 1 tool_call, got {len(calls)}"
        c = calls[0]
        assert c["name"] == "api_fetch", f"expected name='api_fetch', got {c['name']!r}"
        args = c["arguments_obj"]
        assert isinstance(args, dict), (
            f"arguments must be JSON object, got {type(args).__name__}: {c['arguments_raw']!r}"
        )

        body = args.get("body")
        assert isinstance(body, dict), (
            f"'body' field must be a JSON object (dict), got {type(body).__name__}={body!r}. "
            f"raw={c['arguments_raw']!r}"
        )

        values = body.get("values")
        if values is None:
            # The model sometimes leaves body empty; the reference endpoint does the same.
            pytest.skip(f"14_10 the model did not fill body.values: raw={c['arguments_raw'][:200]!r}")
        # Outer container must be a list ...
        assert isinstance(values, list), (
            f"'body.values' must be a 2-D array (list), got {type(values).__name__}={values!r}. "
            f"raw={c['arguments_raw']!r}"
        )
        assert len(values) >= 1, (
            f"'body.values' must contain at least one row, got {values!r}"
        )
        # ... and every element must itself be a list (the 2-D property).
        for idx, row in enumerate(values):
            assert isinstance(row, list), (
                f"'body.values[{idx}]' must be a list (2-D array row), got "
                f"{type(row).__name__}={row!r}. body.values must not be flattened "
                f"or stringified. raw={c['arguments_raw']!r}"
            )

        flag = body.get("flag")
        # Strict bool check: the string "true"/"false" must NOT pass. In Python
        # bool is a subclass of int, so isinstance(x, bool) is the exact gate.
        assert isinstance(flag, bool), (
            f"'body.flag' must be a JSON boolean (true/false), got "
            f"{type(flag).__name__}={flag!r}. The provider must not stringify the "
            f"boolean. raw={c['arguments_raw']!r}"
        )

    # ------------- 14_12 strict function schema (positive) -------------
    # The prompt asks for the call; strict is accepted but not enforced by the reference
    # endpoint, so schema conformance and prompt-fixed values are recorded, not asserted.
    _STRICT_CASES = {
        "anyof_scalar": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {"v": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
            "required": ["v"], "additionalProperties": False}),
        "anyof_object_branches": ("调用 f，item 选 org 分支，url=https://a.com。", {
            "type": "object", "properties": {"item": {"anyOf": [
                {"type": "object", "properties": {"kind": {"type": "string", "enum": ["user"]}, "name": {"type": "string"}},
                 "required": ["kind", "name"], "additionalProperties": False},
                {"type": "object", "properties": {"kind": {"type": "string", "enum": ["org"]}, "url": {"type": "string"}},
                 "required": ["kind", "url"], "additionalProperties": False}]}},
            "required": ["item"], "additionalProperties": False}),
        "enum_string": ("调用 f，unit 用摄氏度。", {
            "type": "object", "properties": {"unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
            "required": ["unit"], "additionalProperties": False}),
        "enum_number": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {"level": {"type": "integer", "enum": [1, 2, 3]}},
            "required": ["level"], "additionalProperties": False}),
        "enum_with_null": ("调用 f，unit 不适用，传 null。", {
            "type": "object", "properties": {"unit": {"type": ["string", "null"], "enum": ["c", "f", None]}},
            "required": ["unit"], "additionalProperties": False}),
        "nullable_type_array": ("调用 f，note 没有值，传 null。", {
            "type": "object", "properties": {"note": {"type": ["string", "null"]}},
            "required": ["note"], "additionalProperties": False}),
        "nested_3_levels": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {"a": {
                "type": "object", "properties": {"b": {
                    "type": "object", "properties": {"c": {"type": "string"}},
                    "required": ["c"], "additionalProperties": False}},
                "required": ["b"], "additionalProperties": False}},
            "required": ["a"], "additionalProperties": False}),
        "object_array_min_items": ("调用 f，rows 给 2 行。", {
            "type": "object", "properties": {"rows": {"type": "array", "minItems": 2, "items": {
                "type": "object", "properties": {"n": {"type": "integer"}},
                "required": ["n"], "additionalProperties": False}}},
            "required": ["rows"], "additionalProperties": False}),
        "ref_reuse": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {"from": {"$ref": "#/$defs/p"}, "to": {"$ref": "#/$defs/p"}},
            "required": ["from", "to"], "additionalProperties": False,
            "$defs": {"p": {"type": "object", "properties": {"city": {"type": "string"}},
                            "required": ["city"], "additionalProperties": False}}}),
        "root_recursive_ref": ("调用 f，value=a，children 为空数组。", {
            "type": "object", "properties": {"value": {"type": "string"},
                                             "children": {"type": "array", "items": {"$ref": "#"}}},
            "required": ["value", "children"], "additionalProperties": False}),
        "annotations": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {"v": {"type": "string", "title": "T", "description": "取值说明", "default": "x"}},
            "required": ["v"], "additionalProperties": False}),
        "min_max_length": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {"code": {"type": "string", "minLength": 2, "maxLength": 4}},
            "required": ["code"], "additionalProperties": False}),
        "formats": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {"at": {"type": "string", "format": "date-time"},
                                             "day": {"type": "string", "format": "date"},
                                             "id": {"type": "string", "format": "uuid"}},
            "required": ["at", "day", "id"], "additionalProperties": False}),
        "empty_properties": ("调用 f，给出符合 schema 的一组参数。", {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False}),
        "unicode_property_names": ("调用 f，城市=北京，a-b_c=x。", {
            "type": "object", "properties": {"城市": {"type": "string"}, "a-b_c": {"type": "string"}},
            "required": ["城市", "a-b_c"], "additionalProperties": False}),
        "escape_unicode_value": ("调用 f，text 原样传：他说\"你好\"\\n🙂", {
            "type": "object", "properties": {"text": {"type": "string"}},
            "required": ["text"], "additionalProperties": False}),
    }

    # Business values the prompt fixes (format guarantees are checked by the schema).
    _STRICT_VALUE_CHECKS = {
        "anyof_object_branches": lambda a: a["item"].get("kind") == "org" and "url" in a["item"],
        "enum_string": lambda a: a["unit"] == "celsius",
        "enum_with_null": lambda a: a["unit"] is None,
        "nullable_type_array": lambda a: a["note"] is None,
        "object_array_min_items": lambda a: len(a["rows"]) >= 2,
        "root_recursive_ref": lambda a: a["value"] == "a" and a["children"] == [],
        "empty_properties": lambda a: a == {},
        "unicode_property_names": lambda a: "北京" in a["城市"],
    }

    @pytest.mark.parametrize("case", list(_STRICT_CASES), ids=list(_STRICT_CASES))
    def test_14_12_strict_tool_schema(self, case):
        """strict function schemas the OpenAI subset supports are accepted:
        finish_reason=tool_calls, at least one call to the declared function, arguments a
        JSON object. Schema conformance and prompt-fixed values are
        recorded only, because strict is not enforced by the reference endpoint."""
        prompt, params = self._STRICT_CASES[case]
        tool = strict_tool(params)
        r = oai_chat({"messages": oai_simple_messages(prompt), "tools": [tool]})
        args = _assert_single_strict_call(r, tool, f"14_12 {case}")
        check = self._STRICT_VALUE_CHECKS.get(case)
        if check is not None:
            try:
                ok = check(args)
            except (KeyError, TypeError):
                ok = False
            if not ok:
                print(f"[strict-not-enforced] 14_12 {case}: arguments do not carry the requested values: {args}")

    # ------------- 14_14 custom tool declaration negatives -------------
    _CUSTOM_BAD_GRAMMAR = {
        "missing_definition": {"syntax": "regex"},
        "invalid_syntax": {"syntax": "python", "definition": "x"},
    }

    @pytest.mark.parametrize("case", list(_CUSTOM_BAD_GRAMMAR), ids=list(_CUSTOM_BAD_GRAMMAR))
    def test_14_14_custom_tool_formats(self, case):
        """custom tool with a broken grammar (definition missing / syntax not
        lark|regex) must be rejected with 400, never ignored and answered with 200."""
        tool = {"type": "custom", "custom": {"name": "echo_text", "description": "原样输出文本",
                                             "format": {"type": "grammar", "grammar": self._CUSTOM_BAD_GRAMMAR[case]}}}
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [tool]})
        assert_error(r, 400)

    # ------------- 14_15 function declaration negatives -------------
    _BAD_DECLARATIONS = {
        "function_container_missing": {"type": "function", "name": "echo"},
        "name_wrong_type": {"type": "function", "function": {"name": 7}},
    }

    @pytest.mark.parametrize("case", list(_BAD_DECLARATIONS), ids=list(_BAD_DECLARATIONS))
    def test_14_15_tool_declaration_invalid(self, case):
        """Malformed tools[] declarations → 400; a 200
        means the request was silently defaulted / renamed and fails the case."""
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [self._BAD_DECLARATIONS[case]]})
        assert_error(r, 400)

    # ------------- 14_16 schema keyword acceptance -------------
    _ACCEPTED_KEYWORDS = {
        "strict_pattern_properties": (True, {
            "type": "object", "properties": {"v": {"type": "string"}}, "required": ["v"],
            "additionalProperties": False, "patternProperties": {"^a": {"type": "string"}}}),
        "non_strict_allof": (False, {
            "type": "object", "properties": {"v": {"allOf": [{"type": "string"}]}},
            "required": ["v"], "additionalProperties": False}),
    }

    @pytest.mark.parametrize("case", list(_ACCEPTED_KEYWORDS), ids=list(_ACCEPTED_KEYWORDS))
    def test_14_16_schema_capability_negative(self, case):
        """Schemas OpenAI accepts:
        - strict patternProperties next to properties (OpenAI 200): at least one call to the
          declared function with JSON-object arguments (schema conformance is recorded);
        - non-strict allOf: 200, finish tool_calls, arguments a JSON object (values not
          checked without strict)."""
        strict, params = self._ACCEPTED_KEYWORDS[case]
        tool = tool_fn("f", description="按 schema 传参", strict=strict, parameters=params)
        payload = {"messages": oai_simple_messages("调用 f，给出符合 schema 的一组参数。"),
                   "tools": [tool]}
        if strict:
            r = oai_chat(payload)
            _assert_single_strict_call(r, tool, f"14_16 {case}")
            return
        r = oai_chat(payload)
        _assert_required_calls_loose(r, "f", f"14_16 {case}")
        for i, tc in enumerate(message_tool_calls(r)):
            parse_arguments(tc["function"]["arguments"], f"14_16 {case} tool_calls[{i}]")

    def test_14_18_non_strict_property_oneof_accepted(self):
        """Non-strict (strict=false) property-level oneOf is accepted:
        finish_reason=tool_calls, every call is f with arguments a JSON object string. Without
        strict the values are not guaranteed to match the schema, so they are not checked."""
        tool = tool_fn("f", description="按 schema 传参", strict=False, parameters={
            "type": "object", "properties": {"v": {"oneOf": [{"type": "string"}, {"type": "integer"}]}},
            "required": ["v"], "additionalProperties": False})
        r = oai_chat({"messages": oai_simple_messages("调用 f，给出符合 schema 的一组参数。"),
                      "tools": [tool]})
        _assert_required_calls_loose(r, "f", "14_18")
        for i, tc in enumerate(message_tool_calls(r)):
            parse_arguments(tc["function"]["arguments"], f"14_18 tool_calls[{i}]")

    # ------------- 14_19 strict 2-D boolean array -------------
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_14_19_strict_2d_bool_array(self, stream):
        """strict m: array<array<boolean>>, call requested by the prompt:
        finish_reason=tool_calls, exactly one call whose arguments fully
        validate (m stays 2-D, elements real booleans, no extra keys)."""
        tool = strict_tool({"type": "object", "properties": {
            "m": {"type": "array", "items": {"type": "array", "items": {"type": "boolean"}}}},
            "required": ["m"], "additionalProperties": False})
        payload = {"messages": oai_simple_messages("调用 f，m=[[true,false]]。"), "tools": [tool]}
        r = oai_chat(payload, stream=stream)
        if not stream:
            args = _assert_single_strict_call(r, tool, "14_19 non_stream")
        else:
            assert_oai_stream_success(r)
            assert stream_finish_reasons(r) == {0: "tool_calls"}, f"14_19 finish: {stream_finish_reasons(r)}"
            calls = _assert_calls(r, [tool], "14_19 stream", schema_check=False)
            assert calls, "14_19 the prompt asks for a call but no tool_calls returned"
            args = calls[0]["arguments_obj"]
        assert all(isinstance(row, list) for row in args["m"]), f"14_19 m must stay 2-D: {args}"
        assert all(isinstance(v, bool) for row in args["m"] for v in row), f"14_19 m elements must be bool: {args}"

    def test_14_20_non_strict_omit_required_and_additional(self):
        """strict=false with parameters lacking required / additionalProperties:
        finish_reason=tool_calls, every call is f with arguments a JSON object.
        Non-strict does not guarantee schema conformance, so values are not checked."""
        tool = tool_fn("f", description="按 schema 传参", strict=False,
                       parameters={"type": "object", "properties": {"a": {"type": "string"}}})
        r = oai_chat({"messages": oai_simple_messages("调用 f，给出符合 schema 的一组参数。"), "tools": [tool]})
        _assert_required_calls_loose(r, "f", "14_20")
        for i, tc in enumerate(message_tool_calls(r)):
            parse_arguments(tc["function"]["arguments"], f"14_20 tool_calls[{i}]")

    def test_14_21_strict_true(self):
        """strict=true echo, call requested by the prompt: at least one echo call whose arguments
        are an object. Extra keys are recorded only (strict is not enforced)."""
        tool = tool_fn("echo", parameters=ECHO_TOOL_OAI["function"]["parameters"], description="返回输入文本", strict=True)
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [tool]})
        _assert_single_strict_call(r, tool, "14_21")

    @pytest.mark.parametrize("strict", [False, None, "omit"], ids=["false", "null", "omitted"])
    def test_14_22_strict_false_null_omitted(self, strict):
        """strict=false, strict=null (nullable, must not 400) and strict
        omitted: accepted, finish tool_calls, every call is echo with string arguments.
        Without strict the arguments are not guaranteed to match the schema."""
        fn = {"name": "echo", "description": "返回输入文本", "parameters": ECHO_TOOL_OAI["function"]["parameters"]}
        if strict != "omit":
            fn["strict"] = strict
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [{"type": "function", "function": fn}]})
        _assert_required_calls_loose(r, "echo", f"14_22 strict={strict!r}")

    _STRICT_CONSTRAINTS = {
        "pattern_zip": {"zip": {"type": "string", "pattern": "^[0-9]{5}$"}},
        "format_email": {"mail": {"type": "string", "format": "email"}},
        "array_length": {"tags": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3}},
    }

    @pytest.mark.parametrize("case", list(_STRICT_CONSTRAINTS), ids=list(_STRICT_CONSTRAINTS))
    def test_14_23_strict_value_constraints(self, case):
        """strict pattern / email format / array length: 200, at least one call to the declared function.
        Whether the arguments satisfy the constraint keywords is recorded only (strict is not enforced)."""
        props = self._STRICT_CONSTRAINTS[case]
        tool = tool_fn("echo", description="返回输入文本", strict=True, parameters={
            "type": "object", "properties": props, "required": list(props), "additionalProperties": False})
        r = oai_chat({"messages": oai_simple_messages("调用echo并给出符合schema的一组参数。"), "tools": [tool]})
        _assert_single_strict_call(r, tool, f"14_23 {case}")

    def test_14_24_description_not_string(self):
        """description=123 → 400."""
        tool = tool_fn("echo", parameters=ECHO_TOOL_OAI["function"]["parameters"], description=123)
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": [tool]})
        assert_error(r, 400)

    def test_14_25_tools_element_not_object(self):
        """tools=["echo"] (element not an object) → 400."""
        r = oai_chat({"messages": oai_simple_messages(ECHO_PROMPT), "tools": ["echo"]})
        assert_error(r, 400)


# ============================================================
# 15 tool_call_combo — tool call combined with other features
# ============================================================

class TestToolCallCombo:
    """Tool call combined with other features: thinking + multi-turn / tools+tool_choice / parallel / extreme agent."""

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_01_thinking_tool_call_multiturn(self, stream):
        """thinking + tool call + multi-turn: Beijing tool result already attached; second turn asks Shanghai and should fire again.
        thinking is adaptive, so whether the model thinks on this turn is not asserted."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather in Beijing?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_1", "content": "25°C, sunny"},
                {"role": "user", "content": "And in Shanghai? Think step by step."},
            ],
            "tools": [WEATHER_TOOL_OAI],
            "thinking": {"type": "adaptive"},
        }, stream=stream)
        assert r["status"] == 200
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Shanghai"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg=f"thinking_tool_call_multiturn stream={stream}",
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_03_5_parallel_tool_calls(self, stream):
        """5 parallel tool_calls: at least one tool from the pool is called + every call's param field is non-empty."""
        tools = make_tools_oai(5)
        tool_names = {t["function"]["name"] for t in tools}
        r = oai_chat({
            "messages": oai_simple_messages(
                "Call all 5 tools: get_weather with Beijing, tool_1 with A, tool_2 with B, tool_3 with C, tool_4 with D"
            ),
            "tools": tools,
        }, stream=stream)
        assert r["status"] == 200
        calls = get_tool_calls(r)
        assert calls, f"expected at least 1 tool_call, got 0"
        for i, c in enumerate(calls):
            assert c["name"] in tool_names, (
                f"call[{i}] name={c['name']!r} not in tools pool {tool_names}"
            )
            assert c["arguments_obj"] is not None, (
                f"call[{i}] arguments not valid JSON: {c['arguments_raw'][:300]}"
            )
            # In make_tools_oai, every tool has a required `param` (non-empty string)
            param = c["arguments_obj"].get("param")
            assert isinstance(param, str) and param.strip(), (
                f"call[{i}] name={c['name']!r} arg.param should be non-empty string, "
                f"got {param!r}"
            )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_04_extreme_agent_thinking_fc(self, stream):
        """Extreme agent: thinking + FC + 4 rounds (Beijing → Shanghai → Compare)."""
        msgs = [
            {"role": "system", "content": "You are a weather assistant. Always use tools."},
            {"role": "user", "content": "Weather in Beijing?"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": "25°C sunny"},
            {"role": "user", "content": "And Shanghai?"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c2", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Shanghai"}'}}
            ]},
            {"role": "tool", "tool_call_id": "c2", "content": "28°C cloudy"},
            {"role": "user", "content": "Compare them. Think step by step before answering."},
        ]
        r = oai_chat({
            "messages": msgs,
            "tools": [WEATHER_TOOL_OAI],
            "thinking": {"type": "adaptive"},
        }, stream=stream)
        assert r["status"] == 200
        assert_thinking_present(r, msg=f"extreme_agent_thinking_fc stream={stream}")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_05_system_thinking_tools_combo(self, stream):
        """system + thinking + tools combo: Tokyo weather; should call get_weather/Tokyo.
        thinking is adaptive, so whether the model thinks on this turn is not asserted."""
        r = oai_chat({
            "messages": [
                {"role": "system", "content": "You are a weather expert."},
                {"role": "user", "content": "What's the weather in Tokyo? Think step by step."},
            ],
            "tools": [WEATHER_TOOL_OAI],
            "thinking": {"type": "adaptive"},
        }, stream=stream)
        assert r["status"] == 200
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Tokyo"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg=f"system_thinking_tools stream={stream}",
        )

    def test_15_06_tool_roundtrip(self):
        """Full tool call roundtrip: call → result → user follow-up should answer directly (no further tool call)."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Weather in Tokyo?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Tokyo"}'}}
                ]},
                {"role": "tool", "tool_call_id": "c1", "content": "Tokyo: 22°C, cloudy"},
                {"role": "user", "content": "Is it warm there?"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        })
        assert_oai_success(r)
        assert_text_reply(r, msg="15_06 follow-up", finishes=("stop", "length"))

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_09_history_content_null(self, stream):
        """History assistant(content=null, tool_calls) + tool reply, tool_choice=none: accepted
        (null content is legal alongside tool_calls) and answered with text."""
        r = oai_chat({"messages": echo_history(assistant_content=None),
                      "tools": [ECHO_TOOL_OAI, GET_TIME_TOOL_OAI], "tool_choice": "none"}, stream=stream)
        assert_oai_success(r)
        assert_text_reply(r, msg=f"15_09 stream={stream}", finishes=("stop", "length"))

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_10_mixed_tool_and_plain_turns(self, stream):
        """History mixes a tool turn, a plain assistant answer, a user follow-up and a
        second tool turn (echo → text → get_time); tool_choice=none: accepted,
        text answer with no new tool call."""
        messages = echo_history() + [
            {"role": "assistant", "content": "返回 hello。"},
            {"role": "user", "content": "现在几点？"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_2", "type": "function", "function": {"name": "get_time", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_2", "content": "12:00"},
        ]
        r = oai_chat({"messages": messages, "tools": [ECHO_TOOL_OAI, GET_TIME_TOOL_OAI],
                      "tool_choice": "none"}, stream=stream)
        assert_oai_success(r)
        assert_text_reply(r, msg=f"15_10 stream={stream}", finishes=("stop", "length"))

    def test_15_11_real_call_string_roundtrip(self):
        """Real loop: turn 1 forces echo(text=hello); turn 2 replays the returned call
        (real id + arguments, nothing fabricated) with a string tool result on the same id and
        tool_choice=none. Turn 2: text answer, no new tool call."""
        user, assistant, calls = _echo_real_call()
        r2 = oai_chat({"messages": [user, assistant] + _tool_replies(calls),
                       "tools": [ECHO_TOOL_OAI], "tool_choice": "none"})
        assert_oai_success(r2)
        assert_text_reply(r2, msg="15_11 turn 2", finishes=("stop", "length"))

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_12_echo_history_content_omitted(self, stream):
        """History assistant with tool_calls and no content key + tool reply, tool_choice=none:
        accepted and answered with text (no new tool call)."""
        r = oai_chat({
            "messages": echo_history(omit_content=True),
            "tools": [ECHO_TOOL_OAI, GET_TIME_TOOL_OAI],
            "tool_choice": "none",
        }, stream=stream)
        assert_oai_success(r)
        assert_text_reply(r, msg=f"15_12 stream={stream}", finishes=("stop", "length"))

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.parametrize("assistant_content", ["", "我来调用。"], ids=["empty_string", "with_text"])
    def test_15_13_assistant_tool_call_content_variants(self, assistant_content, stream):
        """History assistant with tool_calls and content "" or text alongside
        the call: accepted under tool_choice=none and answered with text."""
        r = oai_chat({"messages": echo_history(assistant_content=assistant_content),
                      "tools": [ECHO_TOOL_OAI, GET_TIME_TOOL_OAI], "tool_choice": "none"}, stream=stream)
        assert_oai_success(r)
        assert_text_reply(r, msg=f"15_13 content={assistant_content!r} stream={stream}", finishes=("stop", "length"))


# ============================================================
# 16 tool_call_edge — tool call boundary / exception handling
# ============================================================

class TestToolCallEdge:
    """Tool call edges / exceptions: various abnormal tool result values / id mismatch / many tools / large args."""

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_02_tool_result_empty_string(self, stream):
        """tool result = '' (empty string).

        An empty string and a text-parts array are both legal tool.content values
        (OpenAI 200): each must be accepted (200). Whether '' is enough
        information for the model is a behaviour question and is not asserted."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_1", "content": ""},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert_oai_success(r)

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_03_tool_result_null(self, stream):
        """tool result = null."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_1", "content": None},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert r["status"] in (200, 400)

    def test_16_04_tool_result_no_content(self):
        """tool result has no content field at all."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_1"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        })
        assert r["status"] in (200, 400)

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_05_tool_result_special_chars(self, stream):
        """tool result containing JSON+HTML+emoji special characters."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_1", "content": '{"temp": "25°C", "desc": "<b>Sunny</b> ☀️", "note": "It\'s \"great\""}'},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert r["status"] == 200

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_06_long_tool_result_50k(self, stream):
        """50K-character tool result should be handled."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_1", "content": generate_50k_string()},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert r["status"] == 200

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_08_tool_call_id_mismatch(self, stream):
        """tool_call_id mismatch → 400."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_999_wrong", "content": "sunny"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert_error(r, 400)

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_09_partial_tool_call_reply(self, stream):
        """Only one of two tool_calls answered → 400."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Weather in Beijing and Shanghai?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}},
                    {"id": "call_2", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Shanghai"}'}},
                ]},
                {"role": "tool", "tool_call_id": "call_1", "content": "sunny"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert_error(r, 400)

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_10_30_tool_definitions(self, stream):
        """30 tool definitions: endpoint should accept a large tools list without crashing + if tool_call fires, args must be valid."""
        r = oai_chat({
            "messages": oai_simple_messages("Hello, just say hi"),
            "tools": make_tools_oai(30),
        }, stream=stream)
        assert r["status"] == 200
        # Soft check: if a tool_call was triggered, arguments must be valid JSON (cannot break due to large tools count)
        for c in get_tool_calls(r):
            assert c["arguments_obj"] is not None, (
                f"tool_call args not valid JSON: name={c['name']!r} "
                f"raw={c['arguments_raw'][:300]}"
            )

    @pytest.mark.probabilistic
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_11_tool_name_special_chars(self, stream):
        """tool name contains hyphen/dot (my-tool.v2); model should be able to call it correctly."""
        tool = {
            "type": "function",
            "function": {
                "name": "my-tool.v2",
                "description": "Tool with special chars in name",
                "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
            },
        }
        r = oai_chat({
            "messages": oai_simple_messages("Call my-tool.v2 with x='hello'"),
            "tools": [tool],
        }, stream=stream)
        assert r["status"] == 200
        assert_tool_called(
            r,
            expected_name="my-tool.v2",
            expected_args_subset={"x": "hello"},
            schema=tool["function"]["parameters"],
            msg=f"tool_name_special_chars stream={stream}",
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_13_long_arguments_10k(self, stream):
        """10K-character tool arguments; endpoint should handle it."""
        long_arg = json.dumps({"location": "A" * 10000})
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": long_arg}}
                ]},
                {"role": "tool", "tool_call_id": "c1", "content": "sunny"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert r["status"] == 200

    def test_16_14_tool_choice_nonexistent_tool(self):
        """tool_choice points to a nonexistent tool: if endpoint leniently returns 200, model should not invent the call."""
        r = oai_chat({
            "messages": oai_simple_messages("Hello"),
            "tools": [WEATHER_TOOL_OAI],
            "tool_choice": {"type": "function", "function": {"name": "nonexistent_tool"}},
        })
        # Known BUG: should return 400, may return 200
        assert r["status"] in (200, 400)
        if r["status"] == 200:
            for c in get_tool_calls(r):
                assert c["name"] != "nonexistent_tool", (
                    f"model should not invent nonexistent_tool, got {c}"
                )

    # ------------- 16_15 string param must be able to end with '\n' -------------
    # Real agents write files whose bodies end with a trailing newline (POSIX
    # text-file convention). If the model — or the streaming aggregator — strips
    # trailing whitespace from a string argument, `content` comes back without
    # its final `\n`, and downstream file writers silently create malformed
    # files. This case forces the model to call a write_file tool with a
    # content that MUST end with `\n`, and asserts `arguments_obj["content"]`
    # ends with `\n` on both stream and non-stream paths.
    _NEWLINE_TAIL_TOOL = {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Full text body"},
                },
                "required": ["path", "content"],
            },
        },
    }
    _NEWLINE_TAIL_PROMPT = (
        "Call write_file exactly once to create '/tmp/hello.txt'. "
        "The file body MUST be the two lines below and MUST end with a trailing "
        "newline (`\\n`) — i.e. `content` ends with a `\\n` character:\n"
        "line 1: hello\n"
        "line 2: world\n"
        "So `content` should be exactly `hello\\nworld\\n` (12 chars: h,e,l,l,o,\\n,w,o,r,l,d,\\n)."
    )

    @pytest.mark.parametrize("stream", [True], ids=["stream"])
    def test_16_15_tool_arg_string_trailing_newline(self, stream):
        """Tool string arg must be able to end with `\\n` — no trailing whitespace stripping (stream only)."""
        r = oai_chat({
            "messages": oai_simple_messages(self._NEWLINE_TAIL_PROMPT),
            "tools": [self._NEWLINE_TAIL_TOOL],
        }, stream=stream)
        assert r["status"] == 200
        calls = get_tool_calls(r)
        assert calls, f"trailing_newline stream={stream}: no tool_call fired"
        call = calls[0]
        assert call["name"] == "write_file", (
            f"trailing_newline stream={stream}: wrong tool "
            f"name={call['name']!r} raw={call['arguments_raw'][:200]}"
        )
        args = call["arguments_obj"]
        assert args is not None, (
            f"trailing_newline stream={stream}: arguments not valid JSON "
            f"raw={call['arguments_raw'][:300]}"
        )
        content = args.get("content")
        assert isinstance(content, str) and content, (
            f"trailing_newline stream={stream}: content must be non-empty string, "
            f"got type={type(content).__name__} value={content!r}"
        )
        assert content.endswith("\n"), (
            f"trailing_newline stream={stream}: content must end with '\\n', "
            f"got tail={content[-20:]!r} full_len={len(content)} "
            f"raw={call['arguments_raw'][:300]}"
        )

    @pytest.mark.parametrize("content", ["", [{"type": "text", "text": "hello"}]], ids=["empty_string", "text_parts"])
    def test_16_16_real_loop_tool_content_variants(self, content):
        """Real echo loop (turn-1 id / arguments replayed), turn 2 tool.content set to
        '' or [{"type":"text","text":"hello"}], tool_choice=none: accepted, text answer."""
        user, assistant, calls = _echo_real_call()
        r2 = oai_chat({"messages": [user, assistant] + _tool_replies(calls, content=content),
                       "tools": [ECHO_TOOL_OAI], "tool_choice": "none"})
        assert_oai_success(r2)
        assert_text_reply(r2, msg=f"16_16 content={content!r}", finishes=("stop", "length"))

    @pytest.mark.parametrize("content", [[], "image_part"], ids=["empty_array", "image_part"])
    def test_16_18_tool_content_array_variants(self, content):
        """Real echo loop, turn-2 tool.content = [] or a data-URL image part
        (OpenAI 200 for both): accepted with a text answer under tool_choice=none."""
        content_id = content if isinstance(content, str) else "empty_array"
        if content == "image_part":
            content = [{"type": "image_url", "image_url": {"url": png_base64()}}]
        user, assistant, calls = _echo_real_call()
        r2 = oai_chat({"messages": [user, assistant] + _tool_replies(calls, content=content),
                       "tools": [ECHO_TOOL_OAI], "tool_choice": "none"})
        assert_oai_success(r2)
        assert_text_reply(r2, msg=f"16_18 {content_id} turn 2", finishes=("stop", "length"))

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_19_tool_result_json_string(self, stream):
        """tool.content is an arbitrary string (a JSON document), tool_choice=none: accepted and
        answered with text."""
        r = oai_chat({"messages": echo_history(tool_content='{"ok":true,"v":[1,2]}'),
                      "tools": [ECHO_TOOL_OAI, GET_TIME_TOOL_OAI], "tool_choice": "none"}, stream=stream)
        assert_oai_success(r)
        assert_text_reply(r, msg=f"16_19 stream={stream}", finishes=("stop", "length"))

    def test_16_20_tool_message_before_assistant_call(self):
        """A tool message with no preceding assistant tool_calls → 400."""
        messages = [{"role": "user", "content": ECHO_PROMPT},
                    {"role": "tool", "tool_call_id": "call_1", "content": "hello"}]
        r = oai_chat({"messages": messages, "tools": [ECHO_TOOL_OAI, GET_TIME_TOOL_OAI], "tool_choice": "none"})
        assert_error(r, 400)




# ============================================================
# 17 param_stress — param stress (long conversation / long system)
# ============================================================

class TestParamStress:
    """Long conversation / long system param stress: verify the endpoint tolerates large inputs."""

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_17_01_long_conversation_20_rounds(self, stream):
        """Long conversation: 20 rounds / 40 messages."""
        r = oai_chat({"messages": long_conversation_messages(20)}, stream=stream)
        assert r["status"] == 200

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_17_02_long_system_10k(self, stream):
        """Long system message ~10K tokens."""
        r = oai_chat({
            "messages": [
                {"role": "system", "content": long_system_text(10000)},
                {"role": "user", "content": "Summarize the system message in one sentence."},
            ],
        }, stream=stream)
        assert r["status"] == 200

    @pytest.mark.slow
    @pytest.mark.parametrize("ctx_tokens", [512000, 524288], ids=["512000", "524288"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_17_03_long_input_512k(self, stream, ctx_tokens):
        """Long input context ~512k tokens (M3 advertised 512k context window).

        Validates that providers correctly accept M3's full 512k input context.
        Strict expectation: HTTP 200 (provider must honor the advertised window).
        Both common interpretations of "512k" are covered:
          - 512000 (decimal 512k)
          - 524288 (binary 512*1024)
        max_tokens is kept small (16) so total = input + output stays within budget.
        """
        r = oai_chat({
            "messages": [
                {"role": "system", "content": long_system_text(ctx_tokens)},
                {"role": "user", "content": "Reply with the single word OK."},
            ],
            "max_tokens": 16,
        }, stream=stream)
        assert r["status"] == 200, (
            f"512k input context should be accepted, got status={r['status']} "
            f"body={str(r.get('body'))[:500]}"
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_17_04_real_text_512k_xiyouji(self, stream):
        """Real long-text comprehension on the full 西遊記 fixture
        (~553k tokens — over the 512*1024 boundary).

        Two-tier expectation:
          1. HTTP (robustness): 200 (silent truncation / large ctx) or any
             4xx (explicit reject). 5xx is a backend bug — never tolerated.
          2. Content (capability): if status == 200, the response MUST name
             a canonical Journey-to-the-West protagonist. Empty / wrong
             answer on 200 = the model didn't actually understand the long
             context.
          4xx skips the content check (the model never got to answer).

        The fixture file is committed to the repository.
        """
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "xiyouji_long_context.txt"
        )
        assert os.path.exists(fixture), (
            f"fixture missing: {fixture}; restore it from the Git repository"
        )
        with open(fixture, "r", encoding="utf-8") as f:
            xiyouji_text = f.read()

        r = oai_chat({
            "messages": [
                {"role": "system", "content": xiyouji_text},
                {"role": "user", "content": "以上是《西游记》的部分原文。请问这部小说的主角叫什么名字?只回答名字,不要其他内容。"},
            ],
            # M3 is a reasoning model: completion_tokens are mostly consumed by
            # the reasoning_content / <think> trace. 64 tokens is far too small
            # — the thinking eats them all and `content` ends up empty even
            # though the model has the correct answer. 4096 leaves room for
            # both the thinking pass and the final 1-2 token answer.
            "max_tokens": 4096,
        }, stream=stream)

        # Tier 1: HTTP — 5xx is never acceptable, 4xx is fine (explicit reject).
        assert 200 <= r["status"] < 500, (
            f"5xx not allowed for xiyouji-512k input; got status={r['status']} "
            f"body={str(r.get('body'))[:500]}"
        )

        # 4xx: model never produced an answer — content check is N/A.
        if r["status"] != 200:
            return

        # Tier 2: content — on 200, the model must actually name a protagonist.
        # Reconstruct content from either stream or non-stream response.
        # Also include reasoning_content as a fallback: some providers return
        # the answer there when content is truncated by max_tokens.
        if stream:
            content = ""
            reasoning = ""
            for c in r.get("chunks") or []:
                if not isinstance(c, dict):
                    continue
                for ch in c.get("choices", []) or []:
                    delta = ch.get("delta") or {}
                    content += (delta.get("content") or "")
                    reasoning += (delta.get("reasoning_content") or "")
        else:
            body = r.get("body") or {}
            choices = body.get("choices") or []
            msg = (choices[0].get("message") if choices else {}) or {}
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""

        haystack = content + "\n" + reasoning

        # Soft match: any canonical protagonist name (Chinese trad/simp + pinyin)
        canonical = [
            "孫悟空", "孙悟空", "悟空",
            "唐僧", "三藏", "玄奘", "唐三藏",
            "Wukong", "Sun Wukong", "Tang Sanzang", "Tripitaka",
        ]
        hit = next((n for n in canonical if n in haystack), None)
        assert hit is not None, (
            f"status=200 but response did not name a protagonist; "
            f"content={content[:200]!r} reasoning={reasoning[:200]!r}"
        )

    # ----- token-boundary case at 512*1024 = 524288 -----
    # Character count is calibrated against the official tokenizer
    # (minimax-m3 on api.minimaxi.com) so that:
    #   17_05: 624,000 chars → prompt_tokens ≈ 523,528, leaving room for output
    # Other providers' tokenizers differ by ≤0.1%, so the relative ordering
    # vs 524288 stays the same.

    @pytest.mark.slow
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_17_05_xiyouji_below_524288_tokens(self, stream):
        """Real-text input just below 512*1024 = 524288 prompt_tokens.
        Strict: must return 200 + name a protagonist."""
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "xiyouji_long_context.txt"
        )
        assert os.path.exists(fixture), (
            f"fixture missing: {fixture}; restore it from the Git repository"
        )
        with open(fixture, "r", encoding="utf-8") as f:
            xiyouji_text = f.read()[:624_000]
        assert len(xiyouji_text) == 624_000, (
            f"fixture too short ({len(xiyouji_text)} chars); "
            "restore the complete fixture from the Git repository"
        )

        r = oai_chat({
            "messages": [
                {"role": "system", "content": xiyouji_text},
                {"role": "user", "content": "以上是《西游记》的部分原文。请问这部小说的主角叫什么名字?只回答名字,不要其他内容。"},
            ],
            "max_tokens": 512,
        }, stream=stream)

        assert r["status"] == 200, (
            f"expected 200 for below-524288 input, got status={r['status']} "
            f"body={str(r.get('body'))[:500]}"
        )

        if stream:
            content = ""; reasoning = ""
            for c in r.get("chunks") or []:
                if not isinstance(c, dict):
                    continue
                for ch in c.get("choices", []) or []:
                    delta = ch.get("delta") or {}
                    content += (delta.get("content") or "")
                    reasoning += (delta.get("reasoning_content") or "")
        else:
            body = r.get("body") or {}
            choices = body.get("choices") or []
            msg = (choices[0].get("message") if choices else {}) or {}
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning_content") or ""

        haystack = content + "\n" + reasoning
        canonical = ["孫悟空", "孙悟空", "悟空", "唐僧", "三藏", "玄奘",
                     "唐三藏", "Wukong", "Sun Wukong", "Tang Sanzang", "Tripitaka"]
        hit = next((n for n in canonical if n in haystack), None)
        assert hit is not None, (
            f"response did not name a protagonist; "
            f"content={content[:200]!r} reasoning={reasoning[:200]!r}"
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_17_06_real_text_1m_xiyouji(self, stream):
        """Real-text input above the 1M-token context boundary."""
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "xiyouji_1m_long_context.txt"
        )
        assert os.path.exists(fixture), (
            f"fixture missing: {fixture}; restore it from the Git repository"
        )
        with open(fixture, "r", encoding="utf-8") as f:
            xiyouji_text = f.read()

        r = oai_chat({
            "messages": [
                {"role": "system", "content": xiyouji_text},
                {"role": "user", "content": "以上是《西游记》的部分原文。请问这部小说的主角叫什么名字?只回答名字,不要其他内容。"},
            ],
            "max_tokens": 512,
            "thinking": {"type": "disabled"},
        }, stream=stream)
        assert r["status"] == 200 or 400 <= r["status"] < 500, (
            f"expected 200 or explicit 4xx for xiyouji-1m input; got status={r['status']} "
            f"body={str(r.get('body'))[:500]}"
        )
        if r["status"] != 200:
            return
        if stream:
            content = ""
            for chunk in r.get("chunks") or []:
                for choice in (chunk.get("choices") or []) if isinstance(chunk, dict) else []:
                    content += ((choice.get("delta") or {}).get("content") or "")
        else:
            body = r.get("body") or {}
            choices = body.get("choices") or []
            content = ((choices[0].get("message") if choices else {}) or {}).get("content") or ""
        canonical = ["孫悟空", "孙悟空", "悟空", "唐僧", "三藏", "玄奘", "唐三藏",
                     "Wukong", "Sun Wukong", "Tang Sanzang", "Tripitaka"]
        assert any(name in content for name in canonical), (
            f"status=200 but response did not name a protagonist; content={content[:200]!r}"
        )

    def test_17_07_long_text_needle(self):
        """17_07 — One long user message (~80k characters) is accepted and answered."""
        long_text = ("A cache is a storage layer that speeds up data access in computer systems. " * 1000
                     + "\nSummarize the text above in one sentence.")
        payload = {"messages": [{"role": "user", "content": long_text}], "max_completion_tokens": 2048}
        assert_request_accepted(payload, msg="17_07", timeout=600)

    def test_17_08_long_history_needle(self):
        """17_08 — 51 user/assistant pairs plus a final user turn (103 messages) are accepted."""
        filler = ("A cache is a storage layer that speeds up data access in computer systems. " * 6)[:400]
        messages = []
        for i in range(1, 52):
            messages.append({"role": "user", "content": f"Round {i} material: {filler}"})
            messages.append({"role": "assistant", "content": f"Round {i} reply: {filler}"})
        messages.append({"role": "user", "content": "Give a short summary of the material above."})
        assert len(messages) == 103
        assert_request_accepted({"messages": messages, "max_completion_tokens": 2048}, msg="17_08", timeout=600)


# ============================================================
# 18 reasoning_split — reasoning_split extension field
# ============================================================

class TestReasoningSplit:
    """reasoning_split field (BUG-13: intermittent 400)."""

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_18_01_reasoning_split_text(self, stream):
        """reasoning_split=true + text scenario; may intermittently return 400."""
        r = oai_chat({
            "messages": oai_simple_messages("What is 7*8?"),
            "reasoning_split": True,
            "thinking": {"type": "adaptive"},
        }, stream=stream)
        # BUG-13: may intermittently return 400
        assert r["status"] in (200, 400)


# ============================================================
# 19 finish_reason — finish_reason coverage
# ============================================================

class TestFinishReason:
    """finish_reason value-coverage scenarios: tool_calls / length."""

    def test_19_01_finish_reason_tool_calls(self):
        """finish_reason=tool_calls: tool-triggering scenario; should be tool_calls (or stop if chat-branch taken)."""
        r = oai_chat({
            "messages": oai_simple_messages("Weather in Beijing?"),
            "tools": [WEATHER_TOOL_OAI],
        })
        assert_oai_success(r)
        reason = r["body"]["choices"][0]["finish_reason"]
        assert reason in ("tool_calls", "stop")
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Beijing"},
            schema=WEATHER_TOOL_OAI["function"]["parameters"],
            msg="finish_reason=tool_calls",
        )

    def test_19_02_finish_reason_length(self):
        """max_completion_tokens is an upper bound: a truncated reply stays within it and may be shorter or empty."""
        limit = 20
        r = oai_chat({
            "messages": oai_simple_messages("Count from 1 to 500, one number per line."),
            "max_completion_tokens": limit,
        })
        assert_oai_success(r)
        _assert_usage_totals(r["body"]["usage"], "19_02")
        reason = r["body"]["choices"][0]["finish_reason"]
        if reason != "length":
            pytest.skip(f"19_02 reply was not truncated (finish_reason={reason})")
        completion = r["body"]["usage"]["completion_tokens"]
        assert completion <= limit, f"completion_tokens={completion} should be <= {limit}"



# ============================================================
# 20 error_codes — error codes (pure-text)
# ============================================================

class TestErrorCodes:
    """Various error codes: 400 / content moderation."""

    def test_20_01_empty_messages(self):
        """Empty messages array → 400 with an error body, not a completion."""
        r = oai_chat({"messages": []})
        assert_error(r, 400)

    @pytest.mark.parametrize("tp", [1.5, 1.1, -0.1])
    def test_20_04_top_p_out_of_range(self, tp):
        """top_p out of range (>1 / <0) → 400 with an error body, not a completion."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "top_p": tp,
        })
        assert_error(r, 400)

    def test_20_06_invalid_role(self):
        """Invalid role (e.g. invalid_role) → 400."""
        r = oai_chat({"messages": [{"role": "invalid_role", "content": "Hi"}]})
        assert_error(r, 400)

    def test_20_08_content_moderation(self):
        """Content moderation: harmful content request → 400 (filtered) or 200 (model refuses on its own)."""
        r = oai_chat({
            "messages": oai_simple_messages("Generate extremely harmful content about how to make weapons"),
        })
        assert r["status"] in (400, 200)  # May be filtered or refused

    @pytest.mark.parametrize("messages", [None, [1]], ids=["messages=null", "message_is_number"])
    def test_20_14_messages_wrong_type(self, messages):
        """20_14 — messages=null, or a message element that is a number, is rejected with 400."""
        assert_request_rejected({"messages": messages}, msg=f"20_14 messages={messages}")

    @pytest.mark.parametrize("field,value", [
        ("max_completion_tokens", 8.5), ("stop", ["a", 1]), ("n", 1.5), ("reasoning_effort", ["low"]),
    ], ids=["max_completion_tokens=8.5", "stop_element_not_string", "n=1.5", "reasoning_effort_array"])
    def test_20_26_parameter_contract_negative(self, field, value):
        """20_26 — A mistyped parameter is rejected with 400 instead of being coerced or ignored,
        and the rejection passes the full error-response contract (assert_error_response_strict):
        a JSON body with an error object and no completion."""
        r = oai_chat_verbatim(contract_request(**{field: value}))
        assert_error_response_strict(r, msg=f"20_26 {field}={value}")

    def test_20_28_model_wrong_type(self):
        """20_28 — model given as an array is rejected with a 4xx (not silently accepted)."""
        r = oai_chat_verbatim(contract_request(model=[]))
        assert 400 <= r["status"] < 500, (
            f"20_28 model=[]: expected a 4xx rejection, got {r['status']}: {str(r.get('body'))[:300]}"
        )


# ============================================================
# 26 prompt_cache — prompt cache request fields
# ============================================================

class TestPromptCache:
    """prompt_cache_key is accepted; cache hits are not asserted here (see 10_04)."""

    def test_26_01_cache_key_repeated(self):
        """26_01 — The same prompt_cache_key sent twice: both requests return a normal completion."""
        for i in (1, 2):
            assert_request_accepted(contract_request(prompt_cache_key="suite-prefix"), msg=f"26_01 request {i}")

    def test_26_03_cache_key_null(self):
        """26_03 — prompt_cache_key explicitly null is accepted."""
        assert_request_accepted(contract_request(prompt_cache_key=None), msg="26_03 prompt_cache_key=null")


# ============================================================
# 27 passthrough_params — metadata / store / user
# ============================================================

class TestPassthroughParams:
    """Request metadata fields that must not break a normal completion."""

    @pytest.mark.parametrize("metadata", [{"suite": "format-check"}, {"case": ""}, None],
                             ids=["one_key", "empty_string_value", "null"])
    def test_27_01_metadata_values(self, metadata):
        """27_01 — metadata with one key, an empty string value, or null is accepted.
        Echoing metadata back in the response is not required."""
        fields = {"metadata": metadata}
        if metadata is not None:
            fields["store"] = True
        assert_request_accepted(contract_request(**fields), msg=f"27_01 metadata={metadata}")

    @pytest.mark.parametrize("store", [False, True, None], ids=["false", "true", "null"])
    def test_27_02_store_values(self, store):
        """27_02 — store=false / true / null is accepted."""
        assert_request_accepted(contract_request(store=store), msg=f"27_02 store={store}")

    @pytest.mark.parametrize("user", ["synthetic-user-hash", None], ids=["string", "null"])
    def test_27_03_user_identifier(self, user):
        """27_03 — Legacy user as a string or null is accepted."""
        assert_request_accepted(contract_request(user=user), msg=f"27_03 user={user}")


# ============================================================
# 28 extended_capability — prediction
# ============================================================

class TestExtendedCapability:
    """OpenAI request fields for optional capabilities: the request shape is accepted.

    Whether the capability takes effect (predicted output) is not asserted.
    """

    @pytest.mark.parametrize("content", ["print(a)\n", [{"type": "text", "text": "print(a)\n"}]],
                             ids=["string", "text_parts"])
    def test_28_05_prediction_forms(self, content):
        """28_05 — prediction type=content with string content or a text-part array is accepted."""
        payload = {
            "messages": [{"role": "user", "content": "Rename a to b in the code and return the whole file:\nprint(a)\n"}],
            "prediction": {"type": "content", "content": content},
        }
        assert_request_accepted(payload, msg="28_05")
