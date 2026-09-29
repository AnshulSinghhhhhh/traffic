"""
benchmark_db_scaling.py — Empirical database query and indexing latency benchmark
at 10^4, 10^5, and 10^6 event row scales in PostgreSQL (Db10).

Uses an isolated benchmark table `events_benchmark` with identical schema and B-tree indexes
as production `events` (idx_events_plate, idx_events_timestamp, idx_events_camera_id).

Measures:
1. Single-row INSERT latency (including B-tree index updates).
2. Trajectory retrieval latency (SELECT WHERE plate = $1 ORDER BY timestamp).
3. Density aggregation query latency (COUNT GROUP BY camera_id WHERE timestamp >= window).
4. Table disk footprint / storage growth.

Outputs: paper_evidence/data/db_scaling_benchmark.csv
"""

import asyncio
import asyncpg
import time
import os
import csv
import statistics

DATABASE_URL = "postgresql://postgres:aniline12@localhost:5432/Db10"

TEST_SCALES = [10_000, 100_000, 1_000_000]

async def benchmark_scale(conn, target_rows):
    print(f"\n--- Testing DB Scale: N = {target_rows:,} rows ---")

    # 1. Reset benchmark table
    await conn.execute("DROP TABLE IF EXISTS events_benchmark CASCADE;")
    await conn.execute("""
        CREATE TABLE events_benchmark (
            event_id SERIAL PRIMARY KEY,
            camera_id TEXT NOT NULL,
            plate TEXT NOT NULL,
            track_id INTEGER,
            confidence DOUBLE PRECISION,
            timestamp TIMESTAMPTZ NOT NULL,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            vehicle_type TEXT,
            color TEXT
        );
        CREATE INDEX idx_eb_plate ON events_benchmark(plate);
        CREATE INDEX idx_eb_timestamp ON events_benchmark(timestamp);
        CREATE INDEX idx_eb_camera_id ON events_benchmark(camera_id);
    """)

    # 2. Populate with synthetic realistic traffic events using generate_series
    print(f"Generating {target_rows:,} rows via PostgreSQL set-returning generator...")
    t0 = time.perf_counter()
    await conn.execute(f"""
        INSERT INTO events_benchmark (camera_id, plate, track_id, confidence, timestamp, lat, lng, vehicle_type, color)
        SELECT 
            'CAM_0' || ((g % 4) + 1)::text,
            'PL' || lpad((g % 1000)::text, 5, '0'),
            (g % 500) + 1,
            0.50 + ((g % 50)::float / 100.0),
            NOW() - (g::text || ' seconds')::interval,
            12.9716 + ((g % 100)::float / 1000.0),
            77.5946 + ((g % 100)::float / 1000.0),
            CASE WHEN g % 4 = 0 THEN 'car' WHEN g % 4 = 1 THEN 'truck' WHEN g % 4 = 2 THEN 'bus' ELSE 'motorcycle' END,
            CASE WHEN g % 3 = 0 THEN 'blue' WHEN g % 3 = 1 THEN 'white' ELSE 'black' END
        FROM generate_series(1, {target_rows}) AS g;
    """)
    t1 = time.perf_counter()
    gen_time_s = t1 - t0
    print(f"Populated {target_rows:,} rows in {gen_time_s:.2f} seconds.")

    # Vacuum analyze to refresh planner statistics
    await conn.execute("ANALYZE events_benchmark;")

    # 3. Check table and index size
    table_bytes = await conn.fetchval("SELECT pg_total_relation_size('events_benchmark');")
    table_size_mb = table_bytes / (1024 * 1024)

    # 4. Benchmark Single-Row INSERT (50 repetitions)
    insert_latencies = []
    for i in range(50):
        t_ins0 = time.perf_counter()
        await conn.execute("""
            INSERT INTO events_benchmark (camera_id, plate, track_id, confidence, timestamp, lat, lng, vehicle_type, color)
            VALUES ('CAM_01', 'TEST_SCALE', 9999, 0.95, NOW(), 12.97, 77.59, 'car', 'blue');
        """)
        t_ins1 = time.perf_counter()
        insert_latencies.append((t_ins1 - t_ins0) * 1000.0)

    # 5. Benchmark Trajectory Query (SELECT WHERE plate = $1 ORDER BY timestamp) (50 repetitions)
    traj_latencies = []
    for i in range(50):
        test_plate = f"PL{str(i % 1000).zfill(5)}"
        t_tr0 = time.perf_counter()
        rows = await conn.fetch("""
            SELECT camera_id, timestamp, lat, lng
            FROM events_benchmark
            WHERE plate = $1
            ORDER BY timestamp ASC
        """, test_plate)
        t_tr1 = time.perf_counter()
        traj_latencies.append((t_tr1 - t_tr0) * 1000.0)

    # 6. Benchmark Density Aggregation Query (COUNT GROUP BY camera_id) (50 repetitions)
    density_latencies = []
    for i in range(50):
        t_den0 = time.perf_counter()
        rows = await conn.fetch("""
            SELECT camera_id, COUNT(*) as event_count
            FROM events_benchmark
            WHERE timestamp >= NOW() - INTERVAL '15 minutes'
            GROUP BY camera_id;
        """)
        t_den1 = time.perf_counter()
        density_latencies.append((t_den1 - t_den0) * 1000.0)

    p50_ins = statistics.median(insert_latencies)
    p95_ins = sorted(insert_latencies)[int(len(insert_latencies) * 0.95)]
    p50_traj = statistics.median(traj_latencies)
    p95_traj = sorted(traj_latencies)[int(len(traj_latencies) * 0.95)]
    p50_den = statistics.median(density_latencies)
    p95_den = sorted(density_latencies)[int(len(density_latencies) * 0.95)]

    print(f"Table Footprint: {table_size_mb:.2f} MB")
    print(f"Insert Latency:  p50={p50_ins:.2f}ms, p95={p95_ins:.2f}ms")
    print(f"Trajectory Query: p50={p50_traj:.2f}ms, p95={p95_traj:.2f}ms")
    print(f"Density Query:    p50={p50_den:.2f}ms, p95={p95_den:.2f}ms")

    return {
        "event_rows": target_rows,
        "table_size_mb": table_size_mb,
        "insert_p50_ms": p50_ins,
        "insert_p95_ms": p95_ins,
        "traj_query_p50_ms": p50_traj,
        "traj_query_p95_ms": p95_traj,
        "density_query_p50_ms": p50_den,
        "density_query_p95_ms": p95_den,
    }

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    results = []
    try:
        for scale in TEST_SCALES:
            res = await benchmark_scale(conn, scale)
            results.append(res)
    finally:
        print("\nCleaning up benchmark table...")
        await conn.execute("DROP TABLE IF EXISTS events_benchmark CASCADE;")
        await conn.close()

    os.makedirs("paper_evidence/data", exist_ok=True)
    out_csv = "paper_evidence/data/db_scaling_benchmark.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    print(f"\nSaved scaling benchmark to {out_csv}!")

if __name__ == "__main__":
    asyncio.run(main())
