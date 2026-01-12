# RunPod Serverless Benchmark

This tool benchmarks the performance, cost, and efficiency of your RunPod Serverless endpoints.

## Features

- **Latency Measurement**: End-to-end latency (P50, P95, P99), server execution time, and cold start/queue delays.
- **Cost Estimation**: Estimates run cost based on GPU hourly price and execution duration.
- **Throughput/Efficiency**: Measures successful requests per second.
- **Concurrency**: Stress test with concurrent requests.

## Setup

1. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Rename `.env.example` to `.env` and fill in your details:
   ```env
   RUNPOD_API_KEY=your_key
   ENDPOINT_ID=your_id
   GPU_PRICE_PER_HOUR=0.2  # e.g., $0.20/hr for generic low-end GPU
   ```

## Usage

Run the benchmark script:

```bash
python benchmark.py --help
```

### Example Command

```bash
python benchmark.py --concurrency 10 --requests 50 --input '{"prompt": "test"}'
```

### Arguments

- `--api-key`: RunPod API Key (optional if in env)
- `--endpoint-id`: Endpoint ID (optional if in env)
- `--concurrency`: Number of simultaneous requests (default: 5)
- `--requests`: Total requests to run (default: 10)
- `--input`: JSON payload string (default: `"{\"prompt\": \"Hello world\"}"`)
- `--price`: GPU Price per hour (default: 0.2)
