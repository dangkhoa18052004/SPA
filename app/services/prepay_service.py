"""Thanh toán trước khi đặt lịch (VietQR). Caller giữ transaction.

Hóa đơn trả trước là HoaDon bình thường gắn malh của lịch hẹn, chỉ gồm dịch vụ không dùng buổi gói/quà.
Sau khi hoàn thành dịch vụ, luồng "Tạo hóa đơn" trả lại đúng hóa đơn này, nên khách đã trả không phải trả lại.
"""
from ..extensions import db
from ..models import HoaDon, ChiTietHoaDon, LieuTrinhUsage
from . import loyalty_service as loyalty
from .appointment_service import AppointmentValidationError

UNPAID, PAID, CANCELLED = 'Chưa thanh toán', 'Đã thanh toán', 'Đã hủy'


def invoice_for(appointment):
    return HoaDon.query.filter_by(malh=appointment.malh).first()


def _billable(appointment):
    covered = {u.madv for u in LieuTrinhUsage.query.filter(
        LieuTrinhUsage.malh == appointment.malh, LieuTrinhUsage.state.in_(('reserved', 'consumed'))).all()}
    return [d for d in appointment.chitiet if d.dichvu and d.madv not in covered]


def _fill(invoice, details):
    for row in ChiTietHoaDon.query.filter_by(mahd=invoice.mahd).all():
        db.session.delete(row)
    total = sum(d.dichvu.gia for d in details)
    invoice.tongtien = total
    invoice.payable_amount = total
    for d in details:
        db.session.add(ChiTietHoaDon(mahd=invoice.mahd, madv=d.madv, soluong=1, dongia=d.dichvu.gia, thanhtien=d.dichvu.gia))


def _release_offers(invoice):
    """Trả lại điểm/voucher đang giữ cho hóa đơn chưa thanh toán trước khi sửa hoặc hủy."""
    if invoice.loyalty_discount:
        loyalty.release_points(invoice)
    if invoice.reward_discount:
        loyalty.release_reward(invoice)


def create_prepaid_invoice(appointment):
    """Tạo hóa đơn chờ thanh toán cho phần phải trả của lịch. Không có phần phải trả (toàn buổi gói) → None."""
    existing = invoice_for(appointment)
    if existing:
        return existing
    details = _billable(appointment)
    if not details:
        return None
    if not appointment.manv:
        raise AppointmentValidationError('Lịch chưa có kỹ thuật viên nên chưa thể thanh toán trước')
    invoice = HoaDon(makh=appointment.makh, manv=appointment.manv, tongtien=0, trangthai=UNPAID,
                     malh=appointment.malh)
    db.session.add(invoice)
    db.session.flush()
    _fill(invoice, details)
    db.session.flush()
    return invoice


def ensure_changeable(appointment):
    invoice = invoice_for(appointment)
    if invoice and invoice.trangthai == PAID:
        raise AppointmentValidationError(
            'Lịch hẹn đã thanh toán trước nên không đổi dịch vụ online. Vui lòng liên hệ spa để được hỗ trợ.')
    return invoice


def sync_after_service_change(appointment):
    """Đổi dịch vụ: hóa đơn trả trước chưa thanh toán được tính lại theo dịch vụ mới."""
    invoice = ensure_changeable(appointment)
    if not invoice or invoice.trangthai != UNPAID:
        return invoice
    _release_offers(invoice)
    details = _billable(appointment)
    if not details:
        invoice.trangthai = CANCELLED
        return invoice
    _fill(invoice, details)
    db.session.flush()
    return invoice


def on_appointment_cancelled(appointment):
    """Hủy lịch: hóa đơn chưa trả bị hủy (điểm/voucher trả lại); đã trả thì trả về 'refund' để spa hoàn tiền."""
    invoice = invoice_for(appointment)
    if not invoice:
        return None
    if invoice.trangthai == UNPAID:
        _release_offers(invoice)
        invoice.trangthai = CANCELLED
        return 'void'
    if invoice.trangthai == PAID:
        return 'refund'
    return None


def summary(appointment, invoice=None):
    invoice = invoice if invoice is not None else invoice_for(appointment)
    if not invoice:
        return None
    return dict(mahd=invoice.mahd, trangthai=invoice.trangthai, payable_amount=str(loyalty.payable(invoice)))
