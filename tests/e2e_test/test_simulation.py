"""End to end testing
    - Acting producer to produce tasks under various scenarios
    - Getting produced spans (both producer and workers) from Jaeger
    - Compare actual and expected spans
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List

import redis
import requests
from opentelemetry import trace
from opentelemetry.semconv._incubating.attributes import messaging_attributes
from opentelemetry.semconv._incubating.attributes.messaging_attributes import (
    MessagingOperationTypeValues,
)
from opentelemetry.test.test_base import TestBase
from pydantic import BaseModel
from rq import Callback, Queue
from rq.command import send_stop_job_command
from rq.job import Dependency

from opentelemetry_instrumentation_rq import rq_attributes
from tests import tasks
from tests.e2e_test.model import V1Span, V1TraceData
from tests.e2e_test.simulator.otel_setup import initialize

QUEUE_NAME = "test_queue"
WORKER_NAME = "test_worker"


class ExpectSpan(BaseModel):
    """Expect Span model, for checking important attributes for a span"""

    name: str
    kind: trace.SpanKind
    status: trace.StatusCode
    attributes: Dict
    links_count: int = 0


class TestCase(BaseModel):
    """Test case model, with a callable producer_call and expected span list attributes"""

    __test__ = False

    name: str
    description: str
    producer_call: Callable[[Queue], None]
    expect_span_list: List[ExpectSpan]


def get_basic_usage_task_normal_case() -> TestCase:  # pylint: disable=line-too-long
    """Generate test case for Basic usage: Task success normally"""

    def enqueue(queue: Queue):
        queue.enqueue(tasks.task_normal)

    return TestCase(
        name="Basic usage: Task normal",
        description="Basic usage, with task without delay",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_success {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_success",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
        ],
    )


def get_basic_usage_task_exception_case() -> TestCase:  # pylint: disable=line-too-long
    """Generate test case for Basic usage: Task raise an exception"""

    def enqueue(queue: Queue):
        queue.enqueue(tasks.task_exception)

    return TestCase(
        name="Basic usage: Task exception",
        description="Basic usage, with task rasing exception",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.ERROR,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name=f"handle_job_failure {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_failure",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
        ],
    )


def get_callback_usage_task_normal_callback_normal() -> (
    TestCase
):  # pylint: disable=line-too-long
    """Generate test case for Callback usage:
    - Task finished successfully
    - Success callback finished successfully
    """

    def enqueue(queue: Queue):
        queue.enqueue(tasks.task_normal, on_success=Callback(tasks.success_callback))

    return TestCase(
        name="Callback usage: Both Task and Callback are normal",
        description="Normal task with a normal callback function",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="success_callback",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "success_callback",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_success {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_success",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
        ],
    )


def get_callback_usage_task_normal_callback_exception() -> (
    TestCase
):  # pylint: disable=line-too-long
    """Generate test case for Callback usage:
    - Task finished successfully
    - Success callback finished with exception
    - Failure callback finished successfully
    """

    def enqueue(queue: Queue):
        queue.enqueue(
            tasks.task_normal,
            on_success=Callback(tasks.success_callback_exception),
            on_failure=Callback(tasks.failure_callback),
        )

    return TestCase(
        name="Callback usage: Task Normal and Callback Exception",
        description="Normal task with an error callback function",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="success_callback",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.ERROR,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "success_callback",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="failure_callback",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "failure_callback",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_failure {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_failure",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
        ],
    )


def get_callback_usage_task_exception_callback_success() -> (
    TestCase
):  # pylint: disable=line-too-long
    """Generate test case for Callback usage:
    - Task finished with exception
    - Failure callback finished successfully
    """

    def enqueue(queue: Queue):
        queue.enqueue(tasks.task_exception, on_failure=Callback(tasks.failure_callback))

    return TestCase(
        name="Callback usage: Task Exception and Callback normal",
        description="Exception task with a normal callback function",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.ERROR,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name="failure_callback",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "failure_callback",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name=f"handle_job_failure {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_failure",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
        ],
    )


def get_callback_usage_task_exception_callback_failure() -> (
    TestCase
):  # pylint: disable=line-too-long
    """Generate test case for Callback usage:
    - Task finished with exception
    - Success callback finished with exception
    """

    def enqueue(queue: Queue):
        queue.enqueue(
            tasks.task_exception, on_failure=Callback(tasks.failure_callback_exception)
        )

    return TestCase(
        name="Callback usage: Both task and callback are rasing expection",
        description="Exception task with an exception callback function",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.ERROR,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name="failure_callback",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.ERROR,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "failure_callback",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
            ExpectSpan(
                name=f"handle_job_failure {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_failure",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_exception",
                },
            ),
        ],
    )


def get_callback_usage_stopped_callback() -> TestCase:  # pylint: disable=line-too-long
    """Generate test case for Callback usage:
    - Task terminated by stop command
    - Stopped callback finished successfully
    """

    def enqueue(queue: Queue):
        job = queue.enqueue(
            tasks.task_unstopped, on_stopped=Callback(tasks.stopped_callback)
        )
        time.sleep(1)
        send_stop_job_command(queue.connection, job.id)

    return TestCase(
        name="Callback usage: Stopped callback",
        description="Terminate job using `send_stop_job_command`, trigger stopped callback",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_unstopped",
                },
            ),
            ExpectSpan(
                name="stopped_callback",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "stopped_callback",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_unstopped",
                },
            ),
            ExpectSpan(
                name=f"handle_job_failure {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_failure",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_unstopped",
                },
            ),
        ],
    )


def get_scheduler_usage_enqueue_in() -> TestCase:  # pylint: disable=line-too-long
    """Generate test case for Scheduler usage: using enqueue_in method"""

    def enqueue(queue: Queue):
        queue.enqueue_in(time_delta=timedelta(seconds=3), func=tasks.task_normal)
        time.sleep(3)

    return TestCase(
        name="Scheduler usage: enqueue_in",
        description="Schedule task using Queue.enqueue_in",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"schedule {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.CREATE.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "schedule",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_success {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_success",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
        ],
    )


def get_scheduler_usage_enqueue_at() -> TestCase:  # pylint: disable=line-too-long
    """Generate test case for Scheduler usage: using enqueue_at method"""

    def enqueue(queue: Queue):
        enqueue_at = datetime.now() + timedelta(seconds=3)
        queue.enqueue_at(datetime=enqueue_at, f=tasks.task_normal)
        time.sleep(3)

    return TestCase(
        name="Scheduler usage: enqueue_at",
        description="Schedule task using Queue.enqueue_at",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"schedule {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.CREATE.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "schedule",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_success {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_success",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
        ],
    )


def get_span_link_usage_job_dependencies() -> TestCase:  # pylint: disable=line-too-long
    """Generate test case for Span link usage: linking job dependencies"""

    def enqueue(queue: Queue):
        tracer = trace.get_tracer("opentelemetry_instrumentation_rq.instrumentor")

        # Since enqueuing both parent and child job will create two traces
        # We would like to wrapped it as one, for convenience to adopt e2e test
        with tracer.start_as_current_span(name="wrapped_span") as span:
            parent = queue.enqueue(tasks.task_normal)

            # Avoid the order of span start timestamp in an undetermined order
            # TODO: Consider to rewrite the expected span list using a tree rather than list
            time.sleep(1)
            parent_dep = Dependency(jobs=[parent])
            queue.enqueue(tasks.task_normal, depends_on=parent_dep)

            span.set_status(trace.Status(trace.StatusCode.OK))

    return TestCase(
        name="Span link usage: depends_on",
        description="Span link from child to parent job",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name="wrapped_span",
                kind=trace.SpanKind.INTERNAL,
                status=trace.StatusCode.OK,
                attributes={},
            ),
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_success {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_success",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"setup dependencies {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.CREATE.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "setup dependencies",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
                links_count=1,
            ),
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name="perform",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_success {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                status=trace.StatusCode.OK,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_success",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
        ],
    )


TEST_CASES: List[TestCase] = [
    get_basic_usage_task_normal_case(),
    get_basic_usage_task_exception_case(),
    get_callback_usage_task_normal_callback_normal(),
    get_callback_usage_task_normal_callback_exception(),
    get_callback_usage_task_exception_callback_success(),
    get_callback_usage_task_exception_callback_failure(),
    get_callback_usage_stopped_callback(),
    get_scheduler_usage_enqueue_in(),
    get_scheduler_usage_enqueue_at(),
    get_span_link_usage_job_dependencies(),
]


class TestExpectSpanInfo(TestBase):

    def setUp(self):
        """Setup Fake redis, Queue and Worker"""
        initialize(otlp_http_endpoint="http://localhost:4318")

        self.redis = redis.Redis(host="localhost", port=6379)
        self.queue = Queue(name=QUEUE_NAME, connection=self.redis)

    def get_spans(self) -> List[List[V1Span]]:

        now = datetime.now(timezone.utc)
        prev = now - timedelta(days=1)

        response = requests.get(
            url="http://localhost:16686/api/v3/traces",
            params={
                "query.service_name": "rq-instrumentation",
                "query.start_time_min": prev.isoformat(),
                "query.start_time_max": now.isoformat(),
            },
        )

        response_json = response.json()
        trace_data = V1TraceData.model_validate(response_json.get("result"))
        response_spans = trace_data.resource_spans

        def get_span_unix(span: V1Span):
            return span.start_time_unix_nano

        response_spans.sort(
            key=lambda rs: get_span_unix(
                min(rs.scope_spans[0].spans, key=get_span_unix)
            )
        )

        span_datas: List[List[V1Span]] = []
        for rs in response_spans:
            spans = rs.scope_spans[0].spans
            spans.sort(key=lambda span: span.start_time_unix_nano)
            span_datas.append(spans)

        return span_datas

    def test_simulation(self):
        # Produce Jobs
        for test_case in TEST_CASES:
            test_case.producer_call(self.queue)

        # Get spans from Jaeger
        time.sleep(15)
        span_datas = self.get_spans()

        # Check spans
        for test_case, actual_spans in zip(TEST_CASES, span_datas):
            expect_spans = test_case.expect_span_list

            self.assertEqual(
                len(expect_spans),
                len(actual_spans),
                msg="Failed test case: {}, expect number of spans: {}, got {}".format(
                    test_case.name, len(expect_spans), len(actual_spans)
                ),
            )
            for expect, actual in zip(expect_spans, actual_spans):
                self.assertEqual(
                    expect.name,
                    actual.name,
                    msg="Failed test case: {}, expect span name: {}, got: {}".format(
                        test_case.name, expect.name, actual.name
                    ),
                )
                self.assertEqual(
                    expect.kind.value,
                    actual.kind - 1,
                    msg="Failed test case: {}, expect span kind: {}, got: {}".format(
                        test_case.name, expect.kind, actual.kind
                    ),
                )
                self.assertEqual(
                    expect.status.value,
                    actual.status.code,
                    msg="Failed test case: {}, expect span status: {}, got: {}".format(
                        test_case.name, expect.status, actual.status
                    ),
                )
                self.assertLessEqual(
                    expect.attributes.items(),
                    {
                        attr.key: attr.value.get("stringValue", None)
                        for attr in actual.attributes
                    }.items(),
                    msg="Failed test case: {}, expect span contains attributes: {}, got: {}".format(
                        test_case.name, expect.attributes, actual.attributes
                    ),
                )
                self.assertEqual(
                    expect.links_count,
                    len(actual.links),
                    msg="Failed test case: {}, expect span has {} links, got {}".format(
                        test_case.name, expect.links_count, len(actual.links)
                    ),
                )
