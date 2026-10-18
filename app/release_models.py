"""Small operational records; no customer payloads, credentials or GPS coordinates."""
from datetime import datetime
from .extensions import db


class AuthRateBucket(db.Model):
    __tablename__ = 'auth_rate_bucket'
    key = db.Column(db.String(64), primary_key=True)
    bucket = db.Column(db.BigInteger, primary_key=True)
    attempts = db.Column(db.Integer, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)


class ReportExportAudit(db.Model):
    __tablename__ = 'report_export_audit'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    branch_ids = db.Column(db.JSON, nullable=False)
    business_scope = db.Column(db.String(30), nullable=False)
    request_id = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class WorkerHeartbeat(db.Model):
    __tablename__ = 'worker_heartbeat'
    name = db.Column(db.String(40), primary_key=True)
    last_seen_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False)


class AppointmentOutcome(db.Model):
    __tablename__ = 'appointment_outcome'
    malh = db.Column(db.Integer, db.ForeignKey('lichhen.malh'), primary_key=True)
    outcome = db.Column(db.String(20), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
