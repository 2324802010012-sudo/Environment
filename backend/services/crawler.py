import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from services.cities import CITY_PROFILES, canonical_city_name, strip_accents
from services.robots_checker import RobotsChecker


logger = logging.getLogger(__name__)

WAQI_TOKEN = "174f627bb749f9c59ed41a910cea85c489035956"
WAQI_SEARCH_URL = "https://api.waqi.info/search/"
WAQI_FEED_URL = "https://api.waqi.info/feed/@{uid}/"
IQAIR_BASE_URL = "https://www.iqair.com"
IQAIR_VIETNAM_URL = f"{IQAIR_BASE_URL}/vi/vietnam"

MAX_WORKERS = 32
MAX_STATIONS_PER_TERM = 15
REQUEST_TIMEOUT = 5
VIETNAM_MARKERS = ("vietnam", "viet nam", "việt nam")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def safe_float(value):
    try:
        if value in (None, "-", ""):
            return None
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_time(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    if not value:
        return datetime.now()

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt).replace(tzinfo=None)
        except ValueError:
            continue

    return datetime.now()


def build_record(
    *,
    city: str,
    aqi,
    time_value=None,
    station: Optional[str] = None,
    pm25=None,
    pm10=None,
    co=None,
    no2=None,
    o3=None,
) -> Optional[Dict]:
    aqi_value = safe_float(aqi)
    if aqi_value is None or aqi_value < 0 or aqi_value > 500:
        return None

    return {
        "city": canonical_city_name(city),
        "time": parse_time(time_value),
        "station": station or "unknown",
        "aqi": aqi_value,
        "pm25": safe_float(pm25),
        "pm10": safe_float(pm10),
        "co": safe_float(co),
        "no2": safe_float(no2),
        "o3": safe_float(o3),
    }


