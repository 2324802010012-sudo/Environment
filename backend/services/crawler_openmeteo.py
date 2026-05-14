"""
Open-Meteo Air Quality API crawler.

This is the only crawler used by the project. It collects air-quality
records directly from the Open-Meteo public API and stores only current
or already-observed hourly values, not future forecast rows.

API: https://open-meteo.com/en/docs/air-quality-api
"""

import logging
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cities import CITY_PROFILES

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Parameters mapping: Open-Meteo indicator names
AIR_QUALITY_PARAMS = {
    "pm10": "pm10",
    "pm2_5": "pm25",  # Map to our db column
    "carbon_monoxide": "co",
    "nitrogen_dioxide": "no2",
    "sulphur_dioxide": "so2",
    "ozone": "o3",
    "us_aqi": "aqi",  # Use US AQI as our main AQI
}

REQUEST_TIMEOUT = int(os.getenv("OPEN_METEO_TIMEOUT_SECONDS", "15"))
MAX_WORKERS = int(os.getenv("OPEN_METEO_MAX_WORKERS", "6"))
RETRY_TOTAL = 3
RETRY_BACKOFF = 0.6
REQUEST_DELAY_SECONDS = float(os.getenv("OPEN_METEO_REQUEST_DELAY_SECONDS", "0.05"))


