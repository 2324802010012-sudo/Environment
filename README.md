# Hệ thống thu thập, lưu trữ, tìm kiếm và xếp hạng chất lượng không khí

## 1. Giới thiệu đề tài

Ô nhiễm không khí là một vấn đề môi trường có ảnh hưởng trực tiếp đến sức khỏe cộng đồng, đặc biệt tại các đô thị lớn. Các chỉ số như AQI, PM2.5, PM10, CO, NO2, SO2 và O3 thường được sử dụng để đánh giá mức độ ô nhiễm và hỗ trợ người dân đưa ra quyết định trong sinh hoạt hằng ngày.

Dự án này xây dựng một hệ thống web có khả năng thu thập dữ liệu chất lượng không khí trực tiếp từ Internet, tiền xử lý dữ liệu, lưu trữ vào MySQL, cung cấp API truy vấn và hiển thị trực quan trên dashboard. Hệ thống cũng có thêm chức năng phân nhóm ô nhiễm bằng KMeans và dự đoán AQI bằng Linear Regression.

Nguồn dữ liệu duy nhất của hệ thống là **Open-Meteo Air Quality API**:

```text
https://open-meteo.com/en/docs/air-quality-api
```

Hệ thống không sử dụng dataset tải sẵn như CSV/Kaggle. Toàn bộ dữ liệu được lấy trực tiếp bằng code thông qua thư viện `requests`.

## 2. Phạm vi và mục tiêu

### 2.1. Phạm vi dữ liệu

- Khu vực theo dõi: 108 địa điểm, gồm 93 thành phố/khu vực tại Việt Nam và 15 thành phố nước ngoài.
- Dữ liệu lấy theo tọa độ latitude/longitude của từng địa điểm.
- Chỉ số thu thập:
  - AQI
  - PM2.5
  - PM10
  - CO
  - NO2
  - SO2
  - O3

Nhóm thành phố nước ngoài bổ sung:

```text
Bangkok, Singapore, Kuala Lumpur, Jakarta, Manila,
Phnom Penh, Vientiane, Yangon, Beijing, Shanghai,
Hong Kong, Tokyo, Seoul, Taipei, New Delhi
```

Việc bổ sung các thành phố nước ngoài giúp mỗi lần crawl có nhiều địa điểm hơn, hỗ trợ mục tiêu lấy khoảng 1500 bản ghi raw từ Open-Meteo.

### 2.2. Mục tiêu hệ thống

- Tự động thu thập dữ liệu chất lượng không khí từ Open-Meteo.
- Làm sạch và chuẩn hóa dữ liệu bằng Pandas.
- Lưu dữ liệu vào MySQL.
- Chống trùng dữ liệu theo `city + time + station`.
- Cung cấp REST API bằng FastAPI.
- Hiển thị dashboard gồm xếp hạng, bản đồ, biểu đồ, tìm kiếm, so sánh, phân cụm và dự đoán.
- Có cơ chế auto crawl theo chu kỳ.
- Có hướng dẫn kiểm tra tính đúng của dữ liệu trong MySQL.

## 3. Những phần nên bỏ và đã bỏ

Trong quá trình rà soát, hệ thống cũ có một số phần không còn phù hợp với hướng triển khai hiện tại.

Đã bỏ:

- `backend/services/crawler.py`: crawler WAQI/IQAir cũ.
- `backend/schemas.py`: schema Pydantic cũ không còn được import và thiếu các cột mới như `country`, `station`, `so2`.
- Nhánh `use_backup`, `use_html`, `max_terms`, `max_stations` trong endpoint `/crawl`.
- Phụ thuộc `beautifulsoup4` trong `requirements.txt`.
- Mô tả backup WAQI/IQAir trong README.
- Hướng dẫn SQLite, vì hệ thống hiện chỉ dùng MySQL.

Lý do bỏ:

- Đề tài đã chốt nguồn chính là Open-Meteo Air Quality API.
- Dùng một nguồn duy nhất giúp luồng dữ liệu rõ ràng, dễ thuyết minh và dễ kiểm chứng.
- Không scrape HTML nên tránh phụ thuộc cấu trúc giao diện website.
- Giảm rủi ro vi phạm chính sách nền tảng.
- Giảm độ phức tạp khi chạy demo và bảo vệ bài.

Các phần được giữ:

- `crawler_openmeteo.py`: crawler chính.
- `data_loader.py`: tiền xử lý dữ liệu.
- `crud.py`, `models.py`, `database.py`: lưu trữ MySQL.
- `ml.py`: phân cụm KMeans.
- `predict.py`: dự đoán AQI.
- `robots_checker.py`: báo cáo tuân thủ và nguồn dữ liệu.
- `index.html`: dashboard.

## 4. Kiến trúc tổng thể

```text
Open-Meteo Air Quality API
        |
        | requests
        v
backend/services/crawler_openmeteo.py
        |
        | raw records
        v
backend/services/data_loader.py
        |
        | clean records
        v
backend/crud.py + backend/models.py
        |
        | SQLAlchemy ORM
        v
MySQL: air_quality.air_quality
        |
        v
FastAPI endpoints: backend/main.py
        |
        v
Dashboard: index.html
```

Hệ thống có 3 lớp chính:

1. **Data pipeline**: thu thập, tiền xử lý, lưu trữ.
2. **Backend API**: cung cấp dữ liệu và chức năng phân tích.
3. **Frontend dashboard**: hiển thị dữ liệu cho người dùng.

## 5. Cấu trúc thư mục

```text
DA_MoiTruong/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── crud.py
│   └── services/
│       ├── aqi.py
│       ├── cities.py
│       ├── crawler_openmeteo.py
│       ├── data_loader.py
│       ├── ml.py
│       ├── predict.py
│       └── robots_checker.py
├── index.html
├── requirements.txt
└── README.md
```

### Vai trò từng file chính

| File | Vai trò |
|---|---|
| `backend/main.py` | Khởi tạo FastAPI, định nghĩa endpoint, auto crawl |
| `backend/database.py` | Kết nối MySQL bằng SQLAlchemy |
| `backend/models.py` | Định nghĩa bảng `air_quality` |
| `backend/crud.py` | Insert dữ liệu, truy vấn ranking, history, summary |
| `backend/services/crawler_openmeteo.py` | Thu thập dữ liệu từ Open-Meteo |
| `backend/services/data_loader.py` | Làm sạch dữ liệu bằng Pandas |
| `backend/services/cities.py` | Danh sách 93 địa điểm Việt Nam và 15 thành phố nước ngoài |
| `backend/services/aqi.py` | Hàm tính AQI fallback từ PM2.5/PM10 |
| `backend/services/ml.py` | Phân nhóm ô nhiễm bằng KMeans |
| `backend/services/predict.py` | Dự đoán AQI bằng Linear Regression |
| `backend/services/robots_checker.py` | Báo cáo nguồn dữ liệu và tuân thủ |
| `index.html` | Dashboard HTML/CSS/JavaScript |

## 6. Công nghệ đã áp dụng

Hệ thống sử dụng các công nghệ chính sau:

| Nhóm công nghệ | Công nghệ/thư viện | Vai trò trong hệ thống |
|---|---|---|
| Ngôn ngữ lập trình | Python | Xây dựng backend, crawler, xử lý dữ liệu và học máy |
| Web backend | FastAPI | Xây dựng REST API cho crawl, ranking, map, chart, compare, cluster, predict |
| ASGI server | Uvicorn | Chạy ứng dụng FastAPI trên local server |
| Thu thập dữ liệu | `requests` | Gửi HTTP request đến Open-Meteo Air Quality API |
| Nguồn dữ liệu | Open-Meteo Air Quality API | Cung cấp dữ liệu AQI, PM2.5, PM10, CO, NO2, SO2, O3 |
| Tiền xử lý dữ liệu | Pandas | Chuyển raw records thành DataFrame, ép kiểu, lọc AQI, chuẩn hóa dữ liệu, bỏ trùng |
| ORM | SQLAlchemy | Ánh xạ bảng MySQL thành model Python và thao tác insert/query |
| CSDL | MySQL | Lưu trữ dữ liệu chất lượng không khí |
| Driver MySQL | PyMySQL | Kết nối SQLAlchemy với MySQL |
| Học máy | scikit-learn | KMeans phân nhóm ô nhiễm, Linear Regression dự đoán AQI |
| Kiểm tra nguồn | `urllib.robotparser` | Kiểm tra/báo cáo robots.txt trong endpoint compliance |
| Frontend | HTML, CSS, JavaScript | Xây dựng giao diện dashboard |
| Biểu đồ | Chart.js | Vẽ biểu đồ AQI theo thời gian |
| Bản đồ | Leaflet | Hiển thị AQI trên bản đồ |

