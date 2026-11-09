# Dự báo doanh thu 30 ngày — IBM AI Workflow capstone

Project học tập có ingestion, Flask API, ba phương án dự báo, kiểm thử, EDA,
logging, monitoring và Dockerfile. Mục tiêu: tổng doanh thu trong 30 ngày bắt đầu
tại ngày yêu cầu, theo một quốc gia hoặc tất cả quốc gia cộng lại.

Nguồn đối chiếu: https://github.com/aavail/ai-workflow-capstone
Đây là triển khai mới dựa trên dữ liệu và yêu cầu công khai, không sao chép bài nộp
của học viên khác. Trang Coursera có thể có yêu cầu bổ sung sau đăng nhập;
hãy đối chiếu rubric của lớp trước khi nộp.

## Bước 1 — Chạy bộ khung và kiểm thử

Mở PowerShell trong thư mục chứa README này. Cài Python 3.12 nếu máy chưa có
Python hoạt động; `python --version` cần trả về phiên bản thay vì mở Store.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe run_tests.py
.\.venv\Scripts\python.exe run_app.py
```

Mở terminal thứ hai:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/metrics
```

`health` trả `status: ok`. Nếu chưa có artifact, `model_ready` là false và
`/predict` trả HTTP 503. Bản giao kèm artifact đã huấn luyện trên dữ liệu công khai.
Không cần kích hoạt môi trường ảo; các lệnh dùng trực tiếp Python trong `.venv`.

**Nếu tải từ GitHub:** file mô hình không được lưu trong Git. Sau khi cài thư viện,
chạy hai lệnh dưới đây để tải dữ liệu và tạo mô hình trước khi thử `/predict`
hoặc build Docker. Bộ kiểm thử vẫn chạy được khi chưa có mô hình.

```powershell
.\.venv\Scripts\python.exe download_data.py
.\.venv\Scripts\python.exe -m revenue.reports --source data/raw
```

## Bước 2 — Tải và chuẩn hóa dữ liệu thật

```powershell
.\.venv\Scripts\python.exe download_data.py
.\.venv\Scripts\python.exe -m revenue.ingestion --source data/raw
```

Script tải `cs-train`, lưu phiên bản nguồn và SHA256. Không trộn `cs-production`
vào training ban đầu. Có thể dùng `--source` để đọc dữ liệu khóa học đã tải sẵn.
Các cột cần có: country, customer_id, day, invoice, month, price, stream_id,
times_viewed, year. Hỗ trợ tên thay thế total_price, StreamID, TimesViewed.

Theo hàm tổng hợp của starter, doanh thu = tổng price, **không nhân times_viewed**.
Giữ số âm như khoản hoàn trả; giữ dòng lặp vì chưa có khóa giao dịch duy nhất.
Ngày không có bản ghi được điền doanh thu 0 trong khoảng ngày đầu/cuối toàn bộ
dữ liệu. Đây là giả định không phát sinh giao dịch, không phải bằng chứng dữ liệu
không bị thất lạc; cần xác minh nếu dùng dữ liệu vận hành. Không giả định đơn vị tiền.
Giá thiếu/vô hạn, ngày sai và schema không phù hợp đều gây lỗi rõ ràng.

## Bước 3 — EDA, huấn luyện và so sánh

```powershell
.\.venv\Scripts\python.exe -m revenue.reports --source data/raw
```

Kết quả: `models/revenue.pkl`, `reports/eda.png`, `reports/model_comparison.png`,
`reports/evaluation.json` và `reports/data_summary.json`.

Ba phương án:

* Baseline: tổng doanh thu 30 ngày trước.
* Ridge: hồi quy có chuẩn hóa và regularization.
* Random Forest: mô hình phi tuyến, seed cố định.

Đầu vào gồm doanh thu gần nhất, trung bình 7/14/30/90 ngày, độ lệch chuẩn 30 ngày
và mùa vụ theo ngày trong năm. Mỗi đặc trưng chỉ đọc ngày trước forecast_start.
Nhãn là tổng từ forecast_start đến forecast_start + 29 ngày, bao gồm hai đầu.
Cần ít nhất 360 ngày lịch để chạy quy trình đánh giá.

Chia theo thời gian, bỏ các nhãn có cửa sổ 30 ngày chồng sang tập kế tiếp.
Chọn mô hình bằng MAE validation, báo MAE/RMSE trên test cuối; không chọn bằng test.
Sau đánh giá, refit phương án đã chọn trên toàn bộ nhãn đã quan sát.
Baseline có thể thắng; không mặc định mô hình phức tạp tốt hơn.
Các nhãn test chồng lấn nên sai số có tương quan; đây không phải các quan sát độc lập.

