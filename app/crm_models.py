"""Additive CRM consent and recommendation measurements; no payment data is copied."""
from datetime import datetime
from .extensions import db


class CustomerPreference(db.Model):
    __tablename__ = 'customer_preference'
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), primary_key=True)
    reminders = db.Column(db.Boolean, nullable=False, default=False)
    post_care = db.Column(db.Boolean, nullable=False, default=False)
    review_requests = db.Column(db.Boolean, nullable=False, default=False)
    personalization = db.Column(db.Boolean, nullable=False, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CustomerPreferenceAudit(db.Model):
    __tablename__ = 'customer_preference_audit'
    id = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    settings = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('makh', 'version', name='uq_customer_preference_version'),)


class RecommendationImpression(db.Model):
    __tablename__ = 'recommendation_impression'
    id = db.Column(db.String(36), primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False)
    placement = db.Column(db.String(20), nullable=False)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv'))
    magoi = db.Column(db.Integer, db.ForeignKey('goidichvu.magoi'))
    position = db.Column(db.Integer, nullable=False)
    strategy = db.Column(db.String(20), nullable=False)
    dedupe_key = db.Column(db.String(150), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    clicked_at = db.Column(db.DateTime)
    __table_args__ = (
        db.CheckConstraint('(madv IS NOT NULL AND magoi IS NULL) OR (madv IS NULL AND magoi IS NOT NULL)', name='ck_impression_target'),
        db.CheckConstraint('position BETWEEN 1 AND 6', name='ck_impression_position'),
        db.Index('ix_impression_customer_time', 'makh', 'created_at'),
        db.Index('ix_impression_time', 'created_at'),
    )


class RecommendationTiming(db.Model):
    __tablename__ = 'recommendation_timing'
    id = db.Column(db.Integer, primary_key=True)
    placement = db.Column(db.String(20), nullable=False)
    duration_ms = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
