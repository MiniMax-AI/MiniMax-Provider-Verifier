"""
Regression tests for ValidatorRunner._handle_stream_request usage extraction.

Background: OpenAI's streaming chat completion protocol puts `usage` as a
top-level field on ChatCompletionChunk, not on Choice. When a request sets
stream_options.include_usage=true, the provider sends a terminal chunk whose
`choices` list is empty and which carries the real usage. verify.py used to
read `choice.usage` (an attribute that does not exist on Choice) and, before
that, `continue`d past any chunk with empty choices -- skipping the one
chunk that carries usage. Net effect: response["usage"] was always None for
every --stream run, regardless of what the provider returned.

These tests build a spec-accurate fake stream out of the real openai SDK
types and drive it through the actual ValidatorRunner._handle_stream_request.
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
from openai.types.completion_usage import CompletionUsage

from verify import ValidatorRunner


def make_chunk(content=None, finish_reason=None, usage=None, choices_present=True):
    choices = []
    if choices_present:
        choices = [
            Choice(
                index=0,
                delta=ChoiceDelta(content=content, role="assistant" if content else None),
                finish_reason=finish_reason,
            )
        ]
    return ChatCompletionChunk(
        id="chatcmpl-test",
        choices=choices,
        created=1234567890,
        model="minimax-m2",
        object="chat.completion.chunk",
        usage=usage,
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


def _make_runner():
    return ValidatorRunner(
        model="minimax-m2",
        base_url="http://example.invalid/v1",
        api_key="unused",
        stream=True,
    )


def test_stream_usage_captured_from_terminal_empty_choices_chunk():
    """A spec-compliant stream: content chunk, finish_reason chunk, then a
    terminal chunk with choices=[] carrying usage. response["usage"] must
    match what the provider sent.
    """
    real_usage = CompletionUsage(prompt_tokens=42, completion_tokens=7, total_tokens=49)
    chunks = [
        make_chunk(content="Hello"),
        make_chunk(finish_reason="stop"),
        make_chunk(usage=real_usage, choices_present=False),
    ]

    runner = _make_runner()

    async def fake_create(**kwargs):
        return FakeStream(chunks)

    runner.client.chat.completions.create = fake_create

    async def run():
        return await runner._handle_stream_request({"stream": True, "model": "minimax-m2"})

    status, response = asyncio.run(run())

    assert status == "success"
    assert response["choices"][0]["message"]["content"] == "Hello"
    assert response["choices"][0]["finish_reason"] == "stop"
    assert response["usage"] is not None
    assert response["usage"].model_dump() == real_usage.model_dump()


def test_stream_without_usage_chunk_yields_none_and_does_not_crash():
    """Regression guard: a stream that never sends a usage chunk (provider
    did not receive/support stream_options.include_usage) must still
    complete cleanly with usage=None, not raise.
    """
    chunks = [
        make_chunk(content="Hi"),
        make_chunk(finish_reason="stop"),
    ]

    runner = _make_runner()

    async def fake_create(**kwargs):
        return FakeStream(chunks)

    runner.client.chat.completions.create = fake_create

    async def run():
        return await runner._handle_stream_request({"stream": True, "model": "minimax-m2"})

    status, response = asyncio.run(run())

    assert status == "success"
    assert response["choices"][0]["message"]["content"] == "Hi"
    assert response["usage"] is None
