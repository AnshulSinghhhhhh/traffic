import asyncio
import asyncpg

DATABASE_URL = "postgresql://postgres:aniline12@localhost:5432/Db10"

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    
    # 1. KH06KSU events
    rows = await conn.fetch("SELECT event_id, camera_id, plate, track_id, timestamp FROM events WHERE plate = 'KH06KSU' ORDER BY timestamp ASC")
    print(f"Total events for KH06KSU: {len(rows)}")
    for r in rows:
        print("  ", dict(r))
    
    veh = await conn.fetchrow("SELECT * FROM vehicles WHERE plate = 'KH06KSU'")
    print("Vehicle row for KH06KSU:", dict(veh))

    # 2. Check Blacklist alerts
    alerts = await conn.fetch("SELECT * FROM alerts ORDER BY created_at ASC")
    print(f"\nTotal alerts: {len(alerts)}")
    for a in alerts:
        print("  ", dict(a))

    # 3. Check Edges
    edges = await conn.fetch("SELECT * FROM edges ORDER BY count DESC")
    print(f"\nTotal edges: {len(edges)}")
    for e in edges:
        print("  ", dict(e))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
