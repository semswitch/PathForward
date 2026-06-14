# PathForward Deploy Runbook

One canonical method per surface. No manual file copying, no ad-hoc workarounds. Every step is a
committed script run from the repo root with the project `.venv`.

There are two deploy planes:
- **Azure Function App** (MCP mint / gate / fabric / route) — deployed with `func`.
- **Azure AI Foundry** (Skills, A2A, versioned agents, connections, evals) — provisioned
  with Python SDK / `azd ai` scripts.

> `azd` is intentionally partial: `azure.yaml` only declares the `pathforward-orchestrator` agent
> service for eval resolution. It is **not** the Function App or infra deployer. Do not treat it as
> the deployment source of truth.

---

## 0. Prerequisites (once per machine)

- Tools on PATH: `az`, `func` (Azure Functions Core Tools v4), `azd`, and the project `.venv`.
- Signed in as the **service principal**, pointed at the project subscription:
  ```powershell
  az account show --query "{user:user.name, type:user.type, sub:id}" -o json
  # expect type=servicePrincipal, sub=<your-subscription-id>
  ```
  (`DefaultAzureCredential` picks up the SP from `.env` `AZURE_CLIENT_ID/SECRET/TENANT`.)
- Local `.env` present (gitignored) with at least: `AZURE_AI_PROJECT_ENDPOINT`, the SP creds,
  `MCP_MINT_URL` (`.../api/mcp`), `MCP_MINT_FUNCTION_KEY`, `AZURE_SEARCH_ENDPOINT/INDEX`,
  `AZURE_MONITOR_CONNECTION_STRING`. Gate/fabric/route MCP URLs are **derived** from `MCP_MINT_URL`.
- Function App settings (in Azure, not `.env`) are documented in `functions/mint_mcp/README.md`.

Prove the code before any deploy:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

---

## 1. Surfaces & the one command each

| Surface | Canonical command |
|---|---|
| **Function App** (mint/gate/fabric/route MCP) | `./scripts/deploy_function_app.ps1 -Smoke` |
| **Foundry MCP connections** (gate / mint / route) | `…python scripts/provision_mcp_gate_toolbox.py` · `…provision_mcp_mint_toolbox.py` · `…provision_mcp_route_connection.py` |
| **Foundry Skills** (portal registry) | `…python scripts/register_skills.py` (`--dry-run` to validate offline) |
| **Specialist A2A** (enable + connections) | `…python scripts/provision_specialist_a2a.py` |
| **Versioned agents** (orchestrator + specialists) | `…python scripts/provision_foundry_specialist_agents.py [--roles orchestrator …]` |
| **Evals** | `…python scripts/run_prompt_orchestrator_eval.py --config eval\<suite>.yaml` |

`…` = `.\.venv\Scripts\python.exe`.

### How the Function App deploy works (why it's not hacky)
`functions/mint_mcp/function_app.py` imports the repo-root `pathforward` package, which is neither
pip-installed nor stored under the function folder. `deploy_function_app.ps1` assembles a clean,
self-contained package in a **gitignored** staging dir (`functions/mint_mcp/.deploy/`) = the function
files + the `pathforward` package, then `func azure functionapp publish … --python --build remote`
from that dir, then deletes the staging dir. The new code adds **no** dependencies, so `requirements.txt` is
unchanged. Use `-StageOnly` to inspect the package without publishing.

### Foundry agent tools are directly attached; Skills are injected from local files
The orchestrator agent's runtime tools (route + 5 A2A + gate + mint) are attached **directly** to the
agent definition by `_orchestrator_tools` in `provision_foundry_specialist_agents.py`. Each agent's
Skill is read from its repo-local `skills/<name>/SKILL.md` and **baked** into the agent instructions
at version-create time. PathForward does **not** use Foundry toolboxes: `register_skills.py` only
registers the Skills for portal visibility (architecture contract #4), and the orchestrator's A2A
links reference the `pathforward-a2a-<role>` connections created by `provision_specialist_a2a.py`.
There is no toolbox tool-list to reset, so no restore step is needed after a Skill change.

---

## 2. Full cold redeploy (clean order)

```powershell
# 1. Function App (creates /api/mcp, /api/gate-mcp, /api/fabric-mcp, /api/route-mcp)
./scripts/deploy_function_app.ps1 -Smoke

# 2. MCP RemoteTool connections (route uses the same function key as gate/mint)
.\.venv\Scripts\python.exe scripts\provision_mcp_gate_toolbox.py
.\.venv\Scripts\python.exe scripts\provision_mcp_mint_toolbox.py
.\.venv\Scripts\python.exe scripts\provision_mcp_route_connection.py

# 3. Foundry Skills (portal registry; baked into agents from local files at provision time)
.\.venv\Scripts\python.exe scripts\register_skills.py

# 4. Specialist A2A endpoints + RemoteA2A connections
.\.venv\Scripts\python.exe scripts\provision_specialist_a2a.py

# 5. Versioned agents (orchestrator + 5 specialists), with directly-attached tools
.\.venv\Scripts\python.exe scripts\provision_foundry_specialist_agents.py

# 6. Verify (see section 4)
```

---

## 3. Common incremental flows

**Function code change** (e.g., a new MCP route or server fix):
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .   # prove offline
./scripts/deploy_function_app.ps1 -Smoke
```

**Orchestrator instruction or `/pathforward` Skill change** (re-bake skill → new agent version):
```powershell
.\.venv\Scripts\python.exe scripts\register_skills.py              # portal visibility for updated SKILL.md
.\.venv\Scripts\python.exe scripts\provision_foundry_specialist_agents.py --roles orchestrator
```
The provisioner reads the Skill from the local `skills/<name>/SKILL.md`, so the new agent version is
re-baked directly from the edited file. Tools are attached directly and the A2A/MCP connections
persist across provisions — no toolbox restore step is needed.

**New specialist version only** (e.g., generator prompt change): edit the spec, then
`…provision_foundry_specialist_agents.py --roles generator`.

---

## 4. Verify (proof, not assumption)

```powershell
# Function endpoints (read-only): initialize on all 4 routes + resolve_route_facts
.\.venv\Scripts\python.exe scripts\smoke_mcp_endpoints.py            # expect SMOKE_PASS

# Live agentic route end-to-end (minimal prompt → autonomous route → approval → mint)
.\.venv\Scripts\python.exe scripts\smoke_integrated_orchestrator_live.py --approve --attempt 1
# expect BASELINE_PASS; proof under .agents/evidence/integrated-live-baseline-*.json

# Foundry dashboard eval against the live agent
.\.venv\Scripts\python.exe scripts\run_prompt_orchestrator_eval.py --config eval\prompt_orchestrator_smoke.yaml
```

Confirm the live agent's tool surface (versions, attached tools) at any time with the read-only
introspection in `.agents/temp/introspect_foundry.py`.

---

## 5. Rollback

Foundry agent versions are immutable and additive — a bad provision creates a new version; the prior
version is intact. Roll back by promoting the previous version as default (Foundry portal → Agents →
`pathforward-orchestrator` → set default version), or re-run the provisioner from the prior commit.
The Function App `deploy_function_app.ps1` is a full replace; to roll back, deploy from the prior
commit. Always keep the last-known-good commit hash noted before a deploy.
