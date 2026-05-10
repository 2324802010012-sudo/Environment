# services/aqi.py

def calculate_aqi(pm25, pm10, co, no2, o3):
    """
    Tính AQI đơn giản từ các chỉ số ô nhiễm
    """
    values = [
        float(pm25 or 0),
        float(pm10 or 0),
        float(co or 0),
        float(no2 or 0),
        float(o3 or 0),
    ]

    return max(values)