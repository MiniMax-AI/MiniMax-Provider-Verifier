"""
M3 API Test — pure-text case collection

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

No image / video requests. Modality priority is video > image > text; this file
collects text cases only.

All cases go through helpers.oai_chat() against /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
import json
import os
import re

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


# ============================================================
# 01 basic_text — basic text chat (non-stream)
# ============================================================

class TestBasicText:
    """Basic text chat: validates the minimal usable path of non-stream chat completion."""

    def test_01_01_text_non_stream(self):
        """Most basic non-stream text chat; assert HTTP 200 + non-empty content."""
        r = oai_chat({"messages": oai_simple_messages("What is 1+1?")})
        assert_oai_success(r)
        assert len(get_oai_content(r)) > 0

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
        """SSE terminating [DONE] marker (known to be missing in some implementations; xfail if absent)."""
        r = oai_chat({"messages": oai_simple_messages("Hi")}, stream=True)
        assert_oai_stream_success(r)
        done_chunks = [c for c in r["chunks"] if c.get("_done")]
        if not done_chunks:
            pytest.xfail("Known BUG: SSE stream missing [DONE] marker")

    def test_02_04_stream_chunk_fields(self):
        """Stream chunk required fields: id / choices / object."""
        r = oai_chat({"messages": oai_simple_messages("Hi")}, stream=True)
        assert_oai_stream_success(r)
        for chunk in r["chunks"]:
            if chunk.get("_done") or chunk.get("_raw"):
                continue
            assert "id" in chunk
            assert "choices" in chunk
            assert "object" in chunk

    def test_02_05_text_include_usage(self):
        """stream_options.include_usage=true in text scenario should return a usage chunk."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)

    def test_02_06_stream_usage_only_in_last_chunk(self):
        """stream_options.include_usage=true: usage must be non-empty and only appear in the final stream chunk."""
        r = oai_chat({
            "messages": oai_simple_messages("Say hi"),
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)
        assert_stream_usage_only_in_last_chunk(r, msg="02_06 text include_usage")


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


# ============================================================
# 04 thinking — thinking toggle
# ============================================================

class TestThinking:
    """thinking field: disabled / adaptive / invalid value / combined with streaming."""

    def test_04_01_thinking_disabled(self):
        """thinking.type=disabled: response should not contain any thinking signal."""
        r = oai_chat({
            "messages": oai_simple_messages("Say hello"),
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)
        assert_thinking_absent(r, "thinking=disabled")

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
    """Sampling params: legal values for temperature / top_p / seed."""

    def test_05_01_temperature_values(self):
        """temperature legal range: 0 / 0.5 / 1 / 2 each should return 200."""
        for temp in [0, 0.5, 1, 2]:
            r = oai_chat({
                "messages": oai_simple_messages("Say hi"),
                "temperature": temp,
                "thinking": {"type": "disabled"},
            })
            assert_oai_success(r)

    def test_05_02_top_p(self):
        """top_p boundary values: 0.1 / 0.5 / 0.95 each should return 200."""
        for tp in [0.1, 0.5, 0.95]:
            r = oai_chat({
                "messages": oai_simple_messages("Say hi"),
                "top_p": tp,
                "thinking": {"type": "disabled"},
            })
            assert_oai_success(r)

    def test_05_03_seed_parameter(self):
        """seed parameter + temperature=0; endpoint should accept it for deterministic output."""
        r = oai_chat({
            "messages": oai_simple_messages("Say exactly 'hello world'"),
            "temperature": 0,
            "seed": 42,
            "thinking": {"type": "disabled"},
        })
        assert r["status"] == 200


# ============================================================
# 06 max_tokens — max_tokens / max_completion_tokens boundaries
# ============================================================

class TestMaxTokens:
    """Truncation and boundary behavior for max_tokens / max_completion_tokens."""

    def test_06_01_max_tokens_truncation(self):
        """max_tokens=10 truncation; finish_reason should be length or stop."""
        r = oai_chat({
            "messages": oai_simple_messages("Write a 500-word essay about the ocean"),
            "max_tokens": 10,
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)
        assert r["body"]["choices"][0].get("finish_reason") in ("length", "stop")

    def test_06_02_max_completion_tokens(self):
        """max_completion_tokens alias should be accepted."""
        r = oai_chat({
            "messages": oai_simple_messages("Write a long paragraph"),
            "max_completion_tokens": 20,
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)

    def test_06_03_dual_max_tokens(self):
        """Passing both max_tokens and max_completion_tokens; endpoint should accept it."""
        r = oai_chat({
            "messages": oai_simple_messages("Write a paragraph"),
            "max_tokens": 50,
            "max_completion_tokens": 100,
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)

    @pytest.mark.timeout(600)
    def test_06_04_both_params_combo(self):
        """max_tokens=50 + max_completion_tokens=100 (mct wins semantics)."""
        r = oai_chat({
            "messages": oai_simple_messages("Write a paragraph about the ocean"),
            "max_tokens": 50,
            "max_completion_tokens": 100,
            "thinking": {"type": "disabled"},
        }, timeout=300)
        assert_oai_success(r)

    def test_06_05_mct_only(self):
        """Pass only max_completion_tokens=50; finish_reason should be length/stop."""
        r = oai_chat({
            "messages": oai_simple_messages("Write a long essay about space exploration"),
            "max_completion_tokens": 50,
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)
        assert r["body"]["choices"][0]["finish_reason"] in ("length", "stop")

    def test_06_06_max_tokens_1_timeout(self):
        """max_tokens=1 extreme value (known BUG-4: may time out)."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "max_tokens": 1,
            "thinking": {"type": "disabled"},
        }, timeout=30)
        assert r["status"] in (200, 408), (
            f"max_tokens=1 expected 200/408, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

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

    def test_06_08_max_tokens_negative(self):
        """max_tokens=-1: invalid; expect 4xx reject (returning 200 indicates server-side missing validation, fail)."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "max_tokens": -1,
        })
        assert r.get("trace_id"), (
            f"max_tokens=-1 missing trace_id: status={r.get('status')}"
        )
        assert r["status"] in (400, 422), (
            f"max_tokens=-1 expected 400/422, got {r['status']} trace={r.get('trace_id')}"
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
        assert r.get("trace_id"), (
            f"max_tokens={mt} missing trace_id: status={r.get('status')}"
        )
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
        assert r.get("trace_id"), (
            f"max_completion_tokens=524288 missing trace_id: status={r.get('status')}"
        )
        assert r["status"] in (200, 400), (
            f"max_completion_tokens=524288 unexpected {r['status']} "
            f"trace={r.get('trace_id')}"
        )


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

@pytest.mark.skip(
    reason="minimax-M3 目前不支持 response_format=json_object 参数,整段 §09 暂时跳过,"
           "等 M3 支持后再启用"
)
class TestResponseFormat:
    """response_format=json_object non-stream / stream / known BUG-3 markdown wrap.

    NOTE: minimax-M3 currently does not support response_format; the entire class is
    skipped — see m3_text_cases.md / m3_text_cases_en.md §09 notes.
    """

    def test_09_01_json_object_non_stream(self):
        """response_format=json_object non-stream; content should be a valid JSON dict."""
        r = oai_chat({
            "messages": oai_simple_messages("Return a JSON with key 'answer' and value 42"),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)
        content = get_oai_content(r)
        # BUG-3: may be wrapped in markdown code block
        cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        assert isinstance(parsed, dict)

    def test_09_02_json_object_stream(self):
        """response_format=json_object stream + thinking=disabled; stream should return normally."""
        r = oai_chat({
            "messages": oai_simple_messages("Return JSON with key 'x' value 1"),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }, stream=True)
        assert_oai_stream_success(r)

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_09_03_json_object_format(self, stream):
        """response_format=json_object general validation. BUG-3: if content is wrapped in ```json```, xfail."""
        r = oai_chat({
            "messages": oai_simple_messages("Return JSON: {\"answer\": 42}"),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }, stream=stream)
        assert r["status"] == 200
        if not stream:
            content = get_oai_content(r)
            cleaned = content.strip()
            if cleaned.startswith("```"):
                pytest.xfail("Known BUG-3: json_object wrapped in markdown code block")
            json.loads(cleaned)


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

    def test_10_04_cached_tokens_presence(self):
        """cached_tokens hard presence: run the same long prompt twice; second run should hit cache (cached_tokens > 0)."""
        msgs = [
            {"role": "system", "content": long_system_text(10000)},
            {"role": "user", "content": "Reply with exactly: ACK"},
        ]
        # First call: warm up cache
        r1 = oai_chat({"messages": msgs})
        assert_oai_success(r1)
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
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], (
            f"tool_call usage math: total={usage['total_tokens']} != "
            f"prompt={usage['prompt_tokens']}+completion={usage['completion_tokens']}"
        )

    def test_10_06_length_truncation_completion_equals_limit(self):
        """When finish_reason='length', completion_tokens should strictly equal max_completion_tokens."""
        limit = 20
        r = oai_chat({
            "messages": oai_simple_messages(
                "Write a long essay about space exploration, at least 500 words."
            ),
            "max_completion_tokens": limit,
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)
        finish = r["body"]["choices"][0].get("finish_reason")
        usage = r["body"]["usage"]
        assert finish == "length", (
            f"expected finish_reason='length' with max_completion_tokens={limit}, "
            f"got {finish!r}"
        )
        assert usage["completion_tokens"] == limit, (
            f"completion_tokens should equal max_completion_tokens={limit} "
            f"when finish_reason='length', got {usage['completion_tokens']}"
        )
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"], (
            f"length-truncated usage math: total={usage['total_tokens']} != "
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
    def test_11_01_role_root_accepted(self, stream):
        """Endpoint must accept role=root, returning 200 + non-empty answer (does not require following root content)."""
        r = oai_chat({
            "messages": [
                {"role": "root", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello."},
            ],
            "thinking": {"type": "adaptive"},
        }, stream=stream)
        assert r["status"] == 200, (
            f"role=root should be accepted, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )
        content = get_oai_content(r)
        assert content, (
            f"role=root: model should produce non-empty response, "
            f"got empty content (stream={stream})"
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_11_02_root_overrides_system(self, stream):
        """When root + system identities conflict, the model should follow root (claim to be MiniMax-M3-taoxi).
        Probability resilience: after first failure, fill to 10 runs; pass rate >= 70% counts as case passing.
        """
        payload = {
            "messages": [
                {"role": "root", "content": "你是MiniMax-M3-taoxi,在介绍自己时必须说自已是 MiniMax-M3-taoxi。"},
                {"role": "system", "content": "你是claude opus 3,在介绍自己时必须说自己是claude opus 3。"},
                {"role": "user", "content": "你是谁?请用一句话直接回答。"},
            ],
            "thinking": {"type": "adaptive"},
            "reasoning_split": True,
        }
        self._assert_identity_with_retries(
            payload, stream, "11_02 root_overrides_system",
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

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_11_04_only_root_identity(self, stream):
        """Only root writes identity (no system sent); model should follow root.
        Probability resilience: after first failure, fill to 10 runs; pass rate >= 70% counts as case passing.
        """
        payload = {
            "messages": [
                {"role": "root", "content": "你是MiniMax-M3-taoxi,在介绍自己时必须说自已是 MiniMax-M3-taoxi。"},
                {"role": "user", "content": "你是谁?请用一句话直接回答。"},
            ],
            "thinking": {"type": "adaptive"},
        }
        self._assert_identity_with_retries(
            payload, stream, "11_04 only_root_identity",
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

    @pytest.mark.timeout(600)
    def test_12_06_long_form_output(self):
        """Long-form generation: max_tokens=4096 + detailed photosynthesis explanation; assert content length > 500."""
        r = oai_chat({
            "messages": oai_simple_messages(
                "Write a detailed explanation of how photosynthesis works, including "
                "the light-dependent reactions and the Calvin cycle. Be thorough and "
                "include as much detail as possible."
            ),
            "max_tokens": 4096,
        }, timeout=300)
        assert_oai_success(r)
        assert r.get("trace_id"), (
            f"long_form_output missing trace_id: status={r.get('status')}"
        )
        content = get_oai_content(r)
        assert len(content) > 500, (
            f"expected >500 chars long-form output, got {len(content)}: {content[:200]!r}"
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

    def test_13_08_tool_choice_values(self):
        """tool_choice = none / required / auto branches: none does not trigger, required/auto must trigger."""
        for choice in ["none", "required", "auto"]:
            r = oai_chat({
                "messages": oai_simple_messages("What's the weather in Beijing?"),
                "tools": [WEATHER_TOOL_OAI],
                "tool_choice": choice,
            })
            assert r["status"] == 200, f"tool_choice={choice} HTTP={r['status']}"
            if choice == "none":
                assert_no_tool_called(r, msg=f"tool_choice=none")
            else:
                assert_tool_called(
                    r,
                    expected_name="get_weather",
                    expected_args_subset={"location": "Beijing"},
                    schema=WEATHER_TOOL_OAI["function"]["parameters"],
                    msg=f"tool_choice={choice}",
                )

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
        """Tool call return structure: must trigger get_weather + location≈Beijing + all schema-required fields present."""
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

    def test_13_12_tool_name_mismatch_prompt(self):
        """Format-check: prompt+history demonstrate a tool that is NOT in `tools`.

        Setup:
          - messages[0] = user asks Beijing weather + MUST call `get_weather`.
          - messages[1] = assistant tool_call invoking get_weather/Beijing
            (priming: the model has "already used" this tool name once).
          - messages[2] = tool result "Beijing: 25°C sunny".
          - messages[3] = user follow-up "What's the weather in Shanghai?".
          - `tools` only declares an unrelated `read_file` tool — `get_weather`
            is NOT registered.

        Expected behavior (format-output level):
          - The response MUST be a tool_call (finish_reason='tool_calls'),
            with `name == 'get_weather'` and `arguments.location ≈ Shanghai`,
            following the established pattern from the conversation history,
            regardless of whether the name is in the registered tools list.

        Rationale: validates that the model honors the in-context tool-usage
        pattern over the registered tool inventory — i.e. that provider
        plumbing does not silently rewrite/drop the tool name to match the
        registered list. Schema is intentionally omitted because the invoked
        tool is not in `tools`.
        """
        read_file_tool = {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the content of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                    },
                    "required": ["path"],
                },
            },
        }
        messages = [
            {
                "role": "user",
                "content": (
                    "What's the weather in Beijing? You MUST call the function "
                    "`get_weather` with location='Beijing' to answer. Do not "
                    "reply in natural language."
                ),
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_priming_1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "Beijing"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_priming_1",
                "content": "Beijing: 25°C, sunny",
            },
            {
                "role": "user",
                "content": "What's the weather in Shanghai?",
            },
        ]
        r = oai_chat({
            "messages": messages,
            "tools": [read_file_tool],
        })
        assert_oai_success(r)
        assert_tool_called(
            r,
            expected_name="get_weather",
            expected_args_subset={"location": "Shanghai"},
            msg="tool_name_mismatch_prompt",
        )
        assert r["body"]["choices"][0].get("finish_reason") == "tool_calls", (
            f"finish_reason should be 'tool_calls', got "
            f"{r['body']['choices'][0].get('finish_reason')!r}"
        )


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
    # Verify a tool whose parameters declare an `array` of `object` (list<object>).
    # Each item object strictly declares its own properties with
    # additionalProperties=false. Some provider tool-call parsers (observed on
    # Fireworks) inject extra keys into each item object that were never declared
    # in the schema nor mentioned in the prompt (e.g. echoing the field name, or
    # adding an index/type marker), corrupting downstream consumers.
    #
    # KEY TRIGGER: the array `items` is declared as a *schema-less* object
    # (`{"type": "object"}` with NO `properties`). On Fireworks this reliably
    # reproduces a parser bug where each intended element object
    # `{"title": ..., "done": ...}` is wrapped into a bogus
    # `{"$text": "<stringified JSON of the object>"}`. This mirrors the exact
    # `deep_think` payload reported in the bug doc.

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
                    # Deliberately schema-less object items — this is what
                    # triggers the Fireworks $text wrapping bug.
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

        This directly checks the reported bug: "Fireworks introduces extra
        parameters when handling a list<object> function-call argument." The
        observed manifestation is that each real `{"title": ..., "done": ...}`
        element gets wrapped into `{"$text": "<stringified JSON>"}`, but the
        assertion is generic — any undeclared extra key on an element fails.
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
        # provider-injected extra key. `$text` is just one observed manifestation
        # (the real object gets wrapped into {"$text": "<stringified JSON>"}); the
        # assertion below is generic so any undeclared extra key is rejected.
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
            # The intended element must expose the real 'title' field as a value,
            # never a stringified JSON blob hidden behind an extra key.
            assert "title" in it, (
                f"todo_list[{idx}] missing expected 'title' field; keys={sorted(it.keys())}. "
                f"item={it!r}. raw={c['arguments_raw']!r}"
            )
            assert isinstance(it.get("title"), str), (
                f"todo_list[{idx}].title must be a str, got {type(it.get('title')).__name__}={it.get('title')!r}"
            )

    @staticmethod
    def _find_dollar_text_keys(obj, path="arguments"):
        """Recursively collect JSON paths where a `$text` key appears."""
        hits = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "$text":
                    hits.append(f"{path}.{k}")
                hits.extend(TestToolCallSchema._find_dollar_text_keys(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                hits.extend(TestToolCallSchema._find_dollar_text_keys(v, f"{path}[{i}]"))
        return hits

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.timeout(300)
    def test_14_10_no_injected_dollar_text_field(self, stream):
        """tool-call arguments must not contain an injected `$text` field at any
        depth.

        Reuses the exact `deep_think` payload from the bug report: on Fireworks
        this basically always reproduces, where each element of the schema-less
        `todo_list` array becomes `{"$text": "<stringified JSON>"}`. This case
        recursively scans the parsed arguments and fails if any `$text` key
        appears.
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

        # The critical check: no `$text` key at any depth.
        dollar_hits = self._find_dollar_text_keys(args)
        assert not dollar_hits, (
            f"provider injected bogus `$text` field(s) at {dollar_hits}; "
            f"schema never declares it. args={args!r}. raw={c['arguments_raw']!r}"
        )


# ============================================================
# 15 tool_call_combo — tool call combined with other features
# ============================================================

class TestToolCallCombo:
    """Tool call combined with other features: thinking + multi-turn / tools+tool_choice / parallel / extreme agent."""

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_01_thinking_tool_call_multiturn(self, stream):
        """thinking + tool call + multi-turn: Beijing tool result already attached; second turn asks Shanghai and should fire again."""
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
        assert_thinking_present(r, msg=f"thinking_tool_call_multiturn stream={stream}")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_02_response_format_with_tool_choice(self, stream):
        """tools + tool_choice=auto coexistence (the original response_format was removed since M3 doesn't support it):
        endpoint should not crash + model should take a reasonable path.

        Path A: call get_weather + location≈Beijing
        Path B: content is a JSON-ish string containing the Beijing keyword
        """
        r = oai_chat({
            "messages": oai_simple_messages("What's the weather in Beijing? Return as JSON."),
            "tools": [WEATHER_TOOL_OAI],
            "tool_choice": "auto",
            "thinking": {"type": "disabled"},
        }, stream=stream)
        assert r["status"] == 200
        # Path A: tool was called
        calls = get_tool_calls(r)
        if calls:
            # If tool called, hard-check: name + Beijing + schema
            assert_tool_called(
                r,
                expected_name="get_weather",
                expected_args_subset={"location": "Beijing"},
                schema=WEATHER_TOOL_OAI["function"]["parameters"],
                msg=f"path_A tool_called stream={stream}",
            )
            return
        # Path B: tool not called; model took the JSON-text-reply path
        content = get_oai_content(r)
        assert content.strip(), (
            f"path_B: model went JSON-response route but content empty (stream={stream})"
        )
        # content should be a JSON-ish string (possibly wrapped in ```json``` or raw JSON)
        # At minimum it should contain "Beijing"/"beijing" to prove the model understood the prompt
        assert "beijing" in content.lower() or "北京" in content, (
            f"path_B: JSON content should mention Beijing, got: {content[:300]!r}"
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
        """system + thinking + tools combo: Tokyo weather; should call get_weather/Tokyo."""
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
        assert_thinking_present(r, msg=f"system_thinking_tools stream={stream}")

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


# ============================================================
# 16 tool_call_edge — tool call boundary / exception handling
# ============================================================

class TestToolCallEdge:
    """Tool call edges / exceptions: various abnormal tool result values / id mismatch / many tools / large args."""

    def test_16_01_tool_result_content_object_duplicate(self):
        """tool_result.content as object → 400 (legacy case; overlaps semantically with 16_07, kept for completeness)."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "What's the weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'}}
                ]},
                {"role": "tool", "tool_call_id": "call_1", "content": {"result": "sunny"}},
            ],
            "tools": [WEATHER_TOOL_OAI],
        })
        assert_error(r, 400)

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_16_02_tool_result_empty_string(self, stream):
        """tool result = '' (empty string). Known BUG: may return 400."""
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
        # Known BUG: returns 400
        assert r["status"] in (200, 400)

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
    def test_16_12_invalid_json_arguments(self, stream):
        """tool_calls.arguments is invalid JSON → 400."""
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Weather?"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": "{invalid json}"}}
                ]},
                {"role": "tool", "tool_call_id": "c1", "content": "sunny"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }, stream=stream)
        assert_error(r, 400)

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

    @pytest.mark.slow
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_17_07_xiyouji_below_1048576_tokens(self, stream):
        """Real-text input calibrated below 1M tokens must be accepted."""
        fixture = os.path.join(
            os.path.dirname(__file__), "fixtures", "xiyouji_1m_long_context.txt"
        )
        assert os.path.exists(fixture), (
            f"fixture missing: {fixture}; restore it from the Git repository"
        )
        with open(fixture, "r", encoding="utf-8") as f:
            xiyouji_text = f.read()[:1_220_000]
        assert len(xiyouji_text) == 1_220_000, (
            f"fixture too short ({len(xiyouji_text)} chars); rerun fixture preparation"
        )

        r = oai_chat({
            "messages": [
                {"role": "system", "content": xiyouji_text},
                {"role": "user", "content": "以上是《西游记》的部分原文。请问这部小说的主角叫什么名字?只回答名字,不要其他内容。"},
            ],
            "max_tokens": 512,
            "thinking": {"type": "disabled"},
        }, stream=stream)
        assert r["status"] == 200, (
            f"expected 200 for below-1048576 input, got status={r['status']} "
            f"body={str(r.get('body'))[:500]}"
        )
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
            f"response did not name a protagonist; content={content[:200]!r}"
        )


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
        """finish_reason=length: max_tokens=10 forces truncation."""
        r = oai_chat({
            "messages": oai_simple_messages("Write a very long essay about the universe"),
            "max_tokens": 10,
            "thinking": {"type": "disabled"},
        })
        assert_oai_success(r)
        assert r["body"]["choices"][0]["finish_reason"] in ("length", "stop")


