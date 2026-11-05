"""Module 15: executable project acceptance targets with per-provider overrides."""

from dataclasses import replace

import pytest

from .helpers import (
    ChatClient,
    assert_contract,
    message,
    request_failed,
    sdk_request,
    simple_messages,
)
from .scenarios import all_roles, sample_pairs
from .exercises import exercise_contract, continuation_messages, sample_packet_stream

pytestmark = pytest.mark.compat


def payload(client, **params):
    return {
        "model": client.settings.model,
        "messages": simple_messages(),
        "max_completion_tokens": 128,
        **params,
    }


def assert_confirmed_contract(result, rule):
    assert_contract(result, rule)


class TestCompatibility:
    @pytest.mark.parametrize("variant", ["native_http", "openai_http", "openai_sdk"])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_01_endpoint_sdk_compatibility(
        self, contract, client, variant, stream, preflight
    ):
        """Compare protocol/SDK paths using all seven roles and explicit expectations."""
        rule = contract(f"15_01/{variant}/{'stream' if stream else 'non_stream'}")
        style = "native" if variant == "native_http" else "openai"
        alternate = ChatClient(
            replace(client.settings, style=style),
            case_id=client.case_id,
            log_path=client.log_path,
        )
        if rule["outcome"] != "success":
            preflight(alternate, stream=stream)
        if variant == "openai_sdk":
            result = sdk_request(alternate, all_roles(named=True), stream=stream)
        else:
            result = alternate.chat(all_roles(named=True), stream=stream)
        assert_confirmed_contract(result, rule)

    @pytest.mark.parametrize(
        "variant,limits",
        [
            ("legacy_only", {"max_tokens": 16}),
            ("legacy_smaller", {"max_tokens": 8, "max_completion_tokens": 32}),
            ("completion_smaller", {"max_tokens": 32, "max_completion_tokens": 8}),
        ],
    )
    def test_15_02_legacy_token_parameters(
        self, contract, client, variant, limits, preflight
    ):
        """Explicit limits test alias precedence, rather than mere HTTP acceptance."""
        rule = contract(f"15_02/{variant}")
        if rule["outcome"] != "success":
            preflight(client, stream=False)
        if rule["outcome"] == "success":
            assert "completion_limit" in rule, (
                "accepted alias needs a confirmed completion_limit"
            )
        exercise_contract(
            client,
            {
                "model": client.settings.model,
                "messages": continuation_messages(),
                **limits,
            },
            rule,
        )

    @pytest.mark.parametrize("limit", [2049, 4096])
    def test_15_03_completion_limit_above_2048(
        self, contract, client, limit, preflight
    ):
        """Record rejection or validate an explicitly confirmed capped output."""
        rule = contract(f"15_03/{limit}")
        if rule["outcome"] != "success":
            preflight(client, stream=False)
        if rule["outcome"] == "success":
            assert rule.get("completion_limit") == 2048, (
                "accepted oversized budget needs a confirmed 2048 cap"
            )
        exercise_contract(
            client,
            payload(
                client, messages=continuation_messages(), max_completion_tokens=limit
            ),
            rule,
        )

    @pytest.mark.parametrize(
        "variant",
        [
            "empty_messages",
            "empty_content",
            "whitespace",
            "system_name_only",
            "system_only",
        ],
    )
    def test_15_04_empty_and_name_only_messages(
        self, contract, client, variant, preflight
    ):
        """Empty input and the specification's name-only system example are separate variants."""
        rule = contract(f"15_04/{variant}")
        if rule["outcome"] != "success":
            preflight(client, stream=False)
        messages = {
            "empty_messages": [],
            "empty_content": [message("user", "")],
            "whitespace": [message("user", " \n\t ")],
            "system_name_only": [
                {"role": "system", "name": "MiniMax AI"},
                message("user", "Hi"),
            ],
            "system_only": [message("system", "你是一个友好的助手。", name="助手")],
        }[variant]
        assert_confirmed_contract(
            client.request(payload(client, messages=messages)), rule
        )

    @pytest.mark.parametrize(
        "variant",
        [
            "multiple_system",
            "consecutive_user",
            "consecutive_assistant",
            "sample_user_only",
            "sample_ai_only",
            "role_order",
        ],
    )
    def test_15_05_role_order_and_sample_pairing(
        self, contract, client, variant, preflight
    ):
        """Each concrete ordering/pairing input uses its bundled or overridden rule."""
        rule = contract(f"15_05/{variant}")
        if rule["outcome"] != "success":
            preflight(client, stream=False)
        messages = {
            "multiple_system": [
                message("system", "你的身份是 FIRST_A17。"),
                message("system", "你的身份是 LAST_B29。"),
                message("user", "只返回你的身份编号。"),
            ],
            "consecutive_user": [
                message("user", "记住编号 USER_P38。"),
                message("user", "只返回编号。"),
            ],
            "consecutive_assistant": [
                message("user", "报告编号。"),
                message("assistant", "编号为 USER_P38。"),
                message("assistant", "补充说明完毕。"),
                message("user", "只返回编号。"),
            ],
            "sample_user_only": [sample_pairs()[0], message("user", "Hi")],
            "sample_ai_only": [sample_pairs()[1], message("user", "Hi")],
            "role_order": [
                message("user", "你好"),
                message("group", "场景编号 SCENE_R64"),
                message("user_system", "用户编号 USER_P38"),
                message("user", "只返回场景和用户编号。"),
            ],
        }[variant]
        if rule["outcome"] == "success" and variant == "multiple_system":
            assert rule.get("contains"), (
                "multiple-system success must specify the expected precedence marker"
            )
        assert_confirmed_contract(client.chat(messages), rule)

    @pytest.mark.parametrize(
        "variant", ["omitted", "include_usage_true", "include_usage_false"]
    )
    def test_15_06_stream_extensions(self, contract, client, variant, preflight):
        """DONE, summary and usage expectations are defined per endpoint and option."""
        rule = contract(f"15_06/{client.settings.style}/{variant}")
        if rule["outcome"] != "success":
            preflight(client, stream=True)
        request = payload(client, stream=True)
        if variant != "omitted":
            request["stream_options"] = {
                "include_usage": variant == "include_usage_true"
            }
        result = client.request(request)
        assert_confirmed_contract(result, rule)
        if rule.get("usage_only_last") and not request_failed(result):
            assert result.chunks[-1].get("usage") is not None
            assert not any(d.get("usage") is not None for d in result.chunks[:-1])

    @pytest.mark.parametrize(
        "parameter,value",
        [
            (
                "tools",
                [
                    {
                        "type": "function",
                        "function": {
                            "name": "ping",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            ),
            ("tool_choice", "auto"),
            ("thinking", {"type": "adaptive"}),
            ("reasoning_split", True),
            ("reasoning_effort", "high"),
            ("response_format", {"type": "json_object"}),
            ("seed", 42),
            ("stop", ["END"]),
        ],
        ids=[
            "tools",
            "tool_choice",
            "thinking",
            "reasoning_split",
            "reasoning_effort",
            "response_format",
            "seed",
            "stop",
        ],
    )
    def test_15_07_undeclared_parameters(
        self, contract, client, parameter, value, preflight
    ):
        """Test acceptance/rejection only, not capability activation or ignored semantics."""
        rule = contract(f"15_07/{parameter}")
        if rule["outcome"] != "success":
            preflight(client, stream=False)
        assert_confirmed_contract(
            client.request(payload(client, **{parameter: value})), rule
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("variant", ["essay", "json"])
    def test_15_08_stream_packet_quality(self, contract, client, variant):
        """Observed packet shape: a small initial packet, then batched text events.

        The five M3-style ratios vary with response length and are recorded
        only; the per-response shape is what every observed stream shares.
        """
        rule = contract(f"15_08/{variant}")
        assert rule["outcome"] == "success", (
            "packet quality requires a successful text contract"
        )
        runs = rule.get("runs")
        assert type(runs) is int and 2 <= runs <= 10, (
            "set a bounded sample count of 2–10"
        )
        shape = rule.get("packet_shape", {})
        for key in (
            "first_packet_max_characters",
            "middle_packet_min_characters",
            "packet_max_characters",
        ):
            assert type(shape.get(key)) is int and shape[key] > 0, (
                f"missing/invalid {key}"
            )
        minimum = rule.get("minimum_characters")
        assert type(minimum) is int and minimum > 0, (
            "record the minimum aggregate sample size"
        )
        prompt = (
            "请写一篇约1200字的中文游记，分六段详细描写各站见闻，直接输出正文。"
            if variant == "essay"
            else "只返回一个 JSON 对象，包含 items 数组，其中有30个对象，每个含 name 和约30字的 description。"
        )
        continuation = (
            "继续描写旅途中下一站的新见闻，补充人物、景色和细节，直接续写正文，不要重复已有内容。"
            if variant == "essay"
            else "继续提供下一批不同的条目，仍只返回包含 items 数组的 JSON 对象，每项含 name 和详细的 description，不要重复已有条目。"
        )

        def check_response(number, sizes):
            assert sizes[0] <= shape["first_packet_max_characters"], (
                f"分包形态变化：第 {number} 个响应首包 {sizes[0]} 字符 "
                f"> {shape['first_packet_max_characters']}；分包 {sizes}"
            )
            small = [
                n for n in sizes[1:-1] if n < shape["middle_packet_min_characters"]
            ]
            assert not small, (
                f"分包形态变化：第 {number} 个响应中间出现 {small} 字符的小包 "
                f"(< {shape['middle_packet_min_characters']})；分包 {sizes}"
            )
            assert max(sizes) <= shape["packet_max_characters"], (
                f"分包形态变化：第 {number} 个响应单包 {max(sizes)} 字符 "
                f"> {shape['packet_max_characters']}；分包 {sizes}"
            )

        sample_packet_stream(
            client, prompt, continuation, rule, check_response=check_response
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_09_legacy_narrator(self, contract, client, stream, preflight):
        """The legacy narrator is a named system message, not an eighth role."""
        rule = contract(f"15_09/{'stream' if stream else 'non_stream'}")
        if rule["outcome"] != "success":
            preflight(client, stream=stream)
        messages = [
            message("system", "你是一位勇敢的冒险者。", name="英雄"),
            message("system", "旁白以生动的细节描述场景。", name="旁白"),
            message("user_system", "与英雄一起旅行的忠诚伙伴。", name="伙伴"),
            message("user", "看！前面有个山洞！", name="伙伴"),
        ]
        assert_confirmed_contract(client.chat(messages, stream=stream), rule)

    @pytest.mark.parametrize(
        "samples", [False, True], ids=["without_samples", "with_samples"]
    )
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_10_legacy_suggest_reply(
        self, contract, client, samples, stream, preflight
    ):
        """Preserve the empty final user message named 推荐回复 from both old suites."""
        variant = "with_samples" if samples else "without_samples"
        rule = contract(f"15_10/{variant}/{'stream' if stream else 'non_stream'}")
        if rule["outcome"] != "success":
            preflight(client, stream=stream)
        messages = [
            message("system", "你是旅行向导，帮助旅客安排旅行。", name="向导"),
            message("user_system", "计划去日本旅行的旅客。", name="旅客"),
        ]
        if samples:
            messages += [
                message("sample_message_user", "哪里适合散步？", name="旅客"),
                message("sample_message_ai", "可以去公园。", name="向导"),
            ]
        messages += [
            message("user", "去日本应该看什么？", name="旅客"),
            message("assistant", "可以考虑东京、京都和大阪。", name="向导"),
            message("user", "", name="推荐回复"),
        ]
        assert_confirmed_contract(client.chat(messages, stream=stream), rule)

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_11_legacy_named_group_chat(self, contract, client, stream, preflight):
        """Two named AI systems are distinct from the supported group scene role."""
        rule = contract(f"15_11/{'stream' if stream else 'non_stream'}")
        if rule["outcome"] != "success":
            preflight(client, stream=stream)
        messages = [
            message("system", "你是角色A。", name="角色A"),
            message("system", "你是角色B。", name="角色B"),
            message("user", "你好角色B！", name="角色A"),
        ]
        assert_confirmed_contract(client.chat(messages, stream=stream), rule)

    @pytest.mark.parametrize("limit", [-1, 0, 1])
    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_15_12_legacy_token_boundaries(
        self, contract, client, limit, stream, preflight
    ):
        """Historical max_tokens tolerance does not alter max_completion_tokens rules."""
        rule = contract(f"15_12/{limit}/{'stream' if stream else 'non_stream'}")
        if rule["outcome"] != "success":
            preflight(client, stream=stream)
        elif limit == 1:
            assert rule.get("completion_limit") == 1, (
                "one-token success must verify the budget"
            )
        request = {
            "model": client.settings.model,
            "messages": continuation_messages()
            if limit == 1
            else simple_messages("你好"),
            "stream": stream,
            "max_tokens": limit,
        }
        if stream and client.settings.style == "openai" and "completion_limit" in rule:
            request["stream_options"] = {"include_usage": True}
        exercise_contract(client, request, rule)
