"""Tests for instrumentation for job callbacks"""

import time
from typing import List

import fakeredis
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from redis import Redis
from rq.command import send_stop_job_command
from rq.job import Callback
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import RQInstrumentor
from tests import tasks


def _send_stop_job_command_with_delay(redis_connection: Redis, job_id: str, delay: int):
    """Helper function for send stop command after sleep delay seconds"""
    time.sleep(delay)
    send_stop_job_command(redis_connection, job_id)


class TestJobCallback(TestBase):
    """Test cases for instruemntation for only enqueue and perform

    - Job success, success callback OK
    - Job success, success callback ERROR, failure callback OK
    - Job success, success callback ERROR, failure callback ERROR
    - Job failure, failure callback OK
    - Job failure, failure callback ERROR

    The following are TODO (We want to test those cases using multiple processes, need some scripting)
    - Job stopped, stopped callback OK
    - Job stopped, stopped callback ERROR, failure callback OK
    - Job stopped, stopped callback ERROR, failure callbakc ERROR
    """

    def setUp(self):
        """Setup before testing
        - Setup tracer from opentelemetry.test.test_base.TestBase
        - Setup fake redis connection to mockup redis for rq
        - Instrument rq
        """
        super().setUp()
        RQInstrumentor().instrument()

        self.fakeredis = fakeredis.FakeRedis()
        self.queue = Queue(name="queue_name", connection=self.fakeredis)
        self.worker = Worker(
            queues=[self.queue], name="worker_name", connection=self.fakeredis
        )

    def tearDown(self):
        """Teardown after testing
        - Uninstrument rq
        - Teardown tracer from opentelemetry.test.test_base.TestBase
        """
        RQInstrumentor().uninstrument()
        super().tearDown()

    def test_success_callback_ok(self):
        """Test for success callback finished without exception

        We expected that there are 5 spans in total
            - Enqueue span (from queue)
            - Perform Job span (from worker)
            - Perform span (from job)
            - Success Callback span (from job)
            - Handle Job Success span (from worker)
        """
        job = self.queue.enqueue(
            tasks.task_normal,
            on_success=Callback(tasks.success_callback),
            on_failure=Callback(tasks.failure_callback),
            on_stopped=Callback(tasks.stopped_callback),
        )
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 5)

        enqueue_span = spans[-1]

        success_callback_span = spans[-4]
        self.assertEqual(success_callback_span.name, "success_callback")
        self.assertEqual(success_callback_span.kind, trace.SpanKind.CLIENT)
        self.assertEqual(
            success_callback_span.context.trace_id, enqueue_span.context.trace_id
        )

    def test_success_callback_failed_failure_callback_ok(self):
        """Test for success callback raises exception, but failue callback ok

        We expected that there are 6 spans in total
            - Enqueue span (from queue)
            - Perform Job span (from worker)
            - Perform span (from job)
            - Success Callback span (from job)
            - Failure Callback span (from job)
            - Handle Job Failure span (from worker)
        """
        job = self.queue.enqueue(
            tasks.task_normal,
            on_success=Callback(tasks.success_callback_exception),
            on_failure=Callback(tasks.failure_callback),
            on_stopped=Callback(tasks.stopped_callback),
        )
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 6)

        enqueue_span = spans[-1]

        success_callback_span = spans[-4]
        self.assertEqual(success_callback_span.name, "success_callback")
        self.assertEqual(
            success_callback_span.status.status_code, trace.StatusCode.ERROR
        )

        failure_callback_span = spans[-5]
        self.assertEqual(failure_callback_span.name, "failure_callback")
        self.assertEqual(
            failure_callback_span.context.trace_id, enqueue_span.context.trace_id
        )

    def test_success_callback_failed_failure_callback_failed(self):
        """Test for both success and failure callback raises exception

        We expected that there are 6 spans in total
            - Enqueue span (from queue)
            - Perform Job span (from worker)
            - Perform span (from job)
            - Success Callback span (from job)
            - Failure Callback span (from job)
            - Handle Job Failure span (from worker)
        """
        job = self.queue.enqueue(
            tasks.task_normal,
            on_success=Callback(tasks.success_callback_exception),
            on_failure=Callback(tasks.failure_callback_exception),
            on_stopped=Callback(tasks.stopped_callback),
        )
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 6)

        success_callback_span = spans[-4]
        self.assertEqual(
            success_callback_span.status.status_code, trace.StatusCode.ERROR
        )

        failure_callback_span = spans[-5]
        self.assertEqual(
            failure_callback_span.status.status_code, trace.StatusCode.ERROR
        )

    def test_failure_callback_ok(self):
        """Test for failure callback finished without exception

        We expected that there are 5 spans in total
            - Enqueue span (from queue)
            - Perform Job span (from worker)
            - Perform span (from job)
            - Failure Callback span (from job)
            - Handle Job Failure span (from worker)
        """
        job = self.queue.enqueue(
            tasks.task_exception,
            on_success=Callback(tasks.success_callback),
            on_failure=Callback(tasks.failure_callback),
            on_stopped=Callback(tasks.stopped_callback),
        )
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 5)

        enqueue_span = spans[-1]

        failure_callback_span = spans[-4]
        self.assertEqual(failure_callback_span.name, "failure_callback")
        self.assertEqual(failure_callback_span.kind, trace.SpanKind.CLIENT)
        self.assertEqual(
            failure_callback_span.status.status_code, trace.StatusCode.UNSET
        )
        self.assertEqual(
            failure_callback_span.context.trace_id, enqueue_span.context.trace_id
        )

    def test_failure_callback_failure(self):
        """Test for failure callback raises exception

        We expected that there are 5 spans in total
            - Enqueue span (from queue)
            - Perform Job span (from worker)
            - Perform span (from job)
            - Failure Callback span (from job)
            - Handle Job Failure span (from worker)
        """
        job = self.queue.enqueue(
            tasks.task_exception,
            on_success=Callback(tasks.success_callback),
            on_failure=Callback(tasks.failure_callback_exception),
            on_stopped=Callback(tasks.stopped_callback),
        )
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 5)

        failure_callback_span = spans[-4]
        self.assertEqual(failure_callback_span.name, "failure_callback")
        self.assertEqual(failure_callback_span.kind, trace.SpanKind.CLIENT)
        self.assertEqual(
            failure_callback_span.status.status_code, trace.StatusCode.ERROR
        )
