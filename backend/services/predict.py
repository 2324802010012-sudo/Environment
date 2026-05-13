import pandas as pd
from sklearn.linear_model import LinearRegression
from sqlalchemy import text
from .cities import city_search_terms

def predict_aqi(db, city: str = None):

    # =========================
    # LOAD DATA
    # =========================
    query = text("""
        SELECT pm25, pm10, co, no2, so2, o3, aqi
        FROM air_quality
        WHERE aqi IS NOT NULL AND aqi > 0
    """)

    data = db.execute(query).fetchall()

    if len(data) < 20:
        return {"predicted_aqi": 0, "message": "Not enough data"}

    df = pd.DataFrame(data, columns=['pm25','pm10','co','no2','so2','o3','aqi'])

    # =========================
    # CLEAN DATA 🔥
    # =========================
    df = df.fillna(0)

    X = df[['pm25','pm10','co','no2','so2','o3']]
    y = df['aqi']

    # =========================
    # TRAIN MODEL
    # =========================
    model = LinearRegression()
    model.fit(X, y)

    # =========================
    # LẤY INPUT
    # =========================
    if city:
        terms = city_search_terms(city)

        clauses = " OR ".join([
            f"LOWER(city) LIKE LOWER(:city{i})"
            for i in range(len(terms))
        ])

        region_query = text(f"""
            SELECT pm25, pm10, co, no2, so2, o3
            FROM air_quality
            WHERE {clauses}
            ORDER BY time DESC
            LIMIT 1
        """)

        params = {f"city{i}": f"%{term}%" for i, term in enumerate(terms)}
        last = db.execute(region_query, params).fetchone()

        if last is None:
            return {"error": "City not found", "predicted_aqi": None}

        input_dict = {
            "pm25": float(last[0] or 0),
            "pm10": float(last[1] or 0),
            "co": float(last[2] or 0),
            "no2": float(last[3] or 0),
            "so2": float(last[4] or 0),
            "o3": float(last[5] or 0),
        }

    else:
        row = X.iloc[-1]
        input_dict = row.to_dict()

    # =========================
    # PREDICT (FIX WARNING) 🔥
    # =========================
    input_df = pd.DataFrame([input_dict])

    pred = model.predict(input_df)[0]

    return {
        "predicted_aqi": round(float(pred), 2)
    }
