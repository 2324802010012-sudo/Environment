import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func
try:
    from ..models import AirQuality
except ImportError:
    from models import AirQuality
from .cities import canonical_city_name


def cluster_data(db, n_clusters=3):
    # =========================
    # LOAD DATA
    # =========================
    rows = db.query(
        AirQuality.city,
        func.avg(AirQuality.pm25).label("pm25"),
        func.avg(AirQuality.pm10).label("pm10"),
        func.avg(AirQuality.co).label("co"),
        func.avg(AirQuality.no2).label("no2"),
        func.avg(AirQuality.so2).label("so2"),
        func.avg(AirQuality.o3).label("o3"),
        func.avg(AirQuality.aqi).label("aqi")
    ).group_by(AirQuality.city).all()

    if not rows:
        return {"error": "No data"}

    # =========================
    # DATAFRAME
    # =========================
    df = pd.DataFrame(rows, columns=['city', 'pm25', 'pm10', 'co', 'no2', 'so2', 'o3', 'aqi'])

    pollutant_columns = ['pm25', 'pm10', 'co', 'no2', 'so2', 'o3']
    df = df.dropna(subset=['aqi'])
    for column in pollutant_columns + ['aqi']:
        df[column] = pd.to_numeric(df[column], errors='coerce')
    df[pollutant_columns] = df[pollutant_columns].fillna(df[pollutant_columns].median(numeric_only=True))
    df = df.fillna(0)

    # chuẩn hóa tên city
    df['city'] = df['city'].apply(canonical_city_name)

    # gộp duplicate city (phòng trường hợp DB lỗi)
    df = df.groupby('city', as_index=False).mean()

    if len(df) < n_clusters:
        return {"error": "Not enough city-level data"}

    # =========================
    # SCALE DATA (RẤT QUAN TRỌNG)
    # =========================
    features = df[pollutant_columns]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    # =========================
    # KMEANS
    # =========================
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['cluster'] = model.fit_predict(X_scaled)

    # =========================
    # SẮP XẾP CLUSTER THEO AQI
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
        'summary': summary
    }
