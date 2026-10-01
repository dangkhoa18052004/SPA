# app/services/review_service.py
"""
Review Service - Quản lý đánh giá dịch vụ (Verified Rating).
Ràng buộc:
- Khách hàng đã sử dụng dịch vụ (lịch hẹn đã hoàn thành - completed).
- Mỗi lịch hẹn chỉ được đánh giá 1 lần (1 review per appointment).
- Điểm đánh giá từ 1 đến 5 sao.
"""

from datetime import datetime
from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models import (
    DanhGia,
    LichHen,
    KhachHang,
    NhanVien,
    AppointmentStatus,
)


class ReviewServiceError(Exception):
    """Lỗi cơ sở cho các thao tác đánh giá."""
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ReviewNotFoundError(ReviewServiceError):
    def __init__(self, message="Không tìm thấy lịch hẹn hoặc đánh giá"):
        super().__init__(message, status_code=404)


class ReviewPermissionError(ReviewServiceError):
    def __init__(self, message="Bạn không có quyền đánh giá lịch hẹn này"):
        super().__init__(message, status_code=403)


class ReviewValidationError(ReviewServiceError):
    def __init__(self, message):
        super().__init__(message, status_code=400)


class ReviewConflictError(ReviewServiceError):
    def __init__(self, message="Lịch hẹn này đã được đánh giá trước đó"):
        super().__init__(message, status_code=409)


def create_review(customer_id, appointment_id, rating, comment=None):
    """
    Tạo đánh giá mới cho lịch hẹn:
    1. Kiểm tra rating trong khoảng 1..5.
    2. Lịch hẹn tồn tại.
    3. Lịch hẹn thuộc về khách hàng (customer_id).
    4. Lịch hẹn đã ở trạng thái 'completed'.
    5. Chưa từng được đánh giá (1 review/malh).
    6. Tự động liên kết nhân viên thực hiện (apt.manv).
    """
    # 1. Validate rating
    try:
        rating_int = int(rating)
    except (ValueError, TypeError):
        raise ReviewValidationError("Điểm đánh giá không hợp lệ. Phải là số nguyên từ 1 đến 5 sao.")

    if rating_int < 1 or rating_int > 5:
        raise ReviewValidationError("Điểm đánh giá phải từ 1 đến 5 sao.")

    # 2. Validate appointment
    apt = LichHen.query.get(appointment_id)
    if not apt:
        raise ReviewNotFoundError("Không tìm thấy lịch hẹn cần đánh giá.")

    # 3. Validate ownership
    if apt.makh != customer_id:
        raise ReviewPermissionError("Bạn không có quyền đánh giá lịch hẹn của người khác.")

    # 4. Validate status: chỉ cho phép đánh giá lịch completed
    if apt.trangthai != AppointmentStatus.COMPLETED:
        raise ReviewValidationError(
            f"Chỉ có thể đánh giá lịch hẹn đã hoàn thành. Trạng thái hiện tại: '{AppointmentStatus.to_vietnamese(apt.trangthai)}'."
        )

    # 5. Validate unique review
    existing_review = DanhGia.query.filter_by(malh=appointment_id).first()
    if existing_review:
        raise ReviewConflictError("Lịch hẹn này đã có đánh giá. Mỗi lịch hẹn chỉ được đánh giá một lần.")

    # 6. Tạo đánh giá
    try:
        new_review = DanhGia(
            malh=appointment_id,
            makh=customer_id,
            manv=apt.manv,
            rating=rating_int,
            comment=comment.strip() if comment and isinstance(comment, str) else None,
            created_at=datetime.utcnow(),
        )
        db.session.add(new_review)
        db.session.commit()

        staff_name = apt.nhanvien.hoten if apt.nhanvien else "Spa Team"
        return {
            "success": True,
            "message": "Cảm ơn bạn đã gửi đánh giá!",
            "review": {
                "madg": new_review.madg,
                "malh": new_review.malh,
                "rating": new_review.rating,
                "comment": new_review.comment,
                "nhanvien": staff_name,
                "created_at": new_review.created_at.isoformat(),
            },
        }

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Lỗi khi lưu đánh giá: {e}", exc_info=True)
        raise ReviewServiceError("Lỗi hệ thống khi lưu đánh giá.", status_code=500)


