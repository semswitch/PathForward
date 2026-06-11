"""Local mint authorization: authorization is required before mint, but mint still owns the spine."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fakes import FakeLLMClient
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.generator import Generator
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import LoopResult
from pathforward.credential.approval import (
    MintApprovalDecision,
    MintApprovalError,
    mint_with_approval,
    request_mint_approval,
)
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import HERO_WORKER_ID, build_seed


class TestMintApproval(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[self.worker.target_role_id]
        self.edges = dv.build_all_edges(self.onto)
        self.driving = traversal.cert_gap_edges(self.worker, self.onto, self.edges)[0]
        self.skill = self.onto.skills[self.driving.target_id]
        self.allowed = traversal.approved_refs(self.worker, self.skill, self.onto)
        self.result = run_assessment_loop(
            self.driving, self.skill, self.allowed,
            Generator(FakeLLMClient()), EvidenceGate(LocalNumericChecker()))

    def test_approval_request_contains_code_owned_review_fields(self):
        req = request_mint_approval(self.worker, self.role, self.driving.id,
                                    self.skill.id, self.result)
        self.assertEqual(req.worker_id, self.worker.id)
        self.assertEqual(req.target_role_id, self.role.id)
        self.assertEqual(req.skill_id, self.skill.id)
        self.assertEqual(req.driving_edge_id, self.driving.id)
        self.assertEqual(req.loop_status, "verified")
        self.assertEqual(req.citations, self.result.citations)
        self.assertEqual(req.readiness, dv.readiness_score(self.worker, self.role))
        self.assertEqual(req.require_approval, "always")
        self.assertTrue(req.request_id.startswith("mintreq_"))
        self.assertEqual(req.to_doc()["citations"], list(self.result.citations))

    def test_abstained_loop_gets_no_approval_request(self):
        abstained = LoopResult("abstained", self.driving.id, self.skill.id, 3,
                               None, None, [], ())
        with self.assertRaises(MintApprovalError):
            request_mint_approval(self.worker, self.role, self.driving.id,
                                  self.skill.id, abstained)

    def test_denied_approval_fails_closed(self):
        req = request_mint_approval(self.worker, self.role, self.driving.id,
                                    self.skill.id, self.result)
        decision = MintApprovalDecision(req.request_id, approved=False,
                                        approver="human-reviewer",
                                        rationale="needs manual review")
        with self.assertRaises(MintApprovalError):
            mint_with_approval(self.worker, self.role, self.driving.id,
                               self.skill.id, self.result, decision)

    def test_approved_request_mints_and_preserves_spine(self):
        req = request_mint_approval(self.worker, self.role, self.driving.id,
                                    self.skill.id, self.result)
        decision = MintApprovalDecision(req.request_id, approved=True,
                                        approver="human-reviewer",
                                        rationale="evidence and spine reviewed")
        cred = mint_with_approval(self.worker, self.role, self.driving.id,
                                  self.skill.id, self.result, decision)
        self.assertEqual(cred.credential_subject["cited_edge_id"], self.driving.id)
        self.assertEqual(cred.credential_subject["skill_id"], self.skill.id)
        self.assertEqual(cred.credential_subject["readiness"],
                         dv.readiness_score(self.worker, self.role))

    def test_replayed_or_tampered_approval_is_rejected(self):
        decision = MintApprovalDecision("mintreq_wrong", approved=True,
                                        approver="human-reviewer")
        with self.assertRaises(MintApprovalError):
            mint_with_approval(self.worker, self.role, self.driving.id,
                               self.skill.id, self.result, decision)


if __name__ == "__main__":
    unittest.main()
