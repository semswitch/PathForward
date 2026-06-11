# PathForward Non-Negotiable Agentic Architecture Contract

## Required Architecture Shape

```text
Foundry Prompt Agent: pathforward-orchestrator
  calls versioned Foundry specialist agents
  Foundry Skills / Toolbox define those agent versions
  Orchestrator / Conductor reasoning over the allowed route
  Curator agent
  Generator agent with Foundry grounded retrieval
  Critic agent
  deterministic Evidence Gate
  bounded reflection / adaptive retry
  Planner agent
  Program Insights / Fabric agent
  human approval where applicable
  deterministic mint
```

`run_multiagent` is not to be used for anything ever, except tests that validate that code works.

## Non-Negotiable Requirements

1. **Code does not equal agent.**
   `EvidenceGate`, `LocalNumericChecker`, readiness derivation, mint, and deterministic orchestration
   are code. They are not agents.

2. **Use the Foundry Prompt Agent Orchestrator surface.**
   The architecture surface is the versioned Foundry Prompt Agent `pathforward-orchestrator` calling
   versioned Foundry specialist agents whose Skills, tools, guardrails, and system prompts are
   attached in Foundry. Agent Framework Workflow, `PF_WORKFLOW`, Workflow HITL, and Workflow graph work are unauthorized for this
   architecture unless the user explicitly re-authorizes them.

3. **The Prompt Orchestrator proof must show the agentic reasoning beats in the final demo artifact.**
   The proof surface must visibly show Orchestrator route reasoning, Curator, Generator, Critic,
   reflection, adaptive band, Evidence Gate, Fabric, and ABSTAIN. Telemetry or nested trace views may
   be used for the internal loop if decomposing any execution graph would duplicate trust logic.

4. **Foundry Toolbox and Foundry Skill are runtime surfaces.**
   `/pathforward` must exist as a real `agentskills.io` Skill, be registered in Foundry, be visible in
   the portal/dashboard, and be baked into the versioned Foundry agent definitions used at runtime.
   Local-only Markdown, inline prompt copies, registry-only Skills, and legacy non-Hosted shapes are unapproved.

5. **Each agent must carry its Foundry runtime contract.**
   Foundry tools, Skills, guardrails, and system prompts must be attached to the appropriate agents.
   Evaluations must run against those attached agent contracts, not detached local prompt copies.

6. **Fabric Program Insights must use the live Fabric data agent.**
   Program Insights must return `source="fabric-live"` and at least one Fabric-derived cohort metric
   such as cohort size, cohort rank/percentile, average readiness, or bottleneck skill counts.
   Offline derivation-floor Program Insights is not approved for the product runtime.

7. **Credential minting must be exposed through an MCP mint server.**
   The project requires a hosted MCP mint tool with explicit approval before issuance. The MCP server
   must call the deterministic mint code and must not let an agent bypass Evidence Gate, readiness,
   or causal-spine checks.

8. **Voice Live / Engagement is required.**
   Azure Foundry Voice Live is available through the project's endpoint and API key. PathForward must
   implement a Voice Live engagement path that produces the transcript artifact used by the shared
   scoring and verification flow.

9. **Telemetry must be used for live validation.**
   Telemetry is connected through Azure Application Insights. Live runs and validations must emit and
   use telemetry logs as part of the proof record.

10. **Only live proof can mark product behavior done.**
    Fake-agent and offline tests prove code only. A feature, agent, tool, Skill, Fabric path,
    telemetry path, Voice Live path, or mint path is not done until it has live proof.

11. **FakeLLMClient is code-test only.**
    Do not use or refer to FakeLLMClient during implementation except to prove code works before live
    testing.
