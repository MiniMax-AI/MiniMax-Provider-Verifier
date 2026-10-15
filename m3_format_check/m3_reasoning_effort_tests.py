import pytest

from helpers import *


REASONING_EFFORT_ENUM = ("low", "medium", "high", "xhigh", "max")
MAX_COMPLETION_TOKENS = 4096
COMPLEX_PROMPT = (
    "How many positive divisors of 2^8 * 3^5 are divisible by 12? "
    "Show the calculation step by step."
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


def _assert_usage_if_thinking(r: dict, context: str) -> None:
    if get_thinking_signals(r)["any"]:
        assert _reasoning_tokens(r) > 0, (
            f"{context}: thinking is present but reasoning_tokens={_reasoning_tokens(r)}"
        )


def _assert_disabled(r: dict, context: str) -> None:
    assert_thinking_absent(r, msg=context)
    assert _reasoning_tokens(r) == 0, (
        f"{context}: disabled should have no reasoning tokens, got {_reasoning_tokens(r)}"
    )


# ============================================================
# 01 reasoning_effort — thinking and token usage
# ============================================================

class TestReasoningEffort:
    @pytest.mark.parametrize("thinking", [None, {"type": "adaptive"}],
                             ids=["default", "adaptive"])
    @pytest.mark.parametrize("prompt", ["Say hello.", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_adaptive(self, thinking, prompt, stream):
        """Default and adaptive thinking should return a final answer."""
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
    def test_01_02_thinking_disabled(self, prompt, stream):
        """Disabled thinking should answer without reasoning."""
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

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_03_valid_reasoning_effort_accepted(self, effort, stream):
        """Valid effort values should be accepted."""
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
        _assert_usage_if_thinking(r, f"effort={effort}, stream={stream}")

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    @pytest.mark.slow
    def test_01_04_disabled_repeated(self, stream):
        """Repeated requests should not intermittently return reasoning."""
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

    @pytest.mark.parametrize("prompt", ["Say hello.", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.slow
    def test_01_05_adaptive_repeated(self, prompt):
        """Check token accounting whenever repeated adaptive calls think."""
        for sample in range(5):
            r = oai_chat({
                "messages": oai_simple_messages(prompt),
                "thinking": {"type": "adaptive"},
                "max_completion_tokens": MAX_COMPLETION_TOKENS,
            })
            assert_oai_success(r)
            assert get_oai_content(r).strip()
            _assert_usage_if_thinking(r, f"adaptive sample={sample + 1}")
