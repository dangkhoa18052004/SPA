"""Đồng bộ giao dịch tiền vào từ SePay (userapi) khi webhook không tới được máy chủ.

Ví dụ chạy trên máy trong mạng nội bộ: SePay không gọi được webhook, nên hệ thống tự hỏi
danh sách giao dịch gần đây và xử lý bằng đúng logic webhook (chống trùng theo mã giao dịch).
Token: SEPAY_API_TOKEN, mặc định dùng SEPAY_API_KEY. Không log token hay nội dung giao dịch đầy đủ.
"""
import threading
import time
from datetime import datetime, timedelta

import requests
from flask import current_app

from ..extensions import db
from ..models import PaymentWebhookEvent

SEPAY_LIST_URL = 'https://my.sepay.vn/userapi/transactions/list'
_lock = threading.Lock()
_last_run = 0.0


def _token():
    return (current_app.config.get('SEPAY_API_TOKEN') or current_app.config.get('SEPAY_API_KEY') or '').strip()


def enabled():
    return bool(current_app.config.get('SEPAY_POLL_ENABLED', True)) and bool(_token())


def fetch_recent(limit=50):
    params = {'limit': limit}
    account = (current_app.config.get('VIETQR_ACCOUNT_NO') or '').strip()
    if account:
        params['account_number'] = account
    response = requests.get(SEPAY_LIST_URL, headers={'Authorization': f'Bearer {_token()}'},
                            params=params, timeout=current_app.config.get('SEPAY_TIMEOUT', 15))
    if response.status_code != 200:
        current_app.logger.warning('[sepay-sync] HTTP %s', response.status_code)
        return []
    return response.json().get('transactions') or []


def to_webhook_payload(tx):
    """Chuyển bản ghi userapi sang dạng payload webhook mà process_sepay_transaction hiểu."""
    amount_in = float(tx.get('amount_in') or 0)
    return {
        'id': tx.get('id'),
        'gateway': tx.get('bank_brand_name'),
        'transactionDate': tx.get('transaction_date'),
        'accountNumber': tx.get('account_number'),
        'content': tx.get('transaction_content') or '',
        'transferType': 'in' if amount_in > 0 else 'out',
        'transferAmount': amount_in,
        'referenceCode': tx.get('reference_number'),
        'source': 'sepay-userapi',
    }


def sync(max_age_hours=48, now=None):
    """Xử lý các giao dịch tiền vào gần đây chưa thấy. Trả số giao dịch mới được xử lý."""
    if not enabled():
        return 0
    from .vietqr_service import process_sepay_transaction
    try:
        transactions = fetch_recent()
    except (requests.RequestException, ValueError) as error:
        current_app.logger.warning('[sepay-sync] lỗi kết nối: %s', type(error).__name__)
        return 0
    now = now or (datetime.utcnow() + timedelta(hours=7))
    seen = {e.external_transaction_id for e in PaymentWebhookEvent.query.filter(
        PaymentWebhookEvent.provider == 'sepay',
        PaymentWebhookEvent.external_transaction_id.in_([str(t.get('id')) for t in transactions if t.get('id')])).all()}
    processed = 0
    for tx in sorted(transactions, key=lambda t: str(t.get('transaction_date') or '')):
        tx_id = str(tx.get('id') or '')
        if not tx_id or tx_id in seen or float(tx.get('amount_in') or 0) <= 0:
            continue
        try:
            when = datetime.strptime(str(tx.get('transaction_date')), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            when = now
        if when < now - timedelta(hours=max_age_hours):
            continue  # giao dịch cũ: không tự đối soát lại
        try:
            result = process_sepay_transaction(to_webhook_payload(tx))
            processed += 1
            current_app.logger.info('[sepay-sync] tx=%s %s', tx_id, result.get('status'))
        except Exception as error:
            db.session.rollback()
            current_app.logger.error('[sepay-sync] tx=%s lỗi xử lý: %s', tx_id, type(error).__name__, exc_info=True)
    return processed


def maybe_sync(min_interval=8):
    """Đồng bộ có giới hạn tần suất (dùng khi khách đang chờ QR). Không chặn nếu đang có lượt khác chạy."""
    global _last_run
    if not enabled() or time.monotonic() - _last_run < min_interval:
        return 0
    if not _lock.acquire(blocking=False):
        return 0
    try:
        _last_run = time.monotonic()
        return sync()
    finally:
        _lock.release()
