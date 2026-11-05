"""
M3_1_Flash API Test — request-field contract cases (OAI /v1/chat/completions)

Each case sends one request shape that differs from a minimal valid baseline in
a single request field, then checks the transport-level contract only:

  - expected 200: HTTP 200, non-empty `choices`, choices[0].message.role == "assistant"
  - expected 400: HTTP 400 and the body carries no `choices` (the invalid field
    is rejected instead of being silently accepted)

Generated text, language and capability effects are deliberately not asserted;
those belong to the behavioural suites. Payloads go through oai_chat_verbatim so the
helper never injects `model` or an output budget that the case omits on purpose.

Case IDs (REQ-xxx / ERR-xxx / RES-xxx) map to docs/m3_1_flash_request_cases.md.
Naming: test_<module id>_<field>, one parametrized function per request field.
"""
import base64
import copy

import pytest

from helpers import *


IMAGE_URL = size_fixture_url("image_9mb.png")


def _png_data_url(r, g, b):
    return "data:image/png;base64," + base64.b64encode(make_png_672(r, g, b)).decode()


def _placeholders():
    return {
        "__MODEL__": MODEL,
        "__PNG__": _png_data_url(220, 40, 40),
        "__PNG_2__": _png_data_url(40, 40, 220),
        "__JPEG__": jpeg_base64(),
        "__WEBP__": webp_base64(),
        "__GIF__": gif_base64(),
        "__IMAGE_URL__": IMAGE_URL,
    }


def _resolve(value, table):
    if isinstance(value, dict):
        return {k: _resolve(v, table) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, table) for v in value]
    if isinstance(value, str) and value in table:
        return table[value]
    return value


def _check(result, expected_status, label):
    body = result.get("body")
    assert result["status"] == expected_status, (
        f"{label}: expected HTTP {expected_status}, got {result['status']}: {str(body)[:300]}"
    )
    if expected_status == 200:
        choices = (body or {}).get("choices")
        assert isinstance(choices, list) and choices, f"{label}: empty choices: {str(body)[:300]}"
        role = (choices[0].get("message") or {}).get("role")
        assert role == "assistant", f"{label}: choices[0].message.role={role!r}"
    else:
        assert not (isinstance(body, dict) and "choices" in body), (
            f"{label}: error response must not carry choices: {str(body)[:300]}"
        )


def _run(case_id, expected_status, requests):
    """Send one or more requests in order.

    A later request whose `messages` is "__PRIOR__" continues the conversation:
    it reuses the previous request's messages plus the assistant reply.
    """
    table = _placeholders()
    prior = None
    for i, template in enumerate(requests):
        payload = _resolve(copy.deepcopy(template), table)
        if payload.get("messages") == "__PRIOR__":
            payload["messages"] = prior + [{"role": "user", "content": "Add one more sentence."}]
        r = oai_chat_verbatim(payload, timeout=600)
        _check(r, expected_status, f"{case_id} request#{i + 1}")
        if expected_status == 200:
            reply = r["body"]["choices"][0]["message"].get("content") or ""
            prior = payload["messages"] + [{"role": "assistant", "content": reply}]


# ============================================================
# 01 model — model field
# ============================================================

