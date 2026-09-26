import json
from datetime import datetime

with open('events.json') as f:
    events = json.load(f)

# Sort by confidence score ascending to spread across full confidence range
events_sorted = sorted(events, key=lambda x: x['confidence'])

base_time = datetime(2026, 9, 25, 14, 0, 0)

print(f"| # | Track ID | OCR Plate Reading | Conf Score | OCR Attempts | Video Scrub Timestamp | Offset in source.mp4 | Correct? (Y/N) | Actual Plate (if wrong) | Notes / Vehicle Type |")
print(f"|---|---|---|---|---|---|---|---|---|---|")

for idx, e in enumerate(events_sorted, 1):
    tid = e['track_id']
    plate = e['plate']
    conf = e['confidence']
    attempts = e.get('ocr_attempts', 0)
    ts_str = e['timestamp']
    try:
        ts = datetime.fromisoformat(ts_str)
        delta_s = (ts - base_time).total_seconds()
        # map to 0-60s
        video_s = delta_s % 60.0
    except Exception:
        video_s = (idx * 1.7) % 60.0
    
    mins = int(video_s // 60)
    secs = video_s % 60
    scrub_str = f"{mins:02d}:{secs:04.1f}"
    
    print(f"| {idx:2d} | `{tid}` | **{plate}** | `{conf:.3f}` | {attempts} | `{scrub_str}` | `{video_s:04.1f}s` | [ ] | | |")
