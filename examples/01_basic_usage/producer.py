"""A producer keep enqueuing job to RQ, 5 second per job"""

import logging
import time

from opentelemetry_setup import initialize
from redis import Redis
from rq import Queue
from tasks import task_delay, task_error, task_normal

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.NOTSET,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    initialize(otlp_http_endpoint="http://localhost:4318")

    redis = Redis()
    queue = Queue("task_queue", connection=redis)

    time.sleep(1)
    job = queue.enqueue(task_normal)

    time.sleep(1)
    job = queue.enqueue(task_error)

    time.sleep(1)
    job = queue.enqueue(task_delay)
