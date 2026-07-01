from validator import BaseValidator


class SilenceOutputValidator(BaseValidator):
    """Validate the model echoes `[SILENCE]` verbatim with nothing after it."""

    @property
    def name(self) -> str:
        return "silence_output"

    def validate(self, request: dict, response: dict, status: str, resp_content: str = None) -> dict:
        result = {
            "silence_output_checked": False,
            "silence_output_valid": None,
        }

        if status != "success" or resp_content is None:
            return result

        result["silence_output_checked"] = True
        result["silence_output_valid"] = (
            "]" in resp_content and resp_content.endswith("]")
        )
        return result

    def compute_summary(self, results: list[dict]) -> dict:
        summary = {
            "silence_output_checked_count": 0,
            "silence_output_valid_count": 0,
            "silence_output_invalid_count": 0,
        }

        for r in results:
            if r.get("silence_output_checked"):
                summary["silence_output_checked_count"] += 1
                if r.get("silence_output_valid"):
                    summary["silence_output_valid_count"] += 1
                else:
                    summary["silence_output_invalid_count"] += 1

        return summary
