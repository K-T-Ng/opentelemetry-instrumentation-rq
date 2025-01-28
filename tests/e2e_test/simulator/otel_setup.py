"""Initalize OpenTelemetry instrumentation for logs/tracing"""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from opentelemetry_instrumentation_rq import RQInstrumentor


def init_traces(
    resource: Resource, otlp_http_endpoint: str, enable_console_exporter: bool = False
):
    """Initalize traces instrumentation"""
    provider = TracerProvider(resource=resource)

    if enable_console_exporter:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    otlp_exporter = OTLPSpanExporter(endpoint=f"{otlp_http_endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)


def initialize(
    otlp_http_endpoint: str,
    enable_console_exporter: bool = False,
):
    """Initalize OpenTelemetry instrumentation"""
    resource = Resource(
        attributes={
            "service.name": "rq-instrumentation",
            "service.version": "0.1.0",
        }
    )
    init_traces(resource, otlp_http_endpoint, enable_console_exporter)
    RQInstrumentor().instrument()
