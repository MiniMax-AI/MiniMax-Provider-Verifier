import pytest

from helpers import *


REASONING_EFFORT_ENUM = ("low", "medium", "high", "xhigh", "max")
MAX_COMPLETION_TOKENS = 4096
COMPLEX_PROMPT = (
    "How many positive divisors of 2^8 * 3^5 are divisible by 12? "
    "Show the calculation step by step."
)


def _reasoning_tokens(result: dict) -> int:
    """Treat missing reasoning_tokens as zero."""
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


def _assert_usage_if_thinking(result: dict, context: str) -> None:
    if get_thinking_signals(result)["any"]:
        assert _reasoning_tokens(result) > 0, (
            f"{context}: expected reasoning_tokens > 0 when thinking is present, "
            f"got {_reasoning_tokens(result)}"
        )


def _assert_disabled(result: dict, context: str) -> None:
    assert_thinking_absent(result, msg=context)
    assert _reasoning_tokens(result) == 0, (
        f"{context}: expected zero or absent reasoning_tokens when disabled, "
        f"got {_reasoning_tokens(result)}"
    )


# ============================================================
# 01 reasoning_effort — M3 thinking and reasoning tokens
# ============================================================

class TestReasoningEffort:
    @pytest.mark.parametrize("thinking", [None, {"type": "adaptive"}],
                             ids=["default", "adaptive"])
    @pytest.mark.parametrize("prompt", ["Say hello.", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_adaptive(self, thinking, prompt, stream):
        """Accept default and explicit adaptive thinking; check tokens when reasoning is returned."""
        fields = {} if thinking is None else {"thinking": thinking}
        result = _request(prompt, stream=stream, **fields)
        _assert_usage_if_thinking(result, f"adaptive prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.parametrize("prompt", ["Hi", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_02_thinking_disabled(self, prompt, stream):
        """Answer directly without reasoning content when standalone disabled thinking is requested."""
        result = _request(prompt, stream=stream, thinking={"type": "disabled"})
        _assert_disabled(result, f"disabled prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_03_valid_reasoning_effort_accepted(self, effort, stream):
        """Accept valid effort values and check token counts when reasoning is returned."""
        result = _request(COMPLEX_PROMPT, stream=stream, reasoning_effort=effort)
        _assert_usage_if_thinking(result, f"effort={effort}, stream={stream}")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.slow
    def test_01_04_disabled_repeated(self, stream):
        """Repeat complex prompts to detect reasoning returned intermittently when thinking is disabled."""
        for sample in range(5):
            result = _request(COMPLEX_PROMPT, stream=stream,
                              thinking={"type": "disabled"})
            _assert_disabled(result, f"disabled sample={sample + 1}, stream={stream}")

    @pytest.mark.parametrize("prompt", ["Say hello.", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.slow
    def test_01_05_adaptive_repeated(self, prompt):
        """Repeat adaptive prompts and check token counts for reasoning that is actually returned."""
        for sample in range(5):
            result = _request(prompt, thinking={"type": "adaptive"})
            _assert_usage_if_thinking(result, f"adaptive sample={sample + 1}")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_06_reasoning_tokens_when_present(self, stream):
        """Require reasoning_tokens to be present and positive whenever reasoning content is returned."""
        result = _request(COMPLEX_PROMPT, stream=stream,
                          thinking={"type": "adaptive"})
        if not get_thinking_signals(result)["any"]:
            pytest.skip("No visible thinking; cannot check reasoning token counts")
        assert _reasoning_tokens(result) > 0, (
            f"stream={stream}: thinking signal present but reasoning_tokens is missing or zero"
        )
