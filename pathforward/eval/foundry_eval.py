"""Optional 'second opinion' on groundedness via the Microsoft Foundry eval SDK.

The deterministic harness (cited ⊆ corpus∩retrieved) is the authoritative gate; this adds the
official azure-ai-evaluation GroundednessEvaluator as a corroborating signal for judge appeal.
It is best-effort and GRACEFULLY DEGRADING: any config/auth/model error yields `available=False`
with a one-line reason, and the deterministic scorecard stands on its own.
"""
from __future__ import annotations

from typing import Optional


def _aoai_base(project_endpoint: str) -> str:
    """Derive the resource base (scheme://host) from the Foundry project endpoint."""
    from urllib.parse import urlsplit
    u = urlsplit(project_endpoint)
    return f"{u.scheme}://{u.netloc}" if u.scheme and u.netloc else project_endpoint


class FoundryGroundedness:
    """Lazily builds the GroundednessEvaluator; never raises into the caller."""

    def __init__(self, project_endpoint: str, deployment: str, api_version: str):
        self.available = False
        self.reason = ""
        self._evaluator = None
        try:
            from azure.ai.evaluation import (AzureOpenAIModelConfiguration,
                                             GroundednessEvaluator)
            from azure.identity import DefaultAzureCredential
            cfg: AzureOpenAIModelConfiguration = {
                "azure_endpoint": _aoai_base(project_endpoint),
                "azure_deployment": deployment,
                "api_version": api_version,
            }
            # gpt-5.5 is a reasoning model -> use max_completion_tokens + drop unsupported params
            self._evaluator = GroundednessEvaluator(
                model_config=cfg, credential=DefaultAzureCredential(),
                is_reasoning_model=True)
            self.available = True
        except Exception as exc:  # noqa: BLE001
            self.reason = f"{type(exc).__name__}: {exc}"

    def score(self, context: str, response: str, query: str = "") -> Optional[float]:
        """Return the 1-5 groundedness score, or None if unavailable/errored."""
        if not self._evaluator:
            return None
        try:
            res = self._evaluator(
                query=query or "Is this competency item grounded in the evidence?",
                context=context, response=response)
            for k in ("groundedness", "gpt_groundedness"):
                if isinstance(res, dict) and res.get(k) is not None:
                    return float(res[k])
            return None
        except Exception as exc:  # noqa: BLE001
            if not self.reason:
                self.reason = f"score: {type(exc).__name__}: {exc}"
            return None
