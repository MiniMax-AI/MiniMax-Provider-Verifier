"""
M3 API Test — reasoning_effort (thinking-depth) case collection

reasoning_effort controls thinking depth. Per the spec
(/api-reference/text-chat-openai):

  - reasoning_effort adjusts thinking depth. Models that do not support it
    ignore the field entirely.
  - Valid enum: low / medium / high / xhigh / max.
  - When thinking is forced on, `none` is outside the accepted enum: the
    request is either rejected with HTTP 4xx, or the value is ignored and
    thinking stays adaptive.
  - `minimal` is mapped to `low`.
  - Out-of-enum values are ignored; the model falls back to default depth.
  - When thinking is forced on, thinking runs regardless of reasoning_effort,
    and the thinking content is split into `reasoning_content`
    (reasoning_split defaults to true for such a model).

This is a standalone suite (deliberately separate from the general M3 case
set). There is no in-file model gating: whatever M3_MODEL you provide is used
as-is, so point it at a model that supports reasoning_effort. Run with:

    M3_BASE_URL=... M3_API_KEY=... M3_MODEL=<model-id> \\
        python3 -m pytest m3_reasoning_effort_tests.py -v

Case naming convention: test_<module_id>_<index_within_module>_<scenario>
Module id / topic:
    01  reasoning_effort     reasoning_effort thinking-depth control

All cases go through helpers.oai_chat() against /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
import pytest

from helpers import *
from image_tools import make_png_base64


REASONING_EFFORT_ENUM = ("low", "medium", "high", "xhigh", "max")


def _stream_usage_opts(stream: bool) -> dict:
    """Streaming must explicitly opt in via `stream_options.include_usage=true` to get the usage chunk
    (OpenAI convention; `include_usage` defaults to false). Same helper as m3_a_image_test.py."""
    return {"stream_options": {"include_usage": True}} if stream else {}


def _reasoning_tokens(r: dict) -> int:
    """usage.completion_tokens_details.reasoning_tokens (0 when absent).

    Non-stream reads body.usage; stream reads the last chunk carrying usage.
    """
    if r.get("stream"):
        usage = {}
        for chunk in reversed(r.get("chunks") or []):
            if isinstance(chunk, dict) and chunk.get("usage"):
                usage = chunk["usage"]
                break
    else:
        usage = (r.get("body") or {}).get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


# ============================================================
# 01 reasoning_effort — thinking-depth control
# ============================================================

class TestReasoningEffort:
    """reasoning_effort field: valid-enum acceptance, forced thinking,
    `none` rejection, `minimal`->low mapping, out-of-enum fallback, and
    streaming coexistence."""

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_valid_effort_accepted(self, effort, stream):
        """Each valid enum value (low/medium/high/xhigh/max) is accepted → HTTP 200.

        Thinking is forced on regardless of the effort level, so a thinking
        signal must always be present.
        """
        r = oai_chat({
            "messages": oai_simple_messages("What is 23 * 47? Think it through."),
            "reasoning_effort": effort,
            **_stream_usage_opts(stream),
        }, stream=stream)

        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert_thinking_present(r, msg=f"reasoning_effort={effort} (thinking forced on)")
        assert _reasoning_tokens(r) > 0, (
            f"reasoning_effort={effort}: expected reasoning_tokens > 0, "
            f"got {_reasoning_tokens(r)}"
        )

    def test_01_02_none_rejected_or_adaptive(self):
        """reasoning_effort=none is outside the accepted enum. Two outcomes pass:

          - HTTP 4xx: the value is rejected outright (documented behaviour when
            thinking is forced on).
          - HTTP 200: the value is ignored and thinking stays adaptive, i.e. a
            thinking signal must still be present (non-empty reasoning_content
            and usage reasoning_tokens > 0).

        Anything else (5xx, or 200 with thinking silently turned off) fails.
        """
        r = oai_chat({
            "messages": oai_simple_messages("Say hello"),
            "reasoning_effort": "none",
        })

        assert r["status"] == 200 or 400 <= r["status"] < 500, (
            f"reasoning_effort=none: expected HTTP 200 or 4xx, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )
        if r["status"] != 200:
            return

        # Accepted → thinking must remain adaptive (never silently disabled).
        assert_thinking_present(r, msg="reasoning_effort=none (ignored, thinking adaptive)")
        assert _reasoning_tokens(r) > 0, (
            f"reasoning_effort=none accepted with HTTP 200: expected "
            f"reasoning_tokens > 0, got {_reasoning_tokens(r)}"
        )

    def test_01_03_minimal_mapped_to_low(self):
        """reasoning_effort=minimal is documented to map to `low` → accepted
        (HTTP 200), NOT rejected. Thinking stays on."""
        r = oai_chat({
            "messages": oai_simple_messages("What is 12 + 30?"),
            "reasoning_effort": "minimal",
        })
        assert_oai_success(r)
        assert_thinking_present(r, msg="reasoning_effort=minimal (mapped to low)")
        assert _reasoning_tokens(r) > 0, (
            f"reasoning_effort=minimal: expected reasoning_tokens > 0, "
            f"got {_reasoning_tokens(r)}"
        )

    def test_01_04_out_of_enum_ignored(self):
        """Out-of-enum value is ignored; the model falls back to default depth
        → HTTP 200 with thinking still present.

        Documented behaviour is a silent fallback (not a 400). Tolerate a strict
        deployment that rejects with 400/422 instead.
        """
        r = oai_chat({
            "messages": oai_simple_messages("What is 2+2?"),
            "reasoning_effort": "ultra_super_max_xyz",
        })
        assert r["status"] in (200, 400, 422), (
            f"out-of-enum reasoning_effort HTTP={r['status']}: {str(r.get('body'))[:300]}"
        )
        if r["status"] == 200:
            assert_thinking_present(r, msg="reasoning_effort=out-of-enum (default depth)")
            assert _reasoning_tokens(r) > 0, (
                f"reasoning_effort=out-of-enum: expected reasoning_tokens > 0, "
                f"got {_reasoning_tokens(r)}"
            )

    def test_01_05_effort_with_thinking_adaptive(self):
        """reasoning_effort combined with thinking.type=adaptive (the only
        thinking value accepted when thinking is forced on) → HTTP 200 +
        thinking present."""
        r = oai_chat({
            "messages": oai_simple_messages("Explain why the sky is blue, briefly."),
            "reasoning_effort": "high",
            "thinking": {"type": "adaptive"},
        })
        assert_oai_success(r)
        assert_thinking_present(r, msg="reasoning_effort=high + thinking.adaptive")
        assert _reasoning_tokens(r) > 0, (
            f"reasoning_effort=high + thinking.adaptive: expected reasoning_tokens > 0, "
            f"got {_reasoning_tokens(r)}"
        )

    def test_01_06_effort_with_thinking_disabled(self):
        """reasoning_effort=high + thinking.type=disabled. Two outcomes pass:

          - HTTP 400: thinking is forced on, so `disabled` is rejected.
          - HTTP 200: the request is accepted, in which case thinking must
            actually be off — no <think> tag and no reasoning_content.

        A 200 that still returns thinking means `disabled` was silently
        swallowed, which fails.
        """
        r = oai_chat({
            "messages": oai_simple_messages("Hi"),
            "reasoning_effort": "high",
            "thinking": {"type": "disabled"},
        })

        if r["status"] == 400:
            return

        assert_oai_success(r)
        # Accepted → thinking must be genuinely suppressed.
        assert_thinking_absent(r, msg="reasoning_effort=high + thinking.disabled")

    def test_01_07_reasoning_content_split(self):
        """reasoning_split defaults to true, so WHEN the model thinks, the
        thinking is returned in the dedicated `reasoning_content` field rather
        than as an inline <think> tag in content.

        Per the spec, deep thinking is adaptive: the model may skip thinking on
        simple turns, in which case `reasoning_content` is absent — callers must
        null-check. So this does NOT force a thinking signal; it only verifies
        the split placement when a signal is present.
        """
        r = oai_chat({
            "messages": oai_simple_messages(
                "A train travels 60 km in 45 minutes. What is its average speed "
                "in km/h? Show the reasoning."
            ),
            "reasoning_effort": "high",
        })
        assert_oai_success(r)
        sig = get_thinking_signals(r)
        if not sig["any"]:
            # Adaptive thinking may legitimately skip; nothing to assert about split.
            return
        # A thinking signal exists: with reasoning_split defaulting to true it
        # must land in reasoning_content (not only as an inline <think> tag).
        assert sig["reasoning_content"].strip(), (
            "thinking signal present but reasoning_content is empty; "
            "reasoning_split=true should place thinking in message.reasoning_content"
        )
        assert _reasoning_tokens(r) > 0, (
            f"thinking signal present but reasoning_tokens <= 0, "
            f"got {_reasoning_tokens(r)}"
        )

    @pytest.mark.parametrize("effort", ["low", "max"])
    def test_01_08_effort_stream_thinking(self, effort):
        """reasoning_effort under streaming coexists with the SSE protocol; the
        stream completes cleanly and carries a thinking signal."""
        r = oai_chat({
            "messages": oai_simple_messages("Compute 17 * 19 step by step."),
            "reasoning_effort": effort,
            **_stream_usage_opts(True),
        }, stream=True)
        assert_oai_stream_success(r)
        assert_stream_complete(r, msg=f"reasoning_effort={effort} stream")
        assert_thinking_present(r, msg=f"reasoning_effort={effort} stream")
        assert _reasoning_tokens(r) > 0, (
            f"reasoning_effort={effort} stream: expected reasoning_tokens > 0, "
            f"got {_reasoning_tokens(r)}"
        )

    @pytest.mark.parametrize("effort", ["low", "max"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_09_effort_with_image(self, effort, stream):
        """Image input accepts low/max effort with thinking and a final answer,
        in both non-streaming and complete streaming responses.
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": make_png_base64(672, 672, r=255, g=0, b=0),
                }},
                {"type": "text", "text": (
                    "Identify the dominant color in this image. Use 17 if it is "
                    "red, 23 if green, or 31 if blue, then multiply that number "
                    "by 19. Think it through and give the color and result."
                )},
            ]}],
            "reasoning_effort": effort,
            **_stream_usage_opts(stream),
        }, stream=stream)

        context = f"image + reasoning_effort={effort}, stream={stream}"
        if stream:
            assert_oai_stream_success(r)
            assert_stream_complete(r, msg=context)
        else:
            assert_oai_success(r)
        assert_thinking_present(r, msg=context)
        assert get_oai_content(r).strip(), f"{context}: expected non-empty final answer"
        assert _reasoning_tokens(r) > 0, (
            f"{context}: expected reasoning_tokens > 0, got {_reasoning_tokens(r)}"
        )
