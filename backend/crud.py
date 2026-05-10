from types import SimpleNamespace

from sqlalchemy import asc, desc, func, or_, tuple_
from sqlalchemy.exc import IntegrityError
from models import AirQuality
from services.cities import canonical_city_name, city_search_terms


def _city_filter(city):
    terms = city_search_terms(city)
    return or_(*[AirQuality.city.ilike(f"%{term}%") for term in terms])


def insert_data(db, records):
    valid_records = []

    for record in records:
        aqi = record.get("aqi")
        if aqi is None or aqi < 0 or aqi > 500:
            continue

        city = canonical_city_name(record.get("city", ""))
        station = record.get("station") or "unknown"
        valid_records.append({**record, "city": city, "station": station})

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
                time=record["time"],
                pm25=record.get("pm25"),
                pm10=record.get("pm10"),
                co=record.get("co"),
                no2=record.get("no2"),
                o3=record.get("o3"),
                aqi=record.get("aqi"),
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


def get_unique_latest(db, limit=10, sort_desc=True):
    subquery = (
        db.query(
            AirQuality.city.label("city"),
            func.max(AirQuality.time).label("latest_time"),
        )
        .group_by(AirQuality.city)
        .subquery()
    )

    query = db.query(AirQuality).join(
        subquery,
        (AirQuality.city == subquery.c.city) & (AirQuality.time == subquery.c.latest_time),
    )

    query = query.order_by(desc(AirQuality.aqi) if sort_desc else asc(AirQuality.aqi))
    return query.limit(limit).all()


def search_city_records(db, city, limit=50):
    return (
        db.query(AirQuality)
        .filter(_city_filter(city))
        .order_by(AirQuality.time.desc())
        .limit(limit)
        .all()
    )


def get_city_history(db, city, limit=50):
    return search_city_records(db, city, limit)


def get_city_aggregate(db, city):
    row = (
        db.query(
            func.avg(AirQuality.pm25).label("pm25"),
            func.avg(AirQuality.pm10).label("pm10"),
            func.avg(AirQuality.co).label("co"),
            func.avg(AirQuality.no2).label("no2"),
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
            func.avg(AirQuality.o3).label("o3"),
            func.avg(AirQuality.aqi).label("aqi"),
        )
        .group_by(AirQuality.city)
        .all()
    )


def get_all_latest_by_city(db, limit=None, sort_desc=True):
    return get_unique_latest(db, limit=limit or 100, sort_desc=sort_desc)
