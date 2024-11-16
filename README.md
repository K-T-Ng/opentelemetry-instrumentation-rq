# Opentelemetry Instrumentation for `rq`
This library provides an OpenTelemetry Instrumentation library for Python RQ (Redis Queue). It enables distributed tracing and monitoring of tasks produced and processed by RQ workers, making it easier to gain insights into your application's performance and behavior.

🚧 This project is currently under active development. Some features may not yet be supported. 🚧

## Features
### Currently Supported
* Automatic tracing when
    * Task producing, via `rq.queue.Queue._enqueue`
    * Task execution, via `rq.worker.Worker.perform_job`
* Captures metadata task function, worker and queue name.

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
