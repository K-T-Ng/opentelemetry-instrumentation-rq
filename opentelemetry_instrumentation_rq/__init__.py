"""
Instrument `rq` to trace rq scheduled jobs.
"""

from datetime import datetime
from typing import Callable, Collection, Dict, Literal, Optional, Tuple

import rq.queue
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker
from wrapt import wrap_function_wrapper

from opentelemetry_instrumentation_rq import utils


def _instrument_perform_job(
    func: Callable, instance: Worker, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Worker.perform_job`
    - An outer trace instrumentation for knowing the total executation
        time for user defined task and RQ maintenance tasks
    - Ensure all the span data flushed before fork process exited
    """
    job: Optional[Job] = kwargs.get("job") or (
        args[0] if isinstance(args[0], Job) else None
    )
    queue: Optional[Queue] = kwargs.get("queue") or (
        args[1] if isinstance(args[1], Queue) else None
    )
    span_attributes = utils._get_general_attributes(job=job, queue=queue)
    response = utils._trace_instrument(
        func=func,
        span_name="perform_job",
        span_kind=trace.SpanKind.CONSUMER,
        span_attributes=span_attributes,
        span_context_carrier=job.meta,
        propagate=False,
        args=args,
        kwargs=kwargs,
    )
    trace.get_tracer_provider().force_flush()  # Force flush before fork exited
    return response


def _instrument_perform(
    func: Callable, instance: Job, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Job.perform`
    - An inner trace instrumentation for knowing the execution
        time and status for user defined task
    """
    job: Job = instance
    span_attributes = utils._get_general_attributes(job=job)
    response = utils._trace_instrument(
        func=func,
        span_name="perform",
        span_kind=trace.SpanKind.CLIENT,
        span_attributes=span_attributes,
        span_context_carrier=job.meta,
        propagate=False,
        args=args,
        kwargs=kwargs,
    )
    return response


def _instrument__enqueue_job(
    func: Callable, instance: Queue, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Queue._enqueue_job`
    - A trace instrumentation for knowing when the task
        is enqueued to Redis
    """
    job: Optional[Job] = kwargs.get("job") or (
        args[0] if isinstance(args[0], Job) else None
    )
    queue: Queue = instance
    span_attributes = utils._get_general_attributes(job=job, queue=queue)
    response = utils._trace_instrument(
        func=func,
        span_name="enqueue",
        span_kind=trace.SpanKind.PRODUCER,
        span_attributes=span_attributes,
        span_context_carrier=job.meta,
        propagate=True,
        args=args,
        kwargs=kwargs,
    )
    return response


def _instrument_schedule_job(
    func: Callable, instance: Queue, args: Tuple, kwargs: Dict
) -> Callable:
    """Tracing instrumentation for `Queue.schedule_job`
    - A trace instrumentation for knowing when the task
        is scheduled, handled by scheduler later
    """
    job: Optional[Job] = kwargs.get("job") or (
        args[0] if isinstance(args[0], Job) else None
    )
    queue: Queue = instance
    scheduled_time: Optional[datetime] = kwargs.get("datetime") or (
        args[1] if isinstance(args[1], datetime) else None
    )
    span_attributes = utils._get_general_attributes(job=job, queue=queue)
    span_attributes["schedule.time"] = (
        str(scheduled_time) if scheduled_time else "Unknown"
    )
    response = utils._trace_instrument(
        func=func,
        span_name="schedule",
        span_kind=trace.SpanKind.PRODUCER,
        span_attributes=span_attributes,
        span_context_carrier=job.meta,
        propagate=True,
        args=args,
        kwargs=kwargs,
    )
    return response


def _instrument_execute_callback_factory(
    callback_type: Literal["success_callback", "failure_callback", "stopped_callback"]
) -> Callable:
    """Factory for generate callback instrumentation wrapper"""

    def _instrument_execute_callback(
        func: Callable, instance: Job, args: Tuple, kwargs: Dict
    ) -> Callable:
        """Tracing instrumentation for `rq.job.Job.execute_*_callback
        - Including success, failure, stopped callback
        - An inner trace for knowing the execution time and status
            for user defined callback if provided
        """
        # Early retrun if no such callback
        # (The case that `job.*_callback` is None, user didn't provide callback)
        if not getattr(instance, callback_type):
            return

        job: Job = instance
        span_attributes = utils._get_general_attributes(job=job)
        response = utils._trace_instrument(
            func=func,
            span_name=callback_type,
            span_kind=trace.SpanKind.CLIENT,
            span_attributes=span_attributes,
            span_context_carrier=job.meta,
            propagate=False,
            args=args,
            kwargs=kwargs,
        )
        return response

    return _instrument_execute_callback


def _instrument_job_status_handler_factory(
    handler_type: Literal["handle_job_success", "handle_job_failure"]
) -> Callable:
    def _instrument_job_status_handler(
        func: Callable, instance: Job, args: Tuple, kwargs: Dict
    ):
        """Tracing instrumentation for `rq.worker.Worker.handle_job_*`
        - An inner trace instrumentation for knowing the executation
            time and status for RQ maintainence job (e.g. enqueue depenents when job success)
        """
        job: Optional[Job] = kwargs.get("job") or (
            args[0] if isinstance(args[0], Job) else None
        )
        queue: Optional[Queue] = kwargs.get("queue") or (
            args[1] if isinstance(args[1], Queue) else None
        )
        span_attributes = utils._get_general_attributes(job=job, queue=queue)
        response = utils._trace_instrument(
            func=func,
            span_name=handler_type,
            span_kind=trace.SpanKind.CLIENT,
            span_attributes=span_attributes,
            span_context_carrier=job.meta,
            propagate=False,
            args=args,
            kwargs=kwargs,
        )
        return response

    return _instrument_job_status_handler


class RQInstrumentor(BaseInstrumentor):
    """An instrumentor of rq"""

    def instrumentation_dependencies(self) -> Collection[str]:
        return ("rq >= 2.0.0",)

    def _instrument(self, **kwargs):
        # Instrumentation for task producer
        wrap_function_wrapper(
            "rq.queue", "Queue._enqueue_job", _instrument__enqueue_job
        )
        wrap_function_wrapper(
            "rq.queue", "Queue.schedule_job", _instrument_schedule_job
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

        # Instrumentation for task status handler
        wrap_function_wrapper(
            "rq.worker",
            "Worker.handle_job_success",
            _instrument_job_status_handler_factory("handle_job_success"),
        )
        wrap_function_wrapper(
            "rq.worker",
            "Worker.handle_job_failure",
            _instrument_job_status_handler_factory("handle_job_failure"),
        )

    def _uninstrument(self, **kwargs):
        unwrap(rq.worker.Worker, "handle_job_success")
        unwrap(rq.worker.Worker, "handle_job_failure")

        unwrap(rq.job.Job, "execute_success_callback")
        unwrap(rq.job.Job, "execute_failure_callback")
        unwrap(rq.job.Job, "execute_stopped_callback")

        unwrap(rq.worker.Worker, "perform_job")
        unwrap(rq.job.Job, "perform")

        unwrap(rq.queue.Queue, "schedule_job")
        unwrap(rq.queue.Queue, "_enqueue_job")