class TestModel:
    """Request contract for `model`."""
    CASES = [('REQ-001',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}]}]),
             ('ERR-023', 400, [{'model': [], 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}]}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_01_model(self, case_id, expected_status, requests):
        """model field: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 02 messages — messages structure and message forms
# ============================================================

class TestMessages:
    """Request contract for `messages`."""
    CASES = [('ERR-027', 400, [{'model': '__MODEL__', 'messages': []}]),
             ('ERR-026', 400, [{'model': '__MODEL__', 'messages': None}]),
             ('ERR-029', 400, [{'model': '__MODEL__', 'messages': [1]}]),
             ('REQ-009',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'system', 'content': 'Reply in English.'},
                             {'role': 'system', 'content': 'Keep the answer short.'},
                             {'role': 'user', 'content': 'Hello'}]}]),
             ('ERR-030', 400, [{'model': '__MODEL__', 'messages': [{'content': 'Hello'}]}]),
             ('ERR-032', 400, [{'model': '__MODEL__', 'messages': [{'role': None, 'content': 'Hello'}]}]),
             ('REQ-003',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Remember the code A7.'},
                             {'role': 'assistant', 'content': 'Noted.'},
                             {'role': 'user', 'content': 'What is the code?'}]}]),
             ('REQ-008',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'name': 'a', 'content': 'Please compare plan A.'},
                             {'role': 'user', 'name': 'b', 'content': 'Also compare plan B.'}]}]),
             ('REQ-015',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Hello'},
                             {'role': 'assistant', 'content': 'Hello', 'refusal': None},
                             {'role': 'user', 'content': 'Continue'}]}]),
             ('REQ-012',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Hello'},
                             {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Hello.'}]},
                             {'role': 'user', 'content': 'Continue'}]}]),
             ('REQ-014',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Earlier request'},
                             {'role': 'assistant', 'content': 'I cannot help with the earlier request.', 'refusal': 'I cannot help with the earlier request.'},
                             {'role': 'user', 'content': 'Please explain caching.'}]}]),
             ('REQ-010',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': 'First paragraph.'},
                                          {'type': 'text', 'text': 'Second paragraph, please summarize.'}]}]}]),
             ('REQ-011',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': '输入有中文🙂、引号"、反斜线\\和换行\n请简短回应。'}]}]),
             ('REQ-024',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': ''},
                                          {'type': 'text', 'text': 'Please explain caching.'}]}]}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_02_messages(self, case_id, expected_status, requests):
        """messages structure and message forms: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)

    def test_02_req_016_tool_text_array_content(self):
        """REQ-016: a tool message whose content is a text-part array is accepted."""
        _run("REQ-016", 200, [{
            "model": "__MODEL__",
            "messages": [
                {"role": "user", "content": "What is the weather in Beijing?"},
                {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "call_1", "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"location":"Beijing"}'},
                }]},
                {"role": "tool", "tool_call_id": "call_1", "content": [{"type": "text", "text": "Result: 22."}]},
                {"role": "user", "content": "Continue the answer"},
            ],
            "tools": [WEATHER_TOOL_OAI],
        }])

    def test_02_req_148_long_single_user_message(self):
        """REQ-148: one long user message is delivered and answered.

        The text is synthetic and deterministic; the case checks that a long
        single message is accepted, not recall quality.
        """
        long_text = "A cache is a storage layer that speeds up data access in computer systems. " * 1000 + "\nSummarize the text above in one sentence."
        _run("REQ-148", 200, [{
            "model": "__MODEL__",
            "messages": [{"role": "user", "content": long_text}],
            "max_completion_tokens": 2048,
        }])

    def test_02_req_149_long_history_103_messages(self):
        """REQ-149: 51 user/assistant pairs plus a final user turn (103 messages)."""
        filler = ("A cache is a storage layer that speeds up data access in computer systems. " * 400)[:400]
        messages = []
        for i in range(1, 52):
            messages.append({"role": "user", "content": f"Round {i} material: {filler}"})
            messages.append({"role": "assistant", "content": f"Round {i} reply: {filler}"})
        messages.append({"role": "user", "content": "Give a short summary of the material above."})
        assert len(messages) == 103
        _run("REQ-149", 200, [{"model": "__MODEL__", "messages": messages, "max_completion_tokens": 2048}])

# ============================================================
# 03 image_url — image_url image input
# ============================================================

