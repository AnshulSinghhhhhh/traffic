# IDAHR — Multi-Camera ANPR Trajectory Tracking

Central platform that stitches independent per-camera license-plate detections
into cross-camera vehicle trajectories, traffic analytics, and blacklist
alerts. Originally scoped for SIH 2026 (PS-26127, Bharat Electronics Ltd);
this build is being rebuilt as a working system to support an IEEE
conference paper submission, so correctness and honest evaluation matter
more here than raw feature count.

## Core architectural claim (do not violate this)

**Raw video never leaves a camera node. Only small structured JSON events do.**
Each camera runs its own detection → tracking → OCR pipeline locally (in this
project, simulated by running `ml/detect.ipynb` on a Kaggle GPU) and emits
only `{plate, camera_id, timestamp, lat, lng, confidence, track_id}` per
vehicle sighting. The central backend never touches video. This is the
whole point of the system scaling by vehicle count, not video bandwidth —
keep it that way in every route and service you write.

## Data flow

```
Camera node (edge)
  YOLOv8 vehicle detection -> custom SORT tracker -> full-frame YOLOv8 plate
  detection -> PaddleOCR + character-confusion correction
  -> emits events.json (small JSON only)
        |
        v
Central FastAPI ingestion (POST /events)
        |
        v
PostgreSQL  --------------------------------->  edges table
  events table (raw sightings)                  (cross-camera trajectory graph,
        |                                        built by matching consecutive
        v                                        same-plate events)
Analytics (density, congestion, OD counts)
Alert engine (blacklist check on every ingest)
        |
        v
REST API -> React + Leaflet dashboard (map, vehicle search + path playback,
            alert panel, stats bar)
```

## Repo layout

```
idahr/
├── README.md                  <- this file
├── db_schema.sql              <- apply this exactly; six tables, described below
├── ml/
│   └── detect.ipynb           <- existing, working ANPR pipeline (YOLOv8 + SORT +
│                                  PaddleOCR). Do not modify. Read it to understand
│                                  the exact shape of events.json (below).
├── kaggle_pipeline/
│   ├── kaggle_runner.py       <- pushes detect.ipynb to Kaggle's free T4 GPU,
│   │                              polls until done, pulls events.json back
│   └── kernel-metadata.json   <- Kaggle kernel config (edit dataset_sources
│                                  before running)
├── simulate_multi_camera.py   <- fans one base events.json out into several
│                                  synthetic camera streams for testing/demoing
│                                  cross-camera trajectory stitching (see below)
├── backend/                   <- FastAPI app (build this)
└── frontend/                  <- React + Vite + Tailwind + Leaflet (build this)
```

## ML pipeline contract (from `ml/detect.ipynb`)

The notebook is already built and working — it's the CV/OCR layer, not
something to rebuild. It runs on Kaggle's free T4 GPU (no local GPU
available), detecting vehicles (YOLOv8n, COCO-pretrained), tracking them
with a from-scratch SORT implementation, detecting plates once per frame
with a fine-tuned YOLOv8 model, then reading them with PaddleOCR plus a
per-length character-confusion correction template. It supports both Indian
and UK plate formats via a config switch.

It exports one JSON object per tracked vehicle with **at least one**
successful plate read, shaped like this — the backend's ingestion schema
must accept exactly these fields (extra fields in the notebook's own output,
like `ocr_attempts` and `regex_valid_indian_format`, can be accepted and
stored but are not required for the MVP):

```json
{
  "event_id": 1,
  "camera_id": "CAM_01",
  "plate": "BGG5USJ",
  "timestamp": "2026-09-25T14:03:11.482000",
  "confidence": 0.631,
  "track_id": 11,
  "ocr_attempts": 8,
  "regex_valid_indian_format": true,
  "lat": 12.9716,
  "lng": 77.5946
}
```

## Database schema

