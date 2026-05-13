import unicodedata


CITY_PROFILES = [
    {
        "slug": "hanoi",
        "name": "Hà Nội",
        "aliases": ["hanoi", "ha noi", "hà nội", "Hanoi", "Hà Nội"],
        "coords": [21.03, 105.85],
    },
    {
        "slug": "ho-chi-minh-city",
        "name": "TP. Hồ Chí Minh",
        "aliases": [
            "ho chi minh",
            "ho-chi-minh-city",
            "saigon",
            "sai gon",
            "tp hcm",
            "tphcm",
            "hcm",
            "hồ chí minh",
            "TP. Hồ Chí Minh",
            "Ho Chi Minh City",
        ],
        "coords": [10.82, 106.63],
    },
    {
        "slug": "danang",
        "name": "Đà Nẵng",
        "aliases": ["danang", "da nang", "đà nẵng", "Da Nang", "Đà Nẵng"],
        "coords": [16.05, 108.20],
    },
    {
        "slug": "hue",
        "name": "Huế",
        "aliases": ["hue", "huế", "Hue", "Huế"],
        "coords": [16.47, 107.59],
    },
    {
        "slug": "haiphong",
        "name": "Hải Phòng",
        "aliases": ["haiphong", "hai phong", "hải phòng", "Hai Phong", "Hải Phòng"],
        "coords": [20.85, 106.68],
    },
    {
        "slug": "can-tho",
        "name": "Cần Thơ",
        "aliases": ["can-tho", "can tho", "cần thơ", "Can Tho", "Cần Thơ"],
        "coords": [10.04, 105.78],
    },
    # Các thành phố bổ sung
    {
        "slug": "bac-ninh",
        "name": "Bắc Ninh",
        "aliases": ["bac ninh", "bắc ninh", "Bac Ninh", "Bắc Ninh"],
        "coords": [21.18, 106.07],
    },
    {
        "slug": "bac-giang",
        "name": "Bắc Giang",
        "aliases": ["bac giang", "bắc giang", "Bac Giang", "Bắc Giang"],
        "coords": [21.27, 106.19],
    },
    {
        "slug": "vinh-phuc",
        "name": "Vĩnh Phúc",
        "aliases": ["vinh phuc", "vĩnh phúc", "Vinh Phuc", "Vĩnh Phúc"],
        "coords": [21.31, 105.60],
    },
    {
        "slug": "quang-ninh",
        "name": "Quảng Ninh",
        "aliases": ["quang ninh", "quảng ninh", "Quang Ninh", "Quảng Ninh"],
        "coords": [21.01, 107.30],
    },
    {
        "slug": "thai-nguyen",
        "name": "Thái Nguyên",
        "aliases": ["thai nguyen", "thái nguyên", "Thai Nguyen", "Thái Nguyên"],
        "coords": [21.59, 105.85],
    },
    {
        "slug": "ha-nam",
        "name": "Hà Nam",
        "aliases": ["ha nam", "hà nam", "Ha Nam", "Hà Nam"],
        "coords": [20.54, 105.92],
    },
    {
        "slug": "nam-dinh",
        "name": "Nam Định",
        "aliases": ["nam dinh", "nam định", "Nam Dinh", "Nam Định"],
        "coords": [20.42, 106.17],
    },
    {
        "slug": "ninh-binh",
        "name": "Ninh Bình",
        "aliases": ["ninh binh", "ninh bình", "Ninh Binh", "Ninh Bình"],
        "coords": [20.25, 105.97],
    },
    {
        "slug": "thanh-hoa",
        "name": "Thanh Hóa",
        "aliases": ["thanh hoa", "thanh hóa", "Thanh Hoa", "Thanh Hóa"],
        "coords": [19.81, 105.78],
    },
    {
        "slug": "nghe-an",
        "name": "Nghệ An",
        "aliases": ["nghe an", "nghệ an", "Nghe An", "Nghệ An"],
        "coords": [18.67, 105.69],
    },
    {
        "slug": "ha-tinh",
        "name": "Hà Tĩnh",
        "aliases": ["ha tinh", "hà tĩnh", "Ha Tinh", "Hà Tĩnh"],
        "coords": [18.34, 105.91],
    },
    {
        "slug": "quang-binh",
        "name": "Quảng Bình",
        "aliases": ["quang binh", "quảng bình", "Quang Binh", "Quảng Bình"],
        "coords": [17.47, 106.62],
    },
    {
        "slug": "quang-tri",
        "name": "Quảng Trị",
        "aliases": ["quang tri", "quảng trị", "Quang Tri", "Quảng Trị"],
        "coords": [16.74, 107.19],
    },
    {
        "slug": "quang-nam",
        "name": "Quảng Nam",
        "aliases": ["quang nam", "quảng nam", "Quang Nam", "Quảng Nam"],
        "coords": [15.88, 108.33],
    },
    {
        "slug": "quang-ngai",
        "name": "Quảng Ngãi",
        "aliases": ["quang ngai", "quảng ngãi", "Quang Ngai", "Quảng Ngãi"],
        "coords": [15.12, 108.80],
    },
    {
        "slug": "binh-dinh",
        "name": "Bình Định",
        "aliases": ["binh dinh", "bình định", "Binh Dinh", "Bình Định"],
        "coords": [14.17, 109.03],
    },
    {
        "slug": "phu-yen",
        "name": "Phú Yên",
        "aliases": ["phu yen", "phú yên", "Phu Yen", "Phú Yên"],
        "coords": [13.09, 109.30],
    },
    {
        "slug": "khanh-hoa",
        "name": "Khánh Hòa",
        "aliases": ["khanh hoa", "khánh hòa", "Khanh Hoa", "Khánh Hòa"],
        "coords": [12.24, 109.19],
    },
    {
        "slug": "ninh-thuan",
        "name": "Ninh Thuận",
        "aliases": ["ninh thuan", "ninh thuận", "Ninh Thuan", "Ninh Thuận"],
        "coords": [11.57, 108.99],
    },
    {
        "slug": "binh-thuan",
        "name": "Bình Thuận",
        "aliases": ["binh thuan", "bình thuận", "Binh Thuan", "Bình Thuận"],
        "coords": [10.93, 108.10],
    },
    {
        "slug": "kon-tum",
        "name": "Kon Tum",
        "aliases": ["kon tum", "kon tum", "Kon Tum", "Kon Tum"],
        "coords": [14.35, 108.00],
    },
    {
        "slug": "gia-lai",
        "name": "Gia Lai",
        "aliases": ["gia lai", "gia lai", "Gia Lai", "Gia Lai"],
        "coords": [13.98, 108.00],
    },
    {
        "slug": "dak-lak",
        "name": "Đắk Lắk",
        "aliases": ["dak lak", "đắk lắk", "Dak Lak", "Đắk Lắk"],
        "coords": [12.67, 108.04],
    },
    {
        "slug": "dak-nong",
        "name": "Đắk Nông",
        "aliases": ["dak nong", "đắk nông", "Dak Nong", "Đắk Nông"],
        "coords": [12.26, 107.61],
    },
    {
        "slug": "lam-dong",
        "name": "Lâm Đồng",
        "aliases": ["lam dong", "lâm đồng", "Lam Dong", "Lâm Đồng"],
        "coords": [11.58, 108.44],
    },
    {
        "slug": "binh-phuoc",
        "name": "Bình Phước",
        "aliases": ["binh phuoc", "bình phước", "Binh Phuoc", "Bình Phước"],
        "coords": [11.75, 106.89],
    },
    {
        "slug": "tay-ninh",
        "name": "Tây Ninh",
        "aliases": ["tay ninh", "tây ninh", "Tay Ninh", "Tây Ninh"],
        "coords": [11.31, 106.10],
    },
    {
        "slug": "binh-duong",
        "name": "Bình Dương",
        "aliases": ["binh duong", "bình dương", "Binh Duong", "Bình Dương"],
        "coords": [11.17, 106.60],
    },
    {
        "slug": "dong-nai",
        "name": "Đồng Nai",
        "aliases": ["dong nai", "đồng nai", "Dong Nai", "Đồng Nai"],
        "coords": [10.95, 106.82],
    },
    {
        "slug": "ba-ria-vung-tau",
        "name": "Bà Rịa - Vũng Tàu",
        "aliases": ["ba ria vung tau", "bà rịa vũng tàu", "Ba Ria Vung Tau", "Bà Rịa - Vũng Tàu"],
        "coords": [10.54, 107.24],
    },
    {
        "slug": "long-an",
        "name": "Long An",
        "aliases": ["long an", "long an", "Long An", "Long An"],
        "coords": [10.54, 106.41],
    },
    {
        "slug": "tien-giang",
        "name": "Tiền Giang",
        "aliases": ["tien giang", "tiền giang", "Tien Giang", "Tiền Giang"],
        "coords": [10.36, 106.36],
    },
    {
        "slug": "ben-tre",
        "name": "Bến Tre",
        "aliases": ["ben tre", "bến tre", "Ben Tre", "Bến Tre"],
        "coords": [10.24, 106.38],
    },
    {
        "slug": "tra-vinh",
        "name": "Trà Vinh",
        "aliases": ["tra vinh", "trà vinh", "Tra Vinh", "Trà Vinh"],
        "coords": [9.95, 106.34],
    },
    {
        "slug": "vinh-long",
        "name": "Vĩnh Long",
        "aliases": ["vinh long", "vĩnh long", "Vinh Long", "Vĩnh Long"],
        "coords": [10.25, 105.97],
    },
    {
        "slug": "dong-thap",
        "name": "Đồng Tháp",
        "aliases": ["dong thap", "đồng tháp", "Dong Thap", "Đồng Tháp"],
        "coords": [10.46, 105.63],
    },
    {
        "slug": "an-giang",
        "name": "An Giang",
        "aliases": ["an giang", "an giang", "An Giang", "An Giang"],
        "coords": [10.39, 105.44],
    },
    {
        "slug": "kien-giang",
        "name": "Kiên Giang",
        "aliases": ["kien giang", "kiên giang", "Kien Giang", "Kiên Giang"],
        "coords": [10.01, 105.08],
    },
    {
        "slug": "hau-giang",
        "name": "Hậu Giang",
        "aliases": ["hau giang", "hậu giang", "Hau Giang", "Hậu Giang"],
        "coords": [9.79, 105.47],
    },
    {
        "slug": "soc-trang",
        "name": "Sóc Trăng",
        "aliases": ["soc trang", "sóc trăng", "Soc Trang", "Sóc Trăng"],
        "coords": [9.60, 105.97],
    },
    {
        "slug": "bac-lieu",
        "name": "Bạc Liêu",
        "aliases": ["bac lieu", "bạc liêu", "Bac Lieu", "Bạc Liêu"],
        "coords": [9.29, 105.73],
    },
    {
        "slug": "ca-mau",
        "name": "Cà Mau",
        "aliases": ["ca mau", "cà mau", "Ca Mau", "Cà Mau"],
        "coords": [9.18, 105.15],
    },
]
# =========================
# 🔥 BỔ SUNG THÀNH PHỐ (CITY LEVEL)
# =========================
CITY_PROFILES += [

    {"slug": "thu-duc", "name": "Thủ Đức", "aliases": ["thu duc"], "coords": [10.85,106.75]},
    {"slug": "bien-hoa", "name": "Biên Hòa", "aliases": ["bien hoa"], "coords": [10.95,106.82]},
    {"slug": "vung-tau", "name": "Vũng Tàu", "aliases": ["vung tau"], "coords": [10.41,107.13]},
    {"slug": "nha-trang", "name": "Nha Trang", "aliases": ["nha trang"], "coords": [12.25,109.19]},
    {"slug": "my-tho", "name": "Mỹ Tho", "aliases": ["my tho"], "coords": [10.36,106.36]},
    {"slug": "vinh", "name": "Vinh", "aliases": ["vinh"], "coords": [18.67,105.69]},
    {"slug": "quy-nhon", "name": "Quy Nhơn", "aliases": ["quy nhon"], "coords": [13.77,109.23]},
    {"slug": "pleiku", "name": "Pleiku", "aliases": ["pleiku"], "coords": [13.98,108.00]},
    {"slug": "buon-ma-thuot", "name": "Buôn Ma Thuột", "aliases": ["buon ma thuot"], "coords": [12.67,108.04]},
    {"slug": "da-lat", "name": "Đà Lạt", "aliases": ["da lat"], "coords": [11.94,108.44]},
    {"slug": "long-xuyen", "name": "Long Xuyên", "aliases": ["long xuyen"], "coords": [10.39,105.44]},
    {"slug": "rach-gia", "name": "Rạch Giá", "aliases": ["rach gia"], "coords": [10.01,105.08]},
    {"slug": "ca-mau-city", "name": "TP. Cà Mau", "aliases": ["ca mau"], "coords": [9.18,105.15]},
    {"slug": "soc-trang-city", "name": "TP. Sóc Trăng", "aliases": ["soc trang"], "coords": [9.60,105.97]},
    {"slug": "bac-lieu-city", "name": "TP. Bạc Liêu", "aliases": ["bac lieu"], "coords": [9.29,105.73]},
    {"slug": "can-tho-ninh-kieu", "name": "Ninh Kiều", "aliases": ["ninh kieu"], "coords": [10.03,105.78]},
    {"slug": "thai-nguyen-city", "name": "TP. Thái Nguyên", "aliases": ["thai nguyen"], "coords": [21.59,105.85]},
    {"slug": "viet-tri", "name": "Việt Trì", "aliases": ["viet tri"], "coords": [21.32,105.40]},
    {"slug": "lao-cai-city", "name": "TP. Lào Cai", "aliases": ["lao cai"], "coords": [22.48,103.97]},
    {"slug": "yen-bai-city", "name": "TP. Yên Bái", "aliases": ["yen bai"], "coords": [21.72,104.87]},
    {"slug": "hoa-binh-city", "name": "TP. Hòa Bình", "aliases": ["hoa binh"], "coords": [20.81,105.34]},
    {"slug": "son-la-city", "name": "TP. Sơn La", "aliases": ["son la"], "coords": [21.33,103.90]},
    {"slug": "dien-bien", "name": "Điện Biên Phủ", "aliases": ["dien bien"], "coords": [21.39,103.02]},
    {"slug": "tuyen-quang", "name": "TP. Tuyên Quang", "aliases": ["tuyen quang"], "coords": [21.82,105.21]},
    {"slug": "cao-bang", "name": "TP. Cao Bằng", "aliases": ["cao bang"], "coords": [22.66,106.26]},
    {"slug": "ha-giang", "name": "TP. Hà Giang", "aliases": ["ha giang"], "coords": [22.83,104.98]},
]
MOJIBAKE_NAMES = {
    "HÃ  Ná»™i": "Hà Nội",
    "TP. Há»“ ChÃ­ Minh": "TP. Hồ Chí Minh",
    "ÄÃ  Náºµng": "Đà Nẵng",
    "Huáº¿": "Huế",
    "Háº£i PhÃ²ng": "Hải Phòng",
    "Cáº§n ThÆ¡": "Cần Thơ",
    "Báº¯c Ninh": "Bắc Ninh",
    "Báº¯c Giang": "Bắc Giang",
    "VÄ©nh PhÃºc": "Vĩnh Phúc",
    "Quáº£ng Ninh": "Quảng Ninh",
    "ThÃ¡i NguyÃªn": "Thái Nguyên",
    "HÃ  Nam": "Hà Nam",
    "Nam Äá»‹nh": "Nam Định",
    "Ninh BÃ¬nh": "Ninh Bình",
    "Thanh HÃ³a": "Thanh Hóa",
    "Nghá»‡ An": "Nghệ An",
    "HÃ  TÄ©nh": "Hà Tĩnh",
    "Quáº£ng BÃ¬nh": "Quảng Bình",
    "Quáº£ng Trá»‹": "Quảng Trị",
    "Quáº£ng Nam": "Quảng Nam",
    "Quáº£ng NgÃ£i": "Quảng Ngãi",
    "BÃ¬nh Äá»‹nh": "Bình Định",
    "PhÃº YÃªn": "Phú Yên",
    "KhÃ¡nh HÃ²a": "Khánh Hòa",
    "Ninh Thuáº­n": "Ninh Thuận",
    "BÃ¬nh Thuáº­n": "Bình Thuận",
    "Kon Tum": "Kon Tum",
    "Gia Lai": "Gia Lai",
    "Äáº¯k Láº¯k": "Đắk Lắk",
    "Äáº¯k NÃ´ng": "Đắk Nông",
    "LÃ¢m Äá»“ng": "Lâm Đồng",
    "BÃ¬nh PhÃºc": "Bình Phước",
    "TÃ¢y Ninh": "Tây Ninh",
    "BÃ¬nh DÆ°Æ¡ng": "Bình Dương",
    "Äá»“ng Nai": "Đồng Nai",
    "BÃ  Rá»‹a - VÅ©ng TÃ u": "Bà Rịa - Vũng Tàu",
    "Long An": "Long An",
    "TiÃªn Giang": "Tiền Giang",
    "Báº¿n Tre": "Bến Tre",
    "TrÃ  Vinh": "Trà Vinh",
    "VÄ©nh Long": "Vĩnh Long",
    "Äá»“ng ThÃ¡p": "Đồng Tháp",
    "An Giang": "An Giang",
    "KiÃªn Giang": "Kiên Giang",
    "Háº­u Giang": "Hậu Giang",
    "SÃ³c TrÄƒng": "Sóc Trăng",
    "Báº¡c LiÃªu": "Bạc Liêu",
    "CÃ  Mau": "Cà Mau",
}
CITY_PROFILES += [

    {"slug": "thu-dau-mot", "name": "Thủ Dầu Một", "aliases": ["thu dau mot"], "coords": [10.98,106.65]},
    {"slug": "di-an", "name": "Dĩ An", "aliases": ["di an"], "coords": [10.91,106.77]},
    {"slug": "thuan-an", "name": "Thuận An", "aliases": ["thuan an"], "coords": [10.93,106.72]},
    {"slug": "tan-uyen", "name": "Tân Uyên", "aliases": ["tan uyen"], "coords": [11.05,106.75]},
    {"slug": "ben-cat", "name": "Bến Cát", "aliases": ["ben cat"], "coords": [11.13,106.60]},

    {"slug": "long-khanh", "name": "Long Khánh", "aliases": ["long khanh"], "coords": [10.92,107.15]},

    {"slug": "ba-ria", "name": "Bà Rịa", "aliases": ["ba ria"], "coords": [10.50,107.17]},
    {"slug": "phu-my", "name": "Phú Mỹ", "aliases": ["phu my"], "coords": [10.58,107.05]},

    {"slug": "tan-an", "name": "Tân An", "aliases": ["tan an"], "coords": [10.54,106.41]},

    {"slug": "go-cong", "name": "Gò Công", "aliases": ["go cong"], "coords": [10.36,106.68]},

    {"slug": "sa-dec", "name": "Sa Đéc", "aliases": ["sa dec"], "coords": [10.29,105.76]},
    {"slug": "hong-ngu", "name": "Hồng Ngự", "aliases": ["hong ngu"], "coords": [10.81,105.33]},

    {"slug": "chau-doc", "name": "Châu Đốc", "aliases": ["chau doc"], "coords": [10.70,105.11]},

    {"slug": "ha-tien", "name": "Hà Tiên", "aliases": ["ha tien"], "coords": [10.38,104.48]},
    {"slug": "phu-quoc", "name": "Phú Quốc", "aliases": ["phu quoc"], "coords": [10.22,103.96]},

    {"slug": "vi-thanh", "name": "Vị Thanh", "aliases": ["vi thanh"], "coords": [9.78,105.47]},
    {"slug": "nga-bay", "name": "Ngã Bảy", "aliases": ["nga bay"], "coords": [9.81,105.75]},

    {"slug": "sam-son", "name": "Sầm Sơn", "aliases": ["sam son"], "coords": [19.74,105.90]},

    {"slug": "dong-hoi", "name": "Đồng Hới", "aliases": ["dong hoi"], "coords": [17.48,106.60]},

    {"slug": "dong-ha", "name": "Đông Hà", "aliases": ["dong ha"], "coords": [16.82,107.10]},

    {"slug": "tam-ky", "name": "Tam Kỳ", "aliases": ["tam ky"], "coords": [15.57,108.47]},
    {"slug": "hoi-an", "name": "Hội An", "aliases": ["hoi an"], "coords": [15.88,108.33]},

    {"slug": "tuy-hoa", "name": "Tuy Hòa", "aliases": ["tuy hoa"], "coords": [13.09,109.30]},

    {"slug": "cam-ranh", "name": "Cam Ranh", "aliases": ["cam ranh"], "coords": [11.92,109.15]},

    {"slug": "phan-rang", "name": "Phan Rang", "aliases": ["phan rang"], "coords": [11.57,108.99]},

    {"slug": "phan-thiet", "name": "Phan Thiết", "aliases": ["phan thiet"], "coords": [10.93,108.10]},

    {"slug": "bao-loc", "name": "Bảo Lộc", "aliases": ["bao loc"], "coords": [11.55,107.80]},

    {"slug": "dong-xoai", "name": "Đồng Xoài", "aliases": ["dong xoai"], "coords": [11.53,106.91]},

    {"slug": "tay-ninh-city", "name": "TP. Tây Ninh", "aliases": ["tay ninh"], "coords": [11.31,106.10]},

]

