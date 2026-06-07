"""Credential integrity (JC-3): cited edge == driving edge, fail-closed, citations required."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient
from pathforward.agents.generator import Generator
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import LoopResult
from pathforward.agents.verifier import Verifier
from pathforward.credential.mint import mint
from pathforward.credential.schema import CredentialIntegrityError
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed, HERO_WORKER_ID


class TestCredential(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.worker = self.onto.workers[HERO_WORKER_ID]
        self.role = self.onto.roles[self.worker.target_role_id]
        self.edges = dv.build_all_edges(self.onto)
        self.driving = traversal.cert_gap_edges(self.worker, self.onto, self.edges)[0]
        self.skill = self.onto.skills[self.driving.target_id]
        self.allowed = tuple(self.driving.source_ref_ids) + ("corpus::AZ-204",)
        self.result = run_assessment_loop(
            self.driving, self.skill, self.allowed,
            Generator(FakeLLMClient()), Verifier(LocalNumericChecker()))

    def test_mint_asserts_causal_spine(self):
        cred = mint(self.worker, self.role, self.driving.id, self.skill.id, self.result)
        self.assertEqual(cred.credential_subject["cited_edge_id"], self.driving.id)
        self.assertTrue(cred.evidence)

    def test_mint_rejects_edge_mismatch(self):
        with self.assertRaises(CredentialIntegrityError):
            mint(self.worker, self.role, "certgap::EMP-001::S99", self.skill.id, self.result)

    def test_mint_refuses_abstained_loop(self):
        abstained = LoopResult("abstained", self.driving.id, self.skill.id, 3,
                               None, None, [], ())
        with self.assertRaises(CredentialIntegrityError):
            mint(self.worker, self.role, self.driving.id, self.skill.id, abstained)


if __name__ == "__main__":
    unittest.main()
