"""Modules 01–13 and 16–19: M2-Her text cases. See docs/m2_her_text_cases.md.

Streaming is a fixture dimension, not a second set of copied test bodies.
All negative tests use request() so defaults cannot repair invalid payloads.
Expected values come from the official endpoint (observed.py). Invalid
requests only need to fail (assert_request_failed); values the docs rule out
but the official endpoint accepts may be either accepted or rejected.
"""

import json
import re
import copy

import pytest

from .helpers import (
    assert_contains,
    assert_contract,
    assert_accepted_or_failed,
    assert_envelope,
    assert_request_failed,
    assert_success,
    assert_sensitivity_fields,
    assert_usage,
    message,
    simple_messages,
)
from .exercises import (
    exercise_finish,
    recall_messages,
    record_measurement,
)
from .language import assert_language
from .observed import N_LIMIT
from .scenarios import (
    ESCAPED_TEXT,
    LANGUAGE_PROMPTS,
    all_roles,
    filler,
    history,
    sample_pairs,
    guide_messages,
    travel_conversation,
)

# 19_01 is P0: up to 3 attempts per variant, at least 2 must pass.
LANGUAGE_ATTEMPTS = 3
LANGUAGE_REQUIRED = 2


@pytest.fixture(params=[False, True], ids=["non_stream", "stream"])
def stream(request):
    return request.param


@pytest.fixture(params=[False, True], ids=["original_names", "all_named"])
def named(request):
    return request.param


def base_payload(client, stream=False):
    return {
        "model": client.settings.model,
        "messages": simple_messages(),
        "stream": stream,
        "max_completion_tokens": 32,
    }


class TestBasicText:
    def test_01_01_minimal_user_message(self, client, stream):
        """Minimal user-only text request returns an assistant answer."""
        assert_success(client.chat(simple_messages(), stream=stream))

    def test_01_02_system_user_chat(self, client, stream):
        """Ordinary system and user messages are accepted."""
        assert_success(
            client.chat(simple_messages("你好", "你是一个友好的助手。"), stream=stream)
        )

    @pytest.mark.behavior
    def test_01_03_chinese_text(self, client, stream):
        """A Chinese response contains CJK characters without decoding damage."""
        result = client.chat(
            simple_messages("请用中文写一句简短的问候。"),
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)
        assert re.search(r"[\u4e00-\u9fff]", result.content)
        assert "\ufffd" not in result.content

    @pytest.mark.behavior
    def test_01_04_english_text(self, client, stream):
        """An English-only short greeting contains Latin text."""
        result = client.chat(
            simple_messages("Write one short greeting in English only."),
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)
        assert re.search(r"[A-Za-z]+", result.content)
        assert not re.search(r"[\u4e00-\u9fff]", result.content)

    def test_01_05_text_escaping_unicode(self, client, stream):
        """Accept escaped Unicode input; transport decoding is checked independently."""
        result = client.chat(
            simple_messages(
                f"原样输出下面的文本，不添加说明或代码块：\n{ESCAPED_TEXT}"
            ),
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)

    @pytest.mark.parametrize(
        "text",
        ["こんにちは", "안녕하세요", "مرحبا", "Привет", "Cafe\u0301"],
        ids=["japanese", "korean", "arabic", "russian", "combining_accent"],
    )
    def test_01_06_multilingual_input(self, client, stream, text):
        """Accept multilingual strings without requiring translation or extraction."""
        result = client.chat(
            simple_messages(f"这是一句问候：{text}。请简单回应。"),
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)


class TestSystemPersona:
    @pytest.mark.behavior
    def test_02_01_system_identity(self, client, stream):
        """Read the assistant identity from system rather than the question."""
        result = client.chat(
            simple_messages("只返回你的身份编号。", "你的身份编号是 AI_K72。"),
            temperature=0.01,
            stream=stream,
        )
        assert_contains(result, "AI_K72")

    @pytest.mark.behavior
    def test_02_02_system_reply_prefix(self, client, stream):
        """System specifies a mechanically verifiable reply prefix."""
        result = client.chat(
            simple_messages("你好", "每条回复必须以 HER_REPLY: 开头。"),
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)
        assert result.content.startswith("HER_REPLY:")

    @pytest.mark.behavior
    def test_02_04_system_identity_multiturn(self, client, stream):
        """System identity remains available after unrelated history."""
        messages = [
            message("system", "你的身份编号是 AI_K72。"),
            *history(5)[:-1],
            message("user", "只返回你的身份编号。"),
        ]
        assert_contains(
            client.chat(messages, temperature=0.01, stream=stream), "AI_K72"
        )

    @pytest.mark.behavior
    def test_02_05_system_identity_isolation(self, client, stream):
        """Two independent requests do not share their system identity."""
        for identity, other in (("AI_K72", "AI_B19"), ("AI_B19", "AI_K72")):
            result = client.chat(
                simple_messages("只返回你的身份编号。", f"你的身份编号是 {identity}。"),
                temperature=0.01,
                stream=stream,
            )
            assert_contains(result, identity)
            assert other not in result.content


