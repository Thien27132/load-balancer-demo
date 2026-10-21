# Load Balancer Lab — T22 (Python)

Demo hoàn chỉnh cho môn Lập trình mạng: **Round Robin + Consistent Hashing + health checks**.
Giao diện tiếng Việt; HTTP thật giữa các tiến trình; không cần Node.js, Docker hay cơ sở dữ liệu.

## Chạy nhanh trên máy hiện tại

Máy đã có Python cùng các thư viện cần thiết. Mở **start-demo.cmd** hoặc chạy:

```powershell
cd "C:\Users\ADMIN\OneDrive - ptit.edu.vn\Documents\load-balancer-demo"
python run_demo.py
```

Mở **http://127.0.0.1:8080**. Chờ A, B, C báo **Khỏe** (thường vài giây).
Giữ cửa sổ chạy chương trình. Dừng bằng **Ctrl+C** để đóng cả các backend.

## Cài mới trên máy khác (Python 3.11 trở lên)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_demo.py
```

Không cần kích hoạt môi trường hoặc thay đổi chính sách PowerShell.
Sau khi tạo môi trường, start-demo.cmd tự chọn Python trong .venv.

## Thử ngay

1. Chọn **Round Robin**, bấm **Áp dụng & bắt đầu lượt mới**. Gửi 12 yêu cầu: mỗi máy nhận 4.
2. Bấm **Làm chậm** tại C, gửi 12 lần nữa: mỗi máy vẫn nhận 4 nhưng C mất khoảng 2 giây/lượt.
3. Bấm **Nhanh lại** tại C. Chọn **Consistent Hashing**, bấm Áp dụng, chọn **Lặp lại cùng một khóa**, gửi 12: cùng khóa đến cùng máy.
4. Chọn **Nhiều khóa khác nhau**: quan sát phân phối. Khóa phổ biến có thể tạo điểm nóng.
5. Bấm **Dừng máy** tại C: tiến trình C thật sự dừng. Chờ health check báo Lỗi rồi gửi tiếp.
6. Bấm **Khởi động** tại C: chờ máy trở lại Khỏe.
7. Bấm **So sánh ánh xạ** ở cuối trang: tính trên 1.000 khóa trước/sau khi loại C, so sánh consistent hashing với băm % N.

**Lưu ý về thao tác:** thay giá trị trong danh sách thuật toán chưa đổi thuật toán đang chạy; cần bấm Áp dụng. Nhãn phía trên sơ đồ cho biết thuật toán thực tế.
Đổi thuật toán hoặc đổi độ trễ sẽ bắt đầu lượt thống kê mới. Xóa thống kê không đặt lại lượt Round Robin; bấm Áp dụng để đặt lại. Không đổi thuật toán/độ trễ/reset khi còn yêu cầu đang xử lý. Vẫn có thể dừng máy trong lúc gửi tải để quan sát lỗi.

## Kiến trúc

- Load balancer / giao diện: 127.0.0.1:8080.
- Backend A/B/C: 9001/9002/9003, ba tiến trình dùng chung backend/app.py.
- Lựa chọn backend ở Python, không nằm trong JavaScript.
- Health checker kiểm tra mỗi 2 giây sau một vòng kiểm tra; timeout 1 giây, ngưỡng 2 lần lỗi/2 lần thành công liên tiếp.
- Một worker / event loop cho load balancer. HTTP client dùng lại kết nối, health checker dùng client riêng.
- Cấu hình nằm trong config.json; khi đổi cổng backend, cập nhật cả port và url. Khởi động lại để đọc cấu hình mới.

## Kiểm thử

```powershell
python -m pytest -q
python scripts/verify_live.py
```

Lệnh thứ hai tự mở một cụm riêng trên cổng tạm, kiểm tra HTTP và dừng/khởi động backend thật, rồi đóng cụm. Không ảnh hưởng demo ở cổng 8080.

Đã kiểm chứng 23 unit/API tests; integration script đạt các kịch bản RR, hash, chậm, timeout 504, stop/start/recovery và hết máy khỏe 503. Xem docs/validation.md.

## Benchmark

Nếu chạy trực tiếp trên demo, dừng thao tác trên trang và đảm bảo ba backend khỏe:

```powershell
python -m benchmarks.run_load --requests 120 --concurrency 12 --repeat 3
python -m benchmarks.run_load --requests 120 --concurrency 12 --repeat 3 --pattern hot
python -m benchmarks.compare_mapping --virtual-nodes 1
python -m benchmarks.compare_mapping --virtual-nodes 100
```

Hoặc chạy một cụm riêng, không can thiệp trang đang mở:

```powershell
python scripts/record_sample_benchmarks.py
```

JSON lưu trong benchmarks/results/. Các file mẫu và nhận xét nằm trong docs/experiment-results.md.
Script benchmark đổi thuật toán và xóa thống kê, sau đó trả lại thuật toán ban đầu; không khôi phục thống kê cũ.

## Các số liệu có nghĩa gì?

- **Được phân công:** lượt đã được chọn gửi đến máy, kể cả sau đó lỗi.
- **Đang xử lý:** lượt đang chờ backend tại load balancer, không phải số kết nối TCP hay CPU.
- **Thời gian trên web:** đo ở load balancer từ tiếp nhận đến hoàn tất; gồm chi phí chọn máy và HTTP, kể cả lỗi.
- **p95 trên web:** mẫu tối đa 1.000 kết quả gần nhất. Tổng đếm không bị giới hạn 1.000.
- **Benchmark:** đo phía client, không tính thời gian chờ được worker phát tải lấy ra; có tính lỗi. Throughput = số thành công / tổng thời gian lượt chạy.
- Gửi tuần tự trên web có nghỉ 180 ms giúp nhìn rõ. Không dùng số liệu đó để so tốc độ tối đa.

## Phạm vi và giới hạn

Đây là demo lớp học, không phải reverse proxy đa dụng: chỉ chuyển tiếp POST /api/work sang /work. Không có TLS, WebSocket, streaming, retry, lưu phiên hay đồng bộ nhiều load balancer.
Cả bốn tiến trình dùng một máy. Backend sleep bất đồng bộ mô phỏng thời gian công việc, không mô phỏng CPU hoặc hàng đợi có năng lực giới hạn. Vì vậy không dùng kết quả để khẳng định thuật toán nào luôn nhanh hơn.
Health check không phát hiện lỗi tức thì; request trong cửa sổ chưa phát hiện có thể nhận 502/504. Không có máy khỏe trả 503.
Nút ảo giúp cải thiện phân phối trên nhiều khóa nhưng không tự chia nhỏ một khóa quá nóng.
Dữ liệu thống kê nằm trong bộ nhớ và mất khi khởi động lại. Những tab đang mở dùng chung cấu hình và thống kê.
Chỉ dùng cục bộ; chương trình bind 127.0.0.1. Không mở ra Internet.

## Xử lý sự cố

- **Cổng đang dùng:** đóng phiên demo cũ bằng Ctrl+C hoặc sửa các cổng trong config.json. Chương trình không tự kill dịch vụ bên ngoài.
- **Thiếu thư viện:** dùng đúng Python của .venv và cài requirements.txt.
- **Tất cả máy Unknown lúc mới mở:** chờ đủ lần health check. Kiểm tra log terminal nếu máy không trở lại.
- **HTTP 409:** đợi lượt đang chạy xong trước khi reset/đổi thuật toán.
- **Thao tác không được phản ánh:** tải lại trang sau khi cập nhật mã nguồn; không chạy hai phiên demo chung cổng.
- **Test treo trong môi trường sandbox Windows:** asyncio có thể bị chặn kết nối loopback; chạy trong terminal thông thường.
- Không đóng cưỡng bức cửa sổ khi có thể dùng Ctrl+C để chương trình dọn tiến trình con.

## Tài liệu

- docs/architecture.md — đường đi request, vòng băm, sức khỏe và lỗi.
- docs/demo-script.md — kịch bản trình diễn 5–7 phút và Q&A.
- docs/experiment-results.md — kết quả thật và giới hạn.
- docs/validation.md — phạm vi đã kiểm chứng.
- /docs trên trang demo — OpenAPI tương tác.

## Nguồn kỹ thuật

- FastAPI lifespan: https://fastapi.tiangolo.com/advanced/events/
- HTTPX async client: https://www.python-httpx.org/async/
- HTTPX timeouts: https://www.python-httpx.org/advanced/timeouts/
- Python hashlib: https://docs.python.org/3/library/hashlib.html
- Python bisect: https://docs.python.org/3/library/bisect.html

## Khai báo hỗ trợ AI

ChatGPT/Codex hỗ trợ thiết kế kiến trúc, viết mã, giao diện, kiểm thử, benchmark và bản nháp tài liệu.
Nhóm cần tự chạy lại, rà soát, hiểu và bảo vệ từng phần trong Q&A; cập nhật khai báo theo công việc thực tế trước khi nộp.
