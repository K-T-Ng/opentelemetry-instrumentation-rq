"""A producer keep enqueuing job to RQ"""

import logging
import time

from opentelemetry_setup import initialize
from redis import Redis
from rq import Queue
from tasks import task

if __name__ == "__main__":
    logging.basicConfig(level=logging.NOTSET)
    initialize(
        otlp_http_endpoint="http://localhost:4318", logger_names=("root", __name__)
    )

    redis = Redis()
    queue = Queue("task_queue", connection=redis)

    while True:
        job = queue.enqueue(task)
        time.sleep(10)
