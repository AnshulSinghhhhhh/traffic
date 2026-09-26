from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from ..database import get_db
from ..models import Alert, Blacklist, PlateDisambiguation
from ..schemas import AlertOut, BlacklistIn, BlacklistOut, DisambiguationOut

router = APIRouter(tags=["Alerts"])

@router.get("/alerts", response_model=List[AlertOut])
async def get_alerts(alert_status: str = 'unresolved', db: AsyncSession = Depends(get_db)):
    stmt = select(Alert).order_by(Alert.created_at.desc())
    if alert_status == 'unresolved':
        stmt = stmt.where(Alert.resolved == False)
    elif alert_status == 'resolved':
        stmt = stmt.where(Alert.resolved == True)
        
    res = await db.execute(stmt)
    return res.scalars().all()

@router.patch("/alerts/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Alert).where(Alert.alert_id == alert_id))
    alert = res.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.resolved = True
    await db.commit()
    await db.refresh(alert)
    return alert

@router.post("/blacklist", response_model=BlacklistOut, status_code=status.HTTP_201_CREATED)
async def create_blacklist(bl_in: BlacklistIn, db: AsyncSession = Depends(get_db)):
    stmt = text("""
        INSERT INTO blacklist (plate, reason)
        VALUES (:plate, :reason)
        ON CONFLICT (plate) DO UPDATE SET
        reason = EXCLUDED.reason
        RETURNING plate, reason, added_at
    """)
    res = await db.execute(stmt, {"plate": bl_in.plate, "reason": bl_in.reason})
    await db.commit()
    row = res.mappings().first()
    return BlacklistOut(
        plate=row["plate"],
        reason=row["reason"],
        added_at=row["added_at"]
    )

@router.get("/disambiguations", response_model=List[DisambiguationOut])
async def get_disambiguations(db: AsyncSession = Depends(get_db)):
    stmt = select(PlateDisambiguation).order_by(PlateDisambiguation.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

