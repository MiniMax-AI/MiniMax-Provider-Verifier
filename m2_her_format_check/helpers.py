"""M2-Her HTTP/SSE transport and assertions, without M3 request defaults.

Native reference: https://platform.minimax.cn/docs/api-reference/text/api/openapi-chat.json
SSE framing: https://html.spec.whatwg.org/multipage/server-sent-events.html
No environment, credentials, fixtures, or network are accessed at import time.
"""

from __future__ import annotations

import base64
import copy
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

PATHS = {"native": "/v1/text/chatcompletion_v2", "openai": "/v1/chat/completions"}


@dataclass(frozen=True)
class Settings:
    base_url: str = ""
    api_key: str = ""
    model: str = "M2-her"
    response_model: str | None = None
    style: str = "native"
    timeout: float = 120.0
    extra_headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    auth_type: str = "bearer"

    @classmethod
    def from_env(cls) -> Settings:
        headers = json.loads(os.getenv("M2_HER_EXTRA_HEADERS", "{}"))
        if not isinstance(headers, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
        ):
            raise ValueError("M2_HER_EXTRA_HEADERS must be a JSON object of strings")
        query_params = json.loads(os.getenv("M2_HER_QUERY_PARAMS", "{}"))
        if not isinstance(query_params, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in query_params.items()
        ):
            raise ValueError("M2_HER_QUERY_PARAMS must be a JSON object of strings")
        settings = cls(
            base_url=os.getenv("M2_HER_BASE_URL", "").rstrip("/"),
            api_key=os.getenv("M2_HER_API_KEY", ""),
            model=os.getenv("M2_HER_MODEL", "M2-her"),
            response_model=os.getenv("M2_HER_RESPONSE_MODEL") or None,
            style=os.getenv("M2_HER_API_STYLE", "native"),
            timeout=float(os.getenv("M2_HER_TIMEOUT", "120")),
            extra_headers=headers,
            query_params=query_params,
            auth_type=os.getenv("M2_HER_AUTH_TYPE", "bearer").strip().lower(),
        )
        if settings.auth_type not in ("bearer", "none"):
            raise ValueError("M2_HER_AUTH_TYPE must be bearer or none")
        if settings.style not in PATHS:
            raise ValueError("M2_HER_API_STYLE must be native or openai")
        if not 0 < settings.timeout < float("inf"):
            raise ValueError("M2_HER_TIMEOUT must be a positive finite number")
        return settings

    @property
    def url(self) -> str:
        # Accept either a server origin or the familiar SDK base ending in /v1.
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        return str(
            httpx.URL(base + PATHS[self.style]).copy_merge_params(self.query_params)
        )

    @property
    def headers(self) -> dict[str, str]:
        headers = httpx.Headers({"Content-Type": "application/json"})
        headers.update(self.extra_headers)
        if self.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return dict(headers)


# ---------------- Run log (jsonl) ----------------
# Same mechanism as m3_format_check: conftest.pytest_configure sets
# RUN_LOG_PATH for the session (one file per xdist worker); direct imports
# outside pytest fall back to logs/run_<UTC-ts>.jsonl.
RUN_LOG_PATH: Path | None = None


def _fallback_log_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(__file__).parent / "logs" / f"run_{ts}.jsonl"


