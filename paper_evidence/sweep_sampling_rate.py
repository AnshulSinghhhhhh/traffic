"""
sweep_sampling_rate.py — Edge pipeline sampling-rate sweep harness (2, 5, 10 FPS).

Evaluates the trade-off between edge frame sampling frequency, computational runtime,
tracker yield, plate detection count, and unique plate recognition.

NOTE: This script requires a CUDA-capable GPU (or Kaggle T4 execution) and source.mp4.
      Do not run without user approval due to compute resource requirements.

Usage:
    python paper_evidence/sweep_sampling_rate.py --video source.mp4 --rates 2 5 10
"""

import argparse
import time
import os
import json
import csv

# Skeleton harness for running inference across multiple sampling frame rates:
# FPS = 2:  stride = round(30 / 2)  = 15 (120 sampled frames)
# FPS = 5:  stride = round(30 / 5)  = 6  (300 sampled frames — baseline)
# FPS = 10: stride = round(30 / 10) = 3  (600 sampled frames)

def main():
    parser = argparse.ArgumentParser(description="Sampling rate sweep for IDAHR edge pipeline")
    parser.add_argument("--video", default="source.mp4", help="Path to evaluation video")
    parser.add_argument("--weights", default="idahr_plate_detector.pt", help="Path to plate detector weights")
    parser.add_argument("--rates", nargs="+", type=int, default=[2, 5, 10], help="Sampling rates in FPS")
    parser.add_argument("--output", default="paper_evidence/data/sampling_rate_sweep.csv", help="Output CSV path")
    args = parser.parse_args()

    print("=== SAMPLING RATE SWEEP HARNESS ===")
    print("Video:", args.video)
    print("Sampling rates to evaluate:", args.rates)
    print("\n[NOTE] Execution requires GPU accelerator (NVIDIA Tesla T4 or equivalent).")
    print("Please run via Kaggle runner or with local CUDA environment.")

    # Template structure for output CSV
    fieldnames = [
        "sampling_fps",
        "sampled_frames",
        "video_duration_s",
        "unique_vehicles_tracked",
        "candidate_plates_detected",
        "ocr_invocations",
        "tracks_with_successful_read",
        "unique_decoded_plates",
        "total_runtime_s",
        "effective_fps",
        "realtime_factor"
    ]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    if not os.path.exists(args.output):
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            # Record the known 5.0 FPS baseline row from results.md Section 6.4 (MEASURED)
            writer.writerow({
                "sampling_fps": 5,
                "sampled_frames": 300,
                "video_duration_s": 60.0,
                "unique_vehicles_tracked": 138,
                "candidate_plates_detected": 502,
                "ocr_invocations": 261,
                "tracks_with_successful_read": 35,
                "unique_decoded_plates": 34,
                "total_runtime_s": 130.30,
                "effective_fps": 2.30,
                "realtime_factor": 0.46
            })
        print(f"Initialized {args.output} with baseline 5 FPS telemetry.")

if __name__ == "__main__":
    main()
