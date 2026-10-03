"""Helper script to write notification_service.py content."""
import pathlib, textwrap

target = pathlib.Path(__file__).parent.parent / "app" / "services" / "notification_service.py"

content = textwrap.dedent("""\
\"\"\"Persisted care outbox. UTC scheduling; appointment times are Asia/Saigon.\"\"\"
import time as _time
import signal
import click
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
    \"\"\"
    Tra ve dict chua noi dung dan do sau dich vu:
      {
        'service_sections': [{'tendv': str, 'instructions': str}],
        'package_sections': [{'tengoi': str, 'instructions': str}],
        'has_content': bool,
        'fallback_used': bool,
      }
    Nguon dan do package: noi dung HIEN TAI tu GoiDichVu (khong dung snapshot cu),
    vi huong dan cham soc co the duoc cap nhat de tot/an toan hon.
    \"\"\"
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
    usages = LieuTrinhUsage.query.filter_by(malh=appointment.malh).all()
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
    \"\"\"Build HTML body cho email post-care tu appointment.\"\"\"
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
        instr = escape(sec['instructions']).replace('\\n', '<br>')
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
        instr = escape(sec['instructions']).replace('\\n', '<br>')
        package_care_html += (
            '<div style="background:#f0f7ff;border-left:3px solid #4a90d9;'
            'padding:12px 16px;margin:12px 0;border-radius:0 6px 6px 0;">'
            f'<h4 style="margin:0 0 8px;color:#2c5f8a;font-size:14px;">'
            f'&#128203; Luu y danh cho lieu trinh: {escape(sec["tengoi"])}</h4>'
            f'<p style="margin:0;color:#555;font-size:14px;line-height:1.6;">{instr}</p>'
            '</div>'
        )

    fallback_html = ''
    if content['fallback_used']:
        fallback_html = (
            '<p style="color:#666;font-size:14px;">'
            'Vui long lam theo huong dan cua ky thuat vien va lien he Bin Spa neu can ho tro.'
            '</p>'
        )

    svc_heading = ''
    if service_care_html:
        svc_heading = (
            '<h3 style="color:#8B7355;margin:20px 0 8px;font-size:16px;'
            'border-bottom:2px solid #C9A961;padding-bottom:6px;">'
            '&#127800; Dan do sau dich vu</h3>'
        )
    pkg_heading = ''
    if package_care_html:
        pkg_heading = (
            '<h3 style="color:#2c5f8a;margin:20px 0 8px;font-size:16px;'
            'border-bottom:2px solid #4a90d9;padding-bottom:6px;">'
            '&#128204; Luu y trong lieu trinh</h3>'
        )

    body = (
        f'<p>Xin chao <strong>{name}</strong>,</p>'
        '<p>Cam on ban da tin tuong va trai nghiem dich vu tai <strong>Bin Spa</strong>. '
        'Chung toi hy vong ban da co nhung phut giay thu gian tuyet voi!</p>'
        '<div style="background:#f9f5ef;padding:15px;border-radius:8px;margin:16px 0;">'
        f'<p style="margin:4px 0;"><strong>&#128278; Ma lich hen:</strong> #{appointment.malh}</p>'
        f'<p style="margin:4px 0;"><strong>&#128197; Ngay su dung:</strong> {ngaygio_str}</p>'
        f'<p style="margin:4px 0;"><strong>&#128105;&#8205;&#9877;&#65039; Ky thuat vien:</strong> {nv_name}</p>'
        '<p style="margin:4px 0;"><strong>&#128134; Dich vu da su dung:</strong></p>'
        f'<ul style="margin:4px 0 0 16px;padding:0;color:#555;font-size:14px;">{service_list_html}</ul>'
        '</div>'
        + svc_heading + service_care_html
        + pkg_heading + package_care_html
        + fallback_html
        + '<p style="margin-top:20px;padding-top:16px;border-top:1px solid #eee;color:#666;font-size:13px;">'
          'Neu can ho tro, vui long lien he Bin Spa.<br>'
          'Tran trong,<br><strong>Doi ngu Bin Spa</strong></p>'
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
            existing.payload_json = dict(to=appointment.khachhang.email, subject=subject, body=body)
        return existing
    job = NotificationJob(type=kind, makh=appointment.makh, malh=appointment.malh,
        scheduled_at=scheduled_at, status='pending', unique_key=key,
        payload_json=dict(to=appointment.khachhang.email, subject=subject, body=body))
    db.session.add(job)
    return job


def sync_appointment_jobs(appointment, now=None):
    \"\"\"
    Goi sau moi lan thay doi trang thai lich hen.
    - CONFIRMED  : tao reminder 24h va 2h.
    - COMPLETED  : tao post_care (ngay) + review_request (2h sau).
    - Trang thai khac: cancel reminder pending.
    Idempotent  : unique_key dam bao khong tao trung.
    Khong fail neu khach khong co email (chi log).
    \"\"\"
    now = now or datetime.utcnow()
    if appointment.trangthai != AppointmentStatus.CONFIRMED:
        NotificationJob.query.filter(
            NotificationJob.malh == appointment.malh,
            NotificationJob.type.in_(['appointment_reminder_24h', 'appointment_reminder_2h']),
            NotificationJob.status.in_(['pending', 'processing'])
        ).update({'status': 'cancelled'}, synchronize_session='fetch')

    if not appointment.khachhang or not appointment.khachhang.email:
        current_app.logger.info(
            f'Appointment #{appointment.malh} khong tao post-care vi khach khong co email'
        )
        return

    name = escape(appointment.khachhang.hoten or 'Quy khach')

    if appointment.trangthai == AppointmentStatus.CONFIRMED:
        start_utc = appointment.ngaygio - timedelta(hours=7)
        for hours, suffix in [(24, 'reminder24'), (2, 'reminder2')]:
            at = start_utc - timedelta(hours=hours)
            if at > now:
                enqueue(appointment, f'appointment_reminder_{hours}h', at,
                    f'Bin Spa - Nhac lich hen #{appointment.malh}',
                    f'<p>Xin chao {name}, lich hen #{appointment.malh} cua ban vao '
                    f'{appointment.ngaygio:%H:%M %d/%m/%Y}. Vui long den truoc 10 phut.</p>',
                    suffix)
            else:
                NotificationJob.query.filter_by(
                    unique_key=f'appointment:{appointment.malh}:{suffix}',
                    status='pending'
                ).update({'status': 'cancelled'}, synchronize_session='fetch')

    elif appointment.trangthai == AppointmentStatus.COMPLETED:
        body = build_post_care_html(appointment)
        subject = f'Bin Spa - Dan do sau buoi cham soc (Lich hen #{appointment.malh})'
        enqueue(appointment, 'post_care', now, subject, body, 'postcare')

        base = current_app.config.get('PUBLIC_SITE_URL', 'https://binspa.id.vn').rstrip('/')
        enqueue(appointment, 'review_request', now + timedelta(hours=2),
            'Bin Spa - Chia se trai nghiem cua ban',
            f'<p>Xin chao {name}, hay danh gia lich hen #{appointment.malh}.</p>'
            f'<a href="{escape(base)}/profile?review={appointment.malh}#appointments">'
            'Danh gia dich vu</a>',
            'review')


# ---------------------------------------------------------------------------
# Job processor
# ---------------------------------------------------------------------------

def process_jobs(batch_size=50, now=None):
    \"\"\"
    Xu ly cac NotificationJob den han.
    Idempotent: atomic claim bang UPDATE truoc khi gui.
    Retry toi da max_attempts lan; backoff 5*attempts phut.
    \"\"\"
    now = now or datetime.utcnow()
    stale = now - timedelta(minutes=10)
    eligible = or_(
        and_(NotificationJob.status == 'pending', NotificationJob.scheduled_at <= now),
        and_(NotificationJob.status == 'processing', NotificationJob.processing_at <= stale)
    )
    ids = [row[0] for row in db.session.query(NotificationJob.id).filter(eligible).order_by(
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
        valid = apt and (
            apt.trangthai == AppointmentStatus.CONFIRMED
            if job.type.startswith('appointment_reminder')
            else apt.trangthai == AppointmentStatus.COMPLETED
        )
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
        try:
            payload = job.payload_json
            success = email_service.send_email(
                payload['to'], payload['subject'], payload['body'],
                idempotency_key=job.unique_key
            )
            if not success:
                raise RuntimeError('Email provider did not confirm success')
            job.status, job.sent_at, job.last_error = 'sent', now, None
            result['sent'] += 1
        except Exception as error:
            db.session.refresh(job)
            if job.status != 'cancelled':
                job.status = 'failed' if job.attempts >= job.max_attempts else 'pending'
                job.scheduled_at = now + timedelta(minutes=5 * job.attempts)
                job.last_error = str(error)[:2000]
            result['failed'] += 1
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

    @app.cli.command('notification-worker')
    @click.option('--interval', default=30, type=click.IntRange(5, 300),
                  help='So giay giua moi lan xu ly jobs (mac dinh: 30)')
    @click.option('--batch-size', default=50, type=click.IntRange(1, 500),
                  help='So jobs toi da moi lan xu ly')
    def notification_worker(interval, batch_size):
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
        click.echo(f'[notification-worker] Bat dau. interval={interval}s batch_size={batch_size}')
        click.echo('[notification-worker] Nhan Ctrl+C de dung.')

        running = True

        def handle_signal(signum, frame):
            nonlocal running
            running = False
            click.echo('\\n[notification-worker] Dang dung...')

        signal.signal(signal.SIGINT, handle_signal)
        try:
            signal.signal(signal.SIGTERM, handle_signal)
        except (OSError, AttributeError):
            pass  # Windows khong ho tro SIGTERM day du

        while running:
            try:
                result = process_jobs(batch_size=batch_size)
                if result['sent'] or result['failed'] or result['cancelled']:
                    click.echo(
                        '[notification-worker] sent={sent} failed={failed} cancelled={cancelled}'.format(**result)
                    )
            except Exception as exc:
                current_app.logger.error(f'[notification-worker] Loi xu ly jobs: {exc}', exc_info=True)
            for _ in range(interval):
                if not running:
                    break
                _time.sleep(1)

        click.echo('[notification-worker] Da dung.')
""")

target.write_text(content, encoding='utf-8')
print(f"Written {len(content)} bytes to {target}")
