# Hệ thống thu thập, lưu trữ, tìm kiếm và xếp hạng chất lượng không khí

Đề tài môn **Kĩ thuật lập trình trong phân tích dữ liệu**.

Hệ thống dùng FastAPI, MySQL, SQLAlchemy ORM, Pandas, scikit-learn, Chart.js và Leaflet để xây dựng pipeline:

```text
Open-Meteo Air Quality API
-> requests crawler
-> Pandas clean/normalize
-> MySQL store
-> FastAPI search/ranking/compare/map/chart
-> KMeans + Linear Regression
-> HTML dashboard
```

Nguồn dữ liệu chính và duy nhất là Open-Meteo Air Quality API:

```text
https://open-meteo.com/en/docs/air-quality-api
```

Project không dùng dataset có sẵn như Kaggle/CSV tải sẵn, không scrape HTML và không tạo dữ liệu giả.

## Chức năng chính

- Crawl dữ liệu AQI, PM2.5, PM10, CO, NO2, SO2, O3 theo danh sách thành phố trong `backend/services/cities.py`.
- Chỉ lưu bản ghi hiện tại hoặc hourly đã xảy ra, không lưu mốc tương lai.
- Có timeout, retry, giới hạn số worker và khoảng nghỉ nhỏ giữa request.
- Làm sạch dữ liệu bằng Pandas, giữ `NULL` nếu thiếu chỉ số, không biến thiếu dữ liệu thành 0.
- Lưu MySQL với chống trùng theo `city + observed_time + station`.
- Tìm kiếm nâng cao theo thành phố, quốc gia, thời gian, AQI, mức AQI, chỉ số ô nhiễm, sort và limit.
- Xếp hạng theo AQI, PM2.5, PM10, CO, NO2, SO2, O3 hoặc điểm ô nhiễm tổng hợp.
- So sánh hai thành phố theo bản ghi mới nhất, AQI trung bình và lịch sử AQI.
- Dashboard gồm tổng quan, crawl mới, tìm kiếm, ranking, biểu đồ, bản đồ, compare, KMeans và dự đoán AQI.
- KMeans phân cụm thành phố thành `low`, `medium`, `high`.
- Linear Regression dự đoán AQI tham khảo từ PM2.5, PM10, CO, NO2, SO2, O3.

## Cấu trúc project

```text
backend/
  main.py
  database.py
  models.py
  crud.py
  services/
    aqi.py
    cities.py
    crawler_openmeteo.py
    data_loader.py
    ml.py
    predict.py
    robots_checker.py
index.html
requirements.txt
.env.example
.gitignore
README.md
```

## Cài đặt

Tạo virtual environment nếu cần:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Tạo file `.env` từ mẫu `.env.example` và sửa mật khẩu MySQL:

```text
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/air_quality?charset=utf8mb4
AUTO_CRAWL_ENABLED=false
CURRENT_DATA_MAX_AGE_HOURS=48
OPEN_METEO_MAX_WORKERS=6
```

Không commit file `.env` vì có thể chứa mật khẩu thật.

## Tạo database MySQL

```sql
CREATE DATABASE air_quality
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Backend tự gọi `create_all()` và có lớp migration nhỏ khi khởi động để bổ sung các cột còn thiếu. Schema chính của bảng `air_quality`:

| Cột | Ý nghĩa |
|---|---|
| `id` | Khóa chính |
| `city`, `country` | Thành phố và quốc gia |
| `latitude`, `longitude` | Tọa độ |
| `observed_time` | Thời gian dữ liệu được Open-Meteo ghi nhận |
| `collected_at` | Thời điểm hệ thống crawl/lưu dữ liệu |
| `pm25`, `pm10`, `co`, `no2`, `so2`, `o3` | Chỉ số ô nhiễm |
| `aqi` | US AQI từ Open-Meteo |
| `station` | Nguồn bản ghi: `open_meteo` hoặc `open_meteo_hourly` |

Nếu database đã có schema cũ, backend sẽ tự thêm an toàn:

```sql
ALTER TABLE air_quality ADD COLUMN latitude FLOAT NULL;
ALTER TABLE air_quality ADD COLUMN longitude FLOAT NULL;
ALTER TABLE air_quality ADD COLUMN observed_time DATETIME NULL;
ALTER TABLE air_quality ADD COLUMN collected_at DATETIME NULL;
UPDATE air_quality SET observed_time = time WHERE observed_time IS NULL AND time IS NOT NULL;
UPDATE air_quality SET collected_at = NOW() WHERE collected_at IS NULL;
```

Bảng `air_quality` dùng cho dữ liệu hiện hành để dashboard truy vấn nhanh. Bảng `air_quality_history` dùng để lưu lịch sử các lần crawl, giúp kiểm tra và mở rộng phân tích sau này.

## Chạy backend

Từ thư mục gốc project:

```bash
uvicorn backend.main:app --reload
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Chạy frontend

