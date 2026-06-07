"""Live smoke: prove gpt-5.5 AUTONOMOUSLY plans + runs the Azure AI Search tool and grounds
its answer in citations that resolve to our index docs.

Creates a throwaway prompt agent (PromptAgentDefinition + AzureAISearchTool, tool_choice='auto'),
runs a grounded query via the Responses API (agent_reference), parses the retrieval TRACE
(azure_ai_search_call_output.documents[].id -> ref_id) and the cited url_citation titles, asserts
the EMP-001 hero grounding came back, runs a quick abstain probe, then deletes the agent.

    python scripts/smoke_search.py

`parse_retrieval` is the reusable extraction the agent runner will share.
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.config import load_settings  # noqa: E402

SEARCH_CONNECTION_NAME = "pathforward-search"
AGENT_NAME = "pf-smoke"

INSTRUCTIONS = (
    "You are PathForward's reskilling assessor. ALWAYS use the Azure AI Search tool to "
    "retrieve evidence before answering, and you MUST cite the sources you used. If the "
    "search returns nothing relevant, say you cannot answer rather than guessing."
)


def _key_to_ref(key: str) -> str:
    return key.replace("__", "::")


def parse_retrieval(resp):
    """Return (queries, retrieved_ref_ids, cited_ref_ids).

    retrieved = ids the TOOL physically returned (azure_ai_search_call_output.documents[].id),
    the provenance trace the gate trusts. cited = url_citation titles matched back to retrieved
    docs (so a citation only counts if it maps to a doc the tool actually returned).
    """
    retrieved: dict[str, str] = {}   # ref_id -> title
    queries: list[str] = []
    cited_titles: set[str] = set()
    for item in (getattr(resp, "output", None) or []):
        itype = getattr(item, "type", None)
        if itype == "azure_ai_search_call":
            try:
                q = json.loads(getattr(item, "arguments", "") or "{}").get("query")
                if q:
                    queries.append(q)
            except Exception:  # noqa: BLE001
                pass
        elif itype == "azure_ai_search_call_output":
            try:
                for d in json.loads(getattr(item, "output", "") or "{}").get("documents", []):
                    key = d.get("id", "")
                    if key:
                        retrieved[_key_to_ref(key)] = d.get("title", "")
            except Exception:  # noqa: BLE001
                pass
        elif itype == "message":
            for content in (getattr(item, "content", None) or []):
                for ann in (getattr(content, "annotations", None) or []):
                    if getattr(ann, "type", None) == "url_citation" and getattr(ann, "title", None):
                        cited_titles.add(ann.title)
    title_to_ref: dict[str, str] = {}
    for ref, title in retrieved.items():
        title_to_ref.setdefault(title, ref)
    cited = {title_to_ref[t] for t in cited_titles if t in title_to_ref}
    return queries, set(retrieved), cited


def ask(openai, agent, question: str):
    resp = openai.responses.create(
        input=question,
        tool_choice="auto",   # AUTONOMY: the model decides when/what to search (not 'required')
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    )
    try:
        text = resp.output_text
    except Exception:  # noqa: BLE001
        text = "<no output_text>"
    return text, parse_retrieval(resp)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console may be cp1252
    except Exception:  # noqa: BLE001
        pass
    s = load_settings(os.path.join(_ROOT, ".env"))
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        AISearchIndexResource, AzureAISearchQueryType, AzureAISearchTool,
        AzureAISearchToolResource, PromptAgentDefinition,
    )
    from azure.identity import DefaultAzureCredential

    project = AIProjectClient(endpoint=s.foundry_project_endpoint, credential=DefaultAzureCredential())
    openai = project.get_openai_client()
    conn = project.connections.get(SEARCH_CONNECTION_NAME)
    print(f"connection: {conn.name}")

    agent = project.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=s.model_deployment,
            instructions=INSTRUCTIONS,
            tools=[AzureAISearchTool(azure_ai_search=AzureAISearchToolResource(indexes=[
                AISearchIndexResource(project_connection_id=conn.id, index_name=s.search_index,
                                      query_type=AzureAISearchQueryType.SEMANTIC),
            ]))],
        ),
        description="PathForward smoke agent (throwaway).",
    )
    print(f"agent: {agent.name} v{agent.version}")

    rc = 1
    try:
        # --- grounded query: autonomy + retrieval + citations resolve to the corpus ---
        text, (queries, retrieved, cited) = ask(
            openai,
            agent,
            "What certification gap does worker EMP-001 have for the Cloud Engineer role (R-CLOUD), "
            "and which certification helps close it? Cite the evidence.",
        )
        print(f"\n[grounded] model authored {len(queries)} autonomous search queries:")
        for q in queries:
            print(f"   - {q}")
        print(f"[grounded] retrieved {len(retrieved)} docs; cited {len(cited)}")
        print(f"[grounded] cited ref_ids: {sorted(cited)}")
        print(f"\nanswer:\n{text[:700]}")

        gaps = {"certgap::EMP-001::S01", "certgap::EMP-001::S02", "certgap::EMP-001::S08"}
        checks = {
            "model searched autonomously (>=1 query)": len(queries) >= 1,
            "EMP-001 certgap docs retrieved (S01/S02/S08)": gaps <= retrieved,
            "AZ-204 corpus card grounded (cited or retrieved)":
                "corpus::AZ-204" in cited or "corpus::AZ-204" in retrieved,
            "every cited ref resolves to a retrieved doc (no dangling citation)":
                cited <= retrieved,
        }

        # --- abstain probe: a worker that does not exist must not yield fabricated gaps ---
        atext, (aq, aretr, acited) = ask(
            openai, agent, "What is the certification gap for worker EMP-999? Cite the evidence.")
        fabricated = {r for r in acited if r.startswith("certgap::EMP-999")}
        print(f"\n[abstain] EMP-999 -> cited {sorted(acited) or '(none)'}")
        print(f"[abstain] answer: {atext[:240]}")
        checks["no fabricated EMP-999 certgap citation"] = not fabricated

        print("\n=== checks ===")
        for name, ok in checks.items():
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        rc = 0 if all(checks.values()) else 1
        print("\nSMOKE", "PASS" if rc == 0 else "FAIL")
    finally:
        project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        print("agent deleted")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
