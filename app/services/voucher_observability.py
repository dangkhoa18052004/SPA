"""Structured voucher events, without customer data, payloads or credentials.

Success events are buffered in the SQLAlchemy transaction and emitted only after
its outer commit. Rollback discards them, including a failed OTP activation.
"""
from functools import wraps
import json
import logging
from flask import current_app, g, has_app_context, has_request_context
from sqlalchemy import event
from sqlalchemy.orm import Session
from ..extensions import db

_PENDING = 'voucher_observability_events'
_FIELDS = {'source', 'operation', 'reason', 'redemption_id', 'reward_id', 'status', 'error_type'}


def record(event_name, **fields):
    if not has_app_context():
        return
    data = dict(event=event_name, **{key: value for key, value in fields.items() if key in _FIELDS})
    if has_request_context():
        data['request_id'] = g.get('request_id')
    level = 'error' if event_name == 'failed' else 'info'
    logger = current_app.logger.getChild('voucher')
    logger.setLevel(logging.INFO)
    getattr(logger, level)('voucher_event %s', json.dumps(data, sort_keys=True))


def after_commit(event_name, **fields):
    db.session.info.setdefault(_PENDING, []).append((event_name, fields))


@event.listens_for(Session, 'after_commit')
def committed(session):
    if not session.in_nested_transaction():
        for event_name, fields in session.info.pop(_PENDING, []):
            record(event_name, **fields)


@event.listens_for(Session, 'after_rollback')
def rolled_back(session):
    # Losing telemetry on a rolled-back savepoint is preferable to false success.
    session.info.pop(_PENDING, None)


def observe_failure(source, operation):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as error:
                status = getattr(error, 'status', 400 if isinstance(error, ValueError) else 500)
                record('rejected' if status < 500 else 'failed', source=source, operation=operation,
                       status=status, reason=getattr(error, 'reason', 'validation_error' if status < 500 else 'database_or_server_error'),
                       error_type=type(error).__name__)
                raise
        return wrapped
    return decorate
