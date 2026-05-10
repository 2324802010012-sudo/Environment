import os
import threading
import time
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.orm import Session

import crud
import models
from database import SessionLocal, engine
from services.cities import CITY_PROFILES, canonical_city_name, city_search_terms
from services.crawler import fetch_data
from services.data_loader import DataLoader
from services.ml import cluster_data
from services.predict import predict_aqi


models.Base.metadata.create_all(bind=engine)

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
AUTO_CRAWL_TARGET = int(os.getenv("AUTO_CRAWL_TARGET", "1000"))
AUTO_CRAWL_ROUNDS = int(os.getenv("AUTO_CRAWL_ROUNDS", "12"))
AUTO_CRAWL_STOP = threading.Event()
AUTO_CRAWL_THREAD = None
AUTO_CRAWL_STATUS = {
    "enabled": AUTO_CRAWL_ENABLED,
    "running": False,
    "last_run_at": None,
    "last_result": None,
    "last_error": None,
    "interval_seconds": AUTO_CRAWL_INTERVAL_SECONDS,
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
    aqi = float(row.aqi or 0)
    return {
        "city": canonical_city_name(row.city),
        "time": str(row.time),
        "aqi": round(aqi, 2),
        "pm25": round(float(row.pm25 or 0), 2),
        "pm10": round(float(row.pm10 or 0), 2),
        "co": round(float(row.co or 0), 2),
        "no2": round(float(row.no2 or 0), 2),
        "o3": round(float(row.o3 or 0), 2),
        "level": aqi_level(aqi),
    }


def serialize_summary(row):
    aqi = float(row.aqi or 0)
    return {
        "city": canonical_city_name(row.city),
        "pm25": round(float(row.pm25 or 0), 2),
        "pm10": round(float(row.pm10 or 0), 2),
        "co": round(float(row.co or 0), 2),
        "no2": round(float(row.no2 or 0), 2),
        "o3": round(float(row.o3 or 0), 2),
        "aqi": round(aqi, 2),
        "level": aqi_level(aqi),
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


def run_crawl_job(
    db,
    target=1000,
    max_rounds=12,
    use_html=False,
    max_terms=5,
    max_stations=15,
):
    raw_data = fetch_data(
        target_records=target,
        max_rounds=max_rounds,
        use_html_fallback=use_html,
        max_terms=max_terms,
        max_stations=max_stations,
    )
    clean_data, stats = DataLoader().load_and_process(raw_data)

    if not clean_data:
        return {
            "error": "No valid data fetched",
            "raw_count": len(raw_data),
            "clean_count": stats["valid_count"],
            "inserted_count": 0,
        }

    inserted = crud.insert_data(db, clean_data)
    return {
        "message": "Data inserted",
        "raw_count": len(raw_data),
        "clean_count": stats["valid_count"],
        "inserted_count": inserted,
    }


@app.get("/")
def root():
    return {"message": "Air Quality API running"}


@app.get("/cities")
def cities():
    return [
        {"name": profile["name"], "slug": profile["slug"], "coords": profile["coords"]}
        for profile in CITY_PROFILES
    ]


@app.get("/crawl")
def crawl(
    target: int = Query(1000, ge=1, le=5000),
    max_rounds: int = Query(12, ge=1, le=50),
    use_html: bool = Query(False),
    max_terms: int = Query(5, ge=1, le=8),
    max_stations: int = Query(15, ge=1, le=30),
    db: Session = Depends(get_db),
):
    if not CRAWL_LOCK.acquire(blocking=False):
        return {
            "error": "A crawl job is already running. Please wait for it to finish.",
            "raw_count": 0,
            "clean_count": 0,
            "inserted_count": 0,
        }

    try:
        try:
            return run_crawl_job(
                db,
                target=target,
                max_rounds=max_rounds,
                use_html=use_html,
                max_terms=max_terms,
                max_stations=max_stations,
            )
        except Exception as exc:
            return {
                "error": f"Crawl failed: {exc}",
                "raw_count": 0,
                "clean_count": 0,
                "inserted_count": 0,
            }
    finally:
        CRAWL_LOCK.release()


def run_auto_crawl_once():
    if not CRAWL_LOCK.acquire(blocking=False):
        return {
            "error": "A crawl job is already running. Auto crawl skipped.",
            "raw_count": 0,
            "clean_count": 0,
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
            max_rounds=AUTO_CRAWL_ROUNDS,
            max_terms=5,
            max_stations=15,
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
            "inserted_count": 0,
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


@app.get("/map")
def get_map_data(db: Session = Depends(get_db)):
    rows = crud.get_all_latest_by_city(db, limit=200)
    data_dict = {canonical_city_name(row.city): row for row in rows}

    result = []
    for profile in CITY_PROFILES:
        name = profile["name"]
        row = data_dict.get(name)
        aqi = float(row.aqi or 0) if row else 0
        result.append(
            {
                "city": name,
                "lat": profile["coords"][0],
                "lng": profile["coords"][1],
                "aqi": round(aqi, 2),
                "level": aqi_level(aqi),
            }
        )
    return result


@app.get("/ranking")
def ranking(
    limit: int = Query(10, ge=1, le=50),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    rows = crud.get_unique_latest(db, limit=200, sort_desc=(order == "desc"))
    items = []
    seen = set()

    for row in rows:
        city = canonical_city_name(row.city)
        if city in seen:
            continue
        seen.add(city)
        aqi = float(row.aqi or 0)
        items.append({"city": city, "aqi": round(aqi, 2), "level": aqi_level(aqi)})
        if len(items) >= limit:
            break

    return items


@app.get("/city")
def get_by_city(city: str = Query(...), db: Session = Depends(get_db)):
    items = []
    seen = set()
    for row in crud.get_city_history(db, city, limit=50):
        key = (canonical_city_name(row.city), str(row.time), row.station)
        if key in seen:
            continue
        seen.add(key)
        items.append(serialize_row(row))
    return items


@app.get("/search")
def search(city: str = Query(...), db: Session = Depends(get_db)):
    return get_by_city(city=city, db=db)


@app.get("/compare")
def compare(city1: str = Query(...), city2: str = Query(...), db: Session = Depends(get_db)):
    stats1 = crud.get_city_aggregate(db, city1)
    stats2 = crud.get_city_aggregate(db, city2)

    if not stats1:
        raise HTTPException(status_code=404, detail=f"City not found: {city1}")
    if not stats2:
        raise HTTPException(status_code=404, detail=f"City not found: {city2}")

    data1 = serialize_summary(stats1[0])
    data2 = serialize_summary(stats2[0])

    return {
        "city1": data1,
        "city2": data2,
        "difference": {
            key: round(abs(float(data1[key] or 0) - float(data2[key] or 0)), 2)
            for key in ["aqi", "pm25", "pm10", "co", "no2", "o3"]
        },
        "better_city": data1["city"] if data1["aqi"] <= data2["aqi"] else data2["city"],
    }


@app.get("/summary")
def summary(db: Session = Depends(get_db)):
    raw_latest = crud.get_all_latest_by_city(db, limit=200, sort_desc=False)
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
        return {"message": "No data available"}

    avg_aqi = sum(float(row.aqi or 0) for row in latest) / len(latest)
    avg_pm25 = sum(float(row.pm25 or 0) for row in latest) / len(latest)
    avg_pm10 = sum(float(row.pm10 or 0) for row in latest) / len(latest)
    best = sorted(latest, key=lambda row: float(row.aqi or 0))[:5]
    worst = sorted(latest, key=lambda row: float(row.aqi or 0), reverse=True)[:5]

    return {
        "count_city": len(latest),
        "avg_aqi": round(avg_aqi, 2),
        "avg_pm25": round(avg_pm25, 2),
        "avg_pm10": round(avg_pm10, 2),
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
def get_chart(city: str, db: Session = Depends(get_db)):
    filters = [models.AirQuality.city.ilike(f"%{term}%") for term in city_search_terms(city)]
    rows = (
        db.query(models.AirQuality)
        .filter(or_(*filters))
        .order_by(models.AirQuality.time.desc())
        .limit(20)
        .all()
    )
    rows = distinct_time_series(rows)[:10]
    return {"labels": [str(row.time) for row in rows], "aqi": [row.aqi for row in rows]}


@app.get("/chart_multi")
def get_chart_multi(db: Session = Depends(get_db)):
    time_rows = (
        db.query(models.AirQuality.time)
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
            .order_by(models.AirQuality.time.desc())
            .limit(20)
            .all()
        )
        time_map = {str(row.time): row.aqi for row in rows}
        result[profile["name"]] = {"labels": labels, "aqi": [time_map.get(label) for label in labels]}

    return result


@app.get("/cluster")
def cluster(db: Session = Depends(get_db)):
    return cluster_data(db)


@app.get("/predict")
def predict(city: str = Query(None), db: Session = Depends(get_db)):
    return predict_aqi(db, city=city)


@app.on_event("startup")
def start_auto_crawl_on_startup():
    if AUTO_CRAWL_ENABLED:
        ensure_auto_crawl_thread()
