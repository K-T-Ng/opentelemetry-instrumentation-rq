"""
Instrument `rq` to trace rq scheduled jobs.
"""

from typing import Callable, Collection, Dict, Tuple

import rq.queue
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker
from wrapt import wrap_function_wrapper


def _instrument_perform_job(
    func: Callable, instance: Worker, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Worker.perform_job`"""
    worker: Worker = instance
    job: Job = args[0]
    queue: Queue = args[1]

    attributes: Dict = {
        "worker.name": worker.name,
        "job.id": job.id,
        "job.func_name": job.func_name,
        "queue.name": queue.name,
    }
    ctx: trace.Context = TraceContextTextMapPropagator().extract(carrier=job.meta)

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        name="enqueue", kind=trace.SpanKind.CONSUMER, context=ctx
    ) as span:
        if span.is_recording():
            span.set_attributes(attributes=attributes)

        response = func(*args, **kwargs)

    # Force flush due to job runs in subprocess
    trace.get_tracer_provider().force_flush()

    return response


def _instrument__enqueue_job(
    func: Callable, instance: Queue, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Queue._enqueue_job`"""
    job: Job = args[0]
    queue: Queue = instance

    attributes: Dict = {
        "job.id": job.id,
        "job.func_name": job.func_name,
        "queue.name": queue.name,
    }

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        name="enqueue", kind=trace.SpanKind.PRODUCER
    ) as span:
        if span.is_recording():
            span.set_attributes(attributes=attributes)
            TraceContextTextMapPropagator().inject(job.meta)
        response = func(*args, **kwargs)

    return response


class RQInstrumentor(BaseInstrumentor):
    """An instrumentor of rq"""

    def instrumentation_dependencies(self) -> Collection[str]:
        return ("rq >= 2.0.0",)

    def _instrument(self, **kwargs):
        wrap_function_wrapper(
            "rq.queue", "Queue._enqueue_job", _instrument__enqueue_job
        )
        wrap_function_wrapper(
            "rq.worker", "Worker.perform_job", _instrument_perform_job
        )

    def _uninstrument(self, **kwargs):
        unwrap(rq.worker.Worker, "perform_job")
        unwrap(rq.queue.Queue, "_enqueue_job")
