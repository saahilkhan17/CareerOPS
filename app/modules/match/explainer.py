"""Optional LLM explanation seam.

The numeric score NEVER depends on this module. An explanation is produced
only when `match_llm_enabled` is true AND an Explainer is registered via
set_explainer() (tests register fakes; production wires a real provider).
"""

from typing import Any, Protocol


class Explainer(Protocol):
    """Turn a score breakdown into resume-improvement prose."""

    def explain(
        self,
        *,
        title: str | None,
        score: int,
        breakdown: dict[str, object],
        missing_skills: list[str],
    ) -> str:
        """Return human-readable suggestions. Must not affect the score."""
        ...


class LLMExplainer:
    """Provider-backed explainer. Needs a client with .complete(prompt)->str."""

    def __init__(self, client: Any = None) -> None:
        self._client = client

    def explain(
        self,
        *,
        title: str | None,
        score: int,
        breakdown: dict[str, object],
        missing_skills: list[str],
    ) -> str:
        if self._client is None:
            raise RuntimeError("LLM provider not configured")
        prompt = (
            f"Job title: {title or 'unknown'}. Match score: {score}/100. "
            f"Breakdown: {breakdown}. Missing skills: {missing_skills}. "
            "Give concise resume-improvement suggestions."
        )
        complete = self._client.complete
        result = complete(prompt)
        return str(result)


_explainer: Explainer | None = None


def set_explainer(explainer: Explainer | None) -> None:
    """Register (or clear) the process-wide explainer. Test seam."""
    global _explainer
    _explainer = explainer


def get_explainer() -> Explainer | None:
    """Return the registered explainer, if any."""
    return _explainer
