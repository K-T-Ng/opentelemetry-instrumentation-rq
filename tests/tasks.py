"""Functions used as RQ tasks/callback for testing"""

import time


class CustomException(Exception):
    pass


def task_normal():
    """Normal task function"""
    print("Hello world")


def task_exception():
    """Abnormal task function"""
    raise CustomException("Unexpected error")


def task_unstopped():
    """Task function never stopped"""
    while True:
        time.sleep(10)


def success_callback(job, connection, result, *args, **kwargs):
    """Callback function after task success"""
    print("Success callback")


def success_callback_exception(job, connection, result, *args, **kwargs):
    """Callback function after task success, but with exception"""
    raise CustomException("Unexpected error during success callback")


def failure_callback(job, connection, type, value, traceback):
    """Callback function after task failed"""
    print("Failure callback")


def failure_callback_exception(job, connection, type, value, traceback):
    """Callback function after task failed, but with exception"""
    raise CustomException("Unexpected error during failure callback")


def stopped_callback(job, connection):
    """Callback function after task stopped"""
    print("Stopped callback")
