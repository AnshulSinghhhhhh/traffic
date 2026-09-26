from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from ..database import get_db
from ..schemas import EventIn, EventOut
from ..models import Event, Vehicle, Alert, Blacklist, Camera, PlateDisambiguation
from ..utils import haversine_km, levenshtein_distance
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(event_in: EventIn, db: AsyncSession = Depends(get_db)):
    # Normalize timestamp to UTC-aware
    ts = event_in.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    plate = event_in.plate
    camera_id = event_in.camera_id
    vehicle_type = event_in.vehicle_type
    color = event_in.color
    confidence = event_in.confidence or 0.0

    # 1. Check if this plate was already resolved to a canonical plate in prior disambiguations
    prior_merge_stmt = select(PlateDisambiguation.canonical_plate).where(
        PlateDisambiguation.variant_plate == plate,
        PlateDisambiguation.decision == 'merged'
    ).order_by(PlateDisambiguation.disambiguation_id.desc()).limit(1)
    prior_merge_res = await db.execute(prior_merge_stmt)
    already_canonical = prior_merge_res.scalar_one_or_none()
    if already_canonical:
        plate = already_canonical

    # 2. Ambiguity cross-check before treating a new event's plate as a brand-new vehicle
    if not already_canonical:
        veh_res = await db.execute(select(Vehicle).where(Vehicle.plate == plate))
        existing_veh = veh_res.scalar_one_or_none()

        if not existing_veh:
            # Query recently seen candidate events within corridor time bounds (e.g. 1800s)
            window_start = ts - timedelta(seconds=1800)
            window_end = ts + timedelta(seconds=1800)
            cand_stmt = select(Event).where(
                Event.plate != plate,
                Event.timestamp >= window_start,
                Event.timestamp <= window_end
            ).order_by(Event.timestamp.desc())
            cand_res = await db.execute(cand_stmt)
            cand_events = cand_res.scalars().all()

            # Group candidates by distinct plate
            seen_cands = {}
            for ce in cand_events:
                if ce.plate not in seen_cands:
                    # Enforce camera window: same camera short window (<= 120s), or cross-camera (<= 1800s)
                    dt = abs((ts - ce.timestamp).total_seconds())
                    if ce.camera_id == camera_id and dt > 120:
                        continue
                    seen_cands[ce.plate] = ce

            for cand_plate, cand in seen_cands.items():
                pattern = None
                # Pattern a: Small edit distance (<= 2)
                if abs(len(plate) - len(cand_plate)) <= 2:
                    dist = levenshtein_distance(plate, cand_plate)
                    if 1 <= dist <= 2:
                        pattern = 'edit_distance'

                # Pattern b: Substring / partial read (prefix or suffix, length >= 3)
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
                        disambig = PlateDisambiguation(
                            variant_plate=plate,
                            canonical_plate=cand_plate,
                            camera_id=camera_id,
                            timestamp=ts,
                            ambiguity_pattern=pattern,
                            color_match=None,
                            type_match=None,
                            decision='unresolved',
                            details=f"Unresolved pair ({plate} vs {cand_plate}): vehicle attributes missing or unclear."
                        )
                        db.add(disambig)
                        alert = Alert(
                            type="plate_ambiguity_review",
                            plate=plate,
                            camera_id=camera_id,
                            message=f"Ambiguous plate pair ({plate} vs {cand_plate}, pattern: {pattern}) has unclear attributes. Flagged for review."
                        )
                        db.add(alert)
                    else:
                        type_match = (vehicle_type.lower() == cand.vehicle_type.lower())
                        color_match = (color.lower() == cand.color.lower())

                        if type_match and color_match:
                            # Resolve to SAME vehicle
                            # Determine canonical plate: longer string or higher confidence if equal length
                            if len(plate) != len(cand_plate):
                                is_incoming_canonical = len(plate) > len(cand_plate)
                            else:
                                cand_conf = cand.confidence or 0.0
                                is_incoming_canonical = confidence >= cand_conf

                            if is_incoming_canonical:
                                canonical_plate = plate
                                variant_plate = cand_plate
                            else:
                                canonical_plate = cand_plate
                                variant_plate = plate

                            disambig = PlateDisambiguation(
                                variant_plate=variant_plate,
                                canonical_plate=canonical_plate,
                                camera_id=camera_id,
                                timestamp=ts,
                                ambiguity_pattern=pattern,
                                color_match=True,
                                type_match=True,
                                decision='merged',
                                details=f"Resolved ambiguous pair to canonical plate {canonical_plate} based on matching {vehicle_type} and {color}."
                            )
                            db.add(disambig)

                            if variant_plate == plate:
                                plate = canonical_plate
                            else:
                                # Prior records had variant plate, incoming is canonical
                                await db.execute(
                                    text("UPDATE events SET plate = :canon WHERE plate = :variant"),
                                    {"canon": canonical_plate, "variant": variant_plate}
                                )
                                await db.execute(
                                    text("""
                                        INSERT INTO vehicles (plate, first_seen, last_seen)
                                        SELECT :canon, first_seen, last_seen FROM vehicles WHERE plate = :variant
                                        ON CONFLICT (plate) DO UPDATE SET
                                        first_seen = LEAST(vehicles.first_seen, EXCLUDED.first_seen),
                                        last_seen = GREATEST(vehicles.last_seen, EXCLUDED.last_seen)
                                    """),
                                    {"canon": canonical_plate, "variant": variant_plate}
                                )
                                await db.execute(
                                    text("DELETE FROM vehicles WHERE plate = :variant"),
                                    {"variant": variant_plate}
                                )
                            break
                        else:
                            # Either differs -> treat as genuinely DIFFERENT vehicles
                            disambig = PlateDisambiguation(
                                variant_plate=plate,
                                canonical_plate=cand_plate,
                                camera_id=camera_id,
                                timestamp=ts,
                                ambiguity_pattern=pattern,
                                color_match=color_match,
                                type_match=type_match,
                                decision='distinct',
                                details=f"Distinct vehicles: type_match={type_match}, color_match={color_match} ({plate}: {vehicle_type}/{color} vs {cand_plate}: {cand.vehicle_type}/{cand.color})."
                            )
                            db.add(disambig)

    # Insert Event
    new_event = Event(
        camera_id=camera_id,
        plate=plate,
        track_id=event_in.track_id,
        confidence=event_in.confidence,
        timestamp=ts,
        lat=event_in.lat,
        lng=event_in.lng,
        vehicle_type=vehicle_type,
        color=color
    )
    db.add(new_event)
    await db.flush()

    # Upsert Vehicle
    stmt = text("""
        INSERT INTO vehicles (plate, first_seen, last_seen)
        VALUES (:plate, :ts, :ts)
        ON CONFLICT (plate) DO UPDATE SET
        first_seen = LEAST(vehicles.first_seen, EXCLUDED.first_seen),
        last_seen = GREATEST(vehicles.last_seen, EXCLUDED.last_seen)
    """)
    await db.execute(stmt, {"plate": plate, "ts": ts})

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

    # Edge Building
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
            
    await db.commit()
    await db.refresh(new_event)
    return new_event
