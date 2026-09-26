from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.sql import func
from .database import Base

class Camera(Base):
    __tablename__ = 'cameras'
    camera_id = mapped_column(String, primary_key=True)
    name = mapped_column(String, nullable=False)
    lat = mapped_column(Float, nullable=False)
    lng = mapped_column(Float, nullable=False)
    road_name = mapped_column(String)

class Event(Base):
    __tablename__ = 'events'
    event_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id = mapped_column(String, ForeignKey('cameras.camera_id'), nullable=False)
    plate = mapped_column(String, nullable=False)
    track_id = mapped_column(Integer)
    confidence = mapped_column(Float)
    timestamp = mapped_column(DateTime(timezone=True), nullable=False)
    lat = mapped_column(Float)
    lng = mapped_column(Float)
    vehicle_type = mapped_column(String, nullable=True)
    color = mapped_column(String, nullable=True)

class Edge(Base):
    __tablename__ = 'edges'
    edge_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_cam = mapped_column(String, ForeignKey('cameras.camera_id'), nullable=False)
    to_cam = mapped_column(String, ForeignKey('cameras.camera_id'), nullable=False)
    count = mapped_column(Integer, nullable=False, default=0)
    avg_travel_time_s = mapped_column(Float)
    avg_speed_kmh = mapped_column(Float)
    last_seen = mapped_column(DateTime(timezone=True))

class Vehicle(Base):
    __tablename__ = 'vehicles'
    plate = mapped_column(String, primary_key=True)
    first_seen = mapped_column(DateTime(timezone=True))
    last_seen = mapped_column(DateTime(timezone=True))

class Blacklist(Base):
    __tablename__ = 'blacklist'
    plate = mapped_column(String, primary_key=True)
    reason = mapped_column(String)
    added_by = mapped_column(String)
    added_at = mapped_column(DateTime(timezone=True), server_default=func.now())

class Alert(Base):
    __tablename__ = 'alerts'
    alert_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    type = mapped_column(String, nullable=False)
    plate = mapped_column(String, nullable=False)
    camera_id = mapped_column(String, ForeignKey('cameras.camera_id'))
    message = mapped_column(String)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved = mapped_column(Boolean, default=False)

class PlateDisambiguation(Base):
    __tablename__ = 'plate_disambiguations'
    disambiguation_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_plate = mapped_column(String, nullable=False)
    canonical_plate = mapped_column(String, nullable=False)
    camera_id = mapped_column(String, ForeignKey('cameras.camera_id'))
    timestamp = mapped_column(DateTime(timezone=True), nullable=False)
    ambiguity_pattern = mapped_column(String, nullable=False)
    color_match = mapped_column(Boolean, nullable=True)
    type_match = mapped_column(Boolean, nullable=True)
    decision = mapped_column(String, nullable=False)
    details = mapped_column(String, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

