from datetime import datetime, timedelta

import pandas as pd

from .cities import canonical_city_name


class DataLoader:
    def load_and_process(self, records):
        if not records:
            return [], {"raw_count": 0, "valid_count": 0, "invalid_count": 0}

        df = pd.DataFrame(records)

        if "observed_time" not in df.columns and "time" in df.columns:
            df["observed_time"] = df["time"]
        if "time" not in df.columns and "observed_time" in df.columns:
            df["time"] = df["observed_time"]

        required_columns = [
            "city",
            "country",
            "latitude",
            "longitude",
            "observed_time",
            "time",
            "collected_at",
            "station",
            "pm25",
            "pm10",
            "co",
            "no2",
            "so2",
            "o3",
            "aqi",
        ]
        for column in required_columns:
            if column not in df:
                df[column] = None

        raw_count = len(df)

        df["aqi"] = pd.to_numeric(df["aqi"], errors="coerce")
        df = df[(df["aqi"] >= 0) & (df["aqi"] <= 500)]

        df["city"] = df["city"].fillna("").apply(canonical_city_name).str.strip()
        df = df[df["city"] != ""]
        df["country"] = df["country"].fillna("Vietnam").replace("", "Vietnam")
        df["station"] = df["station"].fillna("open_meteo").replace("", "open_meteo")
        df["observed_time"] = pd.to_datetime(df["observed_time"], errors="coerce")
        df["time"] = df["observed_time"]
        df["collected_at"] = pd.to_datetime(df["collected_at"], errors="coerce")
        df["collected_at"] = df["collected_at"].fillna(pd.Timestamp(datetime.now().replace(microsecond=0)))
        df = df.dropna(subset=["observed_time"])

        now_with_margin = pd.Timestamp(datetime.now() + timedelta(minutes=2))
        df = df[df["observed_time"] <= now_with_margin]

        for column in ["latitude", "longitude", "pm25", "pm10", "co", "no2", "so2", "o3"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.drop_duplicates(subset=["city", "observed_time", "station"])
        df = df.where(pd.notna(df), None)
        clean_data = df[required_columns].to_dict(orient="records")
        for record in clean_data:
            for key, value in list(record.items()):
                try:
                    if pd.isna(value):
                        record[key] = None
                except (TypeError, ValueError):
                    pass
            for field in ("observed_time", "time", "collected_at"):
                if record[field] is not None and hasattr(record[field], "to_pydatetime"):
                    record[field] = record[field].to_pydatetime()
            record["time"] = record["observed_time"]

        return clean_data, {
            "raw_count": raw_count,
            "valid_count": len(clean_data),
            "invalid_count": raw_count - len(clean_data),
        }
