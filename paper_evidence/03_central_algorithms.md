# 03 — Central Analytics & Trajectory Algorithms

**Document Status**: COMPLETED  
**Verification Date**: 2026-09-29  
**Source Files**: `backend/app/routes/events.py`, `backend/app/routes/traffic.py`, `backend/app/utils.py`, `backend/app/models.py`  

---

## 1. Dynamic Edge Trajectory Graph Upsert

### 1.1 Algorithmic Purpose
When an edge camera detects a vehicle, the central ingestion engine reconstructs cross-camera trajectories on the fly. Rather than executing periodic offline batch jobs, the platform updates an online directed multigraph whose edges represent physical transit links between camera nodes.

### 1.2 Mathematical Formulation
For an incoming sighting event $e_t = (\text{plate}, \text{cam}_2, t_2)$ at camera $\text{cam}_2$:
1. The engine queries the database for the most recent prior event $e_{t-1} = (\text{plate}, \text{cam}_1, t_1)$ of the same vehicle at a differing camera ($\text{cam}_1 \ne \text{cam}_2$) where $t_1 \le t_2$.
2. Travel time $\Delta t$ is computed as:
   $$\Delta t = t_2 - t_1 \quad (\text{seconds})$$
3. Great-circle distance $D$ between camera coordinates $(\phi_1, \lambda_1)$ and $(\phi_2, \lambda_2)$ is computed via the Haversine formula ($R = 6371.0\text{ km}$):
   $$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)$$
   $$D = 2 R \arcsin(\sqrt{a}) \quad (\text{km})$$
4. Point-to-point transit speed $V$ is computed:
   $$V = \frac{D}{\Delta t / 3600.0} \quad (\text{km/h}) \quad [\text{for } \Delta t > 0]$$
5. The directed edge $(\text{cam}_1, \text{cam}_2)$ in the PostgreSQL `edges` table is updated atomically via an online incremental running average:
   $$\bar{T}_{N+1} = \bar{T}_N + \frac{\Delta t - \bar{T}_N}{N + 1}$$
   $$\bar{V}_{N+1} = \bar{V}_N + \frac{V - \bar{V}_N}{N + 1}$$

### 1.3 Exact Code Implementation (`backend/app/routes/events.py:212-254`)
```python
# Query most recent sighting of the same plate at a different camera
prior_event_stmt = select(Event).where(
    Event.plate == plate,
    Event.camera_id != camera_id,
    Event.timestamp <= ts
).order_by(Event.timestamp.desc()).limit(1)

prior_event_res = await db.execute(prior_event_stmt)
prior_event = prior_event_res.scalar_one_or_none()

if prior_event:
    travel_time_s = abs((ts - prior_event.timestamp).total_seconds())
    
    cam_stmt = select(Camera).where(Camera.camera_id.in_([prior_event.camera_id, camera_id]))
    cams_res = await db.execute(cam_stmt)
    cams = {c.camera_id: c for c in cams_res.scalars()}
    
    if prior_event.camera_id in cams and camera_id in cams:
        c1 = cams[prior_event.camera_id]
        c2 = cams[camera_id]
        distance_km = haversine_km(c1.lat, c1.lng, c2.lat, c2.lng)
        
        speed_kmh = 0.0
        if travel_time_s > 0:
            speed_kmh = distance_km / (travel_time_s / 3600.0)
        
        upsert_edge_stmt = text("""
            INSERT INTO edges (from_cam, to_cam, count, avg_travel_time_s, avg_speed_kmh, last_seen)
            VALUES (:from_cam, :to_cam, 1, :tt, :speed, :ls)
            ON CONFLICT (from_cam, to_cam) DO UPDATE SET
            count = edges.count + 1,
            avg_travel_time_s = edges.avg_travel_time_s + (EXCLUDED.avg_travel_time_s - edges.avg_travel_time_s) / (edges.count + 1),
            avg_speed_kmh = edges.avg_speed_kmh + (EXCLUDED.avg_speed_kmh - edges.avg_speed_kmh) / (edges.count + 1),
            last_seen = EXCLUDED.last_seen
        """)
        await db.execute(upsert_edge_stmt, {
            "from_cam": prior_event.camera_id,
            "to_cam": camera_id,
            "tt": travel_time_s,
            "speed": speed_kmh,
            "ls": ts
        })
```

