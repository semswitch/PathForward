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

- A Foundry Hosted Agent acts as the top-level Orchestrator.
- Specialist reasoning agents handle skill-gap selection, assessment generation, critique, planning,
  and program insights.
- Foundry Skills define the agent behavior and are baked into versioned specialist agents through
  the Foundry Toolbox/provisioning surface.
- Azure AI Search grounds assessment generation in cited evidence.
- Microsoft Fabric provides live cohort/program insights over the reskilling ontology.
- A deterministic Evidence Gate and governed mint boundary prevent unsafe credential issuance.

## What It Demonstrates

- **Multi-agent reasoning:** agents plan, critique, adapt, and explain the reskilling path.
- **Grounded verification:** assessment items must cite retrieved evidence before they can pass.
- **Honest refusal:** failed or ungrounded attempts end in ABSTAIN, not a fake pass.
- **Governed credentialing:** minting re-checks the causal spine and fails closed when proof is missing.
- **Microsoft-native architecture:** Foundry Hosted Agent, Foundry Skills/Toolbox, Azure AI Search,
  Fabric data agent, Azure Monitor telemetry, and Foundry evals.

## Pending Product Requirements

- **MCP mint server:** signed request tokens are implemented; Azure Function hosting,
  Foundry Toolbox attachment, and end-to-end approval proof are pending.
- **Voice Live / Engagement:** Azure Foundry Voice Live is in scope for the project, but the
  PathForward Voice Live engagement path is not yet implemented.

## Current Proof Status

The project has live proof for the main Foundry multi-agent path, versioned specialist agents,
Fabric-backed Program Insights, and Hosted Agent invocation. Hosted Agent version 18 proves the latest
hardening before the Function-backed MCP mint tool: semantic ABSTAIN, denied mint refusal, governed mint behavior, and a hosted scorecard with
4/4 groundedness cases, 4/4 prompt-surface attacks held, and 1/1 ABSTAIN case passed.

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
