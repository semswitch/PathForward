"""Offline proof for the governed mint approval surface.

This proves checklist item 5's local trust behavior: a verified loop produces a reviewable approval
request, denial fails closed, approval mints through the existing `credential.mint.mint()` spine.
It is not an MCP server proof; live MCP/HITL hosting remains a follow-up.

    python scripts/smoke_mint_approval.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from pathforward.agents.client import FakeLLMClient  # noqa: E402
from pathforward.agents.evidence_gate import EvidenceGate  # noqa: E402
from pathforward.agents.generator import Generator  # noqa: E402
from pathforward.agents.loop import run_assessment_loop  # noqa: E402
from pathforward.agents.numeric import LocalNumericChecker  # noqa: E402
from pathforward.credential.approval import (  # noqa: E402
    MintApprovalDecision,
    MintApprovalError,
    mint_with_approval,
    request_mint_approval,
)
from pathforward.iq import derivation as dv  # noqa: E402
from pathforward.iq import traversal  # noqa: E402
from pathforward.iq.seed import HERO_WORKER_ID, build_seed  # noqa: E402


def main() -> int:
    onto = build_seed()
    worker = onto.workers[HERO_WORKER_ID]
    role = onto.roles[worker.target_role_id]
    edges = dv.build_all_edges(onto)
    driving = traversal.cert_gap_edges(worker, onto, edges)[0]
    skill = onto.skills[driving.target_id]
    result = run_assessment_loop(
        driving, skill, traversal.approved_refs(worker, skill, onto),
        Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()))
    request = request_mint_approval(worker, role, driving.id, skill.id, result)
    print(f"approval request: id={request.request_id} require_approval={request.require_approval} "
          f"worker={request.worker_id} skill={request.skill_id} readiness={request.readiness}")

    try:
        mint_with_approval(worker, role, driving.id, skill.id, result,
                           MintApprovalDecision(request.request_id, approved=False,
                                                approver="demo-reviewer",
                                                rationale="deny path proof"))
    except MintApprovalError as exc:
        print(f"denied path: HELD ({exc})")
    else:
        print("denied path: BREACH")
        return 1

    credential = mint_with_approval(
        worker, role, driving.id, skill.id, result,
        MintApprovalDecision(request.request_id, approved=True,
                             approver="demo-reviewer",
                             rationale="evidence and spine reviewed"))
    cs = credential.credential_subject
    print(f"approved path: MINTED cited_edge_id={cs['cited_edge_id']} readiness={cs['readiness']}")
    print("MINT APPROVAL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
