<div align="center">

<img src="app/static/images/logo.jpg" alt="Biểu trưng Bin Spa" width="88" />

# Bin Spa

**Đặt lịch thuận tiện cho khách hàng. Vận hành tập trung cho spa.**

Ứng dụng web kết nối lịch hẹn, dịch vụ, liệu trình, thanh toán và nhân sự trong cùng một hệ thống.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-173F35?style=flat-square&logo=flask&logoColor=white)
![React](https://img.shields.io/badge/React-18-087EA4?style=flat-square&logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)

[Giao diện](#giao-diện) · [Tính năng](#tính-năng) · [Cài đặt](#cài-đặt-và-chạy-local) · [Kiến trúc](#kiến-trúc) · [Tài liệu](#tài-liệu)

</div>

![Trang chủ Bin Spa với tông xanh và giao diện giới thiệu dịch vụ](docs/images/readme/01-customer-home.png)

## Giới thiệu

Bin Spa là sản phẩm **demo phục vụ đồ án tốt nghiệp**, mô phỏng quy trình từ khi khách tìm hiểu dịch vụ, đặt lịch và mua gói đến khi nhân viên phục vụ, thu tiền và quản lý theo dõi hoạt động.

Dự án có ba không gian làm việc: website khách hàng, cổng nhân viên và trang quản trị theo vai trò. Giao diện kết hợp **React + TypeScript** cho các luồng tương tác với **Jinja** cho các trang nội dung; Flask cung cấp API và xử lý nghiệp vụ, PostgreSQL lưu dữ liệu.

> Bộ ảnh giới thiệu được chụp từ bản phát triển ngày **08/11/2026**, bằng dữ liệu minh họa trong môi trường riêng. Một số màn hình phản ánh thay đổi ở nhánh phát triển và có thể chưa có trong nhánh `main`. Xem [ghi chú bộ ảnh](docs/images/readme/README.md).

## Giao diện

### Trải nghiệm khách hàng

Khách xem giá và thời lượng dịch vụ, nhận ưu đãi phù hợp với hạng thành viên, sau đó chọn dịch vụ để đặt lịch.

| Danh mục dịch vụ | Đặt lịch trực tuyến |
| :---: | :---: |
| [![Danh mục dịch vụ với giá gốc và giá ưu đãi](docs/images/readme/02-service-catalog.png)](docs/images/readme/02-service-catalog.png) | [![Khách chọn dịch vụ và xem tóm tắt lịch hẹn](docs/images/readme/03-customer-booking.png)](docs/images/readme/03-customer-booking.png) |
| Tìm kiếm, phân loại và xem giá dịch vụ. | Chọn dịch vụ → chọn giờ/nhân viên → kiểm tra và xác nhận. |

### Điều hành spa

Trang quản trị tập trung các công việc hằng ngày, từ tiếp nhận lịch hẹn đến theo dõi kết quả kinh doanh.

![Tổng quan công việc với các lịch hẹn và trạng thái phục vụ trong ngày](docs/images/readme/04-admin-dashboard.png)

| Quản lý lịch hẹn | Cấu hình ưu đãi dịch vụ |
| :---: | :---: |
| [![Danh sách lịch hẹn theo khách hàng, nhân viên và trạng thái](docs/images/readme/05-admin-appointments.png)](docs/images/readme/05-admin-appointments.png) | [![Thiết lập mức giảm, hạng thành viên và ngày kết thúc tùy chọn](docs/images/readme/06-service-discounts.png)](docs/images/readme/06-service-discounts.png) |
| Tra cứu, phân công và theo dõi tiến trình phục vụ. | Giảm theo phần trăm, theo thời gian hoặc đúng hạng được chọn. |

### Chấm công và đối chiếu

Giờ nhân viên đề nghị, giờ vào/ra đã ghi nhận và giờ ca được xếp hiển thị cạnh nhau để quản lý có cơ sở xử lý yêu cầu.

| Yêu cầu chỉnh công | Bảng công |
| :---: | :---: |
| [![Đối chiếu giờ đề nghị, giờ thực tế và giờ ca làm](docs/images/readme/07-attendance-requests.png)](docs/images/readme/07-attendance-requests.png) | [![Bảng công với giờ vào ra, thời lượng và trạng thái phê duyệt](docs/images/readme/08-attendance-review.png)](docs/images/readme/08-attendance-review.png) |

<details>
<summary><strong>Xem giao diện trên điện thoại</strong></summary>

<p align="center">
  <img src="docs/images/readme/09-mobile-booking.png" alt="Chọn dịch vụ và đặt lịch trên điện thoại" width="280" />
  &nbsp;&nbsp;
  <img src="docs/images/readme/10-mobile-attendance.png" alt="Đối chiếu yêu cầu chấm công trên điện thoại" width="280" />
</p>

</details>

*Bấm vào ảnh để xem kích thước đầy đủ.*

## Tính năng

| Nhóm | Chức năng tiêu biểu |
| --- | --- |
| **Khách hàng** | Đăng ký/đăng nhập, quản lý hồ sơ, tìm dịch vụ, đặt và theo dõi lịch hẹn, xem gói/liệu trình đã mua, đánh giá và nhắn tin. |
| **Lễ tân** | Tiếp nhận lịch, quản lý khách hàng, bán dịch vụ/gói, thu tiền, theo dõi hóa đơn và chăm sóc khách hàng theo quyền. |
| **Kỹ thuật viên** | Xem lịch được phân công, thông tin phục vụ và gói dịch vụ được phép xem; theo dõi lịch ca, chấm công và thu nhập. |
| **Quản lý / quản trị** | Điều phối lịch, quản lý nhân sự và danh mục theo quyền, duyệt công, xử lý kỳ lương, xem doanh thu và báo cáo. |
| **Gói và liệu trình** | Quản lý số buổi, thời hạn, lịch sử sử dụng và dịch vụ tặng; quyền tặng dành cho lễ tân/quản lý/quản trị. |
| **Ưu đãi và thành viên** | Điểm thưởng, voucher, hạng thành viên; giảm giá dịch vụ công khai hoặc chỉ dành cho hạng được chọn. |
| **Thanh toán** | Thu tiền mặt, tạo VietQR và tiếp nhận xác nhận qua SePay khi đã cấu hình. Tích hợp MoMo Sandbox được giữ cho luồng thử nghiệm. |
| **Chăm sóc và AI** | Chat, email xác nhận/dặn dò, gợi ý dịch vụ, trợ lý đặt lịch và phân tích da khi bật các tích hợp tương ứng. |

### Quy tắc nghiệp vụ nổi bật

- **Chốt giá tại lúc đặt lịch:** thay đổi chương trình giảm giá sau đó không tự đổi giá dịch vụ đã đặt. Voucher và điểm thưởng được áp dụng tiếp trên số tiền sau giảm, theo điều kiện sử dụng.
- **Ưu đãi đúng đối tượng:** chương trình chỉ chọn hạng Vàng thì các hạng khác không được hưởng hoặc thấy ưu đãi riêng đó. Có thể chọn ngày dừng hoặc để chương trình không giới hạn thời gian.
- **Đối chiếu trước khi duyệt công:** phân biệt giờ đề nghị, giờ đã ghi nhận và giờ ca; ghi rõ trường hợp thiếu giờ vào/ra. Duyệt yêu cầu sửa giờ và duyệt công trả lương là hai bước riêng.
- **Phân quyền tại API:** giao diện hiển thị theo vai trò và server tiếp tục kiểm tra quyền khi đọc/ghi dữ liệu.

## Công nghệ

| Thành phần | Công nghệ |
| --- | --- |
| Backend | Python 3.12, Flask 3.1, SQLAlchemy, Flask-Migrate / Alembic |
| Frontend | React 18, TypeScript, Vite, Ant Design, Tailwind CSS, Jinja |
| Dữ liệu | PostgreSQL; SQLite dùng cho các fixture kiểm thử độc lập |
| Xác thực | JWT, mật khẩu băm và kiểm quyền theo vai trò |
| Tích hợp | VietQR / SePay, MoMo Sandbox, Resend / SMTP, Gemini, ESP32 / RFID tùy cấu hình |
| Kiểm thử | pytest, Vitest, Node test runner, Playwright CLI và các bộ kiểm tra trình duyệt |

## Cài đặt và chạy local

### 1. Chuẩn bị

Cài **Python 3.12**, **Node.js 22.12 trở lên trong nhánh 22**, **npm**, **PostgreSQL** và **Git**. Tạo một database riêng cho bản demo trước khi chạy migration.

```bash
git clone https://github.com/dangkhoa18052004/SPA.git
cd SPA
python -m venv .venv
```

Kích hoạt môi trường ảo:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

### 2. Cài thư viện và build giao diện

```bash
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
```

Giao diện React được build vào `app/static/portal/`. Cần build lại sau khi sửa mã trong `frontend/src/`.

### 3. Cấu hình môi trường

Sao chép `.env.example` thành `.env`, rồi điền cấu hình của máy đang chạy. Các giá trị dưới đây chỉ là mẫu:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql://DB_USER:DB_PASSWORD@localhost:5432/binspa_demo
SECRET_KEY=replace-with-a-random-secret
JWT_SECRET_KEY=replace-with-another-random-secret
ADMIN_INITIAL_USERNAME=admin
ADMIN_INITIAL_PASSWORD=replace-with-your-own-password

# Tắt các tích hợp nền khi chỉ xem giao diện local.
SEPAY_POLL_ENABLED=false
AI_CHAT_JOBS_ENABLED=false
```

Mật khẩu quản trị khởi tạo cần ít nhất **12 ký tự**. Không đưa `.env`, khóa API hoặc bản sao dữ liệu cá nhân vào Git. Email, ngân hàng và AI cần cấu hình riêng khi muốn thử các luồng tương ứng.

### 4. Khởi tạo database và quản trị viên

Với **database mới** đã tạo ở bước chuẩn bị:

```bash
python -m flask --app wsgi:app db upgrade
python create_admin.py
```

Nếu dùng database đã có dữ liệu, xem [hướng dẫn migration](docs/DATABASE_MIGRATIONS.md) và sao lưu trước khi nâng cấp. Không dùng `db.create_all()` thay cho lịch sử migration.

### 5. Chạy ứng dụng

```bash
# Chỉ chạy website để xem demo local.
python run.py --web-only
```

Mở `http://127.0.0.1:5000`. Đăng nhập quản trị ở `/admin/login`; khách đặt lịch tại `/appointments/create`.

| Nhu cầu | Lệnh / tài liệu |
| --- | --- |
| Chạy web cùng notification worker và AI chat worker | `python run.py` — xem [hướng dẫn worker](docs/NOTIFICATION_WORKER.md). |
| Thử GPS qua mạng LAN | `python run.py --web-only --https` — dùng HTTPS và cấp quyền vị trí trên thiết bị. |
| Bật cổng nhân viên, GPS và quy trình công/lương | [Cấu hình chấm công và bảng lương](docs/GPS_ATTENDANCE_PAYROLL.md). |
| Chạy qua WSGI | Entry point `wsgi:app`; tham khảo `render.yaml` cho web và worker riêng. |

Sau khi khởi tạo, thêm nhân viên, dịch vụ và ca làm qua giao diện quản trị. Bộ dữ liệu dùng chụp ảnh không phải dữ liệu mặc định của ứng dụng.

## Kiến trúc

```mermaid
flowchart LR
    C[Website khách hàng] --> F[Flask · API và nghiệp vụ]
    E[Cổng nhân viên] --> F
    A[Trang quản trị] --> F
    F --> DB[(PostgreSQL)]
    W[Worker thông báo và AI] --> DB
    W -. tích hợp tùy chọn .-> P[Email · Gemini]
    F -. tích hợp tùy chọn .-> Q[VietQR · SePay · MoMo Sandbox]
```

```text
SPA/
├── app/
│   ├── admin/               # Route quản trị
│   ├── routes/              # API, khách hàng và tích hợp
│   ├── services/            # Xử lý nghiệp vụ
│   ├── templates/           # Trang Jinja và shell React
│   ├── static/              # Ảnh, CSS, JS và frontend đã build
│   ├── models.py            # Model nghiệp vụ chính
│   └── operations_models.py # Model chấm công và lương
├── frontend/src/            # React, TypeScript và các entry frontend
├── migrations/              # Lịch sử thay đổi schema
├── tests/                   # Kiểm thử backend, frontend và browser
├── scripts/                 # Công cụ kiểm thử và vận hành
├── docs/                    # Tài liệu và bộ ảnh giao diện
├── iot/                     # Firmware ESP32 / RFID
├── run.py                   # Chạy local
├── wsgi.py                  # Entry WSGI
└── .env.example             # Mẫu cấu hình, không chứa khóa thật
```

## Kiểm thử

Cài thêm công cụ bằng `python -m pip install -r requirements-dev.txt`, sau đó chọn phạm vi cần kiểm tra:

| Phạm vi | Lệnh |
| --- | --- |
| Backend | `python -m pytest -q` |
| Frontend | `npm --prefix frontend test` |
| Kiểm tra TypeScript và build | `npm --prefix frontend run build` |
| Bộ test JavaScript | `node --test tests/*.test.cjs` |
| Backend với PostgreSQL kiểm thử riêng | `python scripts/test_with_postgres.py -- -q` |
| Hành trình nhân viên, công và lương trên browser | `python tests/operations_browser_check.py` |

Các bộ browser có yêu cầu công cụ riêng; xem hướng dẫn trong runner trước khi chạy. Việc gửi email, nhận webhook ngân hàng và sử dụng AI thật cần được kiểm chứng riêng với cấu hình của môi trường đó.

## Tài liệu

| Chủ đề | Hướng dẫn |
| --- | --- |
| Database | [Migration và database cũ](docs/DATABASE_MIGRATIONS.md) |
| Nhân sự | [Chấm công GPS và bảng lương](docs/GPS_ATTENDANCE_PAYROLL.md) |
| Gói và chăm sóc | [Đặt lịch, tặng dịch vụ và đánh giá](docs/BOOKING_GIFTS_REVIEWS.md) |
| Thành viên | [Điểm thưởng và đổi thưởng](docs/LOYALTY_REWARDS_3A.md) · [Voucher](docs/VOUCHER_ISSUANCE.md) |
| Thông báo | [Notification worker](docs/NOTIFICATION_WORKER.md) |
| AI | [Trợ lý đặt lịch](docs/AI_BOOKING_AGENT.md) · [Chat xử lý nền](docs/AI_CHAT_NAVIGATION.md) · [Phân tích da](docs/SKIN_ANALYSIS_AI.md) |
| Hình ảnh | [Nguồn ảnh, môi trường chụp và danh mục màn hình](docs/images/readme/README.md) |

---

<div align="center">

**Bin Spa · Đồ án tốt nghiệp**

Thiết kế trải nghiệm khách hàng gắn liền với quy trình vận hành spa.

</div>
