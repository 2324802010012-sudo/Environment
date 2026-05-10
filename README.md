#Cách kiểm tra đủ 1000 chưa nè

SELECT COUNT(*) AS total FROM air_quality;

# Hệ thống thu thập và phân tích chất lượng không khí

Dự án thu thập dữ liệu chất lượng không khí trực tiếp từ Internet, tiền xử lý dữ liệu, lưu vào MySQL và cung cấp API/giao diện để xem xếp hạng, bản đồ, biểu đồ, so sánh, phân cụm và dự đoán AQI.

## Công nghệ sử dụng

- Backend: FastAPI, SQLAlchemy
- Thu thập dữ liệu: requests, BeautifulSoup, WAQI API, IQAir HTML fallback
- Kiểm tra quyền scrape: robots.txt qua `urllib.robotparser`
- Tiền xử lý: Pandas
- Cơ sở dữ liệu: MySQL
- Học máy: scikit-learn
- Frontend: HTML, CSS, JavaScript, Chart.js, Leaflet

## Quy trình đáp ứng yêu cầu

1. Thu thập dữ liệu
   - Nguồn chính là WAQI API.
   - Có fallback scrape IQAir bằng requests + BeautifulSoup.
   - Kiểm tra `robots.txt` trước khi scrape HTML.
   - Không dùng dataset có sẵn như Kaggle hoặc file CSV tải về.

2. Tiền xử lý dữ liệu
   - File `backend/services/data_loader.py` dùng Pandas.
   - Lọc AQI không hợp lệ.
   - Chuẩn hóa tên thành phố.
   - Ép kiểu các cột `pm25`, `pm10`, `co`, `no2`, `o3`, `aqi`.
   - Loại bản ghi trùng theo `city`, `time`, `station`.

3. Lưu trữ dữ liệu
   - File `backend/models.py` định nghĩa bảng `air_quality`.
   - File `backend/crud.py` lưu dữ liệu vào MySQL theo lô.
   - Unique key: `city`, `time`, `station`.

## Cấu trúc bảng `air_quality`

- `id`: khóa chính
- `city`: tên thành phố
- `time`: thời gian ghi nhận
- `pm25`, `pm10`, `co`, `no2`, `o3`: chỉ số ô nhiễm
- `aqi`: chỉ số chất lượng không khí
- `station`: tên trạm hoặc nguồn ghi nhận

## Chức năng nổi bật

- Crawl hơn 1000 mẫu dữ liệu trực tiếp từ Internet.
- Giới hạn phạm vi crawl/map/search trong 93 thành phố/khu vực tại Việt Nam.
- Lấy dữ liệu nhiều thành phố và nhiều trạm quan trắc.
- Lưu MySQL, tự bỏ qua dữ liệu trùng.
- Xem danh sách thành phố qua `/cities`.
- Xem AQI trên bản đồ qua `/map`.
- Xếp hạng AQI qua `/ranking`.
- Tìm lịch sử thành phố qua `/city` hoặc `/search`.
- So sánh hai thành phố qua `/compare`.
- Tổng hợp trung bình và nhóm tốt/xấu qua `/summary`.
- Vẽ biểu đồ qua `/chart` và `/chart_multi`.
- Phân cụm ô nhiễm bằng KMeans qua `/cluster`.
- Dự đoán AQI bằng Linear Regression qua `/predict`.

## Phần sử dụng học máy

1. Phân cụm dữ liệu: `backend/services/ml.py`
   - Thuật toán: `KMeans`.
   - Input: trung bình `pm25`, `pm10`, `co`, `no2`, `o3` theo thành phố.
   - Output: nhóm `low`, `medium`, `high`.
   - Endpoint: `/cluster`.

2. Dự đoán AQI: `backend/services/predict.py`
   - Thuật toán: `LinearRegression`.
   - Input: `pm25`, `pm10`, `co`, `no2`, `o3`.
   - Output: AQI dự đoán.
   - Endpoint: `/predict` hoặc `/predict?city=Hanoi`.

## Cài đặt

1. Tạo database MySQL:

