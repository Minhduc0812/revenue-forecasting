# Kết quả kiểm chứng

## Dữ liệu và bài toán

21 file JSON từ cs-train của AAVAIL, 611 ngày từ 2017-11-28 đến 2019-07-31,
43 quốc gia. Hash các file đã đối chiếu với Git blobs; xem source_manifest.json.
Mục tiêu là doanh thu cộng dồn 30 ngày, phục vụ kế hoạch doanh thu/ngân sách.
Giả thuyết kiểm tra: mô hình dùng lịch sử và mùa vụ cải thiện MAE so với tổng
doanh thu 30 ngày trước. Chưa có trọng số chi phí dự báo thừa/thiếu từ nghiệp vụ,
nên dùng MAE cùng đơn vị doanh thu làm thước đo chính.

EDA cho thấy United Kingdom chiếm phần lớn doanh thu, có đột biến lớn và khoản
doanh thu âm. Không tự loại bỏ các giá trị này vì có thể là hoàn trả hoặc giao
dịch thật. Dữ liệu thiếu xác nhận tiền tệ, lịch khuyến mãi, ngày đóng cửa và độ
đầy đủ của nguồn; các thông tin này sẽ giúp giải thích sai số và cải thiện mô hình.

## So sánh trên all

| Phương án | Validation MAE | Test MAE | Test RMSE |
|---|---:|---:|---:|
| Baseline | 19,138.72 | 19,463.96 | 23,319.05 |
| Ridge | 64,614.29 | 33,749.81 | 36,941.68 |
| Random Forest | 75,074.94 | 46,645.88 | 53,518.60 |

Baseline được chọn bởi validation và cũng tốt nhất trên test ở lần thực nghiệm
này. Chưa có bằng chứng hai mô hình ML cải thiện mục tiêu nghiệp vụ.
Không chỉnh mô hình dựa vào test để làm đẹp kết quả.

Các mốc chống rò rỉ: nhãn train cuối kết thúc 2019-03-04; validation bắt đầu
2019-03-05; nhãn validation cuối kết thúc 2019-05-18; test bắt đầu 2019-05-19.
Tập test gồm 45 ngày xuất phát; mỗi nhãn là một cửa sổ 30 ngày nên các sai số
có tương quan. Kết quả từng quốc gia nằm trong evaluation.json.

## Kiểm thử và hoạt động

20 tests kiểm tra API, model, ingestion, download, logging và monitoring.
Mọi file dữ liệu/model/log do tests ghi đều nằm trong TemporaryDirectory.
HTTP thật qua Waitress trả 200 cho health, countries, dự báo all, United Kingdom,
và ngày quá khứ 2019-06-01; chi tiết trong http_smoke.json.
Tiến trình kiểm tra HTTP đã dừng sau khi chạy.

Dự báo mặc định của artifact là 2019-08-01 đến 2019-08-30: all = 182,877.601;
United Kingdom = 169,826.811. Đây là ví dụ từ lịch sử khóa học, không phải dự báo
cho ngày hiện tại hay đơn vị tiền tệ được xác nhận.

Replay 30 ngày có đủ nhãn cho all đạt MAE 23,152.69 và RMSE 26,348.07.
Mỗi yêu cầu lịch sử huấn luyện lại bằng quá khứ tại ngày đó. Xem replay/monitoring.png
và replay/monitoring.json. Các ngày replay chồng với test và không phải đánh giá
độc lập mới. Chưa đánh giá phần cs-production hoặc thiết lập cảnh báo tự động.

## Việc cần hoàn tất trước khi nộp

Máy tạo project không có Docker; chưa xác minh image build/chạy được. Chạy đủ
ba lệnh Docker và gọi API trong README bước 6, lưu bằng chứng trước khi đánh dấu
tiêu chí 11. Kiểm tra rubric trong lớp có yêu cầu riêng về tên endpoint, notebook,
ngày dự báo hay báo cáo hay không. Không tuyên bố đã hoàn tất 12/12 ở trạng thái này.
