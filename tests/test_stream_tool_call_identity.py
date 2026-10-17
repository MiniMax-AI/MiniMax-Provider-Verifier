"""Keep protocol validation in dedicated cases without gating shared request and parsing helpers."""
import importlib
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from m3_format_check.stream_protocol import inspect_stream_tool_calls


def delta(index=0, call_id=None, arguments="", name=None):
    return {"index": index, "id": call_id,
            "function": {"name": name, "arguments": arguments}}


def chunk(*calls, choice_index=0, finish_reason=None):
    return {"id": "chatcmpl-regression", "object": "chat.completion.chunk",
            "created": 1, "model": "test-model", "choices": [{
                "index": choice_index, "delta": {"tool_calls": list(calls)},
                "finish_reason": finish_reason}]}


def complete_stream(*chunks):
    return [*chunks, chunk(finish_reason="tool_calls"), {"_done": True}]


def valid_stream():
    return [
        chunk(delta(0, "call-a", '{"city":', "weather")),
        chunk(delta(1, "call-b", '{"city":', "weather")),
        chunk(delta(0, None, '"Beijing"}')),
        chunk(delta(1, "call-b", '"Shanghai"}'), finish_reason="tool_calls"),
        {"choices": [], "usage": {"total_tokens": 10}}, {"_done": True},
    ]


def test_interleaved_fragments_keep_stable_ids_and_sequential_new_indices():
    tracker = inspect_stream_tool_calls(valid_stream())
    assert tracker.errors == []
    assert [c["first_id"] for c in tracker.id_history] == ["call-a", "call-b"]


@pytest.mark.parametrize("chunks,code", [
    ([chunk(delta(1, "call-a"))], "tool_call_index_sequence"),
    ([chunk(delta(0, "call-a")), chunk(delta(2, "call-b"))], "tool_call_index_sequence"),
    ([chunk(delta(0, "call-a")), chunk(delta(1, "call-a"))], "tool_call_id_reused"),
    ([chunk(delta(0, "call-a")), chunk(delta(0, "call-b"))], "tool_call_id_changed"),
    ([chunk(delta(0, "call-a"), delta(0, "call-b"))], "tool_call_id_changed"),
    ([chunk(delta(None, "call-a"))], "tool_call_index_invalid"),
    ([chunk(delta(-1, "call-a"))], "tool_call_index_invalid"),
    ([chunk(delta(True, "call-a"))], "tool_call_index_invalid"),
    ([chunk(delta(0, None))], "tool_call_id_missing"),
    ([chunk(delta(0, "call-a"), choice_index=0),
      chunk(delta(0, "call-a"), choice_index=1)], "tool_call_id_reused"),
])
def test_protocol_violations_include_the_original_fragment_position(chunks, code):
    tracker = inspect_stream_tool_calls(chunks)
    error = next(e for e in tracker.errors if e["code"] == code)
    assert error["response_id"] == "chatcmpl-regression"
    assert "chunk_index" in error and "delta_index" in error


def test_different_choices_start_their_own_index_sequence():
    tracker = inspect_stream_tool_calls([
        chunk(delta(0, "call-a"), choice_index=0),
        chunk(delta(0, "call-b"), choice_index=1),
    ])
    assert tracker.errors == []


def test_id_history_keeps_both_original_and_conflicting_ids():
    tracker = inspect_stream_tool_calls([
        chunk(delta(0, "call-a")), chunk(delta(0, "call-b")),
    ])
    assert [o["id"] for o in tracker.id_history[0]["observations"]] == ["call-a", "call-b"]
    assert tracker.errors[0]["old_id"] == "call-a"
    assert tracker.errors[0]["new_id"] == "call-b"


