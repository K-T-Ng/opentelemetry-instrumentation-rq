"""Trace instrumentor for creating span & setting span attributes"""

import socket
from typing import Dict, List, Optional, Union

from opentelemetry import trace
from opentelemetry.semconv._incubating.attributes import messaging_attributes
from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker

from opentelemetry_instrumentation_rq import rq_attributes, utils

ATTRIBUTE_BASE: Dict[str, Union[int, str]] = {
    messaging_attributes.MESSAGING_SYSTEM: "Python RQ",
    messaging_attributes.MESSAGING_CLIENT_ID: socket.gethostname(),
}


class TraceInstrumentWrapper:

    def __init__(
        self,
        span_kind: trace.SpanKind,
        operation_type: str,
        operation_name: str,
        should_propagate: bool,
        instance_info: utils.InstanceInfo,
        argument_info_list: List[utils.ArgumentInfo],
    ):
        self.tracer = trace.get_tracer(__name__)

        self.span_kind = span_kind
        self.operation_type = operation_type
        self.operation_name = operation_name

        self.should_propagate = should_propagate
        self.instance_info = instance_info
        self.argument_info_list = argument_info_list

    def get_span_name(self, target: str) -> str:
        """Generate span name by `operation_name` and user specific target.

        Args:
            target (str): for enriching span name

        Returns:
            str: Name for the span
        """
        if not isinstance(target, str) or not len(target):
            return self.operation_name

        return f"{self.operation_name} {target}"

    def get_attributes(
        self, rq_input: Dict[utils.RQElementName, Union[Job, Queue, Worker]]
    ) -> Dict[str, str]:
        """Generate attributes from rq elements

        Args:
            rq_input (Dict[utils.RQElementName, Union[Job, Queue, Worker]]):
                RQ input being extracted.

        Returns:
            Dict[str, str]: Span attributes
        """
        attributes = ATTRIBUTE_BASE.copy()

        attributes[messaging_attributes.MESSAGING_OPERATION_TYPE] = self.operation_type
        attributes[messaging_attributes.MESSAGING_OPERATION_NAME] = self.operation_name

        job: Optional[Job] = rq_input.get(utils.RQElementName.JOB, None)
        if job:
            attributes[rq_attributes.JOB_ID] = job.id
            attributes[rq_attributes.JOB_FUNCTION] = job.func_name

            if job.worker_name and self.span_kind == trace.SpanKind.CONSUMER:
                attributes[messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME] = (
                    job.worker_name
                )

        queue: Optional[Queue] = rq_input.get(utils.RQElementName.QUEUE, None)
        if queue:
            attributes[messaging_attributes.MESSAGING_DESTINATION_NAME] = queue.name

        worker: Optional[Worker] = rq_input.get(utils.RQElementName.WORKER, None)
        if worker and self.span_kind == trace.SpanKind.CONSUMER:
            attributes[messaging_attributes.MESSAGING_CONSUMER_GROUP_NAME] = worker.name

        return attributes
