-- IDAHR central DB schema — plain lat/lng (no PostGIS) for MVP simplicity.
-- Six tables, one dependency chain: cameras <- events -> edges, blacklist -> alerts.

CREATE TABLE cameras (
    camera_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    road_name   TEXT
);

CREATE TABLE events (
    event_id    SERIAL PRIMARY KEY,
    camera_id   TEXT NOT NULL REFERENCES cameras(camera_id),
    plate       TEXT NOT NULL,
    track_id    INTEGER,
    confidence  DOUBLE PRECISION,
    timestamp   TIMESTAMPTZ NOT NULL,
    lat         DOUBLE PRECISION,
    lng         DOUBLE PRECISION,
    vehicle_type TEXT,
    color       TEXT
);
CREATE INDEX idx_events_plate ON events(plate);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_camera_id ON events(camera_id);

-- One row per (from_cam, to_cam) pair, aggregated as consecutive same-plate
-- events are matched — this is the trajectory graph the paper's cross-camera
-- stitching claim rests on.
CREATE TABLE edges (
    edge_id           SERIAL PRIMARY KEY,
    from_cam          TEXT NOT NULL REFERENCES cameras(camera_id),
    to_cam             TEXT NOT NULL REFERENCES cameras(camera_id),
    count              INTEGER NOT NULL DEFAULT 0,
    avg_travel_time_s  DOUBLE PRECISION,
    avg_speed_kmh      DOUBLE PRECISION,
    last_seen          TIMESTAMPTZ,
    UNIQUE (from_cam, to_cam)
);

-- Optional rollup for fast plate lookup without scanning events each time.
CREATE TABLE vehicles (
    plate       TEXT PRIMARY KEY,
    first_seen  TIMESTAMPTZ,
    last_seen   TIMESTAMPTZ
);

CREATE TABLE blacklist (
    plate       TEXT PRIMARY KEY,
    reason      TEXT,
    added_by    TEXT,
    added_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE alerts (
    alert_id    SERIAL PRIMARY KEY,
    type        TEXT NOT NULL,           -- e.g. 'blacklist_hit', 'anomalous_route', 'plate_ambiguity_review'
    plate       TEXT NOT NULL,
    camera_id   TEXT REFERENCES cameras(camera_id),
    message     TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    resolved    BOOLEAN DEFAULT false
);
CREATE INDEX idx_alerts_resolved ON alerts(resolved);

-- Audit table for plate-ambiguity disambiguation checks via color and vehicle type
CREATE TABLE plate_disambiguations (
    disambiguation_id SERIAL PRIMARY KEY,
    variant_plate     TEXT NOT NULL,
    canonical_plate   TEXT NOT NULL,
    camera_id         TEXT REFERENCES cameras(camera_id),
    timestamp         TIMESTAMPTZ NOT NULL,
    ambiguity_pattern TEXT NOT NULL,  -- 'edit_distance' | 'substring'
    color_match       BOOLEAN,
    type_match        BOOLEAN,
    decision          TEXT NOT NULL,  -- 'merged' | 'distinct' | 'unresolved'
    details           TEXT,
    created_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_disambiguations_canonical ON plate_disambiguations(canonical_plate);
CREATE INDEX idx_disambiguations_variant ON plate_disambiguations(variant_plate);

-- Seed camera nodes to match simulate_multi_camera.py's CAMERAS list —
-- edit lat/lng/road_name to your actual demo route before running this.
INSERT INTO cameras (camera_id, name, lat, lng, road_name) VALUES
    ('CAM_01', 'Junction A',      12.9716, 77.5946, 'MG Road'),
    ('CAM_02', 'Ring Road North', 12.9815, 77.6094, 'Outer Ring Road'),
    ('CAM_03', 'Market Circle',   12.9925, 77.6205, 'Commercial St'),
    ('CAM_04', 'Highway Toll',    13.0041, 77.6340, 'NH-44');
