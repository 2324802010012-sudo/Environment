import os
import threading
from datetime import datetime, time as datetime_time, timedelta
from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import asc, desc, inspect, or_, text
from sqlalchemy.orm import Session

try:
    from . import crud, models
    from .database import SessionLocal, engine
    from .services.cities import CITY_PROFILES, canonical_city_name, city_search_terms, strip_accents
    from .services.crawler_openmeteo import GLOBAL_CITIES, fetch_data_openmeteo
    from .services.data_loader import DataLoader
    from .services.ml import city_cluster_level, cluster_data
    from .services.predict import predict_aqi
    from .services.robots_checker import check_openmeteo_compliance
except ImportError:
    import crud
    import models
    from database import SessionLocal, engine
    from services.cities import CITY_PROFILES, canonical_city_name, city_search_terms, strip_accents
    from services.crawler_openmeteo import GLOBAL_CITIES, fetch_data_openmeteo
    from services.data_loader import DataLoader
    from services.ml import city_cluster_level, cluster_data
    from services.predict import predict_aqi
    from services.robots_checker import check_openmeteo_compliance


models.Base.metadata.create_all(bind=engine)


def _column_names(inspector, table_name):
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def ensure_air_quality_schema():
    """Small safe migration layer for projects that already had the old schema."""
    inspector = inspect(engine)
    table_columns = {
        "air_quality": _column_names(inspector, "air_quality"),
        "air_quality_history": _column_names(inspector, "air_quality_history"),
    }

    migrations = []
    common_columns = {
        "country": "VARCHAR(100) DEFAULT 'Vietnam'",
        "latitude": "FLOAT NULL",
        "longitude": "FLOAT NULL",
        "observed_time": "DATETIME NULL",
        "collected_at": "DATETIME NULL",
        "so2": "FLOAT NULL",
        "station": "VARCHAR(200) NULL",
    }

    for table_name, columns in table_columns.items():
        if not columns:
            continue
        for column_name, column_type in common_columns.items():
            if column_name not in columns:
                migrations.append(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    with engine.begin() as connection:
        for statement in migrations:
            connection.execute(text(statement))

        refreshed = inspect(engine)
        for table_name in ("air_quality", "air_quality_history"):
            columns = _column_names(refreshed, table_name)
            if "observed_time" in columns and "time" in columns:
                connection.execute(
                    text(
                        f"UPDATE {table_name} "
                        "SET observed_time = time "
                        "WHERE observed_time IS NULL AND time IS NOT NULL"
                    )
                )
            if "collected_at" in columns:
                if table_name == "air_quality_history" and "crawled_at" in columns:
                    connection.execute(
                        text(
                            "UPDATE air_quality_history "
                            "SET collected_at = crawled_at "
                            "WHERE collected_at IS NULL AND crawled_at IS NOT NULL"
                        )
                    )
                connection.execute(
                    text(
                        f"UPDATE {table_name} "
                        "SET collected_at = NOW() WHERE collected_at IS NULL"
                    )
                )


ensure_air_quality_schema()

app = FastAPI(title="Air Quality Ranking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CRAWL_LOCK = threading.Lock()
AUTO_CRAWL_ENABLED = os.getenv("AUTO_CRAWL_ENABLED", "false").lower() == "true"
AUTO_CRAWL_INTERVAL_SECONDS = int(os.getenv("AUTO_CRAWL_INTERVAL_SECONDS", "3600"))
AUTO_CRAWL_TARGET = int(os.getenv("AUTO_CRAWL_TARGET", "1500"))
CURRENT_DATA_MAX_AGE_HOURS = int(os.getenv("CURRENT_DATA_MAX_AGE_HOURS", "48"))
CRAWL_MIN_INTERVAL_SECONDS = int(os.getenv("CRAWL_MIN_INTERVAL_SECONDS", "300"))
AUTO_CRAWL_STOP = threading.Event()
AUTO_CRAWL_THREAD = None
LAST_MANUAL_CRAWL_AT = None
AUTO_CRAWL_STATUS = {
    "enabled": AUTO_CRAWL_ENABLED,
    "running": False,
    "last_run_at": None,
    "last_result": None,
    "last_error": None,
    "interval_seconds": AUTO_CRAWL_INTERVAL_SECONDS,
    "min_manual_interval_seconds": CRAWL_MIN_INTERVAL_SECONDS,
}

POLLUTANT_FIELDS = ["pm25", "pm10", "co", "no2", "so2", "o3"]
SORTABLE_FIELDS = ["time", "aqi", *POLLUTANT_FIELDS]
RANKING_METRICS = ["aqi", *POLLUTANT_FIELDS, "pollution_score"]
POLLUTION_WEIGHTS = {
    "aqi": 0.5,
    "pm25": 0.2,
    "pm10": 0.15,
    "no2": 0.05,
    "so2": 0.05,
    "o3": 0.05,
}
LEVEL_RANGES = {
    "good": (0, 50),
    "tot": (0, 50),
    "moderate": (51, 100),
    "trung_binh": (51, 100),
    "unhealthy_sensitive": (101, 150),
    "kem": (101, 150),
    "unhealthy": (101, 200),
    "xau": (101, 200),
    "very_unhealthy": (201, 300),
    "rat_xau": (201, 300),
    "hazardous": (301, 500),
    "nguy_hai": (301, 500),
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def metric(value):
    return round(float(value), 2) if value is not None else None


def aqi_level(aqi):
    if aqi is None:
        return "Không có dữ liệu"
    aqi = float(aqi)
    if aqi <= 50:
        return "Tốt"
    if aqi <= 100:
        return "Trung bình"
    if aqi <= 150:
        return "Kém"
    if aqi <= 200:
        return "Xấu"
    if aqi <= 300:
        return "Rất xấu"
    return "Nguy hại"


def aqi_level_code(aqi):
    if aqi is None:
        return "unknown"
    aqi = float(aqi)
    if aqi <= 50:
        return "good"
    if aqi <= 100:
        return "moderate"
    if aqi <= 200:
        return "unhealthy"
    if aqi <= 300:
        return "very_unhealthy"
    return "hazardous"


def parse_datetime_param(value: Optional[str], end_of_day=False):
    if not value:
        return None
    try:
        cleaned = value.strip()
        if len(cleaned) == 10:
            parsed_date = datetime.fromisoformat(cleaned).date()
            boundary = datetime_time.max if end_of_day else datetime_time.min
            return datetime.combine(parsed_date, boundary).replace(microsecond=0)
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date/datetime: {value}") from exc


def level_range(level):
    if not level:
        return None
    key = strip_accents(level).replace(" ", "_")
    return LEVEL_RANGES.get(key)


def data_quality(row):
    present = [field for field in POLLUTANT_FIELDS if getattr(row, field) is not None]
    if len(present) == len(POLLUTANT_FIELDS):
        quality = "complete"
    elif present:
        quality = "partial"
    else:
        quality = "aqi_only"

    return {
        "quality": quality,
        "available_pollutants": present,
        "missing_pollutants": [field for field in POLLUTANT_FIELDS if field not in present],
    }


def row_age_hours(row):
    observed_time = getattr(row, "observed_time", None)
    if not row or not observed_time:
        return None
    return round(max(0, (datetime.now() - observed_time).total_seconds() / 3600), 2)


def serialize_row(row, cluster_level=None):
    aqi = metric(row.aqi)
    return {
        "id": row.id,
        "city": canonical_city_name(row.city),
        "country": row.country,
        "latitude": metric(row.latitude),
        "longitude": metric(row.longitude),
        "observed_time": str(row.observed_time) if row.observed_time else None,
        "time": str(row.observed_time) if row.observed_time else None,
        "collected_at": str(row.collected_at) if row.collected_at else None,
        "pm25": metric(row.pm25),
        "pm10": metric(row.pm10),
        "co": metric(row.co),
        "no2": metric(row.no2),
        "so2": metric(row.so2),
        "o3": metric(row.o3),
        "aqi": aqi,
        "level": aqi_level(aqi),
        "level_code": aqi_level_code(aqi),
        "cluster_level": cluster_level,
        "station": row.station,
        "source": row.station,
        **data_quality(row),
    }


def serialize_summary(row, cluster_level=None):
    payload = serialize_row(row, cluster_level=cluster_level)
    payload.pop("id", None)
    return payload


def distinct_time_series(rows):
    unique = []
    seen = set()
    for row in rows:
        key = str(row.observed_time)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return list(reversed(unique))


def average_present(rows, field):
    values = [float(getattr(row, field)) for row in rows if getattr(row, field) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def pollution_score_for_row(row):
    parts = []
    for field, weight in POLLUTION_WEIGHTS.items():
        value = getattr(row, field, None)
        if value is not None:
            parts.append((float(value), weight, field))

    if not parts:
        return None, []

    weight_sum = sum(weight for _, weight, _ in parts)
    score = sum(value * weight for value, weight, _ in parts) / weight_sum
    return round(score, 2), [field for _, _, field in parts]


def cluster_map(db, max_age_hours=None):
    result = cluster_data(db, max_age_hours=max_age_hours)
    return {
        canonical_city_name(row["city"]): row.get("level")
        for row in result.get("clusters", [])
    }


def manual_crawl_wait_seconds(force=False):
    if force or LAST_MANUAL_CRAWL_AT is None:
        return 0
    elapsed = (datetime.now() - LAST_MANUAL_CRAWL_AT).total_seconds()
    return max(0, int(CRAWL_MIN_INTERVAL_SECONDS - elapsed))


def run_crawl_job(db, target=1500, replace_existing=True):
    source = "open-meteo"
    raw_data = fetch_data_openmeteo(target_records=target, cities_list=GLOBAL_CITIES)
    clean_data, stats = DataLoader().load_and_process(raw_data)

    if not clean_data:
        return {
            "error": "No valid data fetched",
            "raw_count": len(raw_data),
            "clean_count": stats["valid_count"],
            "invalid_count": stats.get("invalid_count", 0),
            "archived_count": 0,
            "deleted_count": 0,
            "inserted_count": 0,
            "replace_existing": replace_existing,
            "source": source,
        }

    deleted = 0
    archived = crud.archive_data(db, clean_data)
    if replace_existing:
        deleted = crud.clear_data(db)

    inserted = crud.insert_data(db, clean_data)
    return {
        "message": "Data refreshed" if replace_existing else "Data inserted",
        "raw_count": len(raw_data),
        "clean_count": stats["valid_count"],
        "invalid_count": stats.get("invalid_count", 0),
        "archived_count": archived,
        "deleted_count": deleted,
        "inserted_count": inserted,
        "replace_existing": replace_existing,
        "source": source,
    }


@app.get("/")
def root():
    return {"message": "Air Quality API running"}


@app.get("/cities")
def cities():
    return [
        {
            "name": profile["name"],
            "slug": profile["slug"],
            "country": profile.get("country", "Vietnam"),
            "coords": profile["coords"],
        }
        for profile in CITY_PROFILES
    ]


def find_city_profile(city):
    canonical = canonical_city_name(city)
    for profile in CITY_PROFILES:
        if canonical_city_name(profile["name"]) == canonical:
            return profile
    return None


def openmeteo_source_url(profile):
    lat, lon = profile["coords"]
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi",
        "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi",
        "timezone": "Asia/Ho_Chi_Minh",
        "past_days": 2,
        "forecast_days": 1,
    }
    return f"https://air-quality-api.open-meteo.com/v1/air-quality?{urlencode(params)}"


@app.get("/source-url")
def source_url(city: str = Query(...)):
    profile = find_city_profile(city)
    if not profile:
        raise HTTPException(status_code=404, detail=f"City not found: {city}")

    lat, lon = profile["coords"]
    return {
        "city": profile["name"],
        "country": profile.get("country", "Vietnam"),
        "latitude": lat,
        "longitude": lon,
        "source": "Open-Meteo Air Quality API",
        "api_url": openmeteo_source_url(profile),
        "docs_url": "https://open-meteo.com/en/docs/air-quality-api",
    }


def start_crawl(target, replace_existing, force, db):
    global LAST_MANUAL_CRAWL_AT
    wait_seconds = manual_crawl_wait_seconds(force=force)
    if wait_seconds > 0:
        return {
            "error": f"Please wait {wait_seconds} seconds before starting another crawl.",
            "retry_after_seconds": wait_seconds,
            "raw_count": 0,
            "clean_count": 0,
            "archived_count": 0,
            "deleted_count": 0,
            "inserted_count": 0,
            "replace_existing": replace_existing,
            "source": "open-meteo",
        }

    if not CRAWL_LOCK.acquire(blocking=False):
        return {
            "error": "A crawl job is already running. Please wait for it to finish.",
            "raw_count": 0,
            "clean_count": 0,
            "archived_count": 0,
            "deleted_count": 0,
            "inserted_count": 0,
            "replace_existing": replace_existing,
            "source": "open-meteo",
        }

    try:
        LAST_MANUAL_CRAWL_AT = datetime.now()
        return run_crawl_job(db, target=target, replace_existing=replace_existing)
    except Exception as exc:
        return {
            "error": f"Crawl failed: {exc}",
            "raw_count": 0,
            "clean_count": 0,
            "archived_count": 0,
            "deleted_count": 0,
            "inserted_count": 0,
            "replace_existing": replace_existing,
            "source": "open-meteo",
        }
    finally:
        CRAWL_LOCK.release()


@app.get("/crawl")
def crawl(
    target: int = Query(1500, ge=1, le=5000),
    replace_existing: bool = Query(True),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    return start_crawl(target, replace_existing, force, db)


@app.get("/crawl-openmeteo")
def crawl_openmeteo(
    target: int = Query(1500, ge=1, le=5000),
    replace_existing: bool = Query(True),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    return start_crawl(target, replace_existing, force, db)


@app.get("/compliance")
def compliance():
    return {
        "legal_target": check_openmeteo_compliance(),
        "pipeline": [
            "Thu thập: requests gọi Open-Meteo Air Quality API trực tiếp từ Internet",
            "Tiền xử lý: DataLoader dùng Pandas để clean, ép kiểu, lọc AQI và bỏ trùng",
            "Lưu trữ: SQLAlchemy ghi vào bảng air_quality trong MySQL",
        ],
        "no_prebuilt_dataset": True,
        "html_scraping": "Không scrape HTML; hệ thống chỉ dùng Open-Meteo Air Quality API.",
    }


@app.post("/maintenance/nullify-zero-pollutants")
def nullify_zero_pollutants(db: Session = Depends(get_db)):
    updated = 0

    rows = db.query(models.AirQuality).all()
    for row in rows:
        changed = False
        values = [getattr(row, field) for field in POLLUTANT_FIELDS]
        zero_count = sum(1 for value in values if value == 0)
        present_count = sum(1 for value in values if value is not None)

        if row.aqi and zero_count and present_count < len(POLLUTANT_FIELDS):
            for field in POLLUTANT_FIELDS:
                if getattr(row, field) == 0:
                    setattr(row, field, None)
                    changed = True

        if changed:
            updated += 1

    db.commit()
    return {"message": "Zero pollutant cleanup completed", "updated_rows": updated}


@app.get("/map")
def get_map_data(
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    rows = crud.get_latest_city_rows(db, max_age_hours=max_age_hours)
    data_dict = {canonical_city_name(row.city): row for row in rows}

    result = []
    for profile in CITY_PROFILES:
        name = profile["name"]
        row = data_dict.get(name)
        aqi = float(row.aqi) if row and row.aqi is not None else None
        lat = row.latitude if row and row.latitude is not None else profile["coords"][0]
        lon = row.longitude if row and row.longitude is not None else profile["coords"][1]
        result.append(
            {
                "city": name,
                "country": profile.get("country", "Vietnam"),
                "lat": lat,
                "lng": lon,
                "aqi": round(aqi, 2) if aqi is not None else None,
                "level": aqi_level(aqi) if aqi is not None else "Không có dữ liệu mới",
                "time": str(row.observed_time) if row and row.observed_time else None,
                "age_hours": row_age_hours(row),
                "fresh_window_hours": max_age_hours,
                "has_fresh_data": row is not None,
            }
        )
    return result


@app.get("/ranking")
def ranking(
    limit: int = Query(10, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    metric_name: str = Query("aqi", alias="metric"),
    sort_by: Optional[str] = Query(None),
    rank_by: Optional[str] = Query(None),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    country: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    selected_metric = (rank_by or sort_by or metric_name).lower()
    if selected_metric not in RANKING_METRICS:
        raise HTTPException(status_code=400, detail=f"Invalid ranking metric: {selected_metric}")

    cluster_levels = cluster_map(db, max_age_hours=max_age_hours)
    rows = crud.get_latest_city_rows(db, max_age_hours=max_age_hours)
    items = []

    for row in rows:
        if country and (row.country or "").lower() != country.lower():
            continue

        score, score_fields = pollution_score_for_row(row)
        value = score if selected_metric == "pollution_score" else metric_value(row, selected_metric)
        city = canonical_city_name(row.city)
        items.append(
            {
                "city": city,
                "country": row.country,
                "aqi": metric(row.aqi),
                "pm25": metric(row.pm25),
                "pm10": metric(row.pm10),
                "co": metric(row.co),
                "no2": metric(row.no2),
                "so2": metric(row.so2),
                "o3": metric(row.o3),
                "pollution_score": score,
                "pollution_score_fields": score_fields,
                "ranking_metric": selected_metric,
                "ranking_value": value,
                "level": aqi_level(row.aqi),
                "level_code": aqi_level_code(row.aqi),
                "cluster_level": cluster_levels.get(city),
                "time": str(row.observed_time) if row.observed_time else None,
                "age_hours": row_age_hours(row),
                "fresh_window_hours": max_age_hours,
            }
        )

    reverse = order == "desc"
    items.sort(
        key=lambda item: (
            item["ranking_value"] is None,
            item["ranking_value"] if item["ranking_value"] is not None else 0,
        ),
        reverse=reverse,
    )
    if reverse:
        items.sort(key=lambda item: item["ranking_value"] is None)
    return items[:limit]


def metric_value(row, field):
    value = getattr(row, field, None)
    return metric(value)


@app.get("/city")
def get_by_city(
    city: str = Query(...),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    cluster_info = city_cluster_level(db, city, max_age_hours=max_age_hours)
    cluster_level = cluster_info.get("level") if cluster_info else None
    return [
        serialize_row(row, cluster_level=cluster_level)
        for row in crud.get_city_history(db, city, limit=50, max_age_hours=max_age_hours)
    ]


@app.get("/search")
def search(
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_aqi: Optional[float] = Query(None, ge=0, le=500),
    max_aqi: Optional[float] = Query(None, ge=0, le=500),
    level: Optional[str] = Query(None),
    pollutant: Optional[str] = Query(None),
    sort_by: str = Query("time"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    max_age_hours: Optional[int] = Query(None, ge=1, le=720),
    db: Session = Depends(get_db),
):
    pollutant = pollutant.lower() if pollutant else None
    sort_by = sort_by.lower()
    if pollutant and pollutant not in ["aqi", *POLLUTANT_FIELDS]:
        raise HTTPException(status_code=400, detail=f"Invalid pollutant: {pollutant}")
    if sort_by not in SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")

    start_dt = parse_datetime_param(start_date)
    end_dt = parse_datetime_param(end_date, end_of_day=True)
    range_filter = level_range(level)

    query = db.query(models.AirQuality)
    if city:
        filters = [models.AirQuality.city.ilike(f"%{term}%") for term in city_search_terms(city)]
        query = query.filter(or_(*filters))
    if country:
        query = query.filter(models.AirQuality.country.ilike(f"%{country}%"))
    if start_dt:
        query = query.filter(models.AirQuality.observed_time >= start_dt)
    if end_dt:
        query = query.filter(models.AirQuality.observed_time <= end_dt)
    if max_age_hours and not start_dt:
        query = query.filter(models.AirQuality.observed_time >= datetime.now() - timedelta(hours=max_age_hours))
    if min_aqi is not None:
        query = query.filter(models.AirQuality.aqi >= min_aqi)
    if max_aqi is not None:
        query = query.filter(models.AirQuality.aqi <= max_aqi)
    if range_filter:
        query = query.filter(models.AirQuality.aqi >= range_filter[0], models.AirQuality.aqi <= range_filter[1])
    if pollutant:
        query = query.filter(getattr(models.AirQuality, pollutant).isnot(None))

    sort_column = models.AirQuality.observed_time if sort_by == "time" else getattr(models.AirQuality, sort_by)
    direction = desc(sort_column) if order == "desc" else asc(sort_column)
    rows = query.order_by(sort_column.is_(None), direction).limit(limit).all()

    clusters = cluster_map(db, max_age_hours=max_age_hours or CURRENT_DATA_MAX_AGE_HOURS)
    return {
        "count": len(rows),
        "filters": {
            "city": city,
            "country": country,
            "start_date": start_date,
            "end_date": end_date,
            "min_aqi": min_aqi,
            "max_aqi": max_aqi,
            "level": level,
            "pollutant": pollutant,
            "sort_by": sort_by,
            "order": order,
            "limit": limit,
        },
        "results": [
            serialize_row(row, cluster_level=clusters.get(canonical_city_name(row.city)))
            for row in rows
        ],
    }


def compare_latest_rows(row1, row2):
    data1 = serialize_summary(row1)
    data2 = serialize_summary(row2)
    metrics = ["aqi", *POLLUTANT_FIELDS]
    better_at = {}
    city1_wins = 0
    city2_wins = 0

    for field in metrics:
        val1 = data1[field]
        val2 = data2[field]
        if val1 is None and val2 is None:
            better_at[field] = None
        elif val2 is None or (val1 is not None and val1 <= val2):
            better_at[field] = data1["city"]
            city1_wins += 1
        else:
            better_at[field] = data2["city"]
            city2_wins += 1

    if city1_wins > city2_wins:
        overall = f"{data1['city']} tốt hơn ở {city1_wins}/{len(metrics)} chỉ số có thể so sánh"
    elif city2_wins > city1_wins:
        overall = f"{data2['city']} tốt hơn ở {city2_wins}/{len(metrics)} chỉ số có thể so sánh"
    else:
        overall = "Hai thành phố khá cân bằng theo dữ liệu mới nhất"

    return {
        "city1": data1,
        "city2": data2,
        "difference": {
            field: round(abs(float(data1[field]) - float(data2[field])), 2)
            if data1[field] is not None and data2[field] is not None
            else None
            for field in metrics
        },
        "better_at": better_at,
        "city1_wins": city1_wins,
        "city2_wins": city2_wins,
        "overall_recommendation": overall,
        "note": "Giá trị thấp hơn thường tốt hơn đối với AQI, PM2.5, PM10, CO, NO2, SO2, O3.",
    }


@app.get("/compare")
def compare(
    city1: str = Query(...),
    city2: str = Query(...),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    rows = crud.get_latest_city_rows(db, max_age_hours=max_age_hours)
    data = {canonical_city_name(row.city): row for row in rows}

    row1 = data.get(canonical_city_name(city1))
    row2 = data.get(canonical_city_name(city2))
    if not row1:
        raise HTTPException(status_code=404, detail=f"City not found: {city1}")
    if not row2:
        raise HTTPException(status_code=404, detail=f"City not found: {city2}")

    return compare_latest_rows(row1, row2)


@app.get("/compare-history")
def compare_history(
    city1: str = Query(...),
    city2: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    max_age_hours: int = Query(168, ge=1, le=2160),
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    start_dt = parse_datetime_param(start_date) or (datetime.now() - timedelta(hours=max_age_hours))
    end_dt = parse_datetime_param(end_date, end_of_day=True) or datetime.now()

    rows1 = crud.get_city_history_between(db, city1, start_dt, end_dt, limit=limit)
    rows2 = crud.get_city_history_between(db, city2, start_dt, end_dt, limit=limit)
    if not rows1:
        raise HTTPException(status_code=404, detail=f"No history found for {city1}")
    if not rows2:
        raise HTTPException(status_code=404, detail=f"No history found for {city2}")

    latest_payload = compare_latest_rows(rows1[0], rows2[0])
    avg1 = {field: average_present(rows1, field) for field in ["aqi", *POLLUTANT_FIELDS]}
    avg2 = {field: average_present(rows2, field) for field in ["aqi", *POLLUTANT_FIELDS]}
    avg_aqi1 = avg1["aqi"]
    avg_aqi2 = avg2["aqi"]

    if avg_aqi1 is not None and avg_aqi2 is not None:
        better_city = canonical_city_name(city1) if avg_aqi1 <= avg_aqi2 else canonical_city_name(city2)
        recommendation = f"{better_city} có AQI trung bình thấp hơn trong khoảng thời gian này."
    else:
        recommendation = "Chưa đủ dữ liệu AQI trung bình để kết luận."

    def series(rows):
        ordered = list(reversed(rows))
        return [
            {
                "time": str(row.observed_time),
                "aqi": metric(row.aqi),
                "pm25": metric(row.pm25),
                "pm10": metric(row.pm10),
            }
            for row in ordered
        ]

    return {
        "city1": canonical_city_name(city1),
        "city2": canonical_city_name(city2),
        "start_date": str(start_dt),
        "end_date": str(end_dt),
        "latest": latest_payload,
        "averages": {
            "city1": {"city": canonical_city_name(city1), **avg1},
            "city2": {"city": canonical_city_name(city2), **avg2},
        },
        "series": {
            "city1": series(rows1),
            "city2": series(rows2),
        },
        "recommendation": recommendation,
    }


@app.get("/summary")
def summary(
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    latest = crud.get_latest_city_rows(db, max_age_hours=max_age_hours)
    total_records = crud.count_records(db)
    fresh_records = crud.count_records(db, max_age_hours=max_age_hours)

    if not latest:
        return {
            "message": "No fresh data available",
            "tracked_city_count": len(CITY_PROFILES),
            "count_city": 0,
            "total_record_count": total_records,
            "fresh_record_count": fresh_records,
            "fresh_window_hours": max_age_hours,
            "avg_aqi": None,
            "max_aqi": None,
            "avg_pm25": None,
            "avg_pm10": None,
            "avg_so2": None,
            "best_places": [],
            "worst_places": [],
        }

    avg_aqi = average_present(latest, "aqi")
    max_aqi = max(float(row.aqi) for row in latest if row.aqi is not None)
    best = sorted(latest, key=lambda row: float(row.aqi) if row.aqi is not None else float("inf"))[:5]
    worst = sorted(latest, key=lambda row: float(row.aqi) if row.aqi is not None else float("-inf"), reverse=True)[:5]

    return {
        "tracked_city_count": len(CITY_PROFILES),
        "count_city": len(latest),
        "total_record_count": total_records,
        "fresh_record_count": fresh_records,
        "fresh_window_hours": max_age_hours,
        "avg_aqi": avg_aqi,
        "max_aqi": round(max_aqi, 2),
        "avg_pm25": average_present(latest, "pm25"),
        "avg_pm10": average_present(latest, "pm10"),
        "avg_so2": average_present(latest, "so2"),
        "best_places": [
            {"city": canonical_city_name(row.city), "aqi": metric(row.aqi)}
            for row in best
        ],
        "worst_places": [
            {"city": canonical_city_name(row.city), "aqi": metric(row.aqi)}
            for row in worst
        ],
    }


@app.get("/chart")
def get_chart(
    city: str,
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    filters = [models.AirQuality.city.ilike(f"%{term}%") for term in city_search_terms(city)]
    rows = (
        db.query(models.AirQuality)
        .filter(or_(*filters))
        .filter(models.AirQuality.observed_time >= datetime.now() - timedelta(hours=max_age_hours))
        .order_by(models.AirQuality.observed_time.desc())
        .limit(50)
        .all()
    )
    rows = distinct_time_series(rows)[-24:]
    return {
        "labels": [str(row.observed_time) for row in rows],
        "aqi": [metric(row.aqi) for row in rows],
    }


@app.get("/chart_multi")
def get_chart_multi(
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    active_cities = [
        row.city
        for row in sorted(
            crud.get_latest_city_rows(db, max_age_hours=max_age_hours),
            key=lambda item: float(item.aqi) if item.aqi is not None else 0,
            reverse=True,
        )[:6]
    ]
    result = {}

    for city in active_cities:
        terms = city_search_terms(city)
        rows = (
            db.query(models.AirQuality)
            .filter(or_(*[models.AirQuality.city.ilike(f"%{term}%") for term in terms]))
            .filter(models.AirQuality.observed_time >= cutoff)
            .order_by(models.AirQuality.observed_time.desc())
            .limit(40)
            .all()
        )
        rows = distinct_time_series(rows)[-24:]
        result[canonical_city_name(city)] = {
            "labels": [str(row.observed_time) for row in rows],
            "aqi": [metric(row.aqi) for row in rows],
        }

    return result


@app.get("/cluster")
def cluster(
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    return cluster_data(db, max_age_hours=max_age_hours)


@app.get("/predict")
def predict(
    city: Optional[str] = Query(None),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    return predict_aqi(db, city=city, max_age_hours=max_age_hours)


@app.get("/city-insight")
def city_insight(
    city: str = Query(...),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    history_limit: int = Query(24, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = crud.get_city_history(db, city, limit=history_limit, max_age_hours=max_age_hours)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No fresh data found for {city}")

    cluster_info = city_cluster_level(db, city, max_age_hours=max_age_hours)
    cluster_level = cluster_info.get("level") if cluster_info else None
    prediction = predict_aqi(db, city=city, max_age_hours=max_age_hours)
    latest = serialize_row(rows[0], cluster_level=cluster_level)
    aqi = latest["aqi"]

    if aqi is None:
        comment = "Chưa có AQI mới để nhận xét."
    elif aqi <= 50:
        comment = "Không khí đang ở mức tốt theo AQI mới nhất."
    elif aqi <= 100:
        comment = "Không khí ở mức trung bình, nên tiếp tục theo dõi."
    else:
        comment = "Không khí đang xấu hơn, nên hạn chế hoạt động ngoài trời nếu nhạy cảm."

    return {
        "city": canonical_city_name(city),
        "latest": latest,
        "history": [serialize_row(row, cluster_level=cluster_level) for row in rows],
        "cluster": cluster_info,
        "cluster_level": cluster_level,
        "prediction": prediction,
        "comment": comment,
        "note": "AQI dự đoán chỉ là kết quả tham khảo từ Linear Regression.",
    }


def run_auto_crawl_once():
    if not CRAWL_LOCK.acquire(blocking=False):
        return {
            "error": "A crawl job is already running. Auto crawl skipped.",
            "raw_count": 0,
            "clean_count": 0,
            "archived_count": 0,
            "deleted_count": 0,
            "inserted_count": 0,
        }

    db = SessionLocal()
    try:
        AUTO_CRAWL_STATUS["running"] = True
        AUTO_CRAWL_STATUS["last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        AUTO_CRAWL_STATUS["last_error"] = None
        result = run_crawl_job(db, target=AUTO_CRAWL_TARGET, replace_existing=True)
        AUTO_CRAWL_STATUS["last_result"] = result
        if result.get("error"):
            AUTO_CRAWL_STATUS["last_error"] = result["error"]
        print(f"[AUTO CRAWL] {result}")
        return result
    except Exception as exc:
        AUTO_CRAWL_STATUS["last_error"] = str(exc)
        print("Auto crawl error:", exc)
        return {
            "error": str(exc),
            "raw_count": 0,
            "clean_count": 0,
            "deleted_count": 0,
            "inserted_count": 0,
            "replace_existing": True,
        }
    finally:
        AUTO_CRAWL_STATUS["running"] = False
        db.close()
        CRAWL_LOCK.release()


def auto_crawl_loop():
    while not AUTO_CRAWL_STOP.is_set():
        if AUTO_CRAWL_STATUS["enabled"]:
            run_auto_crawl_once()
        AUTO_CRAWL_STOP.wait(AUTO_CRAWL_INTERVAL_SECONDS)


def ensure_auto_crawl_thread():
    global AUTO_CRAWL_THREAD
    if AUTO_CRAWL_THREAD and AUTO_CRAWL_THREAD.is_alive():
        return
    AUTO_CRAWL_STOP.clear()
    AUTO_CRAWL_THREAD = threading.Thread(target=auto_crawl_loop, daemon=True)
    AUTO_CRAWL_THREAD.start()


@app.get("/auto-start")
def auto_start(interval_seconds: int = Query(AUTO_CRAWL_INTERVAL_SECONDS, ge=300, le=86400)):
    global AUTO_CRAWL_INTERVAL_SECONDS
    AUTO_CRAWL_STATUS["enabled"] = True
    AUTO_CRAWL_STATUS["interval_seconds"] = interval_seconds
    AUTO_CRAWL_INTERVAL_SECONDS = interval_seconds
    ensure_auto_crawl_thread()
    return {"message": "Auto crawl started", **AUTO_CRAWL_STATUS}


@app.get("/auto-stop")
def auto_stop():
    AUTO_CRAWL_STATUS["enabled"] = False
    return {"message": "Auto crawl stopped", **AUTO_CRAWL_STATUS}


@app.get("/auto-status")
def auto_status():
    return AUTO_CRAWL_STATUS


@app.get("/auto-once")
def auto_once():
    return run_auto_crawl_once()


@app.on_event("startup")
def start_auto_crawl_on_startup():
    if AUTO_CRAWL_ENABLED:
        ensure_auto_crawl_thread()
