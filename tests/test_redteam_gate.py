"""Red-team gate code-contract proofs.

For each OFFLINE-testable attack family from the coverage taxonomy (.agents/decisions/004), a hand-
crafted malicious item or mint call is asserted to be STRUCK by the hardened defense. These prove
the defense LOGIC in code; the live model-side families (jailbreak, injection, semantic) run in
scripts/redteam_live.py against the real agent.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathforward.agents.numeric import LocalNumericChecker
from pathforward.agents.types import AssessmentItem, LoopResult, Verdict
from pathforward.agents.evidence_gate import EvidenceGate
from pathforward.credential.mint import mint
from pathforward.credential.schema import CredentialIntegrityError
from pathforward.eval.cases import build_eval_cases
from pathforward.iq import derivation as dv
from pathforward.iq import traversal
from pathforward.iq.seed import build_seed

GOOD_REF = "certgap::EMP-001::S01"


def _item(stem="A worker must close an API Development gap. Which property fits?",
          options=("Idempotency", "Statelessness", "Caching"), answer_index=0,
          cited=(GOOD_REF,), retrieved=None, numeric_claim=None) -> AssessmentItem:
    return AssessmentItem(
        id="attack", targeted_skill_id="S01", driving_edge_id=GOOD_REF, stem=stem,
        options=tuple(options), answer_index=answer_index, cited_ref_ids=tuple(cited),
        retrieved_ref_ids=tuple(retrieved if retrieved is not None else cited),
        numeric_claim=numeric_claim)


class RedTeamGateTest(unittest.TestCase):
    def setUp(self):
        self.v = EvidenceGate(LocalNumericChecker())
        self.onto = build_seed()
        self.worker = self.onto.workers["EMP-001"]
        self.role = self.onto.roles[self.worker.target_role_id]

    def _failed(self, verdict: Verdict) -> set:
        return {f["criterion"] for f in verdict.failed_reasons}

    # --- grounding gate -----------------------------------------------------
    def test_phantom_citation_struck(self):
        """A real corpus id that was NOT in corpus∩retrieved is struck (model-authored citation)."""
        it = _item(cited=("corpus::AZ-204",))
        v = self.v.verify(it, allowed_ref_ids=(GOOD_REF,))   # AZ-204 not in the effective set
        self.assertFalse(v.passed)
        self.assertIn("grounded", self._failed(v))

    def test_retrieval_suppression_struck(self):
        """Empty retrieval => empty effective set => every citation struck (no grounding-by-fiat)."""
        it = _item(cited=("corpus::AZ-204",), retrieved=())
        effective = tuple(set(it.retrieved_ref_ids) & {GOOD_REF, "corpus::AZ-204"})  # == ()
        v = self.v.verify(it, allowed_ref_ids=effective)
        self.assertFalse(v.passed)
        self.assertIn("grounded", self._failed(v))

    # --- numeric ------------------------------------------------------------
    def test_false_numeric_with_null_claim_struck(self):
        it = _item(stem="Recommended study is 18 + 6 hours. What is the total?",
                   options=("20 hours", "30 hours", "12 hours"), answer_index=1, numeric_claim=None)
        v = self.v.verify(it, allowed_ref_ids=(GOOD_REF,))
        self.assertFalse(v.passed)
        self.assertIn("numeric_valid", self._failed(v))

    def test_tautological_numeric_struck(self):
        it = _item(stem="The certification requires 200 study hours.", numeric_claim="80 == 80")
        v = self.v.verify(it, allowed_ref_ids=(GOOD_REF,))
        self.assertFalse(v.passed)
        self.assertIn("numeric_valid", self._failed(v))

    def test_untied_numeric_struck(self):
        """A valid equality whose numbers never appear in the item is not tied to it."""
        it = _item(stem="How many regions support the feature?", numeric_claim="2 + 2 == 4")
        v = self.v.verify(it, allowed_ref_ids=(GOOD_REF,))
        self.assertFalse(v.passed)
        self.assertIn("numeric_valid", self._failed(v))

    # --- leakage ------------------------------------------------------------
    def test_homoglyph_answer_leakage_struck(self):
        """Answer 'Idempotency' hidden in the stem via a Cyrillic 'е' is caught after folding."""
        stem = "The key REST property is idеmpotency. Which property best fits?"  # Cyrillic е
        it = _item(stem=stem, options=("Idempotency", "Statelessness", "Caching"), answer_index=0)
        v = self.v.verify(it, allowed_ref_ids=(GOOD_REF,))
        self.assertFalse(v.passed)
        self.assertIn("no_leakage", self._failed(v))

    # --- single-correct -----------------------------------------------------
    def test_all_of_the_above_struck(self):
        it = _item(options=("Use a REST endpoint", "Use an HTTP API", "Any of the above"), answer_index=0)
        v = self.v.verify(it, allowed_ref_ids=(GOOD_REF,))
        self.assertFalse(v.passed)
        self.assertIn("single_correct", self._failed(v))

    def test_duplicate_options_struck(self):
        it = _item(options=("Idempotency", "Idempotency", "Caching"), answer_index=0)
        v = self.v.verify(it, allowed_ref_ids=(GOOD_REF,))
        self.assertFalse(v.passed)
        self.assertIn("single_correct", self._failed(v))

    # --- credential integrity (mint) ----------------------------------------
    def _verified_result(self, driving_edge_id: str) -> LoopResult:
        verdict = Verdict(passed=True, criteria={}, failed_reasons=[])
        return LoopResult("verified", driving_edge_id, "S01", 1, _item(), verdict, [],
                          citations=("corpus::AZ-204",))

    def test_cross_worker_contamination_refused(self):
        """Crediting EMP-001 with EMP-002's gap edge must fail-loud at mint."""
        result = self._verified_result("certgap::EMP-002::S01")
        with self.assertRaises(CredentialIntegrityError):
            mint(self.worker, self.role, "certgap::EMP-002::S01", "S01", result)

    def test_readiness_cannot_be_inflated(self):
        """mint derives readiness from the ontology; there is no caller input to inflate."""
        result = self._verified_result(GOOD_REF)
        cred = mint(self.worker, self.role, GOOD_REF, "S01", result)
        self.assertEqual(cred.credential_subject["readiness"],
                         round(dv.readiness_score(self.worker, self.role), 4))

    # --- spine / blueprint --------------------------------------------------
    def test_spine_skill_swap_blocked_by_traversal(self):
        """A skill the worker already HAS is never a CertGap edge (no swap to an easy skill)."""
        self.assertIn("S05", self.worker.has_skill_ids)
        edges = dv.build_all_edges(self.onto)
        gap_ids = {e.id for e in traversal.cert_gap_edges(self.worker, self.onto, edges)}
        self.assertNotIn("certgap::EMP-001::S05", gap_ids)

    def test_uncorpused_skill_not_assessed(self):
        """S09 (Containers) has no corpus card => not assessable => never an eval case."""
        self.assertFalse(traversal.is_assessable("S09", self.onto))
        edges = dv.build_all_edges(self.onto)
        skills = {c.skill.id for c in build_eval_cases(self.onto, edges)}
        self.assertNotIn("S09", skills)


if __name__ == "__main__":
    unittest.main()
