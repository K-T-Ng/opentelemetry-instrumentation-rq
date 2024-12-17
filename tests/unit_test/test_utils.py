"""Unit tests for opentelemetry_instrumentation_rq/utils.py"""

from typing import Dict, List

import fakeredis
import mock
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.test.test_base import TestBase
from rq.job import Job
from rq.queue import Queue

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
