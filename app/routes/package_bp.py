from flask import Blueprint, request, jsonify, g, render_template

from ..extensions import db
from ..decorators import customer_required, roles_required
from ..models import GoiDichVu, GoiDichVuPurchase, TheLieuTrinh, KhachHang, DichVu
from ..services import package_service as service
from ..services.appointment_service import AppointmentValidationError
from ..services.vietqr_service import generate_vietqr_payment_info, vietqr_available
from ..services.upload_service import read_validated_image, InvalidUploadError
from sqlalchemy import or_, func
import json
from functools import wraps
from flask_jwt_extended.exceptions import NoAuthorizationError

package_bp = Blueprint('packages', __name__)


@package_bp.errorhandler(NoAuthorizationError)
def missing_customer_session(error):
    return jsonify(success=False, message='Phiên đăng nhập đã hết hạn'), 401


def active_staff_roles(*roles):
    def decorate(fn):
        @roles_required(*roles)
        @wraps(fn)
        def guarded(*args, **kwargs):
            if not g.current_user.trangthai:
                return jsonify(success=False, message='Tài khoản đã ngừng hoạt động'), 403
            return fn(*args, **kwargs)
        return guarded
    return decorate


package_manager_required = active_staff_roles('admin', 'manager')
package_sales_required = active_staff_roles('admin', 'manager', 'letan')


@package_bp.errorhandler(InvalidUploadError)
def invalid_image(error):
    db.session.rollback()
    return jsonify(success=False, message=str(error)), 400


def package_payload():
    try:
        data = request.get_json(silent=True) if request.is_json else json.loads(request.form.get('data', '{}'))
    except (ValueError, TypeError):
        raise AppointmentValidationError('Dữ liệu gói không hợp lệ')
    if not isinstance(data, dict):
        raise AppointmentValidationError('Dữ liệu gói không hợp lệ')
    image = request.files.get('anhgoi')
    return data, read_validated_image(image) if image else None


@package_bp.route('/api/packages/payment-options')
def payment_options():
    return jsonify(success=True, vietqr_available=vietqr_available())


@package_bp.route('/admin/package-sales')
def package_sales_page():
    return render_template('admin/package_sales.html')


@package_bp.route('/api/admin/packages/<int:package_id>/image', methods=['PUT'])
@package_manager_required
def package_image_upload(package_id):
    package = db.session.get(GoiDichVu, package_id)
    if not package:
        return jsonify(success=False, message='Không tìm thấy gói'), 404
    image = request.files.get('anhgoi')
    if not image:
        raise InvalidUploadError('Vui lòng chọn ảnh')
    package.anhgoi = read_validated_image(image)
    db.session.commit()
    return jsonify(success=True, package=service.serialize_package(package))


@package_bp.errorhandler(AppointmentValidationError)
def validation(error):
    db.session.rollback()
    return jsonify(success=False, message=error.message), 400


@package_bp.route('/packages')
@package_bp.route('/packages/<int:package_id>')
def package_page(package_id=None):
    if package_id and not GoiDichVu.query.filter_by(magoi=package_id, active=True).first():
        return 'Không tìm thấy gói dịch vụ', 404
    return render_template('customer/packages.html', package_id=package_id)


@package_bp.route('/admin/packages')
def admin_package_page():
    return render_template('admin/packages.html')


@package_bp.route('/admin/packages/new')
def admin_package_create_page():
    return render_template('admin/package_form.html', package_id=None, form_mode='create')


@package_bp.route('/admin/packages/<int:package_id>')
def admin_package_detail_page(package_id):
    return render_template('admin/package_detail.html', package_id=package_id)


@package_bp.route('/admin/packages/<int:package_id>/edit')
def admin_package_edit_page(package_id):
    return render_template('admin/package_form.html', package_id=package_id, form_mode='edit')


@package_bp.route('/api/packages')
def packages():
    return jsonify(success=True, packages=[service.serialize_package(p) for p in
        GoiDichVu.query.filter_by(active=True).order_by(GoiDichVu.magoi).all()])


@package_bp.route('/api/packages/<int:package_id>')
def package_detail(package_id):
    package = GoiDichVu.query.filter_by(magoi=package_id, active=True).first()
    if not package:
        return jsonify(success=False, message='Không tìm thấy gói'), 404
    return jsonify(success=True, package=service.serialize_package(package))


