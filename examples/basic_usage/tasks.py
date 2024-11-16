"""Task functions being called from RQ worker"""

import logging
import random
import time
from typing import Callable, List


def print_hello_world():
    """Just print hello word"""
    logging.info("Executing print_hello_word")
    print("Hello world")


def print_hello_world_with_delay():
    """Delay 3 seconds and print hello world"""
    logging.warn("Program delay due to sleeping")
    time.sleep(3)
    print_hello_world()


def raise_error():
    """Just raise an error"""
    logging.error("Unexpected error")
    raise Exception("Unexpected error")


def task():
    """A task function with...
    - 1/3 probability print hello world directly
    - 1/3 probability print hello world with 3 seconds delay
    - 1/3 probability raise an error
    """
    trigger_functions: List[Callable] = [
        print_hello_world,
        print_hello_world_with_delay,
        raise_error,
    ]
    trigger_function: List[Callable] = random.choices(
        trigger_functions, weights=[1, 1, 1]
    )
    trigger_function: Callable = trigger_function[0]
    trigger_function()


if __name__ == "__main__":
    task()
