"""Unit tests for opentelemetry_instrumentation_rq/__init__.py"""

from datetime import datetime

import fakeredis
from opentelemetry.test.test_base import TestBase
from rq import Callback
from rq.job import Job
from rq.queue import Queue
from rq.registry import StartedJobRegistry
from rq.timeouts import UnixSignalDeathPenalty
from rq.worker import Worker

from opentelemetry_instrumentation_rq import RQInstrumentor
from tests import tasks


class TestRQInstrumentor(TestBase):
    """Unit test cases for `RQInstrumentation` methods

    We only assert the call of `utils._trace_instrument` with
    expected arguments here, the correctness of
    `utils._trace_instrument` should be tested in `tests/test_utils.py`
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

    def test_instrument__enqueue_job(self):
        """Test instrumentation for `rq.queue.Queue._enqueue_job`"""
        job = Job.create(tasks.task_normal, id="job_id", connection=self.fakeredis)
        self.queue._enqueue_job(job)

    def test_instrument_schedule_job(self):
        """Test instrumentation for `rq.queue.Queue.schedule_job`"""
        job = Job.create(func=tasks.task_normal, id="job_id", connection=self.fakeredis)
        self.queue.schedule_job(job=job, datetime=datetime.now())

    def test_instrument_perform_job(self):
        """Test instrumetation for `rq.worker.Worker.perform_job`"""
        job = Job.create(tasks.task_normal, id="job_id", connection=self.fakeredis)
        self.worker.perform_job(job, self.queue)

    def test_instrument_perform(self):
        """Test instrumentation for `rq.job.Job.perform`"""
        job = Job.create(tasks.task_normal, id="job_id", connection=self.fakeredis)
        job.prepare_for_execution(
            worker_name="worker_name", pipeline=self.fakeredis.pipeline()
        )
        job.perform()

    def test_instrument_execute_callback(self):
        """Test instrumentation for `rq.job.Job.execute_*_callback`"""

        job = Job.create(
            func=tasks.task_normal,
            id="job_id",
            connection=self.fakeredis,
            on_success=Callback(tasks.success_callback),
        )
        job.execute_success_callback(UnixSignalDeathPenalty, None)

    def test_instrument_job_status_handler(self):
        """Test instrumentation for `rq.worker.Worker.handle_job_*"""

        job = Job.create(
            func=tasks.task_normal,
            id="job_id",
            connection=self.fakeredis,
        )
        # If `handle_job_success` need to execute independently, we need some mockup
        job.started_at = datetime.now()
        job.ended_at = datetime.now()

        self.worker.handle_job_success(
            job=job, queue=self.queue, started_job_registry=StartedJobRegistry
        )
