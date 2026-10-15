"""
M3 API Test — reasoning_effort (thinking-depth) case collection

reasoning_effort controls thinking depth. Per the spec
(/api-reference/text-chat-openai):

  - reasoning_effort adjusts thinking depth. Models that do not support it
    ignore the field entirely.
  - Valid enum: low / medium / high / xhigh / max.
  - `none` is outside the accepted enum: the request is either rejected with
    HTTP 4xx, or the value is ignored and thinking stays adaptive.
  - `minimal` is mapped to `low`.
  - Out-of-enum values are ignored; the model falls back to default depth.
  - Thinking is adaptive (omitting `thinking` behaves like
    thinking.type=adaptive): the model decides how much to think from the
    prompt, so thinking length grows with problem difficulty.
  - When present, the thinking content is split into `reasoning_content` and
    counted in usage.completion_tokens_details.reasoning_tokens.
  - thinking.type=disabled returns no thinking content and zero or absent
    reasoning_tokens. Combined with a non-`none` reasoning_effort the request
    is either rejected with HTTP 400 or accepted with thinking off.

This is a standalone suite (deliberately separate from the general M3 case
set). There is no in-file model gating: whatever M3_MODEL you provide is used
as-is, so point it at a model that supports reasoning_effort. Run with:

    M3_BASE_URL=... M3_API_KEY=... M3_MODEL=<model-id> \\
        python3 -m pytest m3_a_reasoning_effort_tests.py -v

Repeated-sampling cases are marked `slow`; deselect them with -m "not slow".

Case naming convention: test_<module_id>_<index_within_module>_<scenario>
Module id / topic:
    01  reasoning_effort     reasoning_effort thinking-depth control

All cases go through helpers.oai_chat() against /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
from statistics import median

import pytest

from helpers import *
from image_tools import make_png_base64


REASONING_EFFORT_ENUM = ("low", "medium", "high", "xhigh", "max")
# Large enough that the deepest effort level finishes without length truncation.
MAX_COMPLETION_TOKENS = 16384
SHORT_PROMPT = "Say hello."
COMPLEX_PROMPT = (
    "Let N be the number of positive divisors of 17017^17 that are "
    "congruent to 5 modulo 12. Find N modulo 1000 and explain your method."
)
# Repeated-sampling settings for the depth comparisons.
SAMPLES = 5
# Complex prompts are expected to think on (almost) every sample.
MIN_COMPLEX_THINKING_SAMPLES = 4
# Median reasoning_tokens on the complex prompt must be at least this many
# times the short prompt's median (observed gap is well above 20x).
DIFFICULTY_RATIO = 5


def _usage(r: dict) -> dict:
    """Return the response usage (stream: last chunk carrying usage)."""
    if r.get("stream"):
        for chunk in reversed(r.get("chunks") or []):
            if isinstance(chunk, dict) and chunk.get("usage"):
                return chunk["usage"]
        return {}
    return (r.get("body") or {}).get("usage") or {}


def _reasoning_tokens(r: dict) -> int:
    """usage.completion_tokens_details.reasoning_tokens (0 when absent)."""
    details = _usage(r).get("completion_tokens_details") or {}
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _chat(payload: dict, stream: bool = False) -> dict:
    """Send the request (stream asks for usage) and assert a successful response."""
    if stream:
        payload["stream_options"] = {"include_usage": True}
    r = oai_chat(payload, stream=stream)
    if stream:
        assert_oai_stream_success(r)
    else:
        assert_oai_success(r)
    return r


def _assert_reasoning_usage(r: dict, context: str) -> bool:
    """Check that visible thinking and reasoning_tokens agree; return has_thinking.

      - stream with include_usage must carry a usage chunk;
      - visible thinking  => reasoning_tokens > 0;
      - reasoning_tokens > 0 => visible thinking (no hidden or dropped thinking);
      - reasoning_tokens <= completion_tokens.
    """
    usage = _usage(r)
    if r.get("stream"):
        assert usage, f"{context}: no usage chunk despite stream_options.include_usage=true"
    has_thinking = get_thinking_signals(r)["any"]
    tokens = _reasoning_tokens(r)
    if has_thinking:
        assert tokens > 0, f"{context}: thinking is present but reasoning_tokens={tokens}"
    else:
        assert tokens == 0, (
            f"{context}: reasoning_tokens={tokens} but no thinking content was returned"
        )
    completion_tokens = usage.get("completion_tokens")
    if isinstance(completion_tokens, int) and tokens:
        assert tokens <= completion_tokens, (
            f"{context}: reasoning_tokens={tokens} exceeds completion_tokens={completion_tokens}"
        )
    return has_thinking


def _assert_disabled(r: dict, context: str) -> None:
    """Disabled thinking: no thinking content and zero reasoning_tokens."""
    if r.get("stream"):
        assert _usage(r), f"{context}: no usage chunk despite stream_options.include_usage=true"
    assert_thinking_absent(r, msg=context)
    assert _reasoning_tokens(r) == 0, (
        f"{context}: disabled should have no reasoning tokens, got {_reasoning_tokens(r)}"
    )


def _sample_reasoning_tokens(payload: dict, context: str) -> list:
    """Run the same request SAMPLES times; return reasoning_tokens per sample
    (0 for samples without thinking)."""
    tokens = []
    for i in range(SAMPLES):
        r = _chat(dict(payload))
        sample = f"{context} sample={i + 1}"
        assert get_oai_content(r).strip(), f"{sample}: expected non-empty final answer"
        assert r["body"]["choices"][0].get("finish_reason") == "stop", (
            f"{sample}: finish_reason={r['body']['choices'][0].get('finish_reason')!r}, "
            f"reasoning truncated by max_completion_tokens={MAX_COMPLETION_TOKENS}?"
        )
        tokens.append(_reasoning_tokens(r) if _assert_reasoning_usage(r, sample) else 0)
    return tokens


# ============================================================
# 01 reasoning_effort — thinking and token usage
# ============================================================

class TestReasoningEffort:
    """reasoning_effort / thinking: enum handling, adaptive depth, disabled
    thinking, and reasoning_tokens accounting in both response modes."""

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_valid_effort_accepted(self, effort, stream):
        """Each valid enum value is accepted in both response modes, and
        visible thinking matches reasoning_tokens."""
        r = _chat({
            "messages": oai_simple_messages("What is 23 * 47? Think it through."),
            "reasoning_effort": effort,
        }, stream=stream)
        assert get_oai_content(r).strip()
        _assert_reasoning_usage(r, f"reasoning_effort={effort}, stream={stream}")

    def test_01_02_none_rejected_or_adaptive(self):
        """reasoning_effort=none is outside the accepted enum. Two outcomes pass:

          - HTTP 4xx: the value is rejected outright.
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
        (HTTP 200), NOT rejected."""
        r = _chat({
            "messages": oai_simple_messages("What is 12 + 30?"),
            "reasoning_effort": "minimal",
        })
        assert get_oai_content(r).strip()
        _assert_reasoning_usage(r, "reasoning_effort=minimal")

    def test_01_04_out_of_enum_ignored(self):
        """Out-of-enum value falls back to default depth (HTTP 200); a strict
        deployment may reject it with 400/422 instead."""
        r = oai_chat({
            "messages": oai_simple_messages("What is 2+2?"),
            "reasoning_effort": "ultra_super_max_xyz",
        })
        assert r["status"] in (200, 400, 422), (
            f"out-of-enum reasoning_effort HTTP={r['status']}: {str(r.get('body'))[:300]}"
        )
        if r["status"] == 200:
            assert_oai_success(r)
            _assert_reasoning_usage(r, "reasoning_effort=out-of-enum")

    def test_01_05_effort_with_thinking_adaptive(self):
        """reasoning_effort combined with thinking.type=adaptive → HTTP 200."""
        r = _chat({
            "messages": oai_simple_messages("Explain why the sky is blue, briefly."),
            "reasoning_effort": "high",
            "thinking": {"type": "adaptive"},
        })
        assert get_oai_content(r).strip()
        _assert_reasoning_usage(r, "reasoning_effort=high + thinking.adaptive")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_06_effort_with_thinking_disabled(self, stream):
        """reasoning_effort=high + thinking.type=disabled. Two outcomes pass:

          - HTTP 400: the conflicting combination is rejected.
          - HTTP 200: thinking must actually be off — no thinking content and
            zero reasoning_tokens.
        """
        payload = {
            "messages": oai_simple_messages("Hi"),
            "reasoning_effort": "high",
            "thinking": {"type": "disabled"},
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)
        if r["status"] == 400:
            return
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_disabled(r, f"reasoning_effort=high + thinking.disabled, stream={stream}")

    def test_01_07_reasoning_content_split(self):
        """When the model thinks, the thinking lands in message.reasoning_content
        (reasoning_split defaults to true), not as an inline <think> tag."""
        r = _chat({
            "messages": oai_simple_messages(
                "A train travels 60 km in 45 minutes. What is its average speed "
                "in km/h? Show the reasoning."
            ),
            "reasoning_effort": "high",
        })
        if not _assert_reasoning_usage(r, "reasoning_split"):
            return
        message = r["body"]["choices"][0]["message"]
        reasoning_content = message.get("reasoning_content")
        assert isinstance(reasoning_content, str) and reasoning_content.strip(), (
            "thinking signal present but reasoning_content is empty; "
            "reasoning_split=true should place thinking in message.reasoning_content"
        )
        assert "<think>" not in (message.get("content") or ""), (
            "thinking leaked into content as an inline <think> tag"
        )

    @pytest.mark.parametrize("effort", ["low", "max"])
    def test_01_08_effort_stream_thinking(self, effort):
        """Streaming with reasoning_effort finishes cleanly and reports usage."""
        r = _chat({
            "messages": oai_simple_messages("Compute 17 * 19 step by step."),
            "reasoning_effort": effort,
        }, stream=True)
        assert get_oai_content(r).strip()
        _assert_reasoning_usage(r, f"reasoning_effort={effort} stream")

    @pytest.mark.parametrize("effort", ["low", "max"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_09_effort_with_image(self, effort, stream):
        """Image input produces a final answer for low and max effort."""
        r = _chat({
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
        }, stream=stream)
        context = f"image + reasoning_effort={effort}, stream={stream}"
        assert get_oai_content(r).strip(), f"{context}: expected non-empty final answer"
        _assert_reasoning_usage(r, context)

    @pytest.mark.parametrize("effort", ["low", "high", "max"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_10_complex_effort(self, effort, stream):
        """A complex prompt with any effort level must think, and report it in
        reasoning_tokens."""
        r = _chat({
            "messages": oai_simple_messages(COMPLEX_PROMPT),
            "reasoning_effort": effort,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }, stream=stream)
        context = f"complex effort={effort}, stream={stream}"
        assert get_oai_content(r).strip()
        assert _assert_reasoning_usage(r, context), f"{context}: expected thinking"

    @pytest.mark.parametrize("thinking", [None, {"type": "adaptive"}],
                             ids=["default", "adaptive"])
    @pytest.mark.parametrize("prompt", [SHORT_PROMPT, COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_11_adaptive(self, thinking, prompt, stream):
        """Default (no `thinking` field) and adaptive thinking: a short prompt
        may or may not think; a complex prompt must think."""
        payload = {
            "messages": oai_simple_messages(prompt),
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }
        if thinking is not None:
            payload["thinking"] = thinking
        r = _chat(payload, stream=stream)
        context = f"thinking={thinking}, prompt={prompt[:12]}, stream={stream}"
        assert get_oai_content(r).strip()
        has_thinking = _assert_reasoning_usage(r, context)
        if prompt == COMPLEX_PROMPT:
            assert has_thinking, f"{context}: complex prompt should think"

    @pytest.mark.slow
    @pytest.mark.parametrize("thinking", [None, {"type": "adaptive"}],
                             ids=["default", "adaptive"])
    def test_01_12_adaptive_depth_by_difficulty(self, thinking):
        """Adaptive thinking scales with difficulty: over repeated samples the
        complex prompt thinks almost every time, and its median reasoning_tokens
        is at least DIFFICULTY_RATIO times the short prompt's."""
        lengths = {}
        for name, prompt in (("short", SHORT_PROMPT), ("complex", COMPLEX_PROMPT)):
            payload = {
                "messages": oai_simple_messages(prompt),
                "max_completion_tokens": MAX_COMPLETION_TOKENS,
            }
            if thinking is not None:
                payload["thinking"] = thinking
            lengths[name] = _sample_reasoning_tokens(payload, f"thinking={thinking}, {name}")
        thinking_samples = sum(t > 0 for t in lengths["complex"])
        assert thinking_samples >= MIN_COMPLEX_THINKING_SAMPLES, (
            f"complex prompt thought in only {thinking_samples}/{SAMPLES} samples: {lengths}"
        )
        assert median(lengths["complex"]) >= DIFFICULTY_RATIO * median(lengths["short"]), (
            f"reasoning depth does not scale with difficulty: {lengths}"
        )

    @pytest.mark.parametrize("prompt", ["Hi", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_13_thinking_disabled(self, prompt, stream):
        """Disabled thinking answers without reasoning for either prompt."""
        r = _chat({
            "messages": oai_simple_messages(prompt),
            "thinking": {"type": "disabled"},
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }, stream=stream)
        assert get_oai_content(r).strip()
        _assert_disabled(r, f"disabled prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.slow
    def test_01_14_effort_depth_repeated(self):
        """Higher effort thinks longer on the complex prompt: over repeated
        samples, median reasoning_tokens of low is below max. Adjacent levels
        are not compared because their distributions overlap. Every sample must
        think (a complex prompt never skips thinking)."""
        lengths = {}
        for effort in ("low", "max"):
            lengths[effort] = _sample_reasoning_tokens({
                "messages": oai_simple_messages(COMPLEX_PROMPT),
                "reasoning_effort": effort,
                "max_completion_tokens": MAX_COMPLETION_TOKENS,
            }, f"effort={effort}")
            assert all(t > 0 for t in lengths[effort]), (
                f"effort={effort}: complex prompt skipped thinking: {lengths}"
            )
        assert median(lengths["low"]) < median(lengths["max"]), (
            f"max did not think longer than low: {lengths}"
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_15_disabled_repeated(self, stream):
        """Repeated complex requests never intermittently return reasoning when
        thinking is disabled."""
        for sample in range(SAMPLES):
            r = _chat({
                "messages": oai_simple_messages(COMPLEX_PROMPT),
                "thinking": {"type": "disabled"},
                "max_completion_tokens": MAX_COMPLETION_TOKENS,
            }, stream=stream)
            assert get_oai_content(r).strip()
            _assert_disabled(r, f"disabled sample={sample + 1}, stream={stream}")
