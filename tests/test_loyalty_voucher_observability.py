import json
import logging
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import LoyaltyReward
from app.services import loyalty_service as loyalty, voucher_issuance_service as issuance
from test_loyalty_voucher_issuance import gift_template, gift, configure, new_pending


def events(caplog):
    return [json.loads(row.getMessage().split('voucher_event ', 1)[1])
            for row in caplog.records if row.getMessage().startswith('voucher_event ')]


def test_committed_issue_replay_rejection_and_cancellation_are_private(app, client, admin_auth_headers, gift_template, caplog):
    caplog.set_level(logging.INFO)
    app.logger.setLevel(logging.WARNING)  # Voucher events remain visible with default Flask logging.
    response = gift(client, app, admin_auth_headers, gift_template,
                    reason='PRIVATE_REASON_0901234567', customer_message='PRIVATE_MESSAGE')
    rid = response.json['redemption']['id']
    assert gift(client, app, admin_auth_headers, gift_template,
                reason='PRIVATE_REASON_0901234567', customer_message='PRIVATE_MESSAGE').status_code == 200
    assert gift(client, app, admin_auth_headers, gift_template, reason='Changed').status_code == 409
    assert client.post(f'/api/admin/loyalty/voucher-gifts/{rid}/cancel', headers=admin_auth_headers,
                       json={'reason': 'PRIVATE_CANCELLATION'}).status_code == 200
    rows = events(caplog)
    assert [row['event'] for row in rows] == ['issued', 'replayed', 'rejected', 'cancelled']
    assert rows[2]['reason'] == 'idempotency_conflict'
    text = json.dumps(rows)
    assert not any(secret in text for secret in ('PRIVATE_', '0901234567', 'Bearer', 'gift-1'))


def test_rollback_never_logs_an_issued_voucher(app, gift_template, caplog):
    caplog.set_level(logging.INFO)
    with app.app_context():
        issuance.manual_gift(app.config['TEST_CUSTOMER_ID'],
            {'reward_id': gift_template, 'reason': 'Rollback'}, app.config['TEST_ADMIN_ID'], 'rollback')
        db.session.rollback()
        db.session.commit()  # A later unrelated commit must not flush stale events.
    assert events(caplog) == []


def test_welcome_stock_skip_and_database_failure_have_distinct_events(app, client, gift_template, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    configure(app, gift_template)
    new_pending(app, name='stock-event')
    with app.app_context():
        db.session.get(LoyaltyReward, gift_template).stock = 0
        db.session.commit()
    assert client.post('/api/auth/verify-otp', json={'otp_code': '123456'}).status_code == 200
    assert events(caplog)[-1]['reason'] == 'out_of_stock'
    with app.app_context():
        db.session.get(LoyaltyReward, gift_template).stock = 1
        db.session.commit()
    new_pending(app, name='failure-event')
    original = loyalty.issue_reward
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise IntegrityError('PRIVATE_SQL', {}, Exception('PRIVATE_DATABASE_ERROR'))
    monkeypatch.setattr(loyalty, 'issue_reward', fail)
    assert client.post('/api/auth/verify-otp', json={'otp_code': '123456'}).status_code == 500
    rows = events(caplog)
    assert [row['event'] for row in rows] == ['skipped', 'failed']
    assert rows[-1]['error_type'] == 'IntegrityError'
    assert 'PRIVATE_' not in json.dumps(rows)


def test_payment_event_is_logged_once_after_commit(app, client, admin_auth_headers, gift_template, create_invoice, caplog):
    caplog.set_level(logging.INFO)
    rid = gift(client, app, admin_auth_headers, gift_template).json['redemption']['id']
    invoice = create_invoice(amount=500000)
    assert client.post(f'/api/admin/invoices/{invoice}/reward', headers=admin_auth_headers,
                       json={'redemption_id': rid}).status_code == 200
    with app.app_context():
        target = loyalty.lock_target('service_invoice', invoice)
        target.trangthai = 'Đã thanh toán'
        loyalty.finalize_payment(target)
        loyalty.finalize_payment(target)
        assert not [row for row in events(caplog) if row['event'] == 'used']
        db.session.commit()
    assert len([row for row in events(caplog) if row['event'] == 'used']) == 1
