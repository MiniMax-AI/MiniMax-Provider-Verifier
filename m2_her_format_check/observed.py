"""Observed M2-her deployment behavior: the expected values of this case set.

Recorded on 2026-11-05 from repeated full runs of all 509 variants against the
official MiniMax native endpoint (/v1/text/chatcompletion_v2, model M2-her).
Every error envelope below was byte-identical across runs and in both stream
modes where listed. These are what the API does today, not what the public
docs promise; README.md explains the baseline and the expected randomness.

Error expectations are keyword arguments for helpers.assert_error_envelope.
"""


def _error(status_code: int, status_msg: str, framing: str) -> dict:
    return {"status_code": status_code, "status_msg": status_msg, "framing": framing}


# Omitting name on user_system / group / sample_message_* (03_02, 05_04,
# 13_01, 13_05, 16_01). Keyed by stream mode: the two modes fail differently.
NAME_OMITTED_ERROR = {
    False: _error(2013, "invalid params, 400", "json"),
    True: _error(1000, "unknown error, 999", "sse"),
}

# temperature=-0.1 (08_03); 0 and 1.01 are accepted.
NEGATIVE_TEMPERATURE_ERROR = {
    False: _error(1000, "unknown error, 500", "json"),
    True: _error(1000, "unknown error, 999", "sse"),
}

# Non-string user content other than video parts (11_04) and empty user
# content (15_04): a status-0 placeholder envelope followed by the error.
INVALID_CONTENT_ERROR = _error(1000, "unknown error", "concatenated_json")

# A null element inside messages (11_09), in both stream modes: plain JSON.
NULL_MESSAGE_ITEM_ERROR = _error(1000, "unknown error", "json")

# n=1..4 return n candidates; n=5 is an internal error, not a declared limit.
N_LIMIT = 4
N_ABOVE_LIMIT_ERROR = _error(1000, "unknown error, 500", "json")

# Over-64K input (12_04), streamed. Non-stream returns 2013 + context message.
STREAM_CONTEXT_OVER_ERROR = _error(1000, "unknown error, 999", "sse")

# 16_02 greetings whose reply usually glues the greeting onto the marker
# ("UNICODE_K72_안녕하세요"); others return the bare marker.
MARKER_GREETING_GLUED = frozenset({"안녕하세요", "مرحبا", "Привет"})

# Language cases below are model behavior at temperature 0.01. They record the
# usual reply language; an occasional sampling flip can fail a single run.

# 19_02 (persona language, user language) -> usual dominant language where it
# is not the user's; unlisted pairs answer strictly in the user's language.
# zh->ja is Japanese with Chinese stage directions.
PERSONA_LANGUAGE_REPLY = {
    ("zh", "ja"): ("ja",),
    ("zh", "ko"): ("zh",),
    ("zh", "es"): ("zh",),
    ("en", "ko"): ("en",),
    ("ja", "zh"): ("ja",),
    ("ja", "en"): ("ja",),
    ("ja", "ko"): ("ja",),
    ("ja", "es"): ("ja",),
    ("ko", "zh"): ("ko",),
    ("ko", "ja"): ("ko",),
    ("ko", "es"): ("ko",),
    ("es", "zh"): ("es",),
    ("es", "en"): ("es",),
    ("es", "ja"): ("es",),
    ("es", "ko"): ("es",),
}

# 19_03 variant -> usual dominant language where the request is not met.
EXPLICIT_LANGUAGE_REPLY = {"user_request_zh": ("ja",)}

# 19_05 (history language, latest user language) -> usual dominant language.
# zh->ja and ko->en follow the switch (ko->en in 20 of 28 samples) and are
# checked strictly; the rest keep the history language.
LANGUAGE_SWITCH_REPLY = {
    ("zh", "en"): ("zh",),
    ("zh", "ko"): ("zh",),
    ("en", "zh"): ("en",),
    ("en", "ja"): ("en",),
    ("en", "ko"): ("en",),
    ("ja", "zh"): ("ja",),
    ("ja", "en"): ("ja",),
    ("ja", "ko"): ("ja",),
    ("ko", "zh"): ("ko",),
    ("ko", "ja"): ("ko",),
}
