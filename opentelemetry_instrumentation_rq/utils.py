"""Utils for building instrumentation data"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from rq.job import Job
from rq.queue import Queue
from rq.worker import Worker


def _extract_value_from_input(
    argument_name: str,
    argument_pos: Optional[int],
    argument_type: Any,
    args: Tuple,
    kwargs: Dict,
):
    """Extract function input from wrapped function"""

    value_from_kwargs = kwargs.get(argument_name, None)
    if (
        value_from_kwargs
        or not isinstance(argument_pos, int)
        or len(args) <= argument_pos
    ):
        return value_from_kwargs

    value_from_args = args[argument_pos]
    if not isinstance(value_from_args, argument_type):
        return None
    return value_from_args


class RQElementName(Enum):
    JOB = "job"
    QUEUE = "queue"
    WORKER = "worker"


PREDEFINED_ELEMENT_TYPE_MAP = {
    RQElementName.JOB: Job,
    RQElementName.QUEUE: Queue,
    RQElementName.WORKER: Worker,
}


@dataclass(frozen=True)
class ArgumentInfo:
    name: RQElementName
    position: Optional[int]
    type: Any


def get_argument_info(element_name: RQElementName, position: int = 0):
    """Get wrapper argument (args/kwargs) info"""

    return ArgumentInfo(
        name=element_name,
        position=position,
        type=PREDEFINED_ELEMENT_TYPE_MAP.get(
            element_name, type(None)
        ),  # Avoid calling types other than predefined
    )


@dataclass(frozen=True)
class InstanceInfo:
    name: RQElementName
    type: Any


def get_instance_info(element_name: RQElementName) -> InstanceInfo:
    """Get wrapper function instance info"""

    return InstanceInfo(
        name=element_name,
        type=PREDEFINED_ELEMENT_TYPE_MAP.get(element_name, type(None)),
    )  # Avoid calling types other than predefined
