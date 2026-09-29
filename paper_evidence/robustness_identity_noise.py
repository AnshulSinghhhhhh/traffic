"""
robustness_identity_noise.py — Evaluates trajectory tracking robustness against synthetic OCR identity noise.

Injects synthetic character mutations (substitutions) at rates: 0%, 5%, 10%, 15%, 20%, 25%, 30% across 5 seeds.
Measures:
1. False stitches: Different ground-truth vehicles merged under the same plate identity.
2. Fragmented trajectories: Ground-truth vehicles whose cross-camera trajectory was broken/fragmented into singleton sightings.
3. Effective trajectory continuity: Average path length per true vehicle (maximum is 4 cameras).

Outputs: paper_evidence/data/identity_noise_robustness.csv
"""

import json
import random
import copy
import csv
import os
import statistics
import string
from collections import defaultdict
from datetime import datetime, timedelta

CAMERAS_BASE = [
    {"camera_id": "CAM_01", "offset_s": 0},
    {"camera_id": "CAM_02", "offset_s": 240},
    {"camera_id": "CAM_03", "offset_s": 560},
    {"camera_id": "CAM_04", "offset_s": 900},
]
JITTER_SECONDS = 8.0

def mutate_plate(plate, num_substitutions=1):
    if not plate:
        return plate
    chars = list(plate)
    for _ in range(num_substitutions):
        idx = random.randint(0, len(chars) - 1)
        if chars[idx].isdigit():
            chars[idx] = random.choice([d for d in string.digits if d != chars[idx]])
        else:
            chars[idx] = random.choice([c for c in string.ascii_uppercase if c != chars[idx]])
    return "".join(chars)

def run_noise_experiment(base_events, noise_rate, seed):
    random.seed(seed)
    # Generate 4-camera events
    all_events = []
    for cam in CAMERAS_BASE:
        cid = cam["camera_id"]
        offset = cam["offset_s"]
        for base in base_events:
            e = copy.deepcopy(base)
            base_ts = datetime.fromisoformat(e.get("timestamp", "2026-09-25T12:00:00"))
            jitter = random.uniform(-JITTER_SECONDS, JITTER_SECONDS)
            e["timestamp"] = base_ts + timedelta(seconds=offset + jitter)
            e["camera_id"] = cid
            e["true_vehicle_id"] = e.get("track_id")
            
            # Apply identity noise: with probability `noise_rate`, mutate plate
            if random.random() < noise_rate:
                e["plate"] = mutate_plate(e["plate"])
                e["is_mutated"] = True
            else:
                e["is_mutated"] = False
            all_events.append(e)

    # Ingestion / Graph Stitching: Group by emitted `plate`
    stitched_trajectories = defaultdict(list)
    for e in all_events:
        stitched_trajectories[e["plate"]].append(e)

    # 1. Check False Stitches: Does any stitched plate contain events from MORE than one true_vehicle_id?
    false_stitches = 0
    merged_vehicle_pairs = set()
    for plate, evs in stitched_trajectories.items():
        vids = {e["true_vehicle_id"] for e in evs}
        if len(vids) > 1:
            false_stitches += 1
            # record unique pairs
            vlist = sorted(list(vids))
            for i in range(len(vlist)):
                for j in range(i+1, len(vlist)):
                    merged_vehicle_pairs.add((vlist[i], vlist[j]))

    # 2. Check Fragmentation: Group true vehicles and measure how many distinct emitted plates they got
    # If a true vehicle gets 4 events and all 4 have different plates, fragmentation is 100% (4 fragments)
    true_vehicle_events = defaultdict(list)
    for e in all_events:
        true_vehicle_events[e["true_vehicle_id"]].append(e)

    fragmented_vehicles = 0
    path_lengths = []
    for vid, evs in true_vehicle_events.items():
        emitted_plates = {e["plate"] for e in evs}
        if len(emitted_plates) > 1:
            fragmented_vehicles += 1
        # Path length of the primary plate
        plate_counts = defaultdict(int)
        for e in evs:
            plate_counts[e["plate"]] += 1
        max_len = max(plate_counts.values()) if plate_counts else 0
        path_lengths.append(max_len)

    total_true_vehicles = len(true_vehicle_events)
    frag_pct = (fragmented_vehicles / total_true_vehicles) * 100.0
    avg_path_length = statistics.mean(path_lengths) if path_lengths else 0.0

    return {
        "noise_rate": noise_rate,
        "seed": seed,
        "total_true_vehicles": total_true_vehicles,
        "total_events": len(all_events),
        "false_stitched_plates": false_stitches,
        "unique_false_merged_pairs": len(merged_vehicle_pairs),
        "fragmented_vehicles": fragmented_vehicles,
        "fragmentation_pct": frag_pct,
        "mean_dominant_path_length": avg_path_length,
        "distinct_emitted_plates": len(stitched_trajectories)
    }

def main():
    with open("events.json", "r", encoding="utf-8") as f:
        base_events = json.load(f)

    noise_rates = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    seeds = [42, 101, 2024, 777, 9999]

    results = []
    print("=== IDENTITY NOISE ROBUSTNESS SWEEP ===")
    print(f"{'Noise Rate':<12} | {'Seed':<6} | {'False Stitches':<16} | {'Frag Vehicles':<14} | {'Frag %':<8} | {'Avg Path Len'}")
    print("-" * 80)

    for nr in noise_rates:
        for s in seeds:
            res = run_noise_experiment(base_events, nr, s)
            results.append(res)
            print(f"{nr*100:<10.1f}% | {s:<6d} | {res['false_stitched_plates']:<16d} | {res['fragmented_vehicles']:>2d}/{res['total_true_vehicles']:<11d} | {res['fragmentation_pct']:<7.1f}% | {res['mean_dominant_path_length']:.2f}/4.0")

    os.makedirs("paper_evidence/data", exist_ok=True)
    out_csv = "paper_evidence/data/identity_noise_robustness.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print("\n--- SUMMARY ACROSS NOISE RATES (MEAN OVER 5 SEEDS) ---")
    print(f"{'Noise Rate':<12} | {'False Stitches (Mean)':<24} | {'Fragmentation % (Mean)':<24} | {'Avg Path Length'}")
    print("-" * 75)
    for nr in noise_rates:
        nr_rows = [r for r in results if r["noise_rate"] == nr]
        fs = [r["false_stitched_plates"] for r in nr_rows]
        fr = [r["fragmentation_pct"] for r in nr_rows]
        pl = [r["mean_dominant_path_length"] for r in nr_rows]
        print(f"{nr*100:<10.1f}% | {statistics.mean(fs):>6.2f}                   | {statistics.mean(fr):>6.2f}%                  | {statistics.mean(pl):.2f}/4.0")

if __name__ == "__main__":
    main()
