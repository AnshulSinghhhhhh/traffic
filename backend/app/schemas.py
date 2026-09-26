from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class EventIn(BaseModel):
    plate: str
    camera_id: str
    timestamp: datetime
    confidence: Optional[float] = None
    track_id: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    event_id: Optional[int] = None
    ocr_attempts: Optional[int] = None
    regex_valid_indian_format: Optional[bool] = None
    camera_name: Optional[str] = None
    vehicle_type: Optional[str] = None
    color: Optional[str] = None

class EventOut(BaseModel):
    event_id: int
    camera_id: str
    plate: str
    track_id: Optional[int] = None
    confidence: Optional[float] = None
    timestamp: datetime
    lat: Optional[float] = None
    lng: Optional[float] = None
    vehicle_type: Optional[str] = None
    color: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class CameraOut(BaseModel):
    camera_id: str
    name: str
    lat: float
    lng: float
    road_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class VehicleOut(BaseModel):
    plate: str
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    camera_count: int = 0
    has_alerts: bool = False
    model_config = ConfigDict(from_attributes=True)

class TrajectoryPoint(BaseModel):
    camera_id: str
    timestamp: datetime
    lat: Optional[float] = None
    lng: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class DensityOut(BaseModel):
    camera_id: str
    event_count: int
    window_minutes: int
    model_config = ConfigDict(from_attributes=True)

class CongestionOut(BaseModel):
    camera_id: str
    recent_count: int
    rolling_avg: float
    congested: bool
    model_config = ConfigDict(from_attributes=True)

class AlertOut(BaseModel):
    alert_id: int
    type: str
    plate: str
    camera_id: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True)

class BlacklistIn(BaseModel):
    plate: str
    reason: Optional[str] = None

class BlacklistOut(BaseModel):
    plate: str
    reason: Optional[str] = None
    added_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class DisambiguationOut(BaseModel):
    disambiguation_id: int
    variant_plate: str
    canonical_plate: str
    camera_id: Optional[str] = None
    timestamp: datetime
    ambiguity_pattern: str
    color_match: Optional[bool] = None
    type_match: Optional[bool] = None
    decision: str
    details: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

