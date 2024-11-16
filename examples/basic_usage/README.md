# Basic Usage

This example demonstrates the basic usage of the `opentelemetry_instrumentation_rq` library.

## Description

- **`opentelemetry_setup.py`**: Configures the tracer and initializes the `RQInstrumentor`.
- **`tasks.py`**: Defines a task function with a 1/3 probability of success, delay, or error.
- **`producer.py`**: Produces a task to Redis every 10 seconds.
- **`worker.py`**: Listens to the queue and consumes tasks.

## Quick Start

1. **Install required packages:**

    ```bash
    pip install -r requirements.txt
    ```

2. **Set up Redis and the observability backend playground:**
   Navigate to the `examples/` directory and run the following command if Redis and the observability backend are not set up yet:

    ```bash
    docker compose up -d
    ```

3. **Launch `worker` and `producer` in separate terminals:**

    ```bash
    # Terminal A
    python -m producer

    # Terminal B
    python -m worker
    ```

4. **View metrics in Grafana:**
   Open a web browser and visit [http://localhost:3000](http://localhost:3000). Then, navigate to **Dashboards > Dashboards > basic-usage** to access the dashboard.
