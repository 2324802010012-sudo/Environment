import pandas as pd
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sqlalchemy import text
from .cities import city_search_terms

def predict_aqi(db, city: str = None, max_age_hours: int = 48):

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
    feature_columns = ['pm25','pm10','co','no2','so2','o3']
    for column in feature_columns + ['aqi']:
        df[column] = pd.to_numeric(df[column], errors='coerce')

    feature_medians = df[feature_columns].median(numeric_only=True).fillna(0)
    df[feature_columns] = df[feature_columns].fillna(feature_medians)

    X = df[feature_columns]
    y = df['aqi']

    # =========================
    # TRAIN MODEL
    # =========================
    model_r2 = None
    model_mae = None
    if len(df) >= 30:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
        )
        eval_model = LinearRegression()
        eval_model.fit(X_train, y_train)
        y_pred = eval_model.predict(X_test)
        model_r2 = round(float(r2_score(y_test, y_pred)), 4)
        model_mae = round(float(mean_absolute_error(y_test, y_pred)), 2)

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
              AND time >= :cutoff
            ORDER BY time DESC
            LIMIT 1
        """)

        params = {f"city{i}": f"%{term}%" for i, term in enumerate(terms)}
        params["cutoff"] = datetime.now() - timedelta(hours=max_age_hours)
        last = db.execute(region_query, params).fetchone()

        if last is None:
            return {
                "error": "No fresh city data found",
                "predicted_aqi": None,
                "fresh_window_hours": max_age_hours,
            }

        input_dict = {
            "pm25": float(last[0]) if last[0] is not None else None,
            "pm10": float(last[1]) if last[1] is not None else None,
            "co": float(last[2]) if last[2] is not None else None,
            "no2": float(last[3]) if last[3] is not None else None,
            "so2": float(last[4]) if last[4] is not None else None,
            "o3": float(last[5]) if last[5] is not None else None,
        }

    else:
        row = X.iloc[-1]
        input_dict = row.to_dict()

    # =========================
    # PREDICT (FIX WARNING) 🔥
    # =========================
    input_df = pd.DataFrame([input_dict])
    imputed_fields = [
        column
        for column in feature_columns
        if column in input_df and pd.isna(input_df.at[0, column])
    ]
    input_df[feature_columns] = input_df[feature_columns].fillna(feature_medians)

    pred = model.predict(input_df)[0]

    return {
        "predicted_aqi": round(float(pred), 2),
        "fresh_window_hours": max_age_hours,
        "imputed_fields": imputed_fields,
        "model_r2": model_r2,
        "model_mae": model_mae,
        "training_records": int(len(df)),
    }
