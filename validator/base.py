from abc import abstractmethod, ABC


class BaseValidator(ABC):
    """Base class for all validators."""

    @abstractmethod
    def validate(self, request: dict, response: dict, status: str, resp_content: str = None) -> dict:
        """
        Validate a single request-response pair.

        Args:
            request: The prepared request dict
            response: The response dict from API
            status: The request status ('success' or 'failed')
            resp_content: The response content string (optional)

        Returns:
            A dict containing validation results for this validator.
            Keys should be prefixed with the validator name to avoid conflicts.
        """
        pass

    @abstractmethod
    def compute_summary(self, results: list[dict]) -> dict:
        """
        Compute summary statistics from all results.

        Args:
            results: List of all result dicts (including this validator's fields)

        Returns:
            A dict containing summary statistics for this validator.
            Keys should be prefixed with the validator name to avoid conflicts.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this validator."""
        pass