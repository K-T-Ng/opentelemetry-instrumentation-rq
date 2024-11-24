# Examples

This folder contains example use cases for the `opentelemetry_instrumentation_rq` library. Each sub-folder demonstrates a specific use case. Before you explore these examples, you may need to initialize Redis and other Observability backend listed below by following the steps below.

## Description

The `environment/docker-compose.yaml` file includes several components, as described in the table below:

| Service           | Description                                          | Ports Exposed       |
|-------------------|------------------------------------------------------|---------------------|
| `redis`           | Backend for Python RQ                                | `6379:6379`         |
| `otel-collector`  | Collects tracing and logging data from examples      | `4317:4317`, `4318:4318` |
| `jaeger-all-in-one`| Acting Jaeger Collector and Query. Receives and Show tracing data from the `otel-collector`      | `16686:16686`, `4317`, `4318`      |

## Quick Start
1. **Launch the stack:**
   Use Docker Compose to start all the services:

    ```bash
    cd environment
    docker compose up -d
    cd ..
    ```

2. **Access Jaeger Query UI:**
   Open a web browser and navigate to [http://localhost:16686](http://localhost:16686).

## Shutdown

To clean up and stop all running services:

```bash
cd environment
docker compose down --remove-orphans
cd ..
```
