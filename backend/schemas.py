from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

class AirQualityRecord(BaseModel):
    city: str
    time: datetime
    pm25: float
    pm10: float
    co: float
    no2: float
    o3: float
    aqi: float

class RankingItem(BaseModel):
    city: str
    aqi: float

class ChartResponse(BaseModel):
    labels: List[str]
    aqi: List[Optional[float]]

class ClusterItem(BaseModel):
    city: str
    level: str
    pm25: float
    pm10: float
    co: float
    no2: float
    o3: float
    aqi: float