### 6.1. Mức độ đáp ứng yêu cầu thư viện

Yêu cầu đề tài nhấn mạnh sinh viên vận dụng `requests`, BeautifulSoup, Selenium hoặc API, kết hợp CSDL và Pandas. Phiên bản cuối của hệ thống chọn hướng **API chính thức + requests** thay vì scrape HTML.

| Yêu cầu | Trạng thái | Ghi chú |
|---|---|---|
| `requests` | Đã dùng | Gọi Open-Meteo Air Quality API |
| API | Đã dùng | Nguồn chính và duy nhất là Open-Meteo API |
| Pandas | Đã dùng | Tiền xử lý dữ liệu trong `data_loader.py` |
| MySQL | Đã dùng | Lưu dữ liệu vào schema `air_quality` |
| BeautifulSoup | Không dùng trong bản cuối | Không cần scrape HTML vì đã có API công khai, ổn định |
| Selenium | Không dùng | Không cần điều khiển trình duyệt vì không thu thập dữ liệu động từ website |
| SQLite | Không dùng | Project đã chốt chỉ dùng MySQL để lưu dữ liệu |

Việc không dùng BeautifulSoup/Selenium là có chủ đích. Vì Open-Meteo cung cấp API công khai, dùng API giúp hệ thống hợp pháp hơn, ổn định hơn và ít phụ thuộc giao diện website hơn so với scraping HTML.

## 7. Luồng thu thập dữ liệu

### 7.1. Nguồn dữ liệu

Crawler chính nằm tại:

```text
backend/services/crawler_openmeteo.py
```

Endpoint Open-Meteo đang dùng:

```text
https://air-quality-api.open-meteo.com/v1/air-quality
```

Ví dụ request cho Hà Nội:

```text
https://air-quality-api.open-meteo.com/v1/air-quality?latitude=21.03&longitude=105.85&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi&hourly=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi&timezone=auto&past_days=2&forecast_days=1
```

### 7.2. Tham số request

| Tham số | Ý nghĩa |
|---|---|
| `latitude` | Vĩ độ địa điểm |
| `longitude` | Kinh độ địa điểm |
| `current` | Lấy dữ liệu hiện tại |
| `hourly` | Lấy dữ liệu theo giờ |
| `timezone=auto` | Dùng múi giờ tự động theo tọa độ |
| `past_days=2` | Lấy dữ liệu gần đây |
| `forecast_days=1` | API có thể trả thêm mốc dự báo, nhưng hệ thống không lưu mốc tương lai |

### 7.3. Chỉ lưu số liệu đã xảy ra

Open-Meteo có thể trả các mốc giờ dự báo. Để dữ liệu trong MySQL phản ánh số liệu tại thời điểm thu thập, hệ thống chỉ lưu:

- Bản ghi `current`.
- Bản ghi `hourly` có `time <= thời điểm hiện tại`.

Các mốc giờ tương lai bị bỏ qua.

### 7.4. Cấu trúc record sau crawl

Mỗi bản ghi raw được chuẩn hóa về dạng:

```python
{
    "city": "Hà Nội",
    "country": "Vietnam",
    "time": datetime(...),
    "station": "open_meteo_hourly",
    "aqi": 75,
    "pm25": 20.1,
    "pm10": 35.4,
    "co": 180.0,
    "no2": 12.0,
    "so2": 4.0,
    "o3": 55.0
}
```

`station` là nhãn nguồn dữ liệu:

- `open_meteo`: dữ liệu hiện tại.
- `open_meteo_hourly`: dữ liệu theo giờ.

### 7.5. Số lượng mỗi lần crawl

Endpoint:

```text
GET /crawl?target=1500
```

nghĩa là hệ thống cố gắng lấy khoảng 1500 bản ghi raw từ Open-Meteo. Tuy nhiên số dòng mới lưu vào MySQL có thể thấp hơn vì:

- Dữ liệu có thể bị trùng `city + time + station`.
- Open-Meteo cập nhật dữ liệu theo mốc giờ.
- Nếu crawl liên tục trong vài phút, timestamp thường chưa đổi.

Cần phân biệt:

| Trường | Ý nghĩa |
|---|---|
| `raw_count` | Số bản ghi lấy từ API |
| `clean_count` | Số bản ghi hợp lệ sau tiền xử lý |
| `inserted_count` | Số bản ghi mới thật sự lưu vào MySQL |

Ví dụ `inserted_count = 0` không có nghĩa là crawl sai. Nó thường chỉ cho biết dữ liệu đã tồn tại trong MySQL.

Khuyến nghị: crawl khoảng **1 giờ/lần**, phù hợp với dữ liệu hourly.

## 8. Luồng tiền xử lý dữ liệu

File xử lý:

```text
backend/services/data_loader.py
```

Các bước:

1. Chuyển list records thành Pandas DataFrame.
2. Đảm bảo đủ cột:

```text
city, country, time, station, pm25, pm10, co, no2, so2, o3, aqi
```

3. Loại dòng không có AQI.
4. Ép AQI về dạng số.
5. Giữ AQI trong khoảng `0-500`.
6. Chuẩn hóa tên thành phố.
7. Chuẩn hóa thời gian.
8. Ép kiểu số cho các chất ô nhiễm.
9. Loại bản ghi trùng theo:

```text
city + time + station
```

## 9. Luồng lưu trữ MySQL

### 9.1. Cấu hình kết nối

File:

```text
backend/database.py
```

Cấu hình:

```python
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/air_quality"
```

Project chỉ dùng MySQL để lưu dữ liệu.

### 9.2. Bảng dữ liệu

Bảng:

```text
air_quality.air_quality
```

Các cột:

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | Integer | Khóa chính |
| `city` | String | Tên thành phố/khu vực |
| `country` | String | Quốc gia |
| `time` | DateTime | Thời gian ghi nhận |
| `pm25` | Float | PM2.5 |
| `pm10` | Float | PM10 |
| `co` | Float | CO |
| `no2` | Float | NO2 |
| `so2` | Float | SO2 |
| `o3` | Float | O3 |
| `aqi` | Float | Chỉ số AQI |
| `station` | String | Nguồn dữ liệu |

Ràng buộc chống trùng:

```text
UNIQUE(city, time, station)
```

Khi server khởi động, `main.py` tự gọi `create_all()`. Nếu bảng cũ thiếu `country` hoặc `so2`, hệ thống tự bổ sung cột bằng `ALTER TABLE`.

## 10. Luồng API backend

Backend dùng FastAPI. Chạy server:

```bash
uvicorn backend.main:app --reload
```

Hoặc nếu terminal đang ở thư mục `backend`:

```bash
uvicorn main:app --reload
```

API docs:

```text
http://127.0.0.1:8000/docs
```

### Danh sách endpoint

| Endpoint | Chức năng |
|---|---|
| `GET /` | Kiểm tra server |
| `GET /compliance` | Mô tả nguồn dữ liệu và pipeline |
| `GET /cities` | Danh sách 108 địa điểm theo dõi |
| `GET /crawl?target=1500` | Crawl Open-Meteo, clean và lưu MySQL |
| `GET /crawl-openmeteo?target=1500` | Crawl riêng Open-Meteo |
| `GET /ranking?limit=10&order=desc` | Xếp hạng AQI |
| `GET /map` | Dữ liệu bản đồ |
| `GET /summary` | Tổng hợp dữ liệu mới nhất |
| `GET /city?city=Hanoi` | Lịch sử một thành phố |
| `GET /search?city=Hanoi` | Tìm kiếm thành phố |
| `GET /compare?city1=Hanoi&city2=Da Nang` | So sánh hai thành phố |
| `GET /chart?city=Hanoi` | Dữ liệu biểu đồ một thành phố |
| `GET /chart_multi` | Dữ liệu biểu đồ nhiều thành phố |
| `GET /cluster` | Phân nhóm ô nhiễm bằng KMeans |
| `GET /predict` | Dự đoán AQI |
| `GET /predict?city=Hanoi` | Dự đoán AQI cho một thành phố |
| `GET /auto-status` | Trạng thái auto crawl |
| `GET /auto-start?interval_seconds=3600` | Bật auto crawl |
| `GET /auto-stop` | Tắt auto crawl |
| `GET /auto-once` | Crawl một lần ngay lập tức |

## 11. Logic các chức năng phân tích

### 11.1. Xếp hạng AQI

