# PathForward — Architecture

> Foundry-centric. Every box maps to a Microsoft service or a module in this repo.
> This is the diagram for the submission (the rubric requires an architecture diagram
> showing the Microsoft tools).

## Agent topology + IQ wiring

```mermaid
flowchart TB
    user([Worker / Manager]) --> orch

    subgraph WF["Foundry Workflow (sequential + human-in-the-loop)"]
        orch[Orchestrator]
        curator[Curator agent]
        planner[Planner agent\ncapacity + accessibility]
        engage[Engagement agent\nvoice-first optional]
        insights[Manager Insights agent]
    end

    subgraph LOOP["Code-driven Responses loop (the signature)"]
        gen[Generator agent]
        ver[Verifier agent\n5-criterion + evidence gate]
        gen -- propose --> ver
        ver -- reject, regenerate (cap N=3) --> gen
        ver -- fail-closed --> abstain([ABSTAIN / escalate])
    end

    curator --> LOOP
    orch --> curator --> planner --> engage --> insights

    subgraph IQ["Microsoft IQ"]
        fabric[(Fabric IQ ontology\nderived CertGap / Readiness)]
        foundryiq[(Foundry IQ\nagentic retrieval — GA 2026-04-01)]
        mirror[(Search mirror\npre-materialized edges + paths)]
    end

    curator -- multi-hop adjacency --> fabric
    fabric -- derive once --> mirror
    gen -- ground items --> foundryiq
    ver -- ground rationale --> foundryiq
    foundryiq --- mirror

    subgraph TOOLS["Tools"]
        code[Code Interpreter\nnumeric checks]
        mint[[MCP mint\nrequire_approval: always]]
        voice[Voice Live 2026-04-10\nOral Viva]
    end

    ver -- numeric claims --> code
    ver -- verified --> mint
    mint --> cred([Citation-backed credential\ncites the driving CertGap edge])
    engage -. accessibility .-> voice

    subgraph OBS["Trust substrate (visible)"]
        evals[Foundry eval SDK]
        redteam[AI Red Teaming / PyRIT]
        otel[OpenTelemetry tracing]
    end
    LOOP -. traces .-> otel
    LOOP -. groundedness/safety .-> evals
    mint -. ASR scorecard .-> redteam
```

## Key decisions (hardened by the red-team — see ../Microsoft-Agents-League/04-Plan-Redteam.md)

| Area | Decision |
|---|---|
| Loop | **Code-driven GA Responses loop**, not classic connected agents (which don't exist on the GA SDK). Orchestrator owns the payload → citations propagate deterministically. |
| Grounding | **GA agentic retrieval is extractive** (rerank + citations over agent-supplied `intents[]`). The agent layer plans the queries; Search does not. |
| Fabric | Ontology authored as a **non-Power BI Fabric item** on a **paid F2+** capacity (Trial can't run the data agent). The **Search mirror** is the runtime path. |
| Mirror | Pre-materializes base + **derived** edges (provenance + validity-time) + traversal paths as first-class docs; build-time non-empty guard. |
| Region | **North Central US** (satisfies risk evaluators + hosted agents + Voice WebSocket). |
| Reliability | Loop hard-capped **N=3 → fail-closed abstain**; the credential mint refuses abstained results and asserts `cited_edge_id == driving CertGap edge`. |

## Offline ↔ Azure boundary

Everything in `pathforward/` runs offline against `FakeLLMClient` + `LocalNumericChecker`.
Swapping in `FoundryLLMClient` (Responses API) and `CodeInterpreterChecker` (Code Interpreter
tool) — plus wiring agentic retrieval and the Fabric ontology — is the Azure layer. The
interfaces (`LLMClient`, `NumericChecker`) are identical, so the reasoning logic does not change.
