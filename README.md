# PathForward

**A Microsoft Foundry multi-agent reasoning system for workforce reskilling.**

PathForward helps workers in roles at risk of automation find credible paths into adjacent,
in-demand technical roles. It reasons over a skill ontology, builds a practical learning plan, and
runs a grounded competency-verification loop that issues a portable credential only when the evidence
supports it.

> PathForward would rather say **not yet** than issue a credential it cannot prove.

## ▶ See it in action

**[Architecture Tour → semswitch.github.io/PathForward/tour](https://semswitch.github.io/PathForward/tour)** —
a narrated walkthrough of the full reasoning flow.

## The flow

A Foundry Prompt Agent — `pathforward-orchestrator` — reasons over the allowed route and hands off to
versioned Foundry specialist agents:

1. **Route** — resolve the worker's skill-gap facts autonomously (no facts injected into the prompt).
2. **Curator → Generator → Critic** — select the skill gap, generate assessment items grounded in
   cited evidence (Azure AI Search), and critique them.
3. **Evidence Gate** — a deterministic check; only a verified assessment earns a signed mint request.
4. **Planner → Program Insights** — advise next steps and place the worker against live Microsoft
   Fabric cohort metrics.
5. **Mint** — issue a portable credential only after the Evidence Gate passes **and** an explicit
   approval, through a governed MCP boundary that re-checks the proof.

Specialist Skills are baked into each agent at provision time; the route / gate / mint / Fabric MCP
tools and the conversational A2A specialist handoffs are attached directly to the agent definitions.

## Safety

PathForward uses synthetic data only — no real workers, employee records, or PII. The system fails
closed: no grounded evidence → no verified assessment; no verified assessment → no credential; denied
or missing mint authorization → no credential.
