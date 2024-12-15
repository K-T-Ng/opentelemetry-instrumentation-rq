"""Utils for building instrumentation data"""

from typing import Callable, Dict, Optional

from opentelemetry import trace
from opentelemetry.trace import Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from rq.job import Job
from rq.queue import Queue


def _set_span_attributes(span: Span, attributes: Dict):
    """Add attributes to span if it is recording"""
    if span.is_recording():
        span.set_attributes(attributes=attributes)


def _set_span_error_status(span: Span, exception: Exception):
    """Set Error status to span and record exception if it is recording"""
    if span.is_recording():
        span.set_status(trace.Status(trace.StatusCode.ERROR))
        span.record_exception(exception)


def _trace_instrument(
    func: Callable,
    span_name: str,
    span_kind: trace.SpanKind,
    span_attributes: Dict[str, str],
    span_context_carrier: Dict,
    propagate: bool,
    args: tuple,
    kwargs: Dict,
):
    """Tracing instrumentation"""
    tracer = trace.get_tracer(__name__)
    parent_context: trace.Context = TraceContextTextMapPropagator().extract(
        carrier=span_context_carrier
    )
    span_context_manager = tracer.start_as_current_span(
        name=span_name, kind=span_kind, context=parent_context
    )

    span = span_context_manager.__enter__()
    _set_span_attributes(span, span_attributes)
    if propagate:
        TraceContextTextMapPropagator().inject(span_context_carrier)

    try:
        response = func(*args, **kwargs)
    except Exception as exc:
        _set_span_error_status(span, exc)
        raise exc
    finally:
        span_context_manager.__exit__(None, None, None)

    return response


def _get_general_attributes(
    job: Optional[Job] = None,
    queue: Optional[Queue] = None,
) -> Dict:
    attributes: Dict = {}

    if job:
        attributes["job.id"] = job.id
        attributes["job.func_name"] = job.func_name
        if job.worker_name:
            attributes["worker.name"] = job.worker_name

    if queue:
        attributes["queue.name"] = queue.name

    return attributes
