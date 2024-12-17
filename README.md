# Opentelemetry Instrumentation for `rq`
This library provides an OpenTelemetry Instrumentation library for Python RQ (Redis Queue). It enables distributed tracing and monitoring of tasks produced and processed by RQ workers, making it easier to gain insights into your application's performance and behavior.

🚧 This project is currently under active development. Some features may not yet be supported. 🚧

## Features
### Currently Supported
Automatic tracing when
* Task producing, via `rq.queue.Queue._enqueue`
* Task execution, via `rq.job.Job.perform`
* Callback function execution after a job succeeds, fails, or stops, via `rq.job.Job.execute_*_callback`

### Planned
- [ ] Enqueue Tracing
    - [ ] Support span linking for job dependencies.
    - [x] Add tracing for `rq.queue.Queue._enqueue` (not worked for schedlue job).
    - [x] Add support for enqueue functions used by the RQ scheduler.
- [x] Consumer Tracing
    - [x] Add tracing for the outer layer `rq.worker.Worker.perform_job` to visualize the execution time for the entire fork process.
    - [x] Add tracing for the inner layer `rq.job.Job.perform`.
    - [x] Add tracing for the inner layer `handle_job_*`  to visualize post-processing after job execution.
- [ ] Improved Clarity
    - [ ] Refine span names and attributes for better readability and understanding.
- [ ] Adjust the dependencies version by testing the lower limit by github action.

## Installation
Install this package with `pip`:
```
pip install opentemeletry_instrumentation_rq
```

## Usage
### Automatic Instrumentation
In your RQ producer or worker code, initialize the OpenTelemetry RQ instrumentation:
```python
from opentelemetry_instrumentation_rq import RQInstrumentor

RQInstrumentator().instrument()
```

## License
This project is licensed under the [MIT License](./LICENSE).
