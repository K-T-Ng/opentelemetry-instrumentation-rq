"""
Instrument `rq` to trace rq scheduled jobs.
"""

from typing import Callable, Collection, Dict, Literal, Optional, Tuple

import rq.queue
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.semconv._incubating.attributes.messaging_attributes import (
    MessagingOperationTypeValues,
)
from rq.job import Job
from rq.queue import Queue
from wrapt import wrap_function_wrapper

from opentelemetry_instrumentation_rq import utils
from opentelemetry_instrumentation_rq.instrumentor import TraceInstrumentWrapper


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
            "rq.queue",
            "Queue._enqueue_job",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.PRODUCER,
                operation_type=MessagingOperationTypeValues.SEND,
                operation_name="publish",
                should_propagate=True,
                should_flush=False,
                instance_info=utils.get_instance_info(utils.RQElementName.QUEUE),
                argument_info_list=[
                    utils.get_argument_info(utils.RQElementName.JOB, 0)
                ],
            ),
        )

        wrap_function_wrapper(
            "rq.queue",
            "Queue.schedule_job",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.PRODUCER,
                operation_type=MessagingOperationTypeValues.CREATE,
                operation_name="schedule",
                should_propagate=True,
                should_flush=False,
                instance_info=utils.get_instance_info(utils.RQElementName.QUEUE),
                argument_info_list=[
                    utils.get_argument_info(utils.RQElementName.JOB, 0)
                ],
            ),
        )

        # Instrumentation for task consumer
        wrap_function_wrapper(
            "rq.worker",
            "Worker.perform_job",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.CONSUMER,
                operation_type=MessagingOperationTypeValues.PROCESS,
                operation_name="consume",
                should_propagate=False,
                should_flush=True,
                instance_info=utils.get_instance_info(utils.RQElementName.WORKER),
                argument_info_list=[
                    utils.get_argument_info(utils.RQElementName.JOB, 0),
                    utils.get_argument_info(utils.RQElementName.QUEUE, 1),
                ],
            ),
        )

        wrap_function_wrapper(
            "rq.job",
            "Job.perform",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.CLIENT,
                operation_type=MessagingOperationTypeValues.PROCESS,
                operation_name="perform",
                should_propagate=False,
                should_flush=False,
                instance_info=utils.get_instance_info(utils.RQElementName.JOB),
                argument_info_list=[],
            ),
        )

        wrap_function_wrapper(
            "rq.job",
            "Job.execute_success_callback",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.CLIENT,
                operation_type=MessagingOperationTypeValues.PROCESS,
                operation_name="success_callback",
                should_propagate=False,
                should_flush=False,
                instance_info=utils.get_instance_info(utils.RQElementName.JOB),
                argument_info_list=[],
            ),
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
