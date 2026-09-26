import time
import requests
import statistics
import json

session = requests.Session()
BASE_URL = "http://localhost:8000"

routes = [
    ("POST /events", "POST", f"{BASE_URL}/events", {
        "plate": "BENCH_01",
        "camera_id": "CAM_01",
        "timestamp": "2026-09-25T14:30:00Z",
        "confidence": 0.95,
        "track_id": 999,
        "lat": 12.9716,
        "lng": 77.5946
    }),
    ("GET /cameras", "GET", f"{BASE_URL}/cameras", None),
    ("GET /vehicle/{plate}", "GET", f"{BASE_URL}/vehicle/BG65USJ", None),
    ("GET /trajectory/{plate}", "GET", f"{BASE_URL}/trajectory/BG65USJ", None),
    ("GET /traffic/density", "GET", f"{BASE_URL}/traffic/density?window=60", None),
    ("GET /traffic/congestion", "GET", f"{BASE_URL}/traffic/congestion?window=60", None),
    ("GET /alerts", "GET", f"{BASE_URL}/alerts", None),
]

N = 60
results = {}

# Warm up
for name, method, url, data in routes:
    if method == "POST":
        session.post(url, json=data)
    else:
        session.get(url)

print(f"Running {N} requests per route...")
for name, method, url, data in routes:
    latencies = []
    for i in range(N):
        t0 = time.perf_counter()
        if method == "POST":
            # Vary timestamp so it simulates new events
            payload = dict(data)
            payload["timestamp"] = f"2026-09-25T14:30:{i:02d}Z"
            resp = session.post(url, json=payload)
        else:
            resp = session.get(url)
        t1 = time.perf_counter()
        if resp.status_code in (200, 201):
            latencies.append((t1 - t0) * 1000.0)  # ms
        else:
            print(f"Failed {name}: {resp.status_code}")
    
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    mean_val = statistics.mean(latencies)
    min_val = min(latencies)
    max_val = max(latencies)
    results[name] = {
        "n": len(latencies),
        "min": min_val,
        "median": p50,
        "p95": p95,
        "p99": p99,
        "mean": mean_val,
        "max": max_val
    }
    print(f"{name:25s} | N={len(latencies)} | Min={min_val:.2f}ms | Median={p50:.2f}ms | p95={p95:.2f}ms | Mean={mean_val:.2f}ms")

with open("benchmark_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nBenchmark completed and saved to benchmark_results.json!")