def serialize_purchase(purchase):
    record = TheLieuTrinh.query.filter_by(purchase_id=purchase.id).first()
    result = dict(id=purchase.id, magoi=purchase.magoi, tengoi=purchase.snapshot_json['tengoi'],
        amount=str(purchase.amount), status=purchase.status, payment_method=purchase.payment_method,
        created_at=purchase.created_at.isoformat(), mathe=record.mathe if record else None)
    result.update(payment_reference=f'PKG{purchase.id}', receipt_code=f'PG{purchase.id:06d}',
        customer_name=purchase.customer.hoten, phone=purchase.customer.sdt,
        paid_at=purchase.paid_at.isoformat() if purchase.paid_at else None,
        created_by_staff=purchase.created_by_staff, confirmed_by_staff=purchase.confirmed_by_staff,
        staff_name=(purchase.confirmer or purchase.creator).hoten if (purchase.confirmer or purchase.creator) else None,
        cash_received=str(purchase.cash_received) if purchase.cash_received is not None else None,
        change=str(purchase.cash_received-purchase.amount) if purchase.cash_received is not None else None,
        items=purchase.snapshot_json['items'], validity_months=purchase.snapshot_json['validity_months'])
    result['vietqr_available'] = vietqr_available()
    if purchase.status == 'pending' and purchase.payment_method == 'vietqr' and vietqr_available():
        result['payment'] = generate_vietqr_payment_info(purchase.amount, f'PKG{purchase.id}')
    return result


@package_bp.route('/api/packages/<int:package_id>/purchase', methods=['POST'])
@customer_required
def purchase_package(package_id):
    data = request.get_json(silent=True) or {}
    if data.get('payment_method', 'vietqr') == 'vietqr' and not vietqr_available():
        return jsonify(success=False, message='VietQR tạm thời chưa khả dụng; vui lòng thanh toán tại quầy'), 503
    try:
        purchase = service.create_purchase(package_id, g.current_user.makh, data.get('payment_method', 'vietqr'))
        result = serialize_purchase(purchase)
        db.session.commit()
    except RuntimeError:
        db.session.rollback()
        return jsonify(success=False, message='VietQR chưa được cấu hình; vui lòng thanh toán tại quầy'), 503
    return jsonify(success=True, purchase=result), 201


@package_bp.route('/api/packages/my-purchases')
@customer_required
def my_purchases():
    return jsonify(success=True, purchases=[serialize_purchase(p) for p in
        GoiDichVuPurchase.query.filter_by(makh=g.current_user.makh).order_by(GoiDichVuPurchase.id.desc()).all()])


@package_bp.route('/api/packages/purchases/<int:purchase_id>')
@package_bp.route('/api/packages/purchases/<int:purchase_id>/status')
@customer_required
def purchase_status(purchase_id):
    purchase = GoiDichVuPurchase.query.filter_by(id=purchase_id, makh=g.current_user.makh).first()
    if not purchase:
        return jsonify(success=False, message='Không tìm thấy giao dịch'), 404
    return jsonify(success=True, purchase=serialize_purchase(purchase))


@package_bp.route('/api/packages/my-treatments')
@customer_required
def treatments():
    return jsonify(success=True, treatments=[service.serialize_treatment(t) for t in
        TheLieuTrinh.query.filter_by(makh=g.current_user.makh).order_by(TheLieuTrinh.mathe.desc()).all()])


@package_bp.route('/api/packages/my-treatments/<int:record_id>')
@customer_required
def treatment_detail(record_id):
    record = TheLieuTrinh.query.filter_by(mathe=record_id, makh=g.current_user.makh).first()
    if not record:
        return jsonify(success=False, message='Không tìm thấy liệu trình'), 404
    return jsonify(success=True, treatment=service.serialize_treatment(record, history=True))


