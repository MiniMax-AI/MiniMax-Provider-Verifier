"""JSON Schema declaration-form coverage for m3 format checks."""

from helpers import *


class TestSchemaDeclarationForms:
    def test_14_21_type_array_declaration_accepted(self):
        """The standard JSON Schema type-array form is accepted."""
        tool = tool_fn(
            "accept_type_array",
            description="Accept a value using a JSON Schema type array.",
            parameters={
                "type": "object",
                "properties": {
                    "value": {
                        "type": ["string", "number", "boolean", "object", "array"],
                    },
                },
                "required": ["value"],
                "additionalProperties": False,
            },
        )
        r = oai_chat({
            "messages": oai_simple_messages("Call accept_type_array with value hello."),
            "tools": [tool],
            "tool_choice": {
                "type": "function",
                "function": {"name": "accept_type_array"},
            },
        })
        assert_oai_success(r)
        calls = get_tool_calls(r)
        assert calls, "14_21 expected a tool call"
        assert calls[0]["name"] == "accept_type_array"
        assert calls[0]["arguments_obj"] is not None

    def test_14_22_anyof_declaration_accepted(self):
        """The standard JSON Schema anyOf form is accepted."""
        tool = tool_fn(
            "accept_anyof",
            description="Accept a value using JSON Schema anyOf.",
            parameters={
                "type": "object",
                "properties": {
                    "value": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "number"},
                            {"type": "boolean"},
                            {"type": "object"},
                            {"type": "array"},
                        ],
                    },
                },
                "required": ["value"],
                "additionalProperties": False,
            },
        )
        r = oai_chat({
            "messages": oai_simple_messages("Call accept_anyof with value hello."),
            "tools": [tool],
            "tool_choice": {
                "type": "function",
                "function": {"name": "accept_anyof"},
            },
        })
        assert_oai_success(r)
        calls = get_tool_calls(r)
        assert calls, "14_22 expected a tool call"
        assert calls[0]["name"] == "accept_anyof"
        assert calls[0]["arguments_obj"] is not None

    def test_14_23_string_union_type_rejected(self):
        """A pipe-delimited type string is invalid JSON Schema and is rejected."""
        tool = tool_fn(
            "reject_string_union",
            description="This declaration intentionally uses invalid JSON Schema.",
            parameters={
                "type": "object",
                "properties": {
                    "value": {
                        "type": "string | number | boolean | object | array",
                    },
                },
                "required": ["value"],
                "additionalProperties": False,
            },
        )
        r = oai_chat({
            "messages": oai_simple_messages("Call reject_string_union."),
            "tools": [tool],
            "tool_choice": {
                "type": "function",
                "function": {"name": "reject_string_union"},
            },
        })
        assert r["status"] in (400, 422), (
            f"14_23 invalid string union should be rejected, got "
            f"HTTP={r['status']}: {str(r.get('body'))[:300]}"
        )
