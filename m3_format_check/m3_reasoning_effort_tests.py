"""
M3 API Test — thinking / reasoning_effort case collection (M3 suite)

Counterpart of m3_a_reasoning_effort_tests.py for the general M3 case set:

  - Thinking is adaptive (omitting `thinking` behaves like
    thinking.type=adaptive); a complex prompt must think.
  - When present, the thinking content is split into `reasoning_content` and
    counted in usage.completion_tokens_details.reasoning_tokens.
  - thinking.type=disabled returns no thinking content and zero or absent
    reasoning_tokens.
  - Valid reasoning_effort values (low / medium / high / xhigh / max) are
    accepted.

Run with:

    M3_BASE_URL=... M3_API_KEY=... M3_MODEL=<model-id> \\
        python3 -m pytest m3_reasoning_effort_tests.py -v

Repeated-sampling cases are marked `slow`; deselect them with -m "not slow".

Case naming convention: test_<module_id>_<index_within_module>_<scenario>
Module id / topic:
    01  reasoning_effort     thinking and reasoning_tokens accounting

All cases go through helpers.oai_chat() against /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
import pytest

from helpers import *


REASONING_EFFORT_ENUM = ("low", "medium", "high", "xhigh", "max")
MAX_COMPLETION_TOKENS = 16384
SHORT_PROMPT = "Say hello."
COMPLEX_PROMPT = (
    "How many positive divisors of 2^8 * 3^5 are divisible by 12? "
    "Show the calculation step by step."
)
SAMPLES = 5


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
    """Check that visible thinking and reasoning_tokens agree; return has_thinking."""
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


# ============================================================
# 01 reasoning_effort — thinking and token usage
# ============================================================

class TestReasoningEffort:
    """Adaptive / disabled thinking and reasoning_tokens accounting."""

    @pytest.mark.parametrize("thinking", [None, {"type": "adaptive"}],
                             ids=["default", "adaptive"])
    @pytest.mark.parametrize("prompt", [SHORT_PROMPT, COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_01_adaptive(self, thinking, prompt, stream):
        """Default and adaptive thinking return a final answer; a complex
        prompt must think."""
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

    @pytest.mark.parametrize("prompt", ["Hi", COMPLEX_PROMPT],
                             ids=["short", "complex"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_02_thinking_disabled(self, prompt, stream):
        """Disabled thinking answers without reasoning."""
        r = _chat({
            "messages": oai_simple_messages(prompt),
            "thinking": {"type": "disabled"},
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }, stream=stream)
        assert get_oai_content(r).strip()
        _assert_disabled(r, f"disabled prompt={prompt[:12]}, stream={stream}")

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_03_valid_reasoning_effort_accepted(self, effort, stream):
        """Valid effort values are accepted and token accounting stays consistent."""
        r = _chat({
            "messages": oai_simple_messages(COMPLEX_PROMPT),
            "reasoning_effort": effort,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }, stream=stream)
        assert get_oai_content(r).strip()
        _assert_reasoning_usage(r, f"effort={effort}, stream={stream}")

    @pytest.mark.slow
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_01_04_disabled_repeated(self, stream):
        """Repeated requests never intermittently return reasoning when disabled."""
        for sample in range(SAMPLES):
            r = _chat({
                "messages": oai_simple_messages(COMPLEX_PROMPT),
                "thinking": {"type": "disabled"},
                "max_completion_tokens": MAX_COMPLETION_TOKENS,
            }, stream=stream)
            assert get_oai_content(r).strip()
            _assert_disabled(r, f"disabled sample={sample + 1}, stream={stream}")

    @pytest.mark.slow
    @pytest.mark.parametrize("prompt", [SHORT_PROMPT, COMPLEX_PROMPT],
                             ids=["short", "complex"])
    def test_01_05_adaptive_repeated(self, prompt):
        """Token accounting stays consistent over repeated adaptive calls, and
        the complex prompt thinks on every sample."""
        for sample in range(SAMPLES):
            r = _chat({
                "messages": oai_simple_messages(prompt),
                "thinking": {"type": "adaptive"},
                "max_completion_tokens": MAX_COMPLETION_TOKENS,
            })
            context = f"adaptive prompt={prompt[:12]}, sample={sample + 1}"
            assert get_oai_content(r).strip()
            has_thinking = _assert_reasoning_usage(r, context)
            if prompt == COMPLEX_PROMPT:
                assert has_thinking, f"{context}: complex prompt should think"
