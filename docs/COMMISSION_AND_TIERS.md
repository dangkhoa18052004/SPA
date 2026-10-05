# Hoa hồng kỹ thuật viên và hạng thành viên

## Hoa hồng (giai đoạn 3.2)

**Cấu hình**: Quản lý Dịch vụ → mục "Hoa hồng kỹ thuật viên" của từng dịch vụ.
- `% giá trị dịch vụ` hoặc `số tiền cố định / lượt`. Nếu nhập cả hai, số tiền cố định được dùng.
- Để trống cả hai: dịch vụ không có hoa hồng (vẫn ghi bản ghi 0đ để đối soát).
- Chỉ admin/manager thấy và sửa được mức hoa hồng.

**Thời điểm ghi**: khi lịch chuyển sang `completed` và đã có KTV được gán. Mỗi cặp (lịch, dịch vụ)
có đúng một `CommissionEntry` (ràng buộc `uq_commission_appointment_service`); bấm hoàn thành lặp
không tạo thêm. Lịch chưa gán KTV không sinh hoa hồng.

**Giá trị tính hoa hồng (base amount)**

| Nguồn buổi | Base amount |
| --- | --- |
| Trả lẻ (kể cả có voucher/điểm) | Giá niêm yết dịch vụ lúc hoàn thành. Ưu đãi do spa chịu |
| Buổi trong gói | Giá trị phân bổ của buổi (`unit_value_snapshot` của thẻ liệu trình) |
| Buổi quà tặng | Giá niêm yết chụp lúc tặng (`regular_price_snapshot`) |

Số tiền làm tròn tới đồng. Bản ghi lưu lại base, % hoặc số cố định, tên dịch vụ tại thời điểm ghi,
nên đổi giá/mức hoa hồng về sau không sửa lịch sử.

**Mở lại lịch**: admin chuyển lịch đã hoàn thành sang trạng thái khác → hoa hồng chuyển `voided`
(không bị xóa). Hoàn thành lại → khôi phục đúng bản ghi cũ, không tính lại theo mức mới.

**Lương**: Tổng hợp lương tháng = lương ca + hoa hồng + thưởng − khấu trừ. Cột "Hoa hồng" có ở
màn hình lương tháng (bấm vào số để xem chi tiết từng lịch), lương ngày, "Lương của tôi" và PDF.
Hoa hồng tính theo `earned_at` (giờ Việt Nam). Ở chế độ xem theo ngày, hoa hồng của ngày gắn vào ca
đầu tiên của nhân viên; nhân viên không có ca trong ngày đó chỉ thấy hoa hồng ở bảng tháng.
Sau khi hoàn thành thêm lịch trong tháng, bấm "Tổng hợp lương tháng" lại để cập nhật.

## Hạng thành viên (giai đoạn 3)

Hạng được tính lại từ ledger điểm mỗi lần đọc, không lưu số dư riêng, nên không ảnh hưởng đối soát
`available + reserved = SUM(ledger)`.

| Giao dịch | Ảnh hưởng tới điểm xét hạng |
| --- | --- |
| Tích điểm khi thanh toán (`earn`) | Cộng |
| Hoàn tiền thu hồi điểm đã tích (`refund` âm) | Trừ |
| Đổi điểm / đổi thưởng (`redeem`, `reward_redeem`) | Không ảnh hưởng – dùng điểm không tụt hạng |
| Hoàn lại điểm đã đổi (`refund` dương) | Không ảnh hưởng |
| Điều chỉnh thủ công | Chỉ khi bật "Tính cả điều chỉnh điểm thủ công" |

Ngưỡng mặc định: Thành viên 0 · Bạc 200 · Vàng 500 · Kim cương 1000 điểm xét hạng (với quy tắc
10 điểm / 100.000đ, Bạc tương ứng khoảng 2 triệu đồng chi tiêu). Sửa tại Điểm thưởng → Cấu hình →
Hạng thành viên. Ràng buộc: 1–10 hạng, hạng đầu từ 0 điểm, ngưỡng tăng dần, mã không trùng.

API: `GET /api/loyalty/me` trả `tier` (hạng hiện tại, hạng kế tiếp, điểm còn thiếu, % tiến độ);
`GET/PUT /api/admin/loyalty/tiers` cho admin/manager.