class TestImageUrl:
    """Request contract for `messages[].content[type=image_url]`."""
    CASES = [('REQ-020',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': 'Describe the main color in the image.'},
                                          {'type': 'image_url', 'image_url': {'url': '__PNG__'}}]}]}]),
             ('REQ-019',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': 'Describe the main color in the image.'},
                                          {'type': 'image_url', 'image_url': {'url': '__JPEG__'}}]}]}]),
             ('REQ-021',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': 'Describe the main color in the image.'},
                                          {'type': 'image_url', 'image_url': {'url': '__WEBP__'}}]}]}]),
             ('REQ-022',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': 'Describe the main color in the image.'},
                                          {'type': 'image_url', 'image_url': {'url': '__GIF__'}}]}]}]),
             ('REQ-028',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url', 'image_url': {'url': '__PNG__'}},
                                          {'type': 'image_url', 'image_url': {'url': '__PNG__'}},
                                          {'type': 'text', 'text': 'Describe both images.'}]}]}]),
             ('REQ-025',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url', 'image_url': {'url': '__PNG__'}}]}]}]),
             ('REQ-027',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url', 'image_url': {'url': '__IMAGE_URL__'}},
                                          {'type': 'image_url', 'image_url': {'url': '__PNG__'}},
                                          {'type': 'text', 'text': 'Compare the two images.'}]}]}]),
             ('REQ-034',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url',
                                           'image_url': {'url': '__PNG__', 'detail': 'low'}},
                                          {'type': 'image_url',
                                           'image_url': {'url': '__PNG_2__', 'detail': 'high'}},
                                          {'type': 'text', 'text': 'Compare the two images.'}]}]}]),
             ('REQ-026',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': 'Look at this image first.'},
                                          {'type': 'image_url', 'image_url': {'url': '__PNG__'}},
                                          {'type': 'text', 'text': 'Describe the main color in one sentence.'}]}]}]),
             ('REQ-030',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url',
                                           'image_url': {'url': '__PNG__', 'detail': 'low'}},
                                          {'type': 'text', 'text': 'Describe the image.'}]}]}]),
             ('REQ-031',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url',
                                           'image_url': {'url': '__PNG__', 'detail': 'high'}},
                                          {'type': 'text', 'text': 'Describe the image.'}]}]}]),
             ('ERR-041',
              400,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {}}]}]}]),
             ('ERR-042',
              400,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 12}}]}]}]),
             ('REQ-033',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url', 'image_url': {'url': '__PNG__'}},
                                          {'type': 'text', 'text': 'Describe the image.'}]}]}]),
             ('ERR-045',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'system',
                              'content': [{'type': 'image_url', 'image_url': {'url': '__PNG__'}}]},
                             {'role': 'user', 'content': 'Hello'}]}]),
             ('REQ-023',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'text', 'text': 'Describe the image.'},
                                          {'type': 'image_url', 'image_url': {'url': '__IMAGE_URL__'}}]}]}]),
             ('ERR-044',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url',
                                           'image_url': {'url': '__PNG__', 'detail': None}}]}]}]),
             ('REQ-029',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user',
                              'content': [{'type': 'image_url',
                                           'image_url': {'url': '__PNG__', 'detail': 'auto'}},
                                          {'type': 'text', 'text': 'Describe the image.'}]}]}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_03_image_url(self, case_id, expected_status, requests):
        """image_url image input: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 04 max_completion_tokens — max_completion_tokens budget
# ============================================================

class TestMaxCompletionTokens:
    """Request contract for `max_completion_tokens`."""
    CASES = [('REQ-060',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'max_completion_tokens': 32,
                'reasoning_effort': 'low'}]),
             ('ERR-076',
              400,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'max_completion_tokens': 8.5}]),
             ('REQ-061',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}]}]),
             ('REQ-131',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'max_completion_tokens': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_04_max_completion_tokens(self, case_id, expected_status, requests):
        """max_completion_tokens budget: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 05 max_tokens — legacy max_tokens
# ============================================================

class TestMaxTokens:
    """Request contract for `max_tokens`."""
    CASES = [('REQ-132',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'max_tokens': None}]),
             ('REQ-062',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'max_tokens': 64}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_05_max_tokens(self, case_id, expected_status, requests):
        """legacy max_tokens: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 06 stop — stop sequences
# ============================================================

class TestStop:
    """Request contract for `stop`."""
    CASES = [('ERR-081',
              400,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'stop': ['a', 1]}]),
             ('REQ-067',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'stop': ['#A#', '#B#', '#C#', '#D#']}]),
             ('REQ-068',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'stop': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_06_stop(self, case_id, expected_status, requests):
        """stop sequences: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 07 temperature — temperature
# ============================================================

