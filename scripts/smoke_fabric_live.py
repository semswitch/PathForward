"""Live smoke — the 'fabric-live' Program Insights tier (Microsoft Fabric data agent over OneLake).

The model answers a cohort question by querying a PUBLISHED Fabric data agent (NL2SQL, On-Behalf-Of)
through `FabricInsightsClient` (`MicrosoftFabricPreviewTool` on a prompt agent). `cohort.py` (over the
single `derivation.py` source) stays the reconciliation ANCHOR — Fabric is advisory and never gates
anything; this path never touches the Evidence Gate or mint.

Prereqs: `azure_ready`, a published Fabric data agent, and a Foundry 'Microsoft Fabric' connection
whose name is in `FABRIC_CONNECTION_NAME`. IDENTITY: the Fabric data agent is OBO/user-only — service
principals are NOT supported — so `FabricInsightsClient` uses AzureCliCredential. You MUST `az login`
as a USER (not the SP) who has READ on the data agent + Read on the lakehouse before running. Run from
the project .venv (azure-ai-projects present):

    az login            # as a user, NOT the service principal
    .venv\\Scripts\\python.exe scripts\\smoke_fabric_live.py
"""
from __future__ import annotations

import sys

from pathforward.agents.foundry import FabricInsightsClient
from pathforward.agents.insights import ProgramInsightsAgent
from pathforward.config import load_settings
from pathforward.iq import derivation as dv
from pathforward.iq.seed import HERO_WORKER_ID, build_seed


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    s = load_settings()
    if not s.azure_ready:
        print("SKIP: azure not configured (azure_ready=False)")
        return 0
    if not s.fabric_connection_name:
        print("SKIP: FABRIC_CONNECTION_NAME not set (no Foundry 'Microsoft Fabric' connection yet)")
        return 0

    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]

    # Code-truth anchor (independent of Fabric), used only to reconcile the live answer.
    cohort_workers = [w for w in onto.workers.values() if w.target_role_id == role.id]
    size = len(cohort_workers)
    mean = round(sum(dv.readiness_score(w, role) for w in cohort_workers) / size, 4) if size else 0.0

    print(f"worker={worker.id} role={role.name} ({role.id})  connection={s.fabric_connection_name}")
    print(f"code-truth anchor: cohort size={size}  mean readiness={mean}")

    client = FabricInsightsClient(endpoint=s.foundry_project_endpoint,
                                  connection_name=s.fabric_connection_name)
    try:
        agent = ProgramInsightsAgent(client)
        ins = agent.analyze_via_fabric(worker, role, onto)
    finally:
        client.close()
        print("agent deleted")

    print("\n--- Fabric narrative (live, NL2SQL over OneLake) ---")
    print(ins.narrative or "(empty)")

    # Advisory, best-effort reconcile: free-text answers can't be parsed exactly, so this is a
    # REVIEW signal, never a gate. The code-owned aggregates remain authoritative.
    narrative = ins.narrative or ""
    reconciled = str(size) in narrative
    retrieval_failed = any(marker in narrative.lower() for marker in (
        "technical retrieval issue",
        "unable to retrieve",
        "could not retrieve",
    ))
    print(f"\nadvisory reconcile (cohort size {size} appears in the Fabric answer): "
          f"{'AGREES' if reconciled else 'REVIEW (free-text; not a gate)'}")

    checks = [
        ("source is fabric-live", ins.source == "fabric-live"),
        ("Fabric returned a narrative", bool(narrative.strip())),
        ("Fabric retrieved cohort data", not retrieval_failed and reconciled),
        ("code-truth aggregates attached", bool(ins.role_cohort and ins.worker_comparison)),
    ]
    print("\n=== checks ===")
    all_ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        all_ok = all_ok and passed

    if not all_ok:
        print("\nLIVE FABRIC INSIGHTS FAIL")
        return 1
    print("\nLIVE FABRIC INSIGHTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
