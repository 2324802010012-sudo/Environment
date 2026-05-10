# Machine Learning Note

## Mục tiêu
Hệ thống sử dụng học máy để phân nhóm và dự đoán mức độ ô nhiễm không khí tại các thành phố.

## Dữ liệu
- Dữ liệu lấy từ API WAQI.
- Chỉ số chính: PM2.5, PM10, CO, NO2, O3, AQI.
- Dữ liệu lưu trong bảng `air_quality`.

## Phân nhóm (Clustering)
- Sử dụng `KMeans` với `n_clusters=3`.
- Input: trung bình các chỉ số PM2.5, PM10, CO, NO2, O3 theo thành phố.
- Output: nhóm `low`, `medium`, `high`.
- Endpoint: `/cluster`.

## Dự đoán AQI
- Sử dụng `LinearRegression`.
- Input: PM2.5, PM10, CO, NO2, O3.
- Output: giá trị AQI dự đoán.
- Endpoint: `/predict?city=...`.

## Node phần học máy
- `backend/services/ml.py` chứa logic clustering.
- `backend/services/predict.py` chứa logic dự đoán.
- `backend/main.py` cung cấp các endpoint cho frontend gọi.

## Ghi chú
- Nếu có nhiều dữ liệu hơn 1000 mẫu, model sẽ chính xác và ổn định hơn.
