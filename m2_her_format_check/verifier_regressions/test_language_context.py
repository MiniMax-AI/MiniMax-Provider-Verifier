"""Offline counterexamples for language voting, window calibration and gateway fields."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from m2_her_format_check import m2_her_text_tests as live
from m2_her_format_check.helpers import Response, Settings, read_context_samples
from m2_her_format_check.language import language_report
from m2_her_format_check.scenarios import LANGUAGE_PROMPTS


def reply(text, *, prompt_tokens=7):
    body = {
        "id": "offline",
        "model": "M2-her",
        "created": 1,
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 1,
            "total_tokens": prompt_tokens + 1,
        },
    }
    return Response(status=200, body=body, raw_text=json.dumps(body))


@pytest.mark.parametrize(
    "expected,text,verdict",
    [
        ("ru", "На вихідних краще відпочити й прогулятися містом.", "mismatch"),
        ("ar", "برای آخر هفته کمی استراحت کن و به پارک برو.", "mismatch"),
        ("en", "Walk outdoors. Stretch gently. Nap.", "match"),
        ("en", "Try a walk. Αυτό είναι εξ ολοκλήρου ελληνικό κείμενο.", "mismatch"),
        ("en", "Rhythmic zephyrs.", "uncertain"),
        ("ru", "Краткий ответ.", "uncertain"),
        ("ar", "سلام", "uncertain"),
        ("zh_hant", "山川河流", "uncertain"),
        ("zh", "山", "uncertain"),
        ("ar", "وقت من", "uncertain"),
        ("ru", "Как или кога?", "uncertain"),
    ],
)
def test_language_counterexamples(expected, text, verdict):
    assert language_report(text, expected).verdict == verdict


@pytest.mark.parametrize("language,text", LANGUAGE_PROMPTS.items())
def test_target_languages_have_positive_signals(language, text):
    assert language_report(text, language).verdict == "match"


@pytest.mark.parametrize("case", ["single", "multi"])
@pytest.mark.parametrize(
    "outcomes,expected",
    [
        ("xux", "fail"),
        ("umx", "skip"),
        ("umm", "pass"),
        ("mm", "pass"),
        ("xx", "fail"),
        ("m!", "protocol"),
    ],
)
def test_language_vote(case, outcomes, expected):
    texts = {
        "u": "Rhythmic zephyrs.",
        "m": "Walk outdoors. Stretch gently.",
        "x": "你好，今天天气很好。",
    }
    responses = [
        reply(texts[c]) if c != "!" else Response(status=503) for c in outcomes
    ]
    client = Mock()
    client.chat.side_effect = responses
    test = live.TestLanguageConsistency()

    def run():
        if case == "single":
            test.test_19_01_reply_follows_user_language(client, False, "en")
        else:
            test.test_19_04_multiturn_language_retention(client, False, "zh", "en")

    if expected == "pass":
        run()
    else:
        exc = {
            "skip": pytest.skip.Exception,
            "fail": pytest.fail.Exception,
            "protocol": AssertionError,
        }[expected]
        with pytest.raises(exc):
            run()
    assert client.chat.call_count == len(outcomes)


def fixture_data():
    messages = [{"role": "user", "content": "背景记录。" * 8000}]
    return {
        "model": "M2-her",
        "counting": "input_plus_max_output",
        "source": "mock usage",
        "context_window_tokens": 64000,
        "within": {
            "messages": messages,
            "prompt_tokens": 63900,
            "max_completion_tokens": 64,
        },
        "over": {
            "messages": messages,
            "prompt_tokens": 63900,
            "max_completion_tokens": 2048,
        },
    }


@pytest.mark.parametrize(
    "part,key,value",
    [
        ("within", "prompt_tokens", 7),
        ("over", "messages", [None]),
        ("over", "messages", [{"role": "user", "content": "Different input"}]),
        ("over", "prompt_tokens", 63910),
    ],
)
def test_reject_invalid_window_evidence(tmp_path, part, key, value):
    data = fixture_data()
    data[part][key] = value
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data))
    with pytest.raises(AssertionError):
        read_context_samples(str(path), "M2-her")


@pytest.mark.parametrize("measured", [7, 63900])
def test_over_alone_measures_positive_control(tmp_path, measured):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture_data()))
    data = read_context_samples(str(path), "M2-her")
    reject = Response(status=400, raw_text="context exceeded")
    client = Mock()
    client.chat.side_effect = [reply("OK", prompt_tokens=measured), reject]
    test = live.TestLongContext()
    args = (data, lambda key: {"outcome": "reject"}, client, False, Mock())
    if measured != 63900:
        with pytest.raises(AssertionError, match="stale"):
            test.test_12_04_context_over_64k(*args)
        assert client.chat.call_count == 1
    else:
        test.test_12_04_context_over_64k(*args)
        assert [
            c.kwargs["max_completion_tokens"] for c in client.chat.call_args_list
        ] == [64, 2048]
        assert client.chat.call_args_list[0].args == client.chat.call_args_list[1].args


@pytest.mark.parametrize(
    "extra_headers,query_params",
    [
        ({"X-API-Key": "dummy"}, {}),
        ({"Cookie": "session=dummy"}, {}),
        ({}, {"access_token": "dummy"}),
        ({}, {"api-key": "dummy"}),
    ],
)
def test_bearer_negative_skips_independent_credentials(extra_headers, query_params):
    client = SimpleNamespace(
        settings=Settings(extra_headers=extra_headers, query_params=query_params)
    )
    preflight = Mock()
    with pytest.raises(pytest.skip.Exception, match="Additional authentication"):
        live.TestErrors().test_11_06_authentication_errors(
            client, False, "invalid", preflight
        )
    preflight.assert_not_called()


def test_bearer_negative_still_runs_with_routing_configuration():
    client = Mock()
    client.settings = Settings(
        extra_headers={"X-Route": "route"}, query_params={"GroupId": "group"}
    )
    client.request.return_value = Response(status=401, raw_text="unauthorized")
    live.TestErrors().test_11_06_authentication_errors(client, False, "missing", Mock())
    assert client.request.call_args.kwargs["headers"] == {
        "content-type": "application/json",
        "x-route": "route",
    }


@pytest.mark.parametrize("accepted", [False, True])
def test_metadata_checks_ascii_and_observes_utf8_bytes(tmp_path, accepted):
    client = Mock()
    client.settings = Settings()
    client.case_id = "offline"
    client.log_path = tmp_path / "metrics.jsonl"
    reject = Response(status=400, raw_text="too long")
    observed = reply("OK") if accepted else reject
    client.request.side_effect = [
        reply("OK"),
        observed,
        reject,
        observed,
        reject,
        observed,
    ]
    suite = live.TestRequestMetadata()
    suite.test_18_01_request_metadata_valid(client, False, "metadata_boundary")
    for variant in ("key", "value"):
        suite.test_18_03_metadata_length_boundary(client, False, variant, Mock())
    keys = [
        next(iter(call.args[0]["metadata"].items()))
        for call in client.request.call_args_list
    ]
    assert keys == [
        ("k" * 255, "v" * 255),
        ("键" * 85, "值" * 85),
        ("k" * 256, "v"),
        ("界" * 85 + "a", "v"),
        ("k", "v" * 256),
        ("k", "界" * 85 + "a"),
    ]
    measurements = [
        json.loads(line) for line in client.log_path.read_text().splitlines()
    ]
    assert [m["utf8_bytes"] for m in measurements] == [255, 256, 256]
    assert all(
        m["outcome"] == ("accepted" if accepted else "rejected") for m in measurements
    )


@pytest.mark.parametrize(
    "control,target,expected",
    [
        ("accepted", "rejected", "pass"),
        ("accepted", "accepted", "fail"),
        ("rejected", None, "skip"),
        ("fault", None, "fail"),
        ("malformed", None, "fail"),
    ],
)
def test_tool_conflict_requires_both_features_to_work(control, target, expected):
    double = reply("First")
    double.body["choices"].append(
        {
            "index": 1,
            "message": {"role": "assistant", "content": "Second"},
            "finish_reason": "stop",
        }
    )
    double.raw_text = json.dumps(double.body)
    responses = {
        "accepted": reply("OK"),
        "rejected": Response(status=400, raw_text="unsupported"),
        "fault": Response(status=503, raw_text="upstream unavailable"),
        "malformed": Response(
            status=200,
            headers={"content-type": "application/json"},
            raw_text='{"error":',
            errors=["invalid JSON response"],
        ),
    }
    client = Mock()
    client.settings = Settings()
    client.request.side_effect = [double, responses[control]] + (
        [responses[target]] if target else []
    )

    def run():
        live.TestCandidateCount().test_17_06_n_tools_conflict(client, Mock())

    if expected == "pass":
        run()
    else:
        with pytest.raises(
            pytest.skip.Exception if expected == "skip" else AssertionError
        ):
            run()
    payloads = [call.args[0] for call in client.request.call_args_list]
    assert payloads[0]["n"] == 2 and "tools" not in payloads[0]
    assert payloads[1]["n"] == 1 and payloads[1]["tools"]
    if target:
        assert payloads[2] == {**payloads[1], "n": 2}
    else:
        assert len(payloads) == 2
