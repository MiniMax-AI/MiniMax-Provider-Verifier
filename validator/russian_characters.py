from validator import BaseValidator

def not_contains_russian_characters_unicode(text: str) -> bool:
    CYRILLIC_RANGE_START = 0x0400
    CYRILLIC_RANGE_END = 0x04FF

    for char in text:
        char_code = ord(char)

        if CYRILLIC_RANGE_START <= char_code <= CYRILLIC_RANGE_END:
            return False

    return True

class RussianCharactersValidator(BaseValidator):
    @property
    def name(self) -> str:
        return "contains_russian_characters_unicode"

    def validate(self, request: dict, response: dict, status: str, resp_content: str = None) -> dict:
        result = {
            "language_following_checked": False,
            "language_following_valid": None,
        }

        if status != "success" or not resp_content:
            return result

        result["language_following_checked"] = True
        result["language_following_valid"] = not_contains_russian_characters_unicode(resp_content)

        return result

    def compute_summary(self, results: list[dict]) -> dict:
        summary = {
            "language_following_checked_count": 0,
            "language_following_valid_count": 0,
            "language_following_invalid_count": 0,
        }

        for r in results:
            if r.get("language_following_checked"):
                summary["language_following_checked_count"] += 1
                if r.get("language_following_valid"):
                    summary["language_following_valid_count"] += 1
                else:
                    summary["language_following_invalid_count"] += 1

        return summary

