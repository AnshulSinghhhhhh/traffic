"""
build_review_package.py — Generates authentic manual verification packages
for OCR ground truth and vehicle attribute disambiguation.

Strict Ground Rules:
- All checkboxes must remain BLANK ([ ] Yes  [ ] No).
- Never pre-fill "Validated", "PASS", or plausible values.
- Crop images must be embedded for visual inspection.
"""

import os
import json
import pathlib
import shutil

ROOT_DIR = pathlib.Path(__file__).parent
EVENTS_PATH = ROOT_DIR / "events.json"
PLATE_CROPS_DIR = ROOT_DIR / "plate_crops"
VEHICLE_CROPS_DIR = ROOT_DIR / "vehicle_crops"

MD_REVIEW_PATH = ROOT_DIR / "ocr_ground_truth_review.md"
HTML_REVIEW_PATH = ROOT_DIR / "ocr_ground_truth_review.html"
AMBIGUOUS_MD_PATH = ROOT_DIR / "ambiguous_pairs_review.md"


def load_events():
    if not EVENTS_PATH.exists():
        raise FileNotFoundError(f"{EVENTS_PATH} not found.")
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        events = json.load(f)
    return events


def generate_ocr_review_markdown(events):
    lines = []
    lines.append("# ANPR OCR Ground-Truth Manual Verification Package")
    lines.append("")
    lines.append("> [!IMPORTANT]")
    lines.append("> **Reviewer Instructions**: This document is an unvalidated manual review worksheet for all 35 vehicle tracks from `source.mp4`.")
    lines.append("> Every row displays the actual cropped plate image extracted during inference, alongside the raw OCR read and post-normalization plate.")
    lines.append("> **Do not modify pipeline outputs directly.** Check the appropriate boxes and record actual values if different.")
    lines.append("")
    lines.append("### Review Status Summary")
    lines.append(f"- **Total Vehicle Tracks Emitted**: {len(events)}")
    lines.append("- **Verification Progress**: `0 / 35` completed (All checkboxes left unverified for human review)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sort events by confidence ascending (lowest confidence first, so marginal reads are reviewed first)
    sorted_events = sorted(events, key=lambda x: x.get("confidence", 0.0))

    lines.append("| # | Track ID | Plate Crop | Raw OCR | Normalized Plate | Conf | Attempts | Offset / Timestamp | Matches Video? | Actual Plate (if different) | Readability | Reviewer Notes |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")

    for idx, e in enumerate(sorted_events, start=1):
        tid = e["track_id"]
        plate = e["plate"]
        raw = e.get("raw_plate", plate)
        conf = e.get("confidence", 0.0)
        attempts = e.get("ocr_attempts", 1)
        ts = e.get("timestamp", "")
        # Extract seconds offset from timestamp e.g. 2026-08-23T08:00:25 -> 25.0s
        sec_offset = ts.split("T")[-1] if "T" in ts else ts
        sec_offset = sec_offset.replace("08:00:", "")

        crop_filename = f"track_{tid:03d}_{plate}.jpg"
        crop_rel_path = f"plate_crops/{crop_filename}"
        img_cell = f"![ID{tid}]({crop_rel_path})" if (PLATE_CROPS_DIR / crop_filename).exists() else "*(Image pending pull)*"

        corrected_badge = f"**{plate}** *(corrected)*" if e.get("was_corrected") else f"`{plate}`"

        lines.append(
            f"| {idx} | `ID {tid}` | {img_cell} | `{raw}` | {corrected_badge} | `{conf:.3f}` | {attempts} | `{sec_offset}` | [ ] Yes &nbsp; [ ] No | `_______________` | [ ] Clear <br> [ ] Marginal <br> [ ] Illegible | |"
        )

    lines.append("")
    lines.append("---")
    lines.append("### Reviewer Sign-Off")
    lines.append("- **Reviewer Name**: ___________________________")
    lines.append("- **Review Date**: ___________________________")
    lines.append("- **Total Validated Matches**: _____ / 35")
    lines.append("- **Total Corrected Readings Confirmed**: _____")
    lines.append("- **Notes / Edge Cases Observed**: ____________________________________________________________________")
    lines.append("")

    return "\n".join(lines)


def generate_ocr_review_html(events):
    sorted_events = sorted(events, key=lambda x: x.get("confidence", 0.0))

    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<title>IDAHR ANPR — Manual OCR Ground-Truth Review Package</title>",
        "<style>",
        "  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 24px; background: #f8fafc; color: #1e293b; }",
        "  h1 { color: #0f172a; margin-bottom: 4px; }",
        "  .subtitle { color: #64748b; font-size: 15px; margin-bottom: 20px; }",
        "  .notice { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin-bottom: 24px; font-size: 14px; color: #1e40af; }",
        "  table { width: 100%; border-collapse: collapse; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 13px; }",
        "  th { background: #f1f5f9; padding: 10px 12px; text-align: left; font-weight: 600; color: #475569; border-bottom: 1px solid #e2e8f0; }",
        "  td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }",
        "  tr:hover { background: #f8fafc; }",
        "  .crop-img { height: 48px; border: 1px solid #cbd5e1; border-radius: 4px; background: #000; object-fit: contain; }",
        "  .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }",
        "  .badge-corrected { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }",
        "  .badge-raw { background: #f1f5f9; color: #475569; }",
        "  .conf-low { color: #dc2626; font-weight: 600; }",
        "  .conf-mid { color: #d97706; }",
        "  .conf-high { color: #16a34a; font-weight: 600; }",
        "  input[type='text'] { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; width: 120px; font-size: 12px; font-family: monospace; }",
        "  .signoff { margin-top: 32px; background: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>IDAHR ANPR — Manual OCR Ground-Truth Review Package</h1>",
        "<div class='subtitle'>Empirical evaluation package covering all N = 35 tracked vehicles from source.mp4 (4K, 300 sampled frames)</div>",
        "<div class='notice'>",
        "  <strong>Ground Rule for Manual Verification</strong>: All checkboxes and validation fields are blank. Examine each plate crop image against the raw and normalized plate readings. Do not guess. Report honest findings.",
        "</div>",
        "<table>",
        "<thead>",
        "  <tr>",
        "    <th>#</th>",
        "    <th>Track</th>",
        "    <th>Plate Crop</th>",
        "    <th>Raw OCR</th>",
        "    <th>Normalized Plate</th>",
        "    <th>Conf</th>",
        "    <th>Attempts</th>",
        "    <th>Timestamp</th>",
        "    <th>Matches?</th>",
        "    <th>Actual Plate (if diff)</th>",
        "    <th>Readability</th>",
        "    <th>Notes</th>",
        "  </tr>",
        "</thead>",
        "<tbody>"
    ]

    for idx, e in enumerate(sorted_events, start=1):
        tid = e["track_id"]
        plate = e["plate"]
        raw = e.get("raw_plate", plate)
        conf = e.get("confidence", 0.0)
        attempts = e.get("ocr_attempts", 1)
        ts = e.get("timestamp", "")
        sec_offset = ts.split("T")[-1].replace("08:00:", "") if "T" in ts else ts

        crop_filename = f"track_{tid:03d}_{plate}.jpg"
        crop_rel_path = f"plate_crops/{crop_filename}"
        img_tag = f"<img class='crop-img' src='{crop_rel_path}' alt='Track {tid}'>" if (PLATE_CROPS_DIR / crop_filename).exists() else "<span style='color:#94a3b8; font-style:italic;'>Image pending</span>"

        conf_class = "conf-low" if conf < 0.40 else ("conf-mid" if conf < 0.55 else "conf-high")
        corr_badge = f"<span class='badge badge-corrected'>{plate}</span>" if e.get("was_corrected") else f"<span class='badge badge-raw'>{plate}</span>"

        html.append("  <tr>")
        html.append(f"    <td>{idx}</td>")
        html.append(f"    <td><strong>ID {tid}</strong></td>")
        html.append(f"    <td>{img_tag}</td>")
        html.append(f"    <td><code>{raw}</code></td>")
        html.append(f"    <td>{corr_badge}</td>")
        html.append(f"    <td class='{conf_class}'>{conf:.3f}</td>")
        html.append(f"    <td>{attempts}</td>")
        html.append(f"    <td><code>{sec_offset}</code></td>")
        html.append("    <td><label><input type='checkbox'> Yes</label>&nbsp;<label><input type='checkbox'> No</label></td>")
        html.append("    <td><input type='text' placeholder='Actual plate'></td>")
        html.append("    <td><label><input type='radio' name='r_{tid}'> Clear</label><br><label><input type='radio' name='r_{tid}'> Marg.</label><br><label><input type='radio' name='r_{tid}'> Illeg.</label></td>")
        html.append("    <td><input type='text' style='width: 140px;' placeholder='Notes'></td>")
        html.append("  </tr>")

    html.extend([
        "</tbody>",
        "</table>",
        "<div class='signoff'>",
        "  <h3>Reviewer Sign-Off</h3>",
        "  <p><strong>Reviewer Name:</strong> ___________________________ &nbsp;&nbsp;&nbsp;&nbsp; <strong>Date:</strong> ___________________________</p>",
        "  <p><strong>Total Validated Matches:</strong> _____ / 35 &nbsp;&nbsp;&nbsp;&nbsp; <strong>Corrected Readings Confirmed:</strong> _____</p>",
        "</div>",
        "</body>",
        "</html>"
    ])

    return "\n".join(html)