@package_bp.route('/api/admin/packages', methods=['GET', 'POST'])
@package_manager_required
def admin_packages():
    if not g.current_user.trangthai:
        return jsonify(success=False, message='Tài khoản đã ngừng hoạt động'), 403
    if request.method == 'POST':
        data, image = package_payload()
        package = service.save_package(data)
        if image is not None:
            package.anhgoi = image
        db.session.commit()
        return jsonify(success=True, package=service.serialize_package(package)), 201
    data = []
    for package in GoiDichVu.query.order_by(GoiDichVu.magoi).all():
        row = service.serialize_package(package)
        row['sold_count'] = GoiDichVuPurchase.query.filter_by(magoi=package.magoi, status='paid').count()
        row['active_treatments'] = TheLieuTrinh.query.filter(TheLieuTrinh.magoi == package.magoi,
            TheLieuTrinh.status == 'active', or_(TheLieuTrinh.expires_at.is_(None), TheLieuTrinh.expires_at >= service.local_now())).count()
        data.append(row)
    return jsonify(success=True, packages=data, package_revenue=str(service.paid_package_revenue()),
        services=[dict(madv=s.madv, tendv=s.tendv, gia=str(s.gia))
                  for s in DichVu.query.filter_by(active=True).all()])


@package_bp.route('/api/admin/packages/<int:package_id>', methods=['GET', 'PUT'])
@package_manager_required
def update_package(package_id):
    query = GoiDichVu.query.filter_by(magoi=package_id)
    package = query.first() if request.method == 'GET' else query.with_for_update().first()
    if not package:
        return jsonify(success=False, message='Không tìm thấy gói'), 404
    if request.method == 'GET':
        return jsonify(success=True, package=service.serialize_package(package))
    data, image = package_payload()
    updated = service.save_package(data, package)
    if image is not None:
        updated.anhgoi = image
    db.session.commit()
    return jsonify(success=True, package=service.serialize_package(updated))


@package_bp.route('/api/admin/packages/treatments')
@package_manager_required
def admin_treatments():
    query = TheLieuTrinh.query.join(KhachHang)
    term = request.args.get('search', '').strip()
    if term:
        condition = KhachHang.hoten.ilike(f'%{term}%') | KhachHang.sdt.ilike(f'%{term}%')
        if term.isdigit():
            condition = condition | (TheLieuTrinh.mathe == int(term))
        query = query.filter(condition)
    requested_status = request.args.get('status', '').strip()
    if requested_status in ('active', 'used_up', 'expired', 'cancelled'):
        today = service.local_now().date()
        if requested_status == 'expired':
            query = query.filter(or_(
                TheLieuTrinh.status == 'expired',
                (TheLieuTrinh.status == 'active') & (func.date(TheLieuTrinh.expires_at) < today)
            ))
        elif requested_status == 'active':
            query = query.filter(
                TheLieuTrinh.status == 'active',
                or_(TheLieuTrinh.expires_at.is_(None), func.date(TheLieuTrinh.expires_at) >= today)
            )
        else:
            query = query.filter(TheLieuTrinh.status == requested_status)
    return jsonify(success=True, treatments=[dict(service.serialize_treatment(t, True),
        customer_name=t.customer.hoten, phone=t.customer.sdt) for t in query.order_by(TheLieuTrinh.mathe.desc()).limit(200).all()])


@package_bp.route('/api/admin/packages/treatments/<int:record_id>')
@package_manager_required
def admin_treatment_detail(record_id):
    record = db.session.get(TheLieuTrinh, record_id)
    if not record:
        return jsonify(success=False, message='Không tìm thấy liệu trình'), 404
    return jsonify(success=True, treatment=dict(
        service.serialize_treatment(record, True),
        customer_name=record.customer.hoten,
        phone=record.customer.sdt
    ))


@package_bp.route('/api/admin/packages/purchases')
@package_manager_required
def admin_purchases():
    return jsonify(success=True, purchases=[dict(serialize_purchase(p), customer_name=p.customer.hoten)
        for p in GoiDichVuPurchase.query.order_by(GoiDichVuPurchase.id.desc()).limit(200).all()])


@package_bp.route('/api/admin/packages/purchases/<int:purchase_id>/confirm-payment', methods=['POST'])
@package_sales_required
def confirm_cash(purchase_id):
    data = request.get_json(silent=True) or {}
    current = db.session.get(GoiDichVuPurchase, purchase_id)
    if not current or current.payment_method != 'cash':
        raise AppointmentValidationError('Chỉ xác nhận tiền mặt cho giao dịch tiền mặt')
    purchase, record, _ = service.confirm_purchase(purchase_id,
        current.amount if 'cash_received' in data else data.get('amount'), method='cash',
        staff_id=g.current_user.manv, cash_received=data.get('cash_received', data.get('amount')))
    db.session.commit()
    return jsonify(success=True, mathe=record.mathe, purchase=serialize_purchase(purchase))