# Giu dung 93 thanh pho/khu vuc tai Viet Nam, sau do bo sung mot so thanh pho nuoc ngoai.
VIETNAM_CITY_COUNT = 93
CITY_PROFILES = CITY_PROFILES[:VIETNAM_CITY_COUNT]

FOREIGN_CITY_PROFILES = [
    {"slug": "bangkok", "name": "Bangkok", "country": "Thailand", "aliases": ["bangkok", "Bangkok"], "coords": [13.7563, 100.5018]},
    {"slug": "singapore", "name": "Singapore", "country": "Singapore", "aliases": ["singapore", "Singapore"], "coords": [1.3521, 103.8198]},
    {"slug": "kuala-lumpur", "name": "Kuala Lumpur", "country": "Malaysia", "aliases": ["kuala lumpur", "Kuala Lumpur"], "coords": [3.1390, 101.6869]},
    {"slug": "jakarta", "name": "Jakarta", "country": "Indonesia", "aliases": ["jakarta", "Jakarta"], "coords": [-6.2088, 106.8456]},
    {"slug": "manila", "name": "Manila", "country": "Philippines", "aliases": ["manila", "Manila"], "coords": [14.5995, 120.9842]},
    {"slug": "phnom-penh", "name": "Phnom Penh", "country": "Cambodia", "aliases": ["phnom penh", "Phnom Penh"], "coords": [11.5564, 104.9282]},
    {"slug": "vientiane", "name": "Vientiane", "country": "Laos", "aliases": ["vientiane", "Vientiane"], "coords": [17.9757, 102.6331]},
    {"slug": "yangon", "name": "Yangon", "country": "Myanmar", "aliases": ["yangon", "Yangon"], "coords": [16.8409, 96.1735]},
    {"slug": "beijing", "name": "Beijing", "country": "China", "aliases": ["beijing", "Beijing"], "coords": [39.9042, 116.4074]},
    {"slug": "shanghai", "name": "Shanghai", "country": "China", "aliases": ["shanghai", "Shanghai"], "coords": [31.2304, 121.4737]},
    {"slug": "hong-kong", "name": "Hong Kong", "country": "Hong Kong", "aliases": ["hong kong", "Hong Kong"], "coords": [22.3193, 114.1694]},
    {"slug": "tokyo", "name": "Tokyo", "country": "Japan", "aliases": ["tokyo", "Tokyo"], "coords": [35.6762, 139.6503]},
    {"slug": "seoul", "name": "Seoul", "country": "South Korea", "aliases": ["seoul", "Seoul"], "coords": [37.5665, 126.9780]},
    {"slug": "taipei", "name": "Taipei", "country": "Taiwan", "aliases": ["taipei", "Taipei"], "coords": [25.0330, 121.5654]},
    {"slug": "new-delhi", "name": "New Delhi", "country": "India", "aliases": ["new delhi", "New Delhi", "delhi"], "coords": [28.6139, 77.2090]},
]

