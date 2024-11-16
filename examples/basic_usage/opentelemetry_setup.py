"""Initalize OpenTelemetry instrumentation for logs/tracing"""

import logging
from typing import Tuple

from opentelemetry import _logs, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
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


def init_logs(
    resource: Resource,
    otlp_http_endpoint: str,
    logger_names: Tuple[str],
    enable_console_exporter: bool = False,
):
    """Initialize logs instrumentation"""
    provider = LoggerProvider(resource=resource)

    if enable_console_exporter:
        console_exporter = ConsoleLogExporter()
        provider.add_log_record_processor(BatchLogRecordProcessor(console_exporter))

    otlp_exporter = OTLPLogExporter(endpoint=f"{otlp_http_endpoint}/v1/logs")
    provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))

    _logs.set_logger_provider(provider)

    handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
    for logger_name in logger_names:
        logging.getLogger(logger_name).addHandler(handler)


def initialize(
    otlp_http_endpoint: str,
    logger_names: Tuple[str],
    enable_console_exporter: bool = False,
):
    """Initalize OpenTelemetry instrumentation"""
    resource = Resource(
        attributes={
            "service.name": "rq-instrumentation-basic-usage",
            "service.version": "0.1.0",
        }
    )
    init_logs(resource, otlp_http_endpoint, logger_names, enable_console_exporter)
    init_traces(resource, otlp_http_endpoint, enable_console_exporter)
    RQInstrumentor().instrument()