@package_bp.route('/api/admin/package-sales/customers')
@package_sales_required
def sale_customers():
    term = request.args.get('search', '').strip()
    query = KhachHang.query.filter_by(trangthai='active')
    if term:
        query = query.filter(or_(KhachHang.hoten.ilike(f'%{term}%'), KhachHang.sdt.ilike(f'%{term}%')))
    return jsonify(success=True, customers=[dict(makh=c.makh, hoten=c.hoten, sdt=c.sdt)
        for c in query.order_by(KhachHang.hoten).limit(30).all()])


@package_bp.route('/api/admin/package-sales', methods=['GET', 'POST'])
@package_sales_required
def counter_sales():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if data.get('payment_method') == 'vietqr' and not vietqr_available():
            return jsonify(success=False, message='VietQR tạm thời chưa khả dụng'), 503
        customer = db.session.get(KhachHang, data.get('makh'))
        if not customer or customer.trangthai != 'active':
            raise AppointmentValidationError('Khách hàng không tồn tại hoặc đã ngừng hoạt động')
        purchase = service.create_purchase(data.get('magoi'), customer.makh, data.get('payment_method'))
        purchase.created_by_staff = g.current_user.manv
        try:
            result = serialize_purchase(purchase)
        except RuntimeError:
            db.session.rollback()
            return jsonify(success=False, message='VietQR tạm thời chưa khả dụng'), 503
        db.session.commit()
        return jsonify(success=True, purchase=result), 201
    query = GoiDichVuPurchase.query.join(KhachHang)
    term = request.args.get('search', '').strip()
    if term:
        condition = or_(KhachHang.hoten.ilike(f'%{term}%'), KhachHang.sdt.ilike(f'%{term}%'))
        code = term.upper().removeprefix('PG').removeprefix('PKG')
        if code.isdigit():
            condition = or_(condition, GoiDichVuPurchase.id == int(code))
        query = query.filter(condition)
    status = request.args.get('status')
    if status in ('pending', 'paid', 'failed', 'cancelled'):
        query = query.filter(GoiDichVuPurchase.status == status)
    return jsonify(success=True, purchases=[serialize_purchase(p) for p in query.order_by(GoiDichVuPurchase.id.desc()).limit(200)])


@package_bp.route('/api/admin/package-sales/<int:purchase_id>')
@package_bp.route('/api/admin/package-sales/<int:purchase_id>/status')
@package_sales_required
def counter_sale_detail(purchase_id):
    purchase = db.session.get(GoiDichVuPurchase, purchase_id)
    if not purchase:
        return jsonify(success=False, message='Không tìm thấy phiếu'), 404
    return jsonify(success=True, purchase=serialize_purchase(purchase))


@package_bp.route('/api/admin/packages/services/<int:service_id>/post-care', methods=['PUT'])
@package_manager_required
def edit_post_care(service_id):
    """
    DEPRECATED: Quan ly DichVu.post_care_instructions nen thuc hien tai /admin/services.
    Giu lai de khong break bat ky integration nao dang dung endpoint nay.
    Se xoa o phien ban tiep theo khi chac chan khong con duoc goi.
    """
    import warnings
    current_app.logger.warning(
        f"DEPRECATED: PUT /api/admin/packages/services/{service_id}/post-care duoc goi. "
        "Hay chuyen sang su dung PUT /api/admin/services/<madv> voi field post_care_instructions."
    )
    item = db.session.get(DichVu, service_id)
    if not item:
        return jsonify(success=False, message='Khong tim thay dich vu'), 404
    text = (request.get_json(silent=True) or {}).get('instructions', '')
    if not isinstance(text, str) or len(text) > 10000:
        raise AppointmentValidationError('Noi dung dan do khong hop le')
    item.post_care_instructions = text
    db.session.commit()
    return jsonify(success=True, deprecated=True,
        message='Ghi thanh cong. Luu y: endpoint nay da deprecated, hay dung /api/admin/services/<madv> thay the.')

