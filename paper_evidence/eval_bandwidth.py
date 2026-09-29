"""
eval_bandwidth.py — Recomputes per-event JSON size distribution and benchmarks against 4K, 1080p, and 720p streaming.

Outputs: paper_evidence/data/bandwidth_comparison.csv
"""

import json
import os
import csv
import statistics

def main():
    # 1. Inspect events.json payload sizes
    with open("events.json", "r", encoding="utf-8") as f:
        events = json.load(f)

    # Encode as compact UTF-8 JSON bytes (as transmitted via HTTP POST)
    payload_bytes = [len(json.dumps(e, separators=(",", ":")).encode("utf-8")) for e in events]
    # Also standard json dumps with spaces
    standard_bytes = [len(json.dumps(e).encode("utf-8")) for e in events]

    total_events = len(payload_bytes)
    min_b = min(payload_bytes)
    max_b = max(payload_bytes)
    mean_b = statistics.mean(payload_bytes)
    median_b = statistics.median(payload_bytes)
    p95_b = sorted(payload_bytes)[int(total_events * 0.95)]

    print("=== PER-EVENT JSON PAYLOAD SIZE DISTRIBUTION ===")
    print(f"Total Events: {total_events}")
    print(f"Min Size:     {min_b} bytes")
    print(f"Median (p50): {median_b:.1f} bytes")
    print(f"Mean Size:    {mean_b:.2f} bytes")
    print(f"p95 Size:     {p95_b} bytes")
    print(f"Max Size:     {max_b} bytes")

    # 2. Source video specifications (60 seconds, 1800 frames)
    duration_s = 60.0
    total_frames = 1800
    fps = 30.0
    actual_4k_h264_bytes = os.path.getsize("source.mp4")
    actual_4k_h264_kbps = (actual_4k_h264_bytes * 8) / (duration_s * 1000.0)

    # Industry standard streaming bitrates for H.264 CCTV feeds
    # 1080p (Full HD, 30 fps, H.264 High Profile): ~4,000 kbps (4.0 Mbps)
    # 720p  (HD, 30 fps, H.264 Main Profile):      ~2,000 kbps (2.0 Mbps)
    video_profiles = [
        {"name": "Raw 4K UHD (Uncompressed 24-bit)", "resolution": "3840x2160", "fps": 30.0, "bitrate_kbps": (3840 * 2160 * 3 * 8 * 30) / 1000.0, "total_bytes_60s": 3840 * 2160 * 3 * 1800},
        {"name": "Raw 1080p FHD (Uncompressed 24-bit)", "resolution": "1920x1080", "fps": 30.0, "bitrate_kbps": (1920 * 1080 * 3 * 8 * 30) / 1000.0, "total_bytes_60s": 1920 * 1080 * 3 * 1800},
        {"name": "Raw 720p HD (Uncompressed 24-bit)", "resolution": "1280x720", "fps": 30.0, "bitrate_kbps": (1280 * 720 * 3 * 8 * 30) / 1000.0, "total_bytes_60s": 1280 * 720 * 3 * 1800},
        {"name": "H.264 4K UHD (Measured source.mp4)", "resolution": "3840x2160", "fps": 30.0, "bitrate_kbps": actual_4k_h264_kbps, "total_bytes_60s": actual_4k_h264_bytes},
        {"name": "H.264 1080p FHD (Standard CCTV 4 Mbps)", "resolution": "1920x1080", "fps": 30.0, "bitrate_kbps": 4000.0, "total_bytes_60s": (4000.0 * 1000 / 8) * 60.0},
        {"name": "H.264 720p HD (Standard CCTV 2 Mbps)", "resolution": "1280x720", "fps": 30.0, "bitrate_kbps": 2000.0, "total_bytes_60s": (2000.0 * 1000 / 8) * 60.0},
    ]

    total_idahr_bytes_60s = sum(payload_bytes)
    idahr_bitrate_kbps = (total_idahr_bytes_60s * 8) / (duration_s * 1000.0)

    rows = []
    print("\n=== BANDWIDTH COMPARISON (60-SECOND STREAM, 35 VEHICLE EVENTS) ===")
    print(f"{'Stream Format':<38} | {'Bitrate':<12} | {'Data Volume (60s)':<18} | {'IDAHR Reduction'}")
    print("-" * 90)

    for p in video_profiles:
        red_pct = (1.0 - (total_idahr_bytes_60s / p["total_bytes_60s"])) * 100.0
        ratio = p["total_bytes_60s"] / total_idahr_bytes_60s
        bitrate_str = f"{p['bitrate_kbps']/1000.0:.2f} Mbps" if p['bitrate_kbps'] >= 1000 else f"{p['bitrate_kbps']:.1f} kbps"
        vol_str = f"{p['total_bytes_60s']/(1024*1024):.2f} MB" if p['total_bytes_60s'] >= 1024*1024 else f"{p['total_bytes_60s']/1024:.2f} KB"
        print(f"{p['name']:<38} | {bitrate_str:<12} | {vol_str:<18} | {red_pct:.5f}% ({ratio:,.0f}x)")
        rows.append({
            "stream_format": p["name"],
            "resolution": p["resolution"],
            "bitrate_kbps": p["bitrate_kbps"],
            "data_volume_bytes_60s": p["total_bytes_60s"],
            "idahr_data_volume_bytes_60s": total_idahr_bytes_60s,
            "idahr_bitrate_kbps": idahr_bitrate_kbps,
            "bandwidth_reduction_pct": red_pct,
            "bandwidth_saving_factor": ratio
        })

    # Add IDAHR entry
    rows.append({
        "stream_format": "IDAHR Edge JSON Telemetry",
        "resolution": "Structured JSON (Text)",
        "bitrate_kbps": idahr_bitrate_kbps,
        "data_volume_bytes_60s": total_idahr_bytes_60s,
        "idahr_data_volume_bytes_60s": total_idahr_bytes_60s,
        "idahr_bitrate_kbps": idahr_bitrate_kbps,
        "bandwidth_reduction_pct": 0.0,
        "bandwidth_saving_factor": 1.0
    })

    print(f"{'IDAHR Edge JSON Events':<38} | {idahr_bitrate_kbps:.2f} kbps     | {total_idahr_bytes_60s/1024:.2f} KB ({total_idahr_bytes_60s} B)   | Baseline (0.0%)")

    os.makedirs("paper_evidence/data", exist_ok=True)
    out_csv = "paper_evidence/data/bandwidth_comparison.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

if __name__ == "__main__":
    main()
