# Giai đoạn 5 – Gemini AI booking agent và tóm tắt kinh doanh

## Cấu hình môi trường

```env
GEMINI_API_KEY=<khóa Google AI Studio – chỉ đặt trong .env hoặc biến môi trường, không commit>
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODELS=gemini-flash-latest,gemini-3.5-flash-lite   # dùng khi model chính quá tải (429/5xx)
GEMINI_TIMEOUT=30
```

Để trống `GEMINI_API_KEY` thì AI tắt: widget không hiện, `/api/ai/*` trả 503 kèm thông báo cấu hình;
đặt lịch, thanh toán, dashboard… vẫn chạy bình thường. Kiểm tra: `GET /api/ai/status`.
`gemini-2.5-flash` không còn mở cho khóa mới (Google trả 404), nên mặc định là `gemini-3.8-flash`.

## Kiến trúc

| Thành phần | Vai trò |
| --- | --- |
| `app/services/ai_service.py` | Gọi Gemini (REST), vòng tool-calling ≤ 5 lượt, chặn quyền theo vai trò, ẩn PII, kiểm số trong tóm tắt |
| `app/routes/ai_bp.py` | `POST /api/ai/chat`, `POST /api/ai/booking/confirm`, `POST /api/ai/business-summary`, `GET /api/ai/status` |
| `app/models.py` → `AIBookingDraft` (migration `20261005_0016`) | Bản nháp đặt lịch, hết hạn sau 30 phút, liên kết `malh` khi đã xác nhận |
| `app/static/js/ai_chat.js`, `css/ai-chat.css` | Widget khách: chat, thẻ bản nháp, nút "Xác nhận đặt lịch" |
| `dashboard.html/js` | Khối "Tóm tắt kinh doanh AI" cho admin/manager |

AI chỉ điều phối. Mọi đọc dữ liệu đi qua tool; mọi ghi lịch hẹn đi qua `appointment_service.create_appointment`.

```
Khách ──POST /api/ai/chat──▶ ai_bp ──▶ ai_service.chat
                                         │  (lọc câu hỏi y khoa → từ chối, không gọi Gemini)
                                         │  scrub(tên, SĐT, email)
                                         ▼
                                   Gemini generateContent ◀──────────────┐
                                         │ functionCall                    │ functionResponse
                                         ▼                                 │
                     run_tool (chỉ tool được phép theo vai trò) ───────────┘
                       ├─ get_available_services_tool → DichVu (giá DB)
                       ├─ check_availability_tool     → appointment_service (ca làm, trùng lịch, giờ trống)
                       ├─ create_booking_draft_tool   → AIBookingDraft (KHÔNG tạo LichHen; chỉ khách đã đăng nhập)
                       └─ get_business_metrics_tool   → analytics_service (chỉ admin/manager)
                                         │ text + draft
                                         ▼
Khách bấm "Xác nhận đặt lịch" ──POST /api/ai/booking/confirm──▶ confirm_booking_tool
        khóa dòng draft → kiểm tra chủ sở hữu/hạn → appointment_service.create_appointment(source='ai')
        → đúng 1 LichHen; gọi lại trả cùng lịch (idempotent)

Quản lý ──POST /api/ai/business-summary──▶ _metric_range (analytics_service)
        → FACTS do server tạo từ JSON
        → Gemini chỉ viết summary + suggestions (JSON) → bỏ câu có số không có trong dữ liệu
```

## Guardrails

- Tool xác nhận **không** được khai báo cho model; lịch hẹn chỉ tạo khi khách bấm nút xác nhận.
- Khách ẩn danh không được khai báo tool tạo nháp; khách không bao giờ có tool số liệu kinh doanh.
- Ngày giờ phải cụ thể `YYYY-MM-DDTHH:MM` và ở tương lai; thiếu/mơ hồ → tool trả `need: ngaygio`, model hỏi lại, không ghi DB.
- Câu hỏi chẩn đoán bệnh/kê thuốc bị từ chối trước khi gọi Gemini; system prompt giới hạn phạm vi spa.
- Không gửi tên/SĐT/email khách cho Gemini (cả lịch sử chat và tham số tool gửi lại); không log key hay nội dung chat.

## Kiểm thử

- Tự động (Gemini mock, không gọi mạng): `pytest tests/test_ai_booking_agent.py`.
- Thật (cần key, DB trong bộ nhớ, không gửi email): `python tests/ai_manual_check.py`.
- Trình duyệt (Gemini giả lập): `python tests/ui_improvements_browser_check.py`.