Có thể mở trực tiếp `index.html` trong trình duyệt. Nếu muốn chạy bằng local static server:

```bash
python -m http.server 5500
```

Mở:

```text
http://127.0.0.1:5500/index.html
```

## Crawl dữ liệu

Trên dashboard bấm **Thu thập dữ liệu mới**, hoặc gọi:

```text
GET http://127.0.0.1:8000/crawl?target=1500&replace_existing=true&force=true
```

Kết quả trả về có:

- `raw_count`: số bản ghi lấy từ API.
- `clean_count`: số bản ghi hợp lệ sau Pandas clean.
- `inserted_count`: số bản ghi lưu vào MySQL.
- `deleted_count`: số bản ghi hiện hành cũ bị xóa nếu `replace_existing=true`.
- `archived_count`: số bản ghi được lưu vào bảng lịch sử.

Với 108 thành phố/khu vực và khoảng 15-17 giờ dữ liệu mỗi nơi, một lần crawl thường đủ mục tiêu khoảng 1000-1500 bản ghi hợp lệ nếu Open-Meteo trả đủ dữ liệu.

## Endpoint chính

| Endpoint | Chức năng |
|---|---|
| `GET /` | Health check |
| `GET /cities` | Danh sách thành phố/khu vực |
| `GET /source-url?city=Hà Nội` | Link API Open-Meteo để đối chiếu |
| `GET /crawl?target=1500&replace_existing=true` | Crawl, clean, store |
| `GET /summary` | Tổng quan dashboard |
| `GET /search?...` | Tìm kiếm nâng cao |
| `GET /ranking?...` | Xếp hạng thành phố |
| `GET /compare?city1=...&city2=...` | So sánh bản ghi mới nhất |
| `GET /compare-history?city1=...&city2=...` | So sánh lịch sử và AQI trung bình |
| `GET /map` | Dữ liệu marker Leaflet |
| `GET /chart?city=...` | AQI theo thời gian của một thành phố |
| `GET /chart_multi` | AQI theo thời gian của nhiều thành phố |
| `GET /cluster` | KMeans |
| `GET /predict?city=...` | Dự đoán AQI tham khảo |
| `GET /city-insight?city=...` | Latest, history, cluster, prediction và nhận xét |

Ví dụ tìm kiếm nâng cao:

```text
GET /search?city=Hà Nội&start_date=2026-05-01&end_date=2026-05-14&sort_by=aqi&order=desc&limit=50
```

Tham số `/search` hỗ trợ:

```text
city, country, start_date, end_date,
min_aqi, max_aqi,
level=good|moderate|unhealthy|very_unhealthy|hazardous,
pollutant=aqi|pm25|pm10|co|no2|so2|o3,
sort_by=time|aqi|pm25|pm10|co|no2|so2|o3,
order=asc|desc,
limit
```

Ví dụ ranking:

```text
GET /ranking?metric=aqi&order=desc&limit=10
GET /ranking?metric=aqi&order=asc&limit=10
GET /ranking?metric=pm25&order=desc&limit=10
GET /ranking?metric=pm10&order=desc&limit=10
GET /ranking?metric=pollution_score&order=desc&limit=10
```

Điểm ô nhiễm tổng hợp:

```text
pollution_score = aqi * 0.5 + pm25 * 0.2 + pm10 * 0.15 + no2 * 0.05 + so2 * 0.05 + o3 * 0.05
```

