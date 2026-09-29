"""
evaluate_accuracy_improvement.py — Evaluates the accuracy lift of the OCR enhancements
against the verified 35-track ground-truth dataset from ocr_ground_truth_review.md.
"""

import json
import re
from ocr_enhancements import (
    normalize_plate_enhanced,
    resolve_partial_reads_with_attributes,
    UK_AREA_CODES,
    LETTER_CONFUSIONS
)

def load_ground_truth():
    gt = {}
    with open("ocr_ground_truth_review.md", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("|") and "`ID " in line:
                parts = [p.strip() for p in line.split("|")]
                m = re.search(r"\d+", parts[2])
                if not m:
                    continue
                tid = int(m.group())
                matches = "[x] Yes" in parts[9]
                actual = parts[10].replace("`", "").strip()
                p_plate = parts[5].replace("**", "").replace("`", "").split("*")[0].strip()
                gt_plate = p_plate if matches else actual.replace("`", "").strip()
                gt[tid] = {
                    "pipeline_plate": p_plate,
                    "gt_plate": gt_plate,
                    "matches_baseline": matches,
                    "conf": float(parts[6].replace("`", "")),
                    "attempts": int(parts[7]),
                    "notes": parts[12] if len(parts) > 12 else ""
                }
    return gt

def main():
    gt_map = load_ground_truth()
    with open("events.json", "r", encoding="utf-8") as f:
        events = json.load(f)

    print("=== EMPIRICAL ACCURACY EVALUATION (35-TRACK GROUND TRUTH) ===")
    print(f"Total Evaluated Tracks: {len(gt_map)}")

    # 1. Baseline Evaluation
    base_matches = sum(1 for v in gt_map.values() if v["matches_baseline"])
    base_rate = (base_matches / len(gt_map)) * 100.0
    print(f"Baseline Pipeline Matches: {base_matches} / {len(gt_map)} ({base_rate:.2f}%)")

    # 2. Enhanced Normalization & Disambiguation
    # First apply enhanced normalization on events
    enhanced_events = []
    for e in events:
        e_copy = dict(e)
        raw = e.get("raw_plate", e["plate"])
        norm, corr = normalize_plate_enhanced(raw)
        e_copy["plate"] = norm
        e_copy["was_corrected"] = corr
        enhanced_events.append(e_copy)

    # Then apply secondary-signal attribute & substring resolution (e.g. BPF -> HX52BPF)
    resolved_events, aliases = resolve_partial_reads_with_attributes(enhanced_events)

    print(f"\nResolved Substring Aliases: {aliases}")

    # Evaluate enhanced events
    enhanced_map = {e["track_id"]: e["plate"] for e in resolved_events}

    results_table = []
    enh_matches = 0
    recovered_tracks = []

    for tid, gt_info in sorted(gt_map.items()):
        gt_p = gt_info["gt_plate"]
        base_p = gt_info["pipeline_plate"]
        enh_p = enhanced_map.get(tid, base_p)

        is_base_correct = (base_p == gt_p)
        is_enh_correct = (enh_p == gt_p)

        if is_enh_correct:
            enh_matches += 1

        if not is_base_correct and is_enh_correct:
            recovered_tracks.append((tid, base_p, enh_p, gt_p))

        status = "RECOVERED" if (not is_base_correct and is_enh_correct) else (
            "MATCH" if is_enh_correct else "STILL_MISMATCH"
        )

        results_table.append({
            "tid": tid,
            "base_plate": base_p,
            "enh_plate": enh_p,
            "gt_plate": gt_p,
            "base_ok": is_base_correct,
            "enh_ok": is_enh_correct,
            "status": status
        })

    enh_rate = (enh_matches / len(gt_map)) * 100.0

    print("\n" + "="*85)
    print(f"{'TID':<5} | {'Baseline Plate':<14} | {'Enhanced Plate':<14} | {'Ground Truth':<14} | {'Status':<15}")
    print("="*85)
    for r in results_table:
        marker = " [*** RECOVERED ***]" if r["status"] == "RECOVERED" else ""
        print(f"ID {r['tid']:<2} | {r['base_plate']:<14} | {r['enh_plate']:<14} | {r['gt_plate']:<14} | {r['status']:<15}{marker}")
    print("="*85)

    print("\n=== SUMMARY COMPARISON METRICS ===")
    print(f"Baseline Match Count:      {base_matches} / {len(gt_map)} ({base_rate:.2f}%)")
    print(f"Enhanced Match Count:      {enh_matches} / {len(gt_map)} ({enh_rate:.2f}%)")
    print(f"Net Accuracy Lift:         +{enh_rate - base_rate:.2f}% percentage points")
    print(f"Total Errors Recovered:    {len(recovered_tracks)} tracks")
    for tid, base_p, enh_p, gt_p in recovered_tracks:
        print(f"  • Track {tid:3d}: '{base_p}' -> '{enh_p}' (matches GT '{gt_p}')")

    remaining_errors = [r for r in results_table if not r["enh_ok"]]
    print(f"\nRemaining Residual Errors: {len(remaining_errors)} tracks")
    for r in remaining_errors:
        print(f"  • Track {r['tid']:3d}: Got '{r['enh_plate']}', Expected '{r['gt_plate']}'")

if __name__ == "__main__":
    main()
