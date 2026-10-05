"""Persisted care outbox. UTC scheduling; appointment times are Asia/Saigon."""
import time as _time
import signal
import click
import logging
from datetime import datetime, timedelta
from html import escape

from flask import current_app
from sqlalchemy import or_, and_

from ..extensions import db
from ..models import NotificationJob, LichHen, AppointmentStatus, LieuTrinhUsage, TheLieuTrinh, GoiDichVu
from . import email_service


# ---------------------------------------------------------------------------
# Helper: xay dung noi dung dan do (dung chung cho email va profile)
# ---------------------------------------------------------------------------

def build_post_care_content(appointment):
    """
    Tra ve dict chua noi dung dan do sau dich vu:
      {
        'service_sections': [{'tendv': str, 'instructions': str}],
        'package_sections': [{'tengoi': str, 'instructions': str}],
        'has_content': bool,
        'fallback_used': bool,
      }
    Nguon dan do package: noi dung HIEN TAI tu GoiDichVu (khong dung snapshot cu),
    vi huong dan cham soc co the duoc cap nhat de tot/an toan hon.
    """
    service_sections = []
    for detail in appointment.chitiet:
        svc = detail.dichvu
        if svc and svc.post_care_instructions and svc.post_care_instructions.strip():
            service_sections.append({
                'tendv': svc.tendv,
                'instructions': svc.post_care_instructions.strip(),
            })

    # Lay cac package UNIQUE tu LieuTrinhUsage (ca reserved va consumed)
    package_sections = []
    usages = LieuTrinhUsage.query.filter(
        LieuTrinhUsage.malh == appointment.malh,
        LieuTrinhUsage.state.in_(['reserved', 'consumed']),
    ).all()
    seen_magoi = set()
    for usage in usages:
        record = db.session.get(TheLieuTrinh, usage.mathe)
        if not record:
            continue
        magoi = record.magoi
        if magoi in seen_magoi:
            continue
        seen_magoi.add(magoi)
        package = db.session.get(GoiDichVu, magoi)
        if package and package.post_care_instructions and package.post_care_instructions.strip():
            package_sections.append({
                'tengoi': package.tengoi,
                'instructions': package.post_care_instructions.strip(),
            })

    has_content = bool(service_sections or package_sections)
    return {
        'service_sections': service_sections,
        'package_sections': package_sections,
        'has_content': has_content,
        'fallback_used': not has_content,
    }


