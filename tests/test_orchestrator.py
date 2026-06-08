"""Orchestrator behaviour: the three-agent loop runs Curator -> loop -> Planner, the causal spine
survives end to end (the minted credential cites the Curator-chosen CertGap edge), and a worker
with no assessable gap fails closed (no mint)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.client import FakeLLMClient
from pathforward.agents.curator import Curator
from pathforward.agents.generator import Generator
from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.orchestrator import run_multiagent
from pathforward.agents.planner import Planner
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.credential.mint import mint
from pathforward.credential.schema import CredentialIntegrityError
from pathforward.iq import derivation as dv
from pathforward.iq.models import Worker
from pathforward.iq.seed import build_seed, HERO_WORKER_ID


def _agents():
    """One client per agent (the loop chains generator turns; others are single-shot)."""
    return (Curator(FakeLLMClient()), Generator(FakeLLMClient()),
            EvidenceGate(LocalNumericChecker()), Planner(FakeLLMClient(), LocalNumericChecker()))


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.onto = build_seed()
        self.edges = dv.build_all_edges(self.onto)

    def test_end_to_end_emp001_verified_and_minted(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        role = self.onto.roles[worker.target_role_id]
        cur, gen, ver, plan = _agents()
        res = run_multiagent(worker, self.onto, self.edges, cur, gen, ver, plan)

        # Curator chose S01 (demo invariant); loop verified the item.
        self.assertEqual(res.curator.chosen_skill_id, "S01")
        self.assertEqual(res.loop.status, "verified")
        self.assertTrue(res.plan.phases)

        # The causal spine survives the orchestrator: the credential cites the Curator-chosen edge.
        cred = mint(worker, role, res.curator.chosen_edge_id, res.curator.chosen_skill_id, res.loop)
        self.assertEqual(cred.credential_subject["cited_edge_id"], "certgap::EMP-001::S01")
        self.assertEqual(cred.credential_subject["cited_edge_id"], res.loop.driving_edge_id)

    def test_to_doc_round_trips_through_json(self):
        worker = self.onto.workers[HERO_WORKER_ID]
        cur, gen, ver, plan = _agents()
        res = run_multiagent(worker, self.onto, self.edges, cur, gen, ver, plan)
        doc = res.to_doc()
        self.assertEqual(set(doc), {"curator", "loop", "plan"})
        json.dumps(doc)   # must be JSON-serializable end to end

    def test_no_assessable_gap_fails_closed_and_does_not_mint(self):
        # Worker whose only missing skill is S09 (Containers) — required by R-DEVOPS, certified by
        # nothing -> not assessable -> Curator returns no target -> orchestrator abstains.
        worker = Worker("EMP-NOGAP", "Test", "at-risk role", "R-DEVOPS",
                        ("S06", "S07", "S08", "S11"), 5.0, ())
        self.onto.workers[worker.id] = worker
        role = self.onto.roles["R-DEVOPS"]
        edges = dv.build_all_edges(self.onto)
        cur, gen, ver, plan = _agents()
        res = run_multiagent(worker, self.onto, edges, cur, gen, ver, plan)

        self.assertEqual(res.curator.chosen_skill_id, "")
        self.assertEqual(res.loop.status, "abstained")
        self.assertEqual(res.loop.citations, ())
        with self.assertRaises(CredentialIntegrityError):
            mint(worker, role, "", "", res.loop)


if __name__ == "__main__":
    unittest.main()
