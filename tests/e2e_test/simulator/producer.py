"""Simulate producer behavior"""

import time

from redis import Redis
from rq import Queue

from tests.e2e_test.simulator.otel_setup import initialize
from tests import tasks

if __name__ == "__main__":
    initialize(otlp_http_endpoint="http://localhost:4318")

    redis = Redis()
    queue = Queue(name="test_queue", connection=redis)

    time.sleep(1)
    job = queue.enqueue(tasks.task_normal)
