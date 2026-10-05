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
from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload, joinedload

from ..extensions import db
from ..models import (
    DanhGia,
    LichHen,
    KhachHang,
    NhanVien,
    AppointmentStatus,
    DichVu, DanhGiaDichVu, ReviewReply, ChiTietLichHen,
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


def review_values(rating, comment):
    if isinstance(rating, bool) or not isinstance(rating, (str, int)) or not str(rating).isdigit():
        raise ReviewValidationError('Điểm đánh giá phải là số nguyên từ 1 đến 5 sao.')
    value = int(rating)
    if not 1 <= value <= 5:
        raise ReviewValidationError('Điểm đánh giá phải từ 1 đến 5 sao.')
    if comment is not None and (not isinstance(comment, str) or len(comment) > 5000):
        raise ReviewValidationError('Nhận xét tối đa 5000 ký tự.')
    return value, (comment or '').strip() or None


def completed_appointment(customer_id, appointment_id):
    apt = db.session.get(LichHen, appointment_id)
    if not apt:
        raise ReviewNotFoundError()
    if apt.makh != customer_id:
        raise ReviewPermissionError('Bạn không có quyền đánh giá lịch hẹn của người khác.')
    if apt.trangthai != AppointmentStatus.COMPLETED:
        raise ReviewValidationError('Chỉ có thể đánh giá lịch hẹn đã hoàn thành.')
    return apt


def mask_customer_name(name):
    words = (name or 'Khách hàng').split()
    return ' '.join(words[:-1] + [words[-1][:1] + '.'])


def serialize_review(review, public=False):
    reply = review.reply
    used = {d.madv for d in review.lichhen.chitiet} if review.lichhen else set()
    services = [dict(madv=link.madv, tendv=link.service.tendv) for link in review.service_links if link.madv in used]
    result = dict(madg=review.madg, rating=review.rating, comment=review.comment or '',
        created_at=review.created_at.isoformat(), updated_at=review.updated_at.isoformat() if review.updated_at else None,
        service_items=services, services=', '.join(s['tendv'] for s in services),
        customer_name=mask_customer_name(review.khachhang.hoten) if public else review.khachhang.hoten,
        verified=bool(review.lichhen and review.lichhen.trangthai == 'completed' and review.lichhen.makh == review.makh and services),
        reply=dict(id=reply.id, content=reply.content, created_at=reply.created_at.isoformat(),
            updated_at=reply.updated_at.isoformat() if reply.updated_at else None) if reply else None)
    if not public:
        result.update(malh=review.malh, manv=review.manv,
            staff_name=review.nhanvien.hoten if review.nhanvien else 'N/A',
            nhanvien=review.nhanvien.hoten if review.nhanvien else 'N/A',
            appointment_date=review.lichhen.ngaygio.isoformat() if review.lichhen else None)
        if reply:
            result['reply']['staff_name'] = reply.staff.hoten
    return result


def create_review(customer_id, appointment_id, rating, comment=None, service_ids=None):
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
    rating_int, comment = review_values(rating, comment)

    # 2. Validate appointment
    apt = completed_appointment(customer_id, appointment_id)
    actual_services = {d.madv for d in apt.chitiet}
    selected = actual_services if service_ids is None else service_ids
    if not isinstance(selected, (set, list)) or not selected or any(isinstance(s, bool) or not isinstance(s, int) for s in selected):
        raise ReviewValidationError('Vui lòng chọn dịch vụ đã sử dụng để đánh giá.')
    if not set(selected).issubset(actual_services):
        raise ReviewPermissionError('Không thể đánh giá dịch vụ chưa sử dụng trong lịch hẹn.')

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
        new_review.service_links = [DanhGiaDichVu(madv=s) for s in sorted(set(selected))]
        db.session.commit()

        staff_name = apt.nhanvien.hoten if apt.nhanvien else "Spa Team"
        return {
            "success": True,
            "message": "Cảm ơn bạn đã gửi đánh giá!",
            "review": serialize_review(new_review),
        }

    except IntegrityError:
        db.session.rollback()
        raise ReviewConflictError('Lịch hẹn này đã có đánh giá.')
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

    results = [serialize_review(r) for r in reviews]

    return {"success": True, "reviews": results}


def rating_summary(manv_ids=None):
    """{manv: {"average": float, "count": int}} cho các nhân viên có đánh giá (chỉ số tổng hợp, không lộ nội dung)."""
    query = db.session.query(DanhGia.manv, func.avg(DanhGia.rating), func.count(DanhGia.madg)).filter(
        DanhGia.manv.isnot(None))
    if manv_ids is not None:
        query = query.filter(DanhGia.manv.in_(list(manv_ids)))
    return {manv: {"average": round(float(avg), 1), "count": int(count)}
            for manv, avg, count in query.group_by(DanhGia.manv).all()}


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
        cust_name = mask_customer_name(r.khachhang.hoten if r.khachhang else "Khách hàng")
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


def owned_review(review_id, customer_id):
    review = db.session.get(DanhGia, review_id)
    if not review:
        raise ReviewNotFoundError()
    if review.makh != customer_id:
        raise ReviewPermissionError('Bạn không có quyền quản lý đánh giá của người khác.')
    return review


def update_review(review_id, customer_id, data):
    review = owned_review(review_id, customer_id)
    completed_appointment(customer_id, review.malh)
    if set(data) - {'rating', 'comment'}:
        raise ReviewValidationError('Chỉ được sửa số sao và nhận xét.')
    review.rating, review.comment = review_values(data.get('rating', review.rating), data.get('comment', review.comment))
    review.updated_at = datetime.utcnow()
    db.session.commit()
    return serialize_review(review)


def delete_review(review_id, customer_id):
    db.session.delete(owned_review(review_id, customer_id))
    db.session.commit()


def staff_review_permission(review, staff):
    if not staff.trangthai or staff.role not in ('admin', 'manager', 'staff'):
        raise ReviewPermissionError('Không có quyền quản lý đánh giá.')
    if staff.role == 'staff' and review.manv != staff.manv:
        raise ReviewPermissionError('Đánh giá không thuộc lịch hẹn bạn thực hiện.')


def save_reply(review_id, staff, content):
    # Serialize updates to the single official response.
    DanhGia.query.filter_by(madg=review_id).update({DanhGia.madg: DanhGia.madg}, synchronize_session=False)
    review = DanhGia.query.filter_by(madg=review_id).populate_existing().first()
    if not review:
        raise ReviewNotFoundError()
    staff_review_permission(review, staff)
    if not isinstance(content, str) or not content.strip() or len(content) > 5000:
        raise ReviewValidationError('Phản hồi phải có nội dung, tối đa 5000 ký tự.')
    if review.reply:
        review.reply.content, review.reply.staff_id = content.strip(), staff.manv
        review.reply.updated_at = datetime.utcnow()
    else:
        review.reply = ReviewReply(staff_id=staff.manv, content=content.strip())
    db.session.commit()
    return serialize_review(review)


def manage_reviews(staff, filters):
    if not staff.trangthai:
        raise ReviewPermissionError('Tài khoản đã ngừng hoạt động.')
    query = DanhGia.query.join(KhachHang)
    if staff.role == 'staff':
        query = query.filter(DanhGia.manv == staff.manv)
    if filters.get('rating'):
        query = query.filter(DanhGia.rating == int(filters['rating']))
    if filters.get('service'):
        query = query.filter(DanhGia.service_links.any(madv=int(filters['service'])))
    if filters.get('staff'):
        query = query.filter(DanhGia.manv == int(filters['staff']))
    if filters.get('replied') in ('yes', 'no'):
        query = query.filter(DanhGia.reply.has() if filters['replied'] == 'yes' else ~DanhGia.reply.has())
    if filters.get('search'):
        query = query.filter(KhachHang.hoten.ilike('%' + filters['search'].strip() + '%'))
    page = max(1, int(filters.get('page', 1)))
    total = query.count()
    rows = query.order_by(DanhGia.created_at.desc(), DanhGia.madg.desc()).offset((page-1)*20).limit(20).all()
    return dict(success=True, reviews=[serialize_review(r) for r in rows], page=page, total=total, per_page=20,
        services=[dict(madv=s.madv, tendv=s.tendv) for s in DichVu.query.order_by(DichVu.tendv).all()],
        staff=[dict(manv=s.manv, hoten=s.hoten) for s in NhanVien.query.filter_by(trangthai=True).all()] if staff.role != 'staff' else [])


def public_service_reviews(service_id, page=1, per_page=10):
    if not db.session.get(DichVu, service_id):
        raise ReviewNotFoundError('Không tìm thấy dịch vụ.')
    query = DanhGia.query.join(LichHen, DanhGia.malh == LichHen.malh).join(DanhGiaDichVu).join(
        ChiTietLichHen, and_(ChiTietLichHen.malh == DanhGia.malh, ChiTietLichHen.madv == DanhGiaDichVu.madv)).filter(
        DanhGiaDichVu.madv == service_id, LichHen.trangthai == 'completed', LichHen.makh == DanhGia.makh)
    total = query.count()
    ratings = query.with_entities(DanhGia.rating, func.count(DanhGia.madg)).group_by(DanhGia.rating).all()
    distribution = {str(n): 0 for n in range(1, 6)}
    distribution.update({str(n): count for n, count in ratings})
    average = round(sum(n*count for n, count in ratings)/total, 1) if total else 0
    rows = query.options(selectinload(DanhGia.service_links).joinedload(DanhGiaDichVu.service),
        joinedload(DanhGia.khachhang), joinedload(DanhGia.reply),
        joinedload(DanhGia.lichhen).selectinload(LichHen.chitiet)).order_by(
        DanhGia.created_at.desc(), DanhGia.madg.desc()).offset((page-1)*per_page).limit(per_page).all()
    return dict(success=True, stats=dict(average_rating=average, total_reviews=total, distribution=distribution),
        reviews=[serialize_review(r, public=True) for r in rows], page=page, per_page=per_page, total=total)
