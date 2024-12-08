"""A producer keep enqueuing job to RQ, 5 second per job"""

import logging
import time

from redis import Redis
from rq import Callback, Queue
from rq.command import send_stop_job_command

import tasks
from opentelemetry_setup import initialize

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.NOTSET,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    initialize(otlp_http_endpoint="http://localhost:4318")

    redis = Redis()
    queue = Queue("task_queue", connection=redis)

    # Both `job` & `success_callback` success
    # enqueue -> perform -> success_callback
    time.sleep(1)
    job = queue.enqueue(
        tasks.task_normal, on_success=Callback(tasks.success_callback_normal)
    )

    # `job` success but `success_callback` with exception
    # enqueue -> perform -> success_callback -> failure_callback
    time.sleep(1)
    job = queue.enqueue(
        tasks.task_normal,
        on_success=Callback(tasks.success_callback_exception),
        on_failure=Callback(tasks.failure_callback_normal),
    )

    # `job` failed, `failure_callback` success
    # enqueue -> perform -> failure_callback
    time.sleep(1)
    job = queue.enqueue(
        tasks.task_error,
        on_failure=Callback(tasks.failure_callback_normal),
    )

    # Both `job` and `failure_callback` failed
    # enqueue -> perform -> failure_callback (with error detected)
    time.sleep(1)
    job = queue.enqueue(
        tasks.task_error,
        on_failure=Callback(tasks.failure_callback_exception),
    )

    # `job` stopped, `stopped_callback` success
    # enqueue -> stopped_callback
    time.sleep(1)
    job = queue.enqueue(
        tasks.task_delay, on_stopped=Callback(tasks.stopped_callback_normal)
    )
    time.sleep(1)  # `task_delay` sleeps 3 seconds, we sleep 1 second and stop it
    send_stop_job_command(redis, job.id)
