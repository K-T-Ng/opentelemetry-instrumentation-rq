"""Utils for building instrumentation data"""

from typing import Dict, Optional

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


def _inject_context_to_job_meta(span: Span, job: Job):
    """Inject current context to job meta"""
    if span.is_recording():
        TraceContextTextMapPropagator().inject(job.meta)


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
