import asyncio
import aiohttp
import os
import json
import time
import argparse
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def run_benchmark(api_key, endpoint_id, payload, concurrency, num_requests, gpu_price_per_hour):
    url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # RunPod serverless typically has a status check flow, but for sync vs async:
    # If we use /run, it returns an ID, then we poll /status.
    # If we use /runsync, it holds connection. 
    # For benchmarking efficiency and realistic usage, we often use /run and poll.
    # However, to measure "latency" from client perspective, /runsync is good if tasks are short.
    # If tasks are long, /run + polling is better.
    # We will assume /runsync for simpler latency measurement if supported, OR handle /run + poll.
    # Let's check status. USUALLY /runsync is the standard for low latency apps.
    
    # We will try /runsync first. If the user wants async, we can switch. 
    # Let's support both but default to /runsync for benchmarking "fast" inference.
    
    url_sync = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    
    results = []

    async def worker(session, queue):
        while not queue.empty():
            req_id = await queue.get()
            start_time = time.time()
            try:
                # We use runsync for direct latency measurement
                async with session.post(url_sync, headers=headers, json={"input": payload}, timeout=300) as response:
                    resp_json = await response.json()
                    end_time = time.time()
                    
                    # Extract metrics from RunPod response if available
                    # Typical response: {"id":..., "status": "COMPLETED", "output": ..., "executionTime": 100, "delayTime": 20}
                    # executionTime is in ms
                    
                    latency = (end_time - start_time) * 1000 # to ms
                    execution_time = resp_json.get("executionTime", 0)
                    delay_time = resp_json.get("delayTime", 0) # Queue time
                    
                    status = resp_json.get("status", "UNKNOWN")
                    
                    # Calculate cost
                    # Price per hour / 3600 = price per second.
                    # execution time is in ms. -> /1000 to seconds.
                    cost = (execution_time / 1000) * (gpu_price_per_hour / 3600)
                    
                    results.append({
                        "id": req_id,
                        "latency_ms": latency,
                        "execution_ms": execution_time,
                        "delay_ms": delay_time,
                        "status": status,
                        "cost": cost
                    })
                    print(f"Request {req_id} completed. Latency: {latency:.2f}ms, Cost: ${cost:.6f}")
                    
            except Exception as e:
                print(f"Request {req_id} failed: {e}")
                results.append({
                    "id": req_id,
                    "error": str(e),
                    "status": "FAILED"
                })
            finally:
                queue.task_done()

    queue = asyncio.Queue()
    for i in range(num_requests):
        queue.put_nowait(i)

    print(f"Starting benchmark with {concurrency} concurrency, {num_requests} total requests...")
    
    start_bench = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(worker(session, queue)) for _ in range(concurrency)]
        await queue.join()
        for task in tasks:
            task.cancel()
            
    total_time = time.time() - start_bench
    
    # Process results
    latencies = [r["latency_ms"] for r in results if "latency_ms" in r]
    exec_times = [r["execution_ms"] for r in results if "execution_ms" in r]
    delay_times = [r["delay_ms"] for r in results if "delay_ms" in r]
    costs = [r["cost"] for r in results if "cost" in r]
    
    if not latencies:
        print("No successful requests.")
        return

    # Metrics
    p50_lat = np.percentile(latencies, 50)
    p95_lat = np.percentile(latencies, 95)
    p99_lat = np.percentile(latencies, 99)
    avg_lat = np.mean(latencies)
    avg_exec = np.mean(exec_times)
    avg_delay = np.mean(delay_times)
    throughput = len(latencies) / total_time
    total_cost = sum(costs)
    avg_cost = np.mean(costs)

    print("\n--- Benchmark Results ---")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Total Requests: {num_requests}")
    print(f"Successful Requests: {len(latencies)}")
    print(f"Throughput: {throughput:.2f} req/s")
    
    print("\n--- Latency (End-to-End) ---")
    print(f"P50: {p50_lat:.2f} ms")
    print(f"P95: {p95_lat:.2f} ms")
    print(f"P99: {p99_lat:.2f} ms")
    print(f"Avg: {avg_lat:.2f} ms")
    
    print("\n--- Execution Time (Server Side) ---")
    print(f"Avg: {avg_exec:.2f} ms")
    print(f"P95: {np.percentile(exec_times, 95):.2f} ms")

    print("\n--- Cold Start / Queue Time (Delay) ---")
    print(f"Avg: {avg_delay:.2f} ms")
    print(f"Max: {np.max(delay_times):.2f} ms")
    
    print("\n--- Cost Estimation ---")
    print(f"Total Estimated Cost: ${total_cost:.6f}")
    print(f"Avg Cost per Request: ${avg_cost:.6f}")

    # Append to CSV
    csv_file = "benchmark_summary.csv"
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, mode="a") as f:
        if not file_exists:
            f.write("GPU_Name,EndpointID,GPU_Price,Concurrency,Requests,Throughput(req/s),Latency_P50(ms),Latency_P95(ms),Avg_Exec(ms),Avg_Delay(ms),Avg_Cost($)\n")
        f.write(f"{gpu_name},{endpoint_id},{gpu_price_per_hour},{concurrency},{num_requests},{throughput:.2f},{p50_lat:.2f},{p95_lat:.2f},{avg_exec:.2f},{avg_delay:.2f},{avg_cost:.6f}\n")
    print(f"\nResults appended to {csv_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RunPod Serverless Benchmark")
    parser.add_argument("--api-key", help="RunPod API Key (or set RUNPOD_API_KEY env var)")
    parser.add_argument("--endpoint-id", help="Endpoint ID (or set ENDPOINT_ID env var)")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent requests")
    parser.add_argument("--requests", type=int, default=10, help="Total number of requests")
    parser.add_argument("--input", default='{"prompt": "Hello world"}', help="Input JSON payload string")
    parser.add_argument("--price", type=float, default=0.2, help="GPU Price per hour for cost est. (default 0.2)")
    parser.add_argument("--gpu-name", default="Unknown_GPU", help="Name of the GPU being tested")
    
    args = parser.parse_args()
    
    api_key = args.api_key or os.getenv("RUNPOD_API_KEY")
    endpoint_id = args.endpoint_id or os.getenv("ENDPOINT_ID")
    price = float(os.getenv("GPU_PRICE_PER_HOUR", args.price))
    
    if not api_key or not endpoint_id:
        print("Error: API Key and Endpoint ID are required.")
        exit(1)
        
    try:
        payload = json.loads(args.input)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input")
        exit(1)
        
    asyncio.run(run_benchmark(api_key, endpoint_id, payload, args.concurrency, args.requests, price, args.gpu_name))
