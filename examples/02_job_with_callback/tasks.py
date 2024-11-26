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


def success_callback_normal(job, connection, result, *args, **kwargs):
    """Normal success callback, without exception"""
    print(
        f"Normal success callback with parameter {job=} {connection=} {result=} {args=} {kwargs=}"
    )


def success_callback_exception(job, connection, result, *args, **kwargs):
    """Normal success callback, with exception"""
    print(
        f"Abnormal success callback with parameter {job=} {connection=} {result=} {args=} {kwargs=}"
    )
    raise CustomException("Unexpected error in success callback")


def failure_callback_normal(job, connection, type, value, traceback):
    """Normal failure callback, without exception"""
    print(
        f"Normal failure callback with parameter {job=} {connection=} {type=} {value=} {traceback=}"
    )


def failure_callback_exception(job, connection, type, value, traceback):
    """Normal failure callback, with exception"""
    print(
        f"Abnormal failure callback with parameter {job=} {connection=} {type=} {value=} {traceback=}"
    )
    raise CustomException("Unexpected error in failure callback")


def stopped_callback_normal(job, connetion):
    """Normal stopped callback, without exception"""
    print(f"Normal stopped callback wiht parameter {job=} {connetion=}")


def stopped_callback_exception(job, connetion):
    """Normal stopped callback, with exception"""
    print(f"Abnormal stopped callback wiht parameter {job=} {connetion=}")
    raise CustomException("Unexpected error in stopped callback")
