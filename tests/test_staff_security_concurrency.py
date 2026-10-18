"""Independent DB connections must not accept the same TOTP/recovery code twice."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
import pytest
from cryptography.fernet import Fernet
from app.extensions import db
from app.models import StaffMFA, StaffRecoveryCode, StaffStepUp, NhanVien
from app.services import staff_security_service as security
from test_attendance_concurrency import concurrent_operations  # noqa: F401


@pytest.mark.parametrize('proof', ['totp', 'recovery'])
def test_concurrent_proof_is_accepted_once(concurrent_operations, monkeypatch, proof):
    app = concurrent_operations
    app.config.update(STAFF_SECURITY_ENABLED=True, STAFF_MFA_ENCRYPTION_KEY=Fernet.generate_key().decode())
    fixed = datetime.utcnow()
    monkeypatch.setattr(security, 'now', lambda: fixed)
    secret = base64.b32encode(b'concurrency-test-key').decode().rstrip('=')
    with app.app_context():
        actor = NhanVien.query.filter_by(role='staff').one()
        db.session.add(StaffMFA(staff_id=actor.manv, secret_ciphertext=security.cipher().encrypt(secret.encode()).decode(),
            enabled_at=fixed, generation=1, last_counter=-1))
        code = '0123-4567-89AB-CDEF'
        db.session.add(StaffRecoveryCode(code_hash=security.digest(f'recovery|{actor.manv}|0123456789ABCDEF'), staff_id=actor.manv, generation=1))
        db.session.commit()
    if proof == 'totp':
        import calendar
        code = security.otp_at(secret, calendar.timegm(fixed.utctimetuple()) // 30)
    barrier = Barrier(2)
    def verify():
        barrier.wait(timeout=10)
        with app.test_client() as client:
            return client.post('/api/me/security/verify', json={'code': code}, headers=app.config['RACE_HEADERS']).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: verify(), range(2)))
    assert sorted(results) == [200, 400], results
    with app.app_context():
        assert StaffStepUp.query.count() == 1
        if proof == 'recovery': assert StaffRecoveryCode.query.one().used_at is not None
