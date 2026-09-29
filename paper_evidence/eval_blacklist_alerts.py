"""
eval_blacklist_alerts.py — Evaluates Blacklist Alert Precision and Recall under OCR Noise and Matching Rules.

Evaluates:
1. Exact matching (current backend implementation) vs Fuzzy matching (Levenshtein <= 1).
2. Effect of OCR raw misreads vs DVLA-corrected reads.
3. Effect of synthetic OCR error rates (0%, 5%, 10%, 20%) on alert recall (missed alerts).

Outputs: paper_evidence/data/blacklist_alerts_eval.csv
"""

import json
import csv
import os
import random
import statistics
from collections import defaultdict

def levenshtein_dist(s1, s2):
    if s1 == s2: return 0
    if len(s1) > len(s2): s1, s2 = s2, s1
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
    if not plate: return ""
    if len(plate) <= 3: return "***"
    return plate[:-3] + "***"

def load_tracks():
    tracks = {}
    import re
    with open("ocr_ground_truth_review.md", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("|") and "`ID " in line:
                parts = [p.strip() for p in line.split("|")]
                m = re.search(r"\d+", parts[2])
                if not m: continue
                tid = int(m.group())
                raw_ocr = parts[4].replace("`", "").strip()
                p_plate = parts[5].replace("**", "").replace("`", "").split("*")[0].strip()
                matches = "[x] Yes" in parts[9]
                actual = parts[10].replace("`", "").strip()
                gt_plate = p_plate if matches else actual.replace("`", "").strip()
                tracks[tid] = {
                    "raw": raw_ocr,
                    "corrected": p_plate,
                    "true": gt_plate
                }
    return tracks

def main():
    gt_tracks = load_tracks()


    # In source.mp4 evaluation, Track 11 (true: BG65USJ) is blacklisted
    # Let's test with 3 blacklisted targets from the fleet:
    # 1. Track 11 (true: BG65USJ, raw: BGG5USJ) - tests correction recovery!
    # 2. Track 8  (true: KH05ZZK, raw: KHOSZZK) - tests digit/char confusion recovery!
    # 3. Track 97 (true: BP63LYH, raw: BP63LYH) - clean read
    blacklist_targets = {"BG65USJ", "KH05ZZK", "BP63LYH"}

    # Simulate 4 cameras per vehicle = 35 * 4 = 140 sightings total
    # True positives expected: 3 vehicles * 4 cameras = 12 true blacklist sightings
    num_cams = 4
    total_true_events = len(gt_tracks) * num_cams
    total_target_events = len(blacklist_targets) * num_cams

    scenarios = [
        ("Raw OCR (No Correction)", "exact", "raw", 0.0),
        ("Raw OCR (No Correction)", "fuzzy_lev1", "raw", 0.0),
        ("Corrected OCR (DVLA Bounded)", "exact", "corrected", 0.0),
        ("Corrected OCR (DVLA Bounded)", "fuzzy_lev1", "corrected", 0.0),
        ("Corrected OCR + 5% Noise", "exact", "corrected", 0.05),
        ("Corrected OCR + 10% Noise", "exact", "corrected", 0.10),
        ("Corrected OCR + 20% Noise", "exact", "corrected", 0.20),
    ]

    results = []
    print("=== BLACKLIST ALERT PRECISION & RECALL EVALUATION ===")
    print(f"{'Scenario':<30} | {'Matcher':<10} | {'TP':<3} | {'FP':<3} | {'FN':<3} | {'Precision':<10} | {'Recall':<10} | {'F1 Score'}")
    print("-" * 88)

    for scen_name, matcher, read_source, noise in scenarios:
        tp, fp, fn = 0, 0, 0
        random.seed(42)

        for tid, info in gt_tracks.items():
            true_p = info["true"]
            is_target = true_p in blacklist_targets
            base_read = info[read_source]

            for cam_idx in range(num_cams):
                observed = base_read
                if noise > 0 and random.random() < noise:
                    # mutate 1 char
                    chars = list(observed)
                    idx = random.randint(0, len(chars) - 1)
                    chars[idx] = "X" if chars[idx] != "X" else "Y"
                    observed = "".join(chars)

                # Match logic
                if matcher == "exact":
                    hit = observed in blacklist_targets
                else: # fuzzy_lev1
                    hit = any(levenshtein_dist(observed, target) <= 1 for target in blacklist_targets)

                if hit and is_target:
                    tp += 1
                elif hit and not is_target:
                    fp += 1
                elif not hit and is_target:
                    fn += 1

        prec = (tp / (tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        print(f"{scen_name:<30} | {matcher:<10} | {tp:>2d} | {fp:>2d} | {fn:>2d} | {prec:>9.2f}% | {rec:>9.2f}% | {f1:>7.2f}%")
        results.append({
            "scenario": scen_name,
            "matching_rule": matcher,
            "read_source": read_source,
            "noise_rate": noise,
            "tp": tp, "fp": fp, "fn": fn,
            "precision_pct": prec,
            "recall_pct": rec,
            "f1_score_pct": f1
        })

    os.makedirs("paper_evidence/data", exist_ok=True)
    out_csv = "paper_evidence/data/blacklist_alerts_eval.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)

if __name__ == "__main__":
    main()
