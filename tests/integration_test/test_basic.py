"""Tests for instrumentation for basic usage"""

from typing import List

import fakeredis
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import RQInstrumentor
from tests import tasks


class TestBasicUsage(TestBase):
    """Test cases for instruemntation for only enqueue and perform

    - Both `enqueue` and `perform` are normal
    - Task function has exception
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

    def test_normal(self):
        """Test for tasks enqueued and performed successfully

        We expected that
            - There are 4 spans in total
                - Enqueue span (from queue)
                - Perform Job span (from worker)
                - Perform span (from job)
                - Handle Job Success span (from worker)
        """
        job = self.queue.enqueue(tasks.task_normal)
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 4)

        enqueue_span = spans[-1]
        self.assertEqual(enqueue_span.name, "enqueue")
        self.assertEqual(enqueue_span.kind, trace.SpanKind.PRODUCER)
        self.assertIn("traceparent", job.meta)

        perform_job_span = spans[-2]
        self.assertEqual(perform_job_span.name, "perform_job")
        self.assertEqual(perform_job_span.kind, trace.SpanKind.CONSUMER)
        self.assertEqual(
            perform_job_span.context.trace_id, enqueue_span.context.trace_id
        )

        perform_span = spans[-3]
        self.assertEqual(perform_span.name, "perform")
        self.assertEqual(perform_span.kind, trace.SpanKind.CLIENT)
        self.assertEqual(perform_span.context.trace_id, enqueue_span.context.trace_id)

        handle_job_success_span = spans[-4]
        self.assertEqual(handle_job_success_span.name, "handle_job_success")
        self.assertEqual(handle_job_success_span.kind, trace.SpanKind.CLIENT)
        self.assertEqual(
            handle_job_success_span.context.trace_id, enqueue_span.context.trace_id
        )

    def test_job_exception(self):
        """Test for tasks enqueued and performed, but the job raises
        exception when execution

        We expected that
            - There are 4 spans in total
                - Enqueue span (from queue)
                - Perform Job span (from worker)
                - Perform span (from job, but with FAILED status)
                - Handle Job Failure span (from worker)
        """
        job = self.queue.enqueue(tasks.task_exception)
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 4)

        perform_span = spans[-3]
        self.assertEqual(perform_span.status.status_code, trace.StatusCode.ERROR)

        handle_job_failure_span = spans[-4]
        self.assertEqual(handle_job_failure_span.name, "handle_job_failure")
        self.assertEqual(handle_job_failure_span.kind, trace.SpanKind.CLIENT)