def build_post_care_html(appointment):
    """Build HTML body cho email post-care tu appointment."""
    content = build_post_care_content(appointment)
    kh = appointment.khachhang
    nv = appointment.nhanvien
    name = escape(kh.hoten if kh else 'Quy khach')
    ngaygio_str = appointment.ngaygio.strftime('%H:%M %d/%m/%Y') if appointment.ngaygio else 'N/A'
    nv_name = escape(nv.hoten) if nv else 'Ky thuat vien Bin Spa'

    all_services = []
    for detail in appointment.chitiet:
        if detail.dichvu:
            all_services.append(escape(detail.dichvu.tendv))
    service_list_html = ''.join(f'<li>{s}</li>' for s in all_services)

    service_care_html = ''
    for sec in content['service_sections']:
        instr = escape(sec['instructions']).replace('\n', '<br>')
        service_care_html += (
            '<div style="background:#faf8f5;border-left:3px solid #C9A961;'
            'padding:12px 16px;margin:12px 0;border-radius:0 6px 6px 0;">'
            f'<h4 style="margin:0 0 8px;color:#8B7355;font-size:14px;">'
            f'&#127807; {escape(sec["tendv"])}</h4>'
            f'<p style="margin:0;color:#555;font-size:14px;line-height:1.6;">{instr}</p>'
            '</div>'
        )

    package_care_html = ''
    for sec in content['package_sections']:
        instr = escape(sec['instructions']).replace('\n', '<br>')
        package_care_html += (
            '<div style="background:#f0f7ff;border-left:3px solid #4a90d9;'
            'padding:12px 16px;margin:12px 0;border-radius:0 6px 6px 0;">'
            f'<h4 style="margin:0 0 8px;color:#2c5f8a;font-size:14px;">'
            f'&#128203; {escape(sec["tengoi"])}</h4>'
            f'<p style="margin:0;color:#555;font-size:14px;line-height:1.6;">{instr}</p>'
            '</div>'
        )

    fallback_html = ''
    if content['fallback_used']:
        fallback_html = (
            '<p style="color:#666;font-size:14px;">'
            'Cảm ơn bạn đã sử dụng dịch vụ tại Bin Spa. '
            'Vui lòng nghỉ ngơi, làm theo hướng dẫn của kỹ thuật viên '
            'và liên hệ Bin Spa nếu cần hỗ trợ.'
            '</p>'
        )

    svc_heading = ''
    if service_care_html:
        svc_heading = (
            '<h3 style="color:#8B7355;margin:20px 0 8px;font-size:16px;'
            'border-bottom:2px solid #C9A961;padding-bottom:6px;">'
            '&#127800; DẶN DÒ SAU DỊCH VỤ</h3>'
        )
    pkg_heading = ''
    if package_care_html:
        pkg_heading = (
            '<h3 style="color:#2c5f8a;margin:20px 0 8px;font-size:16px;'
            'border-bottom:2px solid #4a90d9;padding-bottom:6px;">'
            '&#128204; LƯU Ý DÀNH CHO LIỆU TRÌNH</h3>'
        )

    body = (
        f'<p>Xin chào <strong>{name}</strong>,</p>'
        '<p>Cảm ơn bạn đã sử dụng dịch vụ tại <strong>Bin Spa</strong>.</p>'
        '<div style="background:#f9f5ef;padding:15px;border-radius:8px;margin:16px 0;">'
        f'<p style="margin:4px 0;"><strong>&#128278; Mã lịch hẹn:</strong> #{appointment.malh}</p>'
        f'<p style="margin:4px 0;"><strong>&#128197; Thời gian:</strong> {ngaygio_str}</p>'
        f'<p style="margin:4px 0;"><strong>&#128105;&#8205;&#9877;&#65039; Kỹ thuật viên:</strong> {nv_name}</p>'
        '<p style="margin:4px 0;"><strong>&#128134; Dịch vụ:</strong></p>'
        f'<ul style="margin:4px 0 0 16px;padding:0;color:#555;font-size:14px;">{service_list_html}</ul>'
        '</div>'
        + svc_heading + service_care_html
        + pkg_heading + package_care_html
        + fallback_html
        + '<p style="margin-top:20px;padding-top:16px;border-top:1px solid #eee;color:#666;font-size:13px;">'
          'Nếu cần hỗ trợ, vui lòng liên hệ Bin Spa.<br>'
          'Trân trọng,<br><strong>Đội ngũ Bin Spa</strong></p>'
    )
    return body


# ---------------------------------------------------------------------------
# Core enqueue / sync
# ---------------------------------------------------------------------------

def enqueue(appointment, kind, scheduled_at, subject, body, suffix):
    key = f'appointment:{appointment.malh}:{suffix}'
    existing = NotificationJob.query.filter_by(unique_key=key).first()
    if existing:
        if existing.first_attempt_at:
            if kind.startswith('appointment_reminder') and existing.scheduled_at != scheduled_at:
                if existing.status in ('pending', 'processing'):
                    existing.status = 'cancelled'
            return existing
        if kind.startswith('appointment_reminder') and existing.status in ('pending', 'cancelled'):
            existing.scheduled_at = scheduled_at
            existing.status = 'pending'
            existing.payload_json = dict(to=appointment.khachhang.email.strip(), subject=subject, body=body)
        return existing
    job = NotificationJob(type=kind, makh=appointment.makh, malh=appointment.malh,
        scheduled_at=scheduled_at, status='pending', unique_key=key,
        payload_json=dict(to=appointment.khachhang.email.strip(), subject=subject, body=body))
    db.session.add(job)
    return job


