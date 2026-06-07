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
| Loop | **Agentic tool-calling on the GA Responses API**: gpt‑5.5 is given the retrieval tool and *itself* decides when to call it (`tool_choice='auto'`, not `'required'`). Server-side prompt agents *with tools* DO exist on `azure-ai-projects 2.2.0` (`PromptAgentDefinition` / `create_version`); only classic thread/run is gone. The orchestrator still owns the payload → citations propagate deterministically, and the Verifier gates on `corpus ∩ retrieved`. |
| Grounding | The model's tool is the **GA agentic-retrieval knowledge base** (`KnowledgeBaseRetrievalClient`, `2026-04-01`, extractive `intents[]` + citations). **gpt‑5.5 plans/authors the searches; Search reranks + cites, it does not plan** (Search-side query planning is preview — kept off the critical path). |
| Fabric | Ontology authored as a **non-Power BI Fabric item** on a **paid F2+** capacity (Trial can't run the data agent). The **Search mirror** is the runtime path. |
| Mirror | Pre-materializes base + **derived** edges (provenance + validity-time) + traversal paths as first-class docs; build-time non-empty guard. |
| Region | **East US 2** — Foundry + gpt-5.5 + Fabric. **Azure AI Search runs in East US** (eastus2 was Search-capacity-constrained; cross-region Search↔model is fine — only the Fabric data agent needs co-location). |
| Reliability | Loop hard-capped **N=3 → fail-closed abstain**; the credential mint refuses abstained results and asserts `cited_edge_id == driving CertGap edge`. |
| Governance | A **Foundry Toolbox** (`pathforward-toolbox`) + named **Skill** (`pathforward`) register the search capability as a **versioned, RAI-policy-bearing catalog** (`scripts/build_toolbox.py`). RAI (`pathforward-rai`, Blocking) is **enforced at the model deployment** and **declared on the toolbox**; agent-definition `rai_config` is a 2.2.0 preview gap (rejects even system policies) so it is not used. The registered toolbox is a **governance/registry artifact, not an inference consume-seam** (CRUD-only routes, no `/mcp`; `PromptAgentDefinition` carries no toolbox ref) — inference stays on the proven GA direct-attach. Framed as *governed seam + versioned RAI registry*, **not** platform-enforced least-privilege (Discover & Govern is roadmap). |

## Offline ↔ Azure boundary

Everything in `pathforward/` runs offline against `FakeLLMClient` + `LocalNumericChecker`.
Swapping in `FoundryLLMClient` (Responses API) and `CodeInterpreterChecker` (Code Interpreter
tool) — plus wiring agentic retrieval and the Fabric ontology — is the Azure layer. The
interfaces (`LLMClient`, `NumericChecker`) are identical, so the reasoning logic does not change.