CITY_PROFILES += FOREIGN_CITY_PROFILES

def strip_accents(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.replace("đ", "d").replace("Đ", "D").lower().strip()


def canonical_city_name(value: str) -> str:
    if not value:
        return ""

    if value in MOJIBAKE_NAMES:
        return MOJIBAKE_NAMES[value]

    normalized_value = strip_accents(value)

    # First prefer exact matches so city-level entries such as
    # "TP. Thai Nguyen" are not collapsed into the broader "Thai Nguyen".
    for profile in CITY_PROFILES:
        names = [profile["name"], profile["slug"], *profile["aliases"]]
        if any(strip_accents(name) == normalized_value for name in names):
            return profile["name"]

    for profile in CITY_PROFILES:
        names = [profile["name"], profile["slug"], *profile["aliases"]]
        if any(strip_accents(name) in normalized_value for name in names):
            return profile["name"]

    return value


def city_search_terms(value: str):
    canonical = canonical_city_name(value)
    terms = {value, canonical}

    for broken, fixed in MOJIBAKE_NAMES.items():
        if fixed == canonical or broken == value:
            terms.update([broken, fixed])

    for profile in CITY_PROFILES:
        if profile["name"] == canonical:
            terms.update(profile["aliases"])
            terms.add(profile["slug"])
            terms.add(strip_accents(profile["name"]))

    return [term for term in terms if term]


def city_coords():
    coords = {}
    for profile in CITY_PROFILES:
        coords[profile["name"]] = profile["coords"]
    return coords


# Mapping tên thành phố cho crawler
CITY_DISPLAY_NAMES = {
    profile["slug"]: profile["name"] for profile in CITY_PROFILES
}