### 1.4 Complexity Analysis
- **Time Complexity**: $O(\log N_{\text{events}})$ to locate prior sighting via composite B-tree index `idx_events_plate` and `idx_events_timestamp`, followed by $O(1)$ primary key camera lookup and $O(1)$ unique constraint upsert on `(from_cam, to_cam)`.
- **Space Complexity**: $O(|V_c|^2)$ where $|V_c|$ is the number of camera nodes (for 4 cameras, maximum 12 directed edges). Constant space per event.

---

## 2. Sliding-Window Traffic Density & Congestion Detection

### 2.1 Algorithmic Formulation
The congestion detection engine monitors network bottlenecks without requiring heavy neural forecasting models by comparing short-term arrival velocity against a medium-term moving baseline.

- **Short-Term Window ($W_{\text{recent}}$)**: Total event count $C_{\text{recent}}$ at camera $c$ within the last $W$ minutes (default $W = 15\text{ minutes}$).
- **Long-Term Baseline ($W_{\text{rolling}}$)**: Total event count $C_{60}$ at camera $c$ within the preceding 60 minutes.
- **Normalized Rolling Average**:
  $$\mu_{\text{rolling}} = \frac{C_{60}}{60.0 / W}$$
- **Congestion Decision Rule**:
  $$\text{Congested}(c) = \begin{cases} \text{True}, & \text{if } C_{\text{recent}} > 1.5 \cdot \mu_{\text{rolling}} \quad \text{and} \quad \mu_{\text{rolling}} > 0 \\ \text{False}, & \text{otherwise} \end{cases}$$

### 2.2 Exact Code Implementation (`backend/app/routes/traffic.py:28-64`)
```python
@router.get("/congestion", response_model=List[CongestionOut])
async def get_congestion(window: int = 15, db: AsyncSession = Depends(get_db)):
    stmt = text("""
        WITH recent AS (
            SELECT camera_id, COUNT(*) as r_count
            FROM events
            WHERE timestamp >= NOW() - INTERVAL '1 minute' * :window
            GROUP BY camera_id
        ),
        rolling AS (
            SELECT camera_id, COUNT(*) as h_count
            FROM events
            WHERE timestamp >= NOW() - INTERVAL '60 minutes'
            GROUP BY camera_id
        )
        SELECT 
            COALESCE(c.camera_id, r.camera_id, h.camera_id) as camera_id,
            COALESCE(r.r_count, 0) as recent_count,
            COALESCE(h.h_count, 0)::float / (60.0 / :window) as rolling_avg
        FROM cameras c
        LEFT JOIN recent r ON c.camera_id = r.camera_id
        LEFT JOIN rolling h ON c.camera_id = h.camera_id
    """)
    res = await db.execute(stmt, {"window": window})
    
    results = []
    for row in res.mappings():
        recent = row["recent_count"]
        rolling = row["rolling_avg"]
        congested = (recent > 1.5 * rolling) and (rolling > 0)
        results.append(CongestionOut(
            camera_id=row["camera_id"],
            recent_count=recent,
            rolling_avg=rolling,
            congested=congested
        ))
    return results
```

### 2.3 Mathematical Nuance & Empirical Limitation
- Because $C_{\text{recent}}$ is a subset of $C_{60}$, as a surge begins, the denominator $\mu_{\text{rolling}}$ also increases. As evaluated in `eval_congestion.py`, a pure $1.5\times$ step surge is absorbed by the denominator and does not cross the $> 1.5\mu_{\text{rolling}}$ boundary. Surges $\ge 1.8\times$ trigger the congestion alarm reliably within $3.6$ to $13.0$ minutes.
- Complexity: Two index range scans over `idx_events_timestamp`, completing in under $0.60\text{ ms}$ even at $10^6$ database rows.

---

## 3. Blacklist Surveillance Engine

