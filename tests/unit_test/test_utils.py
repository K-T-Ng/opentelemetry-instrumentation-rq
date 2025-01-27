"""Unit tests for opentelemetry_instrumentation_rq/utils.py"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import fakeredis
import mock
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import utils


class TestUtils(TestBase):
    """Unit test cases for utils"""

    def setUp(self):
        """Further setup elements before each test"""
        super().setUp()

        self.tracer = trace.get_tracer(__name__)

        self.fakeredis = fakeredis.FakeRedis()
        self.job = Job.create(func=print, connection=self.fakeredis, id="job id")
        self.queue = Queue(name="queue name", connection=self.fakeredis)

    def test__set_span_attributes(self):
        """Test adding attributes to span"""
        attributes_in_record = {"foo": "bar"}
        with self.tracer.start_as_current_span("name") as span:
            utils._set_span_attributes(span, attributes_in_record)
            self.assertSpanHasAttributes(
                span, attributes_in_record
            )  # pylint: disable=protected-access

        attributes_not_in_record = {"baz": "uwu"}
        with mock.patch(
            "opentelemetry.sdk.trace.Span.set_attributes"
        ) as set_attributes:
            utils._set_span_attributes(
                span, attributes_not_in_record
            )  # pylint: disable=protected-access
            set_attributes.assert_not_called()

    def test__set_span_error_status(self):
        """Test recording error status and exception detail to a span"""

        def division_by_zero():
            1 / 0

        with self.tracer.start_as_current_span("name") as span:
            span: Span
            try:
                division_by_zero()
            except Exception as exc:
                utils._set_span_error_status(span, exc)

            self.assertEqual(
                span.status.status_code,
                trace.StatusCode.ERROR,
                "Span staus should be set as ERROR",
            )

    def test__trace_instrument_normal(self):
        """Test normal trace insturmentation flow"""
        carrier: Dict = {}
        utils._trace_instrument(
            func=print,
            span_name="Span name",
            span_kind=trace.SpanKind.INTERNAL,
            span_attributes={"foo": "bar"},
            span_context_carrier=carrier,
            propagate=False,
            args=(),
            kwargs={},
        )

        spans: List[Span] = self.get_finished_spans()
        self.assertEqual(len(spans), 1)

        span: Span = spans[0]
        self.assertEqual(span.name, "Span name")
        self.assertEqual(span.kind, trace.SpanKind.INTERNAL)
        self.assertSpanHasAttributes(span, {"foo": "bar"})
        self.assertDictEqual(carrier, {})

    def test__trace_instrument_with_propagate(self):
        """Test trace instrumentation with context propagation"""
        carrier: Dict = {}
        utils._trace_instrument(
            func=print,
            span_name="Span name",
            span_kind=trace.SpanKind.INTERNAL,
            span_attributes={"foo": "bar"},
            span_context_carrier=carrier,
            propagate=True,
            args=(),
            kwargs={},
        )

        # TODO: make traceparent as configruable constant
        self.assertIn("traceparent", carrier)

    def test__trace_instrument_exception_catching(self):
        """Test trace instrumentation when exception happens in instrumentation function"""

        def task_exception():
            raise Exception

        with (
            mock.patch(
                "opentelemetry_instrumentation_rq.utils._set_span_error_status"
            ) as exception_handler,
            self.assertRaises(Exception),
        ):
            utils._trace_instrument(
                func=task_exception,
                span_name="Span name",
                span_kind=trace.SpanKind.INTERNAL,
                span_attributes={"foo": "bar"},
                span_context_carrier={},
                propagate=False,
                args=(),
                kwargs={},
            )

        exception_handler.assert_called_once()

    def test__get_general_attributes(self):
        """Test getting general attributes from RQ elemenets"""
        setattr(self.job, "worker_name", "worker name")

        test_cases: List[Dict] = [
            {"job": self.job},
            {"queue": self.queue},
        ]
        expected_cases: List[Dict] = [
            {
                "job.id": "job id",
                "job.func_name": "builtins.print",
                "worker.name": "worker name",
            },
            {"queue.name": "queue name"},
        ]

        for tc, ec in zip(test_cases, expected_cases):
            self.assertDictEqual(
                utils._get_general_attributes(**tc), ec
            )  # pylint: disable=protected-access

    def test__extract_value_from_input(self):
        """Test extracting value from wrapped function input (args and kwargs)"""

        @dataclass
        class TestCase:
            name: str
            args: Tuple
            kwargs: Dict
            argument_name: str
            argument_type: Any
            argument_position: int
            expected_return: Optional[str]
            description: str

        test_cases: List[TestCase] = [
            TestCase(
                name="Argument not found",
                args=(),
                kwargs={},
                argument_name="foo",
                argument_type=int,
                argument_position=1,
                expected_return=None,
                description="No such argument and list out of range, should return None",
            ),
            TestCase(
                name="Argument in `kwargs`",
                args=("baz",),
                kwargs={"foo": "bar"},
                argument_name="foo",
                argument_type=str,
                argument_position=0,
                expected_return="bar",
                description="foo should only appears in kwargs, so it has higher priority",
            ),
            TestCase(
                name="Argument in `args` and type matched",
                args=("baz",),
                kwargs={"foo": "bar"},
                argument_name="i",
                argument_type=str,
                argument_position=0,
                expected_return="baz",
                description="`i` appears in the first element in args and type matched",
            ),
            TestCase(
                name="Argument in `args` but type mismatched",
                args=("baz",),
                kwargs={"foo": "bar"},
                argument_name="i",
                argument_type=int,
                argument_position=0,
                expected_return=None,
                description="`i` appears in the first element in args but type unmatched",
            ),
        ]

        for test_case in test_cases:
            actual_return = utils._extract_value_from_input(
                argument_name=test_case.argument_name,
                argument_pos=test_case.argument_position,
                argument_type=test_case.argument_type,
                args=test_case.args,
                kwargs=test_case.kwargs,
            )

            self.assertEqual(
                test_case.expected_return,
                actual_return,
                msg="Failed test case ({}), expected: {}, actual: {}".format(
                    test_case.name, test_case.expected_return, actual_return
                ),
            )

    def test_get_argument_info(self):
        """Test getting common ArgumentInfo"""

        @dataclass
        class TestCase:
            name: str
            element_name: utils.RQElementName
            position: Optional[int]
            expected_return: utils.ArgumentInfo
            description: str

        test_cases: List[TestCase] = [
            TestCase(
                name="Get JOB",
                element_name=utils.RQElementName.JOB,
                position=0,
                expected_return=utils.ArgumentInfo(
                    name=utils.RQElementName.JOB, position=0, type=Job
                ),
                description="Get JOB ArgumentInfo",
            ),
            TestCase(
                name="Get QUEUE",
                element_name=utils.RQElementName.QUEUE,
                position=1,
                expected_return=utils.ArgumentInfo(
                    name=utils.RQElementName.QUEUE, position=1, type=Queue
                ),
                description="Get QUEUE ArgumentInfo",
            ),
            TestCase(
                name="Get WORKER",
                element_name=utils.RQElementName.WORKER,
                position=2,
                expected_return=utils.ArgumentInfo(
                    name=utils.RQElementName.WORKER, position=2, type=Worker
                ),
                description="Get WORKER ArgumentInfo",
            ),
            TestCase(
                name="Get JOB without giving `position` argument",
                element_name=utils.RQElementName.JOB,
                position=None,
                expected_return=utils.ArgumentInfo(
                    name=utils.RQElementName.JOB, position=0, type=Job
                ),
                description="Get JOB ArgumentInfo, the default `position` should be 0",
            ),
            TestCase(
                name="Get non-exist ArgumentInfo",
                element_name="NOT_EXIST",
                position=None,
                expected_return=utils.ArgumentInfo(
                    name="NOT_EXIST", position=0, type=type(None)
                ),
                description="Get non-exist ArgumentInfo, name->NOT_EXIST, type->None",
            ),
        ]

        for test_case in test_cases:
            if test_case.position:
                actual_return = utils.get_argument_info(
                    element_name=test_case.element_name, position=test_case.position
                )
            else:
                actual_return = utils.get_argument_info(
                    element_name=test_case.element_name
                )

            self.assertEqual(
                test_case.expected_return,
                actual_return,
                msg="Failed test case ({}), expected: {}, actual: {}".format(
                    test_case.name, test_case.expected_return, actual_return
                ),
            )

    def test_get_instance_info(self):
        """Test getting common InstanceInfo"""

        @dataclass
        class TestCase:
            name: str
            element_name: utils.RQElementName
            expected_return: utils.InstanceInfo
            description: str

        test_cases: List[TestCase] = [
            TestCase(
                name="Get JOB",
                element_name=utils.RQElementName.JOB,
                expected_return=utils.InstanceInfo(
                    name=utils.RQElementName.JOB, type=Job
                ),
                description="Get JOB InstanceInfo",
            ),
            TestCase(
                name="Get QUEUE",
                element_name=utils.RQElementName.QUEUE,
                expected_return=utils.InstanceInfo(
                    name=utils.RQElementName.QUEUE, type=Queue
                ),
                description="Get QUEUE InstanceInfo",
            ),
            TestCase(
                name="Get WORKER",
                element_name=utils.RQElementName.WORKER,
                expected_return=utils.InstanceInfo(
                    name=utils.RQElementName.WORKER, type=Worker
                ),
                description="Get WORKER InstanceInfo",
            ),
            TestCase(
                name="Get non-exist InstanceInfo",
                element_name="NOT_EXIST",
                expected_return=utils.InstanceInfo(name="NOT_EXIST", type=type(None)),
                description="Get non-exist InstanceInfo, name->NOT_EXIST, type->None",
            ),
        ]

        for test_case in test_cases:
            actual_return = utils.get_instance_info(element_name=test_case.element_name)

            self.assertEqual(
                test_case.expected_return,
                actual_return,
                msg="Failed test case ({}), expected: {}, actual: {}".format(
                    test_case.name, test_case.expected_return, actual_return
                ),
            )
