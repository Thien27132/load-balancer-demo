# Kiến trúc và các quyết định

## Một request đi qua đâu?

Browser / benchmark → POST /api/work → metrics.begin → thuật toán chọn backend khỏe → HTTPX POST backend/work → phản hồi → metrics.finish → client.

Bốn tiến trình: một load balancer, ba backend. run_demo.py chạy uvicorn một worker. Lifespan của app tạo các backend và client dùng lại, khởi động health checker, rồi hủy task và dừng tiến trình con khi thoát.

## Trách nhiệm module

| Module | Trách nhiệm |
|---|---|
| app.py | API, vòng đời, cấu hình hiện tại và xử lý yêu cầu |
| registry.py | Unknown/Healthy/Unhealthy, streak và thời điểm thay đổi |
| algorithms/ | Chọn Backend, không gửi HTTP |
| proxy.py | Chuyển tiếp, kiểm tra nội dung, timeout và lỗi |
| health_checker.py | HTTP GET /health định kỳ, xác minh cả ID backend |
| metrics.py | Counter đầy đủ, p95/log có giới hạn |
| processes.py | Chỉ start/stop tiến trình do app tạo, không kill tiến trình bên ngoài |
| web/ | Chọn kịch bản, gửi request, lấy snapshot thật mỗi 700 ms |
| benchmarks/ | Đo HTTP và thí nghiệm ánh xạ tách biệt |

## Round Robin

Danh sách backend sắp theo ID để kết quả có thể lặp lại. Mỗi lựa chọn trả phần tử next_index rồi tăng modulo số máy.
asyncio.Lock bảo vệ lượt chọn. Khi tập backend thay đổi, chỉ số đặt lại 0. Khi danh sách không đổi, polling và request không đặt lại vòng.
Chọn máy O(1); mã demo còn đồng bộ danh sách từ registry ở mỗi request để luôn sử dụng tập máy khỏe hiện tại.

## Consistent Hashing

- SHA-256 biến chuỗi thành số nguyên 256 bit ổn định.
- Backend A có các nút A#0, A#1 ... theo virtual_nodes.
- Sắp xếp các vị trí; hash khóa người dùng và bisect_left để tìm nút kế tiếp.
- Vượt cuối danh sách thì quay về đầu.
- Tên backend/nút ảo giữ nguyên khi thành viên khác bị loại.
- Với vòng có V nút, tra cứu O(log V); dựng lại vòng O(V log V).
- Khi bỏ C, những khóa vốn ở A/B giữ máy cũ; các khóa thuộc C chuyển sang nút còn lại kế tiếp.
- Nút ảo giảm lệch trên tập khóa rộng; không giải quyết một khóa nóng hoặc tự đo máy chậm.
- Vòng chỉ dựng lại khi tập backend thay đổi hoặc người dùng áp dụng số nút ảo khác.

## Health checks

Unknown ban đầu không nhận công việc. Hai lần thành công liên tiếp → Healthy.
Healthy giữ trạng thái sau một lỗi; đủ hai lỗi liên tiếp → Unhealthy.
Unhealthy cần hai lần thành công liên tiếp để phục hồi.
Lỗi làm mất chuỗi thành công và ngược lại.

Mỗi vòng kiểm tra đồng thời A/B/C, timeout 1 giây/máy, sau đó ngủ 2 giây. Vì thế thời gian phát hiện còn phụ thuộc vị trí trong chu kỳ và thời gian kiểm tra, không bảo đảm đúng 4 giây.
Client riêng cho health check tránh bị dùng hết pool bởi công việc.
Nút dừng chỉ dừng tiến trình; không cập nhật registry ngay, để quan sát được cửa sổ phát hiện.

## Lỗi

| HTTP | Nguyên nhân |
|---|---|
| 200 | Backend xử lý thành công |
| 409 | Đang có yêu cầu/cấu hình bận, không thể reset/đổi cấu hình |
| 422 | Dữ liệu đầu vào không hợp lệ |
| 502 | Lỗi kết nối, backend không trả 200 hoặc dữ liệu sai |
| 503 | Không có backend khỏe |
| 504 | Hết timeout chờ upstream |

Không tự retry. Timeout HTTPX theo pha được bổ sung wait_for giới hạn tổng thời gian chuyển tiếp.
Request đang bay vẫn có thể lỗi dù registry vừa loại máy đó. Thay đổi registry chỉ tác động lựa chọn kế tiếp.

## Nhất quán và thao tác điều khiển

Mọi registry/metrics/thuật toán chạy trên một event loop. Không await giữa kiểm tra idle và đổi thuật toán/reset. Việc chuyển tiếp có await nên nhiều request vẫn chạy đồng thời.
Một request giữ backend và tên thuật toán đã chọn; health thay đổi không sửa request đang chạy.
Process control được khóa riêng và chạy trong thread để thao tác chờ tiến trình không chặn event loop.
Đổi độ trễ chặn nhận request mới trong lúc cập nhật và tạo lượt thống kê mới.
Chỉ load balancer có token trong bộ nhớ để đổi độ trễ backend. Không ghi token vào file hoặc trả cho giao diện.

## Giới hạn thiết kế

Không chia sẻ trạng thái giữa nhiều worker. Không mở remote/public. Chưa mô hình hóa CPU, hàng đợi hữu hạn, cache thật hoặc session. Đây là nền tảng thí nghiệm thuật toán, không thay NGINX/HAProxy.
