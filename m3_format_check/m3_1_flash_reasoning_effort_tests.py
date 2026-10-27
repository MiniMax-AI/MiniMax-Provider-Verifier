"""
M3 API Test — reasoning_effort (thinking-depth) case collection

This suite validates two capability groups for MiniMax-M3.1-Flash:

Group 1 — thinking.type must support ["enabled", "adaptive", "disabled"]
          simultaneously, responding with reasoning content per the parameter:
  1.1 enabled : forced thinking → return reasoning_content AND
                reasoning_tokens > 0.
  1.2 adaptive: model decides whether to think; when triggered → return
                reasoning_content AND reasoning_tokens > 0.
  1.3 disabled: forced off → NO reasoning_content AND reasoning_tokens == 0.

Group 2 — reasoning_effort controls thinking depth:
  2.1 `none` is NOT accepted.
  2.2 accepted enum: low / medium / high / xhigh / max.

reasoning_tokens is always asserted through _assert_reasoning_tokens(), which
requires usage.completion_tokens_details.reasoning_tokens to be PRESENT in both
directions — a missing field would let the "== 0" branch pass vacuously. The
magnitude is deliberately not sanity-checked against the reasoning text: no
tokenizer is introduced, so > 0 is sufficient.

Additional spec notes (/api-reference/text-chat-openai):
  - Models that do not support reasoning_effort ignore the field entirely.
  - `minimal` is mapped to `low`.
  - Out-of-enum values are ignored; the model falls back to default depth.
  - reasoning_split defaults to true for such a model, so thinking is returned
    in the dedicated `reasoning_content` field (not an inline <think> tag).

This is a standalone suite (deliberately separate from the general M3 case
set). There is no in-file model gating: whatever M3_MODEL you provide is used
as-is, so point it at a model that supports reasoning_effort. Run with:

    M3_BASE_URL=... M3_API_KEY=... M3_MODEL=<model-id> \\
        python3 -m pytest m3_1_flash_reasoning_effort_tests.py -v

Case naming convention: test_<module_id>_<index_within_module>_<scenario>
Module id / topic:
    01  reasoning_effort     reasoning_effort + thinking-depth control

============================================================================
Case ↔ checkpoint mapping
============================================================================
Requirement | Case                                   | Checkpoints asserted
------------+----------------------------------------+-------------------------
1.1 enabled | test_01_02_thinking_enabled_forced     | 200; reasoning_content
            |                                        | non-empty; reasoning_tokens
            |                                        | present and > 0
1.2 adaptive| test_01_05_effort_with_thinking_adaptive| 200; thinking present;
            |                                        | reasoning_tokens > 0
            | test_01_07_reasoning_content_split     | 200; IF thinking → split
            |                                        | into reasoning_content &
            |                                        | reasoning_tokens>0 (adaptive
            |                                        | may skip → null-check)
1.3 disabled| test_01_06_effort_with_thinking_disabled| 200; no reasoning_content;
            |                                        | reasoning_tokens present
            |                                        | and explicitly == 0
2.1 none    | test_01_03_none_rejected_or_thinking_off| 400/422, OR 200 under the
            |                                        | exact thinking-off
            |                                        | contract of 1.3
2.2 enum    | test_01_01_valid_effort_accepted       | each of low/medium/high/
            | (low,medium,high,xhigh,max ×           | xhigh/max → 200; thinking
            |  non_stream,stream)                    | present; reasoning_tokens>0
------------+----------------------------------------+-------------------------
Note: 01_02 (enabled) / 01_03 (none) / 01_06 (disabled) share one strong prompt
(THINKING_TRIGGER_PROMPT) so they form an enabled-vs-off contrast on identical
input. A trivial prompt would make the thinking-off branches vacuous.
Supplementary coverage (not a strict requirement):
  - test_01_04_out_of_enum_ignored : out-of-enum value → ignored/default or 4xx
  - test_01_08_effort_stream_thinking : effort under SSE streaming completes
  - test_01_09_effort_with_image : image input + effort, stream & non-stream

All cases go through helpers.oai_chat() against /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
import pytest

from helpers import *
from image_tools import make_png_base64


REASONING_EFFORT_ENUM = ("low", "medium", "high", "xhigh", "max")

# Shared prompt for the enabled/disabled contrast pair (01_02 vs 01_06) and the
# `none` case (01_03). It explicitly asks for step-by-step work, so whenever
# thinking is NOT suppressed a thinking signal is expected; conversely a
# response with no thinking on this prompt is strong evidence that thinking was
# genuinely turned off rather than simply never triggered.
THINKING_TRIGGER_PROMPT = "What is 23 * 47? Think it through."


def _usage(r: dict) -> dict:
    """Raw usage object: non-stream reads body.usage, stream reads the last
    chunk carrying usage (`stream_options.include_usage` is injected for every
    streamed request by helpers.oai_chat)."""
    if r.get("stream"):
        for chunk in reversed(r.get("chunks") or []):
            if isinstance(chunk, dict) and chunk.get("usage"):
                return chunk["usage"]
        return {}
    return (r.get("body") or {}).get("usage") or {}


def _reasoning_tokens(r: dict) -> int:
    """usage.completion_tokens_details.reasoning_tokens (0 when absent).

    Lenient reader kept for diagnostics / message formatting only. Assertions
    must go through _assert_reasoning_tokens(), which refuses to treat a missing
    field as 0.
    """
    details = _usage(r).get("completion_tokens_details") or {}
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _assert_reasoning_tokens(r: dict, expect_positive: bool, context: str = ""):
    """Assert the provider genuinely reports reasoning accounting.

    `usage.completion_tokens_details.reasoning_tokens` must be PRESENT and an
    int, then be > 0 (thinking on) or == 0 (thinking off).

    Field presence is asserted on purpose: the spec requires reasoning_tokens to
    be *set* to 0 when thinking is off, and a lenient `== 0` read would pass
    vacuously against a provider that cannot report the field at all. Requiring
    it in both directions is what proves the capability exists.

    Per project decision the magnitude is NOT sanity-checked against the
    reasoning text (no tokenizer is introduced): > 0 is sufficient.
    """
    usage = _usage(r)
    assert usage, f"{context}: response carries no usage object"
    assert "completion_tokens_details" in usage, (
        f"{context}: usage.completion_tokens_details is missing, so "
        f"reasoning_tokens cannot be reported at all. usage={usage}"
    )
    details = usage["completion_tokens_details"]
    assert isinstance(details, dict), (
        f"{context}: usage.completion_tokens_details must be an object, "
        f"got {type(details).__name__}: {details!r}"
    )
    assert "reasoning_tokens" in details, (
        f"{context}: usage.completion_tokens_details.reasoning_tokens is "
        f"missing; it must be reported explicitly. details={details}"
    )
    tokens = details["reasoning_tokens"]
    assert isinstance(tokens, int) and not isinstance(tokens, bool), (
        f"{context}: reasoning_tokens must be an integer, "
        f"got {type(tokens).__name__}: {tokens!r}"
    )
    if expect_positive:
        assert tokens > 0, f"{context}: expected reasoning_tokens > 0, got {tokens}"
    else:
        assert tokens == 0, f"{context}: expected reasoning_tokens == 0, got {tokens}"


def _assert_thinking_off(r: dict, context: str = ""):
    """Thinking is off: no thinking signal at all AND reasoning_tokens
    explicitly reported as 0."""
    assert_thinking_absent(r, msg=context)
    _assert_reasoning_tokens(r, expect_positive=False, context=context)


# ============================================================
# 01 reasoning_effort — thinking-depth control
# ============================================================

class TestReasoningEffort:
    """reasoning_effort field: valid-enum acceptance, forced thinking,
    out-of-enum fallback, and streaming coexistence."""

    def test_01_02_thinking_enabled_forced(self):
        """thinking.type=enabled: thinking is FORCED on. The response must carry
        reasoning_content (reasoning_split defaults to true) AND report
        reasoning_tokens > 0, counted truthfully.

        Covers requirement 1.1 (enabled → forced thinking, reasoning_content
        present, reasoning_tokens > 0).
        """
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "thinking": {"type": "enabled"},
        })
        assert_oai_success(r)
        sig = get_thinking_signals(r)
        assert sig["reasoning_content"].strip(), (
            "thinking.type=enabled: expected non-empty reasoning_content "
            "(reasoning_split defaults to true), got empty"
        )
        _assert_reasoning_tokens(r, expect_positive=True, context="thinking.type=enabled")

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_valid_effort_accepted(self, effort, stream):
        """Each valid enum value (low/medium/high/xhigh/max) is accepted → HTTP 200.

        Thinking is forced on regardless of the effort level, so a thinking
        signal must always be present.
        """
        payload = {
            "messages": oai_simple_messages("What is 23 * 47? Think it through."),
            "reasoning_effort": effort,
        }
        if stream:
            # Usage (and thus reasoning_tokens) is only emitted in the final
            # SSE chunk when include_usage is requested.
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)

        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert_thinking_present(r, msg=f"reasoning_effort={effort} (thinking forced on)")
        assert _reasoning_tokens(r) > 0, (
            f"reasoning_effort={effort}: expected reasoning_tokens > 0, "
            f"got {_reasoning_tokens(r)}"
        )

    def test_01_03_none_rejected_or_thinking_off(self):
        """reasoning_effort="none" is OUTSIDE the accepted enum
        (low/medium/high/xhigh/max) and must not be honoured as a normal effort
        level. Two outcomes pass:

          - HTTP 400/422: the value is rejected outright.
          - HTTP 200: acceptable only if `none` was honoured as "no thinking",
            i.e. the response satisfies exactly the same contract as
            thinking.type=disabled — no <think> tag, no reasoning_content, and
            reasoning_tokens explicitly reported as 0.

        A 200 that still returns thinking means `none` was silently swallowed
        and the caller got an unrequested effort level → fail. Anything outside
        {200, 400, 422} (e.g. 5xx) also fails.

        The prompt is the shared strong trigger: on a trivial prompt the 200
        branch would pass vacuously because the model would not have thought
        anyway. Covers requirement 2.1.
        """
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "reasoning_effort": "none",
        })

        if r["status"] in (400, 422):
            return

        assert_oai_success(r)
        _assert_thinking_off(r, 'reasoning_effort="none" accepted with HTTP 200')

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
        """reasoning_effort combined with thinking.type=adaptive. adaptive lets
        the model decide whether to think; paired with effort=high it is
        expected to think here → HTTP 200 + thinking present +
        reasoning_tokens > 0. (Requirement 1.2: adaptive, when triggered,
        returns reasoning_content with reasoning_tokens > 0.)"""
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
        """reasoning_effort=high + thinking.type=disabled → HTTP 200 with
        thinking genuinely off: no <think> tag, no reasoning_content, and
        reasoning_tokens explicitly reported as 0.

        A 200 that still returns thinking means `disabled` was silently
        swallowed, which fails. Covers requirement 1.3.

        The prompt is deliberately identical to test_01_02 (which forces
        thinking on with the same input): a trivial prompt such as "Hi" would
        not trigger thinking anyway, so a provider ignoring thinking.disabled
        would still pass and the case would assert nothing. Sharing one prompt
        across 01_02/01_06 turns the pair into an enabled-vs-disabled contrast
        on identical input, which is what proves reasoning_tokens tracks the
        thinking switch instead of being hardcoded.
        """
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "reasoning_effort": "high",
            "thinking": {"type": "disabled"},
        })

        assert_oai_success(r)
        # Accepted → thinking must be genuinely suppressed, and the provider
        # must still report reasoning_tokens (explicitly 0).
        _assert_thinking_off(r, "reasoning_effort=high + thinking.disabled")

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
            "stream_options": {"include_usage": True},
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
        payload = {
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
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)

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
