"""Runtime configuration — loaded from environment / a local .env (never committed).

Zero third-party deps: a tiny .env parser + a dataclass. Defaults encode the
decisions from 03-Build-Plan.md as corrected by the Day-0 verification (region
East US 2 — the only region with Fabric ontology+DTB, agentic retrieval, gpt-5.5,
and native Voice Live; Voice Live api-version 2026-04-10; agentic-retrieval REST
2026-04-01; reasoning model gpt-5.5). Azure values are blank until provisioned —
the offline core never reads them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # strip an inline comment on unquoted values (a '#' preceded by whitespace)
            if val[:1] not in ("'", '"'):
                for i, ch in enumerate(val):
                    if ch == "#" and i > 0 and val[i - 1] in " \t":
                        val = val[:i].rstrip()
                        break
            val = val.strip('"').strip("'")
            os.environ.setdefault(key, val)


@dataclass
class Settings:
    # region / pins (decisions baked into the plan, corrected by Day-0 verification)
    region: str = "eastus2"
    model_deployment: str = "reasoning"             # deployment name; underlying model gpt-5.5 (2026-04-24)
    azure_ai_projects_min_version: str = "2.2.0"
    search_api_version: str = "2026-04-01"          # GA agentic retrieval
    voice_live_api_version: str = "2026-04-10"       # GA Voice Live (agent mode)

    # Foundry / Azure (blank until Day-0 provisioning)
    foundry_project_endpoint: str = ""
    search_endpoint: str = ""
    search_index: str = "pathforward-iq"
    rai_policy: str = ""                              # enforced Responsible AI policy name (blank = none)
    eval_judge_api_version: str = "2025-01-01-preview"  # AOAI api-version for the groundedness judge
    fabric_workspace_id: str = ""
    fabric_artifact_id: str = ""
    voice_resource_endpoint: str = ""
    mcp_mint_url: str = ""

    @property
    def azure_ready(self) -> bool:
        return bool(self.foundry_project_endpoint and self.search_endpoint)


def load_settings(dotenv_path: str = ".env") -> Settings:
    _load_dotenv(dotenv_path)
    g = os.environ.get
    return Settings(
        region=g("PATHFORWARD_REGION", "eastus2"),
        model_deployment=g("AZURE_AI_MODEL_DEPLOYMENT", "reasoning"),
        foundry_project_endpoint=g("AZURE_AI_PROJECT_ENDPOINT", ""),
        search_endpoint=g("AZURE_SEARCH_ENDPOINT", ""),
        search_index=g("AZURE_SEARCH_INDEX", "pathforward-iq"),
        rai_policy=g("AZURE_RAI_POLICY", ""),
        eval_judge_api_version=g("EVAL_JUDGE_API_VERSION", "2025-01-01-preview"),
        fabric_workspace_id=g("FABRIC_WORKSPACE_ID", ""),
        fabric_artifact_id=g("FABRIC_ARTIFACT_ID", ""),
        voice_resource_endpoint=g("VOICE_LIVE_ENDPOINT", ""),
        mcp_mint_url=g("MCP_MINT_URL", ""),
    )