Apply `db_schema.sql` exactly (run it on backend startup if tables don't
exist). Six tables: `cameras`, `events`, `edges` (the trajectory graph —
one row per `from_cam`/`to_cam` pair, aggregated as consecutive same-plate
events are matched), `vehicles` (rollup for fast lookup), `blacklist`,
`alerts`. The schema file already seeds four camera rows matching
`simulate_multi_camera.py`'s `CAMERAS` list — keep those in sync if you
change one.

## API contract

| Method | Endpoint | Purpose | Notes |
|---|---|---|---|
| POST | `/events` | Ingest one detection event | Insert into `events`; upsert `vehicles` (first/last seen); check `blacklist`, insert an `alerts` row (`type='blacklist_hit'`) on a match; if the plate has a prior event at a *different* camera, upsert the `edges` row (increment count, update running avg travel time/speed, update `last_seen`) |
| GET | `/cameras` | List camera nodes | For the map |
| GET | `/vehicle/{plate}` | Summary for one plate | first/last seen, camera count, alert flags |
| GET | `/trajectory/{plate}` | Chronological cross-camera path | ordered `{camera_id, timestamp, lat, lng}` |
| GET | `/traffic/density` | Recent event count per camera | query param: window in minutes, default 15 |
| GET | `/traffic/congestion` | Per-camera congestion flag | flag `congested` if recent count > 1.5x rolling average |
| GET | `/alerts` | Alert list | query param `status=unresolved\|resolved\|all`, default `unresolved` |
| PATCH | `/alerts/{alert_id}/resolve` | Mark an alert resolved | |
| POST | `/blacklist` | Add/update a watchlisted plate | body: `{plate, reason}` |

## Multi-camera test harness (`simulate_multi_camera.py`)

There's no real multi-camera dataset — one source video stands in for the
whole camera network. Rather than re-running the CV pipeline once per
camera (wasteful of Kaggle GPU quota, and can't guarantee the same plates
appear at every camera), this script runs detection **once**, then replays
the same detected plates through 4 synthetic cameras: each gets its own
lat/lng, a time offset (simulated travel time between checkpoints), jitter,
and a small per-camera dropout rate (a real camera doesn't catch every
passing plate). Events from all cameras are merged and time-sorted before
sending, so the backend sees them in realistic arrival order. This is the
system's actual end-to-end test: prove that small structured events from
independently-processing "cameras" correctly reassemble into a trajectory
in the central system — which is the paper's core claim.

Run it against the live backend once ingestion is up:
```
python simulate_multi_camera.py --input events.json --mode api --api-url http://localhost:8000/events --delay 1.5
```

## MVP scope — build this, skip the rest

**Build (GO):** vehicle+plate detection (already done, in `detect.ipynb`),
ingestion endpoint, all API routes above, trajectory graph via `edges`,
density/congestion/OD analytics, blacklist alert engine, React+Leaflet
dashboard (map, vehicle search with path playback, alert panel, stats bar).

**Skip for MVP, note as future work in the paper (WATCH):** route anomaly
scoring (Isolation Forest), congestion prediction (XGBoost/Random Forest),
LLM-based reasoning explanations, WebSocket live push, traffic heatmap
layer, real road-path routing (OSRM).

**Do not attempt:** training a detector/OCR model from scratch, real live
CCTV integration, more than 4 camera nodes, claiming >90% accuracy without
having actually measured it.

## Running locally

1. Postgres running locally (or a connected Neon/Supabase instance),
   `DATABASE_URL` set as an env var.
2. `psql $DATABASE_URL -f db_schema.sql` (or have the backend apply it on
   startup — either is fine, just do it once, not on every request).
3. `uvicorn app.main:app --reload` in `backend/`.
4. `npm run dev` in `frontend/`.
5. Run `ml/detect.ipynb` on Kaggle (via `kaggle_pipeline/kaggle_runner.py`)
   to produce a base `events.json`, then run `simulate_multi_camera.py`
   against the live backend to populate the dashboard end to end.