```sql
CREATE DATABASE air_quality CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Kiểm tra cấu hình trong `backend/database.py`:

```python
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3306/air_quality"
```

3. Cài thư viện:

```bash
pip install -r requirements.txt
```

4. Chạy backend:

```bash
cd backend
uvicorn main:app --reload
```

API mặc định chạy tại:

```text
http://127.0.0.1:8000
```

## Hướng dẫn test API

Kiểm tra server:

```text
GET http://127.0.0.1:8000/
```

Lấy danh sách thành phố:

```text
GET http://127.0.0.1:8000/cities
```

Endpoint này trả về đúng 93 thành phố/khu vực Việt Nam đang được hệ thống theo dõi.

Crawl hơn 1000 mẫu và lưu vào MySQL:

```text
GET http://127.0.0.1:8000/crawl?target=1000&max_rounds=12&max_terms=5&max_stations=15
```

Ý nghĩa tham số crawl:

- `target`: số mẫu muốn lấy, mặc định 1000.
- `max_rounds`: số vòng crawl, mặc định 12. Với 93 thành phố/khu vực, mỗi vòng thường lấy khoảng 90+ mẫu nên cần khoảng 12 vòng để vượt 1000 mẫu.
- `max_terms`: số từ khóa tìm kiếm cho mỗi thành phố, mặc định 5.
- `max_stations`: số trạm tối đa lấy từ mỗi từ khóa, mặc định 15.
- `use_html`: bật fallback HTML IQAir nếu muốn thử scrape, mặc định `false`.

Kết quả crawl trả về:

- `raw_count`: số mẫu lấy được từ Internet.
- `clean_count`: số mẫu hợp lệ sau tiền xử lý.
- `inserted_count`: số mẫu mới lưu vào MySQL.

Các endpoint test tiếp theo:

```text
GET http://127.0.0.1:8000/ranking?limit=10&order=desc
GET http://127.0.0.1:8000/map
GET http://127.0.0.1:8000/summary
GET http://127.0.0.1:8000/city?city=Hanoi
GET http://127.0.0.1:8000/compare?city1=Hanoi&city2=Ho Chi Minh
GET http://127.0.0.1:8000/chart?city=Hanoi
GET http://127.0.0.1:8000/chart_multi
GET http://127.0.0.1:8000/cluster
GET http://127.0.0.1:8000/predict
GET http://127.0.0.1:8000/predict?city=Hanoi
```

## Tự động cập nhật dữ liệu

Backend có auto crawl nền. Khi server khởi động, nếu `AUTO_CRAWL_ENABLED=true` thì hệ thống tự crawl theo chu kỳ và lưu dữ liệu mới vào MySQL.

Mặc định:

- `AUTO_CRAWL_ENABLED=true`
- `AUTO_CRAWL_INTERVAL_SECONDS=900` tương đương 15 phút/lần
- `AUTO_CRAWL_TARGET=1000`
- `AUTO_CRAWL_ROUNDS=12`

Kiểm tra trạng thái auto crawl:

```text
GET http://127.0.0.1:8000/auto-status
```

Bật auto crawl và đặt chu kỳ, ví dụ 15 phút:

```text
GET http://127.0.0.1:8000/auto-start?interval_seconds=900
```

Tắt auto crawl:

```text
GET http://127.0.0.1:8000/auto-stop
```

Chạy auto crawl một lần ngay lập tức:

```text
GET http://127.0.0.1:8000/auto-once
```

Nếu muốn tắt auto crawl khi khởi động server, chạy PowerShell:

```powershell
$env:AUTO_CRAWL_ENABLED="false"
cd backend
uvicorn main:app --reload
```

## Hướng dẫn test giao diện

Sau khi backend chạy, mở `index.html` bằng trình duyệt.

Nếu trình duyệt chặn request khi mở file trực tiếp, chạy server tĩnh ở thư mục gốc:

```bash
python -m http.server 5500
```

Sau đó mở:

```text
http://127.0.0.1:5500/index.html
```

Nút **Thu thập mới** trên giao diện đang gọi:

```text
GET /crawl?target=1000&max_rounds=12&max_terms=5&max_stations=15
```

Bước này có thể mất vài phút vì hệ thống cần gọi API nhiều trạm để đủ hơn 1000 mẫu.
Crawler có cache danh sách station trong một lần chạy: vòng đầu tìm station, các vòng sau dùng lại station đã tìm để giảm thời gian.

## Lưu ý khi chưa đủ 1000 mẫu mới

`raw_count` có thể đạt mục tiêu nhưng `inserted_count` thấp hơn nếu dữ liệu bị trùng `city + time + station` hoặc API trả ít trạm tại thời điểm test.

Có thể tăng tham số:

```text
GET /crawl?target=1500&max_rounds=5&max_terms=6&max_stations=20
```

Hoặc chạy lại sau một khoảng thời gian để có timestamp mới.

## File quan trọng

- `backend/services/crawler.py`: thu thập dữ liệu từ API/HTML.
- `backend/services/robots_checker.py`: kiểm tra robots.txt.
- `backend/services/data_loader.py`: tiền xử lý dữ liệu bằng Pandas.
- `backend/crud.py`: lưu và truy vấn MySQL.
- `backend/models.py`: định nghĩa bảng dữ liệu.
- `backend/services/ml.py`: phân cụm bằng KMeans.
- `backend/services/predict.py`: dự đoán AQI bằng Linear Regression.
- `backend/main.py`: định nghĩa API FastAPI.
- `index.html`: giao diện dashboard.
