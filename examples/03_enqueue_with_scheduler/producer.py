"""A producer keep enqueuing job to RQ, 5 second per job"""

import logging
from datetime import datetime, timedelta

from redis import Redis
from rq import Queue

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

    # Schedule job using `enqueue_in`
    job = queue.enqueue_in(time_delta=timedelta(seconds=3), func=tasks.task_normal)

    # Schedule job using `enqueue_at`
    enqueue_at = datetime.now() + timedelta(seconds=3)
    job = queue.enqueue_at(datetime=enqueue_at, f=tasks.task_normal)