Nếu thiếu chỉ số, hệ thống chỉ tính trên các giá trị có sẵn và chuẩn hóa lại theo tổng trọng số có sẵn. Cách này tránh coi dữ liệu thiếu là 0.

## Học máy

### KMeans

File: `backend/services/ml.py`

- Feature: `pm25`, `pm10`, `co`, `no2`, `so2`, `o3`.
- Dữ liệu đầu vào là bản ghi mới nhất theo từng thành phố.
- Thiếu feature được điền bằng median của cột chỉ trong bước huấn luyện.
- Chuẩn hóa bằng `StandardScaler`.
- Chạy `KMeans(n_clusters=3, random_state=42, n_init=10)`.
- Gán nhãn cụm theo AQI trung bình: `low`, `medium`, `high`.
- Trả `silhouette_score` nếu đủ dữ liệu.

KMeans là phân nhóm tương đối theo dữ liệu đang có, không phải phân loại AQI chính thức.

### Linear Regression

File: `backend/services/predict.py`

- Feature: `pm25`, `pm10`, `co`, `no2`, `so2`, `o3`.
- Target: `aqi`.
- Trả `predicted_aqi`, `training_records`, `mae`, `r2` nếu có thể.
- Nếu dữ liệu quá ít, trả message rõ ràng và `predicted_aqi = null`.
- Kết quả dự đoán chỉ là tham khảo, không phải AQI chính thức.

Endpoint tích hợp:

```text
GET /city-insight?city=Hà Nội
```

Trả dữ liệu mới nhất, lịch sử gần đây, cluster level, AQI dự đoán và nhận xét ngắn.

## Kiểm tra dữ liệu trong MySQL

Tổng số bản ghi:

```sql
SELECT COUNT(*) AS total
FROM air_quality.air_quality;
```

Xem dữ liệu mới nhất:

```sql
SELECT city, country, observed_time, collected_at,
       pm25, pm10, co, no2, so2, o3, aqi, station
FROM air_quality.air_quality
ORDER BY observed_time DESC
LIMIT 20;
```

Kiểm tra không lưu dữ liệu tương lai:

```sql
SELECT COUNT(*) AS future_rows
FROM air_quality.air_quality
WHERE observed_time > NOW();
```

Kiểm tra AQI hợp lệ:

```sql
SELECT COUNT(*) AS invalid_aqi
FROM air_quality.air_quality
WHERE aqi IS NULL OR aqi < 0 OR aqi > 500;
```

Kiểm tra trùng:

```sql
SELECT city, observed_time, station, COUNT(*) AS total
FROM air_quality.air_quality
GROUP BY city, observed_time, station
HAVING COUNT(*) > 1;
```

Kiểm tra nguồn:

```sql
SELECT station, COUNT(*) AS total
FROM air_quality.air_quality
GROUP BY station;
```

Kết quả thường gồm:

```text
open_meteo
open_meteo_hourly
```

## Hạn chế

- Open-Meteo có thể thiếu một vài chất ô nhiễm tùy tọa độ và thời điểm.
- AQI dùng `us_aqi` của Open-Meteo, không tự suy diễn AQI nếu API thiếu.
- Mô hình ML đơn giản, phù hợp minh họa kỹ thuật hơn là dự báo sản xuất.
- KMeans phụ thuộc dữ liệu mới nhất trong MySQL, nên kết quả thay đổi sau mỗi lần crawl.
- Dashboard hiện là HTML/CSS/JavaScript thuần, chưa có authentication.

## Hướng phát triển

- Thêm lịch crawl bằng scheduler riêng.
- Lưu lịch sử lâu dài và thêm biểu đồ theo ngày/tuần/tháng.
- Thêm endpoint export CSV từ dữ liệu đã crawl.
- Thử thêm Random Forest/XGBoost để so sánh với Linear Regression.
- Thêm test tự động cho DataLoader, crawler parser và API filter.

## Dọn project trước khi nộp

Đã thêm `.gitignore` để loại:

- `.env`
- `__pycache__/`
- `*.pyc`
- virtual environment
- cache/test/build output

Không nộp mật khẩu thật, token thật hoặc thư mục `.git` nếu giảng viên không yêu cầu.
