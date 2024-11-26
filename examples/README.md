# Examples

This folder contains example use cases for the `opentelemetry_instrumentation_rq` library. Each sub-folder demonstrates a specific scenario. Before exploring these examples, ensure that Redis and the necessary observability backends are initialized by following the instructions below.

## Description

The `environment/docker-compose.yaml` file defines the following components:

| **Service**       | **Description**                                      | **Exposed Ports**       |
|--------------------|------------------------------------------------------|-------------------------|
| `redis`           | Serves as the backend for Python RQ                  | `6379:6379`             |
| `otel-collector`  | Collects tracing and logging data from examples       | `4317:4317`, `4318:4318` |
| `jaeger-all-in-one` | Acts as both Jaeger Collector and Query. Receives and displays tracing data from the `otel-collector`. | `16686:16686`, `4317`, `4318` |

## Quick Start

1. **Launch the stack**
   Use Docker Compose to start all required services:

   ```bash
   cd environment
   docker compose up -d
   cd ..

2. **Access Jaeger Query UI**
   Open a web browser and navigate to [http://localhost:16686](http://localhost:16686).

## Running Examples
Each example is located in a sub-folder prefixed with a number. To run an example, use two terminal sessions:
1. In Terminal A, start the worker:
```
python -m worker
```
2. In Terminal B, run the producer:
```
python -m producer
```

## Shutdown

To stop all running services and clean up:

```bash
cd environment
docker compose down --remove-orphans
cd ..
```
