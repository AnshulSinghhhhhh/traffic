"""
simulate_multi_camera.py — turns ONE base events.json (from a single Kaggle
T4 run of the ANPR notebook) into several synthetic camera-node event
streams, so you can test/demo cross-camera trajectory stitching without a
real multi-camera dataset.

WHY THIS APPROACH (vs. literally splitting the video into 4 disjoint clips
and running detection on each piece separately):
  - You asked for the same plates to show up at every camera, just at
    different times. A disjoint video split can't guarantee that — different
    seconds of footage usually contain different vehicles. Replaying the
    same detected plate set through each camera's clock does guarantee it.
  - It doesn't spend Kaggle's free T4 quota re-running YOLO + PaddleOCR
    (the expensive part) four separate times on the same footage.
  - It still exercises the actual thing you need to prove for the paper:
    that the central system can correctly stitch cross-camera events into
    a trajectory when each "camera" only ever sends small structured JSON
    (plate, camera_id, timestamp, lat, lng, confidence) — never raw video.

If you later get 4 genuinely different camera angles of the same
junction/road, swap this script out and run the notebook once per angle
instead — the central system doesn't need to know the difference.

HOW IT WORKS
  1. Loads the base events.json your Kaggle run produced (one row per
     tracked vehicle with a plate reading).
  2. For each camera in CAMERAS below: copies every base event, reassigns
     camera_id + lat/lng to that camera, shifts the timestamp by the
     camera's offset_s (simulated travel time from the point the source
     footage was shot) plus small random jitter, and randomly drops some
     vehicles per that camera's dropout rate (a real camera doesn't catch
     every passing plate either — occlusion, lane position, glare).
  3. Merges every camera's synthetic events into one timeline, sorted by
     the shifted timestamp — this is the order a real deployment would see
     them arrive in.
  4. Either writes them to per-camera JSON files, or POSTs them one at a
     time to your running FastAPI ingestion endpoint with a small delay
     between sends, so the dashboard fills in like a live multi-camera feed.

USAGE
    python simulate_multi_camera.py --input events.json --mode files
    python simulate_multi_camera.py --input events.json --mode api \
        --api-url http://localhost:8000/events --delay 1.5

Edit the CAMERAS list below with real lat/lng for your demo route and
however many camera nodes you want (the SIH blueprint scoped 4).
"""
import argparse
import copy
import json
import random
import time
from datetime import datetime, timedelta

# --- Camera network config: edit lat/lng, travel-time offsets, dropout ---
CAMERAS = [
    {"camera_id": "CAM_01", "name": "Junction A",      "lat": 12.9716, "lng": 77.5946, "offset_s": 0,   "dropout": 0.00},
    {"camera_id": "CAM_02", "name": "Ring Road North",  "lat": 12.9815, "lng": 77.6094, "offset_s": 240, "dropout": 0.10},
    {"camera_id": "CAM_03", "name": "Market Circle",    "lat": 12.9925, "lng": 77.6205, "offset_s": 560, "dropout": 0.15},
    {"camera_id": "CAM_04", "name": "Highway Toll",     "lat": 13.0041, "lng": 77.6340, "offset_s": 900, "dropout": 0.20},
]
JITTER_SECONDS = 8  # +/- random noise added per camera, so hops aren't perfectly uniform


def parse_ts(raw):
    """Best-effort timestamp parse — adjust this if your events.json uses a
    different format than ISO 8601 (check one entry's 'timestamp' field)."""
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return datetime.now()


def load_base_events(path):
    with open(path) as f:
        events = json.load(f)
    if not events:
        raise SystemExit(f"{path} has no events — run the notebook pipeline first.")
    return events


def build_camera_events(base_events, camera, next_id):
    out = []
    for base in base_events:
        if random.random() < camera["dropout"]:
            continue  # this camera "missed" this vehicle — realistic, not a bug
        e = copy.deepcopy(base)
        base_ts = parse_ts(e.get("timestamp", datetime.now().isoformat()))
        jitter = random.uniform(-JITTER_SECONDS, JITTER_SECONDS)
        shifted_ts = base_ts + timedelta(seconds=camera["offset_s"] + jitter)

        e["event_id"] = next_id()
        e["camera_id"] = camera["camera_id"]
        e["camera_name"] = camera["name"]
        e["lat"] = camera["lat"]
        e["lng"] = camera["lng"]
        e["timestamp"] = shifted_ts.isoformat()
        out.append(e)
    return out


def make_id_counter(start=1):
    n = start - 1
    def _next():
        nonlocal n
        n += 1
        return n
    return _next


def write_files(camera_streams):
    for cam_id, events in camera_streams.items():
        path = f"{cam_id.lower()}_events.json"
        with open(path, "w") as f:
            json.dump(events, f, indent=2)
        print(f"{cam_id}: {len(events)} events -> {path}")


def send_to_api(all_events_sorted, api_url, delay):
    import urllib.request

    for e in all_events_sorted:
        payload = {
            "plate": e.get("plate"),
            "camera_id": e.get("camera_id"),
            "timestamp": e.get("timestamp"),
            "lat": e.get("lat"),
            "lng": e.get("lng"),
            "confidence": e.get("confidence"),
            "track_id": e.get("track_id"),
            "vehicle_type": e.get("vehicle_type"),
            "color": e.get("color"),
        }
        body = json.dumps(payload).encode()
        req = urllib.request.Request(api_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"[{e['camera_id']}] {e['plate']} @ {e['timestamp']} -> {resp.status}")
        except Exception as exc:  # noqa: BLE001 — this is a demo script, surface any failure plainly
            print(f"[{e['camera_id']}] {e['plate']} -> FAILED: {exc}")
        time.sleep(delay)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="events.json", help="base events.json from the Kaggle run")
    ap.add_argument("--mode", choices=["files", "api"], default="files")
    ap.add_argument("--api-url", default="http://localhost:8000/events")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between API sends, in mode=api")
    args = ap.parse_args()

    base_events = load_base_events(args.input)
    next_id = make_id_counter()

    camera_streams = {}
    all_events = []
    for camera in CAMERAS:
        events = build_camera_events(base_events, camera, next_id)
        camera_streams[camera["camera_id"]] = events
        all_events.extend(events)

    all_events.sort(key=lambda e: e["timestamp"])

    print(f"\nBase plates: {len(base_events)} | Cameras: {len(CAMERAS)} | Total synthetic events: {len(all_events)}\n")

    if args.mode == "files":
        write_files(camera_streams)
        with open("all_camera_events_timeline.json", "w") as f:
            json.dump(all_events, f, indent=2)
        print("Combined, time-sorted timeline -> all_camera_events_timeline.json")
    else:
        print(f"Streaming {len(all_events)} events to {args.api_url} ({args.delay}s apart)...")
        send_to_api(all_events, args.api_url, args.delay)


if __name__ == "__main__":
    main()
