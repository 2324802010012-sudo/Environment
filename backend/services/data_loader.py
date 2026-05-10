import pandas as pd

from services.cities import canonical_city_name


class DataLoader:
    def load_and_process(self, records):
        if not records:
            return [], {"valid_count": 0}

        df = pd.DataFrame(records)

        required_columns = ["city", "time", "station", "pm25", "pm10", "co", "no2", "o3", "aqi"]
        for column in required_columns:
            if column not in df:
                df[column] = None

        df = df.dropna(subset=["aqi"])
        df["aqi"] = pd.to_numeric(df["aqi"], errors="coerce")
        df = df[(df["aqi"] >= 0) & (df["aqi"] <= 500)]

        df["city"] = df["city"].fillna("").apply(canonical_city_name)
        df["station"] = df["station"].fillna("unknown")
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["city", "time"])
        df["time"] = df["time"].apply(lambda value: value.to_pydatetime())

        for column in ["pm25", "pm10", "co", "no2", "o3"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.drop_duplicates(subset=["city", "time", "station"])
        clean_data = df[required_columns].to_dict(orient="records")
        for record in clean_data:
            if hasattr(record["time"], "to_pydatetime"):
                record["time"] = record["time"].to_pydatetime()

        return clean_data, {"valid_count": len(clean_data)}
