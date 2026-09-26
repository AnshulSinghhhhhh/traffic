import asyncio, asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:aniline12@localhost:5432/Db10')
    edges = await conn.fetch('SELECT from_cam, to_cam, count, avg_travel_time_s, avg_speed_kmh FROM edges ORDER BY from_cam, to_cam')
    print("=== EDGES MEASURED VS CONFIGURED ===")
    nominal = {
        ('CAM_01', 'CAM_02'): 240.0,
        ('CAM_01', 'CAM_03'): 560.0,
        ('CAM_02', 'CAM_03'): 320.0,
        ('CAM_02', 'CAM_04'): 660.0,
        ('CAM_03', 'CAM_04'): 340.0,
    }
    for e in edges:
        pair = (e['from_cam'], e['to_cam'])
        nom = nominal.get(pair, 0.0)
        diff = e['avg_travel_time_s'] - nom
        pct_err = (diff / nom) * 100.0 if nom > 0 else 0.0
        print(f"{e['from_cam']} -> {e['to_cam']}: count={e['count']}, measured_tt={e['avg_travel_time_s']:.2f}s, configured_nom={nom:.1f}s, diff={diff:+.2f}s ({pct_err:+.2f}%), speed={e['avg_speed_kmh']:.2f} km/h")
    
    # Table counts
    print("\n=== ROW COUNTS ===")
    for tbl in ['events', 'vehicles', 'edges', 'alerts', 'cameras', 'blacklist']:
        cnt = await conn.fetchval(f"SELECT count(*) FROM {tbl}")
        print(f"  {tbl}: {cnt}")
    
    await conn.close()

asyncio.run(main())
