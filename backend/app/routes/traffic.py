from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..database import get_db
from ..schemas import DensityOut, CongestionOut

router = APIRouter(prefix="/traffic", tags=["Traffic"])

@router.get("/density", response_model=List[DensityOut])
async def get_density(window: int = 15, db: AsyncSession = Depends(get_db)):
    stmt = text("""
        SELECT camera_id, COUNT(*) as event_count
        FROM events
        WHERE timestamp >= NOW() - INTERVAL '1 minute' * :window
        GROUP BY camera_id
    """)
    res = await db.execute(stmt, {"window": window})
    results = []
    for row in res.mappings():
        results.append(DensityOut(
            camera_id=row["camera_id"],
            event_count=row["event_count"],
            window_minutes=window
        ))
    return results

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
