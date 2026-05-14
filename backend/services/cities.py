import unicodedata


def profile(slug, name, lat, lon, country="Vietnam", aliases=None):
    aliases = aliases or []
    return {
        "slug": slug,
        "name": name,
        "country": country,
        "aliases": aliases,
        "coords": [lat, lon],
    }


CITY_PROFILES = [
    profile("hanoi", "Hà Nội", 21.03, 105.85, aliases=["hanoi", "ha noi"]),
    profile(
        "ho-chi-minh-city",
        "TP. Hồ Chí Minh",
        10.82,
        106.63,
        aliases=["ho chi minh", "ho-chi-minh", "ho chi minh city", "saigon", "sai gon", "tp hcm", "tphcm", "hcm"],
    ),
    profile("danang", "Đà Nẵng", 16.05, 108.20, aliases=["danang", "da nang"]),
    profile("hue", "Huế", 16.47, 107.59),
    profile("haiphong", "Hải Phòng", 20.85, 106.68, aliases=["haiphong", "hai phong"]),
    profile("can-tho", "Cần Thơ", 10.04, 105.78, aliases=["can tho"]),
    profile("bac-ninh", "Bắc Ninh", 21.18, 106.07),
    profile("bac-giang", "Bắc Giang", 21.27, 106.19),
    profile("vinh-phuc", "Vĩnh Phúc", 21.31, 105.60),
    profile("quang-ninh", "Quảng Ninh", 21.01, 107.30),
    profile("thai-nguyen", "Thái Nguyên", 21.59, 105.85),
    profile("ha-nam", "Hà Nam", 20.54, 105.92),
    profile("nam-dinh", "Nam Định", 20.42, 106.17),
    profile("ninh-binh", "Ninh Bình", 20.25, 105.97),
    profile("thanh-hoa", "Thanh Hóa", 19.81, 105.78),
    profile("nghe-an", "Nghệ An", 18.67, 105.69),
    profile("ha-tinh", "Hà Tĩnh", 18.34, 105.91),
    profile("quang-binh", "Quảng Bình", 17.47, 106.62),
    profile("quang-tri", "Quảng Trị", 16.74, 107.19),
    profile("quang-nam", "Quảng Nam", 15.88, 108.33),
    profile("quang-ngai", "Quảng Ngãi", 15.12, 108.80),
    profile("binh-dinh", "Bình Định", 14.17, 109.03),
    profile("phu-yen", "Phú Yên", 13.09, 109.30),
    profile("khanh-hoa", "Khánh Hòa", 12.24, 109.19),
    profile("ninh-thuan", "Ninh Thuận", 11.57, 108.99),
    profile("binh-thuan", "Bình Thuận", 10.93, 108.10),
    profile("kon-tum", "Kon Tum", 14.35, 108.00),
    profile("gia-lai", "Gia Lai", 13.98, 108.00),
    profile("dak-lak", "Đắk Lắk", 12.67, 108.04, aliases=["dak lak", "daklak", "buon ma thuot"]),
    profile("dak-nong", "Đắk Nông", 12.26, 107.61),
    profile("lam-dong", "Lâm Đồng", 11.58, 108.44),
    profile("binh-phuoc", "Bình Phước", 11.75, 106.89),
    profile("tay-ninh", "Tây Ninh", 11.31, 106.10),
    profile("binh-duong", "Bình Dương", 11.17, 106.60),
    profile("dong-nai", "Đồng Nai", 10.95, 106.82),
    profile("ba-ria-vung-tau", "Bà Rịa - Vũng Tàu", 10.54, 107.24, aliases=["ba ria vung tau"]),
    profile("long-an", "Long An", 10.54, 106.41),
    profile("tien-giang", "Tiền Giang", 10.36, 106.36),
    profile("ben-tre", "Bến Tre", 10.24, 106.38),
    profile("tra-vinh", "Trà Vinh", 9.95, 106.34),
    profile("vinh-long", "Vĩnh Long", 10.25, 105.97),
    profile("dong-thap", "Đồng Tháp", 10.46, 105.63),
    profile("an-giang", "An Giang", 10.39, 105.44),
    profile("kien-giang", "Kiên Giang", 10.01, 105.08),
    profile("hau-giang", "Hậu Giang", 9.79, 105.47),
    profile("soc-trang", "Sóc Trăng", 9.60, 105.97),
    profile("bac-lieu", "Bạc Liêu", 9.29, 105.73),
    profile("ca-mau", "Cà Mau", 9.18, 105.15),
    profile("thu-duc", "Thủ Đức", 10.85, 106.75),
    profile("bien-hoa", "Biên Hòa", 10.95, 106.82),
    profile("vung-tau", "Vũng Tàu", 10.41, 107.13),
    profile("nha-trang", "Nha Trang", 12.25, 109.19),
    profile("my-tho", "Mỹ Tho", 10.36, 106.36),
    profile("vinh", "Vinh", 18.67, 105.69),
    profile("quy-nhon", "Quy Nhơn", 13.77, 109.23),
    profile("pleiku", "Pleiku", 13.98, 108.00),
    profile("buon-ma-thuot", "Buôn Ma Thuột", 12.67, 108.04, aliases=["buon ma thuot", "buon me thuot"]),
    profile("da-lat", "Đà Lạt", 11.94, 108.44, aliases=["da lat", "dalat"]),
    profile("long-xuyen", "Long Xuyên", 10.39, 105.44),
    profile("rach-gia", "Rạch Giá", 10.01, 105.08),
    profile("ca-mau-city", "TP. Cà Mau", 9.18, 105.15, aliases=["ca mau city", "tp ca mau"]),
    profile("soc-trang-city", "TP. Sóc Trăng", 9.60, 105.97, aliases=["soc trang city", "tp soc trang"]),
    profile("bac-lieu-city", "TP. Bạc Liêu", 9.29, 105.73, aliases=["bac lieu city", "tp bac lieu"]),
    profile("can-tho-ninh-kieu", "Ninh Kiều", 10.03, 105.78),
    profile("thai-nguyen-city", "TP. Thái Nguyên", 21.59, 105.85, aliases=["thai nguyen city", "tp thai nguyen"]),
    profile("viet-tri", "Việt Trì", 21.32, 105.40),
    profile("lao-cai-city", "TP. Lào Cai", 22.48, 103.97, aliases=["lao cai", "tp lao cai"]),
    profile("yen-bai-city", "TP. Yên Bái", 21.72, 104.87, aliases=["yen bai", "tp yen bai"]),
    profile("hoa-binh-city", "TP. Hòa Bình", 20.81, 105.34, aliases=["hoa binh", "tp hoa binh"]),
    profile("son-la-city", "TP. Sơn La", 21.33, 103.90, aliases=["son la", "tp son la"]),
    profile("dien-bien", "Điện Biên Phủ", 21.39, 103.02, aliases=["dien bien", "dien bien phu"]),
    profile("tuyen-quang", "TP. Tuyên Quang", 21.82, 105.21, aliases=["tuyen quang", "tp tuyen quang"]),
    profile("cao-bang", "TP. Cao Bằng", 22.66, 106.26, aliases=["cao bang", "tp cao bang"]),
    profile("ha-giang", "TP. Hà Giang", 22.83, 104.98, aliases=["ha giang", "tp ha giang"]),
    profile("thu-dau-mot", "Thủ Dầu Một", 10.98, 106.65),
    profile("di-an", "Dĩ An", 10.91, 106.77),
    profile("thuan-an", "Thuận An", 10.93, 106.72),
    profile("tan-uyen", "Tân Uyên", 11.05, 106.75),
    profile("ben-cat", "Bến Cát", 11.13, 106.60),
    profile("long-khanh", "Long Khánh", 10.92, 107.15),
    profile("ba-ria", "Bà Rịa", 10.50, 107.17),
    profile("phu-my", "Phú Mỹ", 10.58, 107.05),
    profile("tan-an", "Tân An", 10.54, 106.41),
    profile("go-cong", "Gò Công", 10.36, 106.68),
    profile("sa-dec", "Sa Đéc", 10.29, 105.76),
    profile("hong-ngu", "Hồng Ngự", 10.81, 105.33),
    profile("chau-doc", "Châu Đốc", 10.70, 105.11),
    profile("ha-tien", "Hà Tiên", 10.38, 104.48),
    profile("phu-quoc", "Phú Quốc", 10.22, 103.96),
    profile("vi-thanh", "Vị Thanh", 9.78, 105.47),
    profile("nga-bay", "Ngã Bảy", 9.81, 105.75),
    profile("sam-son", "Sầm Sơn", 19.74, 105.90),
    profile("dong-hoi", "Đồng Hới", 17.48, 106.60),
    profile("bangkok", "Bangkok", 13.7563, 100.5018, "Thailand"),
    profile("singapore", "Singapore", 1.3521, 103.8198, "Singapore"),
    profile("kuala-lumpur", "Kuala Lumpur", 3.1390, 101.6869, "Malaysia", aliases=["kuala lumpur"]),
    profile("jakarta", "Jakarta", -6.2088, 106.8456, "Indonesia"),
    profile("manila", "Manila", 14.5995, 120.9842, "Philippines"),
    profile("phnom-penh", "Phnom Penh", 11.5564, 104.9282, "Cambodia", aliases=["phnom penh"]),
    profile("vientiane", "Vientiane", 17.9757, 102.6331, "Laos"),
    profile("yangon", "Yangon", 16.8409, 96.1735, "Myanmar"),
    profile("beijing", "Beijing", 39.9042, 116.4074, "China"),
    profile("shanghai", "Shanghai", 31.2304, 121.4737, "China"),
    profile("hong-kong", "Hong Kong", 22.3193, 114.1694, "Hong Kong", aliases=["hong kong"]),
    profile("tokyo", "Tokyo", 35.6762, 139.6503, "Japan"),
    profile("seoul", "Seoul", 37.5665, 126.9780, "South Korea"),
    profile("taipei", "Taipei", 25.0330, 121.5654, "Taiwan"),
    profile("new-delhi", "New Delhi", 28.6139, 77.2090, "India", aliases=["new delhi", "delhi"]),
]


