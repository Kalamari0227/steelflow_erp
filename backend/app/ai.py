import os
from typing import Protocol

from .schemas import AIStatus, Risk


class AdviceProvider(Protocol):
    def explain(self, risks: list[Risk]) -> str: ...


class OptionalAIAdapter:
    def __init__(self, provider: AdviceProvider | None = None) -> None:
        self.enabled = os.environ.get("STEELFLOW_AI_ENABLED", "false").lower() == "true"
        self.provider = provider

    def status(self) -> AIStatus:
        return AIStatus(enabled=self.enabled, available=self.enabled and self.provider is not None, provider="none" if self.provider is None else "optional")

    def explain(self, risks: list[Risk]) -> str:
        fallback = " ".join(risk.recommendation for risk in risks) or "All orders follow their planned windows."
        if not self.enabled or self.provider is None:
            return fallback
        try:
            return self.provider.explain(risks)
        except (ConnectionError, TimeoutError, OSError):
            return fallback
