"""
load_test_backend.py — Concurrent client load test harness for IDAHR POST /events endpoint.

Evaluates throughput (events/s), latency percentiles (p50, p95, p99), and error rate
across concurrent client counts: 1, 5, 10, 50, 100.

Usage:
    # Ensure backend is running: uvicorn app.main:app --port 8000
    python paper_evidence/load_test_backend.py --url http://localhost:8000/events --requests-per-client 20
"""

import asyncio
import httpx
import time
import statistics
import argparse
import csv
import os

CONCURRENCY_LEVELS = [1, 5, 10, 50, 100]

async def send_worker(client, url, num_requests, worker_id, results):
    for i in range(num_requests):
        payload = {
            "camera_id": f"CAM_0{(worker_id % 4) + 1}",
            "plate": f"LOAD{worker_id:03d}",
            "track_id": worker_id * 1000 + i,
            "confidence": 0.85,
            "timestamp": "2026-09-25T14:30:00Z",
            "lat": 12.9716,
            "lng": 77.5946,
            "vehicle_type": "car",
            "color": "blue"
        }
        t0 = time.perf_counter()
        try:
            resp = await client.post(url, json=payload, timeout=10.0)
            t1 = time.perf_counter()
            lat_ms = (t1 - t0) * 1000.0
            results.append((lat_ms, resp.status_code))
        except Exception as e:
            t1 = time.perf_counter()
            lat_ms = (t1 - t0) * 1000.0
            results.append((lat_ms, 500))

async def run_load_level(url, concurrency, reqs_per_client):
    results = []
    total_reqs = concurrency * reqs_per_client
    limits = httpx.Limits(max_keepalive_connections=concurrency + 5, max_connections=concurrency + 10)
    
    t0 = time.perf_counter()
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [
            send_worker(client, url, reqs_per_client, w_id, results)
            for w_id in range(concurrency)
        ]
        await asyncio.gather(*tasks)
    t1 = time.perf_counter()

    wall_clock_s = t1 - t0
    throughout_eps = total_reqs / wall_clock_s if wall_clock_s > 0 else 0.0

    latencies = [r[0] for r in results]
    successes = [r for r in results if r[1] in (200, 201)]
    error_count = total_reqs - len(successes)
    error_rate_pct = (error_count / total_reqs) * 100.0 if total_reqs > 0 else 0.0

    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    mean_lat = statistics.mean(latencies) if latencies else 0.0

    print(f"Concurrency: {concurrency:3d} clients | Total: {total_reqs:4d} reqs | Throughput: {throughout_eps:6.1f} evt/s | p50: {p50:5.2f}ms | p95: {p95:5.2f}ms | p99: {p99:5.2f}ms | Err: {error_rate_pct:.1f}%")

    return {
        "concurrency": concurrency,
        "total_requests": total_reqs,
        "throughput_events_per_s": throughout_eps,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "mean_latency_ms": mean_lat,
        "error_count": error_count,
        "error_rate_pct": error_rate_pct
    }

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/events")
    parser.add_argument("--reqs", type=int, default=20)
    parser.add_argument("--output", default="paper_evidence/data/central_service_load_test.csv")
    args = parser.parse_args()

    print("=== CENTRAL SERVICE CONCURRENT LOAD TEST (POST /events) ===")
    print(f"Target URL: {args.url}")
    print(f"Requests per client worker: {args.reqs}")
    print("-" * 80)

    rows = []
    for c in CONCURRENCY_LEVELS:
        try:
            res = await run_load_level(args.url, c, args.reqs)
            rows.append(res)
        except Exception as e:
            print(f"Failed at concurrency {c}: {e}")
            break

    if rows:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        print(f"\nSaved load test results to {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
