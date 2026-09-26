import json
import statistics

with open('events.json') as f:
    events = json.load(f)

confs = [e['confidence'] for e in events]
print(f"Total events: {len(events)}")
print(f"Confidence stats:")
print(f"  Mean:   {statistics.mean(confs):.3f}")
print(f"  Median: {statistics.median(confs):.3f}")
print(f"  Min:    {min(confs):.3f}")
print(f"  Max:    {max(confs):.3f}")

ocr_attempts = [e['ocr_attempts'] for e in events]
print(f"OCR attempts stats:")
print(f"  Total attempts: {sum(ocr_attempts)}")
print(f"  Mean per track: {statistics.mean(ocr_attempts):.1f}")
print(f"  Min: {min(ocr_attempts)}")
print(f"  Max: {max(ocr_attempts)}")