def _write_log_line(record: dict, path: Path | None = None) -> None:
    """Append one jsonl record; path overrides the session log when given."""
    global RUN_LOG_PATH
    if path is None:
        if RUN_LOG_PATH is None:
            RUN_LOG_PATH = _fallback_log_path()
        path = RUN_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def parse_sse(text: str) -> tuple[list[dict], list[str]]:
    """Parse SSE events, including multiline data, CRLF, comments and no-space fields.

    Invalid JSON, non-object payloads, data after DONE, and incomplete final
    events remain visible errors. Heartbeats and unknown SSE fields are ignored
    according to the framing specification, not mistaken for model chunks.
    """
    events, errors = [], []
    data, event_lines = [], []
    event_type = "message"
    done = False
    normalized = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    # The last split element is a cursor after the final newline, not another line.
    lines = normalized.split("\n")
    if normalized.endswith("\n"):
        lines.pop()
    for line in lines:
        if line == "":
            if data:
                value = "\n".join(data)
                event = {
                    "event": event_type,
                    "data": value,
                    "raw": "\n".join(event_lines),
                }
                if done:
                    errors.append("data event after [DONE]")
                if value == "[DONE]":
                    event["done"] = True
                    done = True
                else:
                    try:
                        value_json = json.loads(value)
                        if not isinstance(value_json, dict):
                            raise ValueError("SSE data must be a JSON object")
                        event["json"] = value_json
                    except ValueError as exc:
                        errors.append(f"invalid SSE data: {exc}")
                events.append(event)
            data, event_lines, event_type = [], [], "message"
            continue
        event_lines.append(line)
        if line.startswith(":"):
            continue
        name, sep, value = line.partition(":")
        value = value.removeprefix(" ") if sep else ""
        if name == "data":
            data.append(value)
        elif name == "event":
            event_type = value
    if data:
        errors.append("unterminated SSE event at EOF")
    return events, errors