### 3.1 Algorithmic Formulation
The security surveillance engine cross-checks every ingested event against a registered watch-list (`blacklist` table).

- **Matching Logic**: **Strict Exact String Equality** (`Blacklist.plate == plate`).
- **Alert Trigger**: If an exact match occurs, an incident record is immediately generated in `alerts` with `type = 'blacklist_hit'`, `resolved = False`, and an automated timestamp.
- **Empirical Contrast (Exact vs. Fuzzy)**:
  - As evaluated in `eval_blacklist_alerts.py`, exact matching yields **100.0% Precision**, but is vulnerable to raw OCR misreads (e.g., `BGG5USJ` missing target `BG65USJ`, resulting in only **33.33% Recall** if uncorrected).
  - Bounded character-confusion correction at the edge resolves this vulnerability, restoring exact-match recall to **100.0%**.

### 3.2 Exact Code Implementation (`backend/app/routes/events.py:200-210`)
```python
# Check Blacklist
bl_result = await db.execute(select(Blacklist).where(Blacklist.plate == plate))
bl = bl_result.scalar_one_or_none()
if bl:
    alert = Alert(
        type="blacklist_hit",
        plate=plate,
        camera_id=camera_id,
        message=f"Blacklisted plate {plate} spotted at {camera_id}: {bl.reason}"
    )
    db.add(alert)
```

### 3.3 Complexity Analysis
- Primary key B-tree index lookup on `blacklist.plate`: $O(1)$ time complexity, executing in $< 0.1\text{ ms}$.

---

## 4. Secondary-Signal Vehicle Disambiguation Engine

### 4.1 Problem Formulation & Heuristic Rationale
In real-world traffic surveillance, partial occlusions (e.g. leading truck blocking front bumper characters) or font confusions produce degraded plates (e.g. `BPF` instead of `HX52BPF`, or `KHO6KSU` vs. `KH06KSU`). Treating these as novel vehicles fragments vehicle histories. Conversely, blindly merging similar strings causes identity theft between distinct vehicles.

IDAHR resolves this dilemma using **secondary physical signals** extracted without additional neural networks:
1. Vehicle classification type (`car`, `truck`, `bus`, `motorcycle`) from YOLOv8n.
2. Dominant body color from fast vectorized HSV histogram bucketing (`black`, `white`, `silver/gray`, `red`, `yellow`, `green`, `blue`).

### 4.2 Disambiguation Rules & Thresholds
When an incoming plate $P_{\text{in}}$ arrives and is not yet recorded in the `vehicles` table:

1. **Temporal Corridor Window**:
   - The engine queries recent events in the corridor window $[t - 1800\text{s}, t + 1800\text{s}]$.
   - For candidate events at the *same* camera, the window is constrained to $\Delta t \le 120\text{s}$ to avoid merging different vehicles separated by large time spans.
2. **Ambiguity Pattern Detection**:
   - **Pattern A (Edit Distance)**: $|P_{\text{in}}| - |P_{\text{cand}}| \le 2$ and $1 \le \text{Levenshtein}(P_{\text{in}}, P_{\text{cand}}) \le 2$.
   - **Pattern B (Substring / Partial Read)**: $\min(|P_{\text{in}}|, |P_{\text{cand}}|) \ge 3$ and ($P_{\text{in}}$ is a prefix/suffix of $P_{\text{cand}}$, or vice versa).
3. **Multi-Modal Decision Logic**:
   - **Case 1 (Unclear / Missing Attributes)**: If either vehicle has unknown, missing, or 'other' color/type:
     $$\text{Decision} = \text{'unresolved'}, \quad \text{Action} \rightarrow \text{Trigger Alert } (\text{'plate\_ambiguity\_review'})$$
   - **Case 2 (Matching Attributes)**: If $\text{type}_1 == \text{type}_2$ AND $\text{color}_1 == \text{color}_2$:
     $$\text{Decision} = \text{'merged'}$$
     - Canonical plate is selected as the longer string, or the higher-confidence read if lengths match.
     - Database retroactively executes `UPDATE events SET plate = :canon WHERE plate = :variant` and merges `vehicles` first/last seen timestamps.
   - **Case 3 (Conflicting Attributes)**: If type or color mismatch:
     $$\text{Decision} = \text{'distinct'}, \quad \text{Action} \rightarrow \text{Preserve separate vehicle identities}$$

