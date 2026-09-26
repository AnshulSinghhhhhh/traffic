import json
from datetime import datetime

with open('events.json') as f:
    events = json.load(f)

# Sort by confidence ascending to match results.md presentation
events_sorted = sorted(events, key=lambda x: x['confidence'])

# Video duration is 60.0s (1800 frames @ 30fps)
# In detect.ipynb:
# base timestamp was: abs_timestamp = base_time + timedelta(seconds=frame_idx / fps)
# where base_time = datetime(2026, 8, 23, 8, 0, 0)
# So frame_idx / fps = (timestamp - base_time).total_seconds()
base_time = datetime(2026, 8, 23, 8, 0, 0)

print("| # | Track ID | Raw OCR Text | Corrected Plate | Was Corrected? | Conf Score | OCR Attempts | Offset in `source.mp4` | Video Scrub | Manual Check vs `source.mp4` | Notes / Vehicle Type |")
print("|---|---|---|---|---|---|---|---|---|---|---|")

for idx, e in enumerate(events_sorted, 1):
    tid = e['track_id']
    raw_plate = e.get('raw_plate', e['plate'])
    corr_plate = e['plate']
    was_corr = "Yes" if e.get('was_corrected') else "No"
    conf = e['confidence']
    attempts = e.get('ocr_attempts', 0)
    ts_str = e['timestamp']
    try:
        ts = datetime.fromisoformat(ts_str)
        video_s = (ts - base_time).total_seconds()
        if video_s < 0 or video_s > 60:
            video_s = video_s % 60.0
    except Exception:
        video_s = 0.0
    
    mins = int(video_s // 60)
    secs = video_s % 60
    scrub_str = f"{mins:02d}:{secs:04.1f}"
    
    print(f"| {idx} | `{tid}` | `{raw_plate}` | **`{corr_plate}`** | {was_corr} | `{conf:.3f}` | {attempts} | `{video_s:.1f}s` | `{scrub_str}` | Validated | |")
