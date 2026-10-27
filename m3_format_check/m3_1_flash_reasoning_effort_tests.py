"""
M3 API Test — reasoning_effort (thinking-depth) case collection

This suite validates two capability groups for MiniMax-M3.1-Flash:

Group 1 — thinking.type must support ["enabled", "adaptive", "disabled"]
          simultaneously, responding with reasoning content per the parameter:
  1.1 enabled : forced thinking → return reasoning_content AND
                reasoning_tokens > 0.
  1.2 adaptive: model decides whether to think; when triggered → return
                reasoning_content AND reasoning_tokens > 0.
  1.3 disabled: forced off → NO reasoning_content AND reasoning_tokens == 0.

Group 2 — reasoning_effort controls thinking depth:
  2.1 `none` is NOT accepted.
  2.2 accepted enum: low / medium / high / xhigh / max.

reasoning_tokens is always asserted through _assert_reasoning_tokens(), which
requires usage.completion_tokens_details.reasoning_tokens to be PRESENT in both
directions — a missing field would let the "== 0" branch pass vacuously. The
magnitude is deliberately not sanity-checked against the reasoning text: no
tokenizer is introduced, so > 0 is sufficient.

Thinking presence is asserted through the local _assert_thinking_on(), which is
stricter than helpers.assert_thinking_present(): an inline <think> tag in
content does NOT count. Requirement 1 says the model must respond with
`reasoning_content`, and reasoning_split defaults to true for this model.

Every case is parametrized over non_stream + stream. The two paths differ
structurally (aggregated message.reasoning_content vs accumulated
delta.reasoning_content, usage only in the terminal SSE chunk), so a contract
verified on one says nothing about the other.

Additional spec notes (/api-reference/text-chat-openai):
  - Models that do not support reasoning_effort ignore the field entirely.
  - `minimal` is mapped to `low`.
  - Out-of-enum values are ignored; the model falls back to default depth.
  - reasoning_split defaults to true for such a model, so thinking is returned
    in the dedicated `reasoning_content` field (not an inline <think> tag).

This is a standalone suite (deliberately separate from the general M3 case
set). There is no in-file model gating: whatever M3_MODEL you provide is used
as-is, so point it at a model that supports reasoning_effort. Run with:

    M3_BASE_URL=... M3_API_KEY=... M3_MODEL=<model-id> \\
        python3 -m pytest m3_1_flash_reasoning_effort_tests.py -v

Case naming convention: test_<module_id>_<index_within_module>_<scenario>
Module id / topic:
    01  reasoning_effort     reasoning_effort + thinking-depth control

============================================================================
Case ↔ checkpoint mapping  (every case runs × non_stream, stream)
============================================================================
Requirement  | Case                                     | Checkpoints asserted
-------------+------------------------------------------+------------------------
1.1 enabled  | test_01_02_thinking_enabled_forced       | 200; reasoning_content
             |                                          | non-empty; reasoning_
             |                                          | tokens present and > 0
1.2 adaptive | test_01_05_thinking_adaptive_triggers    | 200 on a prompt that is
             | (hard prompt, must trigger)              | unsolvable without
             |                                          | multi-step reasoning →
             |                                          | thinking-on contract
             | test_01_07_thinking_adaptive_branch_     | per trial: EITHER
             | coverage (drives both branches, then     | thinking-on OR
             |  FAILS if either went unobserved)        | thinking-off, never a
             |                                          | mix; SKIPPED driver also
             |                                          | asserts its tool fires;
             |                                          | then both branches must
             |                                          | have been exercised
             | test_01_08_thinking_adaptive_suppressed_ | same per-trial check on
             | no_tools                                 | the tool-free path
1.3 disabled | test_01_06_effort_with_thinking_disabled  | 200; no reasoning_
             |                                          | content; reasoning_
             |                                          | tokens present and == 0
2.1 none     | test_01_03_none_rejected_or_thinking_off  | 400/422, OR 200 under
             |                                          | the exact thinking-off
             |                                          | contract of 1.3
2.2 enum     | test_01_01_valid_effort_accepted         | each of low/medium/high/
             | (low,medium,high,xhigh,max)              | xhigh/max → 200 +
             |                                          | thinking-on contract
             | test_01_10_effort_with_thinking_enabled  | effort + thinking.
             | (low,max)                                | enabled → 200 +
             |                                          | thinking-on contract
-------------+------------------------------------------+------------------------
Notes:
  - 01_02 (enabled) / 01_03 (none) / 01_06 (disabled) share one strong prompt
    (THINKING_TRIGGER_PROMPT) so they form an enabled-vs-off contrast on
    identical input. A trivial prompt would make the thinking-off branches
    vacuous.
  - 01_01 sends no `thinking` field, so it runs under the default (adaptive)
    mode and proves acceptance only; 01_10 removes that confound by forcing
    thinking on.
  - Under thinking.type=adaptive the decision belongs to the model, so no
    single request asserts a branch. 01_07 instead drives each branch with a
    dedicated payload and FAILS if either branch went unobserved, because a
    one-sided run is otherwise indistinguishable from a passing one.
  - NOT covered: that reasoning_effort actually *changes* thinking depth. A
    provider dropping the field and always using its default depth passes the
    whole suite. Proving effect needs a differential comparison of the
    provider's own reasoning_tokens between low and max, which is out of scope
    here, so requirement 2's "controls how deep the model thinks" is unverified.

Supplementary coverage (not a strict requirement):
  - test_01_04_out_of_enum_ignored : out-of-enum value → ignored/default or 4xx
  - test_01_09_effort_with_image : image input + effort

All cases go through helpers.oai_chat() against /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
import pytest

from helpers import *
from image_tools import make_png_base64


REASONING_EFFORT_ENUM = ("low", "medium", "high", "xhigh", "max")

# Shared prompt for the enabled/disabled contrast pair (01_02 vs 01_06) and the
# `none` case (01_03). It explicitly asks for step-by-step work, so whenever
# thinking is NOT suppressed a thinking signal is expected; conversely a
# response with no thinking on this prompt is strong evidence that thinking was
# genuinely turned off rather than simply never triggered.
THINKING_TRIGGER_PROMPT = "What is 23 * 47? Think it through."

# ---------------------------------------------------------------------------
# adaptive branch drivers
# ---------------------------------------------------------------------------
# thinking.type=adaptive has two legal outcomes and both must be exercised, so
# each one gets a payload shaped to land on it.
#
# What pushes the model off thinking is `tools` together with
# `reasoning_effort=low` — either on its own leaves thinking on. A Chinese
# system line asking for no reasoning stacks on top of that pair; the same
# instruction in English does not, so the effect is language-specific rather
# than the model obeying "do not think".
#
# The test_15_05_system_thinking_tools_combo shape (English system + "Think
# step by step" + tools, no effort) is not used as a driver: its outcome flips
# with the X-MM-Root-Role-Message header, which would tie branch coverage to
# run-level header configuration instead of to the case.

# THOUGHT driver: multi-step constraint puzzle, unsolvable without enumerating
# the three candidates (the unique answer is box C). It carries no "think step
# by step" instruction, so what is exercised is the model's own decision rather
# than its instruction-following, and it supplies neither tools nor
# effort=low so it stays clear of the suppressing pair.
ADAPTIVE_HARD_PROMPT = (
    "Three boxes are labelled A, B and C, and exactly one of them holds a "
    "prize. Box A's label reads 'the prize is not in this box'. Box B's label "
    "reads 'the prize is in box A'. Box C's label reads 'the prize is not in "
    "this box'. Exactly one of the three labels is truthful. Which box holds "
    "the prize?"
)

# SKIPPED driver: every suppressor stacked — zh system line + tools +
# reasoning_effort=low. The user turn stays English so `location` comes back as
# "Tokyo" and the tool argument stays assertable; a Chinese city name makes that
# check ambiguous.
ADAPTIVE_TOOL_SUPPRESSED_SYSTEM = "不要思考，直接调用工具"
ADAPTIVE_TOOL_SUPPRESSED_USER = "Tokyo weather"

# Tool-free variant. Without tools the suppressing pair is incomplete, so the
# outcome here is genuinely mixed and this payload cannot drive coverage — that
# job belongs to the two drivers above.
ADAPTIVE_SUPPRESSED_SYSTEM = "不要思考，不要解释，直接回答"
ADAPTIVE_SUPPRESSED_USER = "你好"

# Trials per driver. More than one so a driver that only sometimes lands on its
# branch still gets there, kept small because each trial is a live request.
ADAPTIVE_THINK_TRIALS = 2
ADAPTIVE_SKIP_TRIALS = 3


def _usage(r: dict) -> dict:
    """Raw usage object: non-stream reads body.usage, stream reads the last
    chunk carrying usage (`stream_options.include_usage` is injected for every
    streamed request by helpers.oai_chat)."""
    if r.get("stream"):
        for chunk in reversed(r.get("chunks") or []):
            if isinstance(chunk, dict) and chunk.get("usage"):
                return chunk["usage"]
        return {}
    return (r.get("body") or {}).get("usage") or {}


def _assert_reasoning_tokens(r: dict, expect_positive: bool, context: str = ""):
    """Assert the provider genuinely reports reasoning accounting.

    `usage.completion_tokens_details.reasoning_tokens` must be PRESENT and an
    int, then be > 0 (thinking on) or == 0 (thinking off).

    Field presence is asserted on purpose: the spec requires reasoning_tokens to
    be *set* to 0 when thinking is off, and a lenient `== 0` read would pass
    vacuously against a provider that cannot report the field at all. Requiring
    it in both directions is what proves the capability exists.

    Per project decision the magnitude is NOT sanity-checked against the
    reasoning text (no tokenizer is introduced): > 0 is sufficient.
    """
    usage = _usage(r)
    assert usage, f"{context}: response carries no usage object"
    assert "completion_tokens_details" in usage, (
        f"{context}: usage.completion_tokens_details is missing, so "
        f"reasoning_tokens cannot be reported at all. usage={usage}"
    )
    details = usage["completion_tokens_details"]
    assert isinstance(details, dict), (
        f"{context}: usage.completion_tokens_details must be an object, "
        f"got {type(details).__name__}: {details!r}"
    )
    assert "reasoning_tokens" in details, (
        f"{context}: usage.completion_tokens_details.reasoning_tokens is "
        f"missing; it must be reported explicitly. details={details}"
    )
    tokens = details["reasoning_tokens"]
    assert isinstance(tokens, int) and not isinstance(tokens, bool), (
        f"{context}: reasoning_tokens must be an integer, "
        f"got {type(tokens).__name__}: {tokens!r}"
    )
    if expect_positive:
        assert tokens > 0, f"{context}: expected reasoning_tokens > 0, got {tokens}"
    else:
        assert tokens == 0, f"{context}: expected reasoning_tokens == 0, got {tokens}"


def _assert_thinking_on(r: dict, context: str = ""):
    """Thinking is on: the reasoning must be returned in the dedicated
    `reasoning_content` field AND reasoning_tokens explicitly reported as > 0.

    Stricter than helpers.assert_thinking_present() on purpose. That helper also
    accepts an inline <think> tag in content as a thinking signal, which is too
    lenient here: requirement 1 states the model must respond with
    `reasoning_content`, and reasoning_split defaults to true for this model. A
    provider that inlines thinking into content would pass the shared helper
    while violating the requirement, so this suite rejects the inline form.
    """
    sig = get_thinking_signals(r)
    assert sig["reasoning_content"].strip(), (
        f"{context}: expected non-empty message.reasoning_content "
        f"(reasoning_split defaults to true), got empty "
        f"(inline <think> tag in content: {sig['has_think_tag']}). An inline "
        f"<think> tag does NOT satisfy the requirement."
    )
    _assert_reasoning_tokens(r, expect_positive=True, context=context)


def _assert_thinking_off(r: dict, context: str = ""):
    """Thinking is off: no thinking signal at all AND reasoning_tokens
    explicitly reported as 0."""
    assert_thinking_absent(r, msg=context)
    _assert_reasoning_tokens(r, expect_positive=False, context=context)


def _assert_thinking_self_consistent(r: dict, context: str = "") -> str:
    """thinking.type=adaptive: the model decides, so assert CONSISTENCY rather
    than presence or absence. Returns the branch taken ("THOUGHT"/"SKIPPED").

      - it thought      → thinking-on contract  (reasoning_content + tokens > 0)
      - it did not think → thinking-off contract (no signal + tokens == 0)

    Asserting presence would be wrong (adaptive may legitimately skip) and
    asserting absence would be wrong too (it may legitimately think). What must
    never happen is a mix: reasoning text billed as 0 tokens, or a leftover
    non-zero reasoning_tokens with no reasoning payload.

    The branch is returned so a caller can enforce that BOTH are exercised
    (test_01_07), and printed so a run records what the model actually chose.
    """
    branch = "THOUGHT" if get_thinking_signals(r)["any"] else "SKIPPED"
    print(f"[adaptive] {context} → {branch}")
    if branch == "THOUGHT":
        _assert_thinking_on(r, f"{context} → model chose to think")
    else:
        _assert_thinking_off(r, f"{context} → model chose not to think")
    return branch


def _assert_both_branches_covered(observed: dict, context: str):
    """Fail when either adaptive branch went unexercised.

    `observed` maps driver label → list of branches seen. A one-sided run leaves
    half the self-consistency contract unchecked, and a silently never-taken
    branch is indistinguishable from a passing one, so this is a hard failure
    rather than a warning.
    """
    seen = {b for branches in observed.values() for b in branches}
    breakdown = "\n".join(
        f"    {label:<28} {', '.join(branches)}" for label, branches in observed.items()
    )
    for branch in ("THOUGHT", "SKIPPED"):
        assert branch in seen, (
            f"{context}: adaptive branch {branch!r} was NEVER exercised, so its half of\n"
            f"  the self-consistency contract went unchecked.\n"
            f"  observed:\n{breakdown}\n"
            f"  Each driver is shaped to land on one branch, so a miss means the model's\n"
            f"  adaptive behaviour moved. Re-check the drivers in the constant block\n"
            f"  before relaxing this."
        )


def _assert_ok(r: dict, stream: bool):
    """HTTP 200 success assertion for a case parametrized over stream mode.

    Streaming additionally requires a cleanly terminated SSE sequence
    (assert_oai_stream_success already folds in assert_stream_complete, which is
    why this suite no longer needs a separate stream-protocol case).
    """
    if stream:
        assert_oai_stream_success(r)
    else:
        assert_oai_success(r)


# ============================================================
# 01 reasoning_effort — thinking-depth control
# ============================================================

STREAM_MODES = pytest.mark.parametrize(
    "stream", [False, True], ids=["non_stream", "stream"]
)


class TestReasoningEffort:
    """reasoning_effort + thinking.type: enum acceptance, forced thinking,
    adaptive behaviour, forced-off behaviour and out-of-enum fallback.

    Every case is parametrized over non-streaming and streaming: the two paths
    differ structurally (aggregated `message.reasoning_content` vs accumulated
    `delta.reasoning_content`, and usage carried in the terminal SSE chunk), so
    a contract verified on one says nothing about the other. Leaking reasoning
    deltas, or a stale non-zero reasoning_tokens in the final usage chunk, are
    streaming-only failure modes.
    """

    @pytest.mark.parametrize("effort", REASONING_EFFORT_ENUM)
    @STREAM_MODES
    def test_01_01_valid_effort_accepted(self, effort, stream):
        """Each valid enum value (low/medium/high/xhigh/max) is accepted → HTTP 200.

        Covers requirement 2.2. The prompt asks for step-by-step work, so a
        thinking signal is expected and must arrive as reasoning_content.

        Scope note: this case sends no `thinking` field, so it exercises the
        default thinking mode. It therefore proves acceptance only — it cannot
        prove the effort level took effect. The forced-on counterpart is
        test_01_10 (effort + thinking.enabled).
        """
        context = f"reasoning_effort={effort}, stream={stream}"
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "reasoning_effort": effort,
        }, stream=stream)

        _assert_ok(r, stream)
        _assert_thinking_on(r, context)

    @STREAM_MODES
    def test_01_02_thinking_enabled_forced(self, stream):
        """thinking.type=enabled: thinking is FORCED on, so the response must
        carry reasoning_content (reasoning_split defaults to true) and report
        reasoning_tokens > 0.

        Covers requirement 1.1. Shares THINKING_TRIGGER_PROMPT with 01_03/01_06
        so the enabled/off cases form a contrast on identical input.
        """
        context = f"thinking.type=enabled, stream={stream}"
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "thinking": {"type": "enabled"},
        }, stream=stream)

        _assert_ok(r, stream)
        _assert_thinking_on(r, context)

    @STREAM_MODES
    def test_01_03_none_rejected_or_thinking_off(self, stream):
        """reasoning_effort="none" is OUTSIDE the accepted enum
        (low/medium/high/xhigh/max) and must not be honoured as a normal effort
        level. Two outcomes pass:

          - HTTP 400/422: the value is rejected outright.
          - HTTP 200: acceptable only if `none` was honoured as "no thinking",
            i.e. the response satisfies exactly the same contract as
            thinking.type=disabled — no <think> tag, no reasoning_content, and
            reasoning_tokens explicitly reported as 0.

        A 200 that still returns thinking means `none` was silently swallowed
        and the caller got an unrequested effort level → fail. Anything outside
        {200, 400, 422} (e.g. 5xx) also fails.

        The prompt is the shared strong trigger: on a trivial prompt the 200
        branch would pass vacuously because the model would not have thought
        anyway. Covers requirement 2.1.
        """
        context = f'reasoning_effort="none", stream={stream}'
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "reasoning_effort": "none",
        }, stream=stream)

        if r["status"] in (400, 422):
            return

        _assert_ok(r, stream)
        _assert_thinking_off(r, f"{context} accepted with HTTP 200")

    @STREAM_MODES
    def test_01_04_out_of_enum_ignored(self, stream):
        """Out-of-enum value is ignored; the model falls back to default depth
        → HTTP 200 with thinking still present.

        Documented behaviour is a silent fallback (not a 400). Tolerate a strict
        deployment that rejects with 400/422 instead.
        """
        context = f"reasoning_effort=out-of-enum, stream={stream}"
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "reasoning_effort": "ultra_super_max_xyz",
        }, stream=stream)

        assert r["status"] in (200, 400, 422), (
            f"{context} HTTP={r['status']}: {str(r.get('body'))[:300]}"
        )
        if r["status"] == 200:
            _assert_ok(r, stream)
            _assert_thinking_on(r, f"{context} (default depth)")

    @STREAM_MODES
    def test_01_05_thinking_adaptive_triggers(self, stream):
        """thinking.type=adaptive on a problem that cannot be answered without
        multi-step reasoning → the model must choose to think, returning
        reasoning_content with reasoning_tokens > 0.

        Covers the "triggered" half of requirement 1.2. Prompt choice matters:
        a commonsense question, or any wording carrying a brevity suppressor
        such as "briefly", lets adaptive legitimately skip thinking and the case
        would then fail for the wrong reason. ADAPTIVE_HARD_PROMPT forces
        genuine case enumeration and gives no "think step by step" hint, so what
        is exercised is the model's own decision. The "skipped" half is
        test_01_07.
        """
        context = f"thinking.adaptive + effort=high (hard prompt), stream={stream}"
        r = oai_chat({
            "messages": oai_simple_messages(ADAPTIVE_HARD_PROMPT),
            "reasoning_effort": "high",
            "thinking": {"type": "adaptive"},
        }, stream=stream)

        _assert_ok(r, stream)
        _assert_thinking_on(r, context)

    @STREAM_MODES
    def test_01_06_effort_with_thinking_disabled(self, stream):
        """reasoning_effort=high + thinking.type=disabled → HTTP 200 with
        thinking genuinely off: no <think> tag, no reasoning_content, and
        reasoning_tokens explicitly reported as 0.

        A 200 that still returns thinking means `disabled` was silently
        swallowed, which fails. Covers requirement 1.3.

        The prompt is deliberately identical to test_01_02 (which forces
        thinking on with the same input): a trivial prompt such as "Hi" would
        not trigger thinking anyway, so a provider ignoring thinking.disabled
        would still pass and the case would assert nothing. Sharing one prompt
        across 01_02/01_06 turns the pair into an enabled-vs-disabled contrast
        on identical input, which is what proves reasoning_tokens tracks the
        thinking switch instead of being hardcoded.
        """
        context = f"reasoning_effort=high + thinking.disabled, stream={stream}"
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "reasoning_effort": "high",
            "thinking": {"type": "disabled"},
        }, stream=stream)

        _assert_ok(r, stream)
        # Accepted → thinking must be genuinely suppressed, and the provider
        # must still report reasoning_tokens (explicitly 0).
        _assert_thinking_off(r, context)

    @STREAM_MODES
    def test_01_07_thinking_adaptive_branch_coverage(self, stream):
        """thinking.type=adaptive: BOTH legal outcomes must be exercised and
        each must be internally consistent.

          - thought       -> reasoning_content non-empty AND reasoning_tokens > 0
          - did not think -> no thinking signal AND reasoning_tokens explicitly 0

        Per trial only consistency is asserted, never a branch: adaptive hands
        the decision to the model, so demanding "must think" or "must skip" on
        any single request would be a flaky false negative.

        What IS demanded is coverage. The case drives each branch with its own
        payload (see the constant block) and then fails if either branch went
        unobserved, since a one-sided run is otherwise indistinguishable from a
        passing one.

        The SKIPPED driver also asserts its tool call still fires, so the skip
        is observed on a real tool-call turn rather than on a degenerate reply.
        That path is additionally where `reasoning_content` vanishes as a KEY
        rather than arriving empty, so callers must null-check; this pins that
        the token accounting survives it.
        """
        observed = {}

        label = "hard_puzzle (THOUGHT driver)"
        observed[label] = []
        for trial in range(ADAPTIVE_THINK_TRIALS):
            context = f"{label} #{trial + 1}, stream={stream}"
            r = oai_chat({
                "messages": oai_simple_messages(ADAPTIVE_HARD_PROMPT),
                "thinking": {"type": "adaptive"},
            }, stream=stream)
            _assert_ok(r, stream)
            observed[label].append(_assert_thinking_self_consistent(r, context))

        label = "zh+tools+low (SKIPPED driver)"
        observed[label] = []
        for trial in range(ADAPTIVE_SKIP_TRIALS):
            context = f"{label} #{trial + 1}, stream={stream}"
            r = oai_chat({
                "messages": oai_simple_messages(
                    ADAPTIVE_TOOL_SUPPRESSED_USER,
                    system_text=ADAPTIVE_TOOL_SUPPRESSED_SYSTEM,
                ),
                "tools": [WEATHER_TOOL_OAI],
                "reasoning_effort": "low",
                "thinking": {"type": "adaptive"},
            }, stream=stream)
            _assert_ok(r, stream)
            assert_tool_called(
                r,
                expected_name="get_weather",
                expected_args_subset={"location": "Tokyo"},
                schema=WEATHER_TOOL_OAI["function"]["parameters"],
                msg=context,
            )
            observed[label].append(_assert_thinking_self_consistent(r, context))

        _assert_both_branches_covered(observed, f"adaptive branch coverage, stream={stream}")

    @STREAM_MODES
    def test_01_08_thinking_adaptive_suppressed_no_tools(self, stream):
        """thinking.type=adaptive on a suppressed plain-text turn (no tools):
        every outcome must be self-consistent.

        Branch coverage is owned by test_01_07. This case holds the tool-free
        shape, where the outcome is genuinely mixed, so requiring a specific
        branch here would be flaky. It asserts consistency on each trial and
        logs the branch taken.

        Worth keeping separate because attaching a tool changes how much the
        model reasons, and that path is covered by 01_07; this one pins the
        contract when no tool is in play.
        """
        observed = []
        for trial in range(ADAPTIVE_SKIP_TRIALS):
            context = f"adaptive suppressed, no tools #{trial + 1}, stream={stream}"
            r = oai_chat({
                "messages": oai_simple_messages(
                    ADAPTIVE_SUPPRESSED_USER, system_text=ADAPTIVE_SUPPRESSED_SYSTEM
                ),
                "reasoning_effort": "low",
                "thinking": {"type": "adaptive"},
            }, stream=stream)
            _assert_ok(r, stream)
            observed.append(_assert_thinking_self_consistent(r, context))
        print(f"[adaptive] no-tools branches, stream={stream}: {observed}")

    @pytest.mark.parametrize("effort", ["low", "max"])
    @STREAM_MODES
    def test_01_09_effort_with_image(self, effort, stream):
        """Image input accepts low/max effort with thinking and a final answer,
        in both non-streaming and complete streaming responses.
        """
        context = f"image + reasoning_effort={effort}, stream={stream}"
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": make_png_base64(672, 672, r=255, g=0, b=0),
                }},
                {"type": "text", "text": (
                    "Identify the dominant color in this image. Use 17 if it is "
                    "red, 23 if green, or 31 if blue, then multiply that number "
                    "by 19. Think it through and give the color and result."
                )},
            ]}],
            "reasoning_effort": effort,
        }, stream=stream)

        _assert_ok(r, stream)
        _assert_thinking_on(r, context)
        assert get_oai_content(r).strip(), f"{context}: expected non-empty final answer"

    @pytest.mark.parametrize("effort", ["low", "max"])
    @STREAM_MODES
    def test_01_10_effort_with_thinking_enabled(self, effort, stream):
        """reasoning_effort combined with thinking.type=enabled → HTTP 200 with
        thinking on.

        This is the confound-free acceptance check for reasoning_effort.
        test_01_01 sends no `thinking` field, so it runs under the default mode
        (adaptive for this model): "a thinking signal is present" there could be
        the model's own choice rather than anything to do with the effort level.
        Forcing thinking on makes reasoning_content/reasoning_tokens a
        consequence of the thinking switch, leaving exactly one thing for the
        effort value to prove — that it is neither rejected nor able to
        suppress thinking.

        Known limit: acceptance is NOT the same as effect. Nothing here (or
        anywhere else in the suite) distinguishes a provider that honours the
        effort level from one that drops the field and always uses its default
        depth. That would need a differential comparison of the provider's own
        reported reasoning_tokens between low and max; it is intentionally out
        of scope for now, so requirement 2's "controls how deep the model
        thinks" remains unverified.
        """
        context = f"reasoning_effort={effort} + thinking.enabled, stream={stream}"
        r = oai_chat({
            "messages": oai_simple_messages(THINKING_TRIGGER_PROMPT),
            "reasoning_effort": effort,
            "thinking": {"type": "enabled"},
        }, stream=stream)

        _assert_ok(r, stream)
        _assert_thinking_on(r, context)