Endpoint:

```text
GET /ranking?limit=10&order=desc
```

Logic:

1. Lấy bản ghi mới nhất của từng thành phố trong MySQL.
2. Chuẩn hóa tên thành phố.
3. Loại thành phố trùng trong response.
4. Sắp xếp theo AQI.

Ý nghĩa:

- `order=desc`: AQI cao nhất đứng đầu, tức ô nhiễm nặng hơn.
- `order=asc`: AQI thấp nhất đứng đầu, tức không khí tốt hơn.

Hệ thống không còn lọc cứng “2 giờ gần nhất”, vì Open-Meteo có thể trả mốc giờ lệch. Dùng bản ghi mới nhất của từng thành phố giúp bảng xếp hạng ổn định hơn.

### 11.2. Bản đồ

Endpoint:

```text
GET /map
```

Logic:

- Lấy dữ liệu AQI mới nhất theo thành phố.
- Ghép với tọa độ trong `CITY_PROFILES`.
- Frontend dùng Leaflet để vẽ marker trên bản đồ.

### 11.3. Tóm tắt

Endpoint:

```text
GET /summary
```

Trả về:

- Tổng số thành phố/khu vực hệ thống theo dõi.
- Số thành phố/khu vực đã có dữ liệu trong MySQL.
- Số thành phố có dữ liệu.
- AQI trung bình.
- PM2.5 trung bình.
- PM10 trung bình.
- SO2 trung bình.
- Top 5 nơi tốt nhất.
- Top 5 nơi ô nhiễm cao nhất.

Lưu ý: hệ thống theo dõi 108 địa điểm trong `CITY_PROFILES`, gồm 93 địa điểm Việt Nam và 15 thành phố nước ngoài. Tuy nhiên số địa điểm đã có dữ liệu trong MySQL có thể thấp hơn 108 nếu chưa crawl đủ, dữ liệu API bị thiếu tại một số tọa độ, hoặc database đang chứa dữ liệu cũ trước khi chuẩn hóa lại tên thành phố. Endpoint `/summary` trả cả `tracked_city_count` và `count_city` để phân biệt hai khái niệm này.

### 11.4. Tìm kiếm và lịch sử

Endpoint:

```text
GET /city?city=Hanoi
GET /search?city=Hanoi
```

Logic:

- Dùng `city_search_terms()` để hỗ trợ tên có dấu, không dấu, alias.
- Trả lịch sử mới nhất của thành phố.

### 11.5. So sánh hai thành phố

Endpoint:

```text
GET /compare?city1=Hanoi&city2=Da Nang
```

Logic:

- Lấy bản ghi mới nhất của từng thành phố.
- So sánh AQI, PM2.5, PM10, CO, NO2, SO2, O3.
- Xác định thành phố có AQI thấp hơn là nơi có chất lượng không khí tốt hơn.

### 11.6. Biểu đồ

Endpoint:

```text
GET /chart?city=Hanoi
GET /chart_multi
```

Logic:

- `/chart`: lấy chuỗi AQI theo thời gian cho một thành phố.
- `/chart_multi`: lấy chuỗi AQI gần nhất cho nhiều thành phố.
- Frontend dùng Chart.js để vẽ line chart.

## 12. Phân nhóm ô nhiễm bằng KMeans

Endpoint:

```text
GET /cluster
```

File:

```text
backend/services/ml.py
```

KMeans dùng dữ liệu thật trong MySQL, không dùng dữ liệu giả lập.

Quy trình:

1. Truy vấn bảng `air_quality`.
2. Tính trung bình theo từng thành phố cho:

```text
pm25, pm10, co, no2, so2, o3, aqi
```

3. Dùng các chất ô nhiễm làm feature:

```text
pm25, pm10, co, no2, so2, o3
```

4. Điền giá trị thiếu bằng median của từng cột để tránh biến thiếu dữ liệu thành ô nhiễm bằng 0.
5. Chuẩn hóa feature bằng `StandardScaler`.
6. Chạy:

```python
KMeans(n_clusters=3, random_state=42, n_init=10)
```

7. Sắp xếp cụm theo AQI trung bình:

```text
AQI thấp nhất  -> low
AQI giữa      -> medium
AQI cao nhất  -> high
```

Lưu ý: KMeans là phân nhóm tương đối theo dữ liệu đang có trong MySQL, không phải bảng phân loại AQI chính thức.

