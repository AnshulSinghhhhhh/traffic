"""
run_tracker_extraction.py — Runs YOLOv8n + SORT tracker + YOLOv8 plate detector
on source.mp4 (exactly matching ml/detect.ipynb logic).

Extracts the exact plate and vehicle crops for each track_id at the exact frame/timestamp
recorded in events.json (or the highest-confidence plate detection during that track's lifetime).
"""

import os
import json
import re
import pathlib
import cv2
import numpy as np
from datetime import datetime, timedelta
from ultralytics import YOLO

ROOT_DIR = pathlib.Path(__file__).parent
VIDEO_PATH = ROOT_DIR / "source.mp4"
EVENTS_PATH = ROOT_DIR / "events.json"
PLATE_CROPS_DIR = ROOT_DIR / "plate_crops"
VEHICLE_CROPS_DIR = ROOT_DIR / "vehicle_crops"
PLATE_WEIGHTS_PATH = ROOT_DIR / "idahr_plate_detector.pt"
VEHICLE_WEIGHTS_PATH = ROOT_DIR / "yolov8n.pt"

# --- CONFIG (Cell 10 of notebook) ---
SAMPLE_FPS = 5
VEHICLE_CONF_THRESHOLD = 0.4
PLATE_DET_CONF = 0.25
MIN_PLATE_AREA_PX = 900
MIN_VEHICLE_AREA_FOR_PLATE_PX = 4000
SORT_MAX_AGE = 12
SORT_MIN_HITS = 2
SORT_IOU_THRESHOLD = 0.2
VEHICLE_CLASS_IDS = [2, 3, 5, 7]
VEHICLE_CLASS_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# --- SORT TRACKER (Cell 8 of notebook) ---
def linear_assignment(cost_matrix):
    try:
        import lap
        _, x, y = lap.lapjv(cost_matrix, extend_cost=True)
        return np.array([[y[i], i] for i in x if i >= 0])
    except ImportError:
        from scipy.optimize import linear_sum_assignment
        x, y = linear_sum_assignment(cost_matrix)
        return np.array(list(zip(x, y)))

def iou_batch(bb_test, bb_gt):
    bb_gt = np.expand_dims(bb_gt, 0)
    bb_test = np.expand_dims(bb_test, 1)
    xx1 = np.maximum(bb_test[..., 0], bb_gt[..., 0])
    yy1 = np.maximum(bb_test[..., 1], bb_gt[..., 1])
    xx2 = np.minimum(bb_test[..., 2], bb_gt[..., 2])
    yy2 = np.minimum(bb_test[..., 3], bb_gt[..., 3])
    w = np.maximum(0., xx2 - xx1)
    h = np.maximum(0., yy2 - yy1)
    wh = w * h
    o = wh / ((bb_test[..., 2] - bb_test[..., 0]) * (bb_test[..., 3] - bb_test[..., 1])
              + (bb_gt[..., 2] - bb_gt[..., 0]) * (bb_gt[..., 3] - bb_gt[..., 1]) - wh)
    return o

