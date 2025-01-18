"""Unit tests for opentelemetry_instrumentation_rq/instrumentor.py"""

from dataclasses import dataclass
from typing import Any, List

import fakeredis
from opentelemetry.test.test_base import TestBase
from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import instrumentor, utils


class TestTraceInstrumentWrapper(TestBase):
    """Unit test cases for `TraceInstrumentWrapper`'s method

    For those function defined in `utils`, we will just mock it
    the correctness of `utils` should be tested in `tests/test_utils.py`
    """

    def setUp(self):
        """Setup before testing

        - Setup common wrapper inputs
        - Setup fake redis connection to mockup redis for rq
        """
        super().setUp()

        self.job_instance_info = utils.InstanceInfo(
            name=utils.RQElementName.JOB, type=Job
        )
        self.queue_instance_info = utils.InstanceInfo(
            name=utils.RQElementName.QUEUE, type=Queue
        )
        self.worker_instance_info = utils.InstanceInfo(
            name=utils.RQElementName.WORKER, type=Worker
        )

        self.job_argument_info = utils.ArgumentInfo(
            name=utils.RQElementName.JOB, position=0, type=Job
        )
        self.queue_argument_info = utils.ArgumentInfo(
            name=utils.RQElementName.QUEUE, position=0, type=Queue
        )
        self.worker_argument_info = utils.ArgumentInfo(
            name=utils.RQElementName.WORKER, position=0, type=Worker
        )

        self.fakeredis = fakeredis.FakeRedis()

    def tearDown(self):
        """Teardown after testing"""
        self.fakeredis.close()

    def test_get_span_name(self):
        """Test generating span name"""

        @dataclass
        class TestCase:
            name: str
            operation_name: str
            target: str
            expected_return: str
            description: str

        test_cases: List[TestCase] = [
            TestCase(
                name="Normal case",
                operation_name="publish",
                target="queue",
                expected_return="publish queue",
                description="If `target` string is non empty, concat them",
            ),
            TestCase(
                name="Empty `target` input",
                operation_name="publish",
                target="",
                expected_return="publish",
                description="If `target` is empty, just leave `operation_name`",
            ),
            TestCase(
                name="Invalid `target` input type",
                operation_name="publish",
                target=123,
                expected_return="publish",
                description="If `target` is not str, just leave `operation_name`",
            ),
        ]

        for test_case in test_cases:
            wrapper = instrumentor.TraceInstrumentWrapper(
                span_kind=Any,
                operation_type=Any,
                operation_name=test_case.operation_name,
                should_propagate=Any,
                instance_info=Any,
                argument_info_list=Any,
            )

            actual_return = wrapper.get_span_name(test_case.target)

            self.assertEqual(
                test_case.expected_return,
                actual_return,
                msg="Failed test case ({}), expected: {}, actual: {}".format(
                    test_case.name, test_case.expected_return, actual_return
                ),
            )
