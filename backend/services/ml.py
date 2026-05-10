import pandas as pd
from sklearn.cluster import KMeans
from sqlalchemy import func
from models import AirQuality
from services.cities import canonical_city_name


def cluster_data(db, n_clusters=3):
    rows = db.query(
        AirQuality.city,
        func.avg(AirQuality.pm25).label("pm25"),
        func.avg(AirQuality.pm10).label("pm10"),
        func.avg(AirQuality.co).label("co"),
        func.avg(AirQuality.no2).label("no2"),
        func.avg(AirQuality.o3).label("o3"),
        func.avg(AirQuality.aqi).label("aqi")
    ).group_by(AirQuality.city).all()

    if not rows:
        return {"error": "No data"}

    df = pd.DataFrame(rows, columns=['city', 'pm25', 'pm10', 'co', 'no2', 'o3', 'aqi']).fillna(0)
    df['city'] = df['city'].apply(canonical_city_name)
    df = df.groupby('city', as_index=False)[['pm25', 'pm10', 'co', 'no2', 'o3', 'aqi']].mean()

    if len(df) < n_clusters:
        return {"error": "Not enough city-level data"}

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['cluster'] = model.fit_predict(df[['pm25', 'pm10', 'co', 'no2', 'o3']])

    cluster_order = (
        df.groupby('cluster')['aqi']
          .mean()
          .sort_values()
          .index
          .tolist()
    )

    labels = {cluster_order[i]: label for i, label in enumerate(['low', 'medium', 'high'])}
    df['level'] = df['cluster'].map(labels)

    clusters = []
    for _, row in df.sort_values('aqi').iterrows():
        clusters.append({
            'city': row['city'],
            'level': row['level'],
            'pm25': round(float(row['pm25']), 2),
            'pm10': round(float(row['pm10']), 2),
            'co': round(float(row['co']), 2),
            'no2': round(float(row['no2']), 2),
            'o3': round(float(row['o3']), 2),
            'aqi': round(float(row['aqi']), 2),
        })

    summary = [
        {'level': name, 'count': int((df['level'] == name).sum())}
        for name in ['low', 'medium', 'high']
    ]

    return {'clusters': clusters, 'summary': summary}
