"""
M3 API Test — reasoning_effort (thinking-depth) case collection

reasoning_effort controls thinking depth. Per the spec
(/api-reference/text-chat-openai):

  - reasoning_effort adjusts thinking depth. Models that do not support it
    ignore the field entirely.
  - Valid enum: low / medium / high / xhigh / max.
  - `minimal` is mapped to `low`.
  - Out-of-enum values are ignored; the model falls back to default depth.
  - Thinking is adaptive; when present, the thinking content is split into
    `reasoning_content` and counted in usage.completion_tokens_details.reasoning_tokens.
  - thinking.type=disabled returns no thinking content and zero or absent
    reasoning_tokens, including when reasoning_effort is provided.

This is a standalone suite (deliberately separate from the general M3 case
set). There is no in-file model gating: whatever M3_MODEL you provide is used
as-is, so point it at a model that supports reasoning_effort. Run with:

    M3_BASE_URL=... M3_API_KEY=... M3_MODEL=<model-id> \\
        python3 -m pytest m3_a_reasoning_effort_tests.py -v

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
MAX_COMPLETION_TOKENS = 8192
COMPLEX_PROMPT = (
    "Let N be the number of positive divisors of 17017^17 that are "
    "congruent to 5 modulo 12. Find N modulo 1000 and explain your method."
)


def _reasoning_tokens(r: dict) -> int:
    """Return reasoning_tokens from the response usage (0 when absent)."""
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


def _assert_usage_if_thinking(r: dict, context: str) -> bool:
    """Check the token count only when the response contains thinking."""
    has_thinking = get_thinking_signals(r)["any"]
    if has_thinking:
        assert _reasoning_tokens(r) > 0, (
            f"{context}: thinking is present but reasoning_tokens={_reasoning_tokens(r)}"
        )
    return has_thinking


def _assert_disabled(r: dict, context: str) -> None:
    assert_thinking_absent(r, msg=context)
    assert _reasoning_tokens(r) == 0, (
        f"{context}: disabled should have no reasoning tokens, got {_reasoning_tokens(r)}"
    )


# ============================================================
# 01 reasoning_effort — thinking and token usage
# ============================================================

class TestReasoningEffort:
    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_valid_effort_accepted(self, effort, stream):
        """Valid effort values should be accepted in both response modes."""
        payload = {
            "messages": oai_simple_messages("What is 23 * 47? Think it through."),
            "reasoning_effort": effort,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_usage_if_thinking(r, f"reasoning_effort={effort}, stream={stream}")

    def test_01_03_minimal_mapped_to_low(self):
        """The historical minimal value should still be accepted."""
        r = oai_chat({
            "messages": oai_simple_messages("What is 12 + 30?"),
            "reasoning_effort": "minimal",
        })
        assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_usage_if_thinking(r, "reasoning_effort=minimal")

    def test_01_04_out_of_enum_ignored(self):
        """Accept a fallback response or a strict validation error."""
        r = oai_chat({
            "messages": oai_simple_messages("What is 2+2?"),
            "reasoning_effort": "ultra_super_max_xyz",
        })
        assert r["status"] in (200, 400, 422), (
            f"out-of-enum reasoning_effort HTTP={r['status']}: {str(r.get('body'))[:300]}"
        )
        if r["status"] == 200:
            assert_oai_success(r)
            _assert_usage_if_thinking(r, "reasoning_effort=out-of-enum")

    def test_01_05_effort_with_thinking_adaptive(self):
        """Effort and adaptive thinking should work together."""
        r = oai_chat({
            "messages": oai_simple_messages("Explain why the sky is blue, briefly."),
            "reasoning_effort": "high",
            "thinking": {"type": "adaptive"},
        })
        assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_usage_if_thinking(r, "reasoning_effort=high + thinking.adaptive")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_06_effort_with_thinking_disabled(self, stream):
        """Disabled thinking should return a final answer without reasoning."""
        payload = {
            "messages": oai_simple_messages("Hi"),
            "reasoning_effort": "high",
            "thinking": {"type": "disabled"},
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_disabled(r, f"reasoning_effort=high + thinking.disabled, stream={stream}")

    def test_01_07_reasoning_content_split(self):
        """When thinking is visible, it should use reasoning_content."""
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
            return
        message = r["body"]["choices"][0]["message"]
        reasoning_content = message.get("reasoning_content")
        assert isinstance(reasoning_content, str) and reasoning_content.strip(), (
            "thinking signal present but reasoning_content is empty; "
            "reasoning_split=true should place thinking in message.reasoning_content"
        )
        assert _reasoning_tokens(r) > 0, (
            f"thinking signal present but reasoning_tokens={_reasoning_tokens(r)}"
        )

    @pytest.mark.parametrize("effort", ["low", "max"])
    def test_01_08_effort_stream_thinking(self, effort):
        """Streaming should finish cleanly and report usage if it thinks."""
        r = oai_chat({
            "messages": oai_simple_messages("Compute 17 * 19 step by step."),
            "reasoning_effort": effort,
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)
        assert get_oai_content(r).strip()
        _assert_usage_if_thinking(r, f"reasoning_effort={effort} stream")

    @pytest.mark.parametrize("effort", ["low", "max"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_09_effort_with_image(self, effort, stream):
        """Image input should produce a final answer for low and max effort."""
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
        else:
            assert_oai_success(r)
        assert get_oai_content(r).strip(), f"{context}: expected non-empty final answer"
        _assert_usage_if_thinking(r, context)

    @pytest.mark.parametrize("effort", ["low", "high", "max"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_10_complex_effort(self, effort, stream):
        """Complex input covers effort levels and both response modes."""
        payload = {
            "messages": oai_simple_messages(COMPLEX_PROMPT),
            "reasoning_effort": effort,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_usage_if_thinking(r, f"complex effort={effort}, stream={stream}")

    @pytest.mark.parametrize("thinking", [None, {"type": "adaptive"}],
                             ids=["default", "adaptive"])
    @pytest.mark.parametrize("prompt", ["Say hello.", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_11_adaptive(self, thinking, prompt, stream):
        """Default and adaptive thinking may vary with the prompt."""
        payload = {
            "messages": oai_simple_messages(prompt),
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }
        if thinking is not None:
            payload["thinking"] = thinking
        if stream:
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_usage_if_thinking(r, f"adaptive prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.parametrize("prompt", ["Hi", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_13_thinking_disabled(self, prompt, stream):
        """Disabled thinking should answer without reasoning for either prompt."""
        payload = {
            "messages": oai_simple_messages(prompt),
            "thinking": {"type": "disabled"},
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        r = oai_chat(payload, stream=stream)
        if stream:
            assert_oai_stream_success(r)
        else:
            assert_oai_success(r)
        assert get_oai_content(r).strip()
        _assert_disabled(r, f"disabled prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.slow
    def test_01_14_effort_depth_repeated(self):
        """Max should use more reasoning tokens than low on repeated inputs."""
        lengths = {"low": [], "max": []}
        for _ in range(5):
            for effort in ("low", "max"):
                r = oai_chat({
                    "messages": oai_simple_messages(COMPLEX_PROMPT),
                    "reasoning_effort": effort,
                    "max_completion_tokens": MAX_COMPLETION_TOKENS,
                })
                assert_oai_success(r)
                assert get_oai_content(r).strip()
                if _assert_usage_if_thinking(r, f"repeated effort={effort}"):
                    lengths[effort].append(_reasoning_tokens(r))
        if min(map(len, lengths.values())) < 3:
            pytest.skip(f"Too few visible thinking samples: {lengths}")
        assert median(lengths["max"]) > median(lengths["low"]), (
            f"max did not use more reasoning tokens than low: {lengths}"
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.slow
    def test_01_15_disabled_repeated(self, stream):
        """Repeated complex requests should not intermittently return reasoning."""
        for sample in range(5):
            payload = {
                "messages": oai_simple_messages(COMPLEX_PROMPT),
                "thinking": {"type": "disabled"},
                "max_completion_tokens": MAX_COMPLETION_TOKENS,
            }
            if stream:
                payload["stream_options"] = {"include_usage": True}
            r = oai_chat(payload, stream=stream)
            if stream:
                assert_oai_stream_success(r)
            else:
                assert_oai_success(r)
            assert get_oai_content(r).strip()
            _assert_disabled(r, f"disabled sample={sample + 1}, stream={stream}")
