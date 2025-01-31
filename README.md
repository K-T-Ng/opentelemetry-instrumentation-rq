# Opentelemetry Instrumentation for `rq`
This library provides an OpenTelemetry Instrumentation library for Python RQ (Redis Queue). It enables distributed tracing and monitoring of tasks produced and processed by RQ workers, making it easier to gain insights into your application's performance and behavior.

## Supported Features
Automatic tracing when
* Task producing, via `rq.queue.Queue._enqueue` or `rq.queue.Queue.schedule_job`
* Task execution, via `rq.worker.Worker.perform_job`, `rq.job.Job.perform`
* Span link between jobs which have dependencies (i.e, produce with `queue.enqueue(f, depends_on=xxx)`)
* Callback function execution after a job succeeds, fails, or stops, via `rq.job.Job.execute_*_callback`

## Installation
Install this package with `pip`:
```
pip install opentemeletry_instrumentation_rq
```

## Usage
### Quick Start
In your RQ producer or worker code, initialize the OpenTelemetry RQ instrumentation:
```python
from opentelemetry_instrumentation_rq import RQInstrumentor

RQInstrumentator().instrument()
```

### Additional Scenarios
For more use cases, refer to the tests in `tests/e2e_test`. You can launch an RQ worker using `tests/e2e_test/simulator/worker.py` and execute producer commands from `tests/e2e_test/test_simulation.py`.

## License
This project is licensed under the [MIT License](./LICENSE).
