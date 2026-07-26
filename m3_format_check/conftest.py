"""
M3 API Test Suite — Configuration & Fixtures
Covers: OAI /v1/chat/completions only

Required env vars:
  M3_BASE_URL  — API base URL (e.g. https://your-endpoint.example.com)
  M3_API_KEY   — API key (e.g. sk-xxx)

Optional env vars:
  M3_MODEL      — Model ID (default: MiniMax-M3)
  M3_MODEL_MINI — Mini model ID (default: MiniMax-M2-mini)
  M3_RUN_LOG    — Override the per-run jsonl path. Default is
                  ./logs/run_<UTC-ts>.jsonl (or run_<UTC-ts>_<workerid>.jsonl
                  per worker when running under pytest-xdist).

Concurrency:
  Serial (default):
    pytest

  Parallel via pytest-xdist (declared in requirements.txt):
    pytest -n auto       # one worker per CPU
    pytest -n 8          # explicit worker count

  Each worker writes to its own jsonl file (run_<ts>_gw0.jsonl,
  run_<ts>_gw1.jsonl, ...) so log lines never interleave. Concatenate them
  afterwards with `cat logs/run_<ts>_gw*.jsonl > run_<ts>.jsonl` if a single
  file is needed.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

BASE_URL = os.environ.get("M3_BASE_URL")
API_KEY = os.environ.get("M3_API_KEY")
AUTH_TYPE = os.environ.get("M3_AUTH_TYPE", "bearer").strip().lower()
MODEL = os.environ.get("M3_MODEL", "MiniMax-M3")
MODEL_MINI = os.environ.get("M3_MODEL_MINI", "MiniMax-M2-mini")

# Capability switch: some implementations do not pass through the OAI extension
# field `reasoning_split`. Set M3_SKIP_REASONING_SPLIT=1 to skip cases that
# depend on this field. Default 0 (do not skip) to preserve existing behavior.
SKIP_REASONING_SPLIT = os.environ.get("M3_SKIP_REASONING_SPLIT", "").strip() in ("1", "true", "True", "yes")


def _resolve_log_path(config) -> Path:
    """Decide the jsonl path for this process.

    Under xdist, the main controller computes the timestamp once and ships it
    to each worker via workerinput; workers append their own gw<N> suffix so
    every process writes to its own file (no cross-process interleaving).
    """
    override = os.environ.get("M3_RUN_LOG")
    if override:
        return Path(override).expanduser().resolve()

    workerinput = getattr(config, "workerinput", None)
    if workerinput is not None:
        # xdist worker: timestamp comes from the controller via workerinput.
        ts = workerinput["m3_run_ts"]
        worker_id = workerinput["workerid"]  # e.g. "gw0"
        suffix = f"_{worker_id}"
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Tag main controller log under xdist so it does not collide with gw*.
        # When running serially there is no controller-vs-worker split, so no suffix.
        suffix = "_main" if _is_xdist_controller(config) else ""

    return Path(__file__).parent / "logs" / f"run_{ts}{suffix}.jsonl"


def _is_xdist_controller(config) -> bool:
    """True if this process is the xdist controller (numprocesses > 0 and not a worker)."""
    if getattr(config, "workerinput", None) is not None:
        return False
    n = getattr(config.option, "numprocesses", None)
    return bool(n) and n != 0


def pytest_configure(config):
    if AUTH_TYPE not in ("bearer", "none"):
        raise pytest.UsageError(
            f"\n\nUnsupported M3_AUTH_TYPE={AUTH_TYPE!r}; expected 'bearer' or 'none'."
        )
    if not BASE_URL or (AUTH_TYPE == "bearer" and not API_KEY):
        raise pytest.UsageError(
            "\n\nMissing required environment variables!\n"
            "Please set before running:\n"
            "  export M3_BASE_URL='https://your-endpoint.example.com'\n"
            "  export M3_API_KEY='sk-your-api-key'  # required for bearer auth\n"
            "  export M3_AUTH_TYPE='none'           # for endpoints without auth\n"
        )

    # Stash a single timestamp on the controller so workers can share it.
    if _is_xdist_controller(config) and not hasattr(config, "_m3_run_ts"):
        config._m3_run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    log_path = _resolve_log_path(config)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    import helpers
    helpers.RUN_LOG_PATH = log_path

    # Visible at the top of pytest output so users can grab the path fast.
    # Workers stay quiet (xdist already aggregates their output and we don't
    # want one print-per-worker cluttering the header).
    if getattr(config, "workerinput", None) is None:
        print(f"\n[m3_api_test] run log → {log_path}")


# pytest_configure_node is an xdist-only hook. Define it conditionally so that
# pytest without xdist loaded doesn't warn about an unknown hook.
try:
    import xdist  # noqa: F401

    def pytest_configure_node(node):
        """xdist hook: ship controller-side state into each worker's workerinput."""
        ts = getattr(node.config, "_m3_run_ts", None)
        if ts is None:
            # Should not happen in practice — controller sets _m3_run_ts above.
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        node.workerinput["m3_run_ts"] = ts
except ImportError:
    pass


@pytest.fixture
def base_url():
    return BASE_URL


@pytest.fixture
def api_key():
    return API_KEY


@pytest.fixture
def model():
    return MODEL


@pytest.fixture
def model_mini():
    return MODEL_MINI


@pytest.fixture
def oai_headers():
    headers = {"Content-Type": "application/json"}
    if AUTH_TYPE == "bearer":
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers
