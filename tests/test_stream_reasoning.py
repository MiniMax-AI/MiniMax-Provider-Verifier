"""
Regression tests for reasoning capture in ValidatorRunner._handle_stream_request.

The non-stream path keeps the provider's `reasoning_content` / `reasoning` field
via response.model_dump(), but the stream path rebuilt the message from
content and tool_calls only. A reasoning-only reply therefore never reached
_is_error_only_reasoning_response in stream mode, so Error-Only-Reasoning could
not fire for --stream runs.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    Choice,
    ChoiceDelta,
)

from verify import ValidatorRunner


def make_chunk(finish_reason=None, **delta):
    return ChatCompletionChunk(
        id="chatcmpl-test",
        choices=[Choice(index=0, delta=ChoiceDelta(**delta), finish_reason=finish_reason)],
        created=1234567890,
        model="minimax-m2",
        object="chat.completion.chunk",
    )


class FakeStream:
    """Mimics an OpenAI streaming response: async-iterable over chunks."""

    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for c in self._chunks:
            yield c


def _run_stream(chunks):
    runner = ValidatorRunner(
        model="minimax-m2",
        base_url="http://example.invalid/v1",
        api_key="unused",
        stream=True,
    )

    async def fake_create(**kwargs):
        return FakeStream(chunks)

    runner.client.chat.completions.create = fake_create

    async def run():
        return await runner._handle_stream_request({"stream": True, "model": "minimax-m2"})

    return asyncio.run(run())


def test_reasoning_only_stream_is_flagged():
    """delta.reasoning_content (M3 spec) is joined into the message and an
    answer with no content or tool_calls counts as Error-Only-Reasoning.
    """
    status, response = _run_stream([
        make_chunk(reasoning_content="Let me think. "),
        make_chunk(reasoning_content="The answer is 4."),
        make_chunk(finish_reason="stop"),
    ])

    assert status == "success"
    message = response["choices"][0]["message"]
    assert message["reasoning_content"] == "Let me think. The answer is 4."
    assert ValidatorRunner._is_error_only_reasoning_response(response) is True


def test_reasoning_field_fallback():
    """Providers that stream delta.reasoning instead are captured too."""
    status, response = _run_stream([
        make_chunk(reasoning="thinking"),
        make_chunk(finish_reason="stop"),
    ])

    assert status == "success"
    assert response["choices"][0]["message"]["reasoning_content"] == "thinking"
    assert ValidatorRunner._is_error_only_reasoning_response(response) is True


def test_reasoning_with_content_is_not_flagged():
    """Reasoning followed by a real answer is a normal response."""
    status, response = _run_stream([
        make_chunk(reasoning_content="thinking"),
        make_chunk(content="4"),
        make_chunk(finish_reason="stop"),
    ])

    assert status == "success"
    message = response["choices"][0]["message"]
    assert message["reasoning_content"] == "thinking"
    assert message["content"] == "4"
    assert ValidatorRunner._is_error_only_reasoning_response(response) is False