### 12.1. Ý nghĩa phần học máy KMeans

KMeans được áp dụng để hỗ trợ phân tích tổng quan mức độ ô nhiễm giữa các thành phố. Thay vì chỉ xem từng chỉ số riêng lẻ, thuật toán gom các thành phố có đặc điểm ô nhiễm gần giống nhau vào cùng một nhóm.

Dữ liệu đầu vào của KMeans là dữ liệu thật đã được crawl từ Open-Meteo và lưu trong MySQL. Hệ thống không dùng dữ liệu mẫu hay dữ liệu sinh ngẫu nhiên. Trước khi đưa vào mô hình, hệ thống tính giá trị trung bình theo từng thành phố để mỗi thành phố có một vector đặc trưng đại diện.

Vector đặc trưng gồm:

```text
PM2.5, PM10, CO, NO2, SO2, O3
```

Các chỉ số này có đơn vị và thang đo khác nhau. Ví dụ CO có thể có giá trị lớn hơn nhiều so với SO2 hoặc NO2. Vì vậy hệ thống dùng `StandardScaler` để chuẩn hóa dữ liệu trước khi chạy KMeans. Nếu không chuẩn hóa, chỉ số có giá trị lớn sẽ ảnh hưởng quá mạnh đến kết quả phân cụm.

Sau khi chạy KMeans, mô hình trả về 3 cụm. Tuy nhiên, mã cụm ban đầu chỉ là số kỹ thuật như `0`, `1`, `2`, chưa có ý nghĩa tốt/xấu. Vì vậy hệ thống tính AQI trung bình của từng cụm và gán nhãn:

```text
Cụm có AQI trung bình thấp nhất  -> low
Cụm có AQI trung bình ở giữa    -> medium
Cụm có AQI trung bình cao nhất  -> high
```

Nhờ vậy, kết quả phân nhóm dễ hiểu hơn trên dashboard:

- `low`: nhóm thành phố có mức ô nhiễm tương đối thấp hơn trong dữ liệu hiện có.
- `medium`: nhóm ô nhiễm trung bình.
- `high`: nhóm thành phố có mức ô nhiễm tương đối cao hơn.

KMeans trong hệ thống có vai trò hỗ trợ phân tích và trực quan hóa. Nó không thay thế quy chuẩn AQI chính thức, mà giúp người dùng nhìn nhanh các nhóm thành phố có đặc điểm ô nhiễm tương đồng.

## 13. Dự đoán AQI bằng Linear Regression

Endpoint:

```text
GET /predict
GET /predict?city=Hanoi
```

File:

```text
backend/services/predict.py
```

Mô hình dùng:

```text
pm25, pm10, co, no2, so2, o3
```

để dự đoán:

```text
aqi
```

Nếu dữ liệu trong MySQL ít hơn 20 dòng, hệ thống trả:

```json
{
  "predicted_aqi": 0,
  "message": "Not enough data"
}
```

### 13.1. Ý nghĩa phần học máy Linear Regression

Linear Regression được dùng để ước lượng AQI dựa trên các chất ô nhiễm đã thu thập. Khác với KMeans là bài toán không giám sát, Linear Regression là mô hình có giám sát vì dữ liệu huấn luyện có cả đầu vào và đầu ra.

Đầu vào của mô hình:

```text
PM2.5, PM10, CO, NO2, SO2, O3
```

Đầu ra cần dự đoán:

```text
AQI
```

Quy trình hoạt động:

1. Đọc dữ liệu từ bảng `air_quality` trong MySQL.
2. Chỉ dùng các dòng có `aqi` hợp lệ.
3. Điền giá trị thiếu bằng `0` để mô hình có thể huấn luyện.
4. Tách dữ liệu thành:

```text
X = PM2.5, PM10, CO, NO2, SO2, O3
y = AQI
```

5. Huấn luyện mô hình `LinearRegression`.
6. Nếu người dùng truyền tên thành phố, hệ thống lấy bản ghi mới nhất của thành phố đó làm đầu vào.
7. Mô hình trả về AQI dự đoán.

Ví dụ:

```text
GET /predict?city=Hanoi
```

Endpoint này lấy dữ liệu mới nhất của Hà Nội trong MySQL, đưa các chỉ số ô nhiễm vào mô hình và trả về:

