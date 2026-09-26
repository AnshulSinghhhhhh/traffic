import collections
import json

with open('events.json') as f:
    events = json.load(f)

print(f"Total events: {len(events)}")
plates = [e['plate'] for e in events]
unique_plates = set(plates)
track_ids = [e['track_id'] for e in events]
unique_tracks = set(track_ids)

print(f"Unique vehicles (track_ids): {len(unique_tracks)}")
print(f"Unique plates: {len(unique_plates)}")

for e in events:
    if e['track_id'] in (55, 73) or 'KH06' in e['plate'] or 'KHO6' in e['plate']:
        print("Target track:", e)

print("\nAll corrected plates (was_corrected == True):")
for e in events:
    if e.get('was_corrected'):
        print(f"Track {e['track_id']}: Raw '{e.get('raw_plate')}' -> Corrected '{e['plate']}' (conf: {e['confidence']})")

print("\nDuplicate plates check:")
counts = collections.Counter(plates)
for plate, cnt in counts.items():
    if cnt > 1:
        matched = [e for e in events if e['plate'] == plate]
        print(f"Duplicate plate {plate} (occurs {cnt} times):")
        for m in matched:
            print(f"   Track {m['track_id']}: raw='{m.get('raw_plate')}', conf={m['confidence']}, was_corrected={m.get('was_corrected')}")
