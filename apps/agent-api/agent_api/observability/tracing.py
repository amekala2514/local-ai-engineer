"""OpenTelemetry tracing setup.

Exports spans to Tempo via OTLP/HTTP. Safe-by-default: if tracing is disabled
or the exporter can't reach Tempo, the app runs normally with no spans — never
let observability break the thing it observes.

Usage (at app startup):
    from agent_api.observability.tracing import setup_tracing
    setup_tracing(app)        # instruments FastAPI + wires the exporter

Elsewhere, to create manual spans:
    from agent_api.observability.tracing import get_tracer
    tracer = get_tracer()
    with tracer.start_as_current_span("hyde_generation") as span:
        span.set_attribute("model", model_name)
        ...
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from agent_api.settings import settings

_SERVICE_NAME = "agent-api"
_initialized = False


def setup_tracing(app=None) -> None:
    """Initialize the tracer provider + OTLP exporter, and instrument FastAPI.

    No-op if tracing_enabled is False. Idempotent. Exporter failures (Tempo
    down) are swallowed by the BatchSpanProcessor — the app keeps running.
    """
    global _initialized
    if _initialized or not settings.tracing_enabled:
        return

    resource = Resource.create({"service.name": _SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=settings.otlp_traces_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            pass  # auto-instrumentation is a bonus; never block startup

    _initialized = True


def get_tracer():
    """Return a tracer. If tracing was never set up, this returns a no-op
    tracer (OTel's default), so manual spans are harmless when disabled."""
    return trace.get_tracer(_SERVICE_NAME)
