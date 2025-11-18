from validator import BaseValidator


def not_contains_repeat_n_gram(text: str, n: int, repeat_count: int = 4) -> bool:
    for i in range(len(text) - n + 1):
        ngram = text[i:i+n]
        if text.count(ngram) >= repeat_count:
            return False
    return True

class RepeatNGramValidator(BaseValidator):
    def __init__(self, n: int = 3, repeat_count: int = 4):
        self.n = n
        self.repeat_count = repeat_count

    @property
    def name(self) -> str:
        return "repeat_n_gram"

    def validate(self, request: dict, response: dict, status: str, resp_content: str = None) -> dict:
        result = {
            "error_repeating_checked": False,
            "error_repeating_valid": None,
            "error_repeating_config": {
                "n": self.n,
                "repeat_count": self.repeat_count,
            }
        }

        if status != "success" or not resp_content:
            return result

        result["error_repeating_checked"] = True
        result["error_repeating_valid"] = not_contains_repeat_n_gram(
            resp_content, 
            self.n, 
            self.repeat_count
        )

        return result

    def compute_summary(self, results: list[dict]) -> dict:
        summary = {
            "error_repeating_checked_count": 0,
            "error_repeating_valid_count": 0,
            "error_repeating_invalid_count": 0,
            "error_repeating_config": {
                "n": self.n,
                "repeat_count": self.repeat_count,
            }
        }

        for r in results:
            if r.get("error_repeating_checked"):
                summary["error_repeating_checked_count"] += 1
                if r.get("error_repeating_valid"):
                    summary["error_repeating_valid_count"] += 1
                else:
                    summary["error_repeating_invalid_count"] += 1

        return summary

