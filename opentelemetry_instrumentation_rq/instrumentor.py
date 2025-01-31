"""Trace instrumentor for creating span & setting span attributes"""

import socket
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from opentelemetry import trace
from opentelemetry.semconv._incubating.attributes import messaging_attributes
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
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
        should_flush: bool,
        instance_info: utils.InstanceInfo,
        argument_info_list: List[utils.ArgumentInfo],
    ):
        self.tracer = trace.get_tracer(__name__)
        self.propagator = TraceContextTextMapPropagator()

        self.span_kind = span_kind
        self.operation_type = operation_type
        self.operation_name = operation_name

        self.should_propagate = should_propagate
        self.should_flush = should_flush
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

    def extract_rq_input(
        self,
        instance: Union[Job, Queue, Worker],
        args: Tuple,
        kwargs: Dict,
        instance_info: utils.InstanceInfo,
        argument_infos: List[utils.ArgumentInfo],
    ) -> Dict[utils.RQElementName, Union[Job, Queue, Worker]]:
        """Extract RQ elements from RQ input within wrapped function

        Args:
            instance (Union[Job, Queue, Worker]): Wrapped instance, one of Job, Queue or Worker
            args (Tuple): Non-keyword arguments input from RQ method
            kwargs (Dict): Keyword arguments input from RQ method
            instance_info (utils.InstanceInfo): Wrapped instance info
            argument_infos (List[utils.ArgumentInfo]): Interested arguments info to be extract

        Returns:
            Dict[utils.RQElementName, Union[Job, Queue, Worker]]: Extracted Job, Queue and Worker
        """
        rq_input: Dict[utils.RQElementName, Union[Job, Queue, Worker]] = {}

        # Handle arguments from args / kwargs
        for arg_info in argument_infos:
            rq_element = utils._extract_value_from_input(
                argument_name=arg_info.name.value,
                argument_pos=arg_info.position,
                argument_type=arg_info.type,
                args=args,
                kwargs=kwargs,
            )

            if rq_element:
                rq_input[arg_info.name] = rq_element

        # Handle arguments from instance
        rq_input[instance_info.name] = instance

        return rq_input

    def link_job_dependencies(self, job: Job, span: trace.Span):
        """For `rq.queue.Queue.setup_dependencies` only

        Creating span links for job dependencies
        """
        dependencies = job.fetch_dependencies()
        for dependent in dependencies:
            dep_ctx = TraceContextTextMapPropagator().extract(carrier=dependent.meta)
            dep_span_ctx = trace.get_current_span(dep_ctx).get_span_context()
            span.add_link(dep_span_ctx)

    def __call__(self, func: Callable, instance: Any, args: Tuple, kwargs: Dict):
        """Trace instrumentaion"""
        # Extract RQ elements
        rq_input = self.extract_rq_input(
            instance, args, kwargs, self.instance_info, self.argument_info_list
        )
        job: Job = rq_input.get(utils.RQElementName.JOB, None)
        queue: Queue = rq_input.get(utils.RQElementName.QUEUE, None)

        # Early return if we can't
        # (1) Get Job Element
        # (2) When handling the outer layer of callback hook, but no such hook user given
        # (3) When Queue setting up job depenencies and there is no any job depends on
        callback_instrument_skip = "callback" in self.operation_name and not getattr(
            instance, self.operation_name
        )
        setup_dependencies_skip = (
            self.operation_name == "setup dependencies" and not len(job._dependency_ids)
        )
        if not job or callback_instrument_skip or setup_dependencies_skip:
            return func(*args, **kwargs)

        # Prepare metadata and parent context
        queue_name: str = queue.name if queue else ""
        span_name: str = self.get_span_name(queue_name)
        span_attributes: Dict[str, str] = self.get_attributes(rq_input)

        parent_context: trace.Context = self.propagator.extract(carrier=job.meta)
        span_context_manager = self.tracer.start_as_current_span(
            name=span_name,
            kind=self.span_kind,
            context=parent_context if parent_context else None,
        )

        # Span record
        span = span_context_manager.__enter__()
        if self.operation_name == "setup dependencies":
            self.link_job_dependencies(job, span)
        if self.should_propagate:
            self.propagator.inject(job.meta)
        if span.is_recording():
            span.set_attributes(span_attributes)
        try:
            response = func(*args, **kwargs)
            span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as exc:
            if span.is_recording():
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                span.record_exception(exception=exc)
            raise
        finally:
            span_context_manager.__exit__(None, None, None)

        # Force flush before fork process exited
        if self.should_flush:
            trace.get_tracer_provider().force_flush()

        return response
