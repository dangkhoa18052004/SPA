# SPA – WebApp quản lý Spa

## Giới thiệu

**SPA** là dự án xây dựng **web application quản lý spa** nhằm hỗ trợ số hóa các nghiệp vụ vận hành trong spa như quản lý khách hàng, nhân viên, dịch vụ, lịch hẹn, hóa đơn, thanh toán và theo dõi hoạt động kinh doanh.

Hệ thống được phát triển chủ yếu bằng **Python Flask**, kết hợp với:
- **PostgreSQL** để lưu trữ dữ liệu
- **Flask-SQLAlchemy** để thao tác cơ sở dữ liệu
- **Flask-Migrate** để quản lý migration
- **Flask-JWT-Extended** để xác thực và phân quyền
- **Flask-Mail / Resend** để gửi email xác thực và thông báo
- **MoMo Sandbox** để hỗ trợ thanh toán trực tuyến

---

## Mục tiêu dự án

Mục tiêu của hệ thống là xây dựng một nền tảng giúp spa có thể:

- Quản lý thông tin khách hàng và nhân viên
- Quản lý dịch vụ và lịch hẹn
- Theo dõi ca làm và lương nhân viên
- Hỗ trợ thanh toán và quản lý hóa đơn
- Tăng trải nghiệm người dùng với email xác nhận, OTP và chat
- Hỗ trợ quản trị viên theo dõi thống kê hoạt động của spa

---

## Tính năng chính

### 1. Xác thực và quản lý tài khoản
- Đăng ký tài khoản khách hàng
- Đăng nhập hệ thống
- Xác thực bằng **JWT**
- Gửi **OTP qua email** để kích hoạt tài khoản
- Hỗ trợ quản lý thông tin hồ sơ người dùng

### 2. Quản lý khách hàng
- Lưu trữ thông tin khách hàng
- Theo dõi lịch sử lịch hẹn
- Quản lý tài khoản và trạng thái hoạt động

### 3. Quản lý nhân viên
- Quản lý danh sách nhân viên
- Quản lý vai trò / chức vụ
- Quản lý ca làm việc
- Theo dõi lương và bảng lương chi tiết

### 4. Quản lý dịch vụ spa
- Thêm / sửa / xóa dịch vụ
- Lưu mô tả, giá, thời lượng và trạng thái dịch vụ
- Hỗ trợ hiển thị danh sách dịch vụ cho khách hàng

### 5. Đặt lịch hẹn
- Khách hàng có thể tạo lịch hẹn trực tuyến
- Chọn dịch vụ và thời gian đặt lịch
- Kiểm tra nhân viên có rảnh hay không
- Gửi email xác nhận lịch hẹn

### 6. Hóa đơn và thanh toán
- Tạo và quản lý hóa đơn
- Theo dõi trạng thái thanh toán
- Hỗ trợ thanh toán trực tuyến qua **MoMo Sandbox**
- Tạo QR / link thanh toán cho khách hàng

### 7. Chat và tương tác
- Hỗ trợ hội thoại giữa khách hàng và nhân viên
- Lưu trữ tin nhắn
- Theo dõi trạng thái đã đọc

### 8. Dashboard và thống kê
- Thống kê lịch hẹn theo trạng thái
- Thống kê doanh thu
- Thống kê số lượng khách hàng
- Theo dõi nhân viên đang làm việc trong ngày

---

## Kiến trúc hệ thống

Dự án được tổ chức theo kiến trúc Flask application package.

### Backend
Phần backend được xây dựng bằng **Flask** với mô hình chia module rõ ràng theo:
- `routes`: các API chính của hệ thống
- `admin`: các module quản trị
- `services`: các dịch vụ xử lý nghiệp vụ
- `models`: các model dữ liệu

### Giao diện
Dự án không chỉ có API mà còn có giao diện web được tổ chức với:
- `templates/admin`
- `templates/customer`
- `static/css`
- `static/js`
- `static/images`

Điều này cho thấy hệ thống được xây dựng theo hướng **web app hoàn chỉnh**, kết hợp giữa giao diện hiển thị và API backend.

---

## Công nghệ sử dụng

### Backend Framework
- Python
- Flask
- Flask-CORS
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-JWT-Extended
- Flask-Mail

### Database
- PostgreSQL

### Authentication & Security
- JWT
- Password Hashing

### Email & Notification
- Flask-Mail
- Resend

### Payment
- MoMo Sandbox

### Frontend / Giao diện
- HTML
- CSS
- JavaScript
- Jinja2 Templates

---

## Cấu trúc thư mục

```bash
SPA/
├── app/
│   ├── admin/                 # Các module quản trị
│   ├── routes/                # Các API route chính
│   ├── services/              # Các service xử lý nghiệp vụ
│   ├── static/                # CSS, JS, images
│   ├── templates/             # Giao diện admin và customer
│   ├── __init__.py            # Hàm create_app và đăng ký blueprint
│   ├── config.py              # Cấu hình ứng dụng
│   ├── decorators.py          # Decorator phân quyền / kiểm tra truy cập
│   ├── extensions.py          # Khởi tạo db, migrate, jwt, mail
│   ├── models.py              # Các bảng dữ liệu
│   └── utils.py               # Hàm hỗ trợ
│
├── uploads/                   # File upload
├── CSDL.sql                   # Script cơ sở dữ liệu
├── create_admin.py            # Tạo tài khoản admin mặc định
├── requirements.txt           # Danh sách thư viện
├── run.py                     # File chạy ứng dụng
├── wsgi.py                    # WSGI entry point
├── build.sh                   # Script build/deploy
└── README.md

Cách chạy dự án
1. Clone project
git clone https://github.com/dangkhoa18052004/SPA.git
cd SPA
2. Tạo môi trường ảo
python -m venv venv
Kích hoạt môi trường ảo:
Windows
venv\\Scripts\\activate
macOS / Linux
source venv/bin/activate
3. Cài đặt thư viện
pip install -r requirements.txt
4. Cấu hình biến môi trường

Tạo file .env và cấu hình các biến cần thiết, ví dụ:

DATABASE_URL=postgresql://user:password@localhost:5432/Spa1
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_secret
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email
MAIL_PASSWORD=your_password
MAIL_USE_TLS=True
MAIL_FROM=your_email
MOMO_PARTNER_CODE_SANDBOX=your_partner_code
MOMO_ACCESS_KEY_SANDBOX=your_access_key
MOMO_SECRET_KEY_SANDBOX=your_secret_key
MOMO_API_ENDPOINT_SANDBOX=your_api_endpoint
YOUR_REDIRECT_URL=http://127.0.0.1:5000/payment/return
YOUR_IPN_URL=http://127.0.0.1:5000/api/payment/momo-ipn
YOUR_BASE_DOMAIN=http://127.0.0.1:5000
5. Chạy migrate database
flask db upgrade
6. Chạy ứng dụng
python run.py






