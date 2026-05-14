import os
import threading
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy import or_
from sqlalchemy.orm import Session

try:
    from . import crud
    from . import models
    from .database import SessionLocal, engine
    from .services.cities import CITY_PROFILES, canonical_city_name, city_search_terms
    from .services.crawler_openmeteo import fetch_data_openmeteo, GLOBAL_CITIES
    from .services.data_loader import DataLoader
    from .services.ml import cluster_data
    from .services.predict import predict_aqi
    from .services.robots_checker import check_openmeteo_compliance
except ImportError:
    import crud
    import models
    from database import SessionLocal, engine
    from services.cities import CITY_PROFILES, canonical_city_name, city_search_terms
    from services.crawler_openmeteo import fetch_data_openmeteo, GLOBAL_CITIES
    from services.data_loader import DataLoader
    from services.ml import cluster_data
    from services.predict import predict_aqi
    from services.robots_checker import check_openmeteo_compliance


models.Base.metadata.create_all(bind=engine)


def ensure_air_quality_schema():
    inspector = inspect(engine)
    existing_columns = {
        column["name"]
        for column in inspector.get_columns(models.AirQuality.__tablename__)
    }
    migrations = []

    if "country" not in existing_columns:
        migrations.append("ALTER TABLE air_quality ADD COLUMN country VARCHAR(100) DEFAULT 'Vietnam'")
    if "so2" not in existing_columns:
        migrations.append("ALTER TABLE air_quality ADD COLUMN so2 FLOAT NULL")

    if not migrations:
        return

    with engine.begin() as connection:
        for statement in migrations:
            connection.execute(text(statement))


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
AUTO_CRAWL_ENABLED = os.getenv("AUTO_CRAWL_ENABLED", "true").lower() == "true"
AUTO_CRAWL_INTERVAL_SECONDS = int(os.getenv("AUTO_CRAWL_INTERVAL_SECONDS", "900"))
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def aqi_level(aqi):
    aqi = float(aqi or 0)
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


def serialize_row(row):
    aqi = float(row.aqi) if row.aqi is not None else 0
    def metric(value):
        return round(float(value), 2) if value is not None else None

    return {
        "city": canonical_city_name(row.city),
        "time": str(row.time),
        "aqi": round(aqi, 2),
        "pm25": metric(row.pm25),
        "pm10": metric(row.pm10),
        "co": metric(row.co),
        "no2": metric(row.no2),
        "so2": metric(row.so2),
        "o3": metric(row.o3),
        "level": aqi_level(aqi),
        **data_quality(row),
    }


def serialize_summary(row):
    aqi = float(row.aqi) if row.aqi is not None else 0
    def metric(value):
        return round(float(value), 2) if value is not None else None

    return {
        "city": canonical_city_name(row.city),
        "pm25": metric(row.pm25),
        "pm10": metric(row.pm10),
        "co": metric(row.co),
        "no2": metric(row.no2),
        "so2": metric(row.so2),
        "o3": metric(row.o3),
        "aqi": round(aqi, 2),
        "level": aqi_level(aqi),
        **data_quality(row),
    }


def distinct_time_series(rows):
    unique = []
    seen = set()
    for row in rows:
        key = str(row.time)
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


def data_quality(row):
    pollutant_fields = ["pm25", "pm10", "co", "no2", "so2", "o3"]
    present = [field for field in pollutant_fields if getattr(row, field) is not None]
    if len(present) == len(pollutant_fields):
        quality = "complete"
    elif present:
        quality = "partial"
    else:
        quality = "aqi_only"

    return {
        "quality": quality,
        "available_pollutants": present,
        "missing_pollutants": [field for field in pollutant_fields if field not in present],
    }


def row_age_hours(row):
    if not row or not row.time:
        return None
    return round(max(0, (datetime.now() - row.time).total_seconds() / 3600), 2)


