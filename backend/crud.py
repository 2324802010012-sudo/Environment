from types import SimpleNamespace
from datetime import datetime, timedelta
from sqlalchemy import asc, desc, func, or_, tuple_
from sqlalchemy.exc import IntegrityError

try:
    from .models import AirQuality, AirQualityHistory
    from .services.cities import canonical_city_name, city_search_terms
except ImportError:
    from models import AirQuality, AirQualityHistory
    from services.cities import canonical_city_name, city_search_terms
import math


def clean(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x


def _city_filter(city):
    terms = city_search_terms(city)
    return or_(*[AirQuality.city.ilike(f"%{term}%") for term in terms])


def clear_data(db):
    deleted = db.query(AirQuality).delete(synchronize_session=False)
    db.flush()
    return deleted


def archive_data(db, records):
    archived = 0
    crawled_at = datetime.now().replace(microsecond=0)

    for record in records:
        aqi = record.get("aqi")
        if aqi is None or aqi < 0 or aqi > 500:
            continue

        city = canonical_city_name(record.get("city", ""))
        station = record.get("station") or "unknown"
        exists = (
            db.query(AirQualityHistory.id)
            .filter(
                AirQualityHistory.city == city,
                AirQualityHistory.time == record.get("time"),
                AirQualityHistory.station == station,
            )
            .first()
        )
        if exists:
            continue

        db.add(
            AirQualityHistory(
                city=city,
                country=record.get("country", "Vietnam"),
                time=record.get("time"),
                crawled_at=crawled_at,
                pm25=clean(record.get("pm25")),
                pm10=clean(record.get("pm10")),
                co=clean(record.get("co")),
                no2=clean(record.get("no2")),
                so2=clean(record.get("so2")),
                o3=clean(record.get("o3")),
                aqi=clean(record.get("aqi")),
                station=station,
            )
        )
        archived += 1

    db.flush()
    return archived


def insert_data(db, records):
    valid_records = []

    for record in records:
        aqi = record.get("aqi")
        if aqi is None or aqi < 0 or aqi > 500:
            continue

        city = canonical_city_name(record.get("city", ""))
        station = record.get("station") or "unknown"
        country = record.get("country", "Vietnam")
        valid_records.append({**record, "city": city, "station": station, "country": country})

    if not valid_records:
        print("[INSERTED] 0 records")
        return 0

    keys = {(record["city"], record["time"], record["station"]) for record in valid_records}
    existing_keys = set()

    for chunk in _chunks(list(keys), 500):
        rows = (
            db.query(AirQuality.city, AirQuality.time, AirQuality.station)
            .filter(tuple_(AirQuality.city, AirQuality.time, AirQuality.station).in_(chunk))
            .all()
        )
        existing_keys.update((row.city, row.time, row.station) for row in rows)

    objects = []
    seen = set()
    for record in valid_records:
        key = (record["city"], record["time"], record["station"])
        if key in existing_keys or key in seen:
            continue

        seen.add(key)
        objects.append(
            AirQuality(
                city=record["city"],
                country=record["country"],
                time=record["time"],
                pm25=clean(record.get("pm25")),
                pm10=clean(record.get("pm10")),
                co=clean(record.get("co")),
                no2=clean(record.get("no2")),
                so2=clean(record.get("so2")),
                o3=clean(record.get("o3")),
                aqi=clean(record.get("aqi")),
                station=record["station"],
            )
        )

    if not objects:
        print("[INSERTED] 0 records")
        return 0

    try:
        db.add_all(objects)
        db.commit()
        inserted = len(objects)
    except Exception as exc:
        db.rollback()
        print(f"[BATCH INSERT ERROR] {exc}")
        inserted = _insert_one_by_one(db, objects)

    print(f"[INSERTED] {inserted} records")
    return inserted


def _insert_one_by_one(db, objects):
    inserted = 0
    for obj in objects:
        try:
            db.add(obj)
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
        except Exception as exc:
            db.rollback()
            print(f"[SKIP INSERT ERROR] {obj.city} - {obj.time}: {exc}")
    return inserted


def _chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _fresh_cutoff(max_age_hours):
    if max_age_hours is None:
        return None
    return datetime.now() - timedelta(hours=max_age_hours)


def _station_priority(row):
    return 0 if row.station == "open_meteo" else 1


def _dedupe_latest_rows(rows):
    latest_by_city = {}
    for row in rows:
        city = canonical_city_name(row.city)
        current = latest_by_city.get(city)
        if current is None:
            latest_by_city[city] = row
            continue

        current_key = (current.time, -_station_priority(current))
        row_key = (row.time, -_station_priority(row))
        if row_key > current_key:
            latest_by_city[city] = row

    return list(latest_by_city.values())


def _dedupe_history_rows(rows):
    best_by_time = {}
    for row in rows:
        key = (canonical_city_name(row.city), row.time)
        current = best_by_time.get(key)
        if current is None or _station_priority(row) < _station_priority(current):
            best_by_time[key] = row

    return sorted(best_by_time.values(), key=lambda row: row.time, reverse=True)


def get_unique_latest(db, limit=10, sort_desc=True, max_age_hours=None):
    query = db.query(AirQuality)

    cutoff = _fresh_cutoff(max_age_hours)
    if cutoff is not None:
        query = query.filter(AirQuality.time >= cutoff)

    rows = query.order_by(AirQuality.time.desc()).all()
    latest_rows = _dedupe_latest_rows(rows)
    latest_rows.sort(
        key=lambda row: float(row.aqi or 0),
        reverse=sort_desc,
    )
    return latest_rows[:limit]

def search_city_records(db, city, limit=50, max_age_hours=None):
    query = (
        db.query(AirQuality)
        .filter(_city_filter(city))
    )

    cutoff = _fresh_cutoff(max_age_hours)
    if cutoff is not None:
        query = query.filter(AirQuality.time >= cutoff)

    rows = query.order_by(AirQuality.time.desc()).limit(limit * 2).all()
    return _dedupe_history_rows(rows)[:limit]


def get_city_history(db, city, limit=50, max_age_hours=None):
    return search_city_records(db, city, limit, max_age_hours=max_age_hours)


def get_city_aggregate(db, city):
    row = (
        db.query(
            func.avg(AirQuality.pm25).label("pm25"),
            func.avg(AirQuality.pm10).label("pm10"),
            func.avg(AirQuality.co).label("co"),
            func.avg(AirQuality.no2).label("no2"),
            func.avg(AirQuality.so2).label("so2"),
            func.avg(AirQuality.o3).label("o3"),
            func.avg(AirQuality.aqi).label("aqi"),
        )
        .filter(_city_filter(city))
        .first()
    )

    if not row or row.aqi is None:
        return []

    return [
        SimpleNamespace(
            city=canonical_city_name(city),
            pm25=float(row.pm25 or 0),
            pm10=float(row.pm10 or 0),
            co=float(row.co or 0),
            no2=float(row.no2 or 0),
            so2=float(row.so2 or 0),
            o3=float(row.o3 or 0),
            aqi=float(row.aqi or 0),
        )
    ]


def get_all_city_averages(db):
    return (
        db.query(
            AirQuality.city,
            func.avg(AirQuality.pm25).label("pm25"),
            func.avg(AirQuality.pm10).label("pm10"),
            func.avg(AirQuality.co).label("co"),
            func.avg(AirQuality.no2).label("no2"),
            func.avg(AirQuality.so2).label("so2"),
            func.avg(AirQuality.o3).label("o3"),
            func.avg(AirQuality.aqi).label("aqi"),
        )
        .group_by(AirQuality.city)
        .all()
    )


def get_all_latest_by_city(db, limit=None, sort_desc=True, max_age_hours=None):
    return get_unique_latest(
        db,
        limit=limit or 100,
        sort_desc=sort_desc,
        max_age_hours=max_age_hours,
    )
