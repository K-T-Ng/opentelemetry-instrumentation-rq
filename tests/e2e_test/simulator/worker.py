"""Simulate RQ worker"""

from redis import Redis
from rq import Queue, Worker

from tests.e2e_test.simulator.otel_setup import initialize

if __name__ == "__main__":
    initialize(otlp_http_endpoint="http://localhost:4318")

    redis = Redis(host="localhost", port=6379)
    queue = Queue("test_queue", connection=redis)

    worker = Worker([queue], connection=redis, name="test_worker")
    worker.work(with_scheduler=True)
