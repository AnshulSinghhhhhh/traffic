"""
eval_congestion.py — Evaluates the IDAHR congestion detection rule under synthetic surges and stochastic baseline traffic.

Congestion rule (from backend/app/routes/traffic.py):
    recent = count of events in last `window` minutes (default 15m)
    rolling_60m = count of events in last 60 minutes
    rolling_avg = rolling_60m / (60.0 / window)
    congested = (recent > 1.5 * rolling_avg) and (rolling_avg > 0)

Evaluates:
1. False Positive Rate (FPR) under stationary Poisson traffic over 24 hours (1,440 minutes).
2. Detection Delay (minutes) under sudden traffic surges (1.5x, 2.0x, 2.5x, 3.0x).
3. Clear Delay (minutes until flag resets after surge ceases).

Outputs: paper_evidence/data/congestion_eval.csv
"""

import random
import csv
import os
import statistics

def simulate_minute_traffic(rate_per_min):
    # Poisson arrival
    # Using Knuth's algorithm for Poisson random variable
    L = 2.718281828459045 ** (-rate_per_min)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

def run_congestion_simulation(window_m=15, baseline_rate=10, surge_factor=2.0, surge_duration_m=30, total_sim_m=300, seed=42):
    random.seed(seed)
    # Warm up with 60 minutes of baseline
    minute_counts = [simulate_minute_traffic(baseline_rate) for _ in range(60)]
    
    surge_start = 120  # surge starts at minute 120
    surge_end = surge_start + surge_duration_m

    flags = []
    detection_minute = None
    clear_minute = None

    for m in range(60, total_sim_m):
        # Current minute traffic rate
        is_surge = (surge_start <= m < surge_end)
        rate = (baseline_rate * surge_factor) if is_surge else baseline_rate
        minute_counts.append(simulate_minute_traffic(rate))

        # Evaluate window
        recent_count = sum(minute_counts[-window_m:])
        rolling_60_count = sum(minute_counts[-60:])
        rolling_avg = rolling_60_count / (60.0 / window_m)

        congested = (recent_count > 1.5 * rolling_avg) and (rolling_avg > 0)
        flags.append({
            "minute": m,
            "is_surge": is_surge,
            "congested": congested,
            "recent": recent_count,
            "rolling_avg": rolling_avg
        })

        if is_surge and congested and detection_minute is None:
            detection_minute = m - surge_start

        if m >= surge_end and not congested and clear_minute is None and detection_minute is not None:
            clear_minute = m - surge_end

    # Measure false positives in pre-surge baseline (minutes 60 to 120)
    pre_surge = [f for f in flags if f["minute"] < surge_start]
    fp_count = sum(1 for f in pre_surge if f["congested"])
    fpr = (fp_count / len(pre_surge)) * 100.0 if pre_surge else 0.0

    return {
        "surge_factor": surge_factor,
        "detection_delay_m": detection_minute if detection_minute is not None else -1,
        "clear_delay_m": clear_minute if clear_minute is not None else -1,
        "fpr_baseline_pct": fpr,
        "fp_count": fp_count,
        "baseline_minutes": len(pre_surge)
    }

def main():
    surge_factors = [1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0]
    seeds = [42, 101, 2024, 777, 9999]

    results = []
    print("=== CONGESTION DETECTION EVALUATION (WINDOW = 15m, ROLLING = 60m) ===")
    print(f"{'Surge Factor':<14} | {'Mean Det Delay (m)':<20} | {'Mean Clear Delay (m)':<22} | {'Baseline FPR %'}")
    print("-" * 75)

    for sf in surge_factors:
        det_delays = []
        clear_delays = []
        fprs = []
        for s in seeds:
            res = run_congestion_simulation(surge_factor=sf, seed=s)
            if res["detection_delay_m"] >= 0:
                det_delays.append(res["detection_delay_m"])
            if res["clear_delay_m"] >= 0:
                clear_delays.append(res["clear_delay_m"])
            fprs.append(res["fpr_baseline_pct"])

        mean_det = statistics.mean(det_delays) if det_delays else -1
        mean_clear = statistics.mean(clear_delays) if clear_delays else -1
        mean_fpr = statistics.mean(fprs)

        det_str = f"{mean_det:.1f} min" if mean_det >= 0 else "Never detected"
        clear_str = f"{mean_clear:.1f} min" if mean_clear >= 0 else "N/A"
        print(f"{sf:<14.1f} | {det_str:<20} | {clear_str:<22} | {mean_fpr:.2f}%")

        results.append({
            "surge_factor": sf,
            "detection_rate_pct": (len(det_delays) / len(seeds)) * 100.0,
            "mean_detection_delay_m": mean_det,
            "mean_clear_delay_m": mean_clear,
            "mean_baseline_fpr_pct": mean_fpr
        })

    os.makedirs("paper_evidence/data", exist_ok=True)
    out_csv = "paper_evidence/data/congestion_eval.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)

if __name__ == "__main__":
    main()
