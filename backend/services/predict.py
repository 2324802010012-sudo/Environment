import pandas as pd
from sklearn.linear_model import LinearRegression
from sqlalchemy import text
from services.cities import city_search_terms

def predict_aqi(db, city: str = None):
    query = text("""
        SELECT pm25, pm10, co, no2, o3, aqi
        FROM air_quality
        WHERE aqi > 0
    """)

    data = db.execute(query).fetchall()

    if len(data) < 20:
        return {"predicted_aqi": 0, "message": "Not enough data to build a model"}

    df = pd.DataFrame(data, columns=['pm25','pm10','co','no2','o3','aqi'])

    X = df[['pm25','pm10','co','no2','o3']]
    y = df['aqi']

    model = LinearRegression()
    model.fit(X, y)

    if city:
        clauses = " OR ".join([f"LOWER(city) LIKE LOWER(:city{i})" for i, _ in enumerate(city_search_terms(city))])
        region_query = text("""
            SELECT pm25, pm10, co, no2, o3
            FROM air_quality
            WHERE """ + clauses + """
            ORDER BY time DESC
            LIMIT 1
        """)
        params = {f"city{i}": f"%{term}%" for i, term in enumerate(city_search_terms(city))}
        last = db.execute(region_query, params).fetchone()

        if last is None:
            return {"error": "City not found", "predicted_aqi": None}

        input_values = [float(value or 0) for value in last]
    else:
        input_values = X.iloc[-1].tolist()

    pred = model.predict([input_values])[0]

    return {
        "predicted_aqi": round(float(pred), 2)
    }