def build_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "AirQualityStudentProject/1.0 (Open-Meteo API client)",
            "Accept": "application/json",
        }
    )
    retry = Retry(
        total=RETRY_TOTAL,
        connect=RETRY_TOTAL,
        read=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


HTTP_SESSION = build_session()


def vietnam_openmeteo_cities() -> List[Dict]:
    """Build Open-Meteo city payloads from Vietnam and foreign city profiles."""
    return [
        {
            "name": profile["name"],
            "lat": profile["coords"][0],
            "lon": profile["coords"][1],
            "country": profile.get("country", "Vietnam"),
        }
        for profile in CITY_PROFILES
    ]


GLOBAL_CITIES = vietnam_openmeteo_cities()


def safe_float(value):
    """Safely convert value to float."""
    try:
        if value is None or value == "" or value == "-":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_openmeteo_time(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def calculate_aqi_from_pollutants(pm25, pm10, co=None, no2=None, so2=None, o3=None) -> Optional[float]:
    """Deprecated fallback. The production crawler stores only Open-Meteo US AQI."""
    if pm25 is None:
        return None
    
    # Fallback only. The primary AQI value comes directly from Open-Meteo us_aqi.
    aqi_from_pm25 = pm25 * 4 if pm25 is not None else 0
    aqi_from_pm10 = pm10 * 2 if pm10 is not None else 0
    return min(max(aqi_from_pm25, aqi_from_pm10), 500)


def fetch_open_meteo_data(city: Dict, hourly_limit: int = 12) -> List[Dict]:
    """
    Fetch air quality data from Open-Meteo for a single city.
    
    Returns:
        List of records with city, time, aqi, pm25, pm10, co, no2, so2, o3
    """
    try:
        params = {
            "latitude": city["lat"],
            "longitude": city["lon"],
            "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi",
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi",
            # Keep every city in the same local timezone as the application.
            # This makes freshness checks consistent for Vietnam and foreign cities.
            "timezone": "Asia/Ho_Chi_Minh",
            "past_days": 2,
            "forecast_days": 1,
        }
        
        if REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

        response = HTTP_SESSION.get(
            OPEN_METEO_URL,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        
        records = []
        
        current_time = None
        collected_at = datetime.now().replace(microsecond=0)
        now_local = collected_at

        # Current data (most recent)
        if "current" in data:
            current = data["current"]
            current_time = parse_openmeteo_time(current.get("time")) or collected_at
            record = {
                "city": city["name"],
                "country": city["country"],
                "latitude": city["lat"],
                "longitude": city["lon"],
                "time": current_time,
                "observed_time": current_time,
                "collected_at": collected_at,
                "station": "open_meteo",
                "aqi": safe_float(current.get("us_aqi")),
                "pm25": safe_float(current.get("pm2_5")),
                "pm10": safe_float(current.get("pm10")),
                "co": safe_float(current.get("carbon_monoxide")),
                "no2": safe_float(current.get("nitrogen_dioxide")),
                "so2": safe_float(current.get("sulphur_dioxide")),
                "o3": safe_float(current.get("ozone")),
            }
            
            if current_time <= now_local and record["aqi"] is not None and 0 <= record["aqi"] <= 500:
                records.append(record)
                logger.debug(f"[OPEN-METEO] {city['name']}: AQI {record['aqi']}")
        
        # Hourly data (last few hours)
        if "hourly" in data and "time" in data["hourly"]:
            times = data["hourly"]["time"]
            pm10_vals = data["hourly"].get("pm10", [])
            pm25_vals = data["hourly"].get("pm2_5", [])
            co_vals = data["hourly"].get("carbon_monoxide", [])
            no2_vals = data["hourly"].get("nitrogen_dioxide", [])
            so2_vals = data["hourly"].get("sulphur_dioxide", [])
            o3_vals = data["hourly"].get("ozone", [])
            aqi_vals = data["hourly"].get("us_aqi", [])
            
            # Only store hourly values that have already happened. Open-Meteo can
            # return forecast hours; those are useful, but this project stores
            # collected/current facts rather than future predictions.
            valid_indexes = []
            for i, value in enumerate(times):
                time_val = parse_openmeteo_time(value)
                if time_val and time_val <= now_local:
                    valid_indexes.append((i, time_val))

            for i, time_val in valid_indexes[-max(1, hourly_limit):]:
                if current_time and time_val == current_time:
                    continue

                pm25 = safe_float(pm25_vals[i] if i < len(pm25_vals) else None)
                aqi = safe_float(aqi_vals[i] if i < len(aqi_vals) else None)

                if aqi is not None and 0 <= aqi <= 500:
                    record = {
                        "city": city["name"],
                        "country": city["country"],
                        "latitude": city["lat"],
                        "longitude": city["lon"],
                        "time": time_val,
                        "observed_time": time_val,
                        "collected_at": collected_at,
                        "station": "open_meteo_hourly",
                        "aqi": aqi,
                        "pm25": pm25,
                        "pm10": safe_float(pm10_vals[i] if i < len(pm10_vals) else None),
                        "co": safe_float(co_vals[i] if i < len(co_vals) else None),
                        "no2": safe_float(no2_vals[i] if i < len(no2_vals) else None),
                        "so2": safe_float(so2_vals[i] if i < len(so2_vals) else None),
                        "o3": safe_float(o3_vals[i] if i < len(o3_vals) else None),
                    }
                    records.append(record)
        
        return records
        
    except Exception as exc:
        logger.warning(f"[OPEN-METEO ERROR] {city['name']}: {exc}")
        return []


def fetch_data_openmeteo(
    target_records: int = 1500,
    cities_list: Optional[List[Dict]] = None,
    hourly_limit: Optional[int] = None,
    verbose: bool = False,
) -> List[Dict]:
    """
    Fetch air quality data from Open-Meteo for multiple cities.
    
    Args:
        target_records: Target number of records to fetch
        cities_list: List of cities (default: GLOBAL_CITIES)
        verbose: Print progress
    
    Returns:
        List of all records fetched
    """
    if cities_list is None:
        cities_list = GLOBAL_CITIES

    if hourly_limit is None:
        hourly_limit = max(6, math.ceil(target_records / max(len(cities_list), 1)) + 2)
    
    print("===== OPEN-METEO CRAWL START =====")
    print(f"Target: {target_records} records")
    print(f"Cities: {len(cities_list)}")
    
    all_records = []
    seen_keys = set()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_open_meteo_data, city, hourly_limit): city
            for city in cities_list
        }
        
        for future in as_completed(futures):
            city = futures[future]
            try:
                records = future.result()
                for record in records:
                    key = (record["city"], record["time"], record["station"])
                    if key in seen_keys:
                        continue
                    
                    seen_keys.add(key)
                    all_records.append(record)
                    
                    if verbose:
                        print(f"  {record['city']}: AQI={record['aqi']}")
                    
            except Exception as exc:
                logger.error(f"Error processing {city['name']}: {exc}")
    
    print(f"TOTAL FETCHED: {len(all_records)} records")
    return all_records


if __name__ == "__main__":
    # Test
    records = fetch_data_openmeteo(target_records=100, verbose=True)
    print(f"\nFetched {len(records)} records")
    if records:
        print(f"Sample: {records[0]}")
