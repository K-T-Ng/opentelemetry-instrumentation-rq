"""Unit tests for opentelemetry_instrumentation_rq/instrumentor.py"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Union

import fakeredis
import mock
from opentelemetry import trace
from opentelemetry.sdk.trace import Span
from opentelemetry.semconv._incubating.attributes import messaging_attributes
from opentelemetry.test.test_base import TestBase
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from rq.job import Dependency, Job
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import instrumentor, rq_attributes, utils


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

        self.fakeredis = fakeredis.FakeRedis()

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

        self.job = Job.create(func=print, connection=self.fakeredis, id="JOB_ID")
        setattr(self.job, "worker_name", "WORKER_NAME")  # Patch worker name
        self.queue = Queue(name="QUEUE_NAME", connection=self.fakeredis)
        self.worker = Worker(
            name="WORKER_NAME", queues=["QUEUE_NAME"], connection=self.fakeredis
        )

    def tearDown(self):
        """Teardown after testing"""
        self.fakeredis.close()
        super().tearDown()

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
                should_flush=Any,
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

    def test_get_attributes(self):
        """Test getting attributes from RQ components"""

        @dataclass
        class TestCase:
            name: str
            description: str
            span_kind: trace.SpanKind
            rq_input: Dict[utils.RQElementName, Union[Job, Queue, Worker]]
            expected_subset: Dict[str, str]
            expected_not_appear_keys: List[str] = field(default_factory=list)

        test_cases: List[TestCase] = [
            TestCase(
                name="Job without worker name",
                span_kind=trace.SpanKind.CLIENT,
                rq_input={utils.RQElementName.JOB: self.job},
                expected_subset={
                    rq_attributes.JOB_ID: "JOB_ID",
                    rq_attributes.JOB_FUNCTION: "builtins.print",
                },
                description="Expected to catch job id and function name",
            ),
            TestCase(
                name="Job with non CONSUMER span kind",
                span_kind=trace.SpanKind.CLIENT,
                rq_input={utils.RQElementName.JOB: self.job},
                expected_subset={
                    rq_attributes.JOB_ID: "JOB_ID",
                    rq_attributes.JOB_FUNCTION: "builtins.print",
                },
                expected_not_appear_keys=[
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME
                ],
                description="Expected to catch job id and function name only",
            ),
            TestCase(
                name="Job with CONSUMER span kind",
                span_kind=trace.SpanKind.CONSUMER,
                rq_input={utils.RQElementName.JOB: self.job},
                expected_subset={
                    rq_attributes.JOB_ID: "JOB_ID",
                    rq_attributes.JOB_FUNCTION: "builtins.print",
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: "WORKER_NAME",
                },
                description="Expected to catch job id, function name and worker name",
            ),
            TestCase(
                name="Extract Queue Name",
                span_kind=trace.SpanKind.CLIENT,
                rq_input={utils.RQElementName.QUEUE: self.queue},
                expected_subset={
                    messaging_attributes.MESSAGING_DESTINATION_NAME: "QUEUE_NAME",
                },
                description="Expected to catch queue name as destination name",
            ),
            TestCase(
                name="Worker without CONSUMER span kind",
                span_kind=trace.SpanKind.CLIENT,
                rq_input={utils.RQElementName.WORKER: self.worker},
                expected_subset={},
                expected_not_appear_keys=[
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME
                ],
                description="Expected nothing to catch since it is NOT consumer",
            ),
            TestCase(
                name="Job with CONSUMER span kind",
                span_kind=trace.SpanKind.CONSUMER,
                rq_input={utils.RQElementName.WORKER: self.worker},
                expected_subset={
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: "WORKER_NAME",
                },
                description="Expected to catch worker name as consumer group name",
            ),
            TestCase(
                name="Empty case",
                span_kind=trace.SpanKind.CONSUMER,
                rq_input={},
                expected_subset={},
                description="Don't broke the process",
            ),
        ]

        for test_case in test_cases:
            wrapper = instrumentor.TraceInstrumentWrapper(
                span_kind=test_case.span_kind,
                operation_type=Any,
                operation_name=Any,
                should_propagate=Any,
                should_flush=Any,
                instance_info=Any,
                argument_info_list=Any,
            )

            actual_return = wrapper.get_attributes(test_case.rq_input)

            self.assertLessEqual(
                test_case.expected_subset.items(),
                actual_return.items(),
                msg="Failed test case ({}), expected: {} in {}".format(
                    test_case.name,
                    test_case.expected_subset,
                    actual_return,
                ),
            )

            for forbidden_key in test_case.expected_not_appear_keys:
                self.assertNotIn(
                    forbidden_key,
                    actual_return,
                    msg="Failed test case ({}), expected: {} not in {}".format(
                        test_case.name,
                        forbidden_key,
                        actual_return,
                    ),
                )

    def test_extract_rq_input(self):
        """Test extract RQ elements from wrapped input"""

        @dataclass
        class TestCase:
            name: str
            description: str
            expected_return: Dict[str, Union[Job, Queue, Worker]]
            instance_input: Any
            instance_info: utils.InstanceInfo
            argument_infos: List[utils.ArgumentInfo] = field(default_factory=list)
            mock_extract_response: List[Union[Job, Queue, Worker]] = field(
                default_factory=list
            )

        test_cases: List[TestCase] = [
            TestCase(
                name="`Queue` instance, with `Job`, `Worker` argument",
                description="Get `Job` and `Worker` from args/kwargs, then `Queue` from instance",
                expected_return={
                    utils.RQElementName.JOB: self.job,
                    utils.RQElementName.QUEUE: self.queue,
                    utils.RQElementName.WORKER: self.worker,
                },
                instance_input=self.queue,
                instance_info=utils.InstanceInfo(
                    name=utils.RQElementName.QUEUE, type=Queue
                ),
                argument_infos=[
                    utils.ArgumentInfo(
                        name=utils.RQElementName.JOB, position=0, type=Job
                    ),
                    utils.ArgumentInfo(
                        name=utils.RQElementName.WORKER, position=1, type=Worker
                    ),
                ],
                mock_extract_response=[self.job, self.worker],
            ),
            TestCase(
                name="Only instance: `Queue`",
                description="Get `Queue` from instance",
                expected_return={
                    utils.RQElementName.QUEUE: self.queue,
                },
                instance_input=self.queue,
                instance_info=utils.InstanceInfo(
                    name=utils.RQElementName.QUEUE, type=Queue
                ),
            ),
            TestCase(
                name="`Queue` instance, with `Job` argument, but cannot extract `Job` normally",
                description="Get `Queue` from instance, skip `Job` due to we can't extract",
                expected_return={
                    utils.RQElementName.QUEUE: self.queue,
                },
                instance_input=self.queue,
                instance_info=utils.InstanceInfo(
                    name=utils.RQElementName.QUEUE, type=Queue
                ),
                argument_infos=[
                    utils.ArgumentInfo(
                        name=utils.RQElementName.JOB, position=0, type=Job
                    ),
                ],
                mock_extract_response=[None],
            ),
        ]

        wrapper = instrumentor.TraceInstrumentWrapper(
            span_kind=Any,
            operation_type=Any,
            operation_name=Any,
            should_propagate=Any,
            should_flush=Any,
            instance_info=Any,
            argument_info_list=Any,
        )

        for test_case in test_cases:
            with mock.patch(
                "opentelemetry_instrumentation_rq.utils._extract_value_from_input",
                side_effect=test_case.mock_extract_response,
            ):
                actual_return = wrapper.extract_rq_input(
                    instance=test_case.instance_input,
                    args=Any,
                    kwargs=Any,
                    instance_info=test_case.instance_info,
                    argument_infos=test_case.argument_infos,
                )

                # RQ Queue object is not comparable, we check the return diction type instead
                expected_typemap = {
                    k: type(v) for k, v in test_case.expected_return.items()
                }
                actual_typemap = {k: type(v) for k, v in actual_return.items()}

                self.assertDictEqual(
                    expected_typemap,
                    actual_typemap,
                    msg="Failed test case ({}), expected: {}, actual: {}".format(
                        test_case.name, test_case.expected_return, actual_return
                    ),
                )

    def test_link_job_dependencies(self):
        """Test case for adding span link on job with dependencies"""
        tracer = trace.get_tracer(__name__)
        wrapper = wrapper = instrumentor.TraceInstrumentWrapper(
            span_kind="producer",
            operation_type="create",
            operation_name="setup dependencies",
            should_propagate=Any,
            should_flush=Any,
            instance_info=Any,
            argument_info_list=Any,
        )

        # Create parent
        parent = Job.create(func=print, connection=self.fakeredis)
        with tracer.start_as_current_span("parent-span") as parent_span:
            TraceContextTextMapPropagator().inject(parent.meta)

        # Create child
        dependency = Dependency(jobs=[parent])
        child = Job.create(func=print, connection=self.fakeredis, depends_on=dependency)
        with tracer.start_as_current_span("child-span") as child_span, mock.patch(
            "rq.job.Job.fetch_dependencies", side_effect=[[parent]]
        ):
            wrapper.link_job_dependencies(child, child_span)

        self.assertEqual(
            len(child_span._links),
            1,
            msg="Error when checking span link quantity, expected: 1, got: {}".format(
                len(child_span._links)
            ),
        )
        self.assertEqual(
            parent_span.context.span_id,
            child_span._links[0].context.span_id,
            msg="Error when testing span link destination on job dependencies",
        )

    def test_call(self):
        """Test __call__ method for `TraceInstrumentWrapper`"""

        def mock_normal_func(*args, **kwargs):
            return

        def mock_exception_func(*args, **kwargs):
            raise Exception

        @dataclass
        class TestCase:
            name: str
            description: str

            span_kind: trace.SpanKind
            operation_type: str
            operation_name: str
            should_propagate: bool

            expect_span_generate: bool
            expect_span_propagate: bool
            expect_span_exception: bool
            expect_span_name: str
            expect_span_kind: trace.SpanKind

            mock_extract: Dict[utils.RQElementName, Union[Job, Queue, Worker]]
            mock_call_func: Callable

        test_cases: List[TestCase] = [
            TestCase(
                name="Skip record (Cannot get Job element)",
                description="No span generated if we can't get Job element",
                span_kind=trace.SpanKind.CLIENT,
                operation_name="process",
                operation_type="process",
                should_propagate=False,
                expect_span_generate=False,
                expect_span_propagate=False,
                expect_span_exception=False,
                expect_span_name="",
                expect_span_kind=trace.SpanKind.CLIENT,
                mock_extract=[{utils.RQElementName.QUEUE: self.queue}],
                mock_call_func=mock_normal_func,
            ),
            TestCase(
                name="Span record with propagation",
                description="Producer span should propagate context to `job.meta`",
                span_kind=trace.SpanKind.PRODUCER,
                operation_name="produce",
                operation_type="send",
                should_propagate=True,
                expect_span_generate=True,
                expect_span_propagate=True,
                expect_span_exception=False,
                expect_span_name="produce QUEUE_NAME",  # self.queue.name
                expect_span_kind=trace.SpanKind.PRODUCER,
                mock_extract=[
                    {
                        utils.RQElementName.QUEUE: self.queue,
                        utils.RQElementName.JOB: self.job,
                    }
                ],
                mock_call_func=mock_normal_func,
            ),
            TestCase(
                name="Span record without propagation",
                description="Producer span should propagate context to `job.meta`",
                span_kind=trace.SpanKind.CONSUMER,
                operation_name="process",
                operation_type="process",
                should_propagate=False,
                expect_span_generate=True,
                expect_span_propagate=False,
                expect_span_exception=False,
                expect_span_name="process QUEUE_NAME",  # self.queue.name
                expect_span_kind=trace.SpanKind.CONSUMER,
                mock_extract=[
                    {
                        utils.RQElementName.QUEUE: self.queue,
                        utils.RQElementName.JOB: self.job,
                        utils.RQElementName.WORKER: self.worker,
                    }
                ],
                mock_call_func=mock_exception_func,
            ),
        ]

        for test_case in test_cases:
            wrapper = instrumentor.TraceInstrumentWrapper(
                span_kind=test_case.span_kind,
                operation_type=test_case.operation_type,
                operation_name=test_case.operation_name,
                should_propagate=test_case.should_propagate,
                should_flush=Any,
                instance_info=Any,
                argument_info_list=Any,
            )

            with mock.patch(
                "opentelemetry_instrumentation_rq.instrumentor.TraceInstrumentWrapper.extract_rq_input",
                side_effect=test_case.mock_extract,
            ):
                try:
                    wrapper(
                        func=test_case.mock_call_func, instance=Any, args=(), kwargs={}
                    )
                except Exception:
                    pass

            # We use job.meta as context carrier, check whether propagation works
            if test_case.expect_span_propagate:
                self.assertIn(
                    "traceparent",
                    self.job.meta,
                    msg="Failed test case ({}), expected context propagate to `job.meta`".format(
                        test_case.name
                    ),
                )

            if test_case.expect_span_generate:
                self.assertEqual(
                    1,
                    len(self.get_finished_spans()),
                    msg="Failed test case ({}), expected one span generated".format(
                        test_case.name
                    ),
                )

                actual_span: Span = self.get_finished_spans()[0]
                self.assertEqual(
                    test_case.expect_span_name,
                    actual_span.name,
                    msg="Failed test case ({}), expected span name {}, actual: {}".format(
                        test_case.name, test_case.expect_span_name, actual_span.name
                    ),
                )
                self.assertEqual(
                    test_case.expect_span_kind,
                    actual_span.kind,
                    msg="Failed test case ({}), expected span kind {}, actual: {}".format(
                        test_case.name, test_case.expect_span_kind, actual_span.kind
                    ),
                )
                if test_case.expect_span_exception:
                    self.assertEqual(
                        trace.StatusCode.ERROR,
                        actual_span.status.status_code,
                        msg="Failed test case ({}), expected span ERROR".format(
                            test_case.name
                        ),
                    )

            else:
                self.assertEqual(
                    len(self.get_finished_spans()),
                    0,
                    msg="Failed test case ({}), expected NO span generated".format(
                        test_case.name
                    ),
                )

            # Reset spans before next test case
            super().tearDown()
            super().setUp()
