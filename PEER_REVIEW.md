# Bằng chứng cho 12 tiêu chí

| # | Tiêu chí | Vị trí bằng chứng | Trạng thái |
|---|---|---|---|
| 1 | API tests | tests/test_project.py: APITests | Đã chạy |
| 2 | Model tests | ModelTests: nhãn, rò rỉ, predict, lưu/nạp | Đã chạy |
| 3 | Logging tests | LoggingTests: append/read, Unicode, số không hợp lệ | Đã chạy |
| 4 | Một script chạy tất cả tests | python run_tests.py; exit code khác 0 khi lỗi | 20 tests pass |
| 5 | Monitoring | /metrics; revenue/monitoring.py; replay.py và biểu đồ | Có; cần chạy định kỳ khi vận hành |
| 6 | Cách ly read/write tests | TemporaryDirectory cho data/model/log; config inject | Đã áp dụng |
| 7 | Predict quốc gia và tất cả | /predict, /countries; HTTP và tests | Có; 10 quốc gia + all |
| 8 | Ingestion tự động | download_data.py; python -m revenue.ingestion | Có |
| 9 | So sánh nhiều mô hình | baseline, Ridge, Random Forest; evaluation.json | Có |
| 10 | EDA trực quan | reports/eda.png | Có |
| 11 | Docker image hoạt động | Dockerfile; các lệnh README bước 6 | CHƯA XÁC MINH: máy không có Docker |
| 12 | Đồ thị baseline vs model | reports/model_comparison.png | Có |

Không coi Dockerfile là bằng chứng container đã chạy. Đính kèm kết quả build,
test trong container và request thật trước khi nộp tiêu chí 11.