# ============================================================
# 20 error_codes — error codes (pure-text)
# ============================================================

class TestErrorCodes:
    """Various error codes: 400 / 401 / content moderation."""

    def test_20_01_empty_messages(self):
        """Empty messages array → 400."""
        r = oai_chat({"messages": []})
        assert_error(r, 400)

    def test_20_02_invalid_model(self):
        """Invalid model name → 400 or 404 (both count as 4xx client error)."""
        r = oai_chat({"messages": oai_simple_messages("Hi"), "model": "nonexistent-model-xyz"})
        assert r["status"] in (400, 404), (
            f"invalid_model should be rejected with 4xx, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_20_03_temperature_out_of_range(self):
        """temperature out of range (5.0) → 400."""
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "temperature": 5.0,
        })
        assert_error(r, 400)

    def test_20_04_top_p_out_of_range(self):
        """top_p out of range (>1 / <0) → 400."""
        for tp in [1.5, -0.1]:
            r = oai_chat({
                "messages": oai_simple_messages("Hi"),
                "top_p": tp,
            })
            assert_error(r, 400)

    def test_20_05_no_authorization(self):
        """No Authorization header → 401."""
        r = oai_chat(
            {"messages": oai_simple_messages("Hi")},
            headers={"Content-Type": "application/json"},
        )
        assert_error(r, 401)

    def test_20_06_invalid_role(self):
        """Invalid role (e.g. invalid_role) → 400."""
        r = oai_chat({"messages": [{"role": "invalid_role", "content": "Hi"}]})
        assert_error(r, 400)

    def test_20_07_invalid_api_key(self):
        """Invalid API key → 401."""
        r = oai_chat(
            {"messages": oai_simple_messages("Hi")},
            headers={"Authorization": "Bearer sk-invalid-key-12345", "Content-Type": "application/json"},
        )
        assert_error(r, 401)

    def test_20_08_content_moderation(self):
        """Content moderation: harmful content request → 400 (filtered) or 200 (model refuses on its own)."""
        r = oai_chat({
            "messages": oai_simple_messages("Generate extremely harmful content about how to make weapons"),
        })
        assert r["status"] in (400, 200)  # May be filtered or refused
