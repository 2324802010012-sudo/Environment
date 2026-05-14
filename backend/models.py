from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy import UniqueConstraint

try:
    from .database import Base
except ImportError:
    from database import Base


class AirQuality(Base):
    __tablename__ = "air_quality"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    country = Column(String(100), default="Vietnam")
    time = Column(DateTime, index=True)

    pm25 = Column(Float)
    pm10 = Column(Float)
    co = Column(Float)
    no2 = Column(Float)
    so2 = Column(Float, nullable=True)
    o3 = Column(Float)
    aqi = Column(Float)
    station = Column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("city", "time", "station", name="unique_record"),
    )


class AirQualityHistory(Base):
    __tablename__ = "air_quality_history"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    country = Column(String(100), default="Vietnam")
    time = Column(DateTime, index=True)
    crawled_at = Column(DateTime, index=True)

    pm25 = Column(Float)
    pm10 = Column(Float)
    co = Column(Float)
    no2 = Column(Float)
    so2 = Column(Float, nullable=True)
    o3 = Column(Float)
    aqi = Column(Float)
    station = Column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("city", "time", "station", name="unique_history_record"),
    )
