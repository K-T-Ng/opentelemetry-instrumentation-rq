"""
Instrument `rq` to trace rq scheduled jobs.
"""

from typing import Callable, Collection, Dict, Literal, Tuple

import rq.queue
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker
from wrapt import wrap_function_wrapper

from opentelemetry_instrumentation_rq import utils


def _instrument_perform_job(
    func: Callable, instance: Worker, args: Tuple, kwargs: Dict
) -> Callable:
    """Ensure all tracing data force flusted before exited `Worker.perform_job`"""
    response = func(*args, **kwargs)
    trace.get_tracer_provider().force_flush()
    return response


def _instrument_perform(
    func: Callable, instance: Job, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Job.perform"""
    job: Job = instance
    attributes = utils._get_general_attributes(job=job)

    tracer = trace.get_tracer(__name__)
    ctx: trace.Context = TraceContextTextMapPropagator().extract(carrier=job.meta)

    span_context_manager = tracer.start_as_current_span(
        name="perform", kind=trace.SpanKind.CONSUMER, context=ctx
    )

    span = span_context_manager.__enter__()
    utils._set_span_attributes(span, attributes)
    try:
        response = func(*args, **kwargs)
    except Exception as exc:
        utils._set_span_error_status(span, exc)
        raise exc
    finally:
        span_context_manager.__exit__(None, None, None)

    return response


def _instrument__enqueue_job(
    func: Callable, instance: Queue, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Queue._enqueue_job`"""
    job: Job = args[0]
    queue: Queue = instance
    attributes = utils._get_general_attributes(job=job, queue=queue)

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        name="enqueue", kind=trace.SpanKind.PRODUCER
    ) as span:
        utils._set_span_attributes(span, attributes)
        utils._inject_context_to_job_meta(span, job)
        response = func(*args, **kwargs)

    return response


def _instrument_execute_callback_factory(
    callback_type: Literal["success_callback", "failure_callback", "stopped_callback"]
) -> Callable:
    """Factory for generate callback instrumentation wrapper"""

    def _instrument_execute_callback(
        func: Callable, instance: Job, args: Tuple, kwargs: Dict
    ) -> Callable:
        """Tracing instrumentation for `rq.job.Job.execute_*_callback"""
        # Early retrun if no such callback
        # (The case that `job.*_callback` is None)
        if not getattr(instance, callback_type):
            return

        job: Job = instance
        attributes = utils._get_general_attributes(job=job)

        tracer = trace.get_tracer(__name__)
        ctx: trace.Context = TraceContextTextMapPropagator().extract(carrier=job.meta)

        span_context_manager = tracer.start_as_current_span(
            name=callback_type, context=ctx
        )

        span = span_context_manager.__enter__()
        utils._set_span_attributes(span, attributes)
        try:
            response = func(*args, **kwargs)
        except Exception as exc:
            utils._set_span_error_status(span, exc)
            raise exc
        finally:
            span_context_manager.__exit__(None, None, None)

        return response

    return _instrument_execute_callback


class RQInstrumentor(BaseInstrumentor):
    """An instrumentor of rq"""

    def instrumentation_dependencies(self) -> Collection[str]:
        return ("rq >= 2.0.0",)

    def _instrument(self, **kwargs):
        # Instrumentation for task producer
        wrap_function_wrapper(
            "rq.queue", "Queue._enqueue_job", _instrument__enqueue_job
        )

        # Instrumentation for task consumer
        wrap_function_wrapper(
            "rq.worker", "Worker.perform_job", _instrument_perform_job
        )
        wrap_function_wrapper(
            "rq.job",
            "Job.perform",
            _instrument_perform,
        )

        # Instrumentation for task callback
        wrap_function_wrapper(
            "rq.job",
            "Job.execute_success_callback",
            _instrument_execute_callback_factory("success_callback"),
        )
        wrap_function_wrapper(
            "rq.job",
            "Job.execute_failure_callback",
            _instrument_execute_callback_factory("failure_callback"),
        )
        wrap_function_wrapper(
            "rq.job",
            "Job.execute_stopped_callback",
            _instrument_execute_callback_factory("stopped_callback"),
        )

    def _uninstrument(self, **kwargs):
        unwrap(rq.job.Job, "execute_success_callback")
        unwrap(rq.job.Job, "execute_failure_callback")
        unwrap(rq.job.Job, "execute_stopped_callback")

        unwrap(rq.worker.Worker, "perform_job")
        unwrap(rq.job.Job, "perform")
        unwrap(rq.queue.Queue, "_enqueue_job")