class TestUserSystem:
    @pytest.mark.behavior
    def test_03_01_user_system_identity(self, client, stream):
        """Read a short fact supplied only through user_system."""
        messages = [
            message("user_system", "用户身份编号是 USER_P38。"),
            message("user", "只返回用户身份编号。"),
        ]
        assert_contains(
            client.chat(messages, temperature=0.01, stream=stream), "USER_P38"
        )

    @pytest.mark.behavior
    def test_03_03_user_system_multiturn(self, client, stream):
        """User persona is retained alongside several conversation turns."""
        messages = [
            message("user_system", "用户所属的小组编号是 TEAM_L63。"),
            *history(5)[:-1],
            message("user", "只返回用户所属小组编号。"),
        ]
        assert_contains(
            client.chat(messages, temperature=0.01, stream=stream), "TEAM_L63"
        )

    def test_03_04_user_system_omitted(self, client, stream):
        """The user_system role is optional for ordinary conversation."""
        assert_success(
            client.chat(
                simple_messages("你好", "你是助手。"), temperature=0.01, stream=stream
            )
        )


class TestGroup:
    @pytest.mark.behavior
    def test_04_01_group_scene_name(self, client, stream):
        """Read a scene marker supplied only in group."""
        assert_contains(
            client.chat(
                [
                    message("group", "场景编号 SCENE_R64"),
                    message("user", "只返回当前场景编号。"),
                ],
                temperature=0.01,
                stream=stream,
            ),
            "SCENE_R64",
        )

    @pytest.mark.behavior
    def test_04_02_group_scene_isolation(self, client, stream):
        """The same question uses each independent request's scene."""
        for scene, other in (("SCENE_R64", "SCENE_N21"), ("SCENE_N21", "SCENE_R64")):
            result = client.chat(
                [
                    message("group", f"场景编号 {scene}"),
                    message("user", "只返回当前场景编号。"),
                ],
                temperature=0.01,
                stream=stream,
            )
            assert_contains(result, scene)
            assert other not in result.content

    def test_04_03_group_omitted(self, client, stream):
        """Group is not required to complete a normal request."""
        assert_success(client.chat(simple_messages(), temperature=0.01, stream=stream))


class TestSampleMessages:
    def test_05_01_single_sample_pair(self, client, stream):
        """A complete named example pair is accepted; style accuracy is separate."""
        result = client.chat(
            [*sample_pairs(named=True), message("user", "lemon", name="访客")],
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)

    def test_05_02_three_sample_pairs(self, client, stream):
        """Three complete named pairs follow the documented sampling guidance."""
        result = client.chat(
            [*sample_pairs(3, named=True), message("user", "lemon", name="访客")],
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)

    @pytest.mark.behavior
    def test_05_04_sample_vs_current_question(self, client, stream, named, preflight):
        """Answer the real input; unnamed sample messages must fail."""
        if not named:
            # The named version of the same messages is the healthy control.
            preflight(
                client,
                stream=stream,
                messages=[*sample_pairs(named=True), message("user", "kiwi", name="访客")],
            )
        result = client.chat(
            [
                *sample_pairs(named=named),
                message("user", "kiwi", **({"name": "访客"} if named else {})),
            ],
            temperature=0.01,
            stream=stream,
        )
        if not named:
            assert_request_failed(result)
            return
        assert_success(result)
        assert "kiwi" in result.content.casefold()

    def test_05_05_samples_with_real_history(self, client, stream):
        """Samples coexist with real history and the final user message."""
        messages = [
            *sample_pairs(2, named=True),
            message("user", "mango", name="访客"),
            message("assistant", "RESULT:MANGO", name="助手"),
            message("user", "kiwi", name="访客"),
        ]
        result = client.chat(messages, temperature=0.01, stream=stream)
        assert_success(result)


class TestNames:
    def test_06_01_name_omitted(self, client, stream):
        """Names are optional when no speaker disambiguation is needed."""
        assert_success(client.chat(simple_messages(), temperature=0.01, stream=stream))

    @pytest.mark.parametrize(
        "name", ["小林", "Alice", "Zoë🙂"], ids=["chinese", "english", "unicode"]
    )
    def test_06_02_name_unicode(self, client, stream, name):
        """Unicode name strings are accepted; name recall is not a type requirement."""
        result = client.chat(
            [message("user", "只返回这条消息发送者的 name。", name=name)],
            temperature=0.01,
            stream=stream,
        )
        assert_success(result)

    @pytest.mark.behavior
    def test_06_03_multiple_named_users(self, client, stream):
        """Facts are bound to user names rather than message order."""
        for first, second, expected in (
            ("Alice", "Bob", {"Alice": "PASS_A17", "Bob": "PASS_B29"}),
            ("Bob", "Alice", {"Alice": "PASS_B29", "Bob": "PASS_A17"}),
        ):
            messages = [
                message("user", "我的通行编号是 PASS_A17。", name=first),
                message("assistant", "已记住。"),
                message("user", "我的通行编号是 PASS_B29。", name=second),
                message("assistant", "已记住。"),
                message(
                    "user",
                    '只返回 JSON 对象，键必须是 "Alice" 和 "Bob"，值分别是对应发送者的通行编号。不要代码块。',
                    name="Alice",
                ),
            ]
            result = client.chat(messages, temperature=0.01, stream=stream)
            assert_success(result)
            assert json.loads(result.content) == expected

    @pytest.mark.behavior
    def test_06_04_multiple_named_assistants(self, client, stream):
        """Named assistant messages retain distinct facts."""
        for first, second, expected in (
            ("Alpha", "Beta", {"Alpha": "NOTE_A17", "Beta": "NOTE_B29"}),
            ("Beta", "Alpha", {"Alpha": "NOTE_B29", "Beta": "NOTE_A17"}),
        ):
            messages = [
                message("user", "请各位助手分别报告记录。"),
                message("assistant", "我的记录是 NOTE_A17。", name=first),
                message("user", "另一位助手呢？"),
                message("assistant", "我的记录是 NOTE_B29。", name=second),
                message(
                    "user",
                    '只返回 JSON 对象，键必须是 "Alpha" 和 "Beta"，值分别是对应助手的记录。不要代码块。',
                ),
            ]
            result = client.chat(messages, temperature=0.01, stream=stream)
            assert_success(result)
            assert json.loads(result.content) == expected


