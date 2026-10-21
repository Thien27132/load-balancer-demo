# Kịch bản live demo — 5–7 phút

## Chuẩn bị

- python run_demo.py, mở http://127.0.0.1:8080.
- Ba backend Khỏe, độ trễ 100 ms.
- Dùng một tab; không chạy benchmark cùng lúc.
- Mở docs/experiment-results.md làm kết quả dự phòng.
- Chọn Round Robin và bấm Áp dụng để reset chỉ số.
- Tập trước các nút, giữ terminal để thấy lỗi nếu có.

## 0:00–1:15 — Round Robin

Chọn 12 yêu cầu, đồng thời 1. Chạy một đợt.
Chỉ nhật ký A/B/C và bộ đếm 4/4/4.
Nói: “Chọn tuần tự theo danh sách máy khỏe. Thuật toán không nhìn thời gian phản hồi.”

## 1:15–2:10 — Máy chậm

Bấm Làm chậm tại C (2.000 ms, tự xóa thống kê). Gửi 6 yêu cầu, đồng thời 6.
Quan sát A/B hoàn thành trước, C còn đang xử lý nhưng vẫn nhận hai lượt.
Nói: “Thứ tự hoàn thành khác thứ tự phân công. Chia đều lượt không đồng nghĩa đều tải.”
Chờ xong, bấm Nhanh lại tại C.

## 2:10–3:20 — Consistent Hashing

Chọn Consistent Hashing, 100 nút ảo, bấm Áp dụng.
Khóa user-001, chọn Lặp lại cùng một khóa, 6 yêu cầu.
Quan sát cùng backend. Dùng Tra khóa để xem vị trí trên vòng.
Đổi sang Nhiều khóa khác nhau, gửi 12 và giải thích phân phối không bắt buộc 4/4/4.
Nói: “Ổn định theo khóa khi vòng không đổi. Một khóa quá phổ biến vẫn có thể tạo điểm nóng.”

## 3:20–4:50 — Health checks

Bấm Dừng máy C. Tiến trình đã dừng nhưng trạng thái có thể còn Khỏe một lúc.
Chờ hai lần kiểm tra thất bại: C chuyển Lỗi, vòng còn A/B.
Gửi tiếp: chỉ máy khỏe nhận request. Khởi động C, chờ hai lần thành công để phục hồi.
Có thể gửi trong cửa sổ lỗi để thấy 502, nhưng không cam kết luôn bắt được vì phụ thuộc thời điểm.
Nói: “Health check không tức thời. Dừng tiến trình và phát hiện lỗi là hai sự kiện khác nhau.”

## 4:50–6:00 — Kết quả và nút ảo

Bấm So sánh ánh xạ: 1.000 khóa, bỏ C, 100 nút ảo.
Dữ liệu mẫu: 30,6% khóa đổi máy với Consistent Hashing, 66,4% với băm % N.
Chọn 1 nút ảo rồi Áp dụng và so sánh: tỷ lệ và phân phối thay đổi. Giải thích đây là tập khóa cố định, không phải con số chung cho mọi hệ thống.
Mở bảng benchmark thật; không kết luận một thuật toán luôn nhanh hơn từ chênh lệch nhỏ.

## Dự phòng

Nếu mạng local/cổng bị chặn: dùng ảnh docs/demo-preview.png và kết quả JSON đã lưu, nói rõ đây là kết quả chạy trước.
Nếu ứng dụng lỗi: giữ thông báo, Ctrl+C và khởi động lại. Không đổi cấu hình giữa lượt đo.
Nếu hết thời gian: ưu tiên RR → cùng khóa → dừng/phục hồi → bảng ánh xạ.

## Câu hỏi cần bảo vệ

1. Vì sao không dùng hash() Python? — Có thể thay đổi theo tiến trình; dùng SHA-256 ổn định.
2. Vì sao không hash(key) % N? — N thay đổi làm nhiều khóa không liên quan đổi máy.
3. Vnodes giải quyết mọi lệch tải? — Không; khóa nóng vẫn vào một backend.
4. Máy chậm có bị loại? — Chỉ nếu /health không đáp ứng ngưỡng; /work chậm không tự làm /health lỗi.
5. Vì sao một worker? — Bản này lưu vòng/metrics tại bộ nhớ; nhiều worker cần cơ chế chia sẻ/điều phối khác.
6. Request đang xử lý lúc máy chết? — Có thể lỗi 502/504; bản này không retry.
7. Có cân bằng CPU không? — Không; backend sleep để mô phỏng độ trễ I/O.
8. p95 là gì? — Khoảng 95% mẫu có độ trễ không vượt mức này; web giữ mẫu gần nhất, benchmark tính toàn bộ lượt.
9. Ai viết mã? — Khai báo AI hỗ trợ và trình bày phần nhóm đã đọc, sửa, kiểm chứng.