class KalmanBoxTracker(object):
    count = 0
    def __init__(self, bbox):
        from filterpy.kalman import KalmanFilter
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.array([
            [1,0,0,0,1,0,0], [0,1,0,0,0,1,0], [0,0,1,0,0,0,1], [0,0,0,1,0,0,0],
            [0,0,0,0,1,0,0], [0,0,0,0,0,1,0], [0,0,0,0,0,0,1]
        ])
        self.kf.H = np.array([
            [1,0,0,0,0,0,0], [0,1,0,0,0,0,0], [0,0,1,0,0,0,0], [0,0,0,1,0,0,0]
        ])
        self.kf.R[2:,2:] *= 10.
        self.kf.P[4:,4:] *= 1000.
        self.kf.P *= 10.
        self.kf.Q[-1,-1] *= 0.01
        self.kf.Q[4:,4:] *= 0.01
        self.kf.x[:4] = self._convert_bbox_to_z(bbox)
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0

    def update(self, bbox):
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(self._convert_bbox_to_z(bbox))

    def predict(self):
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        self.history.append(self._convert_x_to_bbox(self.kf.x))
        return self.history[-1]

    def get_state(self):
        return self._convert_x_to_bbox(self.kf.x)

    def _convert_bbox_to_z(self, bbox):
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = bbox[0] + w / 2.0
        y = bbox[1] + h / 2.0
        s = w * h
        r = w / float(h) if h > 0 else 0
        return np.array([x, y, s, r]).reshape((4, 1))

    def _convert_x_to_bbox(self, x, score=None):
        w = np.sqrt(x[2] * x[3])
        h = x[2] / w if w > 0 else 0
        return np.array([x[0] - w/2., x[1] - h/2., x[0] + w/2., x[1] + h/2.]).reshape((1, 4))

def associate_detections_to_trackers(detections, trackers, iou_threshold=0.3):
    if len(trackers) == 0:
        return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0, 5), dtype=int)
    iou_matrix = iou_batch(detections, trackers)
    if min(iou_matrix.shape) > 0:
        a = (iou_matrix > iou_threshold).astype(np.int32)
        if a.sum(1).max() == 1 and a.sum(0).max() == 1:
            matched_indices = np.stack(np.where(a), axis=1)
        else:
            matched_indices = linear_assignment(-iou_matrix)
    else:
        matched_indices = np.empty(shape=(0, 2))

    unmatched_detections = []
    for d, det in enumerate(detections):
        if d not in matched_indices[:, 0]:
            unmatched_detections.append(d)
    unmatched_trackers = []
    for t, trk in enumerate(trackers):
        if t not in matched_indices[:, 1]:
            unmatched_trackers.append(t)

    matches = []
    for m in matched_indices:
        if iou_matrix[m[0], m[1]] < iou_threshold:
            unmatched_detections.append(m[0])
            unmatched_trackers.append(m[1])
        else:
            matches.append(m.reshape(1, 2))
    if len(matches) == 0:
        matches = np.empty((0, 2), dtype=int)
    else:
        matches = np.concatenate(matches, axis=0)
    return matches, np.array(unmatched_detections), np.array(unmatched_trackers)

class Sort(object):
    def __init__(self, max_age=1, min_hits=3, iou_threshold=0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers = []
        self.frame_count = 0

    def update(self, dets=np.empty((0, 5))):
        self.frame_count += 1
        trks = np.zeros((len(self.trackers), 5))
        to_del = []
        ret = []
        for t, trk in enumerate(trks):
            pos = self.trackers[t].predict()[0]
            trk[:] = [pos[0], pos[1], pos[2], pos[3], 0]
            if np.any(np.isnan(pos)):
                to_del.append(t)
        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
        for t in reversed(to_del):
            self.trackers.pop(t)
        matched, unmatched_dets, unmatched_trks = associate_detections_to_trackers(dets, trks, self.iou_threshold)

        for m in matched:
            self.trackers[m[1]].update(dets[m[0], :])

        for i in unmatched_dets:
            trk = KalmanBoxTracker(dets[i, :])
            self.trackers.append(trk)
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            d = trk.get_state()[0]
            if (trk.time_since_update < 1) and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                ret.append(np.concatenate((d, [trk.id + 1])).reshape(1, -1))
            i -= 1
            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)
        if len(ret) > 0:
            return np.concatenate(ret)
        return np.empty((0, 5))

# --- MATCHING HELPER (Cell 18 of notebook) ---
def match_plate_to_vehicle(plate_bbox, tracked):
    px1, py1, px2, py2 = plate_bbox
    pcx, pcy = (px1 + px2) / 2.0, (py1 + py2) / 2.0
    for x1, y1, x2, y2, tid in tracked:
        if x1 <= pcx <= x2 and y1 <= pcy <= y2:
            return int(tid)
    return None

