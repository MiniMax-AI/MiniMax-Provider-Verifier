"""Offline checks for cases that distinguish usable evidence from malformed streams."""

from types import SimpleNamespace

import pytest

from m2_her_format_check import m2_her_compat_tests as compat
from m2_her_format_check import m2_her_stream_tests as stream
from m2_her_format_check.helpers import Response, Settings


def response(start=None, finish=None, after=None, text="hello"):
    chunks = [
        {"choices": [{"index": 0, "delta": {"content": text}}], "usage": start},
        {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": finish,
        },
    ]
    if after is not None:
        chunks.append({"choices": [], "usage": after})
    return Response(
        status=200,
        headers={"content-type": "text/event-stream"},
        stream=True,
        events=[{"event": "message", "json": chunk} for chunk in chunks],
    )


def test_early_usage_does_not_prove_final_usage():
    result = response(start={"total_tokens": 2})
    with pytest.raises(AssertionError, match="at or after the finish event"):
        stream.TestStreamProtocol().test_14_08_stream_usage(
            SimpleNamespace(chat=lambda *args, **kwargs: result)
        )


@pytest.mark.parametrize("position", ["finish", "after"])
def test_usage_on_or_after_finish_counts(position):
    result = response(start={"total_tokens": 0}, **{position: {"total_tokens": 2}})
    stream.TestStreamProtocol().test_14_08_stream_usage(
        SimpleNamespace(chat=lambda *args, **kwargs: result)
    )


def test_valid_final_usage_does_not_hide_bad_early_usage(contract):
    result = response(start={"total_tokens": -99}, after={"total_tokens": 2})
    client = SimpleNamespace(
        settings=Settings(style="openai"), request=lambda payload: result
    )
    with pytest.raises(AssertionError, match="total_tokens"):
        compat.TestCompatibility().test_15_06_stream_extensions(
            contract, client, "include_usage_true", preflight=None
        )


@pytest.mark.parametrize("streaming", [False, True])
def test_openai_only_never_requests_native_path(streaming):
    client = SimpleNamespace(settings=Settings(style="openai"))
    with pytest.raises(pytest.skip.Exception, match="OpenAI-only"):
        compat.TestCompatibility().test_15_01_endpoint_sdk_compatibility(
            None, client, "native_http", streaming, preflight=None
        )


def test_emoji_stress_skips_missing_sample_but_fails_bad_stream(tmp_path):
    valid = response(text="no emoji here")
    results = iter([valid] * 20)
    client = SimpleNamespace(
        chat=lambda *args, **kwargs: next(results),
        settings=Settings(),
        case_id="14_11",
        log_path=tmp_path / "run.jsonl",
    )
    with pytest.raises(pytest.skip.Exception, match="0/20"):
        stream.TestStreamProtocol().test_14_11_repeated_emoji_integrity(client)
    results = iter([valid, Response(status=503, stream=True)])
    with pytest.raises(AssertionError, match="status=503"):
        stream.TestStreamProtocol().test_14_11_repeated_emoji_integrity(client)
