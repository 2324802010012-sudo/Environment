class DataLoader:

    def load_and_process(self, records):
        clean_data = []

        for r in records:
            if r.get("aqi") is None:
                continue

            r["city"] = r["city"].strip()

            clean_data.append(r)

        return clean_data, {
            "valid_count": len(clean_data)
        }