from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import synonym

try:
    from .database import Base
except ImportError:
    from database import Base


def now_local():
    return datetime.now().replace(microsecond=0)


class AirQuality(Base):
    __tablename__ = "air_quality"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    country = Column(String(100), default="Vietnam")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    observed_time = Column(DateTime, index=True)
    collected_at = Column(DateTime, index=True, default=now_local)

    pm25 = Column(Float)
    pm10 = Column(Float)
    co = Column(Float)
    no2 = Column(Float)
    so2 = Column(Float, nullable=True)
    o3 = Column(Float)
    aqi = Column(Float)
    station = Column(String(200), nullable=True)

    # Backward-compatible Python alias for older code and API responses.
    time = synonym("observed_time")

    __table_args__ = (
        UniqueConstraint("city", "observed_time", "station", name="unique_record"),
    )


class AirQualityHistory(Base):
    __tablename__ = "air_quality_history"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    country = Column(String(100), default="Vietnam")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    observed_time = Column(DateTime, index=True)
    collected_at = Column(DateTime, index=True, default=now_local)

    pm25 = Column(Float)
    pm10 = Column(Float)
    co = Column(Float)
    no2 = Column(Float)
    so2 = Column(Float, nullable=True)
    o3 = Column(Float)
    aqi = Column(Float)
    station = Column(String(200), nullable=True)

    time = synonym("observed_time")
    crawled_at = synonym("collected_at")

    __table_args__ = (
        UniqueConstraint("city", "observed_time", "station", name="unique_history_record"),
    )
