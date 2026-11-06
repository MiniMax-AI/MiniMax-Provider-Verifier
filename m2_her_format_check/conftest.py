"""Configuration is local to this suite; collect-only never needs credentials."""

import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from . import helpers as _helpers
from .exercises import calibrate_context
from .helpers import (
    ChatClient,
    Settings,
    assert_limit,
    assert_success,
    read_context_samples,
    read_contract,
    simple_messages,
)


def _resolve_log_path(config) -> Path:
    """Same layout as m3_format_check: logs/run_<UTC-ts>[_gw<N>].jsonl.

    Under xdist the controller picks one timestamp and ships it to the
    workers, so every worker writes its own file and lines never interleave.
    M2_HER_RUN_LOG overrides the path; workers add their _gw<N> suffix to it.
    """
    workerinput = getattr(config, "workerinput", None)
    suffix = f"_{workerinput['workerid']}" if workerinput is not None else ""
    override = os.environ.get("M2_HER_RUN_LOG")
    if override:
        path = Path(override).expanduser().resolve()
        return path.with_name(f"{path.stem}{suffix}{path.suffix or '.jsonl'}")
    if workerinput is not None:
        ts = workerinput["m2_her_run_ts"]
    else:
        ts = getattr(config, "_m2_her_run_ts", None) or datetime.now(
            UTC
        ).strftime("%Y%m%dT%H%M%SZ")
    return Path(__file__).parent / "logs" / f"run_{ts}{suffix}.jsonl"


def _is_xdist_controller(config) -> bool:
    if getattr(config, "workerinput", None) is not None:
        return False
    n = getattr(config.option, "numprocesses", None)
    return bool(n) and n != 0


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
        help="n limit for 17_08 (default: 4, the official limit)",
    )


def pytest_configure(config):
    # Check on the controller, before xdist starts workers. Explicit offline
    # regression files and collection-only inventory need no live configuration.
    suite_dir = Path(__file__).parent
    targets = [Path(arg.split("::", 1)[0]).resolve() for arg in config.args]
    live = any(
        target == suite_dir
        or target in suite_dir.parents
        or (target.parent == suite_dir and target.match("m2_her_*_tests.py"))
        for target in targets
    )
    if live and not config.option.collectonly:
        settings = Settings.from_env()
        if settings.style == "openai" and not config.getoption("--run-compat"):
            raise pytest.UsageError(
                "OpenAI verification requires --run-compat (add --run-slow for packet sampling)"
            )
        if not settings.base_url or (
            settings.auth_type == "bearer" and not settings.api_key
        ):
            raise pytest.UsageError(
                "Set M2_HER_BASE_URL and configure M2_HER_API_KEY or M2_HER_AUTH_TYPE=none"
            )
    if not hasattr(config, "workerinput"):
        config.pluginmanager.register(_LiveCoverage(), "m2-her-live-coverage")
    n_limit = config.getoption("--n-limit")
    if n_limit is not None and n_limit < 1:
        raise pytest.UsageError("--n-limit must be a confirmed positive integer")
    if _is_xdist_controller(config) and not hasattr(config, "_m2_her_run_ts"):
        config._m2_her_run_ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if config.pluginmanager.hasplugin("xdist") and not config.pluginmanager.has_plugin(
        "m2-her-xdist-hooks"
    ):
        config.pluginmanager.register(_XdistHooks(), "m2-her-xdist-hooks")
    _helpers.RUN_LOG_PATH = _resolve_log_path(config)
    # Workers stay quiet; the controller prints where the per-worker files go.
    if getattr(config, "workerinput", None) is None and not config.option.collectonly:
        shown = _helpers.RUN_LOG_PATH
        if _is_xdist_controller(config):
            shown = shown.with_name(f"{shown.stem}_gw*{shown.suffix}")
        print(f"\n[m2_her_api_test] run log → {shown}")
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


class _XdistHooks:
    """Registered only when xdist is active, so plain pytest never sees the hook."""

    def pytest_configure_node(self, node):
        """Share the controller's log timestamp with each worker."""
        ts = getattr(node.config, "_m2_her_run_ts", None) or datetime.now(
            UTC
        ).strftime("%Y%m%dT%H%M%SZ")
        node.workerinput["m2_her_run_ts"] = ts


class _LiveCoverage:
    """SKIP remains visible per case. A run with zero live verdicts cannot certify a provider."""

    def __init__(self):
        self.seen = False
        self.validated = False

    def pytest_runtest_logreport(self, report):
        if Path(report.location[0]).match("m2_her_*_tests.py"):
            self.seen = True
            if report.when == "call" and report.passed:
                self.validated = True

    def pytest_sessionfinish(self, session, exitstatus):
        if exitstatus == pytest.ExitCode.OK and self.seen and not self.validated:
            session.exitstatus = pytest.ExitCode.NO_TESTS_COLLECTED
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            if reporter is not None:
                reporter.write_line(
                    "No M2-Her live case produced a verdict. See the SKIP reasons."
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
    return _helpers.RUN_LOG_PATH


@pytest.fixture
def client(settings, log_path, request):
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
