from typing import Callable, Dict, List
from datetime import datetime, timedelta, timezone
import time
import redis
import requests
from opentelemetry import trace
from opentelemetry.test.test_base import TestBase
from opentelemetry.semconv._incubating.attributes import messaging_attributes
from opentelemetry.semconv._incubating.attributes.messaging_attributes import (
    MessagingOperationTypeValues,
)
from pydantic import BaseModel
from rq import Queue

from opentelemetry_instrumentation_rq import rq_attributes
from tests import tasks
from tests.e2e_test.model import V1TraceData, V1Span
from tests.e2e_test.simulator.otel_setup import initialize

QUEUE_NAME = "test_queue"
WORKER_NAME = "test_worker"


class ExpectSpan(BaseModel):
    name: str
    kind: trace.SpanKind
    attributes: Dict


class TestCase(BaseModel):
    name: str
    description: str
    producer_call: Callable[[Queue], None]
    expect_span_list: List[ExpectSpan]


def get_basic_usage_task_normal_case() -> TestCase:

    def enqueue(queue: Queue):
        job = queue.enqueue(tasks.task_normal)

    return TestCase(
        name="Basic usage: Task Normal",
        description="Basic usage, with task without delay",
        producer_call=enqueue,
        expect_span_list=[
            ExpectSpan(
                name=f"publish {QUEUE_NAME}",
                kind=trace.SpanKind.PRODUCER,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.SEND.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "publish",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"consume {QUEUE_NAME}",
                kind=trace.SpanKind.CONSUMER,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "consume",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME: WORKER_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"perform",
                kind=trace.SpanKind.CLIENT,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "perform",
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
            ExpectSpan(
                name=f"handle_job_success {QUEUE_NAME}",
                kind=trace.SpanKind.CLIENT,
                attributes={
                    messaging_attributes.MESSAGING_OPERATION_TYPE: MessagingOperationTypeValues.PROCESS.value,
                    messaging_attributes.MESSAGING_OPERATION_NAME: "handle_job_success",
                    messaging_attributes.MESSAGING_DESTINATION_NAME: QUEUE_NAME,
                    rq_attributes.JOB_FUNCTION: "tests.tasks.task_normal",
                },
            ),
        ],
    )


TEST_CASES: List[TestCase] = [get_basic_usage_task_normal_case()]


class TestExpectSpanInfo(TestBase):

    def setUp(self):
        """Setup Fake redis, Queue and Worker"""
        initialize(otlp_http_endpoint="http://localhost:4318")

        self.redis = redis.Redis(host="localhost", port=6379)
        self.queue = Queue(name=QUEUE_NAME, connection=self.redis)
    
    def get_spans(self) -> List[List[V1Span]]:

        now = datetime.now(timezone.utc)
        prev = now - timedelta(days=1)

        response = requests.get(
            url="http://localhost:16686/api/v3/traces",
            params={
                "query.service_name": "rq-instrumentation",
                "query.start_time_min": prev.isoformat(),
                "query.start_time_max": now.isoformat(),
            }
        )

        response_json = response.json()
        trace_data = V1TraceData.model_validate(response_json.get("result"))

        #TODO: Sort by time if needed
        span_datas: List[List[V1Span]] = []
        for rs in trace_data.resource_spans:
            spans = rs.scope_spans[0].spans
            spans.sort(key=lambda span: span.start_time_unix_nano)
            span_datas.append(spans)

        return span_datas


    def test_simulation(self):
        # Produce Jobs
        for test_case in TEST_CASES:
            test_case.producer_call(self.queue)

        # Get spans from Jaeger
        time.sleep(20)
        span_datas = self.get_spans()

        # Check spans
        for test_case, actual_spans in zip(TEST_CASES, span_datas):
            expect_spans = test_case.expect_span_list

            for expect, actual in zip(expect_spans, actual_spans):
                self.assertEqual(
                    expect.name,
                    actual.name,
                    msg="Failed test case: {}, expect span name: {}, got: {}".format(
                        test_case.name,
                        expect.name,
                        actual.name
                    )
                )
                self.assertEqual(
                    expect.kind.value,
                    actual.kind-1,
                    msg="Failed test case: {}, expect span kind: {}, got: {}".format(
                        test_case.name,
                        expect.kind,
                        actual.kind
                    )
                )
                self.assertLessEqual(
                    expect.attributes.items(),
                    {attr.key: attr.value["stringValue"] for attr in actual.attributes}.items(),
                    msg="Failed test case: {}, expect span contains attributes: {}, got: {}".format(
                        test_case.name,
                        expect.attributes,
                        actual.attributes
                    )
                )
