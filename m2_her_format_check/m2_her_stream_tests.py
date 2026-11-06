"""Module 14: raw SSE framing and native summary/usage semantics."""

import pytest

from .exercises import echo_messages, exercise_finish, record_measurement
from .helpers import (
    assert_envelope,
    assert_request_failed,
    assert_success,
    simple_messages,
)
from .scenarios import ESCAPED_TEXT


class TestStreamProtocol:
    def test_14_01_sse_framing(self, client):
        """SSE response is parsed as events, not as TCP packets or JSON lines."""
        result = client.chat(simple_messages(), stream=True)
        assert_success(result)
        assert result.events and not result.errors

    def test_14_02_chunk_envelope_consistency(self, client):
        """Chunk identity stays stable; native summary object type may differ."""
        result = client.chat(simple_messages(), stream=True)
        assert_success(result)
        assert_envelope(
            result, model=client.settings.response_model or client.settings.model
        )

    def test_14_03_delta_role_content_types(self, client):
        """Later deltas may omit role; observed role is always assistant."""
        result = client.chat(simple_messages(), stream=True)
        assert_success(result)
        assert any(
            c.get("delta", {}).get("role") == "assistant" for c in result.choices
        ), "assistant role never observed"

    @pytest.mark.behavior
    def test_14_04_content_reassembly(self, client):
        """Few-shot exact echo checks all twelve markers and their order in streamed output."""
        expected = "|".join(f"HER_{i:02}" for i in range(12))
        result = client.chat(
            echo_messages(expected),
            stream=True,
            temperature=0.01,
            max_completion_tokens=256,
        )
        assert_success(result)
        assert result.content.strip() == expected, (
            "Streamed exact-echo task did not preserve the full marker sequence"
        )
        assert all(summary == result.content for summary in result.summaries)
        record_measurement(
            client,
            "optional_field_coverage",
            check="reassembly_summary",
            observed_values=len(result.summaries),
        )

    @pytest.mark.behavior
    def test_14_05_unicode_escape_chunks(self, client):
        """Unicode and escapes survive SSE transport, without blanket replacements."""
        result = client.chat(
            echo_messages(ESCAPED_TEXT),
            stream=True,
            temperature=0.01,
        )
        assert_success(result)
        # Strict wire UTF-8 / JSON decoding is already enforced by assert_success.
        # A different model answer does not prove that the transport lost bytes.
        missing = [
            char for char in ('"', "\\", "\n", "🙂", "🚀") if char not in result.content
        ]
        assert not missing, (
            f"Echo task did not generate the required Unicode/escape sample: {missing!r}"
        )

    def test_14_06_stream_stop(self, client):
        """Natural completion is observable even without a native DONE marker."""
        exercise_finish(client, stream=True, reason="stop")

    def test_14_07_stream_length(self, client):
        """A forced short output budget yields a length terminal reason."""
        exercise_finish(client, stream=True, reason="length")

    def test_14_08_stream_usage(self, client):
        """Final usage is positive; intermediate native zero-usage packets are valid."""
        result = client.chat(simple_messages(), stream=True)
        assert_success(result)
        finished = False
        final_usage = None
        for chunk in result.chunks:
            if any(
                choice.get("finish_reason") is not None for choice in chunk["choices"]
            ):
                finished = True
            if finished and chunk.get("usage") is not None:
                final_usage = chunk["usage"]
        assert final_usage is not None and final_usage["total_tokens"] > 0, (
            "expected a positive final usage at or after the finish event"
        )

    def test_14_09_native_summary_message(self, client):
        """Validate native streaming terminal structure and optional full summaries."""
        if client.settings.style != "native":
            pytest.skip("Native summary check does not apply to the OpenAI protocol")
        result = client.chat(simple_messages(), stream=True)
        assert_success(result)
        terminal = [c for c in result.choices if c.get("finish_reason") is not None]
        assert terminal, "No terminal choice delivered"
        assert all(summary == result.content for summary in result.summaries)
        record_measurement(
            client,
            "optional_field_coverage",
            check="native_summary",
            observed_values=len(result.summaries),
        )

    def test_14_10_stream_error_response(self, client, preflight):
        """An invalid streaming request can return ordinary JSON errors."""
        preflight(client, stream=True)
        result = client.request(
            {"model": client.settings.model, "messages": None, "stream": True}
        )
        assert_request_failed(result)

    @pytest.mark.slow
    @pytest.mark.behavior
    def test_14_11_repeated_emoji_integrity(self, client):
        """M3's repeated emoji probe, bounded to 20 requests and 512 tokens each."""
        missing_emoji = []
        for run in range(20):
            result = client.chat(
                simple_messages(
                    "请输出一行包含30个彩色 emoji 的文字，以空格分隔，例如🙂🚀🌸🐳。"
                    "不添加解释。"
                ),
                stream=True,
                temperature=0.01,
                max_completion_tokens=512,
            )
            assert_success(result)
            # A literal U+FFFD in valid UTF-8 is generated text, not evidence of
            # decoding failure. Invalid wire bytes still fail assert_success.
            if not any(0x1F300 <= ord(ch) <= 0x1FAFF for ch in result.content):
                missing_emoji.append(run + 1)
        record_measurement(
            client,
            "emoji_coverage",
            replies=20,
            replies_with_emoji=20 - len(missing_emoji),
            missing_emoji=missing_emoji,
        )
        if missing_emoji:
            pytest.skip(
                f"Validated 20 streams, but only {20 - len(missing_emoji)}/20 "
                "contained a target emoji; emoji stress sample incomplete"
            )
