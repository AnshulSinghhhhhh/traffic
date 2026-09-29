"""
sweep_dropout.py — Dropout rate sweep experiment for IDAHR.

Evaluates camera dropout rates: 0%, 10%, 20%, 30%, 40% across 5 random seeds each.
Computes:
1. Trajectory sequence accuracy (% strictly monotonic camera order).
2. Fraction of complete trajectories (% seeing all 4 cameras).
3. Travel-time error across edges (mean error in seconds, std deviation, and relative error %).

Outputs: paper_evidence/data/dropout_sweep.csv
"""

import json
import random
import copy
import csv
import os
import statistics
from datetime import datetime, timedelta

NOMINAL_OFFSETS = {
    ("CAM_01", "CAM_02"): 240.0,
    ("CAM_01", "CAM_03"): 560.0,
    ("CAM_01", "CAM_04"): 900.0,
    ("CAM_02", "CAM_03"): 320.0,
    ("CAM_02", "CAM_04"): 660.0,
    ("CAM_03", "CAM_04"): 340.0,
}

CAMERAS_BASE = [
    {"camera_id": "CAM_01", "name": "Junction A", "offset_s": 0},
    {"camera_id": "CAM_02", "name": "Ring Road North", "offset_s": 240},
    {"camera_id": "CAM_03", "name": "Market Circle", "offset_s": 560},
    {"camera_id": "CAM_04", "name": "Highway Toll", "offset_s": 900},
]

CAM_RANK = {"CAM_01": 0, "CAM_02": 1, "CAM_03": 2, "CAM_04": 3}
JITTER_SECONDS = 8.0

def run_simulation(base_events, dropout_rate, seed):
    random.seed(seed)
    camera_streams = {c["camera_id"]: [] for c in CAMERAS_BASE}
    all_events = []

    # Apply dropout & jitter
    for cam in CAMERAS_BASE:
        cid = cam["camera_id"]
        offset = cam["offset_s"]
        for base in base_events:
            # CAM_01 is ingress camera, but in sweep we test if all cameras experience dropout
            # or if CAM_01 has 0 and rest have rate. We test uniform dropout across downstream cameras (CAM_02..CAM_04)
            # or across all cameras. Here: CAM_02, CAM_03, CAM_04 experience dropout_rate.
            if cid != "CAM_01" and random.random() < dropout_rate:
                continue
            e = copy.deepcopy(base)
            base_ts = datetime.fromisoformat(e.get("timestamp", "2026-09-25T12:00:00"))
            jitter = random.uniform(-JITTER_SECONDS, JITTER_SECONDS)
            shifted_ts = base_ts + timedelta(seconds=offset + jitter)
            e["camera_id"] = cid
            e["timestamp"] = shifted_ts
            camera_streams[cid].append(e)
            all_events.append(e)

    # Group by plate
    plates = {e["plate"] for e in base_events}
    ordered_trajectories = 0
    complete_trajectories = 0
    edge_errors = []

    for p in plates:
        p_events = [e for e in all_events if e["plate"] == p]
        p_events.sort(key=lambda x: x["timestamp"])

        if not p_events:
            continue

        cams = [e["camera_id"] for e in p_events]
        # deduplicate consecutive identical cameras
        dedup_cams = [cams[i] for i in range(len(cams)) if i == 0 or cams[i] != cams[i-1]]
        ranks = [CAM_RANK[c] for c in dedup_cams]

        is_monotonic = all(ranks[i] < ranks[i+1] for i in range(len(ranks)-1))
        if is_monotonic:
            ordered_trajectories += 1

        if len(set(dedup_cams)) == 4:
            complete_trajectories += 1

        # Check travel times between consecutive hops
        for i in range(len(p_events) - 1):
            c1 = p_events[i]["camera_id"]
            c2 = p_events[i+1]["camera_id"]
            if c1 != c2:
                dt = (p_events[i+1]["timestamp"] - p_events[i]["timestamp"]).total_seconds()
                nominal = NOMINAL_OFFSETS.get((c1, c2))
                if nominal is not None:
                    err = dt - nominal
                    edge_errors.append(err)

    seq_acc = (ordered_trajectories / len(plates)) * 100.0 if plates else 0.0
    complete_frac = (complete_trajectories / len(plates)) * 100.0 if plates else 0.0
    mean_err = statistics.mean(edge_errors) if edge_errors else 0.0
    std_err = statistics.stdev(edge_errors) if len(edge_errors) > 1 else 0.0

    return {
        "dropout_rate": dropout_rate,
        "seed": seed,
        "total_plates": len(plates),
        "total_events": len(all_events),
        "seq_accuracy_pct": seq_acc,
        "complete_fraction_pct": complete_frac,
        "mean_travel_time_error_s": mean_err,
        "std_travel_time_error_s": std_err,
        "edge_observation_count": len(edge_errors)
    }

def main():
    with open("events.json", "r", encoding="utf-8") as f:
        base_events = json.load(f)

    dropout_rates = [0.0, 0.10, 0.20, 0.30, 0.40]
    seeds = [42, 101, 2024, 777, 9999]

    results = []
    print("=== DROPOUT SWEEP EXPERIMENT (IDAHR) ===")
    print(f"{'Dropout':<8} | {'Seed':<6} | {'Events':<6} | {'Seq Acc %':<10} | {'Complete %':<11} | {'Mean Err (s)':<13} | {'Std Err (s)'}")
    print("-" * 75)

    for dr in dropout_rates:
        for s in seeds:
            res = run_simulation(base_events, dr, s)
            results.append(res)
            print(f"{dr*100:<7.0f}% | {s:<6d} | {res['total_events']:<6d} | {res['seq_accuracy_pct']:<10.2f} | {res['complete_fraction_pct']:<11.2f} | {res['mean_travel_time_error_s']:<+13.2f} | {res['std_travel_time_error_s']:<10.2f}")

    os.makedirs("paper_evidence/data", exist_ok=True)
    out_csv = "paper_evidence/data/dropout_sweep.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print("\n--- DROPOUT SUMMARY (MEAN +/- STD OVER 5 SEEDS) ---")
    print(f"{'Dropout':<8} | {'Seq Acc Mean (Std)':<20} | {'Complete Frac Mean (Std)':<25} | {'Mean Time Error (s)'}")
    print("-" * 75)
    for dr in dropout_rates:
        dr_rows = [r for r in results if r["dropout_rate"] == dr]
        seqs = [r["seq_accuracy_pct"] for r in dr_rows]
        comps = [r["complete_fraction_pct"] for r in dr_rows]
        errs = [r["mean_travel_time_error_s"] for r in dr_rows]
        print(f"{dr*100:<7.0f}% | {statistics.mean(seqs):>6.2f}% ({statistics.stdev(seqs):.2f}%)   | {statistics.mean(comps):>6.2f}% ({statistics.stdev(comps):.2f}%)          | {statistics.mean(errs):>+6.2f}s")

if __name__ == "__main__":
    main()
