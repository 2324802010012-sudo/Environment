import math
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import func, or_, tuple_
from sqlalchemy.exc import IntegrityError

try:
    from .models import AirQuality, AirQualityHistory
    from .services.cities import canonical_city_name, city_search_terms
except ImportError:
    from models import AirQuality, AirQualityHistory
    from services.cities import canonical_city_name, city_search_terms


POLLUTANT_FIELDS = ["pm25", "pm10", "co", "no2", "so2", "o3"]


def clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _observed_time(record):
    return record.get("observed_time") or record.get("time")


def _collected_at(record):
    return record.get("collected_at") or datetime.now().replace(microsecond=0)


def _city_filter(city):
    terms = city_search_terms(city)
    return or_(*[AirQuality.city.ilike(f"%{term}%") for term in terms])


def _history_city_filter(city):
    terms = city_search_terms(city)
    return or_(*[AirQualityHistory.city.ilike(f"%{term}%") for term in terms])


def clear_data(db):
    deleted = db.query(AirQuality).delete(synchronize_session=False)
    db.flush()
    return deleted


def archive_data(db, records):
    archived = 0

    for record in records:
        aqi = clean(record.get("aqi"))
        observed_time = _observed_time(record)
        if aqi is None or aqi < 0 or aqi > 500 or observed_time is None:
            continue

        city = canonical_city_name(record.get("city", ""))
        station = record.get("station") or "open_meteo"
        exists = (
            db.query(AirQualityHistory.id)
            .filter(
                AirQualityHistory.city == city,
                AirQualityHistory.observed_time == observed_time,
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
                latitude=clean(record.get("latitude")),
                longitude=clean(record.get("longitude")),
                observed_time=observed_time,
                collected_at=_collected_at(record),
                pm25=clean(record.get("pm25")),
                pm10=clean(record.get("pm10")),
                co=clean(record.get("co")),
                no2=clean(record.get("no2")),
                so2=clean(record.get("so2")),
                o3=clean(record.get("o3")),
                aqi=aqi,
                station=station,
            )
        )
        archived += 1

    db.flush()
    return archived


def insert_data(db, records):
    valid_records = []

    for record in records:
        aqi = clean(record.get("aqi"))
        observed_time = _observed_time(record)
        if aqi is None or aqi < 0 or aqi > 500 or observed_time is None:
            continue

        city = canonical_city_name(record.get("city", ""))
        if not city:
            continue

        station = record.get("station") or "open_meteo"
        country = record.get("country") or "Vietnam"
        valid_records.append(
            {
                **record,
                "city": city,
                "country": country,
                "station": station,
                "observed_time": observed_time,
                "collected_at": _collected_at(record),
                "aqi": aqi,
            }
        )

    if not valid_records:
        print("[INSERTED] 0 records")
        return 0

    keys = {
        (record["city"], record["observed_time"], record["station"])
        for record in valid_records
    }
    existing_keys = set()

    for chunk in _chunks(list(keys), 500):
        rows = (
            db.query(AirQuality.city, AirQuality.observed_time, AirQuality.station)
            .filter(tuple_(AirQuality.city, AirQuality.observed_time, AirQuality.station).in_(chunk))
            .all()
        )
        existing_keys.update((row.city, row.observed_time, row.station) for row in rows)

    objects = []
    seen = set()
    for record in valid_records:
        key = (record["city"], record["observed_time"], record["station"])
        if key in existing_keys or key in seen:
            continue

        seen.add(key)
        objects.append(
            AirQuality(
                city=record["city"],
                country=record["country"],
                latitude=clean(record.get("latitude")),
                longitude=clean(record.get("longitude")),
                observed_time=record["observed_time"],
                collected_at=record["collected_at"],
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
            print(f"[SKIP INSERT ERROR] {obj.city} - {obj.observed_time}: {exc}")
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


def _row_time(row):
    return row.observed_time or datetime.min


def _dedupe_latest_rows(rows):
    latest_by_city = {}
    for row in rows:
        city = canonical_city_name(row.city)
        current = latest_by_city.get(city)
        if current is None:
            latest_by_city[city] = row
            continue

        current_key = (_row_time(current), -_station_priority(current))
        row_key = (_row_time(row), -_station_priority(row))
        if row_key > current_key:
            latest_by_city[city] = row

    return list(latest_by_city.values())


def _dedupe_history_rows(rows):
    best_by_time = {}
    for row in rows:
        key = (canonical_city_name(row.city), row.observed_time)
        current = best_by_time.get(key)
        if current is None or _station_priority(row) < _station_priority(current):
            best_by_time[key] = row

    return sorted(best_by_time.values(), key=lambda row: _row_time(row), reverse=True)


def get_latest_city_rows(db, max_age_hours=None):
    query = db.query(AirQuality)

    cutoff = _fresh_cutoff(max_age_hours)
    if cutoff is not None:
        query = query.filter(AirQuality.observed_time >= cutoff)

    rows = query.order_by(AirQuality.observed_time.desc()).all()
    return _dedupe_latest_rows(rows)


def get_unique_latest(db, limit=10, sort_desc=True, max_age_hours=None):
    latest_rows = get_latest_city_rows(db, max_age_hours=max_age_hours)
    latest_rows.sort(
        key=lambda row: float(row.aqi) if row.aqi is not None else float("-inf"),
        reverse=sort_desc,
    )
    return latest_rows[:limit]


def search_city_records(
    db,
    city,
    limit=50,
    max_age_hours=None,
    start_date=None,
    end_date=None,
):
    query = db.query(AirQuality).filter(_city_filter(city))

    cutoff = _fresh_cutoff(max_age_hours)
    if cutoff is not None:
        query = query.filter(AirQuality.observed_time >= cutoff)
    if start_date is not None:
        query = query.filter(AirQuality.observed_time >= start_date)
    if end_date is not None:
        query = query.filter(AirQuality.observed_time <= end_date)

    rows = query.order_by(AirQuality.observed_time.desc()).limit(limit * 3).all()
    return _dedupe_history_rows(rows)[:limit]


def get_city_history(db, city, limit=50, max_age_hours=None):
    return search_city_records(db, city, limit, max_age_hours=max_age_hours)


def get_city_history_between(db, city, start_date=None, end_date=None, limit=300):
    return search_city_records(
        db,
        city,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
    )


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
            pm25=clean(row.pm25),
            pm10=clean(row.pm10),
            co=clean(row.co),
            no2=clean(row.no2),
            so2=clean(row.so2),
            o3=clean(row.o3),
            aqi=clean(row.aqi),
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
    rows = get_unique_latest(
        db,
        limit=limit or 100,
        sort_desc=sort_desc,
        max_age_hours=max_age_hours,
    )
    return rows


def count_records(db, max_age_hours=None):
    query = db.query(func.count(AirQuality.id))
    cutoff = _fresh_cutoff(max_age_hours)
    if cutoff is not None:
        query = query.filter(AirQuality.observed_time >= cutoff)
    return int(query.scalar() or 0)
