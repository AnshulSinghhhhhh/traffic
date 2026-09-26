import asyncio
import asyncpg
import sys

DATABASE_URL = "postgresql://postgres:aniline12@localhost:5432/Db10"

async def get_counts():
    conn = await asyncpg.connect(DATABASE_URL)
    tables = ["cameras", "events", "edges", "vehicles", "blacklist", "alerts"]
    counts = {}
    for t in tables:
        c = await conn.fetchval(f"SELECT count(*) FROM {t}")
        counts[t] = c
    await conn.close()
    return counts

async def wipe_db():
    conn = await asyncpg.connect(DATABASE_URL)
    # TRUNCATE events, vehicles, edges, alerts (leave cameras and blacklist intact, or re-seed)
    await conn.execute("TRUNCATE events, vehicles, edges, alerts CASCADE;")
    print("Truncated events, vehicles, edges, alerts.")
    # Check if cameras are seeded
    cam_count = await conn.fetchval("SELECT count(*) FROM cameras")
    if cam_count == 0:
        await conn.execute("""
            INSERT INTO cameras (camera_id, name, lat, lng, road_name) VALUES
            ('CAM_01', 'Junction A', 12.9716, 77.5946, 'MG Road North'),
            ('CAM_02', 'Ring Road North', 12.9815, 77.6094, 'Outer Ring Road'),
            ('CAM_03', 'Market Circle', 12.9925, 77.6205, 'City Market Circle'),
            ('CAM_04', 'Highway Toll', 13.0041, 77.6340, 'Airport Expressway')
            ON CONFLICT DO NOTHING;
        """)
        print("Re-seeded cameras.")
    await conn.execute("""
        INSERT INTO blacklist (plate, reason, added_by) VALUES
        ('BG65USJ', 'Vehicle of interest — auto-theft investigation', 'Traffic Police HQ'),
        ('BGG5USJ', 'Legacy raw plate alias', 'Traffic Police HQ'),
        ('DL01AB1234', 'Stolen vehicle alert', 'State RTO')
        ON CONFLICT DO NOTHING;
    """)
    print("Seeded blacklist with targets.")
    await conn.close()

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status":
        counts = asyncio.run(get_counts())
        print("Current DB table row counts:")
        for t, c in counts.items():
            print(f"  {t}: {c}")
    elif action == "clean_bench":
        async def _c():
            conn = await asyncpg.connect(DATABASE_URL)
            await conn.execute("DELETE FROM events WHERE plate = 'BENCH_01'; DELETE FROM vehicles WHERE plate = 'BENCH_01';")
            await conn.close()
        asyncio.run(_c())
        print("Cleaned bench events.")
        counts = asyncio.run(get_counts())
        print("DB table row counts:")
        for t, c in counts.items():
            print(f"  {t}: {c}")
