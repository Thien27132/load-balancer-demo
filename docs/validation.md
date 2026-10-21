# Kiểm chứng triển khai

Ngày: 21/10/2026, múi giờ Asia/Bangkok.

## Đã thực hiện

- python -m pytest -q: **23 passed**.
- Python compileall cho backend, load_balancer, benchmarks, scripts, tests: thành công.
- node --check web/app.js: thành công.
- scripts/verify_live.py: đạt với bốn tiến trình HTTP thật và tự dọn tiến trình.
- Benchmark riêng: 6 lượt x 120 yêu cầu đo = 720 thành công, 0 lỗi.
- Mở trang trong trình duyệt và kiểm tra hiển thị backend, gửi đợt, thống kê và vòng băm.
- Ảnh giao diện: demo-preview.png.

Test API dùng ASGITransport và MockTransport để kiểm soát lỗi/timeout; các test đó không thay thế thử nghiệm TCP thật. verify_live.py cung cấp phần thử nghiệm tiến trình và loopback thật.

## Môi trường đã dùng

Python 3.11.9; FastAPI 0.111.0; Uvicorn 0.30.1; HTTPX 0.28.1; Pydantic 2.7.4; pytest 8.2.2.
Có một PendingDeprecationWarning từ dependency multipart của môi trường có sẵn, không phải test thất bại.
requirements.txt cho phép phiên bản trong khoảng tương thích; nếu cài môi trường khác, chạy lại tests để xác nhận.

## Những điều chưa chứng minh

- Hiệu năng production, mạng nhiều máy, TLS và khả năng chịu tải tối đa.
- Mobile browser/device matrix và khả năng truy cập đầy đủ với screen reader.
- Thời gian phát hiện lỗi chính xác trên nhiều lượt đo.
- Hệ thống nhiều worker hoặc nhiều load balancer dùng chung trạng thái.

## Ghi chú môi trường kiểm thử

Sandbox Windows chặn kết nối nội bộ của asyncio. Các bài kiểm thử chạy ngoài sandbox sau khi được cấp phép.
Công cụ benchmark và integration tạo cụm trên cổng tạm, chỉ dừng tiến trình do chính nó tạo.
