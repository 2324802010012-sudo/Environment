def calc_sub_index(C, breakpoints):
    for (C_lo, C_hi, I_lo, I_hi) in breakpoints:
        if C_lo <= C <= C_hi:
            return ((I_hi - I_lo) / (C_hi - C_lo)) * (C - C_lo) + I_lo
    return None


def calculate_aqi(pm25=None, pm10=None):
    pm25_bp = [
        (0.0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400),
        (350.5, 500.4, 401, 500),
    ]

    pm10_bp = [
        (0, 54, 0, 50),
        (55, 154, 51, 100),
        (155, 254, 101, 150),
        (255, 354, 151, 200),
        (355, 424, 201, 300),
        (425, 504, 301, 400),
        (505, 604, 401, 500),
    ]

    sub_indices = []

    if pm25 is not None:
        val = calc_sub_index(pm25, pm25_bp)
        if val is not None:
            sub_indices.append(val)

    if pm10 is not None:
        val = calc_sub_index(pm10, pm10_bp)
        if val is not None:
            sub_indices.append(val)

    if not sub_indices:
        return None

    return round(max(sub_indices), 2)