"""
eval_ocr_accuracy.py — Evaluates OCR predictions against ground truth.

Computes:
1. Plate-level exact-match accuracy.
2. Character-level accuracy (1 - Character Error Rate).
3. Per-track confidence vs. correctness breakdown.

Usage:
    python paper_evidence/eval_ocr_accuracy.py --gt paper_evidence/data/ocr_ground_truth_filled.csv --events events.json
"""
import argparse
import csv
import json
import os

def levenshtein_dist(s1, s2):
    if s1 == s2:
        return 0
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = list(range(len(s1) + 1))
    for i2, c2 in enumerate(s2):
        new_distances = [i2 + 1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                new_distances.append(distances[i1])
            else:
                new_distances.append(1 + min(distances[i1], distances[i1 + 1], new_distances[-1]))
        distances = new_distances
    return distances[-1]

def mask_plate(plate):
    if not plate:
        return ""
    if len(plate) <= 3:
        return "***"
    return plate[:-3] + "***"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gt", default="paper_evidence/data/ocr_ground_truth_filled.csv", help="Path to CSV with true_plate column")
    parser.add_argument("--events", default="events.json", help="Path to pipeline events.json")
    args = parser.parse_args()

    # Load events
    with open(args.events, "r", encoding="utf-8") as f:
        events = json.load(f)
    event_by_track = {e["track_id"]: e for e in events}

    # Load GT
    gt_data = []
    with open(args.gt, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gt_data.append(row)

    total_plates = len(gt_data)
    exact_matches_pred = 0
    exact_matches_corr = 0
    total_chars_gt = 0
    total_char_errors_pred = 0
    total_char_errors_corr = 0

    conf_correctness = {"high_conf_total": 0, "high_conf_correct": 0,
                        "low_conf_total": 0, "low_conf_correct": 0}

    print(f"Loaded {total_plates} ground-truth rows.")
    print("=" * 75)
    print(f"{'Track':<6} | {'True (Masked)':<14} | {'Predicted':<14} | {'Corrected':<14} | {'Conf':<6} | {'Corr Match?'}")
    print("=" * 75)

    for row in gt_data:
        tid = int(row["track_id"])
        true_p = row.get("true_plate", "").strip().upper()
        if not true_p:
            print(f"Skipping Track {tid}: true_plate is blank.")
            continue

        ev = event_by_track.get(tid, {})
        pred_p = ev.get("raw_text", ev.get("plate", "")).strip().upper()
        corr_p = ev.get("plate", "").strip().upper()
        conf = ev.get("confidence", 0.0)

        is_pred_match = (pred_p == true_p)
        is_corr_match = (corr_p == true_p)

        if is_pred_match:
            exact_matches_pred += 1
        if is_corr_match:
            exact_matches_corr += 1

        dist_pred = levenshtein_dist(pred_p, true_p)
        dist_corr = levenshtein_dist(corr_p, true_p)
        total_chars_gt += len(true_p)
        total_char_errors_pred += dist_pred
        total_char_errors_corr += dist_corr

        if conf >= 0.55:
            conf_correctness["high_conf_total"] += 1
            if is_corr_match:
                conf_correctness["high_conf_correct"] += 1
        else:
            conf_correctness["low_conf_total"] += 1
            if is_corr_match:
                conf_correctness["low_conf_correct"] += 1

        print(f"ID {tid:<4} | {mask_plate(true_p):<14} | {mask_plate(pred_p):<14} | {mask_plate(corr_p):<14} | {conf:<6.3f} | {is_corr_match}")

    print("=" * 75)
    if total_plates > 0 and total_chars_gt > 0:
        plate_acc_pred = (exact_matches_pred / total_plates) * 100.0
        plate_acc_corr = (exact_matches_corr / total_plates) * 100.0
        char_acc_pred = max(0.0, 1.0 - (total_char_errors_pred / total_chars_gt)) * 100.0
        char_acc_corr = max(0.0, 1.0 - (total_char_errors_corr / total_chars_gt)) * 100.0

        print(f"\n--- EVALUATION RESULTS ---")
        print(f"Plate-Level Exact Match (Raw Predicted): {exact_matches_pred}/{total_plates} ({plate_acc_pred:.2f}%)")
        print(f"Plate-Level Exact Match (Corrected):     {exact_matches_corr}/{total_plates} ({plate_acc_corr:.2f}%)")
        print(f"Character-Level Accuracy (Raw Predicted): {char_acc_pred:.2f}% (Total CER: {total_char_errors_pred}/{total_chars_gt})")
        print(f"Character-Level Accuracy (Corrected):     {char_acc_corr:.2f}% (Total CER: {total_char_errors_corr}/{total_chars_gt})")

        print(f"\n--- CONFIDENCE VS CORRECTNESS BREAKDOWN (Threshold = 0.55) ---")
        hc_tot = conf_correctness["high_conf_total"]
        hc_corr = conf_correctness["high_conf_correct"]
        lc_tot = conf_correctness["low_conf_total"]
        lc_corr = conf_correctness["low_conf_correct"]
        hc_pct = (hc_corr / hc_tot * 100.0) if hc_tot > 0 else 0.0
        lc_pct = (lc_corr / lc_tot * 100.0) if lc_tot > 0 else 0.0
        print(f"High-Confidence (>= 0.55): {hc_corr}/{hc_tot} correct ({hc_pct:.1f}%)")
        print(f"Low-Confidence  (< 0.55):  {lc_corr}/{lc_tot} correct ({lc_pct:.1f}%)")

if __name__ == "__main__":
    main()
