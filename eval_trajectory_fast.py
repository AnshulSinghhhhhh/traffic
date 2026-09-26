import urllib.request
import json
import time

camera_order = ['CAM_01', 'CAM_02', 'CAM_03', 'CAM_04']
cam_rank = {c: i for i, c in enumerate(camera_order)}

with open('events.json') as f:
    events = json.load(f)

plates = sorted(list(set(e['plate'] for e in events)))

correct = 0
total = 0
results = []

for p in plates:
    url = f"http://localhost:8000/trajectory/{p}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        cams = [x['camera_id'] for x in data]
        ranks = [cam_rank[c] for c in cams if c in cam_rank]
        is_strictly_ordered = all(ranks[i] < ranks[i+1] for i in range(len(ranks)-1))
        if is_strictly_ordered:
            correct += 1
        total += 1
        results.append((p, cams, is_strictly_ordered))

accuracy = (correct / total) * 100.0 if total > 0 else 0.0

print(f"TOTAL_PLATES={total}")
print(f"CORRECT_PLATES={correct}")
print(f"ACCURACY_PCT={accuracy:.2f}")

for p, cams, ok in results:
    print(f"TRAJ|{p}|{'->'.join(cams)}|{ok}")
