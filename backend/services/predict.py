from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import or_
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

try:
    from ..models import AirQuality
except ImportError:
    from models import AirQuality

from .cities import city_search_terms


FEATURE_COLUMNS = ["pm25", "pm10", "co", "no2", "so2", "o3"]
MIN_TRAINING_RECORDS = 20


def _row_to_dict(row):
    return {
        "pm25": row.pm25,
        "pm10": row.pm10,
        "co": row.co,
        "no2": row.no2,
        "so2": row.so2,
        "o3": row.o3,
        "aqi": row.aqi,
    }


def _not_enough_message(count):
    return {
        "predicted_aqi": None,
        "training_records": int(count),
        "mae": None,
        "r2": None,
        "message": f"Not enough data for Linear Regression. Need at least {MIN_TRAINING_RECORDS} valid records.",
        "note": "Prediction is only a reference, not an official AQI measurement.",
    }


def predict_aqi(db, city: str = None, max_age_hours: int = 48):
    rows = (
        db.query(AirQuality)
        .filter(AirQuality.aqi.isnot(None))
        .filter(AirQuality.aqi >= 0)
        .filter(AirQuality.aqi <= 500)
        .order_by(AirQuality.observed_time.asc())
        .all()
    )
    df = pd.DataFrame([_row_to_dict(row) for row in rows])

    if df.empty:
        return _not_enough_message(0)

    for column in FEATURE_COLUMNS + ["aqi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["aqi"])
    df = df[df[FEATURE_COLUMNS].notna().any(axis=1)]
    if len(df) < MIN_TRAINING_RECORDS:
        return _not_enough_message(len(df))

    feature_medians = df[FEATURE_COLUMNS].median(numeric_only=True)
    all_missing_columns = [column for column in FEATURE_COLUMNS if pd.isna(feature_medians[column])]
    feature_medians = feature_medians.fillna(0)
    x = df[FEATURE_COLUMNS].fillna(feature_medians)
    y = df["aqi"]

    model_r2 = None
    model_mae = None
    if len(df) >= 30:
        x_train, x_test, y_train, y_test = train_test_split(
            x,
            y,
            test_size=0.2,
            random_state=42,
        )
        eval_model = LinearRegression()
        eval_model.fit(x_train, y_train)
        y_pred = eval_model.predict(x_test)
        model_mae = round(float(mean_absolute_error(y_test, y_pred)), 2)
        model_r2 = round(float(r2_score(y_test, y_pred)), 4)

    model = LinearRegression()
    model.fit(x, y)

    observed_time = None
    if city:
        terms = city_search_terms(city)
        filters = [AirQuality.city.ilike(f"%{term}%") for term in terms]
        last = (
            db.query(AirQuality)
            .filter(or_(*filters))
            .filter(AirQuality.observed_time >= datetime.now() - timedelta(hours=max_age_hours))
            .order_by(AirQuality.observed_time.desc())
            .first()
        )

        if last is None:
            return {
                "error": "No fresh city data found",
                "predicted_aqi": None,
                "training_records": int(len(df)),
                "mae": model_mae,
                "r2": model_r2,
                "fresh_window_hours": max_age_hours,
                "note": "Prediction is only a reference, not an official AQI measurement.",
            }

        input_dict = {column: getattr(last, column) for column in FEATURE_COLUMNS}
        observed_time = last.observed_time
    else:
        input_dict = x.iloc[-1].to_dict()

    input_df = pd.DataFrame([input_dict])
    for column in FEATURE_COLUMNS:
        input_df[column] = pd.to_numeric(input_df[column], errors="coerce")

    imputed_fields = [
        column for column in FEATURE_COLUMNS if pd.isna(input_df.at[0, column])
    ]
    input_df[FEATURE_COLUMNS] = input_df[FEATURE_COLUMNS].fillna(feature_medians)

    raw_prediction = float(model.predict(input_df[FEATURE_COLUMNS])[0])
    prediction = max(0.0, min(500.0, raw_prediction))

    return {
        "predicted_aqi": round(prediction, 2),
        "raw_predicted_aqi": round(raw_prediction, 2),
        "training_records": int(len(df)),
        "mae": model_mae,
        "r2": model_r2,
        "model_mae": model_mae,
        "model_r2": model_r2,
        "fresh_window_hours": max_age_hours,
        "observed_time": str(observed_time) if observed_time else None,
        "features": FEATURE_COLUMNS,
        "imputed_fields": imputed_fields,
        "all_missing_columns": all_missing_columns,
        "note": "Prediction is only a reference, not an official AQI measurement.",
    }
