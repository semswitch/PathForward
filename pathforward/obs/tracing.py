"""Optional OpenTelemetry tracing for the assessment loop.

OFF by default: `span()` is a no-op until `configure_tracing(...)` is called, so the zero-dep offline
core and all offline tests are unaffected (same optional-layer pattern as Fake vs Foundry client).
When configured, spans export to the Console and/or Azure Monitor (App Insights / Foundry Tracing tab).

The module normally keeps its OWN TracerProvider, so it composes cleanly and is easy to reconfigure in
tests via an in-memory exporter. Azure Monitor export is the exception: that exporter reads the global
provider resource during export, so `configure_tracing(..., azure_connection_string=...)` installs this
provider globally when no real global provider has been installed yet.
"""
from __future__ import annotations

import contextlib
from typing import Any, Iterator, Optional

_PROVIDER = None
_TRACER = None
_CONFIGURED = False


def configure_tracing(*, console: bool = False, azure_connection_string: Optional[str] = None,
                      exporter: Any = None, service_name: str = "pathforward") -> bool:
    """Activate tracing. Returns True if a tracer is live. Safe if OpenTelemetry isn't installed
    (returns False). `exporter` is an extra SpanExporter (used by tests, e.g. InMemorySpanExporter)."""
    global _PROVIDER, _TRACER, _CONFIGURED
    if _CONFIGURED and _TRACER is not None:
        return True
    _CONFIGURED = True
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (BatchSpanProcessor, ConsoleSpanExporter,
                                                    SimpleSpanProcessor)
    except Exception:  # noqa: BLE001 - OpenTelemetry not installed -> stay a no-op
        _TRACER = None
        return False

    from opentelemetry import trace as otel_trace

    global_provider = otel_trace.get_tracer_provider()
    using_global_provider = (
        global_provider.__class__.__name__ != "ProxyTracerProvider"
        and hasattr(global_provider, "add_span_processor")
    )
    provider = (global_provider if using_global_provider else
                TracerProvider(resource=Resource.create({"service.name": service_name})))
    if console:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    if azure_connection_string:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
            if not using_global_provider and global_provider.__class__.__name__ == "ProxyTracerProvider":
                otel_trace.set_tracer_provider(provider)
            provider.add_span_processor(BatchSpanProcessor(
                AzureMonitorTraceExporter(connection_string=azure_connection_string)))
        except Exception as exc:  # noqa: BLE001 - degrade: Azure export unavailable, others still work
            print(f"(Azure Monitor trace export unavailable: {type(exc).__name__})")
    _PROVIDER = provider
    _TRACER = provider.get_tracer("pathforward")
    return True


def flush() -> None:
    """Force-export any buffered spans (call before a short-lived process exits)."""
    if _PROVIDER is not None:
        try:
            _PROVIDER.force_flush()
        except Exception:  # noqa: BLE001
            pass


def reset_tracing() -> None:
    """Tear down the tracer (tests)."""
    global _PROVIDER, _TRACER, _CONFIGURED
    if _PROVIDER is not None:
        try:
            _PROVIDER.shutdown()
        except Exception:  # noqa: BLE001
            pass
    _PROVIDER = _TRACER = None
    _CONFIGURED = False


class _NoopSpan:
    def set(self, **attrs: Any) -> None: ...
    def event(self, name: str, **attrs: Any) -> None: ...


class _RealSpan:
    def __init__(self, span: Any):
        self._span = span

    def set(self, **attrs: Any) -> None:
        for k, v in attrs.items():
            if v is not None:
                self._span.set_attribute(k, v)

    def event(self, name: str, **attrs: Any) -> None:
        self._span.add_event(name, {k: v for k, v in attrs.items() if v is not None})


@contextlib.contextmanager
def span(name: str, **attrs: Any) -> Iterator[Any]:
    """Open a span (parent of nested spans) if tracing is live; otherwise a no-op. The yielded handle
    has `.set(**attrs)` and `.event(name, **attrs)` helpers."""
    if _TRACER is None:
        yield _NoopSpan()
        return
    with _TRACER.start_as_current_span(name) as s:
        for k, v in attrs.items():
            if v is not None:
                s.set_attribute(k, v)
        yield _RealSpan(s)
