"""Tests for instrumentation for scheduled job"""

import time
from datetime import datetime, timedelta
from typing import List

import fakeredis
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import RQInstrumentor
from tests import tasks


class TestScheduledJob(TestBase):
    """Test cases for instruemntation for job creation using RQScheduler

    - Job scheduled using `queue.enqueue_in`
    - Job scheduled using `queue.enqueue_at`
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

    def test_schedule_in(self):
        """Test for job creation using `queue.enqueue_in`

        We expected that there are 6 spans in total
            - Schedule span (from scheduler)
            - Enqueue span (from queue)
            - Perform Job span (from worker)
            - Perform span (from job)
            - Handle Job Success span (from worker)
        """
        job = self.queue.enqueue_in(timedelta(seconds=0.5), tasks.task_normal)
        time.sleep(1)
        self.worker._start_scheduler(burst=True)
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 5)

        schedule_span = spans[-1]
        self.assertEqual(schedule_span.name, "schedule")
        self.assertEqual(schedule_span.kind, trace.SpanKind.PRODUCER)

        enqueue_span = spans[-2]
        self.assertEqual(enqueue_span.name, "enqueue")
        self.assertEqual(enqueue_span.context.trace_id, schedule_span.context.trace_id)

        perform_job_span = spans[-3]
        self.assertEqual(perform_job_span.name, "perform_job")
        self.assertEqual(
            perform_job_span.context.trace_id, schedule_span.context.trace_id
        )

        perform_span = spans[-4]
        self.assertEqual(perform_span.name, "perform")
        self.assertEqual(perform_span.context.trace_id, schedule_span.context.trace_id)

        handle_job_success_span = spans[-5]
        self.assertEqual(handle_job_success_span.name, "handle_job_success")
        self.assertEqual(
            handle_job_success_span.context.trace_id, schedule_span.context.trace_id
        )

    def test_schedule_at(self):
        """Test for job creation using `queue.enqueue_at`

        We expected that there are 6 spans in total
            - Schedule span (from scheduler)
            - Enqueue span (from queue)
            - Perform Job span (from worker)
            - Perform span (from job)
            - Handle Job Success span (from worker)
        """
        job = self.queue.enqueue_at(datetime(2019, 10, 8, 9, 15), tasks.task_normal)
        self.worker._start_scheduler(burst=True)
        self.worker.perform_job(job, self.queue)

        spans: List[Span] = self.sorted_spans(self.get_finished_spans())
        self.assertEqual(len(spans), 5)

        schedule_span = spans[-1]
        self.assertEqual(schedule_span.name, "schedule")
        self.assertEqual(schedule_span.kind, trace.SpanKind.PRODUCER)

        enqueue_span = spans[-2]
        self.assertEqual(enqueue_span.name, "enqueue")
        self.assertEqual(enqueue_span.context.trace_id, schedule_span.context.trace_id)

        perform_job_span = spans[-3]
        self.assertEqual(perform_job_span.name, "perform_job")
        self.assertEqual(
            perform_job_span.context.trace_id, schedule_span.context.trace_id
        )

        perform_span = spans[-4]
        self.assertEqual(perform_span.name, "perform")
        self.assertEqual(perform_span.context.trace_id, schedule_span.context.trace_id)

        handle_job_success_span = spans[-5]
        self.assertEqual(handle_job_success_span.name, "handle_job_success")
        self.assertEqual(
            handle_job_success_span.context.trace_id, schedule_span.context.trace_id
        )
