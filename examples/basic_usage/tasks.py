"""Task function being called from RQ worker"""

import random
import time
from typing import Callable, List


class CustomException(Exception):
    pass


def task_normal():
    """Just print hello word"""
    print("Hello world")


def task_delay():
    """Delay 3 seconds and print hello world"""
    time.sleep(3)
    print("Hello world")


def task_error():
    """Just raise an error"""
    raise CustomException("Unexpected error")


def task():
    """A task function with...
    - 1/3 probability print hello world directly
    - 1/3 probability print hello world with 3 seconds delay
    - 1/3 probability raise an error
    """
    trigger_function: List[Callable] = random.choices(
        population=[task_normal, task_delay, task_error], weights=[1, 1, 1]
    )[0]

    trigger_function()


if __name__ == "__main__":
    task()
