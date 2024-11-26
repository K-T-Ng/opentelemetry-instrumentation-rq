"""Unit tests for opentelemetry_instrumentation_rq/__init__.py"""

from typing import List

import fakeredis
import mock
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from opentelemetry.trace import SpanKind
from rq import Callback
from rq.job import Job
from rq.queue import Queue
from rq.timeouts import UnixSignalDeathPenalty

from opentelemetry_instrumentation_rq import RQInstrumentor
from tests import tasks


class TestRQInstrumentor(TestBase):
    """Unit test cases for `RQInstrumentation` methods"""

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

    def tearDown(self):
        """Teardown after testing
        - Uninstrument rq
        - Teardown tracer from opentelemetry.test.test_base.TestBase
        """
        RQInstrumentor().uninstrument()
        super().tearDown()

    def test_instrument__enqueue(self):
        """Test instrumentation for `rq.queue.Queue._enqueue_job`"""

        job = Job.create(tasks.task_normal, id="job_id", connection=self.fakeredis)

        with mock.patch(
            "opentelemetry_instrumentation_rq.utils._get_general_attributes"
        ) as get_general_attributes:
            # pylint: disable=protected-access
            self.queue._enqueue_job(job)
            self.assertIn("traceparent", job.meta)
            get_general_attributes.assert_called_with(job=job, queue=self.queue)

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
        job = Job.create(tasks.task_normal, id="job_id", connection=self.fakeredis)
        job.prepare_for_execution(
            worker_name="worker_name", pipeline=self.fakeredis.pipeline()
        )

        with mock.patch(
            "opentelemetry_instrumentation_rq.utils._get_general_attributes"
        ) as get_general_attributes:
            job.perform()
            get_general_attributes.assert_called_with(job=job)

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

        job = Job.create(
            func=tasks.task_exception, id="job_id", connection=self.fakeredis
        )
        job.prepare_for_execution(
            worker_name="worker_name", pipeline=self.fakeredis.pipeline()
        )

        # 1. Should raise CustomException, as definition in `task_exception`
        with self.assertRaises(tasks.CustomException):
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
        )

    def test_instrument_execute_callback(self):
        """Test instrumentation for `rq.job.Job.execute_*_callback`"""

        job = Job.create(
            func=tasks.task_normal,
            id="job_id",
            connection=self.fakeredis,
            on_success=Callback(tasks.success_callback),
        )

        job.execute_success_callback(UnixSignalDeathPenalty, None)

        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans),
            1,
            "There should only have one span if we trigger `execute_succes_callback` directly",
        )

        span = spans[0]
        self.assertEqual(span.name, "success_callback")

    def test_instrument_execute_callback_with_exception(self):
        """Test instrumentation for `rq.job.Job.execute_*_callback`, but with exception"""

        job = Job.create(
            func=tasks.task_exception,
            id="job_id",
            connection=self.fakeredis,
            on_success=Callback(tasks.success_callback_exception),
        )

        with self.assertRaises(tasks.CustomException):
            job.execute_success_callback(UnixSignalDeathPenalty, None)

        spans: List[Span] = self.memory_exporter.get_finished_spans()
        self.assertEqual(
            len(spans),
            1,
            "There should only have one span if we trigger `execute_succes_callback` directly",
        )

        span = spans[0]
        self.assertEqual(
            span.status.status_code,
            trace.StatusCode.ERROR,
        )