class TestMultiturn:
    @pytest.mark.behavior
    def test_07_01_two_turn_memory(self, client, stream):
        """Recall a fact from the preceding conversation turn."""
        messages = [
            message("user", "我的编号是 HER_M41。"),
            message("assistant", "已记住。"),
            message("user", "只返回我的编号。"),
        ]
        assert_contains(
            client.chat(messages, temperature=0.01, stream=stream), "HER_M41"
        )

    @pytest.mark.behavior
    def test_07_02_five_turn_facts(self, client, stream):
        """Read the first and last facts from five history turns."""
        assert_contains(
            client.chat(history(5), temperature=0.01, stream=stream),
            "HER_00_VALUE",
            "HER_04_VALUE",
        )

    @pytest.mark.behavior
    def test_07_03_twenty_turn_history(self, client, stream):
        """Read both ends of a twenty-turn history."""
        assert_contains(
            client.chat(history(20), temperature=0.01, stream=stream),
            "HER_00_VALUE",
            "HER_19_VALUE",
        )

    def test_07_04_actual_response_roundtrip(self, client, stream):
        """Feed a real first reply back as assistant history in this case."""
        messages = simple_messages("请记住我的编号 HER_M41，回复一句确认。")
        first = client.chat(messages, temperature=0.01, stream=stream)
        assert_success(first)
        messages += [
            message("assistant", first.content),
            message("user", "只返回我的编号。"),
        ]
        assert_success(client.chat(messages, temperature=0.01, stream=stream))

    @pytest.mark.behavior
    def test_07_05_latest_fact_correction(self, client, stream):
        """An explicit correction supersedes an earlier fact."""
        messages = [
            message("user", "我的编号是 OLD_K19。"),
            message("assistant", "记住了。"),
            message("user", "更正：我的编号是 NEW_T83。"),
            message("assistant", "已经更新。"),
            message("user", "只返回更正后的编号。"),
        ]
        result = client.chat(messages, temperature=0.01, stream=stream)
        assert_contains(result, "NEW_T83")
        assert "OLD_K19" not in result.content

    @pytest.mark.behavior
    def test_07_06_conversation_isolation(self, client, stream):
        """Separate requests keep separate conversation facts."""
        for code, other in (("CODE_A17", "CODE_B29"), ("CODE_B29", "CODE_A17")):
            messages = [
                message("user", f"暗号是 {code}。"),
                message("assistant", "记住了。"),
                message("user", "只返回暗号。"),
            ]
            result = client.chat(messages, temperature=0.01, stream=stream)
            assert_contains(result, code)
            assert other not in result.content


class TestSampling:
    def test_08_01_sampling_omitted(self, client, stream):
        """Neither sampling parameter is sent on the default path."""
        assert_success(client.request(base_payload(client, stream)))

    @pytest.mark.parametrize("value", [0.01, 0.5, 1.0])
    def test_08_02_temperature_valid(self, client, value):
        """Documented temperature values are accepted, without randomness claims."""
        assert_success(client.chat(simple_messages(), temperature=value))

    @pytest.mark.parametrize(
        "value",
        [0, -0.1, 1.01, "0.5", True],
        ids=["zero", "negative", "above_one", "string", "bool"],
    )
    def test_08_03_temperature_invalid(self, client, stream, value, preflight):
        """0 and 1.01 lie outside the documented (0, 1]: accept or reject both pass.

        Negative values and wrong types must fail.
        """
        preflight(client, stream=stream)
        result = client.request({**base_payload(client, stream), "temperature": value})
        if type(value) in (int, float) and value >= 0:
            assert_accepted_or_failed(result)
        else:
            assert_request_failed(result)

    @pytest.mark.parametrize("value", [0.01, 0.5, 0.95, 1.0])
    def test_08_04_top_p_valid(self, client, value):
        """The documented open-lower/closed-upper top_p range is accepted."""
        assert_success(client.chat(simple_messages(), top_p=value))

    @pytest.mark.parametrize(
        "value",
        [0, -0.1, 1.01, "0.95", True],
        ids=["zero", "negative", "above_one", "string", "bool"],
    )
    def test_08_05_top_p_invalid(self, client, stream, value, preflight):
        """top_p=0 lies outside the documented (0, 1]: accept or reject both pass.

        Other out-of-range values and wrong types must fail.
        """
        preflight(client, stream=stream)
        result = client.request({**base_payload(client, stream), "top_p": value})
        if type(value) is int and value == 0:
            assert_accepted_or_failed(result)
        else:
            assert_request_failed(result)


