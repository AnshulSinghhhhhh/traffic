from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..database import get_db
from ..models import Vehicle, Event, Alert
from ..schemas import VehicleOut, TrajectoryPoint

router = APIRouter(tags=["Vehicles"])

@router.get("/vehicle/{plate}", response_model=VehicleOut)
async def get_vehicle(plate: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Vehicle).where(Vehicle.plate == plate))
    vehicle = res.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
        
    cam_count_res = await db.execute(
        select(func.count(func.distinct(Event.camera_id))).where(Event.plate == plate)
    )
    cam_count = cam_count_res.scalar() or 0
    
    alert_res = await db.execute(
        select(func.count(Alert.alert_id)).where(Alert.plate == plate, Alert.resolved == False)
    )
    has_alerts = (alert_res.scalar() or 0) > 0
    
    return VehicleOut(
        plate=vehicle.plate,
        first_seen=vehicle.first_seen,
        last_seen=vehicle.last_seen,
        camera_count=cam_count,
        has_alerts=has_alerts
    )

@router.get("/trajectory/{plate}", response_model=List[TrajectoryPoint])
async def get_trajectory(plate: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Event.camera_id, Event.timestamp, Event.lat, Event.lng)
        .where(Event.plate == plate)
        .order_by(Event.timestamp.asc())
    )
    return res.mappings().all()