```json
{
  "predicted_aqi": 75.23
}
```

Phần dự đoán này có ý nghĩa tham khảo, giúp minh họa cách sử dụng học máy trên dữ liệu môi trường. Độ chính xác phụ thuộc vào số lượng và chất lượng dữ liệu đã crawl. Nếu dữ liệu quá ít, hệ thống sẽ báo chưa đủ dữ liệu để huấn luyện.

Tóm lại:

| Mô hình | Loại bài toán | Mục đích |
|---|---|---|
| KMeans | Không giám sát | Phân nhóm thành phố theo đặc điểm ô nhiễm |
| Linear Regression | Có giám sát | Dự đoán AQI từ các chất ô nhiễm |

## 14. Auto crawl

Mặc định:

```text
AUTO_CRAWL_ENABLED=true
AUTO_CRAWL_INTERVAL_SECONDS=900
AUTO_CRAWL_TARGET=1500
```

Vì Open-Meteo là dữ liệu theo giờ, nên khi chạy thật nên dùng chu kỳ 1 giờ:

```text
GET /auto-start?interval_seconds=3600
```

Tắt auto crawl:

```text
GET /auto-stop
```

Chạy một lần:

```text
GET /auto-once
```

## 15. Frontend dashboard

File:

```text
index.html
```

Dashboard gọi API tại:

```text
http://127.0.0.1:8000
```

Chức năng giao diện:

- Nút thu thập dữ liệu mới.
- Hiển thị AQI cao nhất hiện tại.
- Dự đoán AQI.
- Số thành phố có dữ liệu.
- Thành phố có AQI thấp nhất.
- Biểu đồ AQI theo thời gian.
- Bảng xếp hạng AQI.
- So sánh hai thành phố.
- Tổng hợp chất lượng không khí.
- Phân nhóm ô nhiễm bằng KMeans.
- Bản đồ AQI.

Chạy giao diện:

```bash
python -m http.server 5500
```

Mở:

```text
http://127.0.0.1:5500/index.html
```

## 16. Cài đặt và chạy hệ thống

### 16.1. Cài thư viện

```bash
pip install -r requirements.txt
```

### 16.2. Tạo database MySQL

Trong MySQL Workbench:

```sql
CREATE DATABASE air_quality CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Nếu bảng chưa tồn tại, backend sẽ tự tạo. Nếu bảng cũ thiếu cột:

```sql
ALTER TABLE air_quality.air_quality
ADD COLUMN country VARCHAR(100) DEFAULT 'Vietnam';

