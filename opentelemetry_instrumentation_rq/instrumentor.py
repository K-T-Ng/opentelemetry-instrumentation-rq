"""Trace instrumentor for creating span & setting span attributes"""

import socket
from typing import Dict, List, Union

from opentelemetry import trace
from opentelemetry.semconv._incubating.attributes import messaging_attributes
from opentelemetry.semconv._incubating.attributes.messaging_attributes import (
    MessagingOperationTypeValues,
)

from opentelemetry_instrumentation_rq import utils

ATTRIBUTE_BASE: Dict[str, Union[int, str]] = {
    messaging_attributes.MESSAGING_SYSTEM: "Python RQ",
    messaging_attributes.MESSAGING_CLIENT_ID: socket.gethostname(),
}


class TraceInstrumentWrapper:

    def __init__(
        self,
        span_kind: trace.SpanKind,
        operation_type: MessagingOperationTypeValues,
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
        """Generate span name based on `operation_name` and `target`"""
        if not isinstance(target, str) or not len(target):
            return self.operation_name

        return f"{self.operation_name} {target}"