def sync_appointment_jobs(appointment, now=None):
    """
    Goi sau moi lan thay doi trang thai lich hen.
    - CONFIRMED  : tao reminder 24h va 2h.
    - COMPLETED  : tao post_care (ngay) + review_request (2h sau).
    - Trang thai khac: cancel reminder pending.
    Idempotent  : unique_key dam bao khong tao trung.
    Khong fail neu khach khong co email (chi log).
    """
    now = now or datetime.utcnow()
    if appointment.trangthai != AppointmentStatus.CONFIRMED:
        NotificationJob.query.filter(
            NotificationJob.malh == appointment.malh,
            NotificationJob.type.in_(['appointment_reminder_24h', 'appointment_reminder_2h']),
            NotificationJob.status.in_(['pending', 'processing'])
        ).update({'status': 'cancelled'}, synchronize_session='fetch')

    if not appointment.khachhang or not (appointment.khachhang.email or '').strip():
        current_app.logger.info(
            f'Appointment #{appointment.malh} không tạo post-care vì khách không có email.'
        )
        return

    name = escape(appointment.khachhang.hoten or 'Quy khach')

    if appointment.trangthai == AppointmentStatus.CONFIRMED:
        start_utc = appointment.ngaygio - timedelta(hours=7)
        for hours, suffix in [(24, 'reminder24'), (2, 'reminder2')]:
            at = start_utc - timedelta(hours=hours)
            if at > now:
                enqueue(appointment, f'appointment_reminder_{hours}h', at,
                    f'Bin Spa - Nhắc lịch hẹn #{appointment.malh}',
                    f'<p>Xin chào {name}, lịch hẹn #{appointment.malh} của bạn vào '
                    f'{appointment.ngaygio:%H:%M %d/%m/%Y}. Vui lòng đến trước 10 phút.</p>',
                    suffix)
            else:
                NotificationJob.query.filter_by(
                    unique_key=f'appointment:{appointment.malh}:{suffix}',
                    status='pending'
                ).update({'status': 'cancelled'}, synchronize_session='fetch')

    elif appointment.trangthai == AppointmentStatus.COMPLETED:
        body = build_post_care_html(appointment)
        subject = 'Bin Spa - Dặn dò sau buổi chăm sóc'
        enqueue(appointment, 'post_care', now, subject, body, 'postcare')

        base = current_app.config.get('PUBLIC_SITE_URL', 'https://binspa.id.vn').rstrip('/')
        enqueue(appointment, 'review_request', now + timedelta(hours=2),
            'Bin Spa - Chia sẽ trải nghiệm của bạn',
            f'<p>Xin chào {name}, Hãy đánh giá lịch hẹn #{appointment.malh}.</p>'
            f'<a href="{escape(base)}/profile?review={appointment.malh}#appointments">'
            'Đánh giá dịch vụ</a>',
            'review')


NO_SHOW_JOB = 'appointment_no_show'


def enqueue_no_show_cancelled(appointment, released_sessions=0, grace_minutes=30, now=None):
    """Email báo lịch bị tự hủy vì khách không đến. Cùng transaction với việc hủy; worker gửi và retry."""
    customer = appointment.khachhang
    if not customer or not (customer.email or '').strip():
        current_app.logger.info(f'Appointment #{appointment.malh} tự hủy nhưng khách không có email.')
        return None
    name = escape(customer.hoten or 'Quý khách')
    services = ''.join(f'<li>{escape(d.dichvu.tendv)}</li>' for d in appointment.chitiet if d.dichvu)
    base = current_app.config.get('PUBLIC_SITE_URL', 'https://binspa.id.vn').rstrip('/')
    sessions_html = (f'<p>{released_sessions} buổi liệu trình đã giữ cho lịch này đã được <strong>hoàn trả</strong> '
                     'vào gói của bạn.</p>') if released_sessions else ''
    body = (
        f'<p>Xin chào <strong>{name}</strong>,</p>'
        f'<p>Lịch hẹn <strong>#{appointment.malh}</strong> lúc '
        f'<strong>{appointment.ngaygio:%H:%M %d/%m/%Y}</strong> đã được hệ thống <strong>tự động hủy</strong> '
        f'vì Bin Spa chưa ghi nhận bạn đến sau {grace_minutes} phút kể từ giờ hẹn.</p>'
        f'<ul style="color:#555;">{services}</ul>'
        + sessions_html +
        '<p>Vui lòng đặt lịch mới khi bạn thuận tiện:</p>'
        f'<p><a href="{escape(base)}/appointments/create" style="background:#C9A961;color:#fff;padding:10px 18px;'
        'border-radius:6px;text-decoration:none;display:inline-block;">Đặt lịch mới</a></p>'
        '<p style="color:#666;font-size:13px;">Nếu bạn đã đến spa nhưng vẫn nhận email này, vui lòng liên hệ '
        'Bin Spa để được hỗ trợ.<br>Trân trọng,<br><strong>Đội ngũ Bin Spa</strong></p>'
    )
    return enqueue(appointment, NO_SHOW_JOB, now or datetime.utcnow(),
                   f'Bin Spa - Lịch hẹn #{appointment.malh} đã bị hủy', body, 'noshow')