@pytest.fixture
def helpers(monkeypatch):
    monkeypatch.setenv("M3_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("M3_AUTH_TYPE", "none")
    monkeypatch.syspath_prepend(str(ROOT / "m3_format_check"))
    return importlib.import_module("helpers")


@pytest.fixture
def mock_stream(helpers, monkeypatch):
    """Run oai_chat through an in-memory HTTP transport."""
    client_class = httpx.Client

    def install(chunks=None, status=200, *, responses=None):
        requests, records = [], []

        def handle_request(request):
            requests.append(json.loads(request.content))
            if status != 200:
                return httpx.Response(status, json={"error": "invalid request"})
            current_chunks = responses[len(requests) - 1] if responses is not None else chunks
            lines = [
                "data: [DONE]" if item.get("_done") else f"data: {json.dumps(item)}"
                for item in current_chunks
            ]
            return httpx.Response(
                200, headers={"Content-Type": "text/event-stream", "trace-id": "trace-isolated"},
                text="\n\n".join(lines) + "\n\n",
            )

        transport = httpx.MockTransport(handle_request)
        monkeypatch.setattr(helpers.httpx, "Client", lambda **kwargs: client_class(transport=transport, **kwargs))
        monkeypatch.setattr(helpers, "_write_log_line", records.append)
        return requests, records

    return install


def test_helpers_still_rebuild_valid_interleaved_calls(helpers):
    calls = helpers.get_tool_calls({"stream": True, "chunks": valid_stream()})
    assert [c["id"] for c in calls] == ["call-a", "call-b"]
    assert [c["arguments_obj"] for c in calls] == [{"city": "Beijing"}, {"city": "Shanghai"}]


@pytest.mark.parametrize("entry", ["get_tool_calls", "assert_oai_stream_success"])
def test_generic_helpers_do_not_gate_other_cases_on_identity(helpers, entry):
    chunks = complete_stream(
        chunk(delta(0, "call-a", '{"city":', "weather")),
        chunk(delta(0, "call-b", '"Beijing"}')),
    )
    result = getattr(helpers, entry)({"status": 200, "stream": True, "chunks": chunks})
    if entry == "get_tool_calls":
        assert result[0]["id"] == "call-b"
        assert result[0]["arguments_obj"] == {"city": "Beijing"}


def test_tool_extraction_keeps_legacy_missing_index_fallback(helpers):
    call = delta(0, "call-a", '{"city":"Beijing"}', "weather")
    del call["index"]
    calls = helpers.get_tool_calls({"stream": True, "chunks": complete_stream(chunk(call))})
    assert calls[0]["arguments_obj"] == {"city": "Beijing"}


@pytest.mark.parametrize("status,chunks", [
    (200, valid_stream()),
    (200, complete_stream(chunk())),
    (200, complete_stream(chunk(delta(0, "a")), chunk(delta(0, "b")))),
    (200, complete_stream(chunk(delta(0, "a"), delta(1, "a")))),
    (200, complete_stream(chunk(delta(1, "a")))),
    (400, []),
])
def test_oai_chat_returns_raw_protocol_issues_for_independent_cases(helpers, mock_stream, status, chunks):
    requests, records = mock_stream(chunks, status)
    result = helpers.oai_chat({"messages": [{"role": "user", "content": "weather"}]}, stream=True)
    assert result["status"] == status
    assert result["chunks"] == chunks
    if status == 400:
        assert result["body"] == {"error": "invalid request"}
    assert len(requests) == len(records) == 1
    assert "error" not in records[0]


@pytest.mark.parametrize("case_id", ["02_09", "02_10"])
@pytest.mark.parametrize("chunks,error09,error10", [
    (valid_stream(), None, None),
    (complete_stream(chunk(delta(0, "a"), delta(1, "b")), chunk(delta(0), delta(1, "b"))), None, None),
    (complete_stream(chunk(delta(0, "a"), delta(1, "b")), chunk(delta(0, "changed"))), None, "tool_call_id_changed"),
    (complete_stream(chunk(delta(0, "a"), delta(1, "a"))), None, "tool_call_id_reused"),
    (complete_stream(chunk(delta(0, "a"), delta(2, "b"))), None, "tool_call_index_sequence"),
    (complete_stream(chunk(delta(0), delta(1, "b"))), None, "tool_call_id_missing"),
    (complete_stream(chunk(delta(0, "a"), delta(0, "a"), delta(1, "b"))), "duplicate tool_call index", None),
    (complete_stream(chunk(delta(0, "a"), delta(0, "changed"))), "duplicate tool_call index", "tool_call_id_changed"),
    (complete_stream(chunk(delta(0, "a")), chunk(delta(0, "changed"))), "SKIP", "tool_call_id_changed"),
    (complete_stream(chunk(delta(0))), "SKIP", "tool_call_id_missing"),
    (complete_stream(chunk(delta(0, "a"), delta(0, "a"))), "duplicate tool_call index", "SKIP"),
    (complete_stream(chunk(delta(0, "a"), delta(1, "b")),
                     chunk(delta(0, "c"), delta(1, "d"), choice_index=1)), None, None),
    (complete_stream(), "SKIP", "SKIP"),
    (complete_stream(chunk(delta(0, "a"))), "SKIP", "SKIP"),
], ids=["valid", "interleaved", "id_changed", "id_reused", "index_gap", "missing_id",
        "duplicate_index", "duplicate_index_changed_id", "single_call_changed_id", "single_call_missing_id", "single_index_duplicated",
        "separate_choices", "no_calls", "single_call"])
def test_stream_protocol_cases_report_their_own_rule_once(helpers, mock_stream, case_id, chunks, error09, error10):
    stream_cases = importlib.import_module("m3_stream_tests")
    requests, records = mock_stream(chunks)
    names = {
        "02_09": "test_02_09_tool_call_index_unique_in_chunk",
        "02_10": "test_02_10_tool_call_identity_stable",
    }
    run_case = getattr(stream_cases.TestSSEStream(), names[case_id])
    expected_error = error09 if case_id == "02_09" else error10
    if expected_error == "SKIP":
        with pytest.raises(pytest.skip.Exception, match="parallel tool calls not observed"):
            run_case()
    elif expected_error:
        with pytest.raises(AssertionError, match=expected_error) as exc:
            run_case()
        assert case_id in str(exc.value)
        assert "trace-isolated" in str(exc.value)
        assert "response_id=chatcmpl-regression" in str(exc.value)
        assert "chunk_index" in str(exc.value)
    else:
        run_case()
    assert len(requests) == len(records) == 1
    assert requests[0]["stream"] is True
    assert requests[0]["parallel_tool_calls"] is True
    assert requests[0]["tool_choice"] == "auto"
    assert requests[0]["max_tokens"] == 64000
    assert requests[0]["reasoning_split"] is True
    prompt = requests[0]["messages"][0]["content"]
    assert "pwd && git status --short --branch && git branch --show-current && git log -5 --oneline" in prompt
    assert "**/AGENTS.md" in prompt and "请直接发出工具调用。" in prompt
    tools = {tool["function"]["name"]: tool["function"] for tool in requests[0]["tools"]}
    assert set(tools) == {"bash", "glob"}
    assert tools["bash"]["parameters"]["required"] == ["command"]
    assert tools["glob"]["parameters"]["required"] == ["pattern"]
    assert tools["bash"]["parameters"]["properties"]["timeout"] == {"type": "number"}
    assert tools["glob"]["parameters"]["properties"]["sort"]["enum"] == ["none", "modified"]
