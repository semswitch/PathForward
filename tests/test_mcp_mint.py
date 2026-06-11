import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.agents.generator import Generator
from pathforward.agents.loop import run_assessment_loop
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import LoopResult
from pathforward.credential.mcp_mint import (
    McpMintError,
    MemoryMintReplayStore,
    create_mcp_mint_request,
    mint_from_mcp_request,
    open_mcp_mint_request,
)
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import HERO_WORKER_ID, build_seed
from tests.fakes import FakeLLMClient


class TestMcpMint(unittest.TestCase):
    def setUp(self):
        self.signing_key = "unit-test-mcp-mint-key"
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

    def _sealed(self, *, now=1000, ttl_seconds=900):
        return create_mcp_mint_request(
            self.worker, self.role, self.driving.id, self.skill.id, self.result,
            now=now, ttl_seconds=ttl_seconds, signing_key=self.signing_key,
        )

    def test_create_request_contains_only_reviewable_signed_tool_arguments(self):
        sealed = self._sealed()
        doc = sealed.to_doc()
        self.assertEqual(doc["tool_name"], "pathforward_mint_credential")
        self.assertEqual(doc["server_label"], "pathforward-mint")
        self.assertEqual(doc["require_approval"], "always")
        self.assertEqual(set(doc["arguments"]), {"mint_request_token"})
        request = open_mcp_mint_request(sealed.token, now=1001, signing_key=self.signing_key)
        self.assertEqual(request.worker_id, self.worker.id)
        self.assertEqual(request.skill_id, self.skill.id)
        self.assertEqual(request.driving_edge_id, self.driving.id)
        self.assertEqual(request.loop_status, "verified")
        self.assertEqual(request.citations, self.result.citations)

    def test_abstained_loop_cannot_create_mcp_mint_request(self):
        abstained = LoopResult("abstained", self.driving.id, self.skill.id, 3,
                               None, None, [], ())
        with self.assertRaises(McpMintError):
            create_mcp_mint_request(
                self.worker, self.role, self.driving.id, self.skill.id, abstained,
                signing_key=self.signing_key,
            )

    def test_expired_request_is_rejected(self):
        sealed = self._sealed(now=1000, ttl_seconds=5)
        with self.assertRaisesRegex(McpMintError, "expired"):
            open_mcp_mint_request(sealed.token, now=1006, signing_key=self.signing_key)

    def test_tampered_token_is_rejected(self):
        sealed = self._sealed()
        payload, sig = sealed.token.split(".", 1)
        tampered = payload[:-1] + ("A" if payload[-1] != "A" else "B")
        with self.assertRaisesRegex(McpMintError, "signature|payload"):
            open_mcp_mint_request(f"{tampered}.{sig}", now=1001, signing_key=self.signing_key)

    def test_valid_mcp_request_mints_and_replay_fails_closed(self):
        sealed = self._sealed()
        store = MemoryMintReplayStore()
        cred = mint_from_mcp_request(
            self.worker, self.role, sealed.token,
            replay_store=store, now=1001, signing_key=self.signing_key,
        )
        subject = cred.credential_subject
        self.assertEqual(subject["worker_id"], self.worker.id)
        self.assertEqual(subject["skill_id"], self.skill.id)
        self.assertEqual(subject["cited_edge_id"], self.driving.id)
        self.assertEqual(subject["readiness"], dv.readiness_score(self.worker, self.role))
        with self.assertRaisesRegex(McpMintError, "replay"):
            mint_from_mcp_request(
                self.worker, self.role, sealed.token,
                replay_store=store, now=1001, signing_key=self.signing_key,
            )

    def test_core_returns_tool_ready_structured_credential(self):
        old = os.environ.get("PATHFORWARD_MINT_SIGNING_KEY")
        try:
            os.environ["PATHFORWARD_MINT_SIGNING_KEY"] = self.signing_key
            sealed = create_mcp_mint_request(
                self.worker, self.role, self.driving.id, self.skill.id, self.result,
                signing_key=self.signing_key,
            )
            credential = mint_from_mcp_request(
                self.worker,
                self.role,
                sealed.token,
                replay_store=MemoryMintReplayStore(),
                signing_key=self.signing_key,
            )
            result = {
                "status": "minted",
                "request_id": sealed.request.request_id,
                "credential": credential.to_doc(),
            }
        finally:
            if old is None:
                os.environ.pop("PATHFORWARD_MINT_SIGNING_KEY", None)
            else:
                os.environ["PATHFORWARD_MINT_SIGNING_KEY"] = old
        self.assertEqual(result["status"], "minted")
        self.assertEqual(result["request_id"], sealed.request.request_id)
        self.assertEqual(
            result["credential"]["credentialSubject"]["cited_edge_id"],
            self.driving.id,
        )

    def test_worker_mismatch_is_rejected_before_mint(self):
        sealed = self._sealed()
        wrong_worker = self.onto.workers["EMP-002"]
        wrong_role = self.onto.roles[wrong_worker.target_role_id]
        with self.assertRaisesRegex(McpMintError, "worker mismatch"):
            mint_from_mcp_request(
                wrong_worker, wrong_role, sealed.token,
                replay_store=MemoryMintReplayStore(), now=1001,
                signing_key=self.signing_key,
            )


if __name__ == "__main__":
    unittest.main()