class TestTemperature:
    """Request contract for `temperature`."""
    CASES = [('REQ-040',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'temperature': 0}]),
             ('REQ-041',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'temperature': 0.2}]),
             ('REQ-042',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'temperature': 2}]),
             ('REQ-125',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'temperature': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_07_temperature(self, case_id, expected_status, requests):
        """temperature: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 08 top_p — top_p
# ============================================================

class TestTopP:
    """Request contract for `top_p`."""
    CASES = [('ERR-065',
              400,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'top_p': -0.1}]),
             ('ERR-066',
              400,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'top_p': 1.1}]),
             ('REQ-044',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'top_p': 0.1}]),
             ('REQ-045',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'top_p': 1}]),
             ('REQ-126',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'top_p': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_08_top_p(self, case_id, expected_status, requests):
        """top_p: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 09 presence_penalty — presence_penalty
# ============================================================

class TestPresencePenalty:
    """Request contract for `presence_penalty`."""
    CASES = [('REQ-049',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'presence_penalty': -2}]),
             ('REQ-050',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'presence_penalty': 0}]),
             ('REQ-051',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'presence_penalty': 2}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_09_presence_penalty(self, case_id, expected_status, requests):
        """presence_penalty: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 10 frequency_penalty — frequency_penalty
# ============================================================

class TestFrequencyPenalty:
    """Request contract for `frequency_penalty`."""
    CASES = [('REQ-046',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'frequency_penalty': -2}]),
             ('REQ-047',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'frequency_penalty': 0}]),
             ('REQ-048',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'frequency_penalty': 2}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_10_frequency_penalty(self, case_id, expected_status, requests):
        """frequency_penalty: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 11 logit_bias — logit_bias
# ============================================================

class TestLogitBias:
    """Request contract for `logit_bias`."""
    CASES = [('REQ-052',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'logit_bias': {'1000': -100}}]),
             ('REQ-053',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'logit_bias': {'1000': -1}}]),
             ('REQ-054',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'logit_bias': {'1000': 0}}]),
             ('REQ-055',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'logit_bias': {'1000': 1}}]),
             ('REQ-056',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'logit_bias': {'1000': 100}}]),
             ('REQ-129',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'logit_bias': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_11_logit_bias(self, case_id, expected_status, requests):
        """logit_bias: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 12 seed — seed
# ============================================================

class TestSeed:
    """Request contract for `seed`."""
    CASES = [('REQ-063',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'seed': 42},
               {'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'seed': 42}]),
             ('REQ-064',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'seed': -9223372036854775808}]),
             ('REQ-065',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'seed': 9223372036854775807}]),
             ('REQ-133',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'seed': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_12_seed(self, case_id, expected_status, requests):
        """seed: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 13 n — n (choice count)
# ============================================================

class TestN:
    """Request contract for `n`."""
    CASES = [('REQ-058',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}]}]),
             ('ERR-074',
              400,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'n': 1.5}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_13_n(self, case_id, expected_status, requests):
        """n (choice count): see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 14 reasoning_effort — reasoning_effort
# ============================================================

class TestReasoningEffort:
    """Request contract for `reasoning_effort`."""
    CASES = [('REQ-071',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': 'low'}]),
             ('REQ-072',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': 'medium'}]),
             ('REQ-073',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': 'high'}]),
             ('REQ-074',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': 'xhigh'}]),
             ('REQ-075',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': 'max'}]),
             ('REQ-134',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': None}]),
             ('REQ-077',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': 'low'},
               {'model': '__MODEL__', 'reasoning_effort': 'high', 'messages': '__PRIOR__'}]),
             ('REQ-076',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}]}]),
             ('ERR-083',
              400,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'reasoning_effort': ['low']}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_14_reasoning_effort(self, case_id, expected_status, requests):
        """reasoning_effort: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 15 logprobs — logprobs
# ============================================================