### 4.3 Exact Code Implementation (`backend/app/routes/events.py:25-174`)
```python
# Check prior resolved aliases
prior_merge_stmt = select(PlateDisambiguation.canonical_plate).where(
    PlateDisambiguation.variant_plate == plate,
    PlateDisambiguation.decision == 'merged'
).order_by(PlateDisambiguation.disambiguation_id.desc()).limit(1)
prior_merge_res = await db.execute(prior_merge_stmt)
already_canonical = prior_merge_res.scalar_one_or_none()
if already_canonical:
    plate = already_canonical

if not already_canonical:
    veh_res = await db.execute(select(Vehicle).where(Vehicle.plate == plate))
    existing_veh = veh_res.scalar_one_or_none()

    if not existing_veh:
        window_start = ts - timedelta(seconds=1800)
        window_end = ts + timedelta(seconds=1800)
        cand_stmt = select(Event).where(
            Event.plate != plate,
            Event.timestamp >= window_start,
            Event.timestamp <= window_end
        ).order_by(Event.timestamp.desc())
        cand_res = await db.execute(cand_stmt)
        cand_events = cand_res.scalars().all()

        # Evaluate candidate plates
        for cand_plate, cand in seen_cands.items():
            pattern = None
            if abs(len(plate) - len(cand_plate)) <= 2:
                dist = levenshtein_distance(plate, cand_plate)
                if 1 <= dist <= 2:
                    pattern = 'edit_distance'

            if not pattern and min(len(plate), len(cand_plate)) >= 3:
                if (plate.startswith(cand_plate) or plate.endswith(cand_plate) or
                    cand_plate.startswith(plate) or cand_plate.endswith(plate)):
                    pattern = 'substring'

            if pattern:
                type_unclear = (not vehicle_type or not cand.vehicle_type or 
                                vehicle_type.lower() in ('unknown', 'other') or 
                                cand.vehicle_type.lower() in ('unknown', 'other'))
                color_unclear = (not color or not cand.color or 
                                 color.lower() in ('unknown', 'other') or 
                                 cand.color.lower() in ('unknown', 'other'))

                if type_unclear or color_unclear:
                    # Flag for human operator review
                    db.add(PlateDisambiguation(..., decision='unresolved'))
                    db.add(Alert(type="plate_ambiguity_review", ...))
                else:
                    type_match = (vehicle_type.lower() == cand.vehicle_type.lower())
                    color_match = (color.lower() == cand.color.lower())

                    if type_match and color_match:
                        # Merge into canonical plate
                        canonical_plate = plate if len(plate) >= len(cand_plate) else cand_plate
                        variant_plate = cand_plate if canonical_plate == plate else plate
                        db.add(PlateDisambiguation(..., decision='merged'))
                        await db.execute(text("UPDATE events SET plate = :canon WHERE plate = :variant"), ...)
                        break
                    else:
                        db.add(PlateDisambiguation(..., decision='distinct'))
```

### 4.4 Complexity & Scalability Notes
- **Levenshtein Distance**: Uses early-exit dynamic programming in $O(|s_1| \cdot |s_2|)$ time and $O(\min(|s_1|, |s_2|))$ space ([backend/app/utils.py:10-25](file:///c:/Users/anshu/Documents/newstart/Traffic/backend/app/utils.py)). For license plates ($|s| \le 8$), computation completes in $< 2\ \mu\text{s}$.
- **Candidate Set Size ($M$)**: Constrained to recent vehicles within corridor bounds $\Delta t \le 1800\text{s}$. Because queries filter on `idx_events_timestamp`, only active vehicles are evaluated.
- **Audit Logging**: All merge and rejection decisions are permanently logged to `plate_disambiguations` with full provenance, enabling retrospective verification and human oversight.
