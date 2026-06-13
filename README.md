# PathForward

**A Microsoft Foundry multi-agent reasoning system for workforce reskilling.**

PathForward helps workers in roles at risk of automation find credible paths into adjacent,
in-demand technical roles. It reasons over a skill ontology, builds a practical learning plan, and
runs a grounded competency-verification loop that issues a portable credential only when the evidence
supports it.

The core product promise is simple:

> PathForward would rather say **not yet** than issue a credential it cannot prove.

## Competition Focus

**Microsoft Agents League @ AISF 2026**  
**Track:** Reasoning Agents

PathForward is built around a real agentic workflow:

- A Foundry Prompt Agent, `pathforward-orchestrator`, acts as the top-level Orchestrator.
- Its Foundry Toolbox exposes `/pathforward`, Tool Search, and A2A calls to specialist prompt
  agents.
- Specialist reasoning agents handle skill-gap selection, assessment generation, critique, planning,
  and program insights.
- Foundry Skills define the agent behavior and are baked into versioned specialist agents through
  scoped Foundry Toolboxes/provisioning surfaces.
- Azure AI Search grounds assessment generation in cited evidence.
- Microsoft Fabric provides live cohort/program insights over the reskilling ontology.
- A deterministic Evidence Gate and governed mint boundary prevent unsafe credential issuance.

## What It Demonstrates

- **Multi-agent reasoning:** agents plan, critique, adapt, and explain the reskilling path.
- **Grounded verification:** assessment items must cite retrieved evidence before they can pass.
- **Honest refusal:** failed or ungrounded attempts end in ABSTAIN, not a fake pass.
- **Governed credentialing:** minting re-checks the causal spine and fails closed when proof is missing.
- **Microsoft-native architecture:** Foundry Prompt Agent, Foundry Skills, Azure AI Search,
  Fabric data agent, Azure Monitor telemetry, and Foundry evals.

## Runtime Boundary

The product orchestration surface is Foundry, not a Python control loop:

```text
pathforward-orchestrator Prompt Agent
  /pathforward Skill (baked into the agent instructions)
  directly-attached A2A links + route/gate/mint MCP tools
  versioned specialist Prompt Agents
```

Python remains in the repo for deterministic executors, provisioning, tests, eval utilities, and
small service/tool glue such as the MCP mint boundary. It is not the product Orchestrator brain.

## Pending Product Requirements

- **Voice Live / Engagement:** Azure Foundry Voice Live is in scope for the project, but the
  PathForward Voice Live engagement path is not yet implemented.

## Current Proof Status

The project has live proof for the Foundry Prompt Orchestrator, versioned specialist agents, Tool
Search, A2A specialist calls, Fabric-backed Program Insights, and approval-approved MCP credential
minting from a code-issued gate token.

Offline regression suite:

```powershell
python -m unittest discover -s tests -t .
```

Live proof scripts require the configured Azure/Fabric environment and project `.env`.

## Safety

PathForward uses synthetic data only. No real workers, employee records, or PII are included.

The system is designed to fail closed:

- no grounded evidence means no verified assessment;
- no verified assessment means no credential;
- denied or missing mint authorization means no credential.
