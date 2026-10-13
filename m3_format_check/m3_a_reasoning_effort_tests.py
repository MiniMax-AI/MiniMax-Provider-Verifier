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


def _reasoning_tokens(result: dict) -> int:
    """usage.completion_tokens_details.reasoning_tokens (0 when absent).

    Non-stream reads body.usage; stream reads the last chunk carrying usage.
    """
    if result.get("stream"):
        usage = {}
        for chunk in reversed(result.get("chunks") or []):
            if isinstance(chunk, dict) and chunk.get("usage"):
                usage = chunk["usage"]
                break
    else:
        usage = (result.get("body") or {}).get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    try:
        return int(details.get("reasoning_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _request(prompt: str, *, stream: bool = False, **fields) -> dict:
    payload = {
        "messages": oai_simple_messages(prompt),
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        **fields,
    }
    if stream:
        payload["stream_options"] = {"include_usage": True}
    result = oai_chat(payload, stream=stream)
    if stream:
        assert_oai_stream_success(result)
    else:
        assert_oai_success(result)
    assert get_oai_content(result).strip(), "Expected non-empty final answer"
    return result


def _assert_usage_if_thinking(result: dict, context: str) -> bool:
    """Require positive reasoning_tokens only when reasoning content is returned."""
    has_thinking = get_thinking_signals(result)["any"]
    if has_thinking:
        assert _reasoning_tokens(result) > 0, (
            f"{context}: thinking signal present but reasoning_tokens={_reasoning_tokens(result)}"
        )
    return has_thinking


def _assert_disabled(result: dict, context: str) -> None:
    assert_thinking_absent(result, msg=context)
    assert _reasoning_tokens(result) == 0, (
        f"{context}: expected zero or absent reasoning_tokens when disabled, "
        f"got {_reasoning_tokens(result)}"
    )


# ============================================================
# 01 reasoning_effort — thinking-depth control
# ============================================================

class TestReasoningEffort:
    """reasoning_effort field: valid-enum acceptance, adaptive/disabled thinking,
    `minimal`->low mapping, out-of-enum fallback, and streaming coexistence."""

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_valid_effort_accepted(self, effort, stream):
        """Each valid enum value (low/medium/high/xhigh/max) is accepted → HTTP 200.

        Thinking is adaptive; when a thinking signal is present, reasoning_tokens
        must be positive.
        """
        result = _request("What is 23 * 47? Explain briefly.", stream=stream,
                          reasoning_effort=effort)
        _assert_usage_if_thinking(result, f"effort={effort}, stream={stream}")

    def test_01_03_minimal_mapped_to_low(self):
        """reasoning_effort=minimal is documented to map to `low` → accepted
        (HTTP 200), NOT rejected. Thinking is adaptive."""
        result = _request("What is 12 + 30?", reasoning_effort="minimal")
        _assert_usage_if_thinking(result, "effort=minimal")

    def test_01_04_out_of_enum_ignored(self):
        """Out-of-enum value is ignored; the model falls back to default depth
        → HTTP 200 with adaptive thinking.

        Documented behaviour is a silent fallback (not a 400). Tolerate a strict
        deployment that rejects with 400/422 instead.
        """
        result = oai_chat({
            "messages": oai_simple_messages("What is 2 + 2?"),
            "reasoning_effort": "ultra_super_max_xyz",
        })
        assert result["status"] in (200, 400, 422)
        if result["status"] == 200:
            assert_oai_success(result)
            _assert_usage_if_thinking(result, "effort=out_of_enum")

    def test_01_05_effort_with_thinking_adaptive(self):
        """reasoning_effort combined with thinking.type=adaptive → HTTP 200;
        check reasoning_tokens when thinking is present."""
        result = _request("Explain why the sky is blue, briefly.",
                          reasoning_effort="high", thinking={"type": "adaptive"})
        _assert_usage_if_thinking(result, "effort=high + adaptive")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_06_effort_with_thinking_disabled(self, stream):
        """reasoning_effort=high + thinking.type=disabled: passes when the
        response is HTTP 200 with no reasoning content and zero or absent
        reasoning_tokens."""
        result = _request("Hi", stream=stream, reasoning_effort="high",
                          thinking={"type": "disabled"})
        _assert_disabled(result, f"effort=high + disabled, stream={stream}")

    def test_01_07_reasoning_content_split(self):
        """reasoning_split defaults to true, so WHEN the model thinks, the
        thinking is returned in the dedicated `reasoning_content` field rather
        than as an inline <think> tag in content.

        Per the spec, deep thinking is adaptive: the model may skip thinking on
        simple turns, in which case `reasoning_content` is absent — callers must
        null-check. So this does NOT force a thinking signal; it only verifies
        the split placement when a signal is present.
        """
        result = _request(COMPLEX_PROMPT, reasoning_effort="high")
        signals = get_thinking_signals(result)
        if not signals["any"]:
            # Adaptive thinking may legitimately skip; nothing to assert about split.
            pytest.skip("Adaptive thinking returned no visible reasoning; cannot check field placement")
        # A thinking signal exists: with reasoning_split defaulting to true it
        # must land in reasoning_content (not only as an inline <think> tag).
        message = result["body"]["choices"][0]["message"]
        reasoning_content = message.get("reasoning_content")
        assert isinstance(reasoning_content, str) and reasoning_content.strip(), (
            "thinking signal present but reasoning_content is empty"
        )
        _assert_usage_if_thinking(result, "reasoning_content placement")

    @pytest.mark.parametrize("effort", ["low", "max"])
    def test_01_08_effort_stream_thinking(self, effort):
        """reasoning_effort under streaming coexists with the SSE protocol; the
        stream completes cleanly and may carry a thinking signal."""
        result = _request("Compute 17 * 19 step by step.", stream=True,
                          reasoning_effort=effort)
        _assert_usage_if_thinking(result, f"stream effort={effort}")

    @pytest.mark.parametrize("effort", ["low", "max"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_09_effort_with_image(self, effort, stream):
        """Image input accepts low/max effort with adaptive thinking and a final answer,
        in both non-streaming and complete streaming responses.
        """
        payload = {
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": make_png_base64(672, 672, r=255, g=0, b=0),
                }},
                {"type": "text", "text": "Identify the color and multiply its RGB red value by 19."},
            ]}],
            "reasoning_effort": effort,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        result = oai_chat(payload, stream=stream)
        if stream:
            assert_oai_stream_success(result)
        else:
            assert_oai_success(result)
        assert get_oai_content(result).strip()
        _assert_usage_if_thinking(result, f"image effort={effort}, stream={stream}")

    @pytest.mark.parametrize("effort", ["low", "high", "max"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_10_complex_effort(self, effort, stream):
        """Cover effort levels and reasoning token counts on complex prompts in both response modes."""
        result = _request(COMPLEX_PROMPT, stream=stream, reasoning_effort=effort)
        _assert_usage_if_thinking(result, f"complex effort={effort}, stream={stream}")

    @pytest.mark.parametrize("thinking", [None, {"type": "adaptive"}],
                             ids=["default", "adaptive"])
    @pytest.mark.parametrize("prompt", ["Say hello.", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_11_adaptive(self, thinking, prompt, stream):
        """Allow default and explicit adaptive thinking to decide whether a prompt needs reasoning."""
        fields = {} if thinking is None else {"thinking": thinking}
        result = _request(prompt, stream=stream, **fields)
        _assert_usage_if_thinking(result, f"adaptive prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_12_reasoning_tokens_when_present(self, stream):
        """Require reasoning_tokens to be present and positive whenever reasoning content is returned."""
        result = _request(COMPLEX_PROMPT, stream=stream, reasoning_effort="high")
        if not get_thinking_signals(result)["any"]:
            pytest.skip("No visible thinking; cannot check reasoning token counts")
        assert _reasoning_tokens(result) > 0, (
            f"stream={stream}: thinking signal present but reasoning_tokens is missing or zero"
        )

    @pytest.mark.parametrize("prompt", ["Hi", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_13_thinking_disabled(self, prompt, stream):
        """Answer with standalone disabled thinking, no reasoning content, and zero or absent tokens."""
        result = _request(prompt, stream=stream, thinking={"type": "disabled"})
        _assert_disabled(result, f"disabled prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.slow
    def test_01_14_effort_depth_repeated(self):
        """Compare repeated samples of the same prompt: max should have a higher token median than low."""
        lengths = {"low": [], "max": []}
        for _ in range(5):
            for effort in ("low", "max"):
                result = _request(COMPLEX_PROMPT, reasoning_effort=effort)
                if _assert_usage_if_thinking(result, f"repeated effort={effort}"):
                    lengths[effort].append(_reasoning_tokens(result))
        if min(map(len, lengths.values())) < 3:
            pytest.skip(f"Insufficient samples with visible thinking: {lengths}")
        assert median(lengths["max"]) > median(lengths["low"]), (
            f"Expected max reasoning token median to exceed low: {lengths}"
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.slow
    def test_01_15_disabled_repeated(self, stream):
        """Repeat complex prompts to detect reasoning returned intermittently when thinking is disabled."""
        for sample in range(5):
            result = _request(COMPLEX_PROMPT, stream=stream,
                              thinking={"type": "disabled"})
            _assert_disabled(result, f"disabled sample={sample + 1}, stream={stream}")
