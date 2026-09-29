# 01 — System Architecture & Implementation Audit

**Document Status**: COMPLETED  
**Verification Date**: 2026-09-29  
**Target Submission**: IEEE Conference (e.g., IEEE Transactions on Intelligent Transportation Systems / IEEE VTC / IEEE ITSC)  
**System Evaluated**: Intelligent Distributed ANPR & Highway Routing (IDAHR)  

---

## 1. What the System Actually Does Today (vs. Planned Scope)

The IDAHR codebase implements a hybrid edge-central architecture for vehicle tracking across non-overlapping camera networks. In contrast to the initial conceptual blueprint in [README.md](file:///c:/Users/anshu/Documents/newstart/Traffic/README.md) and earlier roadmap notes, the empirical state of the software is documented below:

### 1.1 Implemented & Working Components (ACTIVE)
- **Edge Analytics Pipeline** ([ml/detect.ipynb](file:///c:/Users/anshu/Documents/newstart/Traffic/ml/detect.ipynb)):
  - Uniform 5.0 FPS video sampling on 4K footage (stride = 6 on 30 FPS video).
  - Object detection for vehicle classes (cars, buses, trucks, motorcycles) via COCO-pretrained YOLOv8n.
  - Multi-target tracking via a custom Python implementation of the SORT Kalman filter with Hungarian bipartite matching.
  - Full-frame license plate detection via fine-tuned YOLOv8n (`idahr_plate_detector.pt`).
  - Spatial containment geometry matching plate bounding box centroids to vehicle tracking bounding boxes.
  - OCR quality gate: Plate area filter ($\ge 900\text{ px}$), per-track attempt cap ($\le 8$ attempts), and confidence early-stop ($\ge 0.90$).
  - Character recognition using PaddleOCR (PP-OCRv4) on dual crops (raw and preprocessed via CLAHE + adaptive thresholding).
  - Bounded UK/Indian plate normalizer with positional character-confusion substitution and authoritative 451-entry DVLA local memory tag validation.
  - Dominant vehicle color classification via lightweight vectorized HSV histogram bucketing ($< 0.15\text{ ms}$).
  - JSON telemetry event generation.
- **Central Event Ingestion & Trajectory Engine** ([backend/app/routes/events.py](file:///c:/Users/anshu/Documents/newstart/Traffic/backend/app/routes/events.py)):
  - REST endpoint `POST /events` accepting structured JSON sightings.
  - Audit logging of raw detections into PostgreSQL `events` table.
  - Automatic `vehicles` rollup table upsert tracking `first_seen` and `last_seen` timestamps.
  - Exact string watch-list matching against `blacklist` table with automated `alerts` generation.
  - Dynamic trajectory graph construction in PostgreSQL `edges` table: matches consecutive events for the same plate at differing camera nodes, computing inter-camera Haversine distance, travel time, and incremental running averages of travel time and transit velocity.
  - Secondary-signal plate disambiguation engine: resolves ambiguous plates using vehicle type and color secondary attributes when Levenshtein distance $\le 2$ or prefix/suffix substring matches occur within a temporal corridor ($\Delta t \le 120\text{s}$ intra-camera or $\le 1800\text{s}$ cross-camera).
- **Central Analytics & Query API** ([backend/app/routes/](file:///c:/Users/anshu/Documents/newstart/Traffic/backend/app/routes)):
  - `GET /cameras`: Camera network topology and geographic coordinates.
  - `GET /vehicle/{plate}`: Vehicle summary (first/last seen, distinct camera count, active alert flags).
  - `GET /trajectory/{plate}`: Chronological multi-camera trajectory path points.
  - `GET /traffic/density`: Real-time camera event density aggregated over sliding windows (default 15 minutes).
  - `GET /traffic/congestion`: Congestion alarm flagging cameras where recent window count exceeds $1.5\times$ rolling 60-minute average.
  - `GET /alerts`, `PATCH /alerts/{alert_id}/resolve`: Alert incident management.
  - `POST /blacklist`: Watch-list plate management.
  - `GET /disambiguations`: Audit trail of attribute-assisted plate merges and rejections.
- **Frontend Operational Dashboard** ([frontend/src/](file:///c:/Users/anshu/Documents/newstart/Traffic/frontend/src)):
  - Single-page dashboard built with React 19, Vite 6, Tailwind CSS v4, and Leaflet / React-Leaflet.
  - Interactive map displaying camera node positions, status badges (normal vs. congested), and vehicle trajectory playback lines.
  - Real-time alert list with interactive resolution triggers.
  - Quick blacklist registration widget.
  - Vehicle plate search with path visualization.
  - Rolling traffic statistics bar.

### 1.2 Unfinished, Unused, or Planned Modules (OMITTED / FUTURE WORK)
The following components mentioned in SIH design notes or early sketches are **not implemented** in the active codebase:
1. **Isolation Forest Route Anomaly Scoring**: Not implemented. No ML-based anomaly model exists in the backend; anomalous routes are not automatically flagged beyond standard blacklist hits and plate ambiguity alerts.
2. **Predictive Congestion Forecasting (XGBoost / Random Forest)**: Not implemented. The congestion endpoint uses a deterministic SQL rolling-average ratio rule, not a predictive machine-learning model.
3. **LLM Reasoning Explanations**: Not implemented. No LLM APIs (OpenAI, Gemini, Anthropic) or local inference pipelines are called in the ingestion or alert path.
4. **WebSocket Live Push**: Not implemented. Frontend polling via HTTP REST (`client.js`) is used instead of bi-directional WebSockets.
5. **Real Road-Path Routing (OSRM)**: Not implemented. Trajectories are drawn on Leaflet as straight geodetic polylines between camera coordinates, not mapped to actual street centerlines.
6. **Multi-Camera Physical Ingestion**: The system processes 1 physical camera video (`source.mp4`). Multi-camera multi-hop feeds are synthesized via `simulate_multi_camera.py` replaying detected plate sequences across 4 synthetic camera nodes with temporal offsets, jitter, and stochastic dropout.

---

## 2. End-to-End System Architecture

```
+---------------------------------------------------------------------------------------------------+
|                                      EDGE CAMERA NODE (x N)                                       |
|                                                                                                   |
|  +----------------+      +-------------------+      +------------------+      +----------------+  |
|  | Video Ingestion| ---> | Vehicle Detection | ---> | Vehicle Tracking | ---> |   Color/Type   |  |
|  | (5 FPS Sample) |      |   (YOLOv8n-COCO)  |      |   (Custom SORT)  |      | (HSV Hist/Cls) |  |
|  +----------------+      +-------------------+      +------------------+      +----------------+  |
|                                                              |                         |          |
|                                                              v                         |          |
|  +----------------+      +-------------------+      +------------------+               |          |
|  | Event Egress   | <--- | Char-Confusion    | <--- | Dual-Crop OCR    | <-------------+          |
|  | (JSON payload) |      | Normalizer (DVLA) |      | (PaddleOCR v4)   |                          |
|  +----------------+      +-------------------+      +------------------+                          |
+---------------------------------------------------------------------------------------------------+
                                                   |
                                     WAN Network Backhaul
                              (JSON Event: ~224 - 375 bytes)
                                                   |
                                                   v
+---------------------------------------------------------------------------------------------------+
|                                     CENTRAL BACKEND (FastAPI)                                     |
|                                                                                                   |
|   POST /events                                                                                    |
|         |                                                                                         |
|         v                                                                                         |
|   +------------------------------------+          +------------------------------------+          |
|   | Secondary-Signal Disambiguation    | -------> | Blacklist Verification Engine      |          |
|   | (Levenshtein <= 2, color/type chk) |          | (Exact string match -> alerts)     |          |
|   +------------------------------------+          +------------------------------------+          |
|         |                                                                                         |
|         v                                                                                         |
|   +------------------------------------+          +------------------------------------+          |
|   | Sighting & Vehicle Rollup Engine   |          | Dynamic Edge Graph Builder         |          |
|   | (events insert, vehicles upsert)   |          | (prior cam lookup -> avg speed/tt) |          |
|   +------------------------------------+          +------------------------------------+          |
|         |                                                           |                             |
|         +-----------------------------+-----------------------------+                             |
|                                       |                                                           |
|                                       v                                                           |
|                         PostgreSQL Relational Storage                                             |
|              (events, vehicles, edges, cameras, blacklist, alerts, plate_disambiguations)         |
+---------------------------------------------------------------------------------------------------+
                                        |
                            REST API Query Endpoints
                                        |
                                        v
+---------------------------------------------------------------------------------------------------+
|                                  OPERATIONAL DASHBOARD (React 19)                                 |
|                                                                                                   |
|   [ Leaflet Interactive Map ]      [ Real-Time Alert Panel ]     [ Cross-Camera Path Playback ]  |
|   [ Rolling Traffic Density ]      [ Congestion Indicator  ]     [ Watch-List Target Manager  ]  |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Request & Data Flow Walkthrough

When a vehicle enters a camera field of view, the exact sequential data processing path is as follows:

1. **Edge Sampling & Tracking**:
   - The video stream is sampled at $5.0\text{ FPS}$ (every 6th frame of 30 FPS footage).
   - YOLOv8n predicts bounding boxes for vehicle classes (car, truck, bus, motorcycle) with confidence threshold $\ge 0.40$.
   - SORT tracker updates Kalman state vectors and assigns a persistent integer `track_id` via Hungarian matching ($IoU \ge 0.20$, $max\_age = 12$, $min\_hits = 2$).
   - A vehicle body crop is extracted; dominant color is classified in $< 0.15\text{ ms}$ into one of 8 bins (black, white, silver/gray, red, yellow, green, blue, other).

2. **Plate Localization & Gated OCR**:
   - YOLOv8 plate detector runs once on the full sampled frame (`PLATE_DET_CONF = 0.25`).
   - Detected plate bounding boxes are matched to active vehicle tracks by testing whether the plate centroid falls within the vehicle box.
   - Quality gate checks:
     - If candidate plate crop area $< 900\text{ px}^2$, OCR is skipped.
     - If the vehicle track has already reached the attempt cap (`MAX_OCR_ATTEMPTS = 8`), OCR is skipped.
     - If the track's existing confidence $\ge 0.90$, OCR is bypassed.
   - Dual OCR execution: PaddleOCR (PP-OCRv4) runs on the raw plate crop and a preprocessed crop (CLAHE contrast enhancement + selective Fast Non-Local Means denoising + adaptive Gaussian thresholding). The higher-confidence string is retained.
   - The string is processed through `normalize_plate()` applying character-confusion rules and validating against 451 DVLA memory tags.

3. **Event Egress & Ingestion**:
   - When a track terminates or is emitted, the edge node formats a structured JSON payload:
     ```json
     {
       "camera_id": "CAM_01",
       "plate": "BG65***",
       "track_id": 11,
       "confidence": 0.631,
       "timestamp": "2026-08-23T08:00:15.482000Z",
       "lat": 12.9716,
       "lng": 77.5946,
       "vehicle_type": "truck",
       "color": "blue"
     }
     ```
   - Egress payload size: **375.1 bytes mean** (uncompressed raw 4K frame is $24,883,200$ bytes; saving is $> 99.999\%$).
   - The payload is transmitted over standard HTTP POST to the central API endpoint `POST /events`.

4. **Central Relational Processing & Graph Upsert**:
   - **Step A: Disambiguation Check**: The backend verifies if the plate has a prior resolved alias in `plate_disambiguations`. If not, and the plate is not yet in `vehicles`, it searches recent events within a $\pm 1800\text{s}$ window for potential matches having Levenshtein distance $\le 2$ or substring relationship. If secondary attributes (`vehicle_type`, `color`) match, observations are merged into the canonical plate. If attributes differ, they are marked distinct. If attributes are missing/unknown, an unresolved ambiguity alert is triggered.
   - **Step B: Event & Vehicle Storage**: The sighting is appended to PostgreSQL `events`. The `vehicles` table is updated via `ON CONFLICT (plate) DO UPDATE SET first_seen = LEAST(...), last_seen = GREATEST(...)`.
   - **Step C: Blacklist Verification**: An exact query matches `plate` against `blacklist`. On a hit, a new row is inserted into `alerts` with `type = 'blacklist_hit'`.
   - **Step D: Dynamic Edge Graph Traversal**: The backend queries the most recent prior event for this plate at a *different* camera node with `timestamp <= ts`. If found:
     - Travel time is computed: $\Delta t = t_{\text{current}} - t_{\text{prior}}$.
     - Inter-camera distance $D$ is computed from camera GPS coordinates using the Haversine formula ($R = 6371\text{ km}$).
     - Transit velocity is computed: $V = D / (\Delta t / 3600)\text{ km/h}$.
     - The corresponding edge in `edges` is upserted with running averages:
       $$\bar{T}_{new} = \bar{T}_{old} + \frac{\Delta t - \bar{T}_{old}}{N+1}, \quad \bar{V}_{new} = \bar{V}_{old} + \frac{V - \bar{V}_{old}}{N+1}$$
   - The entire transaction commits within a median latency of **13.18 ms** (measured on local Postgres).

---

## 4. Mapping Codebase Modules to IEEE Paper Sections

| Codebase Module | Implementation File(s) | Primary Paper Section | Key Scientific & Technical Contribution |
|---|---|---|---|
| **Video Sampling & Preprocessing** | `ml/detect.ipynb` (Cells 10, 18, 21) | **III. Edge Pipeline Design** | Stride-based 5 FPS sampling, Laplacian sharpness gate, selective Fast NL-Means denoising. |
| **Vehicle Detection & Tracking** | `ml/detect.ipynb` (Cells 8, 14, 21) | **III. Edge Pipeline Design** | YOLOv8n object detection coupled with custom SORT Kalman-filter state estimation under occlusion. |
| **Plate Detection & Quality Gate** | `ml/detect.ipynb` (Cells 14, 18, 21), `idahr_plate_detector.pt` | **III. Edge Pipeline Design** | Full-frame plate detection, spatial containment matching, area/attempt quality budget gating. |
| **OCR & Character Normalization** | `ml/detect.ipynb` (Cells 16, 18), `ocr_enhancements.py` | **III. Edge Pipeline Design** | Dual-crop PP-OCRv4, Charles Wright confusion matrix, 451-tag DVLA bounded normalization. |
| **Network Backhaul Compression** | `calc_bandwidth.py`, `eval_bandwidth.py` | **IV. System Architecture & WAN Bandwidth** | Quantitative reduction from 4K/1080p video streams down to 375-byte JSON events ($> 99.99\%$ saving). |
| **FastAPI Ingestion & ORM** | `backend/app/main.py`, `backend/app/routes/events.py` | **IV. Central Analytics Platform** | Asynchronous non-blocking event ingestion, transaction atomicity, sub-15ms write latency. |
| **Secondary-Signal Disambiguation**| `backend/app/routes/events.py`, `test_disambiguation.py` | **IV. Central Analytics Platform** | Spatiotemporal corridor matching with color/type secondary signals resolving optical ambiguity. |
| **Dynamic Trajectory Graph Engine**| `backend/app/routes/events.py`, `backend/app/utils.py` | **IV. Central Analytics Platform** | Running-average edge travel time, velocity estimation, and cross-camera path reconstruction. |
| **Traffic Analytics (Density/Congestion)**| `backend/app/routes/traffic.py` | **IV. Central Analytics Platform** | Sliding-window spatial event density and $1.5\times$ rolling-average congestion alarms. |
| **Surveillance Alert Engine** | `backend/app/routes/alerts.py` | **IV. Central Analytics Platform** | Real-time watchlist verification and incident management lifecycle. |
| **Multi-Camera Simulation Harness** | `simulate_multi_camera.py`, `sweep_dropout.py` | **V. Experimental Evaluation** | 4-camera synthetic testbed with geographic offsets, transit time delay, jitter, and dropout. |
| **Empirical GPU/CPU Benchmark** | `results.md`, `calc_runtime.py`, `eval_live_run.py` | **V. Experimental Evaluation** | Tesla T4 GPU wall-clock telemetry (130.30s) vs. CPU-fallback regime (538.58s). |
| **OCR Accuracy & Ablation** | `eval_ocr_accuracy.py`, `ablation_corrector.py` | **V. Experimental Evaluation** | 35-track ground-truth accuracy (65.71% baseline to 82.86% enhanced), corrector ablation. |
