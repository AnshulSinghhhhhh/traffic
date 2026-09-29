# 04 — Data Provenance & Simulation Testbed Specification

**Document Status**: COMPLETED  
**Verification Date**: 2026-09-29  
**Source Files**: `source.mp4`, `simulate_multi_camera.py`, `cam_01_events.json`–`cam_04_events.json`, `all_camera_events_timeline.json`  

---

## 1. Video Footage Provenance & Technical Specifications

### 1.1 Physical File Metadata (`source.mp4`)
Extracted and verified directly using OpenCV (`cv2.VideoCapture`) and OS filesystem metadata:

| Attribute | Measured Value | Unit / Standard | Status |
|---|---|---|---|
| **Filename** | `source.mp4` | MPEG-4 Part 14 container | **FOUND** |
| **Duration** | `60.00` | seconds (1.00 minute) | **MEASURED** |
| **Frame Rate** | `30.0` | frames per second (fps) | **MEASURED** |
| **Total Frames** | `1,800` | video frames | **MEASURED** |
| **Spatial Resolution** | `3840 × 2160` | 4K Ultra High Definition (UHD, 16:9) | **MEASURED** |
| **Color Space** | BGR / YUV420p | 24-bit color depth | **MEASURED** |
| **Video Compression** | H.264 / AVC | High Profile | **MEASURED** |
| **File Size on Disk** | `183,842,039` | bytes ($175.33\text{ MB}$) | **MEASURED** |
| **Average Bitrate** | `24,512.27` | kbps ($24.51\text{ Mbps}$ / $3.06\text{ MB/s}$) | **MEASURED** |
| **Uncompressed Frame Size** | `24,883,200` | bytes ($23.73\text{ MB}$ per uncompressed frame) | **MEASURED** |

