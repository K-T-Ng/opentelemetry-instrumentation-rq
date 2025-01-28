"""Test case definition"""
from typing import Callable
from dataclasses import dataclass

from rq import Queue

@dataclass(frozen=True)
class TestCase:
    name: str
    description: str
    producer: Callable[[Queue], None]
    expected: Callable
