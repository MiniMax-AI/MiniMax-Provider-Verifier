"""Offline counterexamples for the shared M2-Her transport and verdicts."""

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from m2_her_format_check.exercises import exercise_contract, exercise_finish
from m2_her_format_check.helpers import (
    ChatClient,
    Settings,
    assert_accepted_or_failed,
    assert_request_failed,
    assert_success,
    sdk_request,
)


def client_for(tmp_path, response, **settings):
    return ChatClient(
        Settings(base_url="https://provider.invalid/tenant/v1", **settings),
        log_path=tmp_path / "audit.jsonl",
        transport=httpx.MockTransport(response),
    )


def completion(text="OK", reason="stop", tokens=1):
    return {
        "id": "reply",
        "created": 1,
        "object": "chat.completion",
        "model": "deployed",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": reason,
            }
        ],
        "usage": {
            "prompt_tokens": 2,
            "completion_tokens": tokens,
            "total_tokens": 2 + tokens,
        },
    }


@pytest.mark.parametrize("sdk", [False, True])
def test_routing_and_log_credentials(tmp_path, sdk):
    def capture(request):
        assert request.url.path == "/tenant/v1/chat/completions"
        assert request.url.params["ticket"] == "private-query-canary"
        assert request.headers["X-Vendor-Key"] == "private-header-canary"
        assert request.headers["Authorization"] == "Token private-auth-canary"
        assert json.loads(request.content)["model"] == "deployed"
        return httpx.Response(
            200, json=completion(), headers={"set-cookie": "private-cookie-canary"}
        )

    client = client_for(
        tmp_path,
        capture,
        style="openai",
        model="deployed",
        auth_type="none",
        extra_headers={
            "X-Vendor-Key": "private-header-canary",
            "Authorization": "Token private-auth-canary",
        },
        query_params={"ticket": "private-query-canary"},
    )
    messages = [{"role": "user", "content": "Hi"}]
    response = sdk_request(client, messages) if sdk else client.chat(messages)
    assert_success(response)
    line = client.log_path.read_text()
    assert "canary" not in line
    record = json.loads(line)
    assert record["url"] == "https://provider.invalid/tenant/v1/chat/completions"
    assert record["request"]["model"] == "deployed"
    assert record["response"]["body"]["choices"] == completion()["choices"]


def test_echoed_credential_withholds_all_body_copies(tmp_path):
    client = client_for(
        tmp_path,
        lambda _: httpx.Response(
            400, json={"error": {"message": "Bad key private-echo-canary"}}
        ),
        api_key="private-echo-canary",
    )
    assert_request_failed(client.request({}))
    record = json.loads(client.log_path.read_text())
    assert record["status"] == 400 and record["evidence_withheld"]
    assert "private-echo-canary" not in client.log_path.read_text()
    assert "response" not in record


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("fmt", ["json", "sse", "concatenated_json"])
def test_invalid_numbers_fail_every_verdict(tmp_path, constant, fmt):
    body = '{"error":{},"extra":' + constant + "}"
    if fmt == "sse":
        body = f"data: {body}\n\n"
    elif fmt == "concatenated_json":
        body = '{"error":{}}' + body
    client = client_for(
        tmp_path,
        lambda _: httpx.Response(
            200,
            text=body,
            headers={
                "content-type": "text/event-stream"
                if fmt == "sse"
                else "application/json"
            },
        ),
    )
    result = client.request({"stream": fmt == "sse"})
    for check in (assert_success, assert_request_failed, assert_accepted_or_failed):
        with pytest.raises(AssertionError):
            check(result)


@pytest.mark.parametrize("target", ["length", "ceiling"])
def test_natural_stops_do_not_prove_output_ceiling(tmp_path, target):
    client = client_for(tmp_path, lambda _: httpx.Response(200, json=completion()))
    with pytest.raises(pytest.skip.Exception):
        if target == "length":
            exercise_finish(client, stream=False, reason="length")
        else:
            exercise_contract(client, {}, {"outcome": "success", "completion_limit": 8})
    assert client.request_count == (2 if target == "length" else 3)


def test_invalid_truncation_still_fails_immediately(tmp_path):
    client = client_for(
        tmp_path, lambda _: httpx.Response(200, json=completion(reason="length"))
    )
    with pytest.raises(AssertionError):
        exercise_finish(client, stream=False, reason="length")
    assert client.request_count == 1


@pytest.mark.parametrize("workers", [[], ["-n", "2"]], ids=["serial", "xdist"])
def test_openai_without_compat_is_a_configuration_error(workers):
    env = {**os.environ, "M2_HER_API_STYLE": "openai"}
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *workers],
        capture_output=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        timeout=20,
    )
    assert run.returncode == pytest.ExitCode.USAGE_ERROR
    assert "--run-compat" in run.stderr


def test_entirely_skipped_live_selection_exits_nonzero():
    env = {
        **os.environ,
        "M2_HER_API_STYLE": "native",
        "M2_HER_AUTH_TYPE": "none",
        "M2_HER_BASE_URL": "http://127.0.0.1:1",
    }
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-k", "test_11_06"],
        capture_output=True,
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        timeout=20,
    )
    assert run.returncode == pytest.ExitCode.NO_TESTS_COLLECTED
    assert "No M2-Her live case produced a verdict" in run.stdout