def fetch_station_detail(uid: int, city_name: str, station_name: str) -> Optional[Dict]:
    try:
        response = requests.get(
            WAQI_FEED_URL.format(uid=uid),
            params={"token": WAQI_TOKEN},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != "ok":
            return None

        data = payload.get("data") or {}
        iaqi = data.get("iaqi") or {}

        return build_record(
            city=city_name,
            time_value=(data.get("time") or {}).get("s"),
            station=station_name,
            aqi=data.get("aqi"),
            pm25=(iaqi.get("pm25") or {}).get("v"),
            pm10=(iaqi.get("pm10") or {}).get("v"),
            co=(iaqi.get("co") or {}).get("v"),
            no2=(iaqi.get("no2") or {}).get("v"),
            o3=(iaqi.get("o3") or {}).get("v"),
        )
    except Exception as exc:
        logger.debug("[WAQI DETAIL ERROR] %s - %s: %s", city_name, station_name, exc)
        return None


def api_search_terms(profile: Dict, max_terms: int = 2) -> List[str]:
    terms = [profile["name"], profile["slug"], *(profile.get("aliases") or [])]
    unique_terms = []
    seen = set()

    for term in terms:
        key = str(term).lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_terms.append(term)
        if len(unique_terms) >= max_terms:
            break

    return unique_terms


def station_matches_profile(station_name: str, profile: Dict) -> bool:
    normalized_station = strip_accents(station_name)
    if any(marker in normalized_station for marker in VIETNAM_MARKERS):
        return True

    city_terms = [profile["name"], profile["slug"], *(profile.get("aliases") or [])]
    normalized_terms = [strip_accents(term).replace("-", " ") for term in city_terms]
    return any(term and term in normalized_station.replace("-", " ") for term in normalized_terms)


def discover_stations(profile: Dict, max_terms: int = 2, max_stations: int = MAX_STATIONS_PER_TERM) -> List[Dict]:
    stations = []
    seen_uid = set()

    for term in api_search_terms(profile, max_terms=max_terms):
        try:
            response = requests.get(
                WAQI_SEARCH_URL,
                params={"token": WAQI_TOKEN, "keyword": term},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()

            if payload.get("status") != "ok":
                continue

            for station in payload.get("data") or []:
                uid = station.get("uid")
                station_name = (station.get("station") or {}).get("name") or ""
                if not uid or uid in seen_uid:
                    continue
                if not station_matches_profile(station_name, profile):
                    continue

                seen_uid.add(uid)
                stations.append({
                    "uid": uid,
                    "name": station_name or f"WAQI {uid}",
                })
                if len(stations) >= max_stations:
                    return stations

        except Exception as exc:
            logger.warning("[WAQI SEARCH ERROR] %s - %s: %s", profile["name"], term, exc)

    return stations


def fetch_records_from_stations(city_name: str, stations: List[Dict]) -> List[Dict]:
    records = []
    for station in stations:
        record = fetch_station_detail(station["uid"], city_name, station["name"])
        if record:
            records.append(record)
    return records


def fetch_from_api(
    profile: Dict,
    max_terms: int = 2,
    max_stations: int = MAX_STATIONS_PER_TERM,
    station_cache: Optional[Dict[str, List[Dict]]] = None,
) -> List[Dict]:
    city_name = profile["name"]
    cache_key = profile["slug"]

    if station_cache is not None and cache_key in station_cache:
        return fetch_records_from_stations(city_name, station_cache[cache_key])

    stations = discover_stations(profile, max_terms=max_terms, max_stations=max_stations)
    if station_cache is not None:
        station_cache[cache_key] = stations

    return fetch_records_from_stations(city_name, stations)


def can_scrape_iqair() -> bool:
    checker = RobotsChecker(IQAIR_BASE_URL, user_agent=HEADERS["User-Agent"])
    return checker.fetch_robots() and checker.is_allowed("/vi/vietnam")


def parse_iqair_html(html: str, city_name: str) -> Optional[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    aqi_el = soup.select_one(".aqi-value__value, [data-testid='aqi-value']")
    aqi = safe_float(aqi_el.get_text(strip=True)) if aqi_el else None
    pm25 = None
    pm10 = None

    for row in soup.select(".pollutant-concentration, .aqi-overview-detail__main-pollutant"):
        text = row.get_text(" ", strip=True).lower()
        value_el = row.select_one(".pollutant-concentration__value, .value")
        value = safe_float(value_el.get_text(strip=True) if value_el else None)
        if "pm2.5" in text or "pm 2.5" in text:
            pm25 = value
        elif "pm10" in text or "pm 10" in text:
            pm10 = value

    return build_record(
        city=city_name,
        time_value=datetime.now(),
        station="iqair_html",
        aqi=aqi,
        pm25=pm25,
        pm10=pm10,
    )


def scrape_iqair_city(city_name: str, slug: str) -> Optional[Dict]:
    try:
        url = urljoin(IQAIR_VIETNAM_URL + "/", slug)
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return parse_iqair_html(response.text, city_name)
    except Exception as exc:
        logger.warning("[IQAIR HTML ERROR] %s: %s", city_name, exc)
        return None


def crawl_city(
    profile: Dict,
    allow_html: bool = False,
    max_terms: int = 2,
    max_stations: int = MAX_STATIONS_PER_TERM,
    verbose: bool = False,
    station_cache: Optional[Dict[str, List[Dict]]] = None,
) -> List[Dict]:
    city_name = profile["name"]
    records = fetch_from_api(
        profile,
        max_terms=max_terms,
        max_stations=max_stations,
        station_cache=station_cache,
    )

    if records:
        if verbose:
            print(f"[API OK] {city_name}: {len(records)} records")
        return records

    if allow_html:
        html_record = scrape_iqair_city(city_name, profile["slug"])
        if html_record:
            if verbose:
                print(f"[HTML OK] {city_name}: 1 record")
            return [html_record]

    if verbose:
        print(f"[NO DATA] {city_name}")
    return []


def fetch_data(
    target_records: int = 1000,
    max_rounds: int = 12,
    sleep_seconds: float = 0,
    use_html_fallback: bool = False,
    max_terms: int = 5,
    max_stations: int = MAX_STATIONS_PER_TERM,
    verbose: bool = False,
) -> List[Dict]:
    print("===== CRAWL/SCRAPE/API START =====")

    all_records = []
    seen_keys = set()
    station_cache = {}
    allow_html = use_html_fallback and can_scrape_iqair()
    if not allow_html:
        print("[CRAWL MODE] API only.")

    for round_index in range(max_rounds):
        profiles = CITY_PROFILES[:]
        random.shuffle(profiles)
        collected_at = datetime.now().replace(microsecond=0) + timedelta(seconds=round_index)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(crawl_city, profile, allow_html, max_terms, max_stations, verbose, station_cache)
                for profile in profiles
            ]

            for future in as_completed(futures):
                for record in future.result():
                    record["time"] = collected_at
                    key = (record["city"], record["time"], record.get("station"))
                    if key in seen_keys:
                        continue

                    seen_keys.add(key)
                    all_records.append(record)

                    if len(all_records) >= target_records:
                        print(f"TOTAL FETCHED: {len(all_records)} records")
                        return all_records

        print(f"[ROUND {round_index + 1}] fetched unique: {len(all_records)}")
        if len(all_records) >= target_records:
            break
        if sleep_seconds:
            time.sleep(sleep_seconds)

    print(f"TOTAL FETCHED: {len(all_records)} records")
    return all_records
