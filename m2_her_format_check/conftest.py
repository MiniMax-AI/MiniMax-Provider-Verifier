"""Configuration is local to this suite; collect-only never needs credentials."""

import os
import json
import copy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import httpx

from .helpers import (
    ChatClient,
    Settings,
    assert_limit,
    assert_success,
    read_context_samples,
    read_contract,
    simple_messages,
)
from .exercises import calibrate_context


def pytest_addoption(parser):
    group = parser.getgroup("m2-her")
    group.addoption(
        "--run-slow", action="store_true", help="Run M2-Her long-input cases"
    )
    group.addoption(
        "--run-compat",
        action="store_true",
        help="Run M2-Her compatibility cases with the bundled acceptance baseline",
    )
    group.addoption(
        "--run-behavior",
        action="store_true",
        help="Run prompt/quality evaluations separately from API conformance",
    )
    group.addoption(
        "--contract", help="JSON overrides for the bundled project acceptance baseline"
    )
    group.addoption(
        "--context-fixture",
        help="JSON file with measured within/over-context request samples",
    )
    group.addoption(
        "--context-window",
        type=int,
        choices=(64000, 65536),
        default=64000,
        help="Project context-window baseline for automatic calibration",
    )
    group.addoption(
        "--n-limit",
        type=int,
        help="Confirmed deployment n limit; omitted values use bounded runtime preparation",
    )


def pytest_configure(config):
    n_limit = config.getoption("--n-limit")
    if n_limit is not None and n_limit < 1:
        raise pytest.UsageError("--n-limit must be a confirmed positive integer")
    config.addinivalue_line("markers", "slow: long M2-Her inputs (opt in)")
    config.addinivalue_line("markers", "compat: M2-Her endpoint contracts (opt in)")
    config.addinivalue_line(
        "markers", "behavior: task-specific model quality, not an API format guarantee"
    )
    config.addinivalue_line(
        "markers", "implementation: native fields confirmed by service implementation"
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        if Path(__file__).parent not in Path(str(item.path)).parents:
            continue
        tier = (
            "behavior"
            if item.get_closest_marker("behavior")
            else "endpoint_contract"
            if item.get_closest_marker("compat")
            else "implementation_api"
            if item.get_closest_marker("implementation")
            else "documented_api"
        )
        item.user_properties.append(("validation_tier", tier))
        for marker, option in (
            ("slow", "--run-slow"),
            ("compat", "--run-compat"),
            ("behavior", "--run-behavior"),
        ):
            if item.get_closest_marker(marker) and not config.getoption(option):
                item.add_marker(
                    pytest.mark.skip(
                        reason=f"M2-Her {marker}: enable {option}; not validated"
                    )
                )


@pytest.fixture(scope="session")
def settings():
    return Settings.from_env()


@pytest.fixture
def n_limit(pytestconfig):
    # Runtime preparation belongs to the test call, so failures are recorded as
    # failed assertions with request evidence, not fixture skips/errors.
    return pytestconfig.getoption("--n-limit")


@pytest.fixture(scope="session")
def log_path():
    base = os.getenv("M2_HER_RUN_LOG")
    worker = os.getenv("PYTEST_XDIST_WORKER", "serial")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = Path(base) if base else Path(__file__).parent / "logs" / f"run_{stamp}.jsonl"
    return path.with_name(
        f"{path.stem}_{worker}_{os.getpid()}{path.suffix or '.jsonl'}"
    )


@pytest.fixture
def client(settings, log_path, request):
    if not settings.base_url or not settings.api_key:
        pytest.skip("Live API not validated: set M2_HER_BASE_URL and M2_HER_API_KEY")
    if settings.style != "native" and not request.node.get_closest_marker("compat"):
        pytest.skip(
            "M2-her native contract only; use explicit endpoint cases for OpenAI"
        )
    return ChatClient(settings, case_id=request.node.nodeid, log_path=log_path)


@pytest.fixture(scope="session")
def preflight():
    """Negative checks require a healthy control for this endpoint and stream mode.

    Cache both outcomes within each worker. A failed control is unvalidated,
    never evidence that the mutated field was correctly rejected.
    """
    outcomes = {}

    def require(client, *, stream=False, messages=None):
        settings = client.settings
        control_messages = simple_messages() if messages is None else messages
        key = (
            settings.url,
            settings.model,
            tuple(sorted(settings.headers.items())),
            stream,
            json.dumps(control_messages, sort_keys=True, ensure_ascii=False),
        )
        if key not in outcomes:
            control = ChatClient(
                settings,
                case_id=f"preflight/{settings.style}/{'stream' if stream else 'non_stream'}",
                log_path=client.log_path,
                transport=client.transport,
            )
            try:
                result = control.chat(
                    control_messages, stream=stream, max_completion_tokens=32
                )
                assert_success(result)
            except (AssertionError, httpx.HTTPError) as exc:
                outcomes[key] = f"Preflight failed; negative case not validated: {exc}"
            else:
                outcomes[key] = None
        if outcomes[key] is not None:
            pytest.skip(outcomes[key])

    return require


@pytest.fixture
def check_limit():
    """Budget checks require measured counts; unavailable evidence is an explicit failure."""
    return assert_limit


@pytest.fixture(scope="session")
def contracts(pytestconfig):
    baseline = read_contract(str(Path(__file__).parent / "acceptance_baseline.json"))
    baseline.update(read_contract(pytestconfig.getoption("--contract")))
    return baseline


@pytest.fixture
def contract(contracts):
    def require(key):
        if key not in contracts:
            raise AssertionError(
                f"Missing acceptance baseline for {key}; add the case's expected outcome before running"
            )
        return contracts[key]

    return require


@pytest.fixture
def context_samples(pytestconfig, settings, client, stream):
    path = pytestconfig.getoption("--context-fixture")
    if path:
        samples = read_context_samples(path, settings.model)
        if "stream" in samples:
            assert samples["stream"] is stream, (
                "Calibration file is for a different stream mode"
            )
        return samples
    cache = getattr(pytestconfig, "_her_context_samples", None)
    if cache is None:
        cache = pytestconfig._her_context_samples = {}
    window = pytestconfig.getoption("--context-window")
    key = (
        settings.url,
        settings.model,
        tuple(sorted(settings.headers.items())),
        window,
        stream,
    )
    if key not in cache:
        cache[key] = calibrate_context(client, window=window, stream=stream)
    return copy.deepcopy(cache[key])