class TestCompletionLimit:
    def test_09_01_completion_limit_omitted(self, client, stream):
        """A raw request omits both max_tokens and max_completion_tokens."""
        payload = base_payload(client, stream)
        del payload["max_completion_tokens"]
        assert_success(client.request(payload))

    @pytest.mark.parametrize("limit", [1, 2, 32, 2047, 2048])
    def test_09_02_completion_limit_valid(self, client, stream, limit, check_limit):
        """Valid limits are accepted; a one-token answer may be empty."""
        check_limit(
            client.chat(simple_messages(), stream=stream, max_completion_tokens=limit),
            limit,
        )

    @pytest.mark.parametrize("value", [0, -1])
    def test_09_03_completion_limit_nonpositive(self, client, stream, value, preflight):
        """Nonpositive output limits: accepting or rejecting both pass, never 5xx."""
        preflight(client, stream=stream)
        assert_accepted_or_failed(
            client.request(
                {**base_payload(client, stream), "max_completion_tokens": value}
            ),
            nonempty=False,
        )

    @pytest.mark.parametrize(
        "value", [1.5, "32", True, None], ids=["fraction", "string", "bool", "null"]
    )
    def test_09_04_completion_limit_type(self, client, stream, value, preflight):
        """Fractions, strings and booleans must fail; null may be accepted or rejected."""
        preflight(client, stream=stream)
        result = client.request(
            {**base_payload(client, stream), "max_completion_tokens": value}
        )
        if value is None:
            assert_accepted_or_failed(result)
        else:
            assert_request_failed(result)

    def test_09_05_completion_length_truncation(self, client, stream, check_limit):
        """Prepared long continuations and budgets 8/1 exercise actual truncation."""
        exercise_finish(client, stream=stream, reason="length")


class TestResponseUsage:
    def test_10_01_response_envelope(self, client, stream):
        """Check response fields, object types and within-response identity."""
        result = client.chat(simple_messages(), stream=stream)
        assert_success(result)
        assert_envelope(
            result, model=client.settings.response_model or client.settings.model
        )

    def test_10_02_response_message(self, client):
        """A non-stream reply has assistant role and actual string content."""
        result = client.chat(simple_messages())
        assert_success(result)
        assert result.body["choices"][0]["message"]["role"] == "assistant"

    def test_10_03_finish_reason_stop(self, client, stream):
        """Few-shot short answers and budgets 128/512 exercise natural completion."""
        exercise_finish(client, stream=stream, reason="stop")

    @pytest.mark.parametrize("limit", [1, 32])
    def test_10_04_usage_total_tokens(self, client, stream, limit):
        """Usage must survive even the one-token output path."""
        result = client.chat(
            simple_messages(), stream=stream, max_completion_tokens=limit
        )
        assert_success(result, nonempty=limit > 1)
        assert_usage(result.usage)
        assert result.usage["total_tokens"] > 0

    def test_10_05_usage_breakdown_math(self, client, stream):
        """Validate the usage schema, checking arithmetic whenever breakdowns exist."""
        result = client.chat(simple_messages(), stream=stream)
        assert_success(result)
        assert_usage(result.usage)
        record_measurement(
            client,
            "optional_field_coverage",
            check="usage_breakdown",
            observed=[
                k for k in ("prompt_tokens", "completion_tokens") if k in result.usage
            ],
        )

    def test_10_06_sensitivity_field_types(self, client, stream):
        """Native sensitivity fields, when present, retain their declared types."""
        result = client.chat(simple_messages(), stream=stream)
        assert_success(result)
        observed = assert_sensitivity_fields(result)
        record_measurement(
            client,
            "optional_field_coverage",
            check="sensitivity_types",
            observed_values=observed,
        )

    @pytest.mark.parametrize("named", [False, True], ids=["basic", "seven_roles"])
    @pytest.mark.compat
    def test_10_07_prompt_tokens_across_modes(self, client, named, contract):
        """Each mode counts added history; optional equality is a separate override."""
        rule = contract(f"10_07/{'seven_roles' if named else 'basic'}")
        assert rule["outcome"] == "success", (
            "Input-accounting checks require a successful request baseline"
        )
        messages = all_roles(named=True) if named else simple_messages()
        extended = copy.deepcopy(messages)
        extended[-1]["content"] = (
            "背景资料：" + "河流与山林。" * 256 + "\n" + extended[-1]["content"]
        )
        counts = []
        for stream in (False, True):
            pair = []
            for inputs in (messages, extended):
                result = client.chat(
                    inputs, stream=stream, temperature=0.01, max_completion_tokens=32
                )
                assert_success(result)
                assert_usage(result.usage, breakdown=True)
                pair.append(result.usage["prompt_tokens"])
            assert 0 < pair[0] < pair[1], (
                f"Added input must increase prompt_tokens in mode stream={stream}: {pair}"
            )
            counts.append(pair)
        if rule.get("prompt_tokens_equal"):
            assert counts[0] == counts[1], (
                f"Configured cross-mode equality violated: {counts}"
            )
        record_measurement(
            client,
            "input_accounting",
            counts=counts,
            equality_required=bool(rule.get("prompt_tokens_equal")),
        )


