"""PathForward eval + red-team harness.

Two deterministic scorecards over the SAME loop the product runs:
  - groundedness/spine eval: does the agent produce grounded, spine-intact credentials on legit cases?
  - adversarial red-team: does the refuse-to-bluff defense hold under attack (Attack Success Rate)?

Pass/fail is decided in CODE (never an LLM judge) — that is what makes the safety scorecard credible.
The cases are derived from the synthetic ontology so the benchmark is reproducible run to run.
"""
