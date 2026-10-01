import hashlib
import json
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import PaymentWebhookEvent


def payload_hash(payload):
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def begin_event(provider, external_transaction_id, payload):
    """Create an idempotency record, or return the existing record."""
    external_id = str(external_transaction_id or "").strip()
    if not external_id:
        raise ValueError("Webhook thiếu mã giao dịch bên ngoài")

    existing = PaymentWebhookEvent.query.filter_by(
        provider=provider,
        external_transaction_id=external_id,
    ).first()
    if existing:
        return existing, True

    event = PaymentWebhookEvent(
        provider=provider,
        external_transaction_id=external_id,
        payload_hash=payload_hash(payload),
        payload_json=payload,
        status="processing",
    )
    db.session.add(event)
    try:
        db.session.flush()
    except IntegrityError:
        # A concurrent callback inserted the same provider transaction first.
        db.session.rollback()
        existing = PaymentWebhookEvent.query.filter_by(
            provider=provider,
            external_transaction_id=external_id,
        ).first()
        if existing:
            return existing, True
        raise

    return event, False


def finish_event(event, status, invoice_id=None):
    event.status = status
    event.mahd = invoice_id
    event.processed_at = datetime.utcnow()


def duplicate_response(event):
    return {
        "status": "duplicate",
        "message": "Giao dịch đã được tiếp nhận trước đó",
        "event_status": event.status,
    }
