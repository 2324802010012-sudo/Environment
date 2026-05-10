from types import SimpleNamespace

from sqlalchemy import func, desc, asc, or_
from models import AirQuality
from services.cities import canonical_city_name, city_search_terms


# =========================
# FILTER CITY
# =========================
def _city_filter(city):
    terms = city_search_terms(city)
    return or_(*[AirQuality.city.ilike(f"%{term}%") for term in terms])


# =========================
# INSERT DATA (FINAL)
# =========================
def insert_data(db, records):

    objs = []

    for r in records:

        if r.get("aqi") is None:
            continue

        if r["aqi"] < 0 or r["aqi"] > 500:
            continue

        city = canonical_city_name(r["city"])

        obj = AirQuality(
            city=city,
            time=r["time"],
            pm25=r.get("pm25"),
            pm10=r.get("pm10"),
            co=r.get("co"),
            no2=r.get("no2"),
            o3=r.get("o3"),
            aqi=r.get("aqi")
        )

        objs.append(obj)

    try:
        db.bulk_save_objects(objs)
        db.commit()
    except Exception as e:
        print("Bulk insert error:", e)
        db.rollback()

# =========================
# LẤY TOP MỚI NHẤT
# =========================
def get_unique_latest(db, limit=10, sort_desc=True):

    subquery = db.query(
        AirQuality.city.label("city"),
        func.max(AirQuality.time).label("latest_time")
    ).group_by(AirQuality.city).subquery()

    query = db.query(AirQuality).join(
        subquery,
        (AirQuality.city == subquery.c.city) &
        (AirQuality.time == subquery.c.latest_time)
    )

    if sort_desc:
        query = query.order_by(desc(AirQuality.aqi))
    else:
        query = query.order_by(asc(AirQuality.aqi))

    return query.limit(limit).all()


# =========================
# SEARCH CITY
# =========================
def search_city_records(db, city, limit=50):
    return db.query(AirQuality)\
        .filter(_city_filter(city))\
        .order_by(AirQuality.time.desc())\
        .limit(limit)\
        .all()


def get_city_history(db, city, limit=50):
    return search_city_records(db, city, limit)


# =========================
# AGGREGATE
# =========================
def get_city_aggregate(db, city):

    row = db.query(
        func.avg(AirQuality.pm25).label("pm25"),
        func.avg(AirQuality.pm10).label("pm10"),
        func.avg(AirQuality.co).label("co"),
        func.avg(AirQuality.no2).label("no2"),
        func.avg(AirQuality.o3).label("o3"),
        func.avg(AirQuality.aqi).label("aqi")
    ).filter(_city_filter(city)).first()

    if not row or row.aqi is None:
        return []

    return [SimpleNamespace(
        city=canonical_city_name(city),
        pm25=float(row.pm25 or 0),
        pm10=float(row.pm10 or 0),
        co=float(row.co or 0),
        no2=float(row.no2 or 0),
        o3=float(row.o3 or 0),
        aqi=float(row.aqi or 0),
    )]


# =========================
# ALL CITY AVERAGE
# =========================
def get_all_city_averages(db):
    return db.query(
        AirQuality.city,
        func.avg(AirQuality.pm25).label("pm25"),
        func.avg(AirQuality.pm10).label("pm10"),
        func.avg(AirQuality.co).label("co"),
        func.avg(AirQuality.no2).label("no2"),
        func.avg(AirQuality.o3).label("o3"),
        func.avg(AirQuality.aqi).label("aqi")
    ).group_by(AirQuality.city).all()


# =========================
# ALL LATEST
# =========================
def get_all_latest_by_city(db, limit=None, sort_desc=True):
    return get_unique_latest(db, limit=limit or 100, sort_desc=sort_desc)