`all` dùng tổng của mọi quốc gia trong dữ liệu. API còn phục vụ 10 quốc gia doanh
thu cao nhất, như phạm vi starter. `/countries` cho danh sách chính xác.
Mô hình tổng và mô hình từng nước được huấn luyện riêng, không áp đặt tổng dự báo
của các nước phải bằng dự báo `all`.

## Bước 4 — Gọi API

Giữ `run_app.py` chạy trong terminal riêng:

```powershell
Invoke-RestMethod http://localhost:8000/countries
Invoke-RestMethod http://localhost:8000/predict -Method Post -ContentType 'application/json' -Body '{"country":"all"}'
Invoke-RestMethod http://localhost:8000/predict -Method Post -ContentType 'application/json' -Body '{"country":"United Kingdom"}'
Invoke-RestMethod http://localhost:8000/logs
```

Có thể thêm `"date":"YYYY-MM-DD"`. Bỏ date thì dự báo bắt đầu ngày sau ngày cuối
dữ liệu, không phải ngày hiện tại của máy. Dữ liệu khóa học là dữ liệu lịch sử.
Với ngày quá khứ, hệ thống chọn và huấn luyện lại chỉ bằng phần lịch sử trước ngày
đó (cần 360 ngày). Không dùng artifact huấn luyện trên tương lai để backtest.
Với ngày xa hơn ngày cuối dữ liệu + 1, API báo cần bổ sung quan sát.

`POST /train` huấn luyện từ thư mục cấu hình, lưu artifact nguyên tử:

```powershell
Invoke-RestMethod http://localhost:8000/train -Method Post
```

Biến môi trường `DATA_DIR`, `MODEL_PATH`, `LOG_PATH` thay đổi vị trí dữ liệu,
model, log. API hiện dành cho bài tập/chạy cục bộ: chưa có xác thực hay hàng đợi
huấn luyện; không công khai `/train` hoặc `/logs` trên Internet.
Chỉ nạp file pickle do chính project tạo, không nạp artifact không tin cậy.

## Bước 5 — Monitoring

`GET /metrics` trả số request, lỗi và thời gian trung bình (từ lúc tiến trình khởi
động; không phải số liệu phân tán). Log JSONL lưu lịch sử dự báo và phiên bản model.

```powershell
.\.venv\Scripts\python.exe replay.py
.\.venv\Scripts\python.exe -m revenue.monitoring --source data/raw
```

Replay mô phỏng 30 ngày dự báo lịch sử và tạo đồ thị đối chiếu với thực tế trong
`reports/replay`. Mỗi ngày chỉ dùng quá khứ tại ngày đó. Đây là mô phỏng lịch sử,
không phải bằng chứng monitoring production trực tiếp.
Monitoring chỉ tính MAE/RMSE khi đã có đủ 30 ngày thực tế; tách theo quốc gia,
phiên bản và loại mô hình, bỏ yêu cầu trùng. `[]` nghĩa là chưa có nhãn đủ trưởng
thành, không phải sai số bằng 0. Chưa có lịch chạy hoặc gửi cảnh báo tự động.

## Bước 6 — Docker

Cần Docker Desktop đang chạy với Linux containers:

```powershell
docker build -t revenue-forecasting .
docker run --rm revenue-forecasting python run_tests.py
docker run --rm -p 8000:8000 revenue-forecasting
```

Image chứa code, tests và artifact model kèm project. Dockerfile chạy tests khi
build. Không đóng gói dữ liệu thô hay log. Muốn huấn luyện trong container:

```powershell
docker run --rm -p 8000:8000 --mount "type=bind,source=$((Get-Location).Path)/data/raw,target=/app/data/raw,readonly" --mount "type=bind,source=$((Get-Location).Path)/models,target=/app/models" revenue-forecasting
```

Sau khi khởi chạy, gọi `/health`, `/countries`, `/predict` như bước 4. Cổng 8000
phải trống; dừng API chạy bằng Python trước khi chạy container.
**Docker chưa được kiểm chứng trên máy tạo project vì chưa có lệnh Docker.**
Chỉ đánh dấu tiêu chí này hoàn thành khi build, tests và API trong container chạy thành công.

## Bước 7 — Chuẩn bị nộp

Đọc `PEER_REVIEW.md` để đối chiếu đủ 12 tiêu chí, `reports/RESULTS.md` để xem kết
quả thực nghiệm. Tự giải thích các giả định, baseline, cách chống rò rỉ dữ liệu,
giới hạn mô hình và tradeoff nghiệp vụ trong báo cáo của bạn.

Thứ tự đọc code: ingestion.py → model.py → reports.py → api.py → eventlog.py →
monitoring.py → tests/test_project.py. Thư viện và môi trường được khóa trong
requirements-lock.txt; requirements.txt ghi dải phiên bản chấp nhận được.
