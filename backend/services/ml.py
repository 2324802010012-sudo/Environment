import pandas as pd
from datetime import datetime, timedelta
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
try:
    from ..models import AirQuality
except ImportError:
    from models import AirQuality
from .cities import canonical_city_name


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

        current_key = (current.time, -_station_priority(current))
        row_key = (row.time, -_station_priority(row))
        if row_key > current_key:
            latest[city] = row

    return list(latest.values())


def cluster_data(db, n_clusters=3, max_age_hours=None):
    # =========================
    # LOAD DATA
    # =========================
    query = db.query(AirQuality)

    if max_age_hours is not None:
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        query = query.filter(AirQuality.time >= cutoff)

    rows = _latest_city_rows(query.order_by(AirQuality.time.desc()).all())

    if not rows:
        return {"error": "No data"}

    # =========================
    # DATAFRAME
    # =========================
    df = pd.DataFrame(
        [
            {
                'city': canonical_city_name(row.city),
                'pm25': row.pm25,
                'pm10': row.pm10,
                'co': row.co,
                'no2': row.no2,
                'so2': row.so2,
                'o3': row.o3,
                'aqi': row.aqi,
            }
            for row in rows
        ]
    )

    pollutant_columns = ['pm25', 'pm10', 'co', 'no2', 'so2', 'o3']
    df = df.dropna(subset=['aqi'])
    for column in pollutant_columns + ['aqi']:
        df[column] = pd.to_numeric(df[column], errors='coerce')
    df[pollutant_columns] = df[pollutant_columns].fillna(df[pollutant_columns].median(numeric_only=True))
    df = df.fillna(0)



    if len(df) < n_clusters:
        return {"error": "Not enough city-level data"}

    # =========================
    # SCALE DATA (Ráº¤T QUAN TRá»ŒNG)
    # =========================
    features = df[pollutant_columns]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    # =========================
    # KMEANS
    # =========================
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['cluster'] = model.fit_predict(X_scaled)
    silhouette = None
    if len(df) > n_clusters:
        silhouette = round(float(silhouette_score(X_scaled, df['cluster'])), 4)

    # =========================
    # Sáº®P Xáº¾P CLUSTER THEO AQI
    # =========================
    cluster_order = (
        df.groupby('cluster')['aqi']
        .mean()
        .sort_values()
        .index
        .tolist()
    )

    labels = {
        cluster_order[0]: 'low',
        cluster_order[1]: 'medium',
        cluster_order[2]: 'high'
    }

    df['level'] = df['cluster'].map(labels)

    # =========================
    # OUTPUT
    # =========================
    clusters = []
    for _, row in df.sort_values('aqi').iterrows():
        clusters.append({
            'city': row['city'],
            'level': row['level'],
            'pm25': round(float(row['pm25']), 2),
            'pm10': round(float(row['pm10']), 2),
            'co': round(float(row['co']), 2),
            'no2': round(float(row['no2']), 2),
            'so2': round(float(row['so2']), 2),
            'o3': round(float(row['o3']), 2),
            'aqi': round(float(row['aqi']), 2),
        })

    summary = [
        {'level': level, 'count': int((df['level'] == level).sum())}
        for level in ['low', 'medium', 'high']
    ]

    return {
        'clusters': clusters,
        'summary': summary,
        'model_info': {
            'algorithm': 'KMeans',
            'n_clusters': n_clusters,
            'sample_count': int(len(df)),
            'silhouette_score': silhouette,
            'fresh_window_hours': max_age_hours,
        }
    }
