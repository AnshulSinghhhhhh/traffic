import asyncio, asyncpg, json

camera_order = ['CAM_01', 'CAM_02', 'CAM_03', 'CAM_04']
cam_rank = {c: i for i, c in enumerate(camera_order)}

with open('events.json') as f:
    events = json.load(f)

plates = sorted(list(set(e['plate'] for e in events)))

async def main():
    conn = await asyncpg.connect('postgresql://postgres:aniline12@localhost:5432/Db10')
    correct = 0
    total = len(plates)
    results = []
    
    for p in plates:
        rows = await conn.fetch('SELECT camera_id, timestamp FROM events WHERE plate = $1 ORDER BY timestamp ASC', p)
        cams = [r['camera_id'] for r in rows]
        ranks = [cam_rank[c] for c in cams if c in cam_rank]
        is_strictly_ordered = all(ranks[i] < ranks[i+1] for i in range(len(ranks)-1))
        if is_strictly_ordered:
            correct += 1
        results.append((p, cams, is_strictly_ordered))
    
    await conn.close()
    
    acc = (correct / total) * 100.0
    print(f"Total Plates: {total}")
    print(f"Correct Sequences: {correct}")
    print(f"Trajectory Reconstruction Accuracy: {acc:.1f}%")
    for p, cams, ok in results:
        cam_str = " -> ".join(cams)
        print(f"  {p:10s} : {cam_str} | Correct: {ok}")

asyncio.run(main())