def get_my_reviews(customer_id):
    """Lấy danh sách các đánh giá của khách hàng hiện tại."""
    reviews = (
        DanhGia.query.filter_by(makh=customer_id)
        .order_by(DanhGia.created_at.desc())
        .all()
    )

    results = []
    for r in reviews:
        services = []
        if r.lichhen:
            for d in r.lichhen.chitiet:
                if d.dichvu:
                    services.append(d.dichvu.tendv)

        results.append({
            "madg": r.madg,
            "malh": r.malh,
            "rating": r.rating,
            "comment": r.comment or "",
            "created_at": r.created_at.isoformat(),
            "appointment_date": r.lichhen.ngaygio.isoformat() if r.lichhen else None,
            "staff_name": r.nhanvien.hoten if r.nhanvien else "N/A",
            "services": ", ".join(services) if services else "Dịch vụ Spa",
        })

    return {"success": True, "reviews": results}


def get_staff_reviews(manv):
    """Lấy danh sách đánh giá và điểm trung bình của một nhân viên kỹ thuật."""
    staff = NhanVien.query.get(manv)
    if not staff:
        raise ReviewNotFoundError("Không tìm thấy nhân viên.")

    reviews = (
        DanhGia.query.filter_by(manv=manv)
        .order_by(DanhGia.created_at.desc())
        .all()
    )

    total_reviews = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / total_reviews, 1) if total_reviews > 0 else 0.0

    star_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in reviews:
        if r.rating in star_distribution:
            star_distribution[r.rating] += 1

    review_list = []
    for r in reviews:
        cust_name = r.khachhang.hoten if r.khachhang else "Khách hàng"
        review_list.append({
            "madg": r.madg,
            "rating": r.rating,
            "comment": r.comment or "",
            "customer_name": cust_name,
            "created_at": r.created_at.isoformat(),
        })

    return {
        "success": True,
        "staff": {
            "manv": staff.manv,
            "hoten": staff.hoten,
            "chucvu": staff.chucvu.tencv if staff.chucvu else "Kỹ thuật viên",
        },
        "stats": {
            "total_reviews": total_reviews,
            "average_rating": avg_rating,
            "star_distribution": star_distribution,
        },
        "reviews": review_list,
    }


def get_admin_review_stats():
    """Thống kê tổng quan toàn bộ đánh giá cho trang Admin."""
    total_reviews = db.session.query(func.count(DanhGia.madg)).scalar() or 0
    avg_rating_raw = db.session.query(func.avg(DanhGia.rating)).scalar() or 0.0
    average_rating = round(float(avg_rating_raw), 1)

    dist_rows = (
        db.session.query(DanhGia.rating, func.count(DanhGia.madg))
        .group_by(DanhGia.rating)
        .all()
    )
    star_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r, cnt in dist_rows:
        if r in star_distribution:
            star_distribution[r] = cnt

    recent_reviews = (
        DanhGia.query.order_by(DanhGia.created_at.desc())
        .limit(10)
        .all()
    )

    recent_list = []
    for r in recent_reviews:
        recent_list.append({
            "madg": r.madg,
            "malh": r.malh,
            "rating": r.rating,
            "comment": r.comment or "",
            "customer_name": r.khachhang.hoten if r.khachhang else "Khách hàng",
            "staff_name": r.nhanvien.hoten if r.nhanvien else "N/A",
            "created_at": r.created_at.isoformat(),
        })

    return {
        "success": True,
        "stats": {
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "star_distribution": star_distribution,
        },
        "recent_reviews": recent_list,
    }
