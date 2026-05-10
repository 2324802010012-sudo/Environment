import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import random
import logging
from typing import List, Dict, Optional
from datetime import timedelta
from services.cities import CITY_PROFILES, canonical_city_name

logger = logging.getLogger(__name__)

# =========================
# CONFIG
# =========================
TOKEN = "174f627bb749f9c59ed41a910cea85c489035956"
WAQI_URL = "https://api.waqi.info/feed/{}/?token={}"
IQAIR_URL = "https://www.iqair.com/vi/vietnam"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# SAFE
# =========================
def safe_float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except:
        return None


# =========================
# API (CHÍNH)
# =========================
def parse_time(time_str):
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    except:
        return datetime.now()
def fetch_from_api(city_name: str) -> Optional[Dict]:
    try:
        search_url = f"https://api.waqi.info/search/?token={TOKEN}&keyword={city_name}"
        search_res = requests.get(search_url, timeout=10).json()

        if search_res.get("status") != "ok" or not search_res.get("data"):
            return None

        stations = search_res["data"][:5] # 🔥 lấy tối đa 3 trạm

        best = None

        for s in stations:
            uid = s["uid"]

            url = f"https://api.waqi.info/feed/@{uid}/?token={TOKEN}"
            res = requests.get(url, timeout=10)
            data = res.json()

            if data.get("status") != "ok":
                continue

            d = data.get("data", {})
            aqi = safe_float(d.get("aqi"))

            if aqi is None:
                continue

            # 👉 chọn AQI cao nhất (ưu tiên ô nhiễm nặng)
            if not best or aqi > best["aqi"]:
                iaqi = d.get("iaqi", {})
                best = {
                    "city": canonical_city_name(city_name),
                    "time": parse_time(d.get("time", {}).get("s")) or datetime.now(),
                    "aqi": aqi,
                    "pm25": safe_float(iaqi.get("pm25", {}).get("v")),
                    "pm10": safe_float(iaqi.get("pm10", {}).get("v")),
                    "co": safe_float(iaqi.get("co", {}).get("v")),
                    "no2": safe_float(iaqi.get("no2", {}).get("v")),
                    "o3": safe_float(iaqi.get("o3", {}).get("v")),
                }

        return best

    except Exception as e:
        logger.error(f"[API ERROR] {city_name}: {e}")
        return None
# =========================
# PARSE HTML (FALLBACK)
# =========================
def parse_html(html: str, city: str) -> Optional[Dict]:
    soup = BeautifulSoup(html, "html.parser")

    try:
        aqi_el = soup.select_one(".aqi-value__value")
        aqi = safe_float(aqi_el.text if aqi_el else None)

        pm25 = None
        rows = soup.select(".pollutant-concentration")

        for r in rows:
            text = r.text.lower()
            if "pm2.5" in text:
                val = r.select_one(".pollutant-concentration__value")
                pm25 = safe_float(val.text if val else None)

        if aqi is None:
            return None

        return {
            "city": canonical_city_name(city),
            "time": datetime.now(), # 👉 giả timestamp
            "aqi": aqi,
            "pm25": pm25,
            "pm10": None,
            "co": None,
            "no2": None,
            "o3": None,
        }

    except Exception as e:
        logger.error(f"[PARSE ERROR] {city}: {e}")
        return None


# =========================
# CRAWL HTML (FALLBACK)
# =========================
def crawl_html(city_name: str, slug: str) -> Optional[Dict]:
    try:
        url = f"{IQAIR_URL}/{slug}"
        res = requests.get(url, headers=HEADERS, timeout=10)

        if res.status_code != 200:
            return None

        return parse_html(res.text, city_name)

    except Exception as e:
        logger.error(f"[HTML ERROR] {city_name}: {e}")
        return None


# =========================
# MAIN CRAWL
# =========================
def crawl_city(city_name: str, slug: str) -> Optional[Dict]:

    # 👉 dùng tên city thay vì slug
    data = fetch_from_api(city_name)

    if data and data["aqi"]:
        print(f"[API OK] {city_name} - AQI {data['aqi']}")
        return data

    # 👉 fallback HTML
    data = crawl_html(city_name, slug)

    if data:
        print(f"[HTML OK] {city_name} - AQI {data['aqi']}")
        return data

    print(f"[FAIL] {city_name}")
    return None

# =========================
# FETCH ALL
# =========================
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import random

MAX_WORKERS = 20   # 🔥 số thread song song

def crawl_city_safe(city):
    try:
        name = city["name"]
        slug = city["slug"]

        data = crawl_city(name, slug)

        if data:
            return data   # ✅ giữ time thật

    except Exception as e:
        print("Thread error:", e)

    return None


def fetch_data():
    print("===== FAST CRAWL =====")

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(crawl_city_safe, c) for c in CITY_PROFILES]

        for future in as_completed(futures):
            data = future.result()
            if data:
                results.append(data)

    print(f"TOTAL: {len(results)} records")
    return results