class TestErrors:
    @pytest.mark.parametrize(
        "variant", ["missing", "unknown", "empty", "null", "number"]
    )
    def test_11_01_invalid_model(self, client, stream, variant, preflight):
        """A missing model must not be repaired by the helper."""
        preflight(client, stream=stream)
        payload = base_payload(client, stream)
        if variant == "missing":
            del payload["model"]
        else:
            payload["model"] = {
                "unknown": "m2-her-format-check-nonexistent-model",
                "empty": "",
                "null": None,
                "number": 42,
            }[variant]
        assert_request_failed(client.request(payload))

    @pytest.mark.parametrize("variant", ["missing", "null", "string", "object"])
    def test_11_02_invalid_messages(self, client, stream, variant, preflight):
        """Missing/null/non-array messages are structured request errors."""
        preflight(client, stream=stream)
        payload = base_payload(client, stream)
        if variant == "missing":
            del payload["messages"]
        else:
            payload["messages"] = {"null": None, "string": "hello", "object": {}}[
                variant
            ]
        assert_request_failed(client.request(payload))

    @pytest.mark.parametrize("variant", ["missing", "unknown", "number"])
    def test_11_03_invalid_role(self, client, variant, preflight):
        """Unknown or non-string role fields are rejected."""
        preflight(client, stream=False)
        item = {"content": "Hello"}
        if variant != "missing":
            item["role"] = "her_invalid_role" if variant == "unknown" else 42
        assert_request_failed(client.request({**base_payload(client), "messages": [item]}))

    @pytest.mark.parametrize(
        "variant",
        [
            "missing",
            "null",
            "number",
            "object",
            "text_parts",
            "image",
            "video",
            "audio",
        ],
    )
    def test_11_04_invalid_content(self, client, variant, preflight):
        """Non-string or missing content must fail, regardless of error code or framing."""
        preflight(client, stream=False)
        if client.settings.style != "native":
            pytest.skip(
                "OpenAI content-parts acceptance belongs to endpoint contract verification"
            )
        item = {"role": "user"}
        values = {
            "null": None,
            "number": 42,
            "object": {},
            "text_parts": [{"type": "text", "text": "Hello"}],
            "image": [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,aGVy"},
                }
            ],
            "video": [
                {
                    "type": "video_url",
                    "video_url": {"url": "data:video/mp4;base64,aGVy"},
                }
            ],
            "audio": [
                {
                    "type": "input_audio",
                    "input_audio": {"data": "aGVy", "format": "wav"},
                }
            ],
        }
        if variant != "missing":
            item["content"] = values[variant]
        result = client.request({**base_payload(client), "messages": [item]})
        assert_request_failed(result)

    @pytest.mark.parametrize("value", [42, {}, []], ids=["number", "object", "array"])
    def test_11_05_invalid_name_type(self, client, value, preflight):
        """Non-string speaker names are parameter errors."""
        preflight(client, stream=False)
        assert_request_failed(
            client.request(
                {
                    **base_payload(client),
                    "messages": [message("user", "Hi", name=value)],
                }
            )
        )

    @pytest.mark.parametrize("variant", ["missing", "invalid"])
    def test_11_06_authentication_errors(self, client, stream, variant, preflight):
        """Explicit headers bypass default authorization, including extra headers."""
        if client.settings.auth_type != "bearer":
            pytest.skip(
                "Bearer authentication is not configured; authentication not validated"
            )
        preflight(client, stream=stream)
        headers = {
            k: v
            for k, v in client.settings.headers.items()
            if k.lower() != "authorization"
        }
        if variant == "invalid":
            headers["Authorization"] = (
                "Bearer intentionally-invalid-m2-her-format-check"
            )
        assert_request_failed(
            client.request(base_payload(client, stream), headers=headers)
        )

    @pytest.mark.parametrize(
        "variant", ["json", "array", "stream_string", "stream_number"]
    )
    def test_11_07_invalid_request_envelope(self, client, variant, preflight):
        """Malformed JSON and invalid envelopes remain invalid on the wire."""
        preflight(client, stream=False)
        if variant == "json":
            result = client.request(raw=b'{"messages":')
        elif variant == "array":
            result = client.request([])
        else:
            result = client.request(
                {
                    **base_payload(client),
                    "stream": "true" if variant == "stream_string" else 1,
                }
            )
        assert_request_failed(result)

    @pytest.mark.parametrize(
        "role,alias",
        [
            ("sample_message_user", "user_sample_message"),
            ("sample_message_ai", "ai_sample_message"),
        ],
        ids=["old_user_sample", "old_ai_sample"],
    )
    def test_11_08_legacy_sample_role_spelling(
        self, client, stream, role, alias, preflight
    ):
        """Old overseas cases used reversed role names, not today's canonical roles."""
        if client.settings.style != "native":
            pytest.skip("Canonical seven-role rejection is scoped to native API")
        messages = [*sample_pairs(named=True), message("user", "kiwi", name="访客")]
        preflight(client, stream=stream, messages=messages)
        invalid = copy.deepcopy(messages)
        next(item for item in invalid if item["role"] == role)["role"] = alias
        assert_request_failed(
            client.request({**base_payload(client, stream), "messages": invalid})
        )

    @pytest.mark.parametrize(
        "item", [None, "hello", 42, []], ids=["null", "string", "number", "array"]
    )
    def test_11_09_invalid_message_item(self, client, stream, item, preflight):
        """Every non-object element inside messages must fail."""
        preflight(client, stream=stream)
        assert_request_failed(
            client.request({**base_payload(client, stream), "messages": [item]})
        )


