"""
Instrument `rq` to trace rq scheduled jobs.
"""

from typing import Collection

import rq.queue
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.semconv._incubating.attributes.messaging_attributes import (
    MessagingOperationTypeValues,
)
from wrapt import wrap_function_wrapper

from opentelemetry_instrumentation_rq import utils
from opentelemetry_instrumentation_rq.instrumentor import TraceInstrumentWrapper


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
                operation_type=MessagingOperationTypeValues.SEND.value,
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
                operation_type=MessagingOperationTypeValues.CREATE.value,
                operation_name="schedule",
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
            "Queue.setup_dependencies",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.PRODUCER,
                operation_type=MessagingOperationTypeValues.CREATE.value,
                operation_name="setup dependencies",
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
                operation_type=MessagingOperationTypeValues.PROCESS.value,
                operation_name="consume",
                should_propagate=True,
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
                operation_type=MessagingOperationTypeValues.PROCESS.value,
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
                operation_type=MessagingOperationTypeValues.PROCESS.value,
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
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.CLIENT,
                operation_type=MessagingOperationTypeValues.PROCESS.value,
                operation_name="failure_callback",
                should_propagate=False,
                should_flush=False,
                instance_info=utils.get_argument_info(utils.RQElementName.JOB),
                argument_info_list=[],
            ),
        )
        wrap_function_wrapper(
            "rq.job",
            "Job.execute_stopped_callback",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.CLIENT,
                operation_type=MessagingOperationTypeValues.PROCESS.value,
                operation_name="stopped_callback",
                should_propagate=False,
                should_flush=False,
                instance_info=utils.get_argument_info(utils.RQElementName.JOB),
                argument_info_list=[],
            ),
        )

        # Instrumentation for task status handler
        wrap_function_wrapper(
            "rq.worker",
            "Worker.handle_job_success",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.CLIENT,
                operation_type=MessagingOperationTypeValues.PROCESS.value,
                operation_name="handle_job_success",
                should_propagate=False,
                should_flush=False,
                instance_info=utils.get_instance_info(utils.RQElementName.WORKER),
                argument_info_list=[
                    utils.get_argument_info(utils.RQElementName.JOB),
                    utils.get_argument_info(utils.RQElementName.QUEUE),
                ],
            ),
        )
        wrap_function_wrapper(
            "rq.worker",
            "Worker.handle_job_failure",
            TraceInstrumentWrapper(
                span_kind=trace.SpanKind.CLIENT,
                operation_type=MessagingOperationTypeValues.PROCESS.value,
                operation_name="handle_job_failure",
                should_propagate=False,
                should_flush=False,
                instance_info=utils.get_argument_info(utils.RQElementName.WORKER),
                argument_info_list=[
                    utils.get_argument_info(utils.RQElementName.JOB),
                    utils.get_argument_info(utils.RQElementName.QUEUE),
                ],
            ),
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