def main():
    print("Loading events...")
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        events = json.load(f)
    event_tids = {e["track_id"]: e for e in events}
    print(f"Target tracks: {sorted(event_tids.keys())}")

    print("Loading models...")
    vehicle_model = YOLO(str(VEHICLE_WEIGHTS_PATH))
    plate_model = YOLO(str(PLATE_WEIGHTS_PATH))

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, round(native_fps / SAMPLE_FPS))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {total_frames} frames, interval {frame_interval}, {native_fps} fps")

    tracker = Sort(max_age=SORT_MAX_AGE, min_hits=SORT_MIN_HITS, iou_threshold=SORT_IOU_THRESHOLD)
    base_time = datetime(2026, 8, 23, 8, 0, 0)

    # For each track_id, store:
    # {frame_idx: {"plate_crop": ..., "plate_bbox": ..., "det_conf": ..., "v_crop": ..., "v_bbox": ..., "area": ...}}
    track_observations = {tid: [] for tid in event_tids}

    sample_set = set(range(0, total_frames, frame_interval))
    processed = 0

    print("Running tracking & plate detection across all sampled frames...")
    for seq_idx in range(total_frames):
        if seq_idx not in sample_set:
            cap.grab()
            continue

        ret, frame = cap.read()
        if not ret:
            break
        processed += 1
        frame_idx = seq_idx

        # Vehicle detection
        results = vehicle_model.predict(
            frame, conf=VEHICLE_CONF_THRESHOLD, classes=VEHICLE_CLASS_IDS, verbose=False
        )
        r = results[0]
        if r.boxes is not None and len(r.boxes) > 0:
            dets = np.hstack([
                r.boxes.xyxy.cpu().numpy(),
                r.boxes.conf.cpu().numpy().reshape(-1, 1),
            ])
        else:
            dets = np.empty((0, 5))

        tracked = tracker.update(dets)

        # Vehicle crops map
        tracked_vehicles = {}
        for x1, y1, x2, y2, tid in tracked:
            tid = int(tid)
            vx1, vy1 = max(0, int(x1)), max(0, int(y1))
            vx2, vy2 = min(frame_w, int(x2)), min(frame_h, int(y2))
            v_crop = frame[vy1:vy2, vx1:vx2] if (vx2 > vx1 and vy2 > vy1) else None
            tracked_vehicles[tid] = {
                "bbox": [vx1, vy1, vx2, vy2],
                "crop": v_crop,
            }

        # Filter candidates for plate match
        match_candidates = np.array([
            row for row in tracked
            if (row[2] - row[0]) * (row[3] - row[1]) >= MIN_VEHICLE_AREA_FOR_PLATE_PX
        ]) if len(tracked) > 0 else np.empty((0, 5))

        if len(match_candidates) == 0:
            continue

        # Plate detection
        plate_results = plate_model.predict(frame, conf=PLATE_DET_CONF, verbose=False)
        pr = plate_results[0]
        if pr.boxes is None or len(pr.boxes) == 0:
            continue

        p_boxes = pr.boxes.xyxy.cpu().numpy()
        p_confs = pr.boxes.conf.cpu().numpy()

        for (x1, y1, x2, y2), p_conf in zip(p_boxes, p_confs):
            px1, py1 = max(0, int(x1) - 4), max(0, int(y1) - 4)
            px2, py2 = min(frame_w, int(x2) + 4), min(frame_h, int(y2) + 4)
            if px2 <= px1 or py2 <= py1:
                continue

            area = (px2 - px1) * (py2 - py1)
            if area < MIN_PLATE_AREA_PX:
                continue

            matched_tid = match_plate_to_vehicle((px1, py1, px2, py2), match_candidates)
            if matched_tid is not None and matched_tid in track_observations:
                p_crop = frame[py1:py2, px1:px2].copy()
                v_info = tracked_vehicles.get(matched_tid, {})
                v_crop = v_info.get("crop")
                v_bbox = v_info.get("bbox")
                
                track_observations[matched_tid].append({
                    "frame_idx": frame_idx,
                    "seconds": frame_idx / native_fps,
                    "plate_bbox": [px1, py1, px2, py2],
                    "det_conf": float(p_conf),
                    "area": area,
                    "plate_crop": p_crop,
                    "vehicle_crop": v_crop.copy() if v_crop is not None else None,
                    "vehicle_bbox": v_bbox,
                })

        if processed % 50 == 0:
            print(f"  Frame {processed}/300 processed...")

    cap.release()
    print(f"\nExtraction complete across {processed} frames.")

    # Match each track to its recorded timestamp from events.json
    PLATE_CROPS_DIR.mkdir(exist_ok=True)
    VEHICLE_CROPS_DIR.mkdir(exist_ok=True)

    updated_events = []
    saved_crops = 0

    print("\n=== ASSOCIATING CROPS WITH TARGET EVENTS ===")
    for e in events:
        tid = e["track_id"]
        plate = e["plate"]
        safe_plate = re.sub(r'[^A-Za-z0-9]', '_', plate)
        obs = track_observations.get(tid, [])

        # Parse target timestamp
        ts_str = e["timestamp"]
        ts = datetime.fromisoformat(ts_str)
        target_sec = (ts - base_time).total_seconds()
        target_fidx = int(round(target_sec * native_fps))

        print(f"\nTrack {tid:3d} ({plate}): target {target_sec:.1f}s (frame ~{target_fidx}), {len(obs)} observations")

        chosen = None
        if obs:
            # First preference: observation closest in time to target_sec (within ±1.5 seconds)
            time_filtered = [o for o in obs if abs(o["seconds"] - target_sec) <= 1.5]
            if time_filtered:
                # Pick the highest quality crop (highest det_conf * area) near target time
                chosen = max(time_filtered, key=lambda o: o["det_conf"] * np.sqrt(o["area"]))
                print(f"  -> Selected nearest observation at {chosen['seconds']:.1f}s (frame {chosen['frame_idx']}, diff={chosen['seconds'] - target_sec:+.2f}s, conf={chosen['det_conf']:.3f})")
            else:
                # If none within 1.5s, pick the best quality observation overall for this track
                chosen = max(obs, key=lambda o: o["det_conf"] * np.sqrt(o["area"]))
                print(f"  -> [FALLBACK] Nearest was {abs(chosen['seconds'] - target_sec):.1f}s away; chosen frame {chosen['frame_idx']} at {chosen['seconds']:.1f}s")
        else:
            print(f"  -> [WARNING] No plate observations found for track {tid}!")

        if chosen is not None:
            # Save crops
            p_path = PLATE_CROPS_DIR / f"track_{tid:03d}_{safe_plate}.jpg"
            cv2.imwrite(str(p_path), chosen["plate_crop"])
            saved_crops += 1

            if chosen["vehicle_crop"] is not None:
                v_path = VEHICLE_CROPS_DIR / f"track_{tid:03d}_{safe_plate}_vehicle.jpg"
                cv2.imwrite(str(v_path), chosen["vehicle_crop"])

            e_copy = dict(e)
            e_copy["best_frame_idx"] = chosen["frame_idx"]
            e_copy["plate_bbox"] = chosen["plate_bbox"]
            e_copy["vehicle_bbox"] = chosen["vehicle_bbox"]
            updated_events.append(e_copy)
        else:
            updated_events.append(dict(e))

    # Write updated events.json
    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(updated_events, f, indent=2)

    print(f"\nSaved {saved_crops}/35 plate crops to {PLATE_CROPS_DIR}")
    print(f"Updated {EVENTS_PATH} with verified frame indices and bounding boxes.")

if __name__ == "__main__":
    main()
