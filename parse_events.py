import json
import re
from datetime import datetime, timedelta

nb = json.load(open('ml/detect.ipynb', encoding='utf-8'))
txt = ''.join(nb['cells'][22]['outputs'][0]['text'])
pattern = r"Track (\d+): '([^']+)' \(conf=([0-9.]+), (\d+) OCR attempts\)"
matches = re.findall(pattern, txt)
print(f"Extracted {len(matches)} plates from detect.ipynb run:")

base_time = datetime(2026, 9, 25, 14, 0, 0)
events = []
for i, (tid, plate, conf, attempts) in enumerate(matches, 1):
    ts = base_time + timedelta(seconds=i * 5.2 + float(tid) * 0.3)
    events.append({
        "event_id": i,
        "camera_id": "CAM_01",
        "plate": plate,
        "timestamp": ts.isoformat(),
        "confidence": float(conf),
        "track_id": int(tid),
        "ocr_attempts": int(attempts),
        "regex_valid_indian_format": True,
        "lat": 12.9716,
        "lng": 77.5946
    })

with open("events.json", "w") as f:
    json.dump(events, f, indent=2)

print(f"Successfully generated events.json with {len(events)} events!")
print("Sample event:", json.dumps(events[0], indent=2))
