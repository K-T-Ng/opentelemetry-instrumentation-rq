"""Unit tests for opentelemetry_instrumentation_rq/__init__.py"""

from typing import List

import fakeredis
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import RQInstrumentor


class TestRQInstrumentor(TestBase):
    """Unit test cases for `RQInstrumentation` methods"""

    def setUp(self):
        """Setup before testing
        - Setup tracer from opentelemetry.test.test_base.TestBase
        - Setup fake redis connection to mockup redis for rq
        - Instrument rq
        """
        super().setUp()
        self.fake_redis = fakeredis.FakeRedis()
        RQInstrumentor().instrument()

    def tearDown(self):
        """Teardown after testing
        - Uninstrument rq
        - Teardown tracer from opentelemetry.test.test_base.TestBase
        """
        RQInstrumentor().uninstrument()
        super().tearDown()

    def test_instrument__enqueue(self):
        """Test instrumentation for `rq.queue.Queue._enqueue_job`"""
        job = Job.create(
            func=print, args=(10,), id="job_id", connection=self.fake_redis
        )
        queue = Queue(name="queue_name", connection=self.fake_redis)

        expected_attributes = {
            "job.id": "job_id",
            "job.func_name": "builtins.print",
            "queue.name": "queue_name",
        }

        # pylint: disable=protected-access
        queue._enqueue_job(job)

        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans),
            1,
            "There should only have one span if only _enqueue is triggered",
        )

        span = spans[0]
        self.assertSpanHasAttributes(span, expected_attributes)
        self.assertIn("traceparent", job.meta)

    def test_instrument_perform(self):
        """Test instrumentation for `rq.job.Job.perform`"""
        job = Job.create(
            func=print, args=(10,), id="job_id", connection=self.fake_redis
        )
        job.prepare_for_execution(
            worker_name="worker_name", pipeline=self.fake_redis.pipeline()
        )

        expected_attributes = {
            "worker.name": "worker_name",
            "job.id": "job_id",
            "job.func_name": "builtins.print",
        }

        job.perform()

        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans),
            1,
            "There should only have one span if only perform is triggered",
        )

        span = spans[0]
        self.assertSpanHasAttributes(span, expected_attributes)

    def test_instrument_perform_with_exception(self):
        """Test instrumentation for `rq.job.Job.perform`, but
        with exception within job.
        """

        def task():
            raise ValueError("For testing")

        job = Job.create(func=task, id="job_id", connection=self.fake_redis)
        job.prepare_for_execution(
            worker_name="worker_name", pipeline=self.fake_redis.pipeline()
        )

        # 1. Should raise ValueError, as definition in `task`
        with self.assertRaises(ValueError):
            job.perform()

        # 2. Should have one span finished
        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans),
            1,
            "There should only have one span if only perform is triggered",
        )

        # 3. Span statue should be ERROR
        span = spans[0]
        self.assertEqual(
            span.status.status_code,
            trace.StatusCode.ERROR,
            "Span staus should be ERROR",
        )

    def test_instrument_both_enqeue_and_perform_job(self):
        """Test instumentation for both `rq.queue.Queue._enqueue` and `rq.worker.Worker.perform_job`"""
        job = Job.create(
            func=print, args=(10,), id="job_id", connection=self.fake_redis
        )
        queue = Queue(name="queue_name", connection=self.fake_redis)
        worker = Worker(
            queues=["queue_name"], name="worker_name", connection=self.fake_redis
        )

        # pylint: disable=protected-access
        enqueued_job: Job = queue._enqueue_job(job)
        worker.perform_job(enqueued_job, queue)

        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans), 2, "There should be 2 spans after _enqueue_job and perfrom_job"
        )

        _enqueued_job_span = spans[0]
        perform_job_span = spans[1]

        assert perform_job_span.parent.trace_id == _enqueued_job_span.context.trace_id
