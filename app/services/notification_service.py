"""Persisted care outbox. UTC scheduling; appointment times are Asia/Saigon."""
from datetime import datetime, timedelta
from html import escape
import click
from flask import current_app
from sqlalchemy import or_, and_

from ..extensions import db
from ..models import NotificationJob, LichHen, AppointmentStatus
from . import email_service


def enqueue(appointment, kind, scheduled_at, subject, body, suffix):
    key = f'appointment:{appointment.malh}:{suffix}'
    existing = NotificationJob.query.filter_by(unique_key=key).first()
    if existing:
        if existing.first_attempt_at:
            # Provider retries require the exact same payload. A reminder whose
            # original send was attempted cannot safely be rewritten on reschedule.
            if kind.startswith('appointment_reminder') and existing.scheduled_at != scheduled_at:
                if existing.status in ('pending', 'processing'):
                    existing.status = 'cancelled'
            return existing
        # Do not resend sent messages. Reschedule only unsent reminder jobs.
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
    now = now or datetime.utcnow()
    if appointment.trangthai != AppointmentStatus.CONFIRMED:
        NotificationJob.query.filter(NotificationJob.malh == appointment.malh,
            NotificationJob.type.in_(['appointment_reminder_24h', 'appointment_reminder_2h']),
            NotificationJob.status.in_(['pending', 'processing'])).update(
                {'status':'cancelled'}, synchronize_session='fetch')
    if not appointment.khachhang or not appointment.khachhang.email:
        return
    name = escape(appointment.khachhang.hoten or 'Quý khách')
    if appointment.trangthai == AppointmentStatus.CONFIRMED:
        start_utc = appointment.ngaygio - timedelta(hours=7)
        for hours, suffix in [(24, 'reminder24'), (2, 'reminder2')]:
            at = start_utc - timedelta(hours=hours)
            if at > now:
                enqueue(appointment, f'appointment_reminder_{hours}h', at,
                    f'Bin Spa - Nhắc lịch hẹn #{appointment.malh}',
                    f'<p>Xin chào {name}, lịch hẹn #{appointment.malh} của bạn vào '
                    f'{appointment.ngaygio:%H:%M %d/%m/%Y}. Vui lòng đến trước 10 phút.</p>', suffix)
            else:
                NotificationJob.query.filter_by(unique_key=f'appointment:{appointment.malh}:{suffix}',
                    status='pending').update({'status':'cancelled'}, synchronize_session='fetch')
    elif appointment.trangthai == AppointmentStatus.COMPLETED:
        care = []
        for detail in appointment.chitiet:
            service = detail.dichvu
            if service and service.post_care_instructions:
                care.append(f'<h3>{escape(service.tendv)}</h3><p>' +
                    escape(service.post_care_instructions).replace('\n','<br>') + '</p>')
        body = f'<p>Xin chào {name}, cảm ơn bạn đã sử dụng dịch vụ tại Bin Spa.</p>'
        body += ''.join(care) or '<p>Vui lòng làm theo hướng dẫn của kỹ thuật viên và liên hệ spa nếu cần hỗ trợ.</p>'
        enqueue(appointment, 'post_care', now, 'Bin Spa - Dặn dò sau dịch vụ', body, 'postcare')
        base = current_app.config.get('PUBLIC_SITE_URL', 'https://binspa.id.vn').rstrip('/')
        enqueue(appointment, 'review_request', now + timedelta(hours=2),
            'Bin Spa - Chia sẻ trải nghiệm của bạn',
            f'<p>Xin chào {name}, hãy đánh giá lịch hẹn #{appointment.malh}.</p>'
            f'<a href="{escape(base)}/profile?review={appointment.malh}#appointments">Đánh giá dịch vụ</a>', 'review')


def process_jobs(batch_size=50, now=None):
    now = now or datetime.utcnow()
    stale = now - timedelta(minutes=10)
    eligible = or_(and_(NotificationJob.status == 'pending', NotificationJob.scheduled_at <= now),
                   and_(NotificationJob.status == 'processing', NotificationJob.processing_at <= stale))
    ids = [row[0] for row in db.session.query(NotificationJob.id).filter(eligible).order_by(
        NotificationJob.scheduled_at, NotificationJob.id).limit(batch_size).all()]
    db.session.commit()
    result = dict(sent=0, failed=0, cancelled=0)
    for job_id in ids:
        # Atomic claim: other workers cannot send the same job.
        claimed = NotificationJob.query.filter(NotificationJob.id == job_id, eligible).update(
            {'status':'processing', 'processing_at':now}, synchronize_session=False)
        db.session.commit()
        if not claimed:
            continue
        job = db.session.get(NotificationJob, job_id)
        if job.first_attempt_at and now - job.first_attempt_at >= timedelta(hours=23):
            job.status, job.last_error = 'failed', 'Retry window exceeded; reconcile with email provider before retrying'
            result['failed'] += 1
            db.session.commit()
            continue
        apt = db.session.get(LichHen, job.malh) if job.malh else None
        valid = apt and (apt.trangthai == AppointmentStatus.CONFIRMED if job.type.startswith('appointment_reminder')
                        else apt.trangthai == AppointmentStatus.COMPLETED)
        if not valid or (job.type.startswith('appointment_reminder') and apt.ngaygio-timedelta(hours=7) <= now):
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
            success = email_service.send_email(payload['to'], payload['subject'], payload['body'],
                idempotency_key=job.unique_key)
            if not success:
                raise RuntimeError('Email provider did not confirm success')
            # A cancellation during the HTTP request must not cause a later resend.
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


def register_commands(app):
    @app.cli.command('process-notification-jobs')
    @click.option('--batch-size', default=50, type=click.IntRange(1, 500))
    def process_notification_jobs(batch_size):
        """Process due care jobs. Schedule this bounded command with cron."""
        click.echo(process_jobs(batch_size))
