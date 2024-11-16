# Examples

This folder contains example use cases for the `opentelemetry_instrumentation_rq` library. Each sub-folder demonstrates a specific use case. Before you explore these examples, you may need to initialize Redis and other Observability backend listed below by following the steps below.

## Description

The `docker-compose.yaml` file includes several components, as described in the table below:

| Service           | Description                                          | Ports Exposed       |
|-------------------|------------------------------------------------------|---------------------|
| `redis`           | Backend for Python RQ                               | `6379:6379`         |
| `otel-collector`  | Collects tracing and logging data from examples      | `4317:4317`, `4318:4318` |
| `jaeger-collector`| Receives tracing data from the `otel-collector`      | `4317`, `4318`      |
| `elasticsearch`   | Stores tracing and logging data                     | `9200`              |
| `jaeger-query`    | Query service for tracing data                      |                     |
| `grafana`         | Visualization tool for multiple databases           | `3000:3000`         |

## Quick Start

1. **Launch the stack:**
   Use Docker Compose to start all the services:

    ```bash
    docker compose up -d
    ```

2. **Access Grafana:**
   Open a web browser and navigate to [http://localhost:3000](http://localhost:3000).
   Log in using the credentials:
   **Username:** `admin`
   **Password:** `CHANGEME`

## Shutdown

To clean up and stop all running services:

```bash
docker compose down --remove-orphans
