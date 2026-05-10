import threading
import time

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup
import requests
import crud
import models
from database import SessionLocal, engine
from services.cities import CITY_PROFILES, canonical_city_name, city_search_terms
from services.crawler import fetch_data
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def aqi_level(aqi):
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
    return {
        "city": row.city,
        "pm25": round(float(row.pm25 or 0), 2),
        "pm10": round(float(row.pm10 or 0), 2),
        "co": round(float(row.co or 0), 2),
        "no2": round(float(row.no2 or 0), 2),
        "o3": round(float(row.o3 or 0), 2),
        "aqi": round(float(row.aqi or 0), 2),
        "level": aqi_level(float(row.aqi or 0)),
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


@app.get("/")
def root():
    return {"message": "Air Quality API running"}


@app.get("/cities")
def cities():
    return [
        {"name": profile["name"], "slug": profile["slug"], "coords": profile["coords"]}
        for profile in CITY_PROFILES
    ]
@app.get("/map")
def get_map_data(db: Session = Depends(get_db)):

    # lấy dữ liệu mới nhất mỗi city
    rows = crud.get_all_latest_by_city(db, limit=200)

    # convert thành dict
    data_dict = {}
    for r in rows:
        city = canonical_city_name(r.city)
        data_dict[city] = r

    result = []

    for profile in CITY_PROFILES:
        name = profile["name"]
        coords = profile["coords"]

        if name in data_dict:
            r = data_dict[name]
            aqi = float(r.aqi or 0)
        else:
            aqi = 0  # 👉 không có data

        result.append({
            "city": name,
            "lat": coords[0],
            "lng": coords[1],
            "aqi": aqi,
            "level": aqi_level(aqi)
        })

    return result

@app.get("/crawl")
def crawl(db: Session = Depends(get_db)):
    data = fetch_data()
    if not data:
        return {"error": "No data fetched"}

    crud.insert_data(db, data)
    return {"message": "Data inserted", "count": len(data)}

import threading

@app.get("/auto-fast")
def auto_fast():
    threading.Thread(target=run_auto_crawl, daemon=True).start()
    return {"message": "FAST crawl started 🚀"}


def run_auto_crawl():
    db = SessionLocal()
    total = 0

    try:
        for i in range(50):   # 🔥 chỉ cần 50 vòng là đủ 1000+
            data = fetch_data()
            if data:
                crud.insert_data(db, data)
                total += len(data)

            print(f"[ROUND {i+1}] inserted: {len(data)}")

    except Exception as e:
        print("Auto crawl error:", e)

    finally:
        db.close()

    print(f"TOTAL INSERTED: {total}")

@app.get("/ranking")
def ranking(
    limit: int = Query(10, ge=1, le=50),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    rows = crud.get_unique_latest(db, limit=50, sort_desc=(order == "desc"))
    items = []
    seen = set()
    for row in rows:
        city = canonical_city_name(row.city)
        if city in seen:
            continue
        seen.add(city)
        items.append({
            "city": city,
            "aqi": round(float(row.aqi or 0), 2),
            "level": aqi_level(float(row.aqi or 0)),
        })
        if len(items) >= limit:
            break
    return items


@app.get("/city")
def get_by_city(city: str = Query(...), db: Session = Depends(get_db)):
    items = []
    seen = set()
    for row in crud.get_city_history(db, city, limit=50):
        key = (canonical_city_name(row.city), str(row.time))
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

    summary1 = stats1[0]
    summary2 = stats2[0]
    data1 = serialize_summary(summary1)
    data2 = serialize_summary(summary2)

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
    raw_latest = crud.get_all_latest_by_city(db, limit=50, sort_desc=False)
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
    result = (
        db.query(models.AirQuality)
        .filter(or_(*filters))
        .order_by(models.AirQuality.time.desc())
        .limit(10)
        .all()
    )
    result = distinct_time_series(result)

    return {
        "labels": [str(r.time) for r in result],
        "aqi": [r.aqi for r in result],
    }


@app.get("/chart_multi")
def get_chart_multi(db: Session = Depends(get_db)):
    result = {}

    # 🔥 lấy tất cả time unique từ DB
    all_rows = db.query(models.AirQuality.time)\
        .order_by(models.AirQuality.time.desc())\
        .limit(10)\
        .all()

    labels = [str(r.time) for r in reversed(all_rows)]

    for profile in CITY_PROFILES:
        terms = city_search_terms(profile["name"])

        rows = db.query(models.AirQuality)\
            .filter(or_(*[models.AirQuality.city.ilike(f"%{term}%") for term in terms]))\
            .order_by(models.AirQuality.time.desc())\
            .limit(10)\
            .all()

        # 🔥 convert thành dict để match nhanh
        time_map = {str(r.time): r.aqi for r in rows}

        aqi_values = []
        for t in labels:
            aqi_values.append(time_map.get(t, None))

        result[profile["name"]] = {
            "labels": labels,
            "aqi": aqi_values
        }

    return result


@app.get("/cluster")
def cluster(db: Session = Depends(get_db)):
    return cluster_data(db)


@app.get("/predict")
def predict(city: str = Query(None), db: Session = Depends(get_db)):
    return predict_aqi(db, city=city)


def auto_crawl():
    while True:
        db = SessionLocal()
        try:
            data = fetch_data()
            if data:
                crud.insert_data(db, data)
                print("Auto crawl OK")
        except Exception as e:
            print("Auto crawl error:", e)
        finally:
            db.close()

        time.sleep(10)  # crawl mỗi 10 giây


# @app.on_event("startup")
# def start_auto_crawl():
#     threading.Thread(target=auto_crawl, daemon=True).start()
