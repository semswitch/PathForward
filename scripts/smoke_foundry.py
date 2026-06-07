"""Day-0 smoke test: prove the keyless GA Responses path to the reasoning model.

Reads .env (service-principal creds + project endpoint via pathforward.config),
authenticates with DefaultAzureCredential (no API keys), calls the GA Responses
API on the 'reasoning' deployment (gpt-5.5), and prints the model's reply.

    python scripts/smoke_foundry.py

Exit 0 = the Foundry project + deployment + keyless RBAC are wired end-to-end.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.config import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings(os.path.join(_ROOT, ".env"))
    if not settings.foundry_project_endpoint:
        print("FAIL: AZURE_AI_PROJECT_ENDPOINT is not set in .env")
        return 1

    # load_settings() has loaded AZURE_CLIENT_ID/TENANT_ID/CLIENT_SECRET into the
    # environment, so DefaultAzureCredential -> EnvironmentCredential picks up the SP.
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    print(f"endpoint   : {settings.foundry_project_endpoint}")
    print(f"deployment : {settings.model_deployment}")

    cred = DefaultAzureCredential()
    with AIProjectClient(endpoint=settings.foundry_project_endpoint, credential=cred) as project:
        client = project.get_openai_client()
        resp = client.responses.create(
            model=settings.model_deployment,
            input="Reply with exactly this sentence and nothing else: PathForward Foundry online.",
        )

    text = getattr(resp, "output_text", None)
    if not text:
        # Fallback: stitch text out of the structured output items.
        parts = []
        for item in getattr(resp, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                t = getattr(content, "text", None)
                if t:
                    parts.append(t)
        text = "".join(parts)

    print(f"reply      : {text!r}")
    print("OK: keyless gpt-5.5 Responses call succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