def repair_mojibake(value: str) -> str:
    if not value:
        return ""

    candidates = [value]
    for encoding in ("cp1252", "latin1"):
        try:
            candidates.append(value.encode(encoding).decode("utf-8"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    return min(candidates, key=lambda item: item.count("Ã") + item.count("Ä") + item.count("á»"))


def strip_accents(value: str) -> str:
    value = repair_mojibake(value or "")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.replace("đ", "d").replace("Đ", "D").lower().strip()


def names_for_profile(city_profile):
    return [
        city_profile["name"],
        city_profile["slug"],
        strip_accents(city_profile["name"]),
        *city_profile.get("aliases", []),
    ]


def canonical_city_name(value: str) -> str:
    if not value:
        return ""

    repaired_value = repair_mojibake(value)
    normalized_value = strip_accents(repaired_value)

    for city_profile in CITY_PROFILES:
        if any(strip_accents(name) == normalized_value for name in names_for_profile(city_profile)):
            return city_profile["name"]

    for city_profile in CITY_PROFILES:
        if any(strip_accents(name) in normalized_value for name in names_for_profile(city_profile)):
            return city_profile["name"]

    return repaired_value


def city_search_terms(value: str):
    canonical = canonical_city_name(value)
    terms = {value, repair_mojibake(value), canonical, strip_accents(value), strip_accents(canonical)}

    for city_profile in CITY_PROFILES:
        if city_profile["name"] == canonical:
            terms.update(names_for_profile(city_profile))
            terms.update(strip_accents(name) for name in names_for_profile(city_profile))

    return sorted(term for term in terms if term)


def city_coords():
    return {city_profile["name"]: city_profile["coords"] for city_profile in CITY_PROFILES}


CITY_DISPLAY_NAMES = {city_profile["slug"]: city_profile["name"] for city_profile in CITY_PROFILES}
