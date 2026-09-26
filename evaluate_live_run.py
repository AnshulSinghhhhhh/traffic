import asyncio
import asyncpg
import json
import urllib.request
import statistics

DATABASE_URL = "postgresql://postgres:aniline12@localhost:5432/Db10"

camera_order = ['CAM_01', 'CAM_02', 'CAM_03', 'CAM_04']
cam_rank = {c: i for i, c in enumerate(camera_order)}

NOMINAL_OFFSETS = {
    ('CAM_01', 'CAM_02'): 240.0,
    ('CAM_01', 'CAM_03'): 560.0,
    ('CAM_02', 'CAM_03'): 320.0,  # 560 - 240
    ('CAM_02', 'CAM_04'): 660.0,  # 900 - 240
    ('CAM_03', 'CAM_04'): 340.0,  # 900 - 560
}

async def analyze():
    conn = await asyncpg.connect(DATABASE_URL)
    
    # 1. Total plates and trajectory reconstruction
    rows = await conn.fetch("SELECT DISTINCT plate FROM vehicles ORDER BY plate ASC")
    plates = [r['plate'] for r in rows]
    print(f"Total Unique Vehicle Plates in DB: {len(plates)}")
    
    trajectories = {}
    ordered_count = 0
    traversal_classes = collections.defaultdict(list)

    for p in plates:
        evs = await conn.fetch("SELECT camera_id, timestamp, track_id FROM events WHERE plate = $1 ORDER BY timestamp ASC", p)
        cams = [e['camera_id'] for e in evs]
        # deduplicate consecutive identical cameras for sequence topology classification
        dedup_cams = [cams[i] for i in range(len(cams)) if i == 0 or cams[i] != cams[i-1]]
        ranks = [cam_rank[c] for c in dedup_cams if c in cam_rank]
        is_ordered = all(ranks[i] < ranks[i+1] for i in range(len(ranks)-1))
        if is_ordered:
            ordered_count += 1
        topo_str = " -> ".join(dedup_cams)
        traversal_classes[topo_str].append((p, [e['track_id'] for e in evs]))
        trajectories[p] = (cams, dedup_cams, is_ordered)

    print(f"Correctly ordered trajectories: {ordered_count}/{len(plates)} ({(ordered_count/len(plates))*100:.1f}%)")
    print("\nTraversal Class Breakdown:")
    for topo, plist in sorted(traversal_classes.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {topo} ({len(plist)} vehicles):")
        print(f"     Plates: {[p[0] for p in plist]}")

    # 2. Edges table analysis
    edges = await conn.fetch("SELECT from_cam, to_cam, count, avg_travel_time_s, avg_speed_kmh FROM edges ORDER BY from_cam ASC, to_cam ASC")
    print("\n--- EDGES TABLE EVALUATION ---")
    for e in edges:
        fc, tc = e['from_cam'], e['to_cam']
        cnt = e['count']
        t_avg = e['avg_travel_time_s']
        v_avg = e['avg_speed_kmh']
        nominal = NOMINAL_OFFSETS.get((fc, tc), 0.0)
        delta = t_avg - nominal
        rel_err = (delta / nominal) * 100.0 if nominal > 0 else 0.0
        edge_type = "Direct Link" if abs(cam_rank[tc] - cam_rank[fc]) == 1 else "Dropout Skip"
        print(f"{fc} -> {tc} | Type: {edge_type:12s} | Count: {cnt:2d} | Avg Time: {t_avg:6.2f}s | Nominal: {nominal:5.1f}s | Delta: {delta:+5.2f}s ({rel_err:+5.2f}%) | Avg Speed: {v_avg:5.2f} km/h")

    # 3. Alerts analysis
    alerts = await conn.fetch("SELECT alert_id, type, plate, camera_id, message, created_at, resolved FROM alerts ORDER BY created_at ASC")
    print(f"\n--- ALERTS TABLE ({len(alerts)} alerts) ---")
    for a in alerts:
        print(f"  Alert #{a['alert_id']}: {a['type']} for {a['plate']} at {a['camera_id']}")

    await conn.close()

if __name__ == "__main__":
    import collections
    asyncio.run(analyze())
