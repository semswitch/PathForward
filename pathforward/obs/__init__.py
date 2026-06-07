"""Observability — optional OpenTelemetry tracing for the assessment loop.

Tracing is OFF by default: `span()` is a no-op unless `configure_tracing(...)` is called, so the
zero-dep offline core and every offline test run untouched (same pattern as Fake vs Foundry client).
"""
