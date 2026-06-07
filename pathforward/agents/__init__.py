"""Agents layer: the code-driven Generator->Verifier loop (the signature reasoning
organ), the LLM client abstraction, the numeric checker, and cold-start calibration.

Per the red-team: the loop is plain SDK-shaped code (a `respond()` call chained by
`previous_response_id`), NOT classic connected agents — so the orchestrator owns the
structured payload and citations propagate deterministically.
"""