@dataclass
class Response:
    status: int = 0
    headers: dict = field(default_factory=dict)
    body: Any = None
    raw_text: str = ""
    raw_base64: str = ""
    events: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stream: bool = False
    trace_id: str = ""

    @property
    def chunks(self) -> list[dict]:
        return [event["json"] for event in self.events if "json" in event]

    @property
    def documents(self) -> list[dict]:
        return ([self.body] if isinstance(self.body, dict) else []) + self.chunks

    @property
    def choices(self) -> list[dict]:
        # Native error envelopes legitimately contain choices=null.
        return [
            choice for doc in self.documents for choice in (doc.get("choices") or [])
        ]

    @property
    def content(self) -> str:
        """Single-candidate convenience view; use contents for non-stream n > 1."""
        if self.stream:
            return "".join(
                c.get("delta", {}).get("content") or "" for c in self.choices
            )
        choices = self.body.get("choices", []) if isinstance(self.body, dict) else []
        return (choices[0].get("message", {}).get("content") or "") if choices else ""

    @property
    def contents(self) -> list[str]:
        """All non-stream candidate texts, in wire order; never concatenate them."""
        assert not self.stream, "contents is for non-stream candidates"
        choices = (
            (self.body.get("choices") or []) if isinstance(self.body, dict) else []
        )
        return [choice.get("message", {}).get("content") or "" for choice in choices]

    @property
    def summaries(self) -> list[str]:
        return [c["message"]["content"] for c in self.choices if "message" in c]

    @property
    def finish_reason(self) -> str | None:
        reasons = [
            c.get("finish_reason")
            for c in self.choices
            if c.get("finish_reason") is not None
        ]
        return reasons[-1] if reasons else None

    @property
    def usage(self) -> dict | None:
        usage = [d["usage"] for d in self.documents if d.get("usage") is not None]
        return usage[-1] if usage else None


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Request logs show which credential was sent, never the credential itself."""
    redacted = {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            scheme, _, token = str(value).rpartition(" ")
            shown = f"{token[:4]}…{token[-4:]}" if len(token) > 16 else "***"
            value = f"{scheme} {shown}" if scheme else shown
        redacted[key] = value
    return redacted


class ChatClient:
    """A per-case client. request() sends the supplied payload/headers unchanged."""

    def __init__(
        self,
        settings: Settings,
        *,
        case_id="",
        log_path: Path | None = None,
        transport=None,
    ):
        self.settings = settings
        self.case_id = case_id
        self.log_path = log_path
        self.transport = transport
        self.request_count = 0

    def request(
        self, payload=None, *, raw: bytes | None = None, headers=None
    ) -> Response:
        if not self.settings.base_url:
            raise ValueError("Set M2_HER_BASE_URL before making live requests")
        if payload is not None and raw is not None:
            raise ValueError("Supply payload or raw, not both")
        payload = copy.deepcopy(payload)
        request_headers = dict(self.settings.headers if headers is None else headers)
        result = Response(
            stream=isinstance(payload, dict) and payload.get("stream") is True
        )
        self.request_count += 1
        started = time.monotonic()
        wire = b""
        error = None
        original_error = None
        try:
            with httpx.Client(
                timeout=self.settings.timeout, transport=self.transport
            ) as session:
                kwargs = {"content": raw} if raw is not None else {"json": payload}
                with session.stream(
                    "POST", self.settings.url, headers=request_headers, **kwargs
                ) as response:
                    result.status = response.status_code
                    result.headers = dict(response.headers)
                    # Decode after joining bytes: a UTF-8 code point can span TCP reads.
                    parts = []
                    try:
                        for part in response.iter_bytes():
                            parts.append(part)
                            if time.monotonic() - started > self.settings.timeout:
                                raise httpx.ReadTimeout(
                                    "overall M2-Her request deadline exceeded"
                                )
                    finally:
                        wire = b"".join(parts)
                        result.raw_text = wire.decode("utf-8", errors="replace")
                    try:
                        result.raw_text = wire.decode("utf-8")
                    except UnicodeDecodeError as exc:
                        result.errors.append(f"invalid UTF-8: {exc}")
                    media_type = (
                        result.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if media_type == "text/event-stream":
                        result.events, parse_errors = parse_sse(result.raw_text)
                        result.errors.extend(parse_errors)
                    else:
                        try:
                            result.body = json.loads(result.raw_text)
                        except ValueError as exc:
                            result.errors.append(f"invalid JSON response: {exc}")
            return result
        except Exception as exc:
            original_error = exc
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            result.raw_base64 = base64.b64encode(wire).decode()
            result.trace_id = next(
                (
                    result.headers[k]
                    for k in ("x-request-id", "x-trace-id", "trace-id")
                    if result.headers.get(k)
                ),
                next((str(d["id"]) for d in result.documents if d.get("id")), ""),
            )
            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "case_id": self.case_id,
                "request_number": self.request_count,
                "endpoint": self.settings.style,
                "api_style": self.settings.style,
                "url": self.settings.url,
                "model": self.settings.model,
                "stream": result.stream,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "status": result.status,
                "trace_id": result.trace_id,
                "request_headers": redact_headers(request_headers),
                "request": payload,
                "request_raw_base64": base64.b64encode(raw).decode()
                if raw is not None
                else None,
                "response": asdict(result),
                "error": error,
            }
            try:
                _write_log_line(record, self.log_path)
            except OSError as log_error:
                if original_error is None:
                    raise
                original_error.add_note(
                    f"Also failed to write request evidence: {log_error}"
                )

    def chat(self, messages: list[dict], *, stream=False, **params) -> Response:
        """Convenience for normal cases; omissions/invalid envelopes use request()."""
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": stream,
            "max_completion_tokens": 128,
        }
        payload.update(params)
        return self.request(payload)


def message(role: str, content: str, **extra) -> dict:
    return {"role": role, "content": content, **extra}


def simple_messages(prompt="Reply with exactly OK", system=None) -> list[dict]:
    return ([message("system", system)] if system is not None else []) + [
        message("user", prompt)
    ]


def assert_usage(usage, *, breakdown=False):
    assert isinstance(usage, dict), f"missing/invalid usage: {usage!r}"
    assert type(usage.get("total_tokens")) is int and usage["total_tokens"] >= 0, usage
    present = {key for key in ("prompt_tokens", "completion_tokens") if key in usage}
    if breakdown or present:
        for key in ("prompt_tokens", "completion_tokens"):
            assert type(usage.get(key)) is int and usage[key] >= 0, usage
        assert (
            usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        ), usage
    details = usage.get("prompt_tokens_details")
    if details is not None:
        assert isinstance(details, dict), details
        if "cached_tokens" in details:
            cached = details["cached_tokens"]
            assert type(usage.get("prompt_tokens")) is int, (
                "cached tokens require a prompt token count"
            )
            assert type(cached) is int and 0 <= cached <= usage["prompt_tokens"], usage


def assert_success(result: Response, *, nonempty=True, expected_choices=1):
    """Validate the requested count, every candidate, and single-choice SSE.

    The default remains one: unexpected extra candidates are not silently accepted.
    Native n > 1 is non-stream only; streaming conflicts have rejection cases.
    """
    assert type(expected_choices) is int and expected_choices > 0, (
        "expected_choices must be a positive integer"
    )
    assert not result.stream or expected_choices == 1, (
        "native streaming supports only one candidate"
    )
    context = f"status={result.status}, trace={result.trace_id}, body={result.raw_text[:1000]}"
    assert result.status == 200, context
    assert not result.errors, f"{result.errors}: {context}"
    for doc in result.documents:
        assert not doc.get("error"), context
        if "base_resp" in doc:
            base = doc["base_resp"]
            assert isinstance(base, dict) and type(base.get("status_code")) is int, (
                context
            )
            assert base["status_code"] == 0, context
        assert isinstance(doc.get("choices"), list), context
        for choice in doc["choices"]:
            assert isinstance(choice, dict), context
            assert (
                type(choice.get("index")) is int
                and 0 <= choice["index"] < expected_choices
            ), f"invalid choice index: {context}"
            key = "delta" if "delta" in choice else "message"
            assert isinstance(choice.get(key), dict), context
            value = choice[key]
            if "role" in value:
                assert value["role"] == "assistant", context
            if "content" in value:
                assert (
                    value["content"] is None
                    and key == "delta"
                    or isinstance(value["content"], str)
                ), context
            if key == "message":
                assert value.get("role") == "assistant" and isinstance(
                    value.get("content"), str
                ), context
            if choice.get("finish_reason") is not None:
                assert choice["finish_reason"] in ("stop", "length"), context
    if result.stream:
        assert (
            result.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            == "text/event-stream"
        ), context
        assert result.chunks and any("delta" in c for c in result.choices), context
        assert not any(e["event"] == "error" for e in result.events), context
        reasons = {
            c.get("finish_reason")
            for c in result.choices
            if c.get("finish_reason") is not None
        }
        assert len(reasons) == 1, f"missing/conflicting finish_reason: {context}"
        finished = False
        for choice in result.choices:
            assert not (finished and choice.get("delta", {}).get("content")), (
                f"content after finish_reason: {context}"
            )
            finished = finished or choice.get("finish_reason") is not None
        for summary in result.summaries:
            assert summary == result.content, (
                f"native summary differs from deltas: {context}"
            )
    else:
        assert isinstance(result.body, dict), context
        choices = result.body["choices"]
        assert len(choices) == expected_choices, (
            f"expected {expected_choices} choices, got {len(choices)}: {context}"
        )
        assert {c["index"] for c in choices} == set(range(expected_choices)), (
            f"missing or duplicate choice indices: {context}"
        )
        for choice in choices:
            assert "message" in choice and "delta" not in choice, context
            assert choice.get("finish_reason") in ("stop", "length"), (
                f"choice {choice['index']} missing/invalid finish_reason: {context}"
            )
            if nonempty:
                assert choice["message"]["content"].strip(), (
                    f"empty assistant content in choice {choice['index']}: {context}"
                )
        assert_usage(result.usage)
    if result.stream:
        assert result.finish_reason in ("stop", "length"), context
        if nonempty:
            assert result.content.strip(), f"empty assistant content: {context}"


def assert_envelope(result: Response, *, model: str | None = None):
    for doc in result.documents:
        assert isinstance(doc.get("id"), str) and doc["id"], doc
        assert isinstance(doc.get("model"), str) and doc["model"], doc
        if model is not None:
            assert doc["model"] == model, (
                f"expected response model {model!r}, got {doc['model']!r}"
            )
        assert type(doc.get("created")) is int and doc["created"] > 0, doc
        expected = (
            "chat.completion"
            if any("message" in c for c in doc["choices"])
            else "chat.completion.chunk"
        )
        assert doc.get("object") == expected, doc
    for key in ("id", "model", "created"):
        assert len({d[key] for d in result.documents}) == 1, f"inconsistent {key}"


def response_documents(result: Response) -> list[dict]:
    """Every JSON object on the wire, tolerant of how an endpoint frames errors.

    SSE responses contribute their data events. Other bodies may hold several
    back-to-back JSON documents; anything that does not parse is ignored here
    because the caller only looks for error markers and completion text.
    """
    if result.events:
        return result.chunks
    decoder, text, index, documents = json.JSONDecoder(), result.raw_text, 0, []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        try:
            document, index = decoder.raw_decode(text, index)
        except ValueError:
            break
        if isinstance(document, dict):
            documents.append(document)
    return documents


def request_failed(result: Response) -> bool:
    """True when the endpoint refused the request, however it reports that.

    Either the HTTP status is not 200, or an HTTP 200 body / SSE event carries
    a non-zero business code (base_resp.status_code) or an error object.
    Error codes, messages and framing are deliberately not compared.
    """
    if result.status != 200:
        return True
    return any(
        doc.get("error") or (doc.get("base_resp") or {}).get("status_code")
        for doc in response_documents(result)
    )


def _completion_text(result: Response) -> str:
    text = []
    for doc in response_documents(result):
        for choice in doc.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            for part in (choice.get("message"), choice.get("delta")):
                if isinstance(part, dict) and isinstance(part.get("content"), str):
                    text.append(part["content"])
    return "".join(text)


def assert_request_failed(result: Response):
    """Unified rejection check for invalid requests.

    PASS: HTTP status is not 200, or HTTP 200 with a non-zero business code or
    an error object, and no normal reply text came back.
    """
    context = (
        f"status={result.status}, trace={result.trace_id}, "
        f"body={result.raw_text[:1000]}"
    )
    assert request_failed(result), f"request was not rejected: {context}"
    assert not _completion_text(result).strip(), (
        f"rejected request still returned reply text: {context}"
    )


def assert_accepted_or_failed(result: Response, *, nonempty=True) -> str:
    """Values the docs rule out but some endpoints accept: either is fine.

    A rejection must follow assert_request_failed; an acceptance must be a
    well-formed reply. HTTP 5xx is a server fault and always fails.
    """
    assert result.status < 500, (
        f"server error instead of accept/reject: status={result.status}, "
        f"trace={result.trace_id}, body={result.raw_text[:1000]}"
    )
    if request_failed(result):
        assert_request_failed(result)
        return "rejected"
    assert_success(result, nonempty=nonempty)
    return "accepted"


def assert_contains(result: Response, *values: str):
    assert_success(result)
    for value in values:
        assert value in result.content, (
            f"missing {value!r}: {result.content!r}; trace={result.trace_id}"
        )


def assert_limit(result: Response, limit: int, *, truncated=False):
    # EOS may occur before the budget; a prompt cannot force generation length.
    assert_success(result, nonempty=False)
    # Validate any observed fields before reporting missing optional evidence.
    if result.usage is not None:
        assert_usage(result.usage)
    if not result.usage or "completion_tokens" not in result.usage:
        raise LimitNotExercised(
            "completion_tokens not observed; output budget not validated"
        )
    assert_usage(result.usage, breakdown=True)
    assert result.usage["completion_tokens"] <= limit, result.usage
    if result.finish_reason == "length":
        assert result.usage["completion_tokens"] == limit, result.usage
    if truncated and result.finish_reason != "length":
        raise LimitNotExercised(
            f"truncation not exercised: natural finish={result.finish_reason}; "
            "observed usage is within budget"
        )


def assert_stop_observed(result: Response, limit: int):
    """A short prompt is a sampling strategy, not a promise of natural EOS."""
    assert_success(result)
    if result.finish_reason == "length":
        assert_limit(result, limit)
        raise EvidenceNotObserved("Natural stop not observed; valid length completion")


class EvidenceNotObserved(AssertionError):
    """An optional protocol field needed to prove a claim was not observed."""


class LimitNotExercised(EvidenceNotObserved):
    """Missing counts or natural completion cannot establish an output ceiling."""


def assert_sensitivity_fields(result: Response) -> int:
    """Validate observed native metadata, without requiring optional fields."""
    observed = 0
    for doc in result.documents:
        for key in ("input_sensitive", "output_sensitive"):
            if key in doc:
                assert type(doc[key]) is bool, f"{key} must be boolean: {doc[key]!r}"
                observed += 1
        for key in ("input_sensitive_type", "output_sensitive_type"):
            if key in doc:
                assert type(doc[key]) is int, f"{key} must be integer: {doc[key]!r}"
                observed += 1
    return observed


def assert_prompt_tokens_match(non_stream: Response, stream: Response):
    """Compare the input counts only; generated output counts may differ."""
    for result in (non_stream, stream):
        assert_success(result)
        if result.usage is not None:
            assert_usage(result.usage)
    if any(not r.usage or "prompt_tokens" not in r.usage for r in (non_stream, stream)):
        raise EvidenceNotObserved(
            "prompt_tokens not observed in both modes; input accounting not validated"
        )
    assert non_stream.usage["prompt_tokens"] == stream.usage["prompt_tokens"], (
        f"input token counts differ: non_stream={non_stream.usage}, stream={stream.usage}"
    )


# success: must reply; reject: must fail (assert_request_failed);
# either: accepting or rejecting are both fine, but never a 5xx.
OUTCOMES = ("success", "reject", "either")


def read_contract(path: str | None) -> dict:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contract file must be a JSON object")
    for key, rule in data.items():
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("source"), str)
            or not rule["source"].strip()
        ):
            raise ValueError(
                f"{key}: contract must record a nonempty source/decision reference"
            )
        if rule.get("outcome") not in OUTCOMES:
            raise ValueError(f"{key}: outcome must be one of {', '.join(OUTCOMES)}")
        if "precedence_over" in rule and (
            type(rule["precedence_over"]) is not int
            or not 0 < rule["precedence_over"] < rule.get("completion_limit", 0)
        ):
            raise ValueError(
                f"{key}: precedence_over must be a positive int below completion_limit"
            )
        if "completion_limit" in rule and (
            type(rule["completion_limit"]) is not int
            or not 1 <= rule["completion_limit"] <= 2048
        ):
            raise ValueError(f"{key}: completion_limit must be an integer in [1, 2048]")
        if "contains" in rule and (
            not isinstance(rule["contains"], str) or not rule["contains"].strip()
        ):
            raise ValueError(f"{key}: contains must be a nonempty string")
        for field_name in (
            "done",
            "summary",
            "usage",
            "usage_only_last",
            "prompt_tokens_equal",
        ):
            if field_name in rule and type(rule[field_name]) is not bool:
                raise ValueError(f"{key}: {field_name} must be boolean")
    return data


def assert_contract(result: Response, rule: dict):
    if rule["outcome"] == "reject":
        assert_request_failed(result)
        return
    if rule["outcome"] == "either" and assert_accepted_or_failed(
        result, nonempty=rule.get("completion_limit") != 1
    ) == "rejected":
        return
    assert_success(result, nonempty=rule.get("completion_limit") != 1)
    if "contains" in rule:
        assert_contains(result, rule["contains"])
    if "finish_reason" in rule:
        assert result.finish_reason == rule["finish_reason"], result.finish_reason
    if "completion_limit" in rule:
        assert_usage(result.usage, breakdown=True)
        assert_limit(result, rule["completion_limit"])
        if result.finish_reason == "length":
            assert result.usage["completion_tokens"] == rule["completion_limit"], (
                result.usage
            )
    for key, actual in (
        ("done", any(e.get("done") for e in result.events)),
        ("summary", bool(result.summaries)),
        ("usage", result.usage is not None),
    ):
        if key in rule:
            assert type(rule[key]) is bool and actual == rule[key], (
                key,
                actual,
                rule[key],
            )
    if "completion_limit" in rule and result.finish_reason != "length":
        raise LimitNotExercised(
            "Output stopped naturally; completion ceiling not exercised"
        )


def packet_metrics(result: Response) -> dict:
    sizes = [
        len(c["delta"]["content"])
        for c in result.choices
        if c.get("delta", {}).get("content")
    ]
    return packet_distribution(sizes)


def packet_distribution(sizes: list[int]) -> dict:
    """M3's five distribution dimensions, with no inherited M3 thresholds."""
    assert sizes and all(type(n) is int and n > 0 for n in sizes), (
        "no nonempty content packets or invalid packet sizes"
    )
    total = sum(sizes)
    return {
        "sizes": sizes,
        "count": len(sizes),
        "characters": total,
        "tiny_packet_ratio": sum(n <= 4 for n in sizes) / len(sizes),
        "normal_packet_ratio": sum(5 <= n <= 200 for n in sizes) / len(sizes),
        "large_packet_ratio": sum(n > 200 for n in sizes) / len(sizes),
        "normal_character_ratio": sum(n for n in sizes if 5 <= n <= 200) / total,
        "large_character_ratio": sum(n for n in sizes if n > 200) / total,
    }


