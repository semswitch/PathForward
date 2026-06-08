# Responsible AI — PathForward

One page, cross-linked to the controls that enforce each claim. (Red-team finding C5.)

## Intended use
A **demonstration** of grounded, multi-agent reskilling support: skill-adjacency mapping,
capacity-aware study planning, and grounded competency *verification* that produces a
citation-backed credential. Built for the Agents League hackathon.

## Out of scope (do not use for)
- **Real hiring, firing, promotion, licensure, or compensation decisions.**
- Any decision about a real person. All subjects are synthetic.
- A substitute for an accredited certification body.

## Limitations (stated plainly)
- **Synthetic data only.** The ontology, learner responses, and corpus are fabricated.
- **Cold-start calibration, not population IRT.** Item difficulty/discrimination are *estimated*
  from a synthetic response set and labelled `estimated (cold-start)` — they are not validated
  psychometrics. The Evidence Gate's filtering is the real quality ratchet, not the statistics.
- **Grounding scope.** Answers and items are grounded only in the supplied synthetic corpus; the
  system abstains rather than answer outside it.
- The LLM is never trusted for the assessment gate or for arithmetic — those are computed in code.

## Human oversight
- **Fail-closed credential gate:** below confidence / on loop exhaustion the system **abstains and
  escalates** instead of certifying. (`pathforward/agents/loop.py`, `credential/mint.py`.)
- **Human-in-the-loop mint:** credentials are issued only through an approval-gated MCP endpoint
  (`require_approval: "always"`). A human approves every issuance.
- **Causal-spine integrity:** the credential must cite the exact `CertGap` edge that drove the
  assessment, or minting raises `CredentialIntegrityError`.

## Safety & fairness controls (runtime)
- **Groundedness / faithfulness** evaluated via the Foundry eval SDK (CI gate).
- **Adversarial red-team** (PyRIT) against the student-as-attacker / answer-leakage threat; an
  on-screen ASR scorecard.
- **Content Safety + Prompt Shields** on inputs and tool outputs.
- **Subgroup fairness check** across synthetic cohorts — guards against systematically
  over-certifying the very (synthetic) workers the system is meant to help.
- **Provenance + validity-time** on every derived assertion; a live-vs-mirror source badge so a
  judge can tell inferred-now from served-from-cache.

## Transparency
Users interact with AI agents. The Glass-Box graph, the visible reject→regenerate Arena, and the
citation panel make the reasoning and its sources inspectable rather than opaque.
