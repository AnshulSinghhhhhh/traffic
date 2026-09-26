import json
import os

with open('events.json') as f:
    events = json.load(f)

sizes = [len(json.dumps(e).encode('utf-8')) for e in events]
avg_event_bytes = sum(sizes) / len(sizes)

# Raw frame
w, h = 3840, 2160
raw_frame_bytes = w * h * 3

# Compressed video
video_bytes = os.path.getsize('source.mp4')
duration_s = 60.0
fps = 30.0
total_frames = 1800
compressed_bytes_per_frame = video_bytes / total_frames

total_events_bytes = sum(sizes)

# Reductions
raw_frame_reduction = (1.0 - (avg_event_bytes / raw_frame_bytes)) * 100.0
comp_frame_reduction = (1.0 - (avg_event_bytes / compressed_bytes_per_frame)) * 100.0
stream_bandwidth_reduction = (1.0 - (total_events_bytes / video_bytes)) * 100.0

print(f"Average POST /events JSON size: {avg_event_bytes:.1f} bytes (Min: {min(sizes)}, Max: {max(sizes)})")
print(f"Raw 4K Video Frame (3840x2160x3): {raw_frame_bytes:,} bytes ({raw_frame_bytes / (1024*1024):.2f} MB)")
print(f"Compressed Frame (H.264 avg): {compressed_bytes_per_frame:,.1f} bytes ({compressed_bytes_per_frame / 1024:.2f} KB)")
print(f"Total Video Stream (60s): {video_bytes:,} bytes ({video_bytes / (1024*1024):.2f} MB, {video_bytes*8/duration_s/1e6:.2f} Mbps)")
print(f"Total JSON Events Stream (60s, 35 events): {total_events_bytes:,} bytes ({total_events_bytes / 1024:.2f} KB, {total_events_bytes*8/duration_s/1e3:.2f} kbps)")
print(f"Bandwidth Reduction vs Raw 4K Frame: {raw_frame_reduction:.5f}%")
print(f"Bandwidth Reduction vs Compressed H.264 Frame: {comp_frame_reduction:.4f}%")
print(f"Total Network Bandwidth Reduction (60s stream): {stream_bandwidth_reduction:.5f}%")
