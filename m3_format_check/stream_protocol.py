"""Validate raw OpenAI tool call deltas without network, environment or argument merging dependencies."""

from typing import Any, Iterable


class StreamToolCallTracker:
    """New call indices start at zero and increase sequentially; IDs are unique and stable.

    Only the first appearance of each new index is ordered; existing calls may interleave.
    Later fragments may omit the ID or repeat the same complete ID.
    """

    def __init__(self, response_id: str | None = None):
        self.response_id = response_id
        self.errors: list[dict[str, Any]] = []
        self._calls: dict[int, dict[int, dict[str, Any]]] = {}
        self._id_owners: dict[str, tuple[int, int]] = {}

    def _error(self, code: str, position: dict, **details: Any) -> None:
        self.errors.append({
            "code": code, "response_id": self.response_id, **position, **details,
        })

    def observe(
        self, delta: dict, *, choice_index: int = 0,
        chunk_index: int = 0, delta_index: int = 0,
    ) -> None:
        """Record a tool_calls delta and its exact position before merging."""
        index = delta.get("index")
        position = {
            "choice_index": choice_index, "tool_call_index": index,
            "chunk_index": chunk_index, "delta_index": delta_index,
        }
        if type(index) is not int or index < 0:
            self._error("tool_call_index_invalid", position)
            return

        calls = self._calls.setdefault(choice_index, {})
        if index not in calls:
            expected = len(calls)
            if index != expected:
                self._error("tool_call_index_sequence", position, expected_index=expected)
            calls[index] = {"id": None, "first_position": position, "id_history": []}
        call = calls[index]

        new_id = delta.get("id")
        if new_id is None or new_id == "":
            return
        if not isinstance(new_id, str):
            self._error("tool_call_id_invalid", position, actual_id=new_id)
            return

        call["id_history"].append({"id": new_id, **position})
        if call["id"] is None:
            call["id"] = new_id
        elif new_id != call["id"]:
            self._error(
                "tool_call_id_changed", position, old_id=call["id"], new_id=new_id,
                first_id_position=call["id_history"][0],
            )

        owner = self._id_owners.get(new_id)
        if owner is not None and owner != (choice_index, index):
            self._error("tool_call_id_reused", position, id=new_id,
                        other_choice_index=owner[0], other_tool_call_index=owner[1])
        else:
            self._id_owners[new_id] = (choice_index, index)

    def finish(self) -> None:
        """Check calls that never received an ID after the stream ends; safe to call repeatedly."""
        missing = {
            (e["choice_index"], e["tool_call_index"])
            for e in self.errors if e["code"] == "tool_call_id_missing"
        }
        for choice_index, calls in self._calls.items():
            for index, call in calls.items():
                if call["id"] is None and (choice_index, index) not in missing:
                    self._error("tool_call_id_missing", call["first_position"])

    @property
    def id_history(self) -> list[dict[str, Any]]:
        return [
            {"choice_index": choice_index, "tool_call_index": index,
             "first_id": call["id"], "observations": call["id_history"]}
            for choice_index, calls in self._calls.items()
            for index, call in calls.items()
        ]


def inspect_stream_tool_calls(
    chunks: Iterable[dict], response_id: str | None = None,
) -> StreamToolCallTracker:
    """Inspect raw chunks for format cases, preserving ID history and protocol errors."""
    tracker = StreamToolCallTracker(response_id)
    for chunk_index, chunk in enumerate(chunks):
        if tracker.response_id is None and chunk.get("id"):
            tracker.response_id = chunk["id"]
        for choice_position, choice in enumerate(chunk.get("choices") or []):
            choice_index = choice.get("index", choice_position)
            for delta_index, delta in enumerate((choice.get("delta") or {}).get("tool_calls") or []):
                tracker.observe(delta, choice_index=choice_index,
                                chunk_index=chunk_index, delta_index=delta_index)
    tracker.finish()
    return tracker
