"""Unit tests for opentelemetry_instrumentation_rq/__init__.py"""

from typing import List

import fakeredis
import mock
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from opentelemetry.trace import SpanKind
from rq.job import Job
from rq.queue import Queue

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
        self.fakeredis = fakeredis.FakeRedis()
        RQInstrumentor().instrument()

        self.job = Job.create(
            func=print, args=(10,), id="job_id", connection=self.fakeredis
        )
        self.queue = Queue(name="queue_name", connection=self.fakeredis)

    def tearDown(self):
        """Teardown after testing
        - Uninstrument rq
        - Teardown tracer from opentelemetry.test.test_base.TestBase
        """
        RQInstrumentor().uninstrument()
        super().tearDown()

    def test_instrument__enqueue(self):
        """Test instrumentation for `rq.queue.Queue._enqueue_job`"""

        with mock.patch(
            "opentelemetry_instrumentation_rq.utils._get_general_attributes"
        ) as get_general_attributes:
            # pylint: disable=protected-access
            self.queue._enqueue_job(self.job)
            self.assertIn("traceparent", self.job.meta)
            get_general_attributes.assert_called_with(job=self.job, queue=self.queue)

        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans),
            1,
            "There should only have one span if only _enqueue is triggered",
        )

        span = spans[0]
        self.assertEqual(span.kind, SpanKind.PRODUCER)

    def test_instrument_perform(self):
        """Test instrumentation for `rq.job.Job.perform`"""
        self.job.prepare_for_execution(
            worker_name="worker_name", pipeline=self.fakeredis.pipeline()
        )

        with mock.patch(
            "opentelemetry_instrumentation_rq.utils._get_general_attributes"
        ) as get_general_attributes:
            self.job.perform()
            get_general_attributes.assert_called_with(job=self.job)

        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans),
            1,
            "There should only have one span if only perform is triggered",
        )

        span = spans[0]
        self.assertEqual(span.kind, SpanKind.CONSUMER)

    def test_instrument_perform_with_exception(self):
        """Test instrumentation for `rq.job.Job.perform`, but
        with exception within job.
        """

        def task():
            raise ValueError("For testing")

        self.job = Job.create(func=task, id="job_id", connection=self.fakeredis)
        self.job.prepare_for_execution(
            worker_name="worker_name", pipeline=self.fakeredis.pipeline()
        )

        # 1. Should raise ValueError, as definition in `task`
        with self.assertRaises(ValueError):
            self.job.perform()

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
        )