ALTER TABLE air_quality.air_quality
ADD COLUMN so2 FLOAT NULL;
```

### 16.3. Chạy backend

Từ thư mục gốc:

```bash
uvicorn backend.main:app --reload
```

Hoặc từ thư mục `backend`:

```bash
uvicorn main:app --reload
```

Kiểm tra:

```text
http://127.0.0.1:8000/
```

### 16.4. Crawl dữ liệu

```text
http://127.0.0.1:8000/crawl?target=1500
```

## 17. Kiểm tra dữ liệu trong MySQL

Tổng số dòng:

```sql
SELECT COUNT(*) AS total
FROM air_quality.air_quality;
```

Xem dữ liệu mới nhất:

```sql
SELECT city, time, pm25, pm10, co, no2, so2, o3, aqi, station
FROM air_quality.air_quality
ORDER BY time DESC
LIMIT 20;
```

Kiểm tra nguồn dữ liệu:

```sql
SELECT station, COUNT(*) AS total
FROM air_quality.air_quality
GROUP BY station;
```

Kết quả đúng của luồng chính:

```text
open_meteo
open_meteo_hourly
```

Kiểm tra có lưu nhầm dữ liệu tương lai không:

```sql
SELECT COUNT(*) AS future_rows
FROM air_quality.air_quality
WHERE time > NOW();
```

Kết quả nên là:

```text
0
```

Kiểm tra AQI hợp lệ:

```sql
SELECT COUNT(*) AS invalid_aqi
FROM air_quality.air_quality
WHERE aqi < 0 OR aqi > 500 OR aqi IS NULL;
```

Kết quả nên là:

```text
0
```

Kiểm tra dữ liệu theo thành phố:

```sql
SELECT city, MAX(time) AS latest_time, COUNT(*) AS total
FROM air_quality.air_quality
GROUP BY city
ORDER BY latest_time DESC;
```

Đối chiếu trực tiếp với Open-Meteo, ví dụ Hà Nội:

```text
https://air-quality-api.open-meteo.com/v1/air-quality?latitude=21.03&longitude=105.85&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi&timezone=auto
```

Sau đó kiểm tra MySQL:

```sql
SELECT city, time, pm25, pm10, co, no2, so2, o3, aqi, station
FROM air_quality.air_quality
WHERE city LIKE '%Hà Nội%' OR city LIKE '%Ha Noi%' OR city LIKE '%Hanoi%'
ORDER BY time DESC
LIMIT 10;
```

### 17.1. Vì sao giao diện có dấu `--`?

Open-Meteo có thể trả đủ hoặc thiếu một vài chỉ số ô nhiễm tùy vị trí và thời điểm. Nếu một chỉ số bị thiếu mà hệ thống hiển thị thành `0`, người xem có thể hiểu nhầm rằng nồng độ chất đó thật sự bằng 0. Điều này làm dữ liệu trông không uy tín.

Phiên bản hiện tại xử lý theo nguyên tắc:

- Nếu API có dữ liệu thật: hiển thị số.
- Nếu API thiếu dữ liệu: hiển thị `--`.
- Không biến dữ liệu thiếu thành số 0 trên dashboard.
- Khi so sánh hai thành phố, chỉ tính chênh lệch nếu cả hai bên đều có số liệu thật.

Backend cũng trả thêm trường đánh giá chất lượng dữ liệu:

| Trường | Ý nghĩa |
|---|---|
| `quality = complete` | Có đủ PM2.5, PM10, CO, NO2, SO2, O3 |
| `quality = partial` | Thiếu một vài chỉ số ô nhiễm |
| `quality = aqi_only` | Chỉ có AQI, không có chi tiết chất ô nhiễm |

Nhờ vậy, dashboard minh bạch hơn: số 0 chỉ xuất hiện khi API thật sự trả về 0, còn dữ liệu thiếu được hiển thị là `--`.

Nếu database đã có dữ liệu cũ từng bị lưu số 0 cho chỉ số thiếu, có thể gọi endpoint bảo trì:

```text
POST http://127.0.0.1:8000/maintenance/nullify-zero-pollutants
```

Endpoint này chuyển các giá trị pollutant bằng `0` đáng ngờ về `NULL`, để dashboard hiển thị `--` thay vì số 0 giả.

## 18. Checklist chức năng

| Chức năng | Trạng thái | Ghi chú |
|---|---|---|
| Crawl Open-Meteo | Có | Nguồn duy nhất |
| Không dùng dataset sẵn | Có | Không dùng CSV/Kaggle |
| Tiền xử lý Pandas | Có | Clean, validate, deduplicate |
| Lưu MySQL | Có | SQLAlchemy ORM |
| Chống trùng | Có | `city + time + station` |
| Xếp hạng AQI | Có | Theo bản ghi mới nhất từng thành phố |
| Bản đồ AQI | Có | Leaflet |
| Biểu đồ AQI | Có | Chart.js |
| Tìm kiếm | Có | Hỗ trợ alias city |
| So sánh | Có | AQI và các chất ô nhiễm |
| Summary | Có | Trung bình và top tốt/xấu |
| KMeans | Có | Phân nhóm tương đối |
| Predict | Có | Linear Regression |
| Auto crawl | Có | Theo chu kỳ |
| Compliance | Có | Mô tả nguồn và pipeline |

## 19. Kết luận

Hệ thống đã hoàn thiện pipeline thu thập và phân tích dữ liệu chất lượng không khí theo đúng yêu cầu:

```text
Thu thập bằng API -> Tiền xử lý bằng Pandas -> Lưu vào MySQL -> Truy vấn/hiển thị/phân tích
```

Dự án sử dụng Open-Meteo Air Quality API làm nguồn duy nhất, không dùng dataset có sẵn và không scrape HTML. Dữ liệu sau khi thu thập được chuẩn hóa, kiểm tra hợp lệ và lưu vào MySQL. Trên dữ liệu đã lưu, hệ thống cung cấp các chức năng xếp hạng, bản đồ, biểu đồ, tìm kiếm, so sánh, phân nhóm ô nhiễm bằng KMeans và dự đoán AQI bằng Linear Regression.