class TestLogprobs:
    """Request contract for `logprobs`."""
    CASES = [('REQ-081',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'logprobs': False}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_15_logprobs(self, case_id, expected_status, requests):
        """logprobs: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 16 response_format — response_format structured output
# ============================================================

class TestResponseFormat:
    """Request contract for `response_format`."""
    CASES = [('RES-063',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False}}}}]),
             ('RES-064',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'response_format': {'type': 'text'}}]),
             ('RES-145',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'response_format': {'type': 'text'}}]),
             ('RES-146',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Output a JSON object that contains one greeting.'}],
                'response_format': {'type': 'json_object'}}]),
             ('RES-065',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False}}}}]),
             ('RES-066',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False}}}}]),
             ('RES-067',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False},
                                                    'description': 'Answer card'}}}]),
             ('RES-068',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False}}}}]),
             ('RES-069',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False}}}}]),
             ('RES-070',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'value': {'type': ['string',
                                                                                                 'null']}},
                                                               'required': ['value'],
                                                               'additionalProperties': False}}}}]),
             ('RES-071',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'value': {'type': 'string'}},
                                                               'required': ['value'],
                                                               'additionalProperties': False}}}}]),
             ('RES-072',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'value': {'type': 'string'}},
                                                               'required': ['value'],
                                                               'additionalProperties': False}}}}]),
             ('RES-073',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'value': {'type': 'string'}},
                                                               'required': ['value'],
                                                               'additionalProperties': False}}}}]),
             ('RES-148',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False}}}}]),
             ('RES-150',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Answer in JSON and list a lot of content.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'answer': {'type': 'string'}},
                                                               'required': ['answer'],
                                                               'additionalProperties': False}}},
                'max_completion_tokens': 8}]),
             ('RES-075',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object whose answer field is a short greeting.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'answer_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'value': {'type': ['string',
                                                                                                 'null'],
                                                                                        'enum': ['C',
                                                                                                 'F',
                                                                                                 None]}},
                                                               'required': ['value'],
                                                               'additionalProperties': False}}}}]),
             ('RES-169',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Return a JSON object that follows the schema.'}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'types_card',
                                                    'strict': True,
                                                    'schema': {'type': 'object',
                                                               'properties': {'s': {'type': 'string'},
                                                                              'n': {'type': 'number'},
                                                                              'i': {'type': 'integer'},
                                                                              'b': {'type': 'boolean'},
                                                                              'o': {'type': 'object',
                                                                                    'properties': {'x': {'type': 'integer'}},
                                                                                    'required': ['x'],
                                                                                    'additionalProperties': False},
                                                                              'a': {'type': 'array',
                                                                                    'items': {'type': 'number'}},
                                                                              'nullable': {'type': ['string',
                                                                                                    'null']}},
                                                               'required': ['s',
                                                                            'n',
                                                                            'i',
                                                                            'b',
                                                                            'o',
                                                                            'a',
                                                                            'nullable'],
                                                               'additionalProperties': False}}}}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_16_response_format(self, case_id, expected_status, requests):
        """response_format structured output: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 17 prediction — prediction (predicted output)
# ============================================================

class TestPrediction:
    """Request contract for `prediction`."""
    CASES = [('RES-088',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Rename a to b in the code and return the whole file:\nprint(a)\n'}],
                'prediction': {'type': 'content', 'content': 'print(a)\n'}}]),
             ('RES-089',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Rename a to b in the code and return the whole file:\nprint(a)\n'}],
                'prediction': {'type': 'content', 'content': 'print(a)\n'}}]),
             ('RES-090',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Rename a to b in the code and return the whole file:\nprint(a)\n'}],
                'prediction': {'type': 'content', 'content': 'print(a)\n'}}]),
             ('RES-091',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Rename a to b in the code and return the whole file:\nprint(a)\n'}],
                'prediction': {'type': 'content', 'content': 'print(a)\n'}}]),
             ('RES-092',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Rename a to b in the code and return the whole file:\nprint(a)\n'}],
                'prediction': {'type': 'content', 'content': 'print(a)\n'}}]),
             ('RES-161',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Rename a to b in the code and return the whole file:\nprint(a)\n'}],
                'prediction': {'type': 'content', 'content': 'print(a)\n'}},
               {'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Rename a to b in the code and return the whole file:\nprint(a)\n'}],
                'prediction': {'type': 'content', 'content': [{'type': 'text', 'text': 'print(a)\n'}]}}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_17_prediction(self, case_id, expected_status, requests):
        """prediction (predicted output): see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 18 modalities — modalities
# ============================================================

class TestModalities:
    """Request contract for `modalities`."""
    CASES = [('REQ-099',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'modalities': ['text']}]),
             ('REQ-143',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'modalities': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_18_modalities(self, case_id, expected_status, requests):
        """modalities: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 19 audio — audio
