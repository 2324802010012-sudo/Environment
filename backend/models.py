from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base

from sqlalchemy import UniqueConstraint

class AirQuality(Base):
    __tablename__ = "air_quality"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    time = Column(DateTime, index=True)

    pm25 = Column(Float)
    pm10 = Column(Float)
    co = Column(Float)
    no2 = Column(Float)
    o3 = Column(Float)
    aqi = Column(Float)
    station = Column(String(200), nullable=True)

    __table_args__ = (
    UniqueConstraint('city', 'time', 'station', name='unique_record'),
)