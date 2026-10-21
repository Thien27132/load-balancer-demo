# Kết quả chạy thực tế — 21/10/2026

## Điều kiện

Windows, Python 3.11.9. Load balancer và ba backend ở tiến trình riêng trên cùng máy.
Backend sleep bất đồng bộ 100 ms. Bộ phát tải dùng 12 worker client, 120 yêu cầu/lượt, 3 lượt/thuật toán; warmup 12 yêu cầu trước mỗi lượt.
Tập khóa user-0000 ... user-0119. Consistent Hashing dùng 100 nút ảo/backend.
Cụm benchmark sử dụng cổng tạm riêng, không dùng cụm giao diện 8080.

## HTTP thật

| Thuật toán | Lượt | Thành công/giây | Độ trễ TB (ms) | p95 (ms) | Lỗi | Phân phối A/B/C |
|---|---:|---:|---:|---:|---:|---|
| Round Robin | 1 | 88,50 | 132,44 | 165,87 | 0 | 40 / 40 / 40 |
| Round Robin | 2 | 92,61 | 124,50 | 150,99 | 0 | 40 / 40 / 40 |
| Round Robin | 3 | 92,90 | 125,84 | 152,62 | 0 | 40 / 40 / 40 |
| Consistent Hashing | 1 | 89,39 | 127,42 | 153,86 | 0 | 43 / 44 / 33 |
| Consistent Hashing | 2 | 84,43 | 136,20 | 165,46 | 0 | 43 / 44 / 33 |
| Consistent Hashing | 3 | 92,55 | 126,98 | 150,55 | 0 | 43 / 44 / 33 |

Tổng 720 yêu cầu đo (không tính warmup), không lỗi.
Nguồn: ../benchmarks/results/http-20261021T031457491366Z.json.

Các lần chạy ngắn và cùng máy; chênh lệch nhỏ không đủ để kết luận hiệu năng vượt trội. Round Robin chia đúng bằng nhau; hashing giữ phân phối của tập khóa nên không nhất thiết bằng nhau.
Độ trễ đo phía client; không tính thời gian chờ worker chọn request, có tính chi phí HTTP. Đây không phải giới hạn chịu tải hay phép đo CPU.

## Ánh xạ trước/sau khi bỏ C — không gửi HTTP

Tập cố định 1.000 khóa user-0000 ... user-0999.

| Cách ánh xạ | Nút ảo/backend | Phân phối trước A/B/C | Khóa đổi máy | Tỷ lệ |
|---|---:|---|---:|---:|
| Consistent Hashing | 1 | 117 / 415 / 468 | 468 | 46,8% |
| Consistent Hashing | 100 | 333 / 361 / 306 | 306 | 30,6% |
| SHA-256(key) % N | Không áp dụng | 341 / 362 / 297 | 664 | 66,4% |

Nguồn: mapping-20261021T031457716248Z.json và mapping-20261021T031457910096Z.json trong benchmarks/results/.

Với Consistent Hashing, số khóa chuyển đúng bằng số khóa trước đó thuộc C. Các khóa thuộc A/B giữ nguyên máy. Với bộ dữ liệu này, 100 nút ảo phân phối đều hơn 1 nút ảo; không khẳng định càng nhiều nút ảo luôn tốt hơn ở mọi dữ liệu.

## Chậm, lỗi và phục hồi

scripts/verify_live.py đã kiểm chứng:
- C giả lập 200 ms chậm hơn A/B 10 ms rõ rệt.
- C giả lập 1.000 ms vượt timeout 400 ms của cấu hình test → HTTP 504.
- Dừng thật C → health check loại C; yêu cầu sau đó không đến C.
- Khởi động C → health check đưa C trở lại và C nhận request.
- Dừng cả ba máy và chờ loại hết → HTTP 503.

Đây là kiểm chứng chức năng, không phải bảng thống kê thời gian phát hiện. Chưa đo lặp nhiều lần thời gian failover hoặc benchmark các kịch bản lỗi/khóa nóng; công cụ đã hỗ trợ để nhóm tiếp tục làm.

## Tái lập

Chạy python scripts/record_sample_benchmarks.py để tạo các file mới. Không ghi đè hoặc sửa số liệu mẫu thành kết quả khác.
Thêm kết quả mới cùng cấu hình, thời gian, các tác vụ nền và giới hạn thí nghiệm.