# ============================================================

class TestAudio:
    """Request contract for `audio`."""
    CASES = [('REQ-144',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'audio': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_19_audio(self, case_id, expected_status, requests):
        """audio: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 20 prompt_cache_key — prompt_cache_key
# ============================================================

class TestPromptCacheKey:
    """Request contract for `prompt_cache_key`."""
    CASES = [('REQ-107',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'prompt_cache_key': 'suite-prefix'},
               {'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'prompt_cache_key': 'suite-prefix'}]),
             ('REQ-145',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'prompt_cache_key': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_20_prompt_cache_key(self, case_id, expected_status, requests):
        """prompt_cache_key: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 21 prompt_cache_options — prompt cache options default
# ============================================================

class TestPromptCacheOptions:
    """Request contract for `prompt_cache_options`."""
    CASES = [('REQ-108',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}]}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_21_prompt_cache_options(self, case_id, expected_status, requests):
        """prompt cache options default: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 22 web_search_options — web_search_options
# ============================================================

class TestWebSearchOptions:
    """Request contract for `web_search_options`."""
    CASES = [('REQ-120',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'web_search_options': {'search_context_size': 'low'}}]),
             ('REQ-121',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'web_search_options': {'search_context_size': 'medium'}}]),
             ('REQ-122',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'web_search_options': {'search_context_size': 'high'}}]),
             ('REQ-123',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'web_search_options': {'user_location': {'type': 'approximate',
                                                         'approximate': {'city': 'San Francisco',
                                                                         'country': 'US',
                                                                         'region': 'California',
                                                                         'timezone': 'America/Los_Angeles'}}}}]),
             ('REQ-124',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'web_search_options': {'user_location': {'type': 'approximate',
                                                         'approximate': {'country': 'US'}}}}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_22_web_search_options(self, case_id, expected_status, requests):
        """web_search_options: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 23 metadata — metadata
# ============================================================

class TestMetadata:
    """Request contract for `metadata`."""
    CASES = [('REQ-086',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'metadata': {'suite': 'format-check'},
                'store': True}]),
             ('REQ-088',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'metadata': {'case': ''},
                'store': True}]),
             ('REQ-138',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'metadata': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_23_metadata(self, case_id, expected_status, requests):
        """metadata: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 24 store — store
# ============================================================

class TestStore:
    """Request contract for `store`."""
    CASES = [('REQ-089',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'store': False}]),
             ('REQ-090',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'store': True}]),
             ('REQ-139',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'store': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_24_store(self, case_id, expected_status, requests):
        """store: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 25 user — legacy user
# ============================================================

class TestUser:
    """Request contract for `user`."""
    CASES = [('REQ-092',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'user': 'synthetic-user-hash'}]),
             ('REQ-141',
              200,
              [{'model': '__MODEL__', 'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}], 'user': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_25_user(self, case_id, expected_status, requests):
        """legacy user: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)


# ============================================================
# 26 service_tier — service_tier
# ============================================================

class TestServiceTier:
    """Request contract for `service_tier`."""
    CASES = [('REQ-093',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'service_tier': 'auto'}]),
             ('REQ-094',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'service_tier': 'default'}]),
             ('REQ-095',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'service_tier': 'flex'}]),
             ('REQ-096',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'service_tier': 'priority'}]),
             ('REQ-142',
              200,
              [{'model': '__MODEL__',
                'messages': [{'role': 'user', 'content': 'Explain caching in one sentence.'}],
                'service_tier': None}])]

    @pytest.mark.parametrize("case_id,expected_status,requests", CASES, ids=[c[0] for c in CASES])
    def test_26_service_tier(self, case_id, expected_status, requests):
        """service_tier: see the case table in docs/m3_1_flash_request_cases.md."""
        _run(case_id, expected_status, requests)
