"""Encrypted authenticators, short-lived elevation and minimal security audit."""
from datetime import datetime
from .extensions import db


class StaffMFA(db.Model):
    __tablename__ = 'staff_mfa'
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), primary_key=True)
    secret_ciphertext = db.Column(db.Text)
    pending_ciphertext = db.Column(db.Text)
    pending_expires_at = db.Column(db.DateTime)
    enabled_at = db.Column(db.DateTime)
    generation = db.Column(db.Integer, nullable=False, default=0)
    last_counter = db.Column(db.BigInteger, nullable=False, default=-1)


class StaffRecoveryCode(db.Model):
    __tablename__ = 'staff_recovery_code'
    code_hash = db.Column(db.String(64), primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False, index=True)
    generation = db.Column(db.Integer, nullable=False)
    used_at = db.Column(db.DateTime)


class StaffStepUp(db.Model):
    __tablename__ = 'staff_step_up'
    token_hash = db.Column(db.String(64), primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False, index=True)
    generation = db.Column(db.Integer, nullable=False)
    auth_digest = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)


class StaffSecurityAudit(db.Model):
    __tablename__ = 'staff_security_audit'
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('nhanvien.manv'), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    request_id = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