def manual_crawl_wait_seconds(force=False):
    if force or LAST_MANUAL_CRAWL_AT is None:
        return 0
    elapsed = (datetime.now() - LAST_MANUAL_CRAWL_AT).total_seconds()
    return max(0, int(CRAWL_MIN_INTERVAL_SECONDS - elapsed))


def run_crawl_job(
    db,
    target=1500,
    replace_existing=True,
):
    source = "open-meteo"
    raw_data = fetch_data_openmeteo(target_records=target, cities_list=GLOBAL_CITIES)
    clean_data, stats = DataLoader().load_and_process(raw_data)

    if not clean_data:
        return {
            "error": "No valid data fetched",
            "raw_count": len(raw_data),
            "clean_count": stats["valid_count"],
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
        for alias in profile.get("aliases", []):
            if canonical_city_name(alias) == canonical:
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


@app.get("/crawl")
def crawl(
    target: int = Query(1500, ge=1, le=5000),
    replace_existing: bool = Query(True),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
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
        }

    try:
        try:
            LAST_MANUAL_CRAWL_AT = datetime.now()
            return run_crawl_job(
                db,
                target=target,
                replace_existing=replace_existing,
            )
        except Exception as exc:
            return {
                "error": f"Crawl failed: {exc}",
                "raw_count": 0,
                "clean_count": 0,
                "archived_count": 0,
                "deleted_count": 0,
                "inserted_count": 0,
            }
    finally:
        CRAWL_LOCK.release()


@app.get("/crawl-openmeteo")
def crawl_openmeteo(
    target: int = Query(1500, ge=1, le=5000),
    replace_existing: bool = Query(True),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Crawl from Open-Meteo Air Quality API.
    
    Advantages:
    - No API key required
    - Global cities support
    - All indicators: AQI, PM2.5, PM10, CO, NO2, SO2, O3
    - No rate limiting
    
    Query params:
    - target: number of records to fetch (default 1500)
    
    Returns:
    - raw_count: records fetched from API
    - clean_count: valid records after processing
    - inserted_count: new records saved to database
    """
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
        }

    try:
        LAST_MANUAL_CRAWL_AT = datetime.now()
        raw_data = fetch_data_openmeteo(target_records=target, cities_list=GLOBAL_CITIES)
        clean_data, stats = DataLoader().load_and_process(raw_data)
        
        if not clean_data:
            return {
                "error": "No valid data fetched",
                "raw_count": len(raw_data),
                "clean_count": stats["valid_count"],
                "archived_count": 0,
                "deleted_count": 0,
                "inserted_count": 0,
                "replace_existing": replace_existing,
                "source": "open-meteo",
            }
        
        deleted = 0
        archived = crud.archive_data(db, clean_data)
        if replace_existing:
            deleted = crud.clear_data(db)

        inserted = crud.insert_data(db, clean_data)
        return {
            "message": "Data refreshed from Open-Meteo" if replace_existing else "Data inserted from Open-Meteo",
            "raw_count": len(raw_data),
            "clean_count": stats["valid_count"],
            "archived_count": archived,
            "deleted_count": deleted,
            "inserted_count": inserted,
            "replace_existing": replace_existing,
            "source": "open-meteo",
        }
    except Exception as exc:
        return {
            "error": f"OpenMeteo crawl failed: {exc}",
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


@app.get("/compliance")
def compliance():
    return {
        "legal_target": check_openmeteo_compliance(),
        "pipeline": [
            "Thu thap: requests goi Open-Meteo Air Quality API truc tiep tu Internet",
            "Tien xu ly: DataLoader dung Pandas de clean, ep kieu, loc AQI va bo trung",
            "Luu tru: SQLAlchemy ghi vao bang air_quality trong MySQL",
        ],
        "no_prebuilt_dataset": True,
        "html_scraping": "Khong scrape HTML; he thong chi dung Open-Meteo Air Quality API.",
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
        result = run_crawl_job(
            db,
            target=AUTO_CRAWL_TARGET,
            replace_existing=True,
        )
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
            "archived_count": 0,
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
def auto_start(
    interval_seconds: int = Query(AUTO_CRAWL_INTERVAL_SECONDS, ge=300, le=86400),
):
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
    result = run_auto_crawl_once()
    return result


@app.post("/maintenance/nullify-zero-pollutants")
def nullify_zero_pollutants(db: Session = Depends(get_db)):
    pollutant_fields = ["pm25", "pm10", "co", "no2", "so2", "o3"]
    updated = 0

    rows = db.query(models.AirQuality).all()
    for row in rows:
        changed = False
        values = [getattr(row, field) for field in pollutant_fields]
        zero_count = sum(1 for value in values if value == 0)
        present_count = sum(1 for value in values if value is not None)

        if row.aqi and zero_count and present_count < len(pollutant_fields):
            for field in pollutant_fields:
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
    rows = crud.get_all_latest_by_city(db, limit=200, max_age_hours=max_age_hours)
    data_dict = {canonical_city_name(row.city): row for row in rows}

    result = []
    for profile in CITY_PROFILES:
        name = profile["name"]
        row = data_dict.get(name)
        aqi = float(row.aqi) if row and row.aqi is not None else None
        result.append(
            {
                "city": name,
                "lat": profile["coords"][0],
                "lng": profile["coords"][1],
                "aqi": round(aqi, 2) if aqi is not None else None,
                "level": aqi_level(aqi) if aqi is not None else "Không có dữ liệu mới",
                "time": str(row.time) if row else None,
                "age_hours": row_age_hours(row),
                "fresh_window_hours": max_age_hours,
                "has_fresh_data": row is not None,
            }
        )
    return result


@app.get("/ranking")
def ranking(
    limit: int = Query(10, ge=1, le=50),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    country: str = Query(None),
    db: Session = Depends(get_db),
):
    rows = crud.get_unique_latest(
        db,
        limit=200,
        sort_desc=(order == "desc"),
        max_age_hours=max_age_hours,
    )
    items = []
    seen = set()

    for row in rows:
        if country and (row.country or "").lower() != country.lower():
            continue

        city = canonical_city_name(row.city)
        if city in seen:
            continue
        seen.add(city)
        aqi = float(row.aqi or 0)
        items.append({
            "city": city,
            "aqi": round(aqi, 2),
            "level": aqi_level(aqi),
            "time": str(row.time),
            "age_hours": row_age_hours(row),
            "fresh_window_hours": max_age_hours,
        })
        if len(items) >= limit:
            break

    return items


@app.get("/city")
def get_by_city(
    city: str = Query(...),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    items = []
    seen = set()
    for row in crud.get_city_history(db, city, limit=50, max_age_hours=max_age_hours):
        key = (canonical_city_name(row.city), str(row.time), row.station)
        if key in seen:
            continue
        seen.add(key)
        items.append(serialize_row(row))
    return items


@app.get("/search")
def search(
    city: str = Query(...),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    return get_by_city(city=city, max_age_hours=max_age_hours, db=db)


@app.get("/compare")
def compare(
    city1: str = Query(...),
    city2: str = Query(...),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):

    rows = crud.get_unique_latest(db, limit=200, max_age_hours=max_age_hours)

    data = {canonical_city_name(r.city): r for r in rows}

    row1 = data.get(canonical_city_name(city1))
    row2 = data.get(canonical_city_name(city2))

    if not row1:
        raise HTTPException(status_code=404, detail=f"City not found: {city1}")
    if not row2:
        raise HTTPException(status_code=404, detail=f"City not found: {city2}")

    data1 = serialize_summary(row1)
    data2 = serialize_summary(row2)

    return {
        "city1": data1,
        "city2": data2,
        "difference": {
            key: (
                round(abs(float(data1[key]) - float(data2[key])), 2)
                if data1[key] is not None and data2[key] is not None
                else None
            )
            for key in ["aqi", "pm25", "pm10", "co", "no2", "so2", "o3"]
        },
        "better_city": data1["city"] if data1["aqi"] <= data2["aqi"] else data2["city"],
    }

@app.get("/summary")
def summary(
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    raw_latest = crud.get_all_latest_by_city(
        db,
        limit=200,
        sort_desc=False,
        max_age_hours=max_age_hours,
    )
    latest = []
    seen = set()

    for row in raw_latest:
        city = canonical_city_name(row.city)
        if city in seen:
            continue
        row.city = city
        seen.add(city)
        latest.append(row)

    if not latest:
        return {
            "message": "No fresh data available",
            "tracked_city_count": len(CITY_PROFILES),
            "count_city": 0,
            "fresh_window_hours": max_age_hours,
            "avg_aqi": None,
            "max_aqi": None,
            "avg_pm25": None,
            "avg_pm10": None,
            "avg_so2": None,
            "best_places": [],
            "worst_places": [],
        }

    avg_aqi = average_present(latest, "aqi") or 0
    avg_pm25 = average_present(latest, "pm25")
    avg_pm10 = average_present(latest, "pm10")
    avg_so2 = average_present(latest, "so2")
    max_aqi = max(float(row.aqi or 0) for row in latest)
    best = sorted(latest, key=lambda row: float(row.aqi or 0))[:5]
    worst = sorted(latest, key=lambda row: float(row.aqi or 0), reverse=True)[:5]

    return {
        "tracked_city_count": len(CITY_PROFILES),
        "count_city": len(latest),
        "fresh_window_hours": max_age_hours,
        "avg_aqi": round(avg_aqi, 2),
        "max_aqi": round(max_aqi, 2), 
        "avg_pm25": avg_pm25,
        "avg_pm10": avg_pm10,
        "avg_so2": avg_so2,
        "best_places": [
            {"city": canonical_city_name(row.city), "aqi": round(float(row.aqi or 0), 2)}
            for row in best
        ],
        "worst_places": [
            {"city": canonical_city_name(row.city), "aqi": round(float(row.aqi or 0), 2)}
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
        .filter(models.AirQuality.time >= datetime.now() - timedelta(hours=max_age_hours))
        .order_by(models.AirQuality.time.desc())
        .limit(20)
        .all()
    )
    rows = distinct_time_series(rows)[:10]
    return {"labels": [str(row.time) for row in rows], "aqi": [row.aqi for row in rows]}


@app.get("/chart_multi")
def get_chart_multi(
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    time_rows = (
        db.query(models.AirQuality.time)
        .filter(models.AirQuality.time >= cutoff)
        .group_by(models.AirQuality.time)
        .order_by(models.AirQuality.time.desc())
        .limit(10)
        .all()
    )
    labels = [str(row.time) for row in reversed(time_rows)]
    result = {}

    for profile in CITY_PROFILES:
        terms = city_search_terms(profile["name"])
        rows = (
            db.query(models.AirQuality)
            .filter(or_(*[models.AirQuality.city.ilike(f"%{term}%") for term in terms]))
            .filter(models.AirQuality.time >= cutoff)
            .order_by(models.AirQuality.time.desc())
            .limit(20)
            .all()
        )
        time_map = {str(row.time): row.aqi for row in rows}
        result[profile["name"]] = {"labels": labels, "aqi": [time_map.get(label) for label in labels]}

    return result


@app.get("/cluster")
def cluster(
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    return cluster_data(db, max_age_hours=max_age_hours)


@app.get("/predict")
def predict(
    city: str = Query(None),
    max_age_hours: int = Query(CURRENT_DATA_MAX_AGE_HOURS, ge=1, le=720),
    db: Session = Depends(get_db),
):
    return predict_aqi(db, city=city, max_age_hours=max_age_hours)


@app.on_event("startup")
def start_auto_crawl_on_startup():
    if AUTO_CRAWL_ENABLED:
        ensure_auto_crawl_thread()