def sdk_request(client: ChatClient, messages: list[dict], *, stream=False) -> Response:
    """Verify SDK serialization/deserialization through the real logged transport.

    The SDK receives the exact response bytes. Buffering here deliberately does
    not measure SDK delivery latency; native chunk timing is not a quality metric.
    max_retries=0 prevents hidden duplicate requests.
    """
    from openai import APIStatusError, OpenAI

    responses = []

    def forward(request: httpx.Request):
        assert str(request.url) == client.settings.url, request.url
        headers = dict(request.headers)
        if client.settings.auth_type == "none":
            headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
        result = client.request(json.loads(request.content), headers=headers)
        responses.append(result)
        # iter_bytes decoded Content-Encoding already; don't decompress twice.
        headers = {
            k: v
            for k, v in result.headers.items()
            if k.lower()
            not in ("content-encoding", "content-length", "transfer-encoding")
        }
        return httpx.Response(
            result.status, headers=headers, content=base64.b64decode(result.raw_base64)
        )

    assert client.settings.style == "openai", "SDK path requires the OpenAI protocol"
    with OpenAI(
        api_key=client.settings.api_key or "unused",
        base_url=str(httpx.URL(client.settings.url).copy_with(query=None)).removesuffix(
            "/chat/completions"
        ),
        default_query=client.settings.query_params,
        default_headers={
            k: v
            for k, v in client.settings.extra_headers.items()
            if k.lower() != "authorization"
        },
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(forward)),
    ) as sdk:
        try:
            response = sdk.chat.completions.create(
                model=client.settings.model,
                messages=messages,
                max_completion_tokens=128,
                stream=stream,
            )
            if stream:
                with response:
                    sdk_content = "".join(
                        chunk.choices[0].delta.content or ""
                        for chunk in response
                        if chunk.choices
                    )
            else:
                sdk_content = response.choices[0].message.content
        except APIStatusError:
            assert len(responses) == 1, (
                "SDK request failed before its response could be captured"
            )
            return responses[0]
    assert len(responses) == 1, "unexpected SDK retries"
    assert sdk_content == responses[0].content, "SDK content differs from wire response"
    return responses[0]


def read_context_samples(path: str, model: str) -> dict:
    """Validate supplied calibration evidence without estimating tokens from text."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data.get("model") == model, (
        "context measurements must match the configured model"
    )
    assert data.get("counting") == "input_plus_max_output", (
        "record the confirmed context counting rule"
    )
    assert isinstance(data.get("source"), str) and data["source"].strip(), (
        "measurement source is required"
    )
    window = data.get("context_window_tokens")
    assert type(window) is int and window in (64000, 65536), (
        "record which 64K definition was confirmed"
    )
    for kind in ("within", "over"):
        sample = data[kind]
        assert isinstance(sample["messages"], list) and sample["messages"]
        assert type(sample["prompt_tokens"]) is int and sample["prompt_tokens"] > 0
        assert (
            type(sample["max_completion_tokens"]) is int
            and 1 <= sample["max_completion_tokens"] <= 2048
        )
        total = sample["prompt_tokens"] + sample["max_completion_tokens"]
        assert (total <= window) == (kind == "within"), (
            f"{kind} sample is on the wrong side of the boundary"
        )
    if "expected_marker" in data["within"]:
        assert (
            isinstance(data["within"]["expected_marker"], str)
            and data["within"]["expected_marker"]
        )
    return data