### 1.2 Video Provenance, Licensing & Consent Audit
- **Footage Origin**: Real-world daytime arterial traffic recording depicting mixed passenger vehicles, delivery vans, and commercial vehicles on a multi-lane UK roadway under overcast sky conditions.
- **Specific Recording Provenance**: **MISSING**. The codebase does not contain a copyright license agreement, model/property release form, or metadata attributing the source URL (e.g. Pexels, YouTube Creative Commons, Kaggle dataset, or personal camera recording).
- **Paper Action Required**: The user must provide the explicit provenance and license (e.g. Creative Commons CC-BY, personal filming with public road privacy release, or commercial open-access license) to satisfy IEEE submission ethics guidelines (see [10_ethics_privacy.md](file:///c:/Users/anshu/Documents/newstart/Traffic/paper_evidence/10_ethics_privacy.md)).

---

## 2. Edge Execution of Detection & Recognition on `source.mp4`

The video was evaluated through `ml/detect.ipynb` under the following deterministic procedure:

1. **Temporal Stride Subsampling**:
   - Stride factor: $S = \text{round}(30.0 / 5.0) = 6$ frames.
   - Exactly **300 frames** were sampled and ingested ($t = 0.0\text{s}, 0.2\text{s}, 0.4\text{s}, \dots, 59.8\text{s}$), skipping intermediate frames via single-pass `cap.grab()` and decoding only selected sample indices via `cap.read()`.
2. **Vehicle Tracking**:
   - YOLOv8n object detection ran once per sampled frame (`conf = 0.40`).
   - The SORT tracker assigned and maintained state for **138 discrete vehicle tracks**.
3. **Plate Localization & Association**:
   - The fine-tuned YOLOv8 plate model ran once per sampled frame (`conf = 0.25`), yielding **502 raw candidate plate boxes**.
   - Spatial containment geometry successfully associated **492 plate boxes** with tracked vehicle bounds; **10 boxes** fell in background foliage or road shoulders without vehicle overlap and were safely discarded.
4. **Gated OCR Execution**:
   - PaddleOCR (PP-OCRv4) executed **261 forward passes** across active vehicle tracks.
   - Attempt budgeting suppressed **207 redundant OCR calls** on tracks that had reached the maximum limit of 8 attempts.
   - A total of **35 unique vehicle tracks** yielded at least one valid license plate reading (yielding a $25.36\%$ track-to-plate yield).
   - Bounded DVLA character-confusion normalization collapsed Track 55 and Track 73 into single vehicle identity `KH06***`, producing **34 unique vehicle identities**.

---

## 3. Multi-Camera Network Simulation Harness (`simulate_multi_camera.py`)

### 3.1 Motivation & Methodological Justification
Real-world multi-camera traffic datasets with non-overlapping fields of view and confirmed cross-camera ground-truth re-identification are notoriously scarce and expensive to collect. Rather than re-running the edge neural pipeline multiple times on disjoint video fragments (which cannot guarantee that identical vehicles traverse all camera nodes), IDAHR adopts an event-level trajectory simulation harness:
1. Edge inference is executed once on the base traffic recording to extract verified detection events (`events.json`, $N = 35$).
2. The simulation harness fans out these verified detections across a synthetic 4-junction arterial corridor with realistic inter-camera transit times, road-network travel delays, stochastic driver speed jitter, and optical camera dropouts.
3. Events are merged into a unified timeline and sorted chronologically, exposing the central platform to realistic asynchronous network arrival patterns.

### 3.2 Simulation Parameters & Configuration

| Parameter | Configuration Value | Units | Source Code Reference | Notes |
|---|---|---|---|---|
| **Camera Topology** | 4 Sequential Nodes | — | `simulate_multi_camera.py:56-61` | Linear arterial route spanning 4.78 km total length. |
| **`CAM_01` (Junction A)** | Lat: `12.9716`, Lng: `77.5946` | Deg | `simulate_multi_camera.py:57` | Nominal Ingress node; Offset: $0\text{ s}$; Dropout: $0.0\%$. |
| **`CAM_02` (Ring Road North)**| Lat: `12.9815`, Lng: `77.6094` | Deg | `simulate_multi_camera.py:58` | Hop 1; Offset: $240\text{ s}$ ($4.0\text{ min}$); Dropout: $10.0\%$. |
| **`CAM_03` (Market Circle)** | Lat: `12.9925`, Lng: `77.6205` | Deg | `simulate_multi_camera.py:59` | Hop 2; Offset: $560\text{ s}$ ($9.33\text{ min}$); Dropout: $15.0\%$. |
| **`CAM_04` (Highway Toll)** | Lat: `13.0041`, Lng: `77.6340` | Deg | `simulate_multi_camera.py:60` | Hop 3; Offset: $900\text{ s}$ ($15.0\text{ min}$); Dropout: $20.0\%$. |
| **Travel Time Jitter** | $\pm 8.0$ | seconds | `simulate_multi_camera.py:62` | Continuous uniform noise $U(-8, +8)$ added to each vehicle's transit timestamp. |
| **Event Re-ordering** | Chronological Sort | — | `simulate_multi_camera.py:162` | `all_events.sort(key=lambda e: e['timestamp'])` ensures realistic cross-camera interleaving. |
| **Random PRNG Seed** | **MISSING** (Unseeded) | — | `simulate_multi_camera.py` | The base simulation script does not invoke `random.seed()`, causing small stochastic variations across runs. |

### 3.3 Event Yield per Camera Node

#### Current Saved Files on Disk (`paper_evidence/data/` & root):
- **`CAM_01` (`cam_01_events.json`)**: **35 events** ($100.0\%$ capture rate; 0 drops).
- **`CAM_02` (`cam_02_events.json`)**: **31 events** ($88.57\%$ capture rate; 4 stochastic drops vs. 10% configured).
- **`CAM_03` (`cam_03_events.json`)**: **29 events** ($82.86\%$ capture rate; 6 stochastic drops vs. 15% configured).
- **`CAM_04` (`cam_04_events.json`)**: **26 events** ($74.29\%$ capture rate; 9 stochastic drops vs. 20% configured).
- **Total Combined Timeline (`all_camera_events_timeline.json`)**: **121 events**.

#### Baseline Evaluation Run Recorded in `results.md` (§ 2.1):
- Total Events Ingested: **122 events** (derived from an earlier unseeded run of `simulate_multi_camera.py`).
- Trajectory Sequence Accuracy: **$100.0\%$** ($34 / 34$ vehicles reconstructed with valid monotonic camera ordering).
- Traversal Topology Breakdown:
  - 4-Camera Traversal (`CAM_01 -> CAM_02 -> CAM_03 -> CAM_04`): **19 vehicles** ($55.88\%$).
  - Missed `CAM_04` (`CAM_01 -> CAM_02 -> CAM_03`): **9 vehicles** ($26.47\%$).
  - Missed `CAM_03` (`CAM_01 -> CAM_02 -> CAM_04`): **5 vehicles** ($14.71\%$).
  - Missed `CAM_02 & CAM_04` (`CAM_01 -> CAM_03`): **1 vehicle** ($2.94\%$).
