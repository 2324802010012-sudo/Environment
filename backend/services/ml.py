import warnings
from datetime import datetime, timedelta

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

try:
    from ..models import AirQuality
except ImportError:
    from models import AirQuality

from .cities import canonical_city_name


FEATURE_COLUMNS = ["pm25", "pm10", "co", "no2", "so2", "o3"]


def _station_priority(row):
    return 0 if row.station == "open_meteo" else 1


def _latest_city_rows(rows):
    latest = {}
    for row in rows:
        city = canonical_city_name(row.city)
        current = latest.get(city)
        if current is None:
            latest[city] = row
            continue

        current_key = (current.observed_time, -_station_priority(current))
        row_key = (row.observed_time, -_station_priority(row))
        if row_key > current_key:
            latest[city] = row

    return list(latest.values())


def _to_float_or_none(value):
    if pd.isna(value):
        return None
    return round(float(value), 2)


def cluster_data(db, n_clusters=3, max_age_hours=None):
    query = db.query(AirQuality)

    if max_age_hours is not None:
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        query = query.filter(AirQuality.observed_time >= cutoff)

    rows = _latest_city_rows(query.order_by(AirQuality.observed_time.desc()).all())
    if not rows:
        return {"error": "No data", "clusters": [], "summary": []}

    df = pd.DataFrame(
        [
            {
                "city": canonical_city_name(row.city),
                "pm25": row.pm25,
                "pm10": row.pm10,
                "co": row.co,
                "no2": row.no2,
                "so2": row.so2,
                "o3": row.o3,
                "aqi": row.aqi,
            }
            for row in rows
        ]
    )

    for column in FEATURE_COLUMNS + ["aqi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["aqi"])
    df = df[df[FEATURE_COLUMNS].notna().any(axis=1)]
    if len(df) < n_clusters:
        return {
            "error": "Not enough city-level data for KMeans",
            "clusters": [],
            "summary": [],
            "model_info": {
                "algorithm": "KMeans",
                "n_clusters": n_clusters,
                "sample_count": int(len(df)),
                "fresh_window_hours": max_age_hours,
            },
        }

    raw_features = df[FEATURE_COLUMNS].copy()
    medians = raw_features.median(numeric_only=True)
    all_missing_columns = [column for column in FEATURE_COLUMNS if pd.isna(medians[column])]
    feature_frame = raw_features.fillna(medians).fillna(0)

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(feature_frame)

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        df["cluster"] = model.fit_predict(x_scaled)

    silhouette = None
    unique_clusters = sorted(df["cluster"].unique())
    if len(df) > len(unique_clusters) and len(unique_clusters) > 1:
        silhouette = round(float(silhouette_score(x_scaled, df["cluster"])), 4)

    cluster_order = (
        df.groupby("cluster")["aqi"]
        .mean()
        .sort_values()
        .index
        .tolist()
    )
    label_order = ["low", "medium", "high"]
    if len(cluster_order) == 2:
        label_order = ["low", "high"]

    labels = {
        cluster_id: label_order[min(index, len(label_order) - 1)]
        for index, cluster_id in enumerate(cluster_order)
    }
    df["level"] = df["cluster"].map(labels)

    clusters = []
    for index, row in df.sort_values("aqi").iterrows():
        original = raw_features.loc[index]
        clusters.append(
            {
                "city": row["city"],
                "cluster": int(row["cluster"]),
                "level": row["level"],
                "pm25": _to_float_or_none(original["pm25"]),
                "pm10": _to_float_or_none(original["pm10"]),
                "co": _to_float_or_none(original["co"]),
                "no2": _to_float_or_none(original["no2"]),
                "so2": _to_float_or_none(original["so2"]),
                "o3": _to_float_or_none(original["o3"]),
                "aqi": round(float(row["aqi"]), 2),
            }
        )

    summary = [
        {"level": level, "count": int((df["level"] == level).sum())}
        for level in ["low", "medium", "high"]
    ]

    return {
        "clusters": clusters,
        "summary": summary,
        "model_info": {
            "algorithm": "KMeans",
            "features": FEATURE_COLUMNS,
            "n_clusters": n_clusters,
            "sample_count": int(len(df)),
            "silhouette_score": silhouette,
            "fresh_window_hours": max_age_hours,
            "imputation": "Missing pollutant features are filled with column medians for training only.",
            "all_missing_columns": all_missing_columns,
        },
    }


def city_cluster_level(db, city, max_age_hours=None):
    result = cluster_data(db, max_age_hours=max_age_hours)
    canonical = canonical_city_name(city)
    for row in result.get("clusters", []):
        if canonical_city_name(row["city"]) == canonical:
            return row
    return None
