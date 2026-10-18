"""Short-lived, owner-scoped AI work that survives page navigation."""
from datetime import datetime
from .extensions import db


class AIChatJob(db.Model):
    __tablename__ = 'ai_chat_job'
    id = db.Column(db.String(36), primary_key=True)
    owner_key = db.Column(db.String(64), nullable=False)
    actor_kind = db.Column(db.String(12), nullable=False)
    actor_id = db.Column(db.Integer)
    payload_hash = db.Column(db.String(64), nullable=False)
    payload_json = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='PENDING')
    result_json = db.Column(db.JSON)
    error_message = db.Column(db.String(500))
    error_status = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=False)
    __table_args__ = (
        db.CheckConstraint("status IN ('PENDING','PROCESSING','SUCCEEDED','FAILED')", name='ck_ai_chat_job_status'),
        db.Index('ix_ai_chat_job_queue', 'status', 'created_at'),
        db.Index('ix_ai_chat_job_owner', 'owner_key', 'created_at'),
        db.Index('ix_ai_chat_job_expires_at', 'expires_at'),
    )