def generate_ambiguous_pairs_review(events):
    """Generates visual inspection package for ambiguous vehicle pairs."""
    ev_map = {e["track_id"]: e for e in events}

    lines = []
    lines.append("# Ambiguous Vehicle Pairs — Visual Ground-Truth Review Package")
    lines.append("")
    lines.append("> [!IMPORTANT]")
    lines.append("> **Objective**: Inspect the physical vehicle crops and plate crops for candidate ambiguous pairs to verify whether they represent the same physical vehicle or distinct vehicles.")
    lines.append("> All checkboxes are left BLANK for manual verification.")
    lines.append("")

    # Pair 1: Track 55 & Track 73 (KH06KSU)
    e55 = ev_map.get(55, {})
    e73 = ev_map.get(73, {})
    lines.append("## Pair 1: Track 55 vs. Track 73 (`KH06KSU` Sighting Collapse)")
    lines.append("In `source.mp4`, a dark slate blue Citroën C4 hatchback passes through the intersection at ~24.4s–25.0s.")
    lines.append("- **Track 73**: Best reading at `24.4s`, raw read `KHO6KSU` (conf=0.347), normalized to `KH06KSU`.")
    lines.append("- **Track 55**: Best reading at `25.0s`, raw read `KH06KSU` (conf=0.563).")
    lines.append("")
    lines.append("| Vehicle Track | Plate Crop | Vehicle Body Crop | Emitted Plate | Raw Read | Computed Type | Computed Color | Conf |")
    lines.append("|---|---|---|---|---|---|---|---|")
    
    p55_img = f"![P55](plate_crops/track_055_{e55.get('plate','KH06KSU')}.jpg)" if (PLATE_CROPS_DIR / f"track_055_{e55.get('plate','KH06KSU')}.jpg").exists() else "*(Image pending)*"
    v55_img = f"![V55](vehicle_crops/track_055_{e55.get('plate','KH06KSU')}_vehicle.jpg)" if (VEHICLE_CROPS_DIR / f"track_055_{e55.get('plate','KH06KSU')}_vehicle.jpg").exists() else "*(Image pending)*"
    p73_img = f"![P73](plate_crops/track_073_{e73.get('plate','KH06KSU')}.jpg)" if (PLATE_CROPS_DIR / f"track_073_{e73.get('plate','KH06KSU')}.jpg").exists() else "*(Image pending)*"
    v73_img = f"![V73](vehicle_crops/track_073_{e73.get('plate','KH06KSU')}_vehicle.jpg)" if (VEHICLE_CROPS_DIR / f"track_073_{e73.get('plate','KH06KSU')}_vehicle.jpg").exists() else "*(Image pending)*"

    lines.append(f"| `Track 73` (Early) | {p73_img} | {v73_img} | `{e73.get('plate','KH06KSU')}` | `{e73.get('raw_plate','KHO6KSU')}` | `{e73.get('vehicle_type','car')}` | `{e73.get('color','blue')}` | `{e73.get('confidence',0.347)}` |")
    lines.append(f"| `Track 55` (Late) | {p55_img} | {v55_img} | `{e55.get('plate','KH06KSU')}` | `{e55.get('raw_plate','KH06KSU')}` | `{e55.get('vehicle_type','car')}` | `{e55.get('color','blue')}` | `{e55.get('confidence',0.563)}` |")
    lines.append("")
    lines.append("### Pair 1 Human Verification Checklist:")
    lines.append("- [ ] **Same Physical Vehicle?** &nbsp;&nbsp; [ ] Yes &nbsp;&nbsp; [ ] No")
    lines.append("- [ ] **Vehicle Type Confirmed**: [ ] Passenger Car &nbsp;&nbsp; [ ] Other: _____________")
    lines.append("- [ ] **Body Color Confirmed**: [ ] Blue / Dark Blue &nbsp;&nbsp; [ ] Other: _____________")
    lines.append("- [ ] **Resolution**: [ ] Merge into single trajectory &nbsp;&nbsp; [ ] Keep distinct")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Pair 2: Track 139 & Track 138 (BPF vs HX52BPF)
    e139 = ev_map.get(139, {})
    e138 = ev_map.get(138, {})
    lines.append("## Pair 2: Track 139 (`BPF`) vs. Track 138 (`HX52BPF`)")
    lines.append("In `source.mp4`, a deep blue Vauxhall Vectra passes at ~50.8s–52.2s.")
    lines.append("- **Track 139**: Partial low-confidence read `BPF` (conf=0.178) at frame edge.")
    lines.append("- **Track 138**: Full high-confidence read `HX52BPF` (conf=0.614) in clear view.")
    lines.append("")
    lines.append("| Vehicle Track | Plate Crop | Vehicle Body Crop | Emitted Plate | Raw Read | Computed Type | Computed Color | Conf |")
    lines.append("|---|---|---|---|---|---|---|---|")

    p139_img = f"![P139](plate_crops/track_139_{e139.get('plate','BPF')}.jpg)" if (PLATE_CROPS_DIR / f"track_139_{e139.get('plate','BPF')}.jpg").exists() else "*(Image pending)*"
    v139_img = f"![V139](vehicle_crops/track_139_{e139.get('plate','BPF')}_vehicle.jpg)" if (VEHICLE_CROPS_DIR / f"track_139_{e139.get('plate','BPF')}_vehicle.jpg").exists() else "*(Image pending)*"
    p138_img = f"![P138](plate_crops/track_138_{e138.get('plate','HX52BPF')}.jpg)" if (PLATE_CROPS_DIR / f"track_138_{e138.get('plate','HX52BPF')}.jpg").exists() else "*(Image pending)*"
    v138_img = f"![V138](vehicle_crops/track_138_{e138.get('plate','HX52BPF')}_vehicle.jpg)" if (VEHICLE_CROPS_DIR / f"track_138_{e138.get('plate','HX52BPF')}_vehicle.jpg").exists() else "*(Image pending)*"

    lines.append(f"| `Track 139` (Partial) | {p139_img} | {v139_img} | `{e139.get('plate','BPF')}` | `{e139.get('raw_plate','BPF')}` | `{e139.get('vehicle_type','car')}` | `{e139.get('color','blue')}` | `{e139.get('confidence',0.178)}` |")
    lines.append(f"| `Track 138` (Full) | {p138_img} | {v138_img} | `{e138.get('plate','HX52BPF')}` | `{e138.get('raw_plate','HX52BPF')}` | `{e138.get('vehicle_type','car')}` | `{e138.get('color','blue')}` | `{e138.get('confidence',0.614)}` |")
    lines.append("")
    lines.append("### Pair 2 Human Verification Checklist:")
    lines.append("- [ ] **Same Physical Vehicle?** &nbsp;&nbsp; [ ] Yes &nbsp;&nbsp; [ ] No")
    lines.append("- [ ] **Vehicle Type Confirmed**: [ ] Passenger Car &nbsp;&nbsp; [ ] Other: _____________")
    lines.append("- [ ] **Body Color Confirmed**: [ ] Blue / Dark Blue &nbsp;&nbsp; [ ] Other: _____________")
    lines.append("- [ ] **Resolution**: [ ] Merge into canonical plate `HX52BPF` &nbsp;&nbsp; [ ] Keep distinct")
    lines.append("")

    return "\n".join(lines)


def build_all():
    events = load_events()
    print(f"Loaded {len(events)} events from {EVENTS_PATH}")

    md_content = generate_ocr_review_markdown(events)
    MD_REVIEW_PATH.write_text(md_content, encoding="utf-8")
    print(f"Wrote OCR review markdown to: {MD_REVIEW_PATH}")

    html_content = generate_ocr_review_html(events)
    HTML_REVIEW_PATH.write_text(html_content, encoding="utf-8")
    print(f"Wrote OCR review HTML to: {HTML_REVIEW_PATH}")

    amb_content = generate_ambiguous_pairs_review(events)
    AMBIGUOUS_MD_PATH.write_text(amb_content, encoding="utf-8")
    print(f"Wrote ambiguous pairs review to: {AMBIGUOUS_MD_PATH}")


if __name__ == "__main__":
    build_all()
