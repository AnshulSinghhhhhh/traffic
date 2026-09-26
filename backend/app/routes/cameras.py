from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import Camera
from ..schemas import CameraOut

router = APIRouter(prefix="/cameras", tags=["Cameras"])

@router.get("", response_model=List[CameraOut])
async def get_cameras(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Camera))
    return res.scalars().all()
