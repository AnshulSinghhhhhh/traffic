"""
ablation_corrector.py — Corrector ablation study.

Compares:
1. No correction (raw OCR string)
2. Template-only correction (character confusion based on template length LLDDLLL without area-code whitelist)
3. Template + DVLA Whitelist (full bounded normalization)

Reports:
- Exact-match accuracy vs ground truth
- Unique plate count
- False merges (distinct ground-truth vehicles assigned same plate)
- Missed merges (same vehicle divided into separate plate identities)

Outputs: paper_evidence/data/corrector_ablation.csv
"""

import json
import csv
import re
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath("."))
from ocr_enhancements import UK_AREA_CODES, correct_uk_area_code_enhanced

CHAR_TO_DIGIT = {"O": "0", "I": "1", "Z": "2", "A": "4", "S": "5", "G": "6", "B": "8", "Q": "0", "T": "7"}
DIGIT_TO_CHAR = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "8": "B", "7": "T"}


def mask_plate(plate):
    if not plate: return ""
    if len(plate) <= 3: return "***"
    return plate[:-3] + "***"

def apply_template_only(raw):
    text = raw.upper().replace(" ", "").replace("-", "")
    if len(text) != 7:
        return text, False
    template = "LLDDLLL"
    corrected = []
    changed = False
    for ch, exp in zip(text, template):
        new_ch = ch
        if exp == "L":
            if ch in DIGIT_TO_CHAR:
                new_ch = DIGIT_TO_CHAR[ch]
                changed = True
            if new_ch == "I":
                new_ch = "L"
                changed = True
            elif new_ch == "Q":
                new_ch = "O"
                changed = True
        elif exp == "D":
            if ch in CHAR_TO_DIGIT:
                new_ch = CHAR_TO_DIGIT[ch]
                changed = True
        corrected.append(new_ch)
    return "".join(corrected), changed

def apply_template_plus_dvla(raw):
    text = raw.upper().replace(" ", "").replace("-", "")
    # Check 8-char prefix strip
    if len(text) == 8 and text[0] == text[1]:
        cand_7 = text[1:]
        if cand_7[:2] in UK_AREA_CODES:
            text = cand_7
    
    cand, changed = apply_template_only(text)
    if len(cand) == 7:
        pref = cand[:2]
        valid_pref, p_changed = correct_uk_area_code_enhanced(pref)
        if p_changed:
            cand = valid_pref + cand[2:]
            changed = True
    return cand, changed

def load_data():
    # Load raw OCR and ground truth from ocr_ground_truth_review.md
    data = []
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
                data.append({
                    "track_id": tid,
                    "raw_ocr": raw_ocr,
                    "gt_plate": gt_plate
                })
    return data

def evaluate_mode(data, mode_func, mode_name):
    predictions = {}
    exact_matches = 0
    plate_to_tracks = defaultdict(list)
    gt_to_tracks = defaultdict(list)

    for item in data:
        tid = item["track_id"]
        raw = item["raw_ocr"]
        gt = item["gt_plate"]
        pred, _ = mode_func(raw)
        predictions[tid] = pred
        if pred == gt:
            exact_matches += 1
        plate_to_tracks[pred].append(tid)
        gt_to_tracks[gt].append(tid)

    total = len(data)
    acc = (exact_matches / total) * 100.0
    unique_plates = len(plate_to_tracks)

    # False merges: two tracks with DIFFERENT ground-truth plates assigned the SAME predicted plate
    false_merges = 0
    for pred, tids in plate_to_tracks.items():
        if len(tids) > 1:
            gts = {next(d["gt_plate"] for d in data if d["track_id"] == t) for t in tids}
            if len(gts) > 1:
                false_merges += (len(gts) - 1)

    # Missed merges: two tracks with the SAME ground-truth plate assigned DIFFERENT predicted plates
    missed_merges = 0
    for gt, tids in gt_to_tracks.items():
        if len(tids) > 1:
            preds = {predictions[t] for t in tids}
            if len(preds) > 1:
                missed_merges += (len(preds) - 1)

    return {
        "mode": mode_name,
        "exact_matches": exact_matches,
        "total": total,
        "accuracy_pct": acc,
        "unique_plates": unique_plates,
        "false_merges": false_merges,
        "missed_merges": missed_merges
    }

def main():
    data = load_data()
    modes = [
        ("No Correction", lambda r: (r, False)),
        ("Template Only", apply_template_only),
        ("Template + DVLA Whitelist", apply_template_plus_dvla)
    ]

    results = []
    for name, func in modes:
        res = evaluate_mode(data, func, name)
        results.append(res)

    os.makedirs("paper_evidence/data", exist_ok=True)
    out_csv = "paper_evidence/data/corrector_ablation.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mode", "exact_matches", "total", "accuracy_pct", "unique_plates", "false_merges", "missed_merges"])
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print("=== CORRECTOR ABLATION RESULTS ===")
    print(f"{'Ablation Mode':<28} | {'Accuracy':<10} | {'Exact/Total':<12} | {'Unique Plates':<14} | {'False Merges':<12} | {'Missed Merges'}")
    print("-" * 100)
    for r in results:
        print(f"{r['mode']:<28} | {r['accuracy_pct']:<9.2f}% | {r['exact_matches']:>2d}/{r['total']:<8d} | {r['unique_plates']:<14d} | {r['false_merges']:<12d} | {r['missed_merges']:<12d}")

if __name__ == "__main__":
    main()