# ---------------------------------------------------------------------------
# Job processor
# ---------------------------------------------------------------------------

def process_jobs(batch_size=50, now=None, appointment_id=None):
    """
    Xu ly cac NotificationJob den han.
    Idempotent: atomic claim bang UPDATE truoc khi gui.
    Retry toi da max_attempts lan; backoff 5*attempts phut.
    """
    now = now or datetime.utcnow()
    stale = now - timedelta(minutes=10)
    eligible = or_(
        and_(NotificationJob.status == 'pending', NotificationJob.scheduled_at <= now),
        and_(NotificationJob.status == 'processing', NotificationJob.processing_at <= stale)
    )
    query = db.session.query(NotificationJob.id).filter(eligible)
    if appointment_id is not None:
        query = query.filter(NotificationJob.malh == appointment_id)
    ids = [row[0] for row in query.order_by(
        NotificationJob.scheduled_at, NotificationJob.id).limit(batch_size).all()]
    db.session.commit()
    result = dict(sent=0, failed=0, cancelled=0)
    for job_id in ids:
        claimed = NotificationJob.query.filter(NotificationJob.id == job_id, eligible).update(
            {'status': 'processing', 'processing_at': now}, synchronize_session=False)
        db.session.commit()
        if not claimed:
            continue
        job = db.session.get(NotificationJob, job_id)
        if job.first_attempt_at and now - job.first_attempt_at >= timedelta(hours=23):
            job.status = 'failed'
            job.last_error = 'Retry window exceeded; reconcile with email provider before retrying'
            result['failed'] += 1
            db.session.commit()
            continue
        apt = db.session.get(LichHen, job.malh) if job.malh else None
        if not apt:
            valid = False
        elif job.type.startswith('appointment_reminder'):
            valid = apt.trangthai == AppointmentStatus.CONFIRMED
        elif job.type == NO_SHOW_JOB:
            valid = apt.trangthai == AppointmentStatus.CANCELLED
        else:
            valid = apt.trangthai == AppointmentStatus.COMPLETED
        if not valid or (job.type.startswith('appointment_reminder') and apt.ngaygio - timedelta(hours=7) <= now):
            job.status = 'cancelled'
            result['cancelled'] += 1
            db.session.commit()
            continue
        if job.attempts >= job.max_attempts:
            job.status = 'failed'
            db.session.commit()
            result['failed'] += 1
            continue
        job.attempts += 1
        job.first_attempt_at = job.first_attempt_at or now
        db.session.commit()
        current_app.logger.info(
            '[notification-worker] %s appointment=%s recipient=%s processing attempt=%s',
            job.type, job.malh, email_service.masked_recipient(job.payload_json.get('to')), job.attempts)
        try:
            payload = job.payload_json
            success = email_service.send_email(
                payload['to'], payload['subject'], payload['body'],
                idempotency_key=job.unique_key, return_provider_response=True
            )
            if not success:
                raise RuntimeError('Email provider did not confirm success')
            job.status, job.sent_at, job.last_error = 'sent', now, None
            result['sent'] += 1
            provider_id = success.get('id') if isinstance(success, dict) else 'N/A'
            current_app.logger.info(
                '[notification-worker] %s appointment=%s recipient=%s sent provider_id=%s',
                job.type, job.malh, email_service.masked_recipient(payload['to']), provider_id)
        except Exception as error:
            db.session.refresh(job)
            if job.status != 'cancelled':
                job.status = 'failed' if job.attempts >= job.max_attempts else 'pending'
                job.scheduled_at = now + timedelta(minutes=5 * job.attempts)
                job.last_error = email_service.safe_provider_error(error)
            result['failed'] += 1
            current_app.logger.warning(
                '[notification-worker] %s appointment=%s recipient=%s status=%s attempts=%s/%s retry_at=%s error=%s',
                job.type, job.malh, email_service.masked_recipient(job.payload_json.get('to')),
                job.status, job.attempts, job.max_attempts, job.scheduled_at, job.last_error)
        db.session.commit()
    return result


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def register_commands(app):
    @app.cli.command('process-notification-jobs')
    @click.option('--batch-size', default=50, type=click.IntRange(1, 500))
    def process_notification_jobs(batch_size):
        'Process due care jobs (one-shot). Use notification-worker for continuous processing.'
        click.echo(process_jobs(batch_size))

    @app.cli.command('auto-cancel-no-shows')
    @click.option('--grace-minutes', default=None, type=click.IntRange(1, 1440))
    def auto_cancel_no_shows_command(grace_minutes):
        'Tự hủy (one-shot) lịch khách không đến; notification-worker cũng chạy việc này mỗi chu kỳ.'
        from .appointment_service import auto_cancel_no_shows
        click.echo(f'auto-cancelled: {auto_cancel_no_shows(grace_minutes=grace_minutes)}')

    @app.cli.command('notification-worker')
    @click.option('--interval', default=30, type=click.IntRange(5, 300),
                  help='So giay giua moi lan xu ly jobs (mac dinh: 30)')
    @click.option('--batch-size', default=50, type=click.IntRange(1, 500),
                  help='So jobs toi da moi lan xu ly')
    @click.option('--appointment-id', type=click.IntRange(1), default=None,
                  help='Only process this appointment during a real-email integration check.')
    def notification_worker(interval, batch_size, appointment_id):
        '''
        Worker lien tuc xu ly NotificationJob. Chay nhu PROCESS RIENG biet.

        Windows (local dev):
          Terminal 1: python run.py
          Terminal 2: python -m flask --app wsgi:app notification-worker --interval 15

        Production (Gunicorn):
          Web:    gunicorn wsgi:app
          Worker: python -m flask --app wsgi:app notification-worker --interval 30

        KHONG chay worker ben trong moi Gunicorn worker (tranh duplicate processor).
        Graceful shutdown: Ctrl+C
        '''
        configured = bool(email_service.configured_api_key())
        click.echo(f'RESEND_API_KEY configured: {"yes" if configured else "no"}')
        if not configured:
            raise click.ClickException('RESEND_API_KEY is not configured for notification worker.')
        current_app.logger.setLevel(logging.INFO)
        click.echo(f'Notification worker started. interval={interval}s batch_size={batch_size} appointment={appointment_id or "all"}')
        click.echo('[notification-worker] Nhan Ctrl+C de dung.')

        running = True

        def handle_signal(signum, frame):
            nonlocal running
            running = False
            click.echo('\n[notification-worker] Dang dung...')

        signal.signal(signal.SIGINT, handle_signal)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, handle_signal)
        try:
            signal.signal(signal.SIGTERM, handle_signal)
        except (OSError, AttributeError):
            pass  # Windows khong ho tro SIGTERM day du

        while running:
            try:
                # Tự hủy lịch khách không đến (quá NO_SHOW_GRACE_MINUTES) trước khi gửi email trong outbox.
                from .appointment_service import auto_cancel_no_shows
                cancelled = auto_cancel_no_shows()
                if cancelled:
                    click.echo(f'[notification-worker] no-show auto-cancelled={len(cancelled)}')
            except Exception as exc:
                db.session.rollback()
                current_app.logger.error(f'[notification-worker] Loi tu huy lich: {exc}', exc_info=True)
            try:
                result = process_jobs(batch_size=batch_size) if appointment_id is None else process_jobs(
                    batch_size=batch_size, appointment_id=appointment_id)
                if result['sent'] or result['failed'] or result['cancelled']:
                    click.echo(
                        '[notification-worker] sent={sent} failed={failed} cancelled={cancelled}'.format(**result)
                    )
            except Exception as exc:
                db.session.rollback()
                current_app.logger.error(f'[notification-worker] Loi xu ly jobs: {exc}', exc_info=True)
            for _ in range(interval):
                if not running:
                    break
                _time.sleep(1)

        click.echo('[notification-worker] Da dung.')