@pytest.mark.slow
class TestLongContext:
    def test_12_01_long_system(self, client, stream):
        """A modest long system input is not claimed to be an exact token boundary."""
        system = (
            "开头暗号 BEGIN_S72。\n"
            + filler(250)
            + "\n中间暗号 MIDDLE_S83。\n"
            + filler(250)
            + "\n末尾暗号 END_S94。"
        )
        assert_success(
            client.chat(
                simple_messages("请简单回应这些背景记录。", system),
                temperature=0.01,
                stream=stream,
            ),
        )

    @pytest.mark.parametrize("role", ["user_system", "sample_message_ai"])
    def test_12_02_long_persona_and_samples(self, client, stream, role):
        """Long persona/sample text is accepted; examples are not a factual memory store."""
        messages = (
            [message("sample_message_user", "介绍背景记录。", name="访客")]
            if role == "sample_message_ai"
            else []
        )
        messages += [
            message(
                role,
                "开头暗号 BEGIN_P38。\n"
                + filler(250)
                + "\n中间暗号 MIDDLE_P49。\n"
                + filler(250)
                + "\n末尾暗号 END_P50。",
                name="助手" if role == "sample_message_ai" else "访客",
            ),
            message("user", "请简单回应这些背景记录。", name="访客"),
        ]
        assert_success(client.chat(messages, temperature=0.01, stream=stream))

    def test_12_03_context_within_64k(self, context_samples, client, stream):
        """Use an externally measured sample rather than estimating tokens from chars."""
        sample = context_samples["within"]
        result = client.chat(
            sample["messages"],
            temperature=0.01,
            stream=stream,
            max_completion_tokens=sample["max_completion_tokens"],
        )
        assert_success(result)
        if result.usage and "prompt_tokens" in result.usage:
            assert_usage(result.usage, breakdown=True)
            if result.usage["prompt_tokens"] != sample["prompt_tokens"]:
                raise AssertionError(
                    "Measured prompt count changed; context calibration is stale"
                )

    def test_12_04_context_over_64k(
        self, context_samples, contract, client, stream, preflight
    ):
        """Over-window behavior requires measured input and a per-mode observed contract."""
        rule = contract(f"12_04/over_context/{'stream' if stream else 'non_stream'}")
        if rule["outcome"] != "success":
            preflight(client, stream=stream)
        if rule["outcome"] == "success":
            assert rule.get("contains"), (
                "accepted truncation must specify the retained answer marker"
            )
        sample = context_samples["over"]
        assert_contract(
            client.chat(
                sample["messages"],
                temperature=0.01,
                stream=stream,
                max_completion_tokens=sample["max_completion_tokens"],
            ),
            rule,
        )


class TestCombinations:
    def test_13_01_all_seven_roles(self, client, stream, named, preflight):
        """Named seven roles succeed; the guide's unnamed advanced roles must fail."""
        if not named:
            preflight(client, stream=stream, messages=all_roles(named=True))
        result = client.chat(all_roles(named=named), temperature=0.01, stream=stream)
        if named:
            assert_success(result)
        else:
            assert_request_failed(result)

    @pytest.mark.behavior
    def test_13_02_persona_samples_named_history(self, client, stream):
        """All six values in the requested order; the RESULT: prefix is optional."""
        messages = all_roles(named=True)[:-1] + [
            message("user", "我的物品编号是 ITEM_A73。", name="访客"),
            message("assistant", "已记住。", name="助手"),
            message("user", "我的物品编号是 ITEM_B84。", name="来客"),
            message("assistant", "已记住。", name="助手"),
            message(
                "user",
                "使用 RESULT: 前缀，依次返回助手身份、用户人设编号、场景编号、历史暗号、访客物品编号、来客物品编号。用|分隔，不加解释。",
                name="访客",
            ),
        ]
        result = client.chat(messages, temperature=0.01, stream=stream)
        assert_success(result)
        # Formatting is not the target: tolerate the prefix, spaces and a trailing |.
        values = [
            v.strip()
            for v in result.content.strip().removeprefix("RESULT:").strip("| ").split("|")
        ]
        assert values == [
            "AI_K72", "USER_P38", "SCENE_R64", "CODE_V59", "ITEM_A73", "ITEM_B84"
        ], result.content

    def test_13_03_long_history_small_output(self, client, stream, check_limit):
        """Long history plus a short output budget obeys the token ceiling."""
        result = client.chat(
            history(20), temperature=0.01, stream=stream, max_completion_tokens=64
        )
        check_limit(result, 64)

    def test_13_04_roles_with_sampling(self, client, stream):
        """The full role combination works with explicit legal sampling values."""
        result = client.chat(
            all_roles(named=True), stream=stream, temperature=0.5, top_p=0.95
        )
        assert_success(result)

    @pytest.mark.parametrize(
        "role", ["user_system", "group", "sample_message_user", "sample_message_ai"]
    )
    def test_13_05_one_special_name_omitted(self, client, stream, role, preflight):
        """Dropping any single advanced-role name must make the request fail."""
        preflight(client, stream=stream, messages=all_roles(named=True))
        messages = all_roles(named=True)
        next(item for item in messages if item["role"] == role).pop("name")
        result = client.chat(messages, stream=stream, temperature=0.01)
        assert_request_failed(result)


