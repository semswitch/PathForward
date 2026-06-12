"""Runtime configuration — loaded from environment / a local .env (never committed).

Zero third-party deps: a tiny .env parser + a dataclass. Defaults encode the
decisions from 03-Build-Plan.md as corrected by the Day-0 verification (region
East US 2 — our chosen region co-locating Fabric ontology+DTB, agentic retrieval,
gpt-5.5, and native Voice Live; not the only such region — Sweden Central also
qualifies; Voice Live api-version 2026-04-10; agentic-retrieval REST
2026-04-01; reasoning model gpt-5.5). Azure values are blank until provisioned —
the offline core never reads them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    stripped = value.strip()
    if stripped.startswith("${") and stripped.endswith("}"):
        return default
    if stripped.startswith("{{") and stripped.endswith("}}"):
        return default
    return value


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
    azure_monitor_connection_string: str = ""         # App Insights conn string for OTel trace export
    fabric_workspace_id: str = ""
    fabric_artifact_id: str = ""
    fabric_connection_name: str = ""                  # Foundry 'Microsoft Fabric' connection name (the data agent)
    fabric_data_agent_openai_base: str = ""           # Published Fabric data-agent OpenAI-compatible API base
    fabric_mcp_url: str = ""                          # Azure Function MCP bridge to published Fabric data agent
    voice_resource_endpoint: str = ""
    mcp_mint_url: str = ""
    mcp_gate_url: str = ""

    @property
    def azure_ready(self) -> bool:
        return bool(self.foundry_project_endpoint and self.search_endpoint)


def load_settings(dotenv_path: str = ".env") -> Settings:
    _load_dotenv(dotenv_path)
    return Settings(
        region=_env_value("PATHFORWARD_REGION", "eastus2"),
        model_deployment=_env_value(
            "AZURE_AI_MODEL_DEPLOYMENT",
            _env_value("AZURE_AI_MODEL_DEPLOYMENT_NAME", "reasoning"),
        ),
        foundry_project_endpoint=_env_value(
            "AZURE_AI_PROJECT_ENDPOINT",
            _env_value("FOUNDRY_PROJECT_ENDPOINT", ""),
        ),
        search_endpoint=_env_value("AZURE_SEARCH_ENDPOINT", ""),
        search_index=_env_value("AZURE_SEARCH_INDEX", "pathforward-iq"),
        rai_policy=_env_value("AZURE_RAI_POLICY", ""),
        eval_judge_api_version=_env_value("EVAL_JUDGE_API_VERSION", "2025-01-01-preview"),
        azure_monitor_connection_string=_env_value("AZURE_MONITOR_CONNECTION_STRING", ""),
        fabric_workspace_id=_env_value("FABRIC_WORKSPACE_ID", ""),
        fabric_artifact_id=_env_value("FABRIC_ARTIFACT_ID", ""),
        fabric_connection_name=_env_value("FABRIC_CONNECTION_NAME", ""),
        fabric_data_agent_openai_base=_env_value("FABRIC_DATA_AGENT_OPENAI_BASE", ""),
        fabric_mcp_url=_env_value("FABRIC_MCP_URL", ""),
        voice_resource_endpoint=_env_value("VOICE_LIVE_ENDPOINT", ""),
        mcp_mint_url=_env_value("MCP_MINT_URL", ""),
        mcp_gate_url=_env_value("MCP_GATE_URL", ""),
    )
