"""Read-only view of service invoices and package sale receipts."""
import json
from datetime import timezone, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload, selectinload
from ..models import HoaDon, GoiDichVuPurchase, ChiTietHoaDon
from . import loyalty_service as loyalty

LOCAL_TZ = timezone(timedelta(hours=7))


def timestamp(value, local=False):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ if local else timezone.utc)
    return value.astimezone(LOCAL_TZ).isoformat()


def service_query():
    return HoaDon.query.options(joinedload(HoaDon.khachhang), joinedload(HoaDon.nhanvien),
                                selectinload(HoaDon.thanhtoan),
                                selectinload(HoaDon.chitiet).joinedload(ChiTietHoaDon.dichvu))


def package_query():
    return GoiDichVuPurchase.query.options(joinedload(GoiDichVuPurchase.customer),
                                          joinedload(GoiDichVuPurchase.creator),
                                          joinedload(GoiDichVuPurchase.confirmer))


def serialize_service(invoice):
    payments = sorted(invoice.thanhtoan, key=lambda payment: payment.matt)
    payment = payments[-1] if payments else None
    cash_received = None
    if payment and payment.phuongthuc == 'Tiền mặt':
        try:
            metadata = json.loads(payment.ghichu or '{}')
            cash_received = metadata.get('cash_received') if isinstance(metadata, dict) else None
            if cash_received is not None:
                received = Decimal(str(cash_received))
                cash_received = str(received) if received.is_finite() and received >= loyalty.payable(invoice) else None
        except (ValueError, TypeError, InvalidOperation):
            cash_received = None  # Historical notes may be free text or unrelated JSON.
    return dict(transaction_type='service', display_type_label='Dịch vụ riêng lẻ', **loyalty.payment_summary(invoice),
                id=invoice.mahd, code=f'HD{invoice.mahd:06d}',
                customer_name=invoice.khachhang.hoten if invoice.khachhang else 'N/A',
                customer_phone=invoice.khachhang.sdt if invoice.khachhang else None,
                appointment_id=invoice.malh, package_name=None,
                total_amount=str(invoice.tongtien), status=invoice.trangthai,
                payment_method=payment.phuongthuc if payment else None,
                created_at=timestamp(invoice.ngaylap),
                paid_at=timestamp(payment.ngaythanhtoan) if payment else None,
                staff_name=invoice.nhanvien.hoten if invoice.nhanvien else None,
                source_label=invoice.nhanvien.hoten if invoice.nhanvien else 'Không có thông tin',
                cash_received=cash_received,
                change=str(Decimal(cash_received) - loyalty.payable(invoice)) if cash_received is not None else None,
                payment_reference=f'HD{invoice.mahd}', can_pay=invoice.trangthai == 'Chưa thanh toán',
                detail_url=f'/api/admin/billing/transactions/service/{invoice.mahd}',
                items=[dict(name=item.dichvu.tendv if item.dichvu else 'Dịch vụ không xác định',
                            quantity=item.soluong, unit_price=str(item.dongia), total=str(item.thanhtien))
                       for item in invoice.chitiet])


def serialize_package(purchase):
    snapshot = purchase.snapshot_json or {}
    staff = purchase.confirmer or purchase.creator
    return dict(transaction_type='package', display_type_label='Gói dịch vụ', id=purchase.id, **loyalty.payment_summary(purchase),
                code=f'PG{purchase.id:06d}', customer_name=purchase.customer.hoten if purchase.customer else 'N/A',
                customer_phone=purchase.customer.sdt if purchase.customer else None,
                appointment_id=None, package_name=snapshot.get('tengoi', 'Gói dịch vụ'),
                total_amount=str(purchase.amount),
                status={'paid': 'Đã thanh toán', 'pending': 'Chưa thanh toán',
                        'failed': 'Thất bại', 'cancelled': 'Đã hủy'}.get(purchase.status, purchase.status),
                payment_method={'cash': 'Tiền mặt', 'vietqr': 'VietQR', 'points': 'Điểm thưởng'}.get(purchase.payment_method, purchase.payment_method),
                created_at=timestamp(purchase.created_at, local=True), paid_at=timestamp(purchase.paid_at, local=True),
                staff_name=staff.hoten if staff else None, source_label=staff.hoten if staff else 'Khách mua online',
                cash_received=str(purchase.cash_received) if purchase.cash_received is not None else None,
                change=str(purchase.cash_received - loyalty.payable(purchase)) if purchase.cash_received is not None else None,
                payment_reference=f'PKG{purchase.id}', validity_months=snapshot.get('validity_months'),
                can_pay=purchase.status == 'pending',
                detail_url=f'/api/admin/billing/transactions/package/{purchase.id}',
                items=[dict(name=item.get('tendv', 'Dịch vụ'), sessions=item.get('total_sessions', 0))
                       for item in snapshot.get('items', [])])


def transactions(filters):
    kind = filters.get('type', 'all')
    status = filters.get('status', 'all')
    status = {'paid': 'Đã thanh toán', 'unpaid': 'Chưa thanh toán'}.get(status, status)
    if kind not in ('all', 'service', 'package'):
        raise ValueError('Loại hóa đơn không hợp lệ')
    if status not in ('all', 'Đã thanh toán', 'Chưa thanh toán', 'Thất bại', 'Đã hủy'):
        raise ValueError('Trạng thái không hợp lệ')
    from datetime import date
    start = date.fromisoformat(filters['start_date']) if filters.get('start_date') else None
    end = date.fromisoformat(filters['end_date']) if filters.get('end_date') else None
    if start and end and start > end:
        raise ValueError('Ngày bắt đầu phải trước ngày kết thúc')
    search = filters.get('search', '').strip().casefold()
    rows = []
    if kind in ('all', 'service'):
        rows.extend(serialize_service(invoice) for invoice in service_query().all())
    if kind in ('all', 'package'):
        rows.extend(serialize_package(purchase) for purchase in package_query().all())
    def matches(row):
        created = date.fromisoformat(row['created_at'][:10]) if row['created_at'] else None
        return (not start or created and created >= start) and (not end or created and created <= end) and (
            status == 'all' or row['status'] == status) and (not search or search in ' '.join(
                str(row.get(key) or '') for key in ('code', 'id', 'customer_name', 'customer_phone',
                                                   'appointment_id', 'package_name')).casefold())
    rows = [row for row in rows if matches(row)]
    rows.sort(key=lambda row: (row['created_at'] or '', row['transaction_type'], row['id']), reverse=True)
    paid = [row for row in rows if row['status'] == 'Đã thanh toán']
    stats = dict(total=len(rows), paid=len(paid), unpaid=sum(row['status'] == 'Chưa thanh toán' for row in rows),
                 revenue=str(sum((Decimal(row['payable_amount']) for row in paid), Decimal('0'))))
    return rows, stats
