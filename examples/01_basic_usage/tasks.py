"""Task function being called from RQ worker"""

import time


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
