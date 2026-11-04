"""Customer skin analyses (acne): AI result per photo, stored only with the customer's explicit consent."""
from datetime import datetime
from .extensions import db


class SkinServiceMap(db.Model):
    __tablename__ = 'skin_service_map'
    __table_args__ = (
        db.CheckConstraint("type_code IN ('closed_comedo','open_comedo','papule','pustule','nodule')",
                           name='ck_skin_service_map_type'),
        db.UniqueConstraint('type_code', 'madv', name='uq_skin_service_map_type_service'),
    )
    id = db.Column(db.Integer, primary_key=True)
    type_code = db.Column(db.String(30), nullable=False)
    madv = db.Column(db.Integer, db.ForeignKey('dichvu.madv', ondelete='CASCADE'), nullable=False, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('nhanvien.manv', ondelete='SET NULL'))
    approved_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approver = db.relationship('NhanVien')


class SkinAnalysis(db.Model):
    __tablename__ = 'skin_analysis'
    id = db.Column(db.Integer, primary_key=True)
    makh = db.Column(db.Integer, db.ForeignKey('khachhang.makh'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)  # ok | location_only | demo (retake_photo is never stored)
    lesion_count = db.Column(db.Integer, nullable=False, default=0)
    confident_count = db.Column(db.Integer, nullable=False, default=0)
    type_counts = db.Column(db.JSON, nullable=False)  # lesions per shown type (every lesion in demo)
    result = db.Column(db.JSON, nullable=False)  # AI response (boxes, types, checks)
    image_file = db.Column(db.String(80))  # uploads/skin/<makh>/<file>; private, served only to the owner
    image_width = db.Column(db.Integer)
    image_height = db.Column(db.Integer)
    consent_version = db.Column(db.String(20), nullable=False)
    consent_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