class TestGuideAlignment:
    @pytest.mark.parametrize("scenario", ["basic", "roleplay", "samples"])
    def test_16_01_guide_role_structures(
        self, client, stream, named, scenario, preflight
    ):
        """Guide structures succeed when named; the guide's unnamed advanced roles must fail."""
        if not named and scenario != "basic":
            preflight(
                client, stream=stream, messages=guide_messages(scenario, named=True)
            )
        result = client.chat(guide_messages(scenario, named=named), stream=stream)
        if named or scenario == "basic":
            assert_success(result)
        else:
            assert_request_failed(result)

    @pytest.mark.slow
    @pytest.mark.behavior
    def test_16_04_context_recall(self, client, stream):
        """Recall independent markers at the beginning, middle and end of 800 records."""
        result = client.chat(
            recall_messages(),
            stream=stream,
            temperature=0.01,
            max_completion_tokens=128,
        )
        assert_contains(result, "BEGIN_P38", "MIDDLE_P49", "END_P50")


@pytest.mark.implementation
class TestCandidateCount:
    """Native n returns n candidates; the observed deployment limit is documented
    in docs/m2_her_text_cases.md. No reward ranking or uniqueness guarantee.
    """

    @pytest.mark.parametrize("variant", ["omitted", "null", "zero", "negative"])
    def test_17_01_n_default_single_choice(self, client, stream, variant, preflight):
        """Omitted n returns one reply; null/0/-1 may be accepted (as one) or rejected."""
        request = base_payload(client, stream)
        if variant == "omitted":
            result = client.request(request)
            assert_success(result)
        else:
            preflight(client, stream=stream)
            request["n"] = {"null": None, "zero": 0, "negative": -1}[variant]
            result = client.request(request)
            if assert_accepted_or_failed(result) == "rejected":
                return
        assert_envelope(
            result, model=client.settings.response_model or client.settings.model
        )

    @pytest.mark.parametrize("n", [1, 2])
    def test_17_02_n_candidate_count(self, client, n):
        """A successful request must return exactly n complete, indexed candidates."""
        result = client.request({**base_payload(client), "n": n})
        assert_success(result, expected_choices=n)
        assert_envelope(
            result, model=client.settings.response_model or client.settings.model
        )

    def test_17_03_n_one_stream(self, client):
        """Explicit n=1 retains the native single-candidate SSE contract."""
        result = client.request({**base_payload(client, stream=True), "n": 1})
        assert_success(result)
        assert_envelope(
            result, model=client.settings.response_model or client.settings.model
        )

    @pytest.mark.parametrize(
        "value",
        [1.5, "2", True, False, {}, [], 9223372036854775808],
        ids=[
            "fraction",
            "string",
            "true",
            "false",
            "object",
            "array",
            "int64_overflow",
        ],
    )
    def test_17_04_n_invalid_type(self, client, stream, value, preflight):
        """The request decoder requires an int64, not strings, booleans or containers."""
        preflight(client, stream=stream)
        assert_request_failed(client.request({**base_payload(client, stream), "n": value}))

    def test_17_05_n_stream_conflict(self, client, preflight):
        """Prove the non-stream n=2 path, then require stream + n=2 to fail."""
        preflight(client, stream=True)
        request = {**base_payload(client), "n": 2}
        assert_success(client.request(request), expected_choices=2)
        assert_contract(
            client.request({**request, "stream": True}),
            {"outcome": "reject"},
        )

    def test_17_06_n_tools_conflict(self, client, preflight):
        """Prove the non-stream n=2 path, then require n=2 + tools to fail."""
        preflight(client, stream=False)
        request = {**base_payload(client), "n": 2}
        assert_success(client.request(request), expected_choices=2)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "ping",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        assert_contract(
            client.request({**request, "tools": tools}),
            {"outcome": "reject"},
        )

    @pytest.mark.parametrize("token_field", ["max_tokens", "max_completion_tokens"])
    def test_17_07_n_with_roles_and_parameters(self, client, token_field):
        """Multi-candidate output coexists with seven named roles and sampling fields.

        Token aliases are sent separately. Aggregate usage is not misread as a
        per-candidate token count; actual budget enforcement has separate cases.
        """
        result = client.request(
            {
                "model": client.settings.model,
                "messages": all_roles(named=True),
                "stream": False,
                "n": 2,
                "temperature": 0.7,
                "top_p": 0.95,
                token_field: 100,
            }
        )
        assert_success(result, expected_choices=2)
        assert_envelope(
            result, model=client.settings.response_model or client.settings.model
        )

    @pytest.mark.parametrize("variant", ["at_limit", "above_limit"])
    def test_17_08_n_configured_boundary(self, client, n_limit, variant):
        """n=4 (the official limit) succeeds; n=5 must fail.

        --n-limit replaces the observed boundary for another deployment.
        """
        limit = N_LIMIT if n_limit is None else n_limit
        request = {**base_payload(client), "n": limit}
        # The max request is also the healthy control for the next step.
        assert_success(client.request(request), expected_choices=limit)
        if variant == "above_limit":
            assert_request_failed(client.request({**request, "n": limit + 1}))


@pytest.mark.implementation
class TestRequestMetadata:
    """Shared gateway fields: validate acceptance/types, not model or moderation effects."""

    @pytest.mark.parametrize(
        "variant", ["metadata", "metadata_boundary", "user", "mask_on", "mask_off"]
    )
    def test_18_01_request_metadata_valid(self, client, stream, variant):
        """Harmless text probes cover metadata, logging-only user, and mask flag types."""
        fields = {
            "metadata": {"metadata": {"case": "HER-18_01", "语言": "中文"}},
            "metadata_boundary": {"metadata": {"k" * 255: "v" * 255}},
            "user": {"user": "format-check-user"},
            "mask_on": {"mask_sensitive_info": True},
            "mask_off": {"mask_sensitive_info": False},
        }[variant]
        result = client.request({**base_payload(client, stream), **fields})
        assert_success(result)
        assert_envelope(
            result, model=client.settings.response_model or client.settings.model
        )

    @pytest.mark.parametrize(
        "field,value",
        [
            ("metadata", "invalid"),
            ("metadata", []),
            ("metadata", {"case": 1}),
            ("user", 42),
            ("user", {}),
            ("mask_sensitive_info", "true"),
            ("mask_sensitive_info", 1),
        ],
        ids=[
            "metadata_string",
            "metadata_array",
            "metadata_number_value",
            "user_number",
            "user_object",
            "mask_string",
            "mask_number",
        ],
    )
    def test_18_02_request_metadata_invalid_type(
        self, client, stream, field, value, preflight
    ):
        """Malformed gateway field types must produce structured parameter errors."""
        preflight(client, stream=stream)
        assert_request_failed(client.request({**base_payload(client, stream), field: value}))

    @pytest.mark.parametrize("variant", ["key", "value"])
    def test_18_03_metadata_length_boundary(self, client, stream, variant, preflight):
        """A 256-byte ASCII key/value exceeds the gateway's 255-byte limit."""
        preflight(client, stream=stream)
        metadata = {"k" * 256: "v"} if variant == "key" else {"k": "v" * 256}
        assert_contract(
            client.request({**base_payload(client, stream), "metadata": metadata}),
            {"outcome": "reject"},
        )


class TestLanguageConsistency:
    """A chat reply stays in the user's language unless a reply language is required.

    Unlike 01_06's quoted greetings, every user turn here is monolingual, so the
    expected language is unambiguous. language.py applies deterministic script,
    variant and function-word rules; this is a behavior target, not wire format.
    """

    @pytest.mark.behavior
    @pytest.mark.parametrize(
        "language",
        ["zh", "zh_hant", "en", "ja", "ko", "es", "fr", "de", "pt", "ru", "ar"],
    )
    def test_19_01_reply_follows_user_language(self, client, stream, language):
        """A monolingual user turn is answered in that language without foreign spans.

        P0 behavior with rare sampling slips: up to 3 attempts, 2 must pass.
        Request or format errors fail at once and are never retried.
        """
        passed, failures = 0, []
        for attempt in range(1, LANGUAGE_ATTEMPTS + 1):
            result = client.chat(
                [message("user", LANGUAGE_PROMPTS[language])],
                temperature=0.01,
                stream=stream,
            )
            assert_success(result)
            try:
                assert_language(result, language)
                passed += 1
            except AssertionError as exc:
                failures.append(f"attempt {attempt}: {exc}")
            if passed >= LANGUAGE_REQUIRED:
                return
            if len(failures) > LANGUAGE_ATTEMPTS - LANGUAGE_REQUIRED:
                break
        raise AssertionError(
            f"{passed}/{LANGUAGE_ATTEMPTS} replies in {language}, "
            f"need {LANGUAGE_REQUIRED}: " + " | ".join(failures)
        )

    @pytest.mark.behavior
    @pytest.mark.parametrize(
        "persona,language",
        [
            ("zh", "en"),
            ("zh", "ja"),
            ("zh", "ko"),
            ("en", "zh"),
            ("en", "ja"),
            ("en", "ko"),
            ("ja", "zh"),
            ("ja", "en"),
            ("ja", "ko"),
            ("ko", "zh"),
            ("ko", "en"),
            ("ko", "ja"),
        ],
        ids=[
            "zh_persona-en_user",
            "zh_persona-ja_user",
            "zh_persona-ko_user",
            "en_persona-zh_user",
            "en_persona-ja_user",
            "en_persona-ko_user",
            "ja_persona-zh_user",
            "ja_persona-en_user",
            "ja_persona-ko_user",
            "ko_persona-zh_user",
            "ko_persona-en_user",
            "ko_persona-ja_user",
        ],
    )
    def test_19_04_multiturn_language_retention(
        self, client, stream, persona, language
    ):
        """A persona in one language does not pull a multi-turn conversation into it.

        The system is in the persona language; three real turns and the follow-up
        are in the user's language. Every ordered pair of zh/en/ja/ko is covered.
        """
        result = client.chat(
            travel_conversation(persona, language, "rainy_day", language),
            temperature=0.01,
            stream=stream,
        )
        assert_language(result, language